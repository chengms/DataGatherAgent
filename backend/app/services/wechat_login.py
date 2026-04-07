from __future__ import annotations

import http.cookiejar
import json
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import BASE_DIR, WECHAT_EXPORTER_BASE_URL
from app.core.exceptions import NetworkError, NotFoundError


REPO_ROOT = BASE_DIR.parent
LOCAL_OVERRIDE_PATH = REPO_ROOT / "services.local.json"
LOCAL_EXAMPLE_PATH = REPO_ROOT / "services.local.example.json"
MANIFEST_PATH = REPO_ROOT / "services.manifest.json"
DEFAULT_DEBUG_KEY = "data-gather-agent-wechat-debug"
DEFAULT_SAVE_ENV = "WECHAT_EXPORTER_API_KEY"
TRANSIENT_HTTP_STATUS = {502, 503, 504}


@dataclass
class WechatLoginSession:
    session_id: str
    upstream_sid: str
    opener: urllib.request.OpenerDirector
    base_url: str
    debug_key: str
    known_auth_keys: set[str]
    qrcode_bytes: bytes
    qrcode_content_type: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    status: str = "pending_scan"
    message: str = "请使用微信扫码登录。"
    auth_key_prefix: str | None = None
    qrcode_revision: int = 1


class WechatLoginService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, WechatLoginSession] = {}

    def start_session(self) -> dict[str, Any]:
        self._cleanup_expired_sessions()
        base_url = self._current_base_url()
        debug_key = self._debug_key()
        saved_auth_key = self._saved_auth_key()
        if saved_auth_key and self._auth_key_is_valid(base_url, saved_auth_key):
            return {
                "session_id": None,
                "status": "already_valid",
                "message": "当前公众号登录仍然有效，无需重新扫码。",
                "qrcode_url": None,
                "qrcode_revision": 0,
                "auth_key_prefix": saved_auth_key[:8],
            }

        opener = self._build_opener()
        initial_store = self._fetch_debug_store(opener, base_url, debug_key)
        existing_auth_key = self._select_valid_auth_key(opener, base_url, initial_store)
        if existing_auth_key:
            self._save_auth_key(existing_auth_key)
            return {
                "session_id": None,
                "status": "already_valid",
                "message": "已恢复公众号登录态，无需重新扫码。",
                "qrcode_url": None,
                "qrcode_revision": 0,
                "auth_key_prefix": existing_auth_key[:8],
            }

        upstream_sid = f"{int(time.time() * 1000)}{secrets.randbelow(1000):03d}"
        payload = self._request_json(
            opener,
            f"{base_url}/api/web/login/session/{upstream_sid}",
            method="POST",
        )
        if payload.get("base_resp", {}).get("ret") != 0:
            raise NetworkError("无法创建公众号登录会话", {"response": payload})

        qrcode_bytes, content_type = self._request_bytes(
            opener,
            f"{base_url}/api/web/login/getqrcode?rnd={time.time()}",
        )
        session_id = secrets.token_hex(16)
        session = WechatLoginSession(
            session_id=session_id,
            upstream_sid=upstream_sid,
            opener=opener,
            base_url=base_url,
            debug_key=debug_key,
            known_auth_keys=set(initial_store.keys()),
            qrcode_bytes=qrcode_bytes,
            qrcode_content_type=content_type,
        )
        with self._lock:
            self._sessions[session_id] = session
        return self._serialize_session(session, include_qrcode=True)

    def poll_session(self, session_id: str) -> dict[str, Any]:
        session = self._require_session(session_id)
        if self._session_expired(session):
            session.status = "expired"
            session.message = "二维码登录会话已过期，请重新生成。"
            return self._serialize_session(session, include_qrcode=True)

        if session.status in {"success", "failed", "expired"}:
            return self._serialize_session(session, include_qrcode=True)

        payload = self._request_json(
            session.opener,
            f"{session.base_url}/api/web/login/scan",
        )
        if payload.get("base_resp", {}).get("ret") != 0:
            raise NetworkError("公众号扫码状态检查失败", {"response": payload})

        status = int(payload.get("status", 0))
        session.updated_at = time.time()
        if status == 0:
            session.status = "pending_scan"
            session.message = "二维码已就绪，请使用微信扫码。"
        elif status == 1:
            self._complete_login(session)
        elif status in {2, 3}:
            qrcode_bytes, content_type = self._request_bytes(
                session.opener,
                f"{session.base_url}/api/web/login/getqrcode?rnd={time.time()}",
            )
            session.qrcode_bytes = qrcode_bytes
            session.qrcode_content_type = content_type
            session.qrcode_revision += 1
            session.status = "pending_scan"
            session.message = "二维码已刷新，请重新扫码。"
        elif status in {4, 6}:
            session.status = "scanned_wait_confirm"
            session.message = "已检测到扫码，请在微信里确认登录。"
        elif status == 5:
            session.status = "failed"
            session.message = "当前微信账号不支持公众号登录。"
        else:
            session.status = "pending_scan"
            session.message = "正在等待扫码确认。"
        return self._serialize_session(session, include_qrcode=True)

    def get_qrcode(self, session_id: str) -> tuple[bytes, str]:
        session = self._require_session(session_id)
        return session.qrcode_bytes, session.qrcode_content_type

    def discard_session(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def _complete_login(self, session: WechatLoginSession) -> None:
        payload = self._request_json(
            session.opener,
            f"{session.base_url}/api/web/login/bizlogin",
            method="POST",
        )
        if payload.get("err"):
            session.status = "failed"
            session.message = str(payload["err"])
            return

        auth_key = self._get_cookie_value(session.opener, "auth-key")
        if not auth_key:
            current_store = self._fetch_debug_store(session.opener, session.base_url, session.debug_key)
            auth_key = self._select_valid_auth_key(session.opener, session.base_url, current_store)
        if not auth_key:
            session.status = "failed"
            session.message = "登录成功，但未能提取 auth-key。"
            return

        self._ensure_authkey_valid(session.opener, session.base_url, auth_key)
        self._save_auth_key(auth_key)
        session.status = "success"
        session.message = "公众号登录成功，已写入本地配置。"
        session.auth_key_prefix = auth_key[:8]

    def _serialize_session(self, session: WechatLoginSession, *, include_qrcode: bool) -> dict[str, Any]:
        payload = {
            "session_id": session.session_id,
            "status": session.status,
            "message": session.message,
            "qrcode_revision": session.qrcode_revision,
            "auth_key_prefix": session.auth_key_prefix,
        }
        payload["qrcode_url"] = (
            f"/api/discovery/wechat-login/sessions/{session.session_id}/qrcode"
            if include_qrcode
            else None
        )
        return payload

    def _require_session(self, session_id: str) -> WechatLoginSession:
        with self._lock:
            session = self._sessions.get(session_id)
        if session is None:
            raise NotFoundError("Wechat login session not found", "WechatLoginSession")
        return session

    def _session_expired(self, session: WechatLoginSession, *, ttl_seconds: int = 300) -> bool:
        return (time.time() - session.created_at) > ttl_seconds

    def _cleanup_expired_sessions(self) -> None:
        with self._lock:
            expired = [session_id for session_id, session in self._sessions.items() if self._session_expired(session)]
            for session_id in expired:
                self._sessions.pop(session_id, None)

    def _request_json(
        self,
        opener: urllib.request.OpenerDirector,
        url: str,
        *,
        method: str = "GET",
        body: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        data = None
        headers: dict[str, str] = {}
        if body is not None:
            data = urllib.parse.urlencode(body).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        request = urllib.request.Request(url, data=data, method=method, headers=headers)
        with self._open_with_retry(opener, request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def _request_bytes(self, opener: urllib.request.OpenerDirector, url: str) -> tuple[bytes, str]:
        with self._open_with_retry(opener, url, timeout=30) as response:
            body = response.read()
            media_type = response.headers.get_content_type() or "image/png"
            return body, media_type

    def _fetch_debug_store(
        self,
        opener: urllib.request.OpenerDirector,
        base_url: str,
        debug_key: str,
    ) -> dict[str, dict[str, Any]]:
        request = urllib.request.Request(
            f"{base_url.rstrip('/')}/api/_debug?key={urllib.parse.quote(debug_key)}",
            method="GET",
        )
        with self._open_with_retry(opener, request, timeout=30) as response:
            raw = response.read().decode("utf-8")
        try:
            payload = json.loads(raw)
        except ValueError as exc:
            raise NetworkError("公众号调试接口返回了无效响应", {"response": raw[:200]}) from exc
        if not isinstance(payload, dict):
            raise NetworkError("公众号调试接口不可用", {"response": raw[:200]})
        return {str(key): value for key, value in payload.items() if isinstance(value, dict) and "token" in value}

    def _ensure_authkey_valid(
        self,
        opener: urllib.request.OpenerDirector,
        base_url: str,
        auth_key: str,
    ) -> None:
        request = urllib.request.Request(
            f"{base_url.rstrip('/')}/api/public/v1/authkey",
            headers={"X-Auth-Key": auth_key},
            method="GET",
        )
        with self._open_with_retry(opener, request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("code") != 0:
            raise NetworkError("公众号登录校验失败", {"response": payload})

    def _select_valid_auth_key(
        self,
        opener: urllib.request.OpenerDirector,
        base_url: str,
        store: dict[str, dict[str, Any]],
    ) -> str | None:
        for auth_key in reversed(list(store.keys())):
            try:
                self._ensure_authkey_valid(opener, base_url, auth_key)
                return auth_key
            except Exception:
                continue
        return None

    def _auth_key_is_valid(self, base_url: str, auth_key: str) -> bool:
        opener = self._build_opener()
        try:
            self._ensure_authkey_valid(opener, base_url, auth_key)
            return True
        except Exception:
            return False

    def _build_opener(self) -> urllib.request.OpenerDirector:
        cookie_jar = http.cookiejar.CookieJar()
        return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

    def _get_cookie_value(self, opener: urllib.request.OpenerDirector, name: str) -> str | None:
        for handler in opener.handlers:
            if isinstance(handler, urllib.request.HTTPCookieProcessor):
                for cookie in handler.cookiejar:
                    if cookie.name == name:
                        return cookie.value
        return None

    def _open_with_retry(
        self,
        opener: urllib.request.OpenerDirector,
        request: urllib.request.Request | str,
        *,
        timeout: int,
        retry_window_seconds: float = 45.0,
        retry_delay_seconds: float = 1.5,
    ):
        deadline = time.time() + retry_window_seconds
        last_error: BaseException | None = None
        while True:
            try:
                return opener.open(request, timeout=timeout)
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
                if not self._is_transient_http_error(exc):
                    raise NetworkError("公众号服务当前不可达", {"reason": str(exc)}) from exc
                last_error = exc
                if time.time() >= deadline:
                    raise NetworkError("公众号服务启动中，请稍后重试", {"reason": str(last_error)}) from exc
                time.sleep(retry_delay_seconds)

    def _is_transient_http_error(self, exc: BaseException) -> bool:
        if isinstance(exc, TimeoutError):
            return True
        if isinstance(exc, urllib.error.HTTPError):
            return exc.code in TRANSIENT_HTTP_STATUS
        return isinstance(exc, urllib.error.URLError)

    def _current_base_url(self) -> str:
        payload = self._load_local_config()
        backend_env = payload.get("services", {}).get("backend", {}).get("env", {})
        return str(backend_env.get("WECHAT_EXPORTER_BASE_URL", WECHAT_EXPORTER_BASE_URL) or WECHAT_EXPORTER_BASE_URL).rstrip("/")

    def _saved_auth_key(self) -> str:
        payload = self._load_local_config()
        return str(payload.get("global_env", {}).get(DEFAULT_SAVE_ENV, "") or "").strip()

    def _save_auth_key(self, auth_key: str) -> None:
        payload = self._load_local_config()
        payload.setdefault("global_env", {})
        payload["global_env"][DEFAULT_SAVE_ENV] = auth_key
        LOCAL_OVERRIDE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _debug_key(self) -> str:
        if not MANIFEST_PATH.exists():
            return DEFAULT_DEBUG_KEY
        try:
            payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return DEFAULT_DEBUG_KEY
        for service in payload.get("services", []):
            if service.get("name") != "wechat_exporter":
                continue
            env = service.get("env", {})
            return str(env.get("DEBUG_KEY") or DEFAULT_DEBUG_KEY)
        return DEFAULT_DEBUG_KEY

    def _load_local_config(self) -> dict[str, Any]:
        source = LOCAL_OVERRIDE_PATH if LOCAL_OVERRIDE_PATH.exists() else LOCAL_EXAMPLE_PATH
        payload = json.loads(source.read_text(encoding="utf-8"))
        payload.setdefault("global_env", {})
        payload.setdefault("services", {})
        return payload


wechat_login_service = WechatLoginService()

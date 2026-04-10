from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import BASE_DIR
from app.core.exceptions import NetworkError, NotFoundError


REPO_ROOT = BASE_DIR.parent
RUNTIME_DIR = REPO_ROOT / ".runtime" / "platform_login"
DEFAULT_MEDIACRAWLER_REPO = REPO_ROOT / "external_tools" / "MediaCrawler"
SUPPORTED_PLATFORMS = {"xhs", "weibo", "douyin", "bilibili"}


@dataclass
class PlatformLoginSession:
    session_id: str
    platform: str
    process: subprocess.Popen[str]
    status_file: Path
    started_at: float


class PlatformLoginService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, PlatformLoginSession] = {}

    def start_session(self, platform: str) -> dict[str, Any]:
        normalized = str(platform).strip().lower()
        if normalized not in SUPPORTED_PLATFORMS:
            raise NotFoundError(f"Unsupported platform login: {platform}", "PlatformLogin")
        self._cleanup_finished_sessions()
        session_id = f"{normalized}-{int(time.time() * 1000)}"
        status_file = RUNTIME_DIR / f"{session_id}.json"
        command = [
            sys.executable,
            "scripts/mediacrawler_terminal_login.py",
            "--platform",
            normalized,
            "--login-type",
            "qrcode",
            "--headless",
            "true",
            "--status-file",
            str(status_file),
            "--repo",
            str(DEFAULT_MEDIACRAWLER_REPO),
        ]
        process = subprocess.Popen(
            command,
            cwd=REPO_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            **self._windows_background_kwargs(),
        )
        session = PlatformLoginSession(
            session_id=session_id,
            platform=normalized,
            process=process,
            status_file=status_file,
            started_at=time.time(),
        )
        with self._lock:
            self._sessions[session_id] = session
        return self.poll_session(session_id)

    def poll_session(self, session_id: str) -> dict[str, Any]:
        session = self._require_session(session_id)
        payload = self._load_status_file(session)
        if payload:
            return self._serialize_payload(session, payload)

        exit_code = session.process.poll()
        if exit_code is None:
            return {
                "session_id": session.session_id,
                "platform": session.platform,
                "status": "starting",
                "message": "正在准备无头登录会话。",
                "qrcode_data_url": None,
                "auth_key_prefix": None,
            }
        raise NetworkError("平台登录进程已结束，但未返回可用状态", {"platform": session.platform, "exit_code": exit_code})

    def discard_session(self, session_id: str) -> None:
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is None:
            return
        if session.process.poll() is None:
            session.process.terminate()
            try:
                session.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                session.process.kill()
        if session.status_file.exists():
            try:
                session.status_file.unlink()
            except OSError:
                pass

    def _serialize_payload(self, session: PlatformLoginSession, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "session_id": session.session_id,
            "platform": session.platform,
            "status": str(payload.get("status") or "starting"),
            "message": str(payload.get("message") or "正在准备无头登录会话。"),
            "qrcode_data_url": payload.get("qrcode_data_url"),
            "auth_key_prefix": payload.get("auth_key_prefix"),
        }

    def _load_status_file(self, session: PlatformLoginSession) -> dict[str, Any] | None:
        if not session.status_file.exists():
            return None
        try:
            payload = json.loads(session.status_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def _require_session(self, session_id: str) -> PlatformLoginSession:
        with self._lock:
            session = self._sessions.get(session_id)
        if session is None:
            raise NotFoundError("Platform login session not found", "PlatformLoginSession")
        return session

    def _cleanup_finished_sessions(self, *, ttl_seconds: int = 600) -> None:
        with self._lock:
            stale_ids = [
                session_id
                for session_id, session in self._sessions.items()
                if session.process.poll() is not None or (time.time() - session.started_at) > ttl_seconds
            ]
        for session_id in stale_ids:
            self.discard_session(session_id)

    def _windows_background_kwargs(self) -> dict[str, Any]:
        if os.name != "nt":
            return {}
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        return {
            "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
            "startupinfo": startupinfo,
        }


platform_login_service = PlatformLoginService()

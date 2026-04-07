from __future__ import annotations

import json
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import BASE_DIR
from app.services.workflow import WorkflowService


REPO_ROOT = BASE_DIR.parent
MANIFEST_PATH = REPO_ROOT / "services.manifest.json"
LOCAL_OVERRIDE_PATH = REPO_ROOT / "services.local.json"
LOCAL_EXAMPLE_PATH = REPO_ROOT / "services.local.example.json"

PLATFORM_SERVICE_MAP = {
    "wechat": "wechat_exporter",
    "xiaohongshu": "mediacrawler_xhs",
    "weibo": "mediacrawler_xhs",
    "douyin": "mediacrawler_xhs",
    "bilibili": "mediacrawler_xhs",
}

PLATFORM_LOGIN_CHECK = {
    "wechat": ["scripts/wechat_login_status.py"],
    "xiaohongshu": ["scripts/mediacrawler_login_status.py", "--platforms", "xhs"],
    "weibo": ["scripts/mediacrawler_login_status.py", "--platforms", "weibo"],
    "douyin": ["scripts/mediacrawler_login_status.py", "--platforms", "douyin"],
    "bilibili": ["scripts/mediacrawler_login_status.py", "--platforms", "bilibili"],
}

PLATFORM_CREDENTIAL_KEYS = {
    "wechat": ("global_env", "WECHAT_EXPORTER_API_KEY"),
    "xiaohongshu": ("service:mediacrawler_xhs", "XHS_MEDIACRAWLER_COOKIES"),
    "weibo": ("service:mediacrawler_xhs", "WEIBO_MEDIACRAWLER_COOKIES"),
    "douyin": ("service:mediacrawler_xhs", "DY_MEDIACRAWLER_COOKIES"),
    "bilibili": ("service:mediacrawler_xhs", "BILI_MEDIACRAWLER_COOKIES"),
}

SERVICE_LABELS = {
    "wechat_exporter": "公众号服务",
    "mediacrawler_xhs": "MediaCrawler 服务",
}

_CACHE_LOCK = threading.Lock()
_CACHE: dict[str, tuple[float, Any]] = {}


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_local_config() -> dict[str, Any]:
    source = LOCAL_OVERRIDE_PATH if LOCAL_OVERRIDE_PATH.exists() else LOCAL_EXAMPLE_PATH
    payload = _load_json(source)
    payload.setdefault("global_env", {})
    payload.setdefault("services", {})
    return payload


def _load_manifest() -> dict[str, dict[str, Any]]:
    payload = _load_json(MANIFEST_PATH)
    return {str(service["name"]): service for service in payload.get("services", [])}


def _cached(key: str, ttl_seconds: int, producer, *, force_refresh: bool = False):
    now = time.time()
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and not force_refresh and cached[0] > now:
            return deepcopy(cached[1])
    value = producer()
    with _CACHE_LOCK:
        _CACHE[key] = (now + ttl_seconds, deepcopy(value))
    return value


def _is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _probe_healthcheck(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=1.5) as response:
            return 200 <= response.status < 300
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return False


def _resolve_service_state(service: dict[str, Any]) -> tuple[str, bool]:
    healthcheck_url = str(service.get("healthcheck_url") or "").strip()
    ready_port = service.get("ready_port")
    if healthcheck_url:
        online = _probe_healthcheck(healthcheck_url)
        return ("online" if online else "offline"), online
    if ready_port:
        online = _is_port_in_use(int(ready_port))
        return ("online" if online else "offline"), online
    return "unknown", False


def _service_runtime_map(*, force_refresh: bool = False) -> dict[str, dict[str, Any]]:
    def produce() -> dict[str, dict[str, Any]]:
        services = _load_manifest()
        runtime: dict[str, dict[str, Any]] = {}
        for name, service in services.items():
            status, online = _resolve_service_state(service)
            runtime[name] = {
                "service_name": name,
                "service_label": SERVICE_LABELS.get(name, name),
                "service_status": status,
                "service_online": online,
            }
        return runtime

    return _cached("service_runtime", 10, produce, force_refresh=force_refresh)


def _credential_present(platform: str, local_config: dict[str, Any]) -> bool:
    scope, key = PLATFORM_CREDENTIAL_KEYS.get(platform, ("", ""))
    if scope == "global_env":
        value = local_config.get("global_env", {}).get(key)
        return bool(str(value or "").strip())
    if scope.startswith("service:"):
        service_name = scope.split(":", 1)[1]
        value = local_config.get("services", {}).get(service_name, {}).get("env", {}).get(key)
        return bool(str(value or "").strip())
    return False


def _login_check_ttl(platform: str, manifest: dict[str, dict[str, Any]]) -> int:
    service_name = PLATFORM_SERVICE_MAP.get(platform)
    service = manifest.get(service_name or "", {})
    interval = service.get("login_check", {}).get("interval_seconds", 120)
    try:
        return max(30, int(interval))
    except (TypeError, ValueError):
        return 120


def _run_login_check(platform: str, *, timeout_seconds: int = 45) -> tuple[str, str | None]:
    argv = PLATFORM_LOGIN_CHECK.get(platform)
    if not argv:
        return "not_required", None

    completed = subprocess.run(
        [sys.executable, *argv],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=timeout_seconds,
    )
    stdout = completed.stdout.strip() or "{}"
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        reason = stdout[:200] or completed.stderr.strip()[:200] or "invalid_json"
        return "unknown", reason

    if bool(payload.get("ok")):
        return "valid", str(payload.get("reason") or "ok")

    reason = str(payload.get("reason") or "login_check_failed")
    if reason in {"missing_api_key", "missing_cookies"}:
        return "missing", reason
    if reason == "service_unreachable":
        return "unknown", reason
    return "invalid", reason


def _login_runtime_map(
    service_runtime: dict[str, dict[str, Any]],
    *,
    force_refresh: bool = False,
) -> dict[str, dict[str, str | None]]:
    manifest = _load_manifest()
    local_config = _load_local_config()
    platforms = list(WorkflowService.PLATFORM_STRATEGIES.keys())
    runtime: dict[str, dict[str, str | None]] = {}

    for platform in platforms:
        service_name = PLATFORM_SERVICE_MAP.get(platform)
        service_online = bool(service_runtime.get(service_name or "", {}).get("service_online"))
        credential_present = _credential_present(platform, local_config)
        ttl = _login_check_ttl(platform, manifest)
        cache_key = f"login_status:{platform}"

        if not service_online:
            runtime[platform] = {
                "login_status": "unknown" if credential_present else "missing",
                "login_reason": "service_offline" if credential_present else "missing_credentials",
            }
            continue

        def produce(platform_name: str = platform) -> dict[str, str | None]:
            status, reason = _run_login_check(platform_name)
            return {"login_status": status, "login_reason": reason}

        runtime[platform] = _cached(cache_key, ttl, produce, force_refresh=force_refresh)
    return runtime


def _status_summary(platform: str, runtime_state: str, login_reason: str | None, service_label: str | None) -> str:
    if runtime_state == "ready":
        return "默认抓取链路已通过服务与登录检查，可直接执行实时任务。"
    if runtime_state == "service_offline":
        return f"{service_label or '关联服务'}未启动，当前平台暂时不能执行默认抓取链路。"
    if runtime_state == "login_required":
        return "尚未配置登录信息，补齐登录后才能执行默认抓取链路。"
    if runtime_state == "login_expired":
        return _humanize_login_reason(platform, login_reason)
    if runtime_state == "attention":
        return "服务已在线，但登录状态暂时无法确认，建议重新复检或重新登录。"
    if runtime_state == "capability_missing":
        return "发现或抓取能力尚未完整接入。"
    return "当前状态未知。"


def _humanize_login_reason(platform: str, reason: str | None) -> str:
    mapping = {
        "missing_api_key": "未发现公众号登录信息，请先重新登录。",
        "missing_cookies": "未发现平台登录 Cookie，请先重新登录。",
        "service_unreachable": "服务未在线，暂时无法校验登录状态。",
        "cookie_invalid": "登录信息已过期，请重新扫码登录。",
        "auth_invalid": "公众号登录信息已失效，请重新扫码登录。",
    }
    if reason in mapping:
        return mapping[reason]
    if reason and reason.startswith("xhs:"):
        return "小红书登录信息已过期，请重新扫码登录。"
    if reason and reason.startswith("weibo:"):
        return "微博登录信息已过期，请重新扫码登录。"
    if reason and reason.startswith("douyin:"):
        return "抖音登录信息已过期，请重新扫码登录。"
    if reason and reason.startswith("bilibili:"):
        return "B站登录信息已过期，请重新扫码登录。"
    return f"{platform} 登录状态异常：{reason or 'unknown'}"


def list_platform_status(*, force_refresh: bool = False) -> dict[str, dict[str, Any]]:
    service_runtime = _service_runtime_map(force_refresh=force_refresh)
    login_runtime = _login_runtime_map(service_runtime, force_refresh=force_refresh)
    strategies = WorkflowService.PLATFORM_STRATEGIES
    statuses: dict[str, dict[str, Any]] = {}
    checked_at = datetime.now(UTC).isoformat()

    for platform, (discovery_source, fetch_source) in strategies.items():
        service_name = PLATFORM_SERVICE_MAP.get(platform)
        service_meta = service_runtime.get(service_name or "", {})
        service_online = bool(service_meta.get("service_online"))
        service_status = str(service_meta.get("service_status") or "unknown")
        login_meta = login_runtime.get(platform, {"login_status": "not_required", "login_reason": None})
        login_status = str(login_meta.get("login_status") or "not_required")
        login_reason = login_meta.get("login_reason")
        login_required = platform in PLATFORM_LOGIN_CHECK

        if not service_online:
            runtime_state = "service_offline"
            runtime_ready = False
        elif login_required and login_status == "missing":
            runtime_state = "login_required"
            runtime_ready = False
        elif login_required and login_status == "invalid":
            runtime_state = "login_expired"
            runtime_ready = False
        elif login_required and login_status == "unknown":
            runtime_state = "attention"
            runtime_ready = False
        else:
            runtime_state = "ready"
            runtime_ready = True

        statuses[platform] = {
            "platform": platform,
            "discovery_source": discovery_source,
            "fetch_source": fetch_source,
            "service_name": service_name,
            "service_label": service_meta.get("service_label"),
            "service_online": service_online,
            "service_status": service_status,
            "login_required": login_required,
            "login_status": login_status,
            "login_reason": login_reason,
            "runtime_state": runtime_state,
            "runtime_ready": runtime_ready,
            "status_summary": _status_summary(platform, runtime_state, login_reason, service_meta.get("service_label")),
            "last_checked_at": checked_at,
        }
    return statuses

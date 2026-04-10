from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.core.config import BASE_DIR


REPO_ROOT = BASE_DIR.parent
LOCAL_OVERRIDE_PATH = Path(os.getenv("DATA_GATHER_SERVICE_CONFIG_PATH", REPO_ROOT / "services.local.json"))
LOCAL_EXAMPLE_PATH = Path(os.getenv("DATA_GATHER_SERVICE_CONFIG_EXAMPLE_PATH", REPO_ROOT / "services.local.example.json"))

MEDIACRAWLER_DEFAULTS = {
    "browser_mode": "safe",
    "browser_headless": True,
    "max_sleep_sec": 4,
    "max_concurrency": 1,
    "browser_path": "",
}

MEDIACRAWLER_PLATFORM_SCOPE = ["xiaohongshu", "weibo", "douyin", "bilibili"]
GLOBAL_ENV_KEY_MAP = {
    "browser_mode": "DATA_GATHER_BROWSER_MODE",
    "browser_headless": "DATA_GATHER_BROWSER_HEADLESS",
    "max_sleep_sec": "DATA_GATHER_CRAWLER_MAX_SLEEP_SEC",
    "max_concurrency": "DATA_GATHER_CRAWLER_MAX_CONCURRENCY",
    "browser_path": "DATA_GATHER_BROWSER_PATH",
}


def _config_source_path() -> Path:
    return LOCAL_OVERRIDE_PATH if LOCAL_OVERRIDE_PATH.exists() else LOCAL_EXAMPLE_PATH


def _load_local_config() -> dict[str, Any]:
    payload = json.loads(_config_source_path().read_text(encoding="utf-8"))
    payload.setdefault("global_env", {})
    payload.setdefault("services", {})
    return payload


def _save_local_config(payload: dict[str, Any]) -> None:
    LOCAL_OVERRIDE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "f", "no", "n", "off"}:
        return False
    return default


def _coerce_int(value: Any, default: int, *, minimum: int = 1, maximum: int = 30) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(parsed, maximum))


def get_mediacrawler_settings() -> dict[str, Any]:
    payload = _load_local_config()
    global_env = payload.get("global_env", {})
    settings = {
        "platform": "mediacrawler",
        "display_name": "MediaCrawler 安全设置",
        "platform_scope": list(MEDIACRAWLER_PLATFORM_SCOPE),
        "browser_mode": str(global_env.get(GLOBAL_ENV_KEY_MAP["browser_mode"], MEDIACRAWLER_DEFAULTS["browser_mode"]) or MEDIACRAWLER_DEFAULTS["browser_mode"]).strip().lower(),
        "browser_headless": _coerce_bool(global_env.get(GLOBAL_ENV_KEY_MAP["browser_headless"]), MEDIACRAWLER_DEFAULTS["browser_headless"]),
        "max_sleep_sec": _coerce_int(global_env.get(GLOBAL_ENV_KEY_MAP["max_sleep_sec"]), MEDIACRAWLER_DEFAULTS["max_sleep_sec"], minimum=1, maximum=15),
        "max_concurrency": _coerce_int(global_env.get(GLOBAL_ENV_KEY_MAP["max_concurrency"]), MEDIACRAWLER_DEFAULTS["max_concurrency"], minimum=1, maximum=4),
        "browser_path": str(global_env.get(GLOBAL_ENV_KEY_MAP["browser_path"], MEDIACRAWLER_DEFAULTS["browser_path"]) or "").strip(),
    }
    if settings["browser_mode"] not in {"safe", "cdp", "standard"}:
        settings["browser_mode"] = MEDIACRAWLER_DEFAULTS["browser_mode"]
    return settings


def update_mediacrawler_settings(payload: dict[str, Any]) -> dict[str, Any]:
    current = get_mediacrawler_settings()
    merged = {
        **current,
        "browser_mode": str(payload.get("browser_mode", current["browser_mode"]) or current["browser_mode"]).strip().lower(),
        "browser_headless": _coerce_bool(payload.get("browser_headless", current["browser_headless"]), current["browser_headless"]),
        "max_sleep_sec": _coerce_int(payload.get("max_sleep_sec", current["max_sleep_sec"]), current["max_sleep_sec"], minimum=1, maximum=15),
        "max_concurrency": _coerce_int(payload.get("max_concurrency", current["max_concurrency"]), current["max_concurrency"], minimum=1, maximum=4),
        "browser_path": str(payload.get("browser_path", current["browser_path"]) or "").strip(),
    }
    if merged["browser_mode"] not in {"safe", "cdp", "standard"}:
        merged["browser_mode"] = MEDIACRAWLER_DEFAULTS["browser_mode"]

    local_config = _load_local_config()
    global_env = local_config.setdefault("global_env", {})
    global_env[GLOBAL_ENV_KEY_MAP["browser_mode"]] = merged["browser_mode"]
    global_env[GLOBAL_ENV_KEY_MAP["browser_headless"]] = "true" if merged["browser_headless"] else "false"
    global_env[GLOBAL_ENV_KEY_MAP["max_sleep_sec"]] = str(merged["max_sleep_sec"])
    global_env[GLOBAL_ENV_KEY_MAP["max_concurrency"]] = str(merged["max_concurrency"])
    global_env[GLOBAL_ENV_KEY_MAP["browser_path"]] = merged["browser_path"]
    _save_local_config(local_config)
    return get_mediacrawler_settings()


def build_mediacrawler_runtime_cli_args() -> list[str]:
    settings = get_mediacrawler_settings()
    return [
        "--browser-mode",
        settings["browser_mode"],
        "--headless",
        "true" if settings["browser_headless"] else "false",
        "--max-sleep-sec",
        str(settings["max_sleep_sec"]),
        "--max-concurrency",
        str(settings["max_concurrency"]),
        "--browser-path",
        settings["browser_path"],
    ]

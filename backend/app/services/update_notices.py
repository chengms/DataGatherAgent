from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import BASE_DIR


REPO_ROOT = BASE_DIR.parent
UPDATE_STATUS_PATH = REPO_ROOT / ".runtime" / "service_updates.json"


def list_update_notices() -> dict[str, Any]:
    if not UPDATE_STATUS_PATH.exists():
        return {"checked_at": None, "items": []}
    try:
        with UPDATE_STATUS_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {"checked_at": None, "items": []}
    if not isinstance(payload, dict):
        return {"checked_at": None, "items": []}
    items = payload.get("items")
    if not isinstance(items, list):
        items = []
    payload["items"] = items
    return payload

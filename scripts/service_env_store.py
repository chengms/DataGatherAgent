#!/usr/bin/env python3
"""Helpers for reading and updating services.local.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
LOCAL_OVERRIDE_PATH = ROOT_DIR / "services.local.json"
LOCAL_EXAMPLE_PATH = ROOT_DIR / "services.local.example.json"


def load_local_config() -> dict[str, Any]:
    source = LOCAL_OVERRIDE_PATH if LOCAL_OVERRIDE_PATH.exists() else LOCAL_EXAMPLE_PATH
    with source.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    payload.setdefault("global_env", {})
    payload.setdefault("services", {})
    return payload


def save_local_config(payload: dict[str, Any]) -> None:
    LOCAL_OVERRIDE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def set_global_env(name: str, value: str) -> None:
    payload = load_local_config()
    payload.setdefault("global_env", {})
    payload["global_env"][name] = value
    save_local_config(payload)


def set_service_env(service_name: str, name: str, value: str) -> None:
    payload = load_local_config()
    payload.setdefault("services", {})
    service = payload["services"].setdefault(service_name, {})
    service_env = service.setdefault("env", {})
    service_env[name] = value
    save_local_config(payload)

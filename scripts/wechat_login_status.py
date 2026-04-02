#!/usr/bin/env python3
"""Check whether the managed wechat-article-exporter login is still valid."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import service_env_store


def main() -> int:
    payload = service_env_store.load_local_config()
    global_env = payload.get("global_env", {})
    backend_env = payload.get("services", {}).get("backend", {}).get("env", {})
    auth_key = str(global_env.get("WECHAT_EXPORTER_API_KEY", "")).strip()
    base_url = str(backend_env.get("WECHAT_EXPORTER_BASE_URL", "http://127.0.0.1:3000")).rstrip("/")
    if not auth_key:
        print(json.dumps({"ok": False, "reason": "missing_api_key"}, ensure_ascii=False))
        return 0

    request = urllib.request.Request(
        f"{base_url}/api/public/v1/authkey",
        headers={"X-Auth-Key": auth_key},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError:
        print(json.dumps({"ok": False, "reason": "service_unreachable"}, ensure_ascii=False))
        return 0

    ok = isinstance(data, dict) and data.get("code") == 0
    print(
        json.dumps(
            {
                "ok": ok,
                "reason": "ok" if ok else str(data.get("msg") or "auth_invalid"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Terminal QR-code login flow for the managed wechat-article-exporter service."""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import secrets
import time
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path

from service_env_store import ROOT_DIR, set_global_env
from terminal_qr import render_terminal_qr


DEFAULT_BASE_URL = "http://127.0.0.1:3000"
DEFAULT_DEBUG_KEY = "data-gather-agent-wechat-debug"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Log into the managed wechat-article-exporter service from the terminal.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--save-env", default="WECHAT_EXPORTER_API_KEY")
    parser.add_argument("--debug-key", default=DEFAULT_DEBUG_KEY)
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    return parser.parse_args()


def build_opener() -> urllib.request.OpenerDirector:
    cookie_jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))


def request_json(
    opener: urllib.request.OpenerDirector,
    url: str,
    *,
    method: str = "GET",
    body: dict[str, str] | None = None,
) -> dict:
    data = None
    headers: dict[str, str] = {}
    if body is not None:
        data = urllib.parse.urlencode(body).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    with opener.open(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def request_bytes(opener: urllib.request.OpenerDirector, url: str) -> bytes:
    with opener.open(url, timeout=30) as response:
        return response.read()


def fetch_debug_store(opener: urllib.request.OpenerDirector, base_url: str, debug_key: str) -> dict[str, dict] | None:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/_debug?key={urllib.parse.quote(debug_key)}",
        method="GET",
    )
    with opener.open(request, timeout=30) as response:
        raw = response.read().decode("utf-8")
    try:
        payload = json.loads(raw)
    except ValueError:
        return None
    if isinstance(payload, dict):
        return {str(key): value for key, value in payload.items() if isinstance(value, dict) and "token" in value}
    return None


def get_cookie_value(opener: urllib.request.OpenerDirector, name: str) -> str | None:
    for handler in opener.handlers:
        if isinstance(handler, urllib.request.HTTPCookieProcessor):
            for cookie in handler.cookiejar:
                if cookie.name == name:
                    return cookie.value
    return None


def ensure_authkey_valid(opener: urllib.request.OpenerDirector, base_url: str, auth_key: str) -> None:
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/public/v1/authkey",
        headers={"X-Auth-Key": auth_key},
        method="GET",
    )
    with opener.open(req, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("code") != 0:
        raise RuntimeError(f"wechat exporter auth-key validation failed: {payload}")


def select_valid_auth_key(
    opener: urllib.request.OpenerDirector,
    base_url: str,
    store: dict[str, dict],
) -> str | None:
    for auth_key in reversed(list(store.keys())):
        try:
            ensure_authkey_valid(opener, base_url, auth_key)
            return auth_key
        except Exception:
            continue
    return None


def run_login(base_url: str, save_env: str, debug_key: str, poll_seconds: float, timeout_seconds: int) -> int:
    opener = build_opener()
    base_url = base_url.rstrip("/")
    sid = f"{int(time.time() * 1000)}{secrets.randbelow(1000):03d}"
    initial_store = fetch_debug_store(opener, base_url, debug_key)
    if initial_store is None:
        raise RuntimeError(
            "wechat exporter debug store is unavailable. Restart the service with DEBUG_KEY configured, then retry login."
        )
    existing_auth_key = select_valid_auth_key(opener, base_url, initial_store)
    if existing_auth_key:
        set_global_env(save_env, existing_auth_key)
        print(
            json.dumps(
                {
                    "status": "ok",
                    "saved_env": save_env,
                    "auth_key_prefix": existing_auth_key[:8],
                    "base_url": base_url,
                    "login_mode": "existing_session",
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        return 0
    known_auth_keys = set(initial_store.keys())

    start = request_json(
        opener,
        f"{base_url}/api/web/login/session/{sid}",
        method="POST",
    )
    if start.get("base_resp", {}).get("ret") != 0:
        raise RuntimeError(f"unable to start wechat login session: {start}")

    qrcode_bytes = request_bytes(opener, f"{base_url}/api/web/login/getqrcode?rnd={time.time()}")
    try:
        render_terminal_qr(qrcode_bytes, "Scan this QR code with WeChat Official Accounts:")
        login_mode = "session_qr"
    except Exception:
        login_mode = "browser_qr"
        print(
            f"Terminal QR rendering is unavailable. Open {base_url}/dashboard/account and use the page login QR code.",
            flush=True,
        )

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if login_mode == "session_qr":
            status_payload = request_json(opener, f"{base_url}/api/web/login/scan")
            if status_payload.get("base_resp", {}).get("ret") != 0:
                raise RuntimeError(f"wechat login status request failed: {status_payload}")
            status = status_payload.get("status")
            if status == 1:
                break
            if status in {4, 6}:
                print("Scan detected. Confirm the login in WeChat.", flush=True)
            elif status in {2, 3}:
                qrcode_bytes = request_bytes(opener, f"{base_url}/api/web/login/getqrcode?rnd={time.time()}")
                try:
                    render_terminal_qr(qrcode_bytes, "WeChat QR code refreshed. Scan again:")
                except Exception:
                    print(
                        f"QR refresh is available on {base_url}/dashboard/account .",
                        flush=True,
                    )
                    login_mode = "browser_qr"
            elif status == 5:
                raise RuntimeError("The WeChat account is not eligible for public account login.")
        else:
            current_store = fetch_debug_store(opener, base_url, debug_key)
            if current_store is None:
                raise RuntimeError(
                    "wechat exporter debug store is unavailable. Restart the service with DEBUG_KEY configured, then retry login."
                )
            new_auth_keys = [key for key in current_store if key not in known_auth_keys]
            if new_auth_keys:
                auth_key = new_auth_keys[-1]
                ensure_authkey_valid(opener, base_url, auth_key)
                set_global_env(save_env, auth_key)
                print(
                    json.dumps(
                        {
                            "status": "ok",
                            "saved_env": save_env,
                            "auth_key_prefix": auth_key[:8],
                            "base_url": base_url,
                            "login_mode": login_mode,
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
                return 0
        time.sleep(poll_seconds)
    else:
        raise RuntimeError("wechat QR login timed out")

    bizlogin_payload = request_json(
        opener,
        f"{base_url}/api/web/login/bizlogin",
        method="POST",
    )
    if bizlogin_payload.get("err"):
        raise RuntimeError(str(bizlogin_payload["err"]))

    auth_key = get_cookie_value(opener, "auth-key")
    if not auth_key:
        raise RuntimeError("wechat login succeeded but auth-key cookie was not returned")

    ensure_authkey_valid(opener, base_url, auth_key)
    set_global_env(save_env, auth_key)
    print(
        json.dumps(
            {
                "status": "ok",
                "saved_env": save_env,
                "auth_key_prefix": auth_key[:8],
                "base_url": base_url,
                "login_mode": login_mode,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0


def main() -> int:
    args = parse_args()
    return run_login(
        base_url=args.base_url,
        save_env=args.save_env,
        debug_key=args.debug_key,
        poll_seconds=args.poll_seconds,
        timeout_seconds=args.timeout_seconds,
    )


if __name__ == "__main__":
    raise SystemExit(main())

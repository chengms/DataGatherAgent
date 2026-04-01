#!/usr/bin/env python3
"""Terminal QR-code login flow for the managed wechat-article-exporter service."""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from service_env_store import ROOT_DIR, set_global_env
from terminal_qr import render_terminal_qr


DEFAULT_BASE_URL = "http://127.0.0.1:3000"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Log into the managed wechat-article-exporter service from the terminal.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--save-env", default="WECHAT_EXPORTER_API_KEY")
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


def run_login(base_url: str, save_env: str, poll_seconds: float, timeout_seconds: int) -> int:
    opener = build_opener()
    base_url = base_url.rstrip("/")
    sid = f"{int(time.time() * 1000)}{secrets.randbelow(1000):03d}"

    start = request_json(
        opener,
        f"{base_url}/api/web/login/session/{sid}",
        method="POST",
    )
    if start.get("base_resp", {}).get("ret") != 0:
        raise RuntimeError(f"unable to start wechat login session: {start}")

    qrcode_bytes = request_bytes(opener, f"{base_url}/api/web/login/getqrcode?rnd={time.time()}")
    render_terminal_qr(qrcode_bytes, "Scan this QR code with WeChat Official Accounts:")

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
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
            render_terminal_qr(qrcode_bytes, "WeChat QR code refreshed. Scan again:")
        elif status == 5:
            raise RuntimeError("The WeChat account is not eligible for public account login.")
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
        poll_seconds=args.poll_seconds,
        timeout_seconds=args.timeout_seconds,
    )


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Check whether the managed Xiaohongshu login cookies are still valid."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import service_env_store


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_REPO = ROOT_DIR / "external_tools" / "MediaCrawler"


def ensure_repo_python(repo_dir: Path) -> None:
    if os.getenv("XHS_LOGIN_STATUS_BOOTSTRAPPED") == "1":
        return
    candidate = repo_dir / ".venv" / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")
    if not candidate.exists():
        return
    env = os.environ.copy()
    env["XHS_LOGIN_STATUS_BOOTSTRAPPED"] = "1"
    completed = subprocess.run([str(candidate), __file__, *sys.argv[1:]], env=env, check=False)
    raise SystemExit(completed.returncode)


def prepend_repo_to_syspath(repo_dir: Path) -> None:
    repo_str = str(repo_dir)
    if repo_str not in sys.path:
        sys.path.insert(0, repo_str)


async def run_check(repo_dir: Path, cookies: str) -> bool:
    prepend_repo_to_syspath(repo_dir)
    import config  # type: ignore
    from media_platform.xhs.core import XiaoHongShuCrawler  # type: ignore
    from media_platform.xhs.login import XiaoHongShuLogin  # type: ignore
    from playwright.async_api import async_playwright  # type: ignore

    original_save_login_state = config.SAVE_LOGIN_STATE
    original_login_type = config.LOGIN_TYPE
    original_cookies = config.COOKIES
    config.SAVE_LOGIN_STATE = False
    config.LOGIN_TYPE = "cookie"
    config.COOKIES = cookies

    crawler = XiaoHongShuCrawler()
    try:
        async with async_playwright() as playwright:
            crawler.browser_context = await crawler.launch_browser(
                playwright.chromium,
                None,
                crawler.user_agent,
                headless=True,
            )
            await crawler.browser_context.add_init_script(path=str(repo_dir / "libs" / "stealth.min.js"))
            crawler.context_page = await crawler.browser_context.new_page()
            await crawler.context_page.goto(crawler.index_url)
            login = XiaoHongShuLogin(
                login_type="cookie",
                browser_context=crawler.browser_context,
                context_page=crawler.context_page,
                cookie_str=cookies,
            )
            await login.login_by_cookies()
            crawler.xhs_client = await crawler.create_xhs_client(None)
            return await crawler.xhs_client.pong()
    finally:
        config.SAVE_LOGIN_STATE = original_save_login_state
        config.LOGIN_TYPE = original_login_type
        config.COOKIES = original_cookies
        try:
            if getattr(crawler, "browser_context", None) is not None:
                await crawler.browser_context.close()
        except Exception:
            pass


def main() -> int:
    payload = service_env_store.load_local_config()
    service_env = payload.get("services", {}).get("mediacrawler_xhs", {}).get("env", {})
    cookies = str(service_env.get("XHS_MEDIACRAWLER_COOKIES", "")).strip()
    if not cookies:
        print(json.dumps({"ok": False, "reason": "missing_cookies"}, ensure_ascii=False))
        return 0
    repo_dir = DEFAULT_REPO.resolve()
    if not repo_dir.exists():
        print(json.dumps({"ok": False, "reason": "missing_repo"}, ensure_ascii=False))
        return 0
    ensure_repo_python(repo_dir)
    ok = asyncio.run(run_check(repo_dir, cookies))
    print(json.dumps({"ok": ok, "reason": "ok" if ok else "cookie_invalid"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Check managed MediaCrawler cookie login status across platforms."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import service_env_store


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_REPO = ROOT_DIR / "external_tools" / "MediaCrawler"
COOKIE_ENV_BY_PLATFORM = {
    "xhs": "XHS_MEDIACRAWLER_COOKIES",
    "weibo": "WEIBO_MEDIACRAWLER_COOKIES",
    "douyin": "DY_MEDIACRAWLER_COOKIES",
    "bilibili": "BILI_MEDIACRAWLER_COOKIES",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check MediaCrawler platform cookie login states.")
    parser.add_argument("--repo", default=str(DEFAULT_REPO))
    parser.add_argument("--service", default="mediacrawler_xhs")
    parser.add_argument("--platforms", default="xhs,weibo,douyin,bilibili")
    parser.add_argument("--allow-missing", action="store_true", help="Treat missing platform cookies as non-failing checks.")
    return parser.parse_args()


def ensure_repo_python(repo_dir: Path) -> None:
    if os.getenv("MEDIACRAWLER_LOGIN_STATUS_BOOTSTRAPPED") == "1":
        return
    candidate = repo_dir / ".venv" / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")
    if not candidate.exists():
        return
    env = os.environ.copy()
    env["MEDIACRAWLER_LOGIN_STATUS_BOOTSTRAPPED"] = "1"
    completed = subprocess.run([str(candidate), __file__, *sys.argv[1:]], env=env, check=False)
    raise SystemExit(completed.returncode)


def prepend_repo_to_syspath(repo_dir: Path) -> None:
    repo_str = str(repo_dir)
    if repo_str not in sys.path:
        sys.path.insert(0, repo_str)


@asynccontextmanager
async def _new_context_page(crawler: Any, repo_dir: Path):
    from playwright.async_api import async_playwright  # type: ignore

    async with async_playwright() as playwright:
        user_agent = getattr(crawler, "mobile_user_agent", None) or getattr(crawler, "user_agent", None)
        crawler.browser_context = await crawler.launch_browser(
            playwright.chromium,
            None,
            user_agent,
            headless=True,
        )
        stealth_path = repo_dir / "libs" / "stealth.min.js"
        if stealth_path.exists():
            await crawler.browser_context.add_init_script(path=str(stealth_path))
        crawler.context_page = await crawler.browser_context.new_page()
        await crawler.context_page.goto(crawler.index_url)
        await asyncio.sleep(0.5)
        try:
            yield
        finally:
            await crawler.browser_context.close()


async def run_platform_check(platform: str, repo_dir: Path, cookies: str) -> bool:
    prepend_repo_to_syspath(repo_dir)
    import config  # type: ignore

    original_save_login_state = config.SAVE_LOGIN_STATE
    original_login_type = config.LOGIN_TYPE
    original_cookies = config.COOKIES
    original_enable_ip_proxy = getattr(config, "ENABLE_IP_PROXY", False)
    original_platform = getattr(config, "PLATFORM", "")
    config.SAVE_LOGIN_STATE = False
    config.LOGIN_TYPE = "cookie"
    config.COOKIES = cookies
    config.ENABLE_IP_PROXY = False
    config.PLATFORM = {
        "xhs": "xhs",
        "weibo": "wb",
        "douyin": "dy",
        "bilibili": "bili",
    }[platform]

    crawler = None
    try:
        if platform == "xhs":
            from media_platform.xhs.core import XiaoHongShuCrawler  # type: ignore
            from media_platform.xhs.login import XiaoHongShuLogin  # type: ignore

            crawler = XiaoHongShuCrawler()
            async with _new_context_page(crawler, repo_dir):
                login = XiaoHongShuLogin(
                    login_type="cookie",
                    browser_context=crawler.browser_context,
                    context_page=crawler.context_page,
                    cookie_str=cookies,
                )
                await login.login_by_cookies()
                crawler.xhs_client = await crawler.create_xhs_client(None)
                return await crawler.xhs_client.pong()

        if platform == "weibo":
            from media_platform.weibo.core import WeiboCrawler  # type: ignore
            from media_platform.weibo.login import WeiboLogin  # type: ignore

            crawler = WeiboCrawler()
            async with _new_context_page(crawler, repo_dir):
                login = WeiboLogin(
                    login_type="cookie",
                    browser_context=crawler.browser_context,
                    context_page=crawler.context_page,
                    cookie_str=cookies,
                )
                await login.login_by_cookies()
                await crawler.context_page.goto(crawler.mobile_index_url)
                await asyncio.sleep(1.0)
                crawler.wb_client = await crawler.create_weibo_client(None)
                return await crawler.wb_client.pong()

        if platform == "douyin":
            from media_platform.douyin.core import DouYinCrawler  # type: ignore
            from media_platform.douyin.login import DouYinLogin  # type: ignore

            crawler = DouYinCrawler()
            async with _new_context_page(crawler, repo_dir):
                login = DouYinLogin(
                    login_type="cookie",
                    browser_context=crawler.browser_context,
                    context_page=crawler.context_page,
                    cookie_str=cookies,
                )
                await login.login_by_cookies()
                crawler.dy_client = await crawler.create_douyin_client(None)
                return await crawler.dy_client.pong(browser_context=crawler.browser_context)

        if platform == "bilibili":
            from media_platform.bilibili.core import BilibiliCrawler  # type: ignore
            from media_platform.bilibili.login import BilibiliLogin  # type: ignore

            crawler = BilibiliCrawler()
            async with _new_context_page(crawler, repo_dir):
                login = BilibiliLogin(
                    login_type="cookie",
                    browser_context=crawler.browser_context,
                    context_page=crawler.context_page,
                    cookie_str=cookies,
                )
                await login.login_by_cookies()
                crawler.bili_client = await crawler.create_bilibili_client(None)
                return await crawler.bili_client.pong()

    finally:
        config.SAVE_LOGIN_STATE = original_save_login_state
        config.LOGIN_TYPE = original_login_type
        config.COOKIES = original_cookies
        config.ENABLE_IP_PROXY = original_enable_ip_proxy
        config.PLATFORM = original_platform
    return False


def parse_platforms(raw: str) -> list[str]:
    allowed = set(COOKIE_ENV_BY_PLATFORM.keys())
    result: list[str] = []
    for item in str(raw).split(","):
        normalized = item.strip().lower()
        if not normalized:
            continue
        if normalized not in allowed:
            continue
        if normalized not in result:
            result.append(normalized)
    return result or ["xhs", "weibo", "douyin", "bilibili"]


def main() -> int:
    args = parse_args()
    repo_dir = Path(args.repo).resolve()
    if not repo_dir.exists():
        print(json.dumps({"ok": False, "reason": "missing_repo", "checks": []}, ensure_ascii=False))
        return 0
    ensure_repo_python(repo_dir)

    payload = service_env_store.load_local_config()
    service_env = payload.get("services", {}).get(args.service, {}).get("env", {})
    checks: list[dict[str, Any]] = []
    overall_ok = True
    failing_reason = "ok"
    for platform in parse_platforms(args.platforms):
        cookie_env_name = COOKIE_ENV_BY_PLATFORM[platform]
        cookies = str(service_env.get(cookie_env_name, "")).strip()
        if not cookies:
            ok = bool(args.allow_missing)
            reason = "missing_cookies"
        else:
            try:
                ok = asyncio.run(run_platform_check(platform, repo_dir, cookies))
                reason = "ok" if ok else "cookie_invalid"
            except ModuleNotFoundError as exc:
                ok = False
                reason = f"missing_dependency:{exc.name or type(exc).__name__}"
            except Exception as exc:
                ok = False
                reason = f"check_error:{type(exc).__name__}"
        checks.append({"platform": platform, "ok": ok, "reason": reason})
        if not ok and overall_ok:
            overall_ok = False
            failing_reason = f"{platform}:{reason}"

    print(
        json.dumps(
            {
                "ok": overall_ok,
                "reason": "ok" if overall_ok else failing_reason,
                "checks": checks,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

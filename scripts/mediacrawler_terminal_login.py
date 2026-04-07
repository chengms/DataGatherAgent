#!/usr/bin/env python3
"""Terminal QR login flow for managed MediaCrawler platforms."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from service_env_store import set_service_env
from terminal_qr import render_terminal_qr


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_REPO = ROOT_DIR / "external_tools" / "MediaCrawler"
SAVE_SERVICE = "mediacrawler_xhs"
PLATFORM_SPECS: dict[str, dict[str, str]] = {
    "xhs": {
        "platform_arg": "xhs",
        "label": "小红书",
        "cookie_env": "XHS_MEDIACRAWLER_COOKIES",
        "login_env": "XHS_MEDIACRAWLER_LOGIN_TYPE",
    },
    "weibo": {
        "platform_arg": "wb",
        "label": "微博",
        "cookie_env": "WEIBO_MEDIACRAWLER_COOKIES",
        "login_env": "WEIBO_MEDIACRAWLER_LOGIN_TYPE",
    },
    "douyin": {
        "platform_arg": "dy",
        "label": "抖音",
        "cookie_env": "DY_MEDIACRAWLER_COOKIES",
        "login_env": "DY_MEDIACRAWLER_LOGIN_TYPE",
    },
    "bilibili": {
        "platform_arg": "bili",
        "label": "B站",
        "cookie_env": "BILI_MEDIACRAWLER_COOKIES",
        "login_env": "BILI_MEDIACRAWLER_LOGIN_TYPE",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Log into MediaCrawler platforms and persist cookie env values.")
    parser.add_argument("--repo", default=str(DEFAULT_REPO))
    parser.add_argument("--platform", choices=("xhs", "weibo", "douyin", "bilibili", "all"), default="all")
    parser.add_argument("--login-type", default="qrcode")
    parser.add_argument("--save-service", default=SAVE_SERVICE)
    return parser.parse_args()


def ensure_repo_python(repo_dir: Path) -> None:
    if os.getenv("MEDIACRAWLER_TERMINAL_LOGIN_BOOTSTRAPPED") == "1":
        return
    candidate = repo_dir / ".venv" / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")
    if not candidate.exists():
        return
    env = os.environ.copy()
    env["MEDIACRAWLER_TERMINAL_LOGIN_BOOTSTRAPPED"] = "1"
    completed = subprocess.run([str(candidate), __file__, *sys.argv[1:]], env=env, check=False)
    raise SystemExit(completed.returncode)


def prepend_repo_to_syspath(repo_dir: Path) -> None:
    repo_str = str(repo_dir)
    if repo_str not in sys.path:
        sys.path.insert(0, repo_str)


def render_qrcode(qr_code: str, platform: str) -> None:
    label = PLATFORM_SPECS[platform]["label"]
    render_terminal_qr(qr_code, f"Scan this QR code with {label}:")


def _crawler_and_login_cls(platform: str):
    try:
        if platform == "xhs":
            from media_platform.xhs.core import XiaoHongShuCrawler  # type: ignore
            from media_platform.xhs.login import XiaoHongShuLogin  # type: ignore

            return XiaoHongShuCrawler, XiaoHongShuLogin
        if platform == "weibo":
            from media_platform.weibo.core import WeiboCrawler  # type: ignore
            from media_platform.weibo.login import WeiboLogin  # type: ignore

            return WeiboCrawler, WeiboLogin
        if platform == "douyin":
            from media_platform.douyin.core import DouYinCrawler  # type: ignore
            from media_platform.douyin.login import DouYinLogin  # type: ignore

            return DouYinCrawler, DouYinLogin
        if platform == "bilibili":
            from media_platform.bilibili.core import BilibiliCrawler  # type: ignore
            from media_platform.bilibili.login import BilibiliLogin  # type: ignore

            return BilibiliCrawler, BilibiliLogin
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            f"MediaCrawler is missing dependency '{exc.name}'. Run the MediaCrawler install/bootstrap steps again."
        ) from exc
    raise ValueError(f"unsupported platform: {platform}")


def _collect_cookie_string(cookies: list[dict[str, Any]]) -> str:
    return ";".join(
        f"{item.get('name')}={item.get('value')}"
        for item in cookies
        if item.get("name") and item.get("value")
    )


async def run_single_login(
    *,
    repo_dir: Path,
    platform: str,
    login_type: str,
    save_service: str,
) -> dict[str, Any]:
    prepend_repo_to_syspath(repo_dir)

    import config  # type: ignore
    from cmd_arg.arg import parse_cmd  # type: ignore
    from playwright.async_api import async_playwright  # type: ignore
    from tools import crawler_util  # type: ignore

    crawler_cls, login_cls = _crawler_and_login_cls(platform)
    platform_arg = PLATFORM_SPECS[platform]["platform_arg"]
    cookie_env = PLATFORM_SPECS[platform]["cookie_env"]
    login_env = PLATFORM_SPECS[platform]["login_env"]
    original_show_qrcode = crawler_util.show_qrcode
    original_auto_close = config.AUTO_CLOSE_BROWSER

    def patched_show_qrcode(qr_code: str) -> None:
        render_qrcode(qr_code, platform)

    crawler_util.show_qrcode = patched_show_qrcode
    config.AUTO_CLOSE_BROWSER = True
    crawler = crawler_cls()
    try:
        await parse_cmd(
            [
                "--platform",
                platform_arg,
                "--lt",
                login_type,
                "--headless",
                "false",
            ]
        )
        async with async_playwright() as playwright:
            user_agent = getattr(crawler, "mobile_user_agent", None) or getattr(crawler, "user_agent", None)
            crawler.browser_context = await crawler.launch_browser(
                playwright.chromium,
                None,
                user_agent,
                headless=False,
            )
            stealth_path = repo_dir / "libs" / "stealth.min.js"
            if stealth_path.exists():
                await crawler.browser_context.add_init_script(path=str(stealth_path))
            crawler.context_page = await crawler.browser_context.new_page()
            await crawler.context_page.goto(crawler.index_url)
            print(f"Starting {PLATFORM_SPECS[platform]['label']} login flow. Complete login in browser.", flush=True)
            login_obj = login_cls(
                login_type=login_type,
                login_phone="",
                browser_context=crawler.browser_context,
                context_page=crawler.context_page,
                cookie_str="",
            )
            await login_obj.begin()
            cookies = await crawler.browser_context.cookies()
            cookie_string = _collect_cookie_string(cookies)
            if not cookie_string:
                raise RuntimeError(f"{platform} login finished but no cookies were captured")
            set_service_env(save_service, cookie_env, cookie_string)
            set_service_env(save_service, login_env, "cookie")
            return {
                "status": "ok",
                "platform": platform,
                "cookie_env": cookie_env,
                "cookie_length": len(cookie_string),
            }
    finally:
        try:
            close_fn = getattr(crawler, "close", None)
            if close_fn is not None:
                close_result = close_fn()
                if asyncio.iscoroutine(close_result):
                    await close_result
        except Exception:
            pass
        crawler_util.show_qrcode = original_show_qrcode
        config.AUTO_CLOSE_BROWSER = original_auto_close


def target_platforms(platform_arg: str) -> list[str]:
    if platform_arg == "all":
        return ["xhs", "weibo", "douyin", "bilibili"]
    return [platform_arg]


def main() -> int:
    args = parse_args()
    repo_dir = Path(args.repo).resolve()
    if not repo_dir.exists():
        raise RuntimeError(f"managed MediaCrawler checkout does not exist: {repo_dir}")
    ensure_repo_python(repo_dir)
    results: list[dict[str, Any]] = []
    for platform in target_platforms(args.platform):
        results.append(
            asyncio.run(
                run_single_login(
                    repo_dir=repo_dir,
                    platform=platform,
                    login_type=args.login_type,
                    save_service=args.save_service,
                )
            )
        )
    print(json.dumps({"status": "ok", "results": results}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

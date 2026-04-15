#!/usr/bin/env python3
"""Terminal QR-code login flow for MediaCrawler Xiaohongshu without modifying the upstream checkout."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

from service_env_store import set_service_env
from terminal_qr import render_terminal_qr


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_REPO = ROOT_DIR / "external_tools" / "MediaCrawler"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Log into Xiaohongshu through the managed MediaCrawler checkout.")
    parser.add_argument("--repo", default=str(DEFAULT_REPO))
    parser.add_argument("--login-type", default="qrcode")
    parser.add_argument("--save-service", default="mediacrawler_xhs")
    parser.add_argument("--save-env", default="XHS_MEDIACRAWLER_COOKIES")
    return parser.parse_args()


def ensure_repo_python(repo_dir: Path) -> None:
    if os.getenv("XHS_TERMINAL_LOGIN_BOOTSTRAPPED") == "1":
        return
    candidate = repo_dir / ".venv" / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")
    if not candidate.exists():
        return
    env = os.environ.copy()
    env["XHS_TERMINAL_LOGIN_BOOTSTRAPPED"] = "1"
    completed = subprocess.run([str(candidate), __file__, *sys.argv[1:]], env=env, check=False)
    raise SystemExit(completed.returncode)


def prepend_repo_to_syspath(repo_dir: Path) -> None:
    repo_str = str(repo_dir)
    if repo_str not in sys.path:
        sys.path.insert(0, repo_str)


def render_qrcode(qr_code: str) -> None:
    render_terminal_qr(qr_code, "Scan this QR code with Xiaohongshu:")


async def run_login(repo_dir: Path, login_type: str, save_service: str, save_env: str) -> int:
    prepend_repo_to_syspath(repo_dir)

    import config  # type: ignore
    from cmd_arg.arg import parse_cmd  # type: ignore
    from media_platform.xhs import XiaoHongShuCrawler  # type: ignore
    from tools import crawler_util  # type: ignore

    original_show_qrcode = crawler_util.show_qrcode
    original_auto_close = config.AUTO_CLOSE_BROWSER

    def patched_show_qrcode(qr_code: str) -> None:
        render_qrcode(qr_code)

    crawler_util.show_qrcode = patched_show_qrcode
    config.AUTO_CLOSE_BROWSER = True

    try:
        await parse_cmd(
            [
                "--platform",
                "xhs",
                "--lt",
                login_type,
                "--type",
                "search",
                "--headless",
                "false",
                "--save_data_option",
                "json",
                "--keywords",
                "登录校验",
                "--save_data_path",
                str(repo_dir / ".codex-login-output"),
            ]
        )
        crawler = XiaoHongShuCrawler()
        await crawler.start()
        cookies = await crawler.browser_context.cookies()
        cookie_string = ";".join(
            f"{item.get('name')}={item.get('value')}"
            for item in cookies
            if item.get("name") and item.get("value")
        )
        if not cookie_string:
            raise RuntimeError("Xiaohongshu login finished but no cookies were captured")
        set_service_env(save_service, save_env, cookie_string)
        set_service_env(save_service, "XHS_MEDIACRAWLER_LOGIN_TYPE", "cookie")
        print(
            json.dumps(
                {
                    "status": "ok",
                    "saved_service": save_service,
                    "saved_env": save_env,
                    "cookie_length": len(cookie_string),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        return 0
    finally:
        crawler_util.show_qrcode = original_show_qrcode
        config.AUTO_CLOSE_BROWSER = original_auto_close


def main() -> int:
    args = parse_args()
    repo_dir = Path(args.repo).resolve()
    if not repo_dir.exists():
        raise RuntimeError(f"managed MediaCrawler checkout does not exist: {repo_dir}")
    ensure_repo_python(repo_dir)
    return asyncio.run(
        run_login(
            repo_dir=repo_dir,
            login_type=args.login_type,
            save_service=args.save_service,
            save_env=args.save_env,
        )
    )


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Run MediaCrawler Xiaohongshu search without modifying the upstream checkout."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a managed MediaCrawler Xiaohongshu search.")
    parser.add_argument("--repo", required=True, help="Path to the MediaCrawler checkout")
    parser.add_argument("--keyword", required=True)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--login-type", default=os.getenv("XHS_MEDIACRAWLER_LOGIN_TYPE", "qrcode"))
    parser.add_argument("--cookies", default=os.getenv("XHS_MEDIACRAWLER_COOKIES", ""))
    parser.add_argument(
        "--start-command",
        nargs="+",
        default=["uv", "run", "main.py", "--platform", "xhs", "--type", "search"],
        help="Command used to launch MediaCrawler search within the managed checkout",
    )
    return parser.parse_args()


def load_base_config(repo_dir: Path) -> dict[str, Any]:
    config_path = repo_dir / "config" / "base_config.py"
    spec = importlib.util.spec_from_file_location("media_base_config", config_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load base config from {config_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {
        name: getattr(module, name)
        for name in dir(module)
        if name.isupper()
    }


def build_override_config(repo_dir: Path, keyword: str, limit: int, login_type: str, cookies: str, output_dir: Path) -> str:
    defaults = load_base_config(repo_dir)
    merged: dict[str, Any] = dict(defaults)
    merged.update(
        {
            "PLATFORM": "xhs",
            "KEYWORDS": keyword,
            "LOGIN_TYPE": login_type,
            "COOKIES": cookies,
            "CRAWLER_TYPE": "search",
            "CRAWLER_MAX_NOTES_COUNT": max(limit, 1),
            "SAVE_DATA_OPTION": "json",
            "SAVE_DATA_PATH": str(output_dir),
            "ENABLE_GET_COMMENTS": False,
        }
    )

    lines = [
        "from pkgutil import extend_path",
        "__path__ = extend_path(__path__, __name__)",
        "",
    ]
    return "\n".join(lines)


def build_override_base_config(repo_dir: Path, keyword: str, limit: int, login_type: str, cookies: str, output_dir: Path) -> str:
    defaults = load_base_config(repo_dir)
    lines = [
        "from __future__ import annotations",
        "import importlib.util",
        "from pathlib import Path",
        "",
        f"_CONFIG_PATH = Path(r'''{(repo_dir / 'config' / 'base_config.py').as_posix()}''')",
        "_SPEC = importlib.util.spec_from_file_location('_media_base_config', _CONFIG_PATH)",
        "if _SPEC is None or _SPEC.loader is None:",
        "    raise RuntimeError(f'unable to load upstream MediaCrawler config: {_CONFIG_PATH}')",
        "_MODULE = importlib.util.module_from_spec(_SPEC)",
        "_SPEC.loader.exec_module(_MODULE)",
        "",
    ]
    for name in sorted(defaults):
        lines.append(f"{name} = getattr(_MODULE, {name!r})")
    overrides = {
        "PLATFORM": "xhs",
        "KEYWORDS": keyword,
        "LOGIN_TYPE": login_type,
        "COOKIES": cookies,
        "CRAWLER_TYPE": "search",
        "CRAWLER_MAX_NOTES_COUNT": max(limit, 1),
        "SAVE_DATA_OPTION": "json",
        "SAVE_DATA_PATH": str(output_dir),
        "ENABLE_GET_COMMENTS": False,
    }
    for name, value in overrides.items():
        lines.append(f"{name} = {value!r}")
    lines.append("")
    return "\n".join(lines)


def collect_saved_items(output_dir: Path) -> list[dict[str, Any]]:
    json_files = sorted(output_dir.rglob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    for json_file in json_files:
        try:
            payload = json.loads(json_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("items", "data", "notes"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
    return []


def normalize_items(keyword: str, items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in items:
        title = first_text(item, "title", "note_title", "desc")
        source_url = first_text(item, "note_url", "url", "share_url")
        account_name = first_text(item, "nickname", "user_name", "author", "account_name") or "unknown"
        if not title or not source_url:
            continue
        normalized.append(
            {
                "keyword": keyword,
                "title": title,
                "snippet": first_text(item, "desc", "content", "snippet") or "",
                "source_url": source_url,
                "account_name": account_name,
            }
        )
        if len(normalized) >= limit:
            break
    return normalized


def first_text(item: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def main() -> int:
    args = parse_args()
    repo_dir = Path(args.repo).resolve()
    if not repo_dir.exists():
        raise RuntimeError(f"managed MediaCrawler checkout does not exist: {repo_dir}")

    with tempfile.TemporaryDirectory(prefix="mediacrawler-xhs-") as temp_dir:
        temp_path = Path(temp_dir)
        config_dir = temp_path / "config"
        output_dir = temp_path / "output"
        config_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        (config_dir / "__init__.py").write_text(
            build_override_config(
                repo_dir=repo_dir,
                keyword=args.keyword,
                limit=args.limit,
                login_type=args.login_type,
                cookies=args.cookies,
                output_dir=output_dir,
            ),
            encoding="utf-8",
        )
        (config_dir / "base_config.py").write_text(
            build_override_base_config(
                repo_dir=repo_dir,
                keyword=args.keyword,
                limit=args.limit,
                login_type=args.login_type,
                cookies=args.cookies,
                output_dir=output_dir,
            ),
            encoding="utf-8",
        )

        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join([str(temp_path), env.get("PYTHONPATH", "")]).rstrip(os.pathsep)
        completed = subprocess.run(
            args.start_command,
            cwd=repo_dir,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            sys.stderr.write(completed.stderr[-4000:])
            return completed.returncode

        payload = {
            "items": normalize_items(
                keyword=args.keyword,
                items=collect_saved_items(output_dir),
                limit=args.limit,
            )
        }
        sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

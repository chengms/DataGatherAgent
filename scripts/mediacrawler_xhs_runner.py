#!/usr/bin/env python3
"""Run MediaCrawler Xiaohongshu search or detail fetch without modifying the upstream checkout."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a managed MediaCrawler Xiaohongshu workflow.")
    parser.add_argument("--mode", choices=("search", "fetch"), default="search")
    parser.add_argument("--repo", required=True, help="Path to the MediaCrawler checkout")
    parser.add_argument("--keyword")
    parser.add_argument("--source-url")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--login-type", default=os.getenv("XHS_MEDIACRAWLER_LOGIN_TYPE", "qrcode"))
    parser.add_argument("--cookies", default=os.getenv("XHS_MEDIACRAWLER_COOKIES", ""))
    parser.add_argument(
        "--start-command",
        nargs="+",
        default=["uv", "run", "main.py", "--platform", "xhs"],
        help="Command prefix used to launch MediaCrawler within the managed checkout",
    )
    args = parser.parse_args()
    if args.mode == "search" and not args.keyword:
        parser.error("--keyword is required in search mode")
    if args.mode == "fetch" and not args.source_url:
        parser.error("--source-url is required in fetch mode")
    return args


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


def build_override_config() -> str:
    lines = [
        "from pkgutil import extend_path",
        "__path__ = extend_path(__path__, __name__)",
        "",
    ]
    return "\n".join(lines)


def build_override_base_config(
    repo_dir: Path,
    *,
    mode: str,
    keyword: str | None,
    source_url: str | None,
    limit: int,
    login_type: str,
    cookies: str,
    output_dir: Path,
) -> str:
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
    overrides: dict[str, Any] = {
        "PLATFORM": "xhs",
        "LOGIN_TYPE": login_type,
        "COOKIES": cookies,
        "CRAWLER_TYPE": "search" if mode == "search" else "detail",
        "CRAWLER_MAX_NOTES_COUNT": max(limit, 1),
        "SAVE_DATA_OPTION": "json",
        "SAVE_DATA_PATH": str(output_dir),
        "ENABLE_GET_COMMENTS": False,
        "ENABLE_GET_SUB_COMMENTS": False,
        "ENABLE_GET_MEIDAS": False,
        "KEYWORDS": keyword or "",
        "XHS_SPECIFIED_NOTE_URL_LIST": [source_url] if source_url else [],
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


def normalize_fetch_item(item: dict[str, Any], fallback_source_url: str) -> dict[str, Any]:
    account_name = (
        first_text(item, "nickname", "user_nickname", "author", "account_name")
        or nested_text(item, "user", "nickname")
        or "unknown"
    )
    source_url = first_text(item, "note_url", "url", "share_url") or fallback_source_url
    title = first_text(item, "title", "note_title", "desc") or "小红书内容"
    publish_time = normalize_datetime(
        item.get("time") or item.get("publish_time") or item.get("create_time") or item.get("create_date_time")
    )
    return {
        "title": title,
        "source_url": source_url,
        "account_name": account_name,
        "publish_time": publish_time,
        "read_count": coerce_int(item.get("liked_count") or nested_value(item, "interact_info", "liked_count")),
        "comment_count": coerce_int(item.get("comment_count") or nested_value(item, "interact_info", "comment_count")),
        "content_text": first_text(item, "desc", "content", "title") or "",
        "source_id": first_text(item, "note_id", "id") or extract_note_id(source_url),
    }


def first_text(item: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def nested_value(item: dict[str, Any], *keys: str) -> Any:
    current: Any = item
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def nested_text(item: dict[str, Any], *keys: str) -> str | None:
    value = nested_value(item, *keys)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def coerce_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def normalize_datetime(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        text = value.strip()
        if "T" in text:
            try:
                return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(UTC).isoformat().replace("+00:00", "Z")
            except ValueError:
                pass
        if text.isdigit():
            return normalize_datetime(int(text))
    if isinstance(value, (int, float)):
        seconds = float(value)
        if seconds > 10_000_000_000:
            seconds /= 1000.0
        return datetime.fromtimestamp(seconds, tz=UTC).isoformat().replace("+00:00", "Z")
    return datetime.fromtimestamp(0, tz=UTC).isoformat().replace("+00:00", "Z")


def extract_note_id(source_url: str) -> str:
    parsed = urlparse(source_url)
    path = parsed.path.rstrip("/")
    if not path:
        return ""
    return path.split("/")[-1]


def build_start_command(args: argparse.Namespace) -> list[str]:
    command = list(args.start_command)
    command.extend(["--lt", args.login_type, "--type", "search" if args.mode == "search" else "detail"])
    if args.mode == "fetch":
        command.extend(["--specified_id", args.source_url])
    return command


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

        (config_dir / "__init__.py").write_text(build_override_config(), encoding="utf-8")
        (config_dir / "base_config.py").write_text(
            build_override_base_config(
                repo_dir=repo_dir,
                mode=args.mode,
                keyword=args.keyword,
                source_url=args.source_url,
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
            build_start_command(args),
            cwd=repo_dir,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            sys.stderr.write(completed.stderr[-4000:])
            return completed.returncode

        items = collect_saved_items(output_dir)
        if args.mode == "search":
            payload = {
                "items": normalize_items(
                    keyword=args.keyword or "",
                    items=items,
                    limit=args.limit,
                )
            }
        else:
            payload = {
                "item": normalize_fetch_item(
                    next((item for item in items if isinstance(item, dict)), {}),
                    fallback_source_url=args.source_url or "",
                )
            }
        sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

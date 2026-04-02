#!/usr/bin/env python3
"""Run MediaCrawler search/detail workflows for multiple platforms without modifying the upstream checkout."""

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


PLATFORM_SPECS: dict[str, dict[str, str]] = {
    "xiaohongshu": {
        "platform_arg": "xhs",
        "specified_var": "XHS_SPECIFIED_NOTE_URL_LIST",
        "title_default": "Xiaohongshu content",
    },
    "weibo": {
        "platform_arg": "wb",
        "specified_var": "WEIBO_SPECIFIED_ID_LIST",
        "title_default": "Weibo content",
    },
    "bilibili": {
        "platform_arg": "bili",
        "specified_var": "BILI_SPECIFIED_ID_LIST",
        "title_default": "Bilibili content",
    },
    "douyin": {
        "platform_arg": "dy",
        "specified_var": "DY_SPECIFIED_ID_LIST",
        "title_default": "Douyin content",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a managed MediaCrawler workflow for a specific platform.")
    parser.add_argument("--platform", choices=tuple(PLATFORM_SPECS.keys()), required=True)
    parser.add_argument("--mode", choices=("search", "fetch"), default="search")
    parser.add_argument("--repo", required=True, help="Path to the MediaCrawler checkout")
    parser.add_argument("--keyword")
    parser.add_argument("--source-url")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--login-type", default="qrcode")
    parser.add_argument("--cookies", default="")
    parser.add_argument(
        "--start-command",
        nargs="+",
        default=["uv", "run", "main.py"],
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
    return {name: getattr(module, name) for name in dir(module) if name.isupper()}


def build_override_config_init() -> str:
    return "from pkgutil import extend_path\n__path__ = extend_path(__path__, __name__)\n"


def build_override_base_config(
    repo_dir: Path,
    *,
    platform: str,
    mode: str,
    keyword: str | None,
    source_url: str | None,
    limit: int,
    login_type: str,
    cookies: str,
    output_dir: Path,
) -> str:
    defaults = load_base_config(repo_dir)
    spec = PLATFORM_SPECS[platform]
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
        "PLATFORM": spec["platform_arg"],
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
        spec["specified_var"]: [source_url] if source_url else [],
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
            for key in ("items", "data", "notes", "videos"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
    return []


def nested_value(item: dict[str, Any], *keys: str) -> Any:
    current: Any = item
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def first_text(item: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


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
                return (
                    datetime.fromisoformat(text.replace("Z", "+00:00"))
                    .astimezone(UTC)
                    .isoformat()
                    .replace("+00:00", "Z")
                )
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


def unwrap_platform_item(platform: str, item: dict[str, Any]) -> dict[str, Any]:
    if platform == "weibo" and isinstance(item.get("mblog"), dict):
        return item["mblog"]
    if platform == "douyin":
        aweme = item.get("aweme_info")
        if isinstance(aweme, dict):
            return aweme
        mix_items = nested_value(item, "aweme_mix_info", "mix_items")
        if isinstance(mix_items, list) and mix_items and isinstance(mix_items[0], dict):
            return mix_items[0]
    return item


def build_source_url(platform: str, item: dict[str, Any], fallback_source_url: str = "") -> str:
    direct = (
        first_text(item, "note_url", "url", "share_url", "content_url", "jump_url")
        or nested_text(item, "share_info", "share_url")
    )
    if direct:
        return direct
    if platform == "weibo":
        note_id = first_text(item, "id", "mid")
        return f"https://m.weibo.cn/detail/{note_id}" if note_id else fallback_source_url
    if platform == "douyin":
        aweme_id = first_text(item, "aweme_id")
        return f"https://www.douyin.com/video/{aweme_id}" if aweme_id else fallback_source_url
    if platform == "bilibili":
        bvid = first_text(item, "bvid")
        if bvid:
            return f"https://www.bilibili.com/video/{bvid}"
        aid = first_text(item, "aid")
        return f"https://www.bilibili.com/video/av{aid}" if aid else fallback_source_url
    return fallback_source_url


def build_account_name(platform: str, item: dict[str, Any]) -> str:
    candidates = [
        first_text(item, "nickname", "user_name", "author", "account_name", "name", "screen_name"),
        nested_text(item, "user", "nickname"),
        nested_text(item, "user", "screen_name"),
        nested_text(item, "owner", "name"),
        nested_text(item, "author", "name"),
    ]
    return next((value for value in candidates if value), "unknown")


def build_title(platform: str, item: dict[str, Any], default_title: str) -> str:
    candidates = [
        first_text(item, "title", "note_title", "desc", "text_raw", "content"),
        nested_text(item, "module_author", "name"),
        nested_text(item, "archive", "title"),
    ]
    return next((value for value in candidates if value), default_title)


def build_snippet(item: dict[str, Any], title: str) -> str:
    candidates = [
        first_text(item, "desc", "content", "snippet", "text_raw", "summary", "dynamic"),
        nested_text(item, "desc", "text"),
    ]
    return next((value for value in candidates if value), title)


def build_publish_time(item: dict[str, Any]) -> str:
    value = (
        item.get("time")
        or item.get("publish_time")
        or item.get("create_time")
        or item.get("create_date_time")
        or item.get("pubtime")
        or item.get("created_at")
        or nested_value(item, "modules", "module_author", "pub_ts")
    )
    return normalize_datetime(value)


def build_read_count(platform: str, item: dict[str, Any]) -> int:
    if platform == "weibo":
        return coerce_int(item.get("attitudes_count"))
    if platform == "douyin":
        return coerce_int(nested_value(item, "statistics", "digg_count") or item.get("digg_count"))
    if platform == "bilibili":
        return coerce_int(nested_value(item, "stat", "view") or item.get("play") or item.get("play_count"))
    return coerce_int(item.get("liked_count"))


def build_comment_count(platform: str, item: dict[str, Any]) -> int:
    if platform == "bilibili":
        return coerce_int(nested_value(item, "stat", "reply") or item.get("comment") or item.get("comment_count"))
    return coerce_int(item.get("comment_count") or item.get("comments_count") or nested_value(item, "statistics", "comment_count"))


def build_source_id(platform: str, item: dict[str, Any], source_url: str) -> str:
    direct = first_text(item, "note_id", "id", "mid", "aweme_id", "bvid", "aid")
    if direct:
        return direct
    path = urlparse(source_url).path.rstrip("/")
    return path.split("/")[-1] if path else ""


def normalize_items(platform: str, keyword: str, items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    default_title = PLATFORM_SPECS[platform]["title_default"]
    for raw in items:
        item = unwrap_platform_item(platform, raw)
        title = build_title(platform, item, default_title)
        source_url = build_source_url(platform, item)
        if not source_url or not title:
            continue
        normalized.append(
            {
                "keyword": keyword,
                "title": title,
                "snippet": build_snippet(item, title),
                "source_url": source_url,
                "account_name": build_account_name(platform, item),
            }
        )
        if len(normalized) >= limit:
            break
    return normalized


def normalize_fetch_item(platform: str, item: dict[str, Any], fallback_source_url: str) -> dict[str, Any]:
    unwrapped = unwrap_platform_item(platform, item)
    default_title = PLATFORM_SPECS[platform]["title_default"]
    source_url = build_source_url(platform, unwrapped, fallback_source_url)
    return {
        "title": build_title(platform, unwrapped, default_title),
        "source_url": source_url,
        "account_name": build_account_name(platform, unwrapped),
        "publish_time": build_publish_time(unwrapped),
        "read_count": build_read_count(platform, unwrapped),
        "comment_count": build_comment_count(platform, unwrapped),
        "content_text": build_snippet(unwrapped, build_title(platform, unwrapped, default_title)),
        "source_id": build_source_id(platform, unwrapped, source_url),
    }


def build_start_command(args: argparse.Namespace) -> list[str]:
    command = list(args.start_command)
    command.extend(
        [
            "--platform",
            PLATFORM_SPECS[args.platform]["platform_arg"],
            "--lt",
            args.login_type,
            "--type",
            "search" if args.mode == "search" else "detail",
        ]
    )
    if args.mode == "fetch":
        command.extend(["--specified_id", args.source_url])
    return command


def main() -> int:
    args = parse_args()
    repo_dir = Path(args.repo).resolve()
    if not repo_dir.exists():
        raise RuntimeError(f"managed MediaCrawler checkout does not exist: {repo_dir}")

    with tempfile.TemporaryDirectory(prefix=f"mediacrawler-{args.platform}-") as temp_dir:
        temp_path = Path(temp_dir)
        config_dir = temp_path / "config"
        output_dir = temp_path / "output"
        config_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        (config_dir / "__init__.py").write_text(build_override_config_init(), encoding="utf-8")
        (config_dir / "base_config.py").write_text(
            build_override_base_config(
                repo_dir=repo_dir,
                platform=args.platform,
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
            payload = {"items": normalize_items(args.platform, args.keyword or "", items, args.limit)}
        else:
            payload = {
                "item": normalize_fetch_item(
                    args.platform,
                    next((item for item in items if isinstance(item, dict)), {}),
                    args.source_url or "",
                )
            }
        sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

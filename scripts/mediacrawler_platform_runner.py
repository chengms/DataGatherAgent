#!/usr/bin/env python3
"""Run MediaCrawler search/detail workflows for multiple platforms without modifying the upstream checkout."""

from __future__ import annotations

import argparse
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
    parser.add_argument("--login-type", default=None)
    parser.add_argument("--cookies", default=None)
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


def build_subprocess_env(cache_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    cache_dir.mkdir(parents=True, exist_ok=True)
    env["UV_CACHE_DIR"] = str(cache_dir)
    return env


def resolve_login_type_and_cookies(args: argparse.Namespace) -> tuple[str, str]:
    login_env = {
        "weibo": "WEIBO_MEDIACRAWLER_LOGIN_TYPE",
        "douyin": "DY_MEDIACRAWLER_LOGIN_TYPE",
        "bilibili": "BILI_MEDIACRAWLER_LOGIN_TYPE",
        "xiaohongshu": "XHS_MEDIACRAWLER_LOGIN_TYPE",
    }
    cookie_env = {
        "weibo": "WEIBO_MEDIACRAWLER_COOKIES",
        "douyin": "DY_MEDIACRAWLER_COOKIES",
        "bilibili": "BILI_MEDIACRAWLER_COOKIES",
        "xiaohongshu": "XHS_MEDIACRAWLER_COOKIES",
    }
    login_type = str(args.login_type or os.getenv(login_env[args.platform], "qrcode")).strip() or "qrcode"
    cookies = str(args.cookies if args.cookies is not None else os.getenv(cookie_env[args.platform], "")).strip()
    return login_type, cookies


def _extract_dict_items(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("items", "data", "notes", "videos", "contents", "comments"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def collect_saved_payload(output_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    contents: list[dict[str, Any]] = []
    comments: list[dict[str, Any]] = []
    json_files = sorted(output_dir.rglob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    for json_file in json_files:
        try:
            payload = json.loads(json_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        items = _extract_dict_items(payload)
        if not items:
            continue
        lower_name = json_file.name.lower()
        if "_comments_" in lower_name:
            comments.extend(items)
            continue
        if "_contents_" in lower_name:
            contents.extend(items)
            continue
        sample = items[0]
        if any(key in sample for key in ("comment_id", "parent_comment_id", "sub_comment_count")):
            comments.extend(items)
        else:
            contents.extend(items)
    return contents, comments


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
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y/%m/%d"):
            try:
                return datetime.strptime(text, fmt).replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")
            except ValueError:
                continue
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
        first_text(item, "note_url", "aweme_url", "video_url", "url", "share_url", "content_url", "jump_url")
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
        or item.get("create_date_time")
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
        return coerce_int(item.get("attitudes_count") or item.get("liked_count"))
    if platform == "douyin":
        return coerce_int(nested_value(item, "statistics", "digg_count") or item.get("digg_count") or item.get("liked_count"))
    if platform == "bilibili":
        return coerce_int(
            nested_value(item, "stat", "view")
            or item.get("play")
            or item.get("play_count")
            or item.get("video_play_count")
        )
    return coerce_int(item.get("liked_count"))


def build_comment_count(platform: str, item: dict[str, Any]) -> int:
    if platform == "bilibili":
        return coerce_int(
            nested_value(item, "stat", "reply")
            or item.get("comment")
            or item.get("comment_count")
            or item.get("video_comment")
        )
    return coerce_int(
        item.get("comment_count")
        or item.get("comments_count")
        or nested_value(item, "statistics", "comment_count")
    )


def build_source_id(platform: str, item: dict[str, Any], source_url: str) -> str:
    direct = first_text(item, "note_id", "id", "mid", "aweme_id", "video_id", "bvid", "aid")
    if direct:
        return direct
    path = urlparse(source_url).path.rstrip("/")
    return path.split("/")[-1] if path else ""


def infer_content_kind(platform: str, item: dict[str, Any], source_url: str) -> str:
    raw = first_text(item, "content_kind", "type", "video_type", "aweme_type")
    if isinstance(raw, str):
        low = raw.lower()
        if "video" in low:
            return "video"
        if "note" in low:
            return "note"
    if platform in {"douyin", "bilibili"}:
        return "video"
    if platform == "xiaohongshu":
        return "note"
    if "video" in source_url:
        return "video"
    return "article"


def content_id_from_url(platform: str, source_url: str) -> str:
    parsed = urlparse(source_url)
    path = parsed.path.rstrip("/")
    if not path:
        return ""
    token = path.split("/")[-1]
    if platform == "bilibili" and token.startswith("av"):
        return token[2:]
    return token


def filter_comments_by_source_id(platform: str, source_id: str, comments: list[dict[str, Any]], limit: int = 50) -> list[dict[str, Any]]:
    if not source_id:
        return []
    id_fields = {
        "xiaohongshu": ("note_id",),
        "weibo": ("note_id",),
        "douyin": ("aweme_id",),
        "bilibili": ("video_id",),
    }.get(platform, ("note_id", "aweme_id", "video_id"))
    matched: list[dict[str, Any]] = []
    for item in comments:
        for field in id_fields:
            if str(item.get(field) or "") == source_id:
                matched.append(item)
                break
        if len(matched) >= limit:
            break
    return matched


def normalize_comment_items(comments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in comments:
        content = first_text(item, "content", "text")
        if not content:
            continue
        normalized.append(
            {
                "nickname": first_text(item, "nickname", "user_name", "screen_name") or "匿名用户",
                "content": content,
                "publish_time": normalize_datetime(item.get("create_date_time") or item.get("publish_time") or item.get("create_time")),
                "like_count": coerce_int(item.get("like_count") or item.get("comment_like_count") or item.get("digg_count")),
                "sub_comment_count": coerce_int(item.get("sub_comment_count")),
            }
        )
    return normalized


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
                "content_kind": infer_content_kind(platform, item, source_url),
            }
        )
        if len(normalized) >= limit:
            break
    return normalized


def pick_best_content_item(platform: str, contents: list[dict[str, Any]], source_url: str) -> dict[str, Any]:
    if not contents:
        return {}
    source_id = content_id_from_url(platform, source_url)
    if source_id:
        for item in contents:
            if build_source_id(platform, item, build_source_url(platform, item, source_url)) == source_id:
                return item
    return contents[0]


def normalize_fetch_item(platform: str, contents: list[dict[str, Any]], comments: list[dict[str, Any]], fallback_source_url: str) -> dict[str, Any]:
    unwrapped = unwrap_platform_item(platform, pick_best_content_item(platform, contents, fallback_source_url))
    default_title = PLATFORM_SPECS[platform]["title_default"]
    source_url = build_source_url(platform, unwrapped, fallback_source_url)
    source_id = build_source_id(platform, unwrapped, source_url)
    return {
        "title": build_title(platform, unwrapped, default_title),
        "source_url": source_url,
        "account_name": build_account_name(platform, unwrapped),
        "publish_time": build_publish_time(unwrapped),
        "read_count": build_read_count(platform, unwrapped),
        "comment_count": build_comment_count(platform, unwrapped),
        "content_text": build_snippet(unwrapped, build_title(platform, unwrapped, default_title)),
        "source_id": source_id,
        "content_kind": infer_content_kind(platform, unwrapped, source_url),
        "comments": normalize_comment_items(filter_comments_by_source_id(platform, source_id, comments)),
    }


def build_start_command(args: argparse.Namespace, output_dir: Path, login_type: str, cookies: str) -> list[str]:
    command = list(args.start_command)
    crawler_type = "search" if args.mode == "search" else "detail"
    command.extend(
        [
            "--platform",
            PLATFORM_SPECS[args.platform]["platform_arg"],
            "--lt",
            login_type,
            "--type",
            crawler_type,
            "--save_data_option",
            "json",
            "--save_data_path",
            str(output_dir),
            "--get_comment",
            "true",
            "--get_sub_comment",
            "false",
        ]
    )
    if cookies:
        command.extend(["--cookies", cookies])
    if args.mode == "search":
        command.extend(["--keywords", args.keyword or ""])
    else:
        command.extend(["--specified_id", args.source_url])
    return command


def main() -> int:
    args = parse_args()
    repo_dir = Path(args.repo).resolve()
    if not repo_dir.exists():
        raise RuntimeError(f"managed MediaCrawler checkout does not exist: {repo_dir}")

    with tempfile.TemporaryDirectory(prefix=f"mediacrawler-{args.platform}-") as temp_dir:
        temp_root = Path(temp_dir)
        output_dir = temp_root / "output"
        cache_dir = temp_root / "uv-cache"
        stdout_path = temp_root / "stdout.log"
        stderr_path = temp_root / "stderr.log"
        output_dir.mkdir(parents=True, exist_ok=True)
        login_type, cookies = resolve_login_type_and_cookies(args)
        with stdout_path.open("w", encoding="utf-8", errors="replace") as stdout_handle, stderr_path.open(
            "w", encoding="utf-8", errors="replace"
        ) as stderr_handle:
            completed = subprocess.run(
                build_start_command(args, output_dir, login_type, cookies),
                cwd=repo_dir,
                env=build_subprocess_env(cache_dir),
                stdin=subprocess.DEVNULL,
                stdout=stdout_handle,
                stderr=stderr_handle,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        if completed.returncode != 0:
            stderr_tail = stderr_path.read_text(encoding="utf-8", errors="replace")[-4000:]
            if not stderr_tail:
                stderr_tail = stdout_path.read_text(encoding="utf-8", errors="replace")[-4000:]
            sys.stderr.write(stderr_tail)
            return completed.returncode

        contents, comments = collect_saved_payload(output_dir)
        if args.mode == "search":
            payload = {"items": normalize_items(args.platform, args.keyword or "", contents, args.limit)}
        else:
            payload = {
                "item": normalize_fetch_item(
                    args.platform,
                    contents,
                    comments,
                    args.source_url or "",
                )
            }
        sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

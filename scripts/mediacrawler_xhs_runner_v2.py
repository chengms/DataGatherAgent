#!/usr/bin/env python3
"""Run MediaCrawler Xiaohongshu search/detail workflow and normalize payloads."""

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run managed MediaCrawler Xiaohongshu workflow.")
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


def build_subprocess_env(cache_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    cache_dir.mkdir(parents=True, exist_ok=True)
    env["UV_CACHE_DIR"] = str(cache_dir)
    return env


def _extract_dict_items(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("items", "data", "notes", "contents", "comments"):
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
                return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(UTC).isoformat().replace("+00:00", "Z")
            except ValueError:
                pass
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
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


def extract_note_id(source_url: str) -> str:
    parsed = urlparse(source_url)
    path = parsed.path.rstrip("/")
    if not path:
        return ""
    return path.split("/")[-1]


def build_source_url(item: dict[str, Any], fallback_source_url: str = "") -> str:
    return (
        first_text(item, "note_url", "url", "share_url")
        or nested_text(item, "share_info", "share_url")
        or fallback_source_url
    )


def infer_content_kind(item: dict[str, Any], source_url: str) -> str:
    raw_type = (first_text(item, "note_type", "type") or "").lower()
    if "video" in raw_type or "video" in source_url:
        return "video"
    return "note"


def normalize_search_items(keyword: str, items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in items:
        title = first_text(item, "title", "note_title", "desc")
        source_url = build_source_url(item)
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
                "content_kind": infer_content_kind(item, source_url),
            }
        )
        if len(normalized) >= limit:
            break
    return normalized


def filter_comments_by_source_id(source_id: str, comments: list[dict[str, Any]], limit: int = 50) -> list[dict[str, Any]]:
    if not source_id:
        return []
    matched: list[dict[str, Any]] = []
    for item in comments:
        if str(item.get("note_id") or "") == source_id:
            matched.append(item)
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
                "publish_time": normalize_datetime(item.get("create_date_time") or item.get("create_time")),
                "like_count": coerce_int(item.get("like_count") or item.get("comment_like_count")),
                "sub_comment_count": coerce_int(item.get("sub_comment_count")),
            }
        )
    return normalized


def pick_best_content_item(contents: list[dict[str, Any]], source_url: str) -> dict[str, Any]:
    if not contents:
        return {}
    source_id = extract_note_id(source_url)
    if source_id:
        for item in contents:
            item_url = build_source_url(item, source_url)
            item_id = first_text(item, "note_id", "id") or extract_note_id(item_url)
            if item_id == source_id:
                return item
    return contents[0]


def normalize_fetch_item(contents: list[dict[str, Any]], comments: list[dict[str, Any]], fallback_source_url: str) -> dict[str, Any]:
    item = pick_best_content_item(contents, fallback_source_url)
    source_url = build_source_url(item, fallback_source_url)
    source_id = first_text(item, "note_id", "id") or extract_note_id(source_url)
    title = first_text(item, "title", "note_title", "desc") or "小红书内容"
    publish_time = normalize_datetime(
        item.get("time") or item.get("publish_time") or item.get("create_time") or item.get("create_date_time")
    )
    return {
        "title": title,
        "source_url": source_url,
        "account_name": (
            first_text(item, "nickname", "user_nickname", "author", "account_name")
            or nested_text(item, "user", "nickname")
            or "unknown"
        ),
        "publish_time": publish_time,
        "read_count": coerce_int(item.get("liked_count") or nested_value(item, "interact_info", "liked_count")),
        "comment_count": coerce_int(item.get("comment_count") or nested_value(item, "interact_info", "comment_count")),
        "content_text": first_text(item, "desc", "content", "title") or "",
        "source_id": source_id,
        "content_kind": infer_content_kind(item, source_url),
        "comments": normalize_comment_items(filter_comments_by_source_id(source_id, comments)),
    }


def build_start_command(args: argparse.Namespace, output_dir: Path) -> list[str]:
    command = list(args.start_command)
    crawler_type = "search" if args.mode == "search" else "detail"
    command.extend(
        [
            "--lt",
            args.login_type,
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
    if args.cookies:
        command.extend(["--cookies", args.cookies])
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

    with tempfile.TemporaryDirectory(prefix="mediacrawler-xhs-") as temp_dir:
        temp_root = Path(temp_dir)
        output_dir = temp_root / "output"
        cache_dir = temp_root / "uv-cache"
        stdout_path = temp_root / "stdout.log"
        stderr_path = temp_root / "stderr.log"
        output_dir.mkdir(parents=True, exist_ok=True)
        with stdout_path.open("w", encoding="utf-8", errors="replace") as stdout_handle, stderr_path.open(
            "w", encoding="utf-8", errors="replace"
        ) as stderr_handle:
            completed = subprocess.run(
                build_start_command(args, output_dir),
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
            payload = {"items": normalize_search_items(args.keyword or "", contents, args.limit)}
        else:
            payload = {"item": normalize_fetch_item(contents, comments, args.source_url or "")}
        sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
import os
import subprocess
import sys
from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from app.adapters.base import AdapterInfo, BaseDiscoveryAdapter, BaseFetchAdapter
from app.adapters.html_utils import text_to_html_fragment
from app.core.config import BASE_DIR, EXTERNAL_TOOLS_DIR
from app.core.exceptions import FetchRequestError, SearchRequestError
from app.schemas.workflow import ArticleComment, DiscoveryCandidate, FetchedArticle


@dataclass(frozen=True)
class ExternalRepositorySpec:
    slug: str
    default_dirname: str
    remote_url: str
    update_strategy: str = "git-pull"
    env_var: str | None = None

    def resolve_path(self) -> Path:
        configured = os.getenv(self.env_var) if self.env_var else None
        if configured:
            candidate = Path(configured).expanduser()
            if not candidate.is_absolute():
                candidate = (BASE_DIR / candidate).resolve()
            return candidate
        return (EXTERNAL_TOOLS_DIR / self.default_dirname).resolve()


@dataclass(frozen=True)
class ExternalCommandSpec:
    argv: list[str]
    cwd: Path
    env: dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 300


@dataclass(frozen=True)
class ExternalRunResult:
    argv: list[str]
    cwd: Path
    exit_code: int
    stdout: str
    stderr: str

    def parse_json(self) -> object:
        return json.loads(self.stdout)


class ExternalToolRunner:
    def run(self, command: ExternalCommandSpec) -> ExternalRunResult:
        env = os.environ.copy()
        env.update(command.env)
        completed = subprocess.run(
            command.argv,
            cwd=command.cwd,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=command.timeout_seconds,
            check=False,
        )
        return ExternalRunResult(
            argv=command.argv,
            cwd=command.cwd,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


class ExternalToolAdapterMixin:
    repository: ExternalRepositorySpec
    runner: ExternalToolRunner

    def __init__(self, runner: ExternalToolRunner | None = None) -> None:
        self.runner = runner or ExternalToolRunner()

    def managed_repository_path(self) -> Path:
        return self.repository.resolve_path()

    def managed_repository_exists(self) -> bool:
        return self.managed_repository_path().exists()

    def describe_managed_repository(self) -> dict[str, str]:
        return {
            "slug": self.repository.slug,
            "remote_url": self.repository.remote_url,
            "path": str(self.managed_repository_path()),
            "update_strategy": self.repository.update_strategy,
        }

    def _normalize_comments(self, raw: object) -> list[ArticleComment]:
        if not isinstance(raw, list):
            return []
        comments: list[ArticleComment] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            content = item.get("content") or item.get("text")
            if not isinstance(content, str) or not content.strip():
                continue
            comments.append(
                ArticleComment(
                    nickname=str(
                        item.get("nickname")
                        or item.get("user_name")
                        or item.get("screen_name")
                        or item.get("account_name")
                        or "匿名用户"
                    ),
                    content=content.strip(),
                    publish_time=str(item.get("publish_time") or item.get("create_date_time") or item.get("create_time") or ""),
                    like_count=int(item.get("like_count") or item.get("comment_like_count") or item.get("digg_count") or 0),
                    sub_comment_count=int(item.get("sub_comment_count") or item.get("reply_comment_total") or item.get("total_number") or 0),
                )
            )
        return comments

    def _infer_content_kind(self, platform: str, item: dict, source_url: str) -> str:
        declared = item.get("content_kind")
        if isinstance(declared, str) and declared in {"article", "video", "mixed", "note"}:
            return declared
        if platform in {"douyin", "bilibili"}:
            return "video"
        if platform == "xiaohongshu":
            raw_type = str(item.get("note_type") or item.get("type") or "").lower()
            if "video" in raw_type:
                return "video"
            return "note"
        if "video" in source_url:
            return "video"
        return "article"

    def _resolve_content_html(self, item: dict, fallback_text: str) -> str:
        raw_html = item.get("content_html") or item.get("html") or item.get("body_html")
        if isinstance(raw_html, str) and raw_html.strip():
            return raw_html
        return text_to_html_fragment(fallback_text)


class ExternalDiscoveryAdapter(ExternalToolAdapterMixin, BaseDiscoveryAdapter):
    @abstractmethod
    def build_discovery_command(self, keyword: str, limit: int) -> ExternalCommandSpec:
        raise NotImplementedError

    @abstractmethod
    def parse_discovery_result(
        self,
        keyword: str,
        result: ExternalRunResult,
    ) -> list[DiscoveryCandidate]:
        raise NotImplementedError

    def _discover(self, keyword: str, limit: int) -> list[DiscoveryCandidate]:
        command = self.build_discovery_command(keyword=keyword, limit=limit)
        result = self.runner.run(command)
        if result.exit_code != 0:
            raise SearchRequestError(
                f"external discovery command failed with exit code {result.exit_code}",
                details={
                    "adapter": self.info.name,
                    "argv": command.argv,
                    "cwd": str(command.cwd),
                    "stderr": result.stderr[-1000:],
                },
            )
        return self.parse_discovery_result(keyword=keyword, result=result)


class ExternalFetchAdapter(ExternalToolAdapterMixin, BaseFetchAdapter):
    @abstractmethod
    def build_fetch_command(self, candidate: DiscoveryCandidate) -> ExternalCommandSpec:
        raise NotImplementedError

    @abstractmethod
    def parse_fetch_result(
        self,
        candidate: DiscoveryCandidate,
        result: ExternalRunResult,
    ) -> FetchedArticle:
        raise NotImplementedError

    def _fetch_article(self, candidate: DiscoveryCandidate) -> FetchedArticle:
        command = self.build_fetch_command(candidate)
        result = self.runner.run(command)
        if result.exit_code != 0:
            raise FetchRequestError(
                f"external fetch command failed with exit code {result.exit_code}",
                details={
                    "adapter": self.info.name,
                    "argv": command.argv,
                    "cwd": str(command.cwd),
                    "stderr": result.stderr[-1000:],
                    "source_url": candidate.source_url,
                },
            )
        return self.parse_fetch_result(candidate=candidate, result=result)


class MediaCrawlerXiaohongshuDiscoveryAdapter(ExternalDiscoveryAdapter):
    info = AdapterInfo(
        name="xiaohongshu_external_search",
        kind="search",
        platform="xiaohongshu",
        description="Managed MediaCrawler-based Xiaohongshu discovery adapter scaffold backed by a clean upstream repository checkout.",
        live=True,
    )
    repository = ExternalRepositorySpec(
        slug="mediacrawler",
        default_dirname="MediaCrawler",
        remote_url="git@github.com:NanmiCoder/MediaCrawler.git",
        env_var="DATA_GATHER_XHS_CRAWLER_DIR",
    )

    def build_discovery_command(self, keyword: str, limit: int) -> ExternalCommandSpec:
        repo_path = self.managed_repository_path()
        if not repo_path.exists():
            raise SearchRequestError(
                "managed MediaCrawler checkout is missing",
                details={
                    **self.describe_managed_repository(),
                    "service_hint": "Run ./up.sh or .\\up.ps1 to prepare the managed MediaCrawler checkout.",
                },
            )
        runner_script = BASE_DIR.parent / "scripts" / "mediacrawler_xhs_runner_v2.py"
        return ExternalCommandSpec(
            argv=[
                sys.executable,
                str(runner_script),
                "--repo",
                str(repo_path),
                "--keyword",
                keyword,
                "--limit",
                str(limit),
            ],
            cwd=repo_path,
            timeout_seconds=600,
        )

    def parse_discovery_result(
        self,
        keyword: str,
        result: ExternalRunResult,
    ) -> list[DiscoveryCandidate]:
        payload = result.parse_json()
        items = payload["items"] if isinstance(payload, dict) else []
        candidates: list[DiscoveryCandidate] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            title = item.get("title")
            source_url = item.get("source_url")
            account_name = item.get("account_name")
            if not isinstance(title, str) or not isinstance(source_url, str) or not isinstance(account_name, str):
                continue
            candidates.append(
                DiscoveryCandidate(
                    keyword=keyword,
                    source_engine=self.info.name,
                    title=title,
                    snippet=str(item.get("snippet", "")),
                    source_url=source_url,
                    account_name=account_name,
                    discovered_at=datetime.now(UTC),
                )
            )
        return candidates


class MediaCrawlerXiaohongshuFetchAdapter(ExternalFetchAdapter):
    info = AdapterInfo(
        name="xiaohongshu_external_fetch",
        kind="fetch",
        platform="xiaohongshu",
        description="Managed MediaCrawler-based Xiaohongshu article fetch adapter backed by a clean upstream repository checkout.",
        live=True,
    )
    repository = MediaCrawlerXiaohongshuDiscoveryAdapter.repository

    def build_fetch_command(self, candidate: DiscoveryCandidate) -> ExternalCommandSpec:
        repo_path = self.managed_repository_path()
        if not repo_path.exists():
            raise FetchRequestError(
                "managed MediaCrawler checkout is missing",
                details={
                    **self.describe_managed_repository(),
                    "service_hint": "Run ./up.sh or .\\up.ps1 to prepare the managed MediaCrawler checkout.",
                },
            )
        runner_script = BASE_DIR.parent / "scripts" / "mediacrawler_xhs_runner_v2.py"
        return ExternalCommandSpec(
            argv=[
                sys.executable,
                str(runner_script),
                "--mode",
                "fetch",
                "--repo",
                str(repo_path),
                "--source-url",
                candidate.source_url,
            ],
            cwd=repo_path,
            timeout_seconds=600,
        )

    def parse_fetch_result(
        self,
        candidate: DiscoveryCandidate,
        result: ExternalRunResult,
    ) -> FetchedArticle:
        payload = result.parse_json()
        item = payload.get("item") if isinstance(payload, dict) else None
        if not isinstance(item, dict):
            raise FetchRequestError(
                "external MediaCrawler fetch command returned an invalid payload",
                details={"adapter": self.info.name, "source_url": candidate.source_url},
            )

        publish_time_raw = item.get("publish_time")
        if not isinstance(publish_time_raw, str):
            raise FetchRequestError(
                "external MediaCrawler fetch payload is missing publish_time",
                details={"adapter": self.info.name, "source_url": candidate.source_url},
            )

        content_text = str(item.get("content_text") or candidate.snippet)
        return FetchedArticle(
            keyword=candidate.keyword,
            platform="xiaohongshu",
            source_engine=self.info.name,
            content_kind=self._infer_content_kind("xiaohongshu", item, candidate.source_url),
            title=str(item.get("title") or candidate.title),
            source_url=str(item.get("source_url") or candidate.source_url),
            account_name=str(item.get("account_name") or candidate.account_name),
            publish_time=datetime.fromisoformat(publish_time_raw.replace("Z", "+00:00")),
            read_count=int(item.get("read_count") or 0),
            comment_count=int(item.get("comment_count") or 0),
            content_text=content_text,
            content_html=self._resolve_content_html(item, content_text),
            source_id=str(item.get("source_id") or ""),
            comments=self._normalize_comments(item.get("comments")),
        )


class MediaCrawlerPlatformDiscoveryAdapter(ExternalDiscoveryAdapter):
    platform_name: str
    runner_name: str

    def build_discovery_command(self, keyword: str, limit: int) -> ExternalCommandSpec:
        repo_path = self.managed_repository_path()
        if not repo_path.exists():
            raise SearchRequestError(
                "managed MediaCrawler checkout is missing",
                details={
                    **self.describe_managed_repository(),
                    "service_hint": "Run ./up.sh or .\\up.ps1 to prepare the managed MediaCrawler checkout.",
                },
            )
        runner_script = BASE_DIR.parent / "scripts" / "mediacrawler_platform_runner.py"
        return ExternalCommandSpec(
            argv=[
                sys.executable,
                str(runner_script),
                "--platform",
                self.platform_name,
                "--repo",
                str(repo_path),
                "--keyword",
                keyword,
                "--limit",
                str(limit),
            ],
            cwd=repo_path,
            timeout_seconds=600,
        )

    def parse_discovery_result(
        self,
        keyword: str,
        result: ExternalRunResult,
    ) -> list[DiscoveryCandidate]:
        payload = result.parse_json()
        items = payload["items"] if isinstance(payload, dict) else []
        candidates: list[DiscoveryCandidate] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            title = item.get("title")
            source_url = item.get("source_url")
            account_name = item.get("account_name")
            if not isinstance(title, str) or not isinstance(source_url, str) or not isinstance(account_name, str):
                continue
            candidates.append(
                DiscoveryCandidate(
                    keyword=keyword,
                    source_engine=self.info.name,
                    title=title,
                    snippet=str(item.get("snippet", "")),
                    source_url=source_url,
                    account_name=account_name,
                    discovered_at=datetime.now(UTC),
                )
            )
        return candidates


class MediaCrawlerPlatformFetchAdapter(ExternalFetchAdapter):
    platform_name: str

    def build_fetch_command(self, candidate: DiscoveryCandidate) -> ExternalCommandSpec:
        repo_path = self.managed_repository_path()
        if not repo_path.exists():
            raise FetchRequestError(
                "managed MediaCrawler checkout is missing",
                details={
                    **self.describe_managed_repository(),
                    "service_hint": "Run ./up.sh or .\\up.ps1 to prepare the managed MediaCrawler checkout.",
                },
            )
        runner_script = BASE_DIR.parent / "scripts" / "mediacrawler_platform_runner.py"
        return ExternalCommandSpec(
            argv=[
                sys.executable,
                str(runner_script),
                "--platform",
                self.platform_name,
                "--mode",
                "fetch",
                "--repo",
                str(repo_path),
                "--source-url",
                candidate.source_url,
            ],
            cwd=repo_path,
            timeout_seconds=600,
        )

    def parse_fetch_result(
        self,
        candidate: DiscoveryCandidate,
        result: ExternalRunResult,
    ) -> FetchedArticle:
        payload = result.parse_json()
        item = payload.get("item") if isinstance(payload, dict) else None
        if not isinstance(item, dict):
            raise FetchRequestError(
                "external MediaCrawler fetch command returned an invalid payload",
                details={"adapter": self.info.name, "source_url": candidate.source_url},
            )

        publish_time_raw = item.get("publish_time")
        if not isinstance(publish_time_raw, str):
            raise FetchRequestError(
                "external MediaCrawler fetch payload is missing publish_time",
                details={"adapter": self.info.name, "source_url": candidate.source_url},
            )

        content_text = str(item.get("content_text") or candidate.snippet)
        return FetchedArticle(
            keyword=candidate.keyword,
            platform=self.platform_name,
            source_engine=self.info.name,
            content_kind=self._infer_content_kind(self.platform_name, item, candidate.source_url),
            title=str(item.get("title") or candidate.title),
            source_url=str(item.get("source_url") or candidate.source_url),
            account_name=str(item.get("account_name") or candidate.account_name),
            publish_time=datetime.fromisoformat(publish_time_raw.replace("Z", "+00:00")),
            read_count=int(item.get("read_count") or 0),
            comment_count=int(item.get("comment_count") or 0),
            content_text=content_text,
            content_html=self._resolve_content_html(item, content_text),
            source_id=str(item.get("source_id") or ""),
            comments=self._normalize_comments(item.get("comments")),
        )


class MediaCrawlerWeiboDiscoveryAdapter(MediaCrawlerPlatformDiscoveryAdapter):
    info = AdapterInfo(
        name="weibo_external_search",
        kind="search",
        platform="weibo",
        description="Managed MediaCrawler-based Weibo discovery adapter backed by a clean upstream repository checkout.",
        live=True,
    )
    platform_name = "weibo"
    repository = MediaCrawlerXiaohongshuDiscoveryAdapter.repository


class MediaCrawlerWeiboFetchAdapter(MediaCrawlerPlatformFetchAdapter):
    info = AdapterInfo(
        name="weibo_external_fetch",
        kind="fetch",
        platform="weibo",
        description="Managed MediaCrawler-based Weibo fetch adapter backed by a clean upstream repository checkout.",
        live=True,
    )
    platform_name = "weibo"
    repository = MediaCrawlerXiaohongshuDiscoveryAdapter.repository


class MediaCrawlerBilibiliDiscoveryAdapter(MediaCrawlerPlatformDiscoveryAdapter):
    info = AdapterInfo(
        name="bilibili_external_search",
        kind="search",
        platform="bilibili",
        description="Managed MediaCrawler-based Bilibili discovery adapter backed by a clean upstream repository checkout.",
        live=True,
    )
    platform_name = "bilibili"
    repository = MediaCrawlerXiaohongshuDiscoveryAdapter.repository


class MediaCrawlerBilibiliFetchAdapter(MediaCrawlerPlatformFetchAdapter):
    info = AdapterInfo(
        name="bilibili_external_fetch",
        kind="fetch",
        platform="bilibili",
        description="Managed MediaCrawler-based Bilibili fetch adapter backed by a clean upstream repository checkout.",
        live=True,
    )
    platform_name = "bilibili"
    repository = MediaCrawlerXiaohongshuDiscoveryAdapter.repository


class MediaCrawlerDouyinDiscoveryAdapter(MediaCrawlerPlatformDiscoveryAdapter):
    info = AdapterInfo(
        name="douyin_external_search",
        kind="search",
        platform="douyin",
        description="Managed MediaCrawler-based Douyin discovery adapter backed by a clean upstream repository checkout.",
        live=True,
    )
    platform_name = "douyin"
    repository = MediaCrawlerXiaohongshuDiscoveryAdapter.repository


class MediaCrawlerDouyinFetchAdapter(MediaCrawlerPlatformFetchAdapter):
    info = AdapterInfo(
        name="douyin_external_fetch",
        kind="fetch",
        platform="douyin",
        description="Managed MediaCrawler-based Douyin fetch adapter backed by a clean upstream repository checkout.",
        live=True,
    )
    platform_name = "douyin"
    repository = MediaCrawlerXiaohongshuDiscoveryAdapter.repository

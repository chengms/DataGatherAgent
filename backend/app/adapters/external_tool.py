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
from app.core.config import BASE_DIR, EXTERNAL_TOOLS_DIR
from app.core.exceptions import FetchRequestError, SearchRequestError
from app.schemas.workflow import DiscoveryCandidate, FetchedArticle


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
            return Path(configured).expanduser().resolve()
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


class StubWechatExporterDiscoveryAdapter(ExternalDiscoveryAdapter):
    info = AdapterInfo(
        name="wechat_exporter_search",
        kind="search",
        platform="wechat",
        description="External-tool discovery adapter placeholder for a mature WeChat exporter/crawler repository.",
        live=False,
    )
    repository = ExternalRepositorySpec(
        slug="wechat-exporter",
        default_dirname="wechat-exporter",
        remote_url="git@github.com:wechat-article/wechat-article-exporter.git",
        env_var="DATA_GATHER_WECHAT_EXPORTER_DIR",
    )

    def build_discovery_command(self, keyword: str, limit: int) -> ExternalCommandSpec:
        raise SearchRequestError(
            "external WeChat discovery adapter is scaffolded but not wired to a concrete repository command yet",
            details=self.describe_managed_repository(),
        )

    def parse_discovery_result(
        self,
        keyword: str,
        result: ExternalRunResult,
    ) -> list[DiscoveryCandidate]:
        raise NotImplementedError


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
        runner_script = BASE_DIR.parent / "scripts" / "mediacrawler_xhs_runner.py"
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

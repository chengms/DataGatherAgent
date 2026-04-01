from __future__ import annotations

import json
import os
import subprocess
from abc import abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from app.adapters.base import AdapterInfo, BaseDiscoveryAdapter, BaseFetchAdapter
from app.core.config import EXTERNAL_TOOLS_DIR
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


class StubXiaohongshuDiscoveryAdapter(ExternalDiscoveryAdapter):
    info = AdapterInfo(
        name="xiaohongshu_external_search",
        kind="search",
        platform="xiaohongshu",
        description="External-tool discovery adapter placeholder for a mature Xiaohongshu crawler repository.",
        live=False,
    )
    repository = ExternalRepositorySpec(
        slug="xiaohongshu-crawler",
        default_dirname="xiaohongshu-crawler",
        remote_url="git@github.com:NanmiCoder/MediaCrawler.git",
        env_var="DATA_GATHER_XHS_CRAWLER_DIR",
    )

    def build_discovery_command(self, keyword: str, limit: int) -> ExternalCommandSpec:
        raise SearchRequestError(
            "external Xiaohongshu discovery adapter is scaffolded but not wired to a concrete repository command yet",
            details=self.describe_managed_repository(),
        )

    def parse_discovery_result(
        self,
        keyword: str,
        result: ExternalRunResult,
    ) -> list[DiscoveryCandidate]:
        raise NotImplementedError

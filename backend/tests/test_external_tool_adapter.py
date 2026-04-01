import json
import unittest
from datetime import UTC, datetime
from pathlib import Path

from app.adapters.base import AdapterInfo
from app.adapters.external_tool import (
    ExternalCommandSpec,
    ExternalDiscoveryAdapter,
    ExternalRepositorySpec,
    ExternalRunResult,
    ExternalToolRunner,
    MediaCrawlerXiaohongshuDiscoveryAdapter,
    StubWechatExporterDiscoveryAdapter,
)
from app.core.exceptions import SearchRequestError
from app.schemas.workflow import DiscoveryCandidate


class FakeRunner(ExternalToolRunner):
    def __init__(self, result: ExternalRunResult) -> None:
        self.result = result

    def run(self, command: ExternalCommandSpec) -> ExternalRunResult:
        return self.result


class DemoExternalDiscoveryAdapter(ExternalDiscoveryAdapter):
    info = AdapterInfo(
        name="demo_external_search",
        kind="search",
        platform="wechat",
        description="Test external discovery adapter.",
    )
    repository = ExternalRepositorySpec(
        slug="demo",
        default_dirname="demo",
        remote_url="git@github.com:example/demo.git",
        env_var="DATA_GATHER_DEMO_TOOL_DIR",
    )

    def build_discovery_command(self, keyword: str, limit: int) -> ExternalCommandSpec:
        return ExternalCommandSpec(argv=["demo", keyword, str(limit)], cwd=Path("."))

    def parse_discovery_result(
        self,
        keyword: str,
        result: ExternalRunResult,
    ) -> list[DiscoveryCandidate]:
        payload = json.loads(result.stdout)
        return [
            DiscoveryCandidate(
                keyword=keyword,
                source_engine=self.info.name,
                title=item["title"],
                snippet=item["snippet"],
                source_url=item["source_url"],
                account_name=item["account_name"],
                discovered_at=datetime.now(UTC),
            )
            for item in payload["items"]
        ]


class ExternalToolAdapterTests(unittest.TestCase):
    def test_external_discovery_adapter_parses_runner_output(self) -> None:
        runner = FakeRunner(
            ExternalRunResult(
                argv=["demo"],
                cwd=Path("."),
                exit_code=0,
                stdout=json.dumps(
                    {
                        "items": [
                            {
                                "title": "Article",
                                "snippet": "Summary",
                                "source_url": "https://example.com/article",
                                "account_name": "Example",
                            }
                        ]
                    }
                ),
                stderr="",
            )
        )
        adapter = DemoExternalDiscoveryAdapter(runner=runner)
        items = adapter.discover(keyword="AI", limit=1)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].source_engine, "demo_external_search")

    def test_external_discovery_adapter_raises_domain_error_on_nonzero_exit(self) -> None:
        runner = FakeRunner(
            ExternalRunResult(
                argv=["demo"],
                cwd=Path("."),
                exit_code=2,
                stdout="",
                stderr="boom",
            )
        )
        adapter = DemoExternalDiscoveryAdapter(runner=runner)
        with self.assertRaises(SearchRequestError):
            adapter.discover(keyword="AI", limit=1)

    def test_stub_adapter_exposes_managed_repository_metadata(self) -> None:
        adapter = StubWechatExporterDiscoveryAdapter()
        metadata = adapter.describe_managed_repository()
        self.assertEqual(metadata["slug"], "wechat-exporter")
        self.assertIn("wechat-article-exporter", metadata["remote_url"])

    def test_mediacrawler_adapter_points_to_managed_repo(self) -> None:
        adapter = MediaCrawlerXiaohongshuDiscoveryAdapter()
        metadata = adapter.describe_managed_repository()
        self.assertEqual(metadata["slug"], "mediacrawler")
        self.assertIn("MediaCrawler", metadata["path"])
        self.assertIn("NanmiCoder/MediaCrawler", metadata["remote_url"])


if __name__ == "__main__":
    unittest.main()

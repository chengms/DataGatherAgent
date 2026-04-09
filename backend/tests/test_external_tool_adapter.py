import json
import unittest
from datetime import UTC, datetime
from pathlib import Path

from app.adapters.base import AdapterInfo
from app.adapters.external_tool import (
    ExternalCommandSpec,
    ExternalDiscoveryAdapter,
    ExternalFetchAdapter,
    ExternalRepositorySpec,
    ExternalRunResult,
    ExternalToolRunner,
    MediaCrawlerBilibiliFetchAdapter,
    MediaCrawlerDouyinFetchAdapter,
    MediaCrawlerWeiboDiscoveryAdapter,
    MediaCrawlerXiaohongshuDiscoveryAdapter,
    MediaCrawlerXiaohongshuFetchAdapter,
)
from app.core.exceptions import FetchRequestError, SearchRequestError
from app.schemas.workflow import DiscoveryCandidate, FetchedArticle


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


class DemoExternalFetchAdapter(ExternalFetchAdapter):
    info = AdapterInfo(
        name="demo_external_fetch",
        kind="fetch",
        platform="xiaohongshu",
        description="Test external fetch adapter.",
    )
    repository = ExternalRepositorySpec(
        slug="demo",
        default_dirname="demo",
        remote_url="git@github.com:example/demo.git",
        env_var="DATA_GATHER_DEMO_TOOL_DIR",
    )

    def build_fetch_command(self, candidate: DiscoveryCandidate) -> ExternalCommandSpec:
        return ExternalCommandSpec(argv=["demo", candidate.source_url], cwd=Path("."))

    def parse_fetch_result(
        self,
        candidate: DiscoveryCandidate,
        result: ExternalRunResult,
    ) -> FetchedArticle:
        payload = json.loads(result.stdout)
        item = payload["item"]
        return FetchedArticle(
            keyword=candidate.keyword,
            platform="xiaohongshu",
            title=item["title"],
            source_url=item["source_url"],
            account_name=item["account_name"],
            publish_time=datetime.fromisoformat(item["publish_time"].replace("Z", "+00:00")),
            read_count=item["read_count"],
            comment_count=item["comment_count"],
            content_text=item["content_text"],
            source_id=item["source_id"],
        )


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

    def test_external_fetch_adapter_parses_runner_output(self) -> None:
        candidate = DiscoveryCandidate(
            keyword="AI",
            source_engine="demo_external_search",
            title="XHS Title",
            snippet="Summary",
            source_url="https://www.xiaohongshu.com/explore/demo",
            account_name="Author A",
            discovered_at=datetime.now(UTC),
        )
        runner = FakeRunner(
            ExternalRunResult(
                argv=["demo"],
                cwd=Path("."),
                exit_code=0,
                stdout=json.dumps(
                    {
                        "item": {
                            "title": "XHS Title",
                            "source_url": candidate.source_url,
                            "account_name": "Author A",
                            "publish_time": "2026-04-01T00:00:00Z",
                            "read_count": 120,
                            "comment_count": 8,
                            "content_text": "正文",
                            "source_id": "demo",
                        }
                    }
                ),
                stderr="",
            )
        )
        adapter = DemoExternalFetchAdapter(runner=runner)
        article = adapter.fetch_article(candidate)
        self.assertEqual(article.platform, "xiaohongshu")
        self.assertEqual(article.source_id, "demo")

    def test_external_fetch_adapter_raises_domain_error_on_nonzero_exit(self) -> None:
        candidate = DiscoveryCandidate(
            keyword="AI",
            source_engine="demo_external_search",
            title="XHS Title",
            snippet="Summary",
            source_url="https://www.xiaohongshu.com/explore/demo",
            account_name="Author A",
            discovered_at=datetime.now(UTC),
        )
        runner = FakeRunner(
            ExternalRunResult(
                argv=["demo"],
                cwd=Path("."),
                exit_code=2,
                stdout="",
                stderr="boom",
            )
        )
        adapter = DemoExternalFetchAdapter(runner=runner)
        with self.assertRaises(FetchRequestError):
            adapter.fetch_article(candidate)

    def test_mediacrawler_adapter_points_to_managed_repo(self) -> None:
        adapter = MediaCrawlerXiaohongshuDiscoveryAdapter()
        metadata = adapter.describe_managed_repository()
        self.assertEqual(metadata["slug"], "mediacrawler")
        self.assertIn("MediaCrawler", metadata["path"])
        self.assertIn("NanmiCoder/MediaCrawler", metadata["remote_url"])

    def test_mediacrawler_adapter_parses_normalized_output(self) -> None:
        adapter = MediaCrawlerXiaohongshuDiscoveryAdapter()
        result = ExternalRunResult(
            argv=["python"],
            cwd=Path("."),
            exit_code=0,
            stdout=json.dumps(
                {
                    "items": [
                        {
                            "title": "XHS Title",
                            "snippet": "XHS Summary",
                            "source_url": "https://www.xiaohongshu.com/explore/demo",
                            "account_name": "Author A",
                        }
                    ]
                }
            ),
            stderr="",
        )
        items = adapter.parse_discovery_result(keyword="AI", result=result)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].source_engine, "xiaohongshu_external_search")
        self.assertEqual(items[0].account_name, "Author A")

    def test_mediacrawler_fetch_adapter_points_to_managed_repo(self) -> None:
        adapter = MediaCrawlerXiaohongshuFetchAdapter()
        metadata = adapter.describe_managed_repository()
        self.assertEqual(metadata["slug"], "mediacrawler")
        self.assertIn("MediaCrawler", metadata["path"])

    def test_mediacrawler_fetch_adapter_parses_normalized_output(self) -> None:
        adapter = MediaCrawlerXiaohongshuFetchAdapter()
        candidate = DiscoveryCandidate(
            keyword="AI",
            source_engine="xiaohongshu_external_search",
            title="XHS Title",
            snippet="XHS Summary",
            source_url="https://www.xiaohongshu.com/explore/demo",
            account_name="Author A",
            discovered_at=datetime.now(UTC),
        )
        result = ExternalRunResult(
            argv=["python"],
            cwd=Path("."),
            exit_code=0,
            stdout=json.dumps(
                {
                    "item": {
                        "title": "XHS Title",
                        "source_url": "https://www.xiaohongshu.com/explore/demo",
                        "account_name": "Author A",
                        "publish_time": "2026-04-01T00:00:00Z",
                        "read_count": 321,
                        "comment_count": 17,
                        "content_text": "详细正文",
                        "source_id": "demo",
                    }
                }
            ),
            stderr="",
        )
        article = adapter.parse_fetch_result(candidate=candidate, result=result)
        self.assertEqual(article.platform, "xiaohongshu")
        self.assertEqual(article.read_count, 321)
        self.assertEqual(article.comment_count, 17)
        self.assertTrue(article.content_html.startswith("<p>"))

    def test_weibo_adapter_parses_normalized_output(self) -> None:
        adapter = MediaCrawlerWeiboDiscoveryAdapter()
        result = ExternalRunResult(
            argv=["python"],
            cwd=Path("."),
            exit_code=0,
            stdout=json.dumps(
                {
                    "items": [
                        {
                            "title": "Weibo Title",
                            "snippet": "Weibo Summary",
                            "source_url": "https://m.weibo.cn/detail/demo",
                            "account_name": "Author WB",
                        }
                    ]
                }
            ),
            stderr="",
        )
        items = adapter.parse_discovery_result(keyword="AI", result=result)
        self.assertEqual(items[0].source_engine, "weibo_external_search")
        self.assertEqual(items[0].source_url, "https://m.weibo.cn/detail/demo")

    def test_bilibili_fetch_adapter_parses_normalized_output(self) -> None:
        adapter = MediaCrawlerBilibiliFetchAdapter()
        candidate = DiscoveryCandidate(
            keyword="AI",
            source_engine="bilibili_external_search",
            title="Bilibili Title",
            snippet="summary",
            source_url="https://www.bilibili.com/video/BV1demo",
            account_name="UP A",
            discovered_at=datetime.now(UTC),
        )
        result = ExternalRunResult(
            argv=["python"],
            cwd=Path("."),
            exit_code=0,
            stdout=json.dumps(
                {
                    "item": {
                        "title": "Bilibili Title",
                        "source_url": "https://www.bilibili.com/video/BV1demo",
                        "account_name": "UP A",
                        "publish_time": "2026-04-01T00:00:00Z",
                        "read_count": 456,
                        "comment_count": 12,
                        "content_text": "video summary",
                        "source_id": "BV1demo",
                    }
                }
            ),
            stderr="",
        )
        article = adapter.parse_fetch_result(candidate=candidate, result=result)
        self.assertEqual(article.platform, "bilibili")
        self.assertEqual(article.source_id, "BV1demo")

    def test_douyin_fetch_adapter_parses_normalized_output(self) -> None:
        adapter = MediaCrawlerDouyinFetchAdapter()
        candidate = DiscoveryCandidate(
            keyword="AI",
            source_engine="douyin_external_search",
            title="Douyin Title",
            snippet="summary",
            source_url="https://www.douyin.com/video/demo",
            account_name="Creator A",
            discovered_at=datetime.now(UTC),
        )
        result = ExternalRunResult(
            argv=["python"],
            cwd=Path("."),
            exit_code=0,
            stdout=json.dumps(
                {
                    "item": {
                        "title": "Douyin Title",
                        "source_url": "https://www.douyin.com/video/demo",
                        "account_name": "Creator A",
                        "publish_time": "2026-04-01T00:00:00Z",
                        "read_count": 789,
                        "comment_count": 34,
                        "content_text": "video body",
                        "source_id": "demo",
                    }
                }
            ),
            stderr="",
        )
        article = adapter.parse_fetch_result(candidate=candidate, result=result)
        self.assertEqual(article.platform, "douyin")
        self.assertEqual(article.comment_count, 34)


if __name__ == "__main__":
    unittest.main()

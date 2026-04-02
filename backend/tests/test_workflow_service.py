import unittest
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from app.core.exceptions import FetchRequestError, SearchRequestError
from app.schemas.workflow import DiscoveryCandidate, FetchedArticle
from app.schemas.workflow import WorkflowPreviewRequest
from app.services.workflow import WorkflowService


class WorkflowServiceTests(unittest.TestCase):
    def test_multi_platform_preview_aggregates_candidates(self) -> None:
        request_payload = WorkflowPreviewRequest(
            keywords=["AI Agent"],
            platforms=["wechat", "xiaohongshu"],
            limit=1,
            top_k=2,
            fallback_to_mock=False,
        )
        wechat_discovery = MagicMock()
        wechat_discovery.discover.return_value = [
            DiscoveryCandidate(
                keyword="AI Agent",
                source_engine="wechat_exporter_search",
                title="Wechat Brief",
                snippet="summary",
                source_url="https://mp.weixin.qq.com/s/mock-1",
                account_name="AI Insight",
                discovered_at=datetime.now(UTC),
            )
        ]
        xhs_discovery = MagicMock()
        xhs_discovery.discover.return_value = [
            DiscoveryCandidate(
                keyword="AI Agent",
                source_engine="xiaohongshu_external_search",
                title="XHS Brief",
                snippet="summary",
                source_url="https://www.xiaohongshu.com/explore/mock-1",
                account_name="XHS Insight",
                discovered_at=datetime.now(UTC),
            )
        ]
        wechat_fetch = MagicMock()
        wechat_fetch.fetch_article.return_value = FetchedArticle(
            keyword="AI Agent",
            platform="wechat",
            title="Wechat Brief",
            source_url="https://mp.weixin.qq.com/s/mock-1",
            account_name="AI Insight",
            publish_time=datetime.now(UTC),
            read_count=100,
            comment_count=10,
            content_text="wechat body",
            source_id="wechat-1",
        )
        xhs_fetch = MagicMock()
        xhs_fetch.fetch_article.return_value = FetchedArticle(
            keyword="AI Agent",
            platform="xiaohongshu",
            title="XHS Brief",
            source_url="https://www.xiaohongshu.com/explore/mock-1",
            account_name="XHS Insight",
            publish_time=datetime.now(UTC),
            read_count=200,
            comment_count=20,
            content_text="xhs body",
            source_id="xhs-1",
        )

        with (
            patch("app.services.workflow.ensure_db_initialized"),
            patch("app.services.workflow.workflow_repository") as workflow_repository,
            patch("app.services.workflow.adapter_registry") as adapter_registry,
        ):
            workflow_repository.create_job.return_value = 100
            adapter_registry.get_discovery.side_effect = lambda name: {
                "wechat_exporter_search": wechat_discovery,
                "xiaohongshu_external_search": xhs_discovery,
            }[name]
            adapter_registry.get_fetch.side_effect = lambda name: {
                "wechat_exporter_fetch": wechat_fetch,
                "xiaohongshu_external_fetch": xhs_fetch,
            }[name]

            response = WorkflowService().run_preview(request_payload)

        self.assertEqual(response.platforms, ["wechat", "xiaohongshu"])
        self.assertEqual(response.discovered_count, 2)
        self.assertEqual(response.fetched_count, 2)
        self.assertEqual(response.ranked_count, 2)

    def test_live_adapter_failures_fall_back_to_mock_sources(self) -> None:
        request_payload = WorkflowPreviewRequest(
            keywords=["AI Agent"],
            platforms=["wechat"],
            discovery_source="web_search_wechat",
            fetch_source="web_fetch_wechat",
            limit=2,
            top_k=1,
            fallback_to_mock=True,
        )
        live_discovery = MagicMock()
        live_discovery.discover.side_effect = SearchRequestError("search failed")
        mock_discovery = MagicMock()
        mock_discovery.discover.return_value = [
            DiscoveryCandidate(
                keyword="AI Agent",
                source_engine="mock_wechat_search",
                title="AI Agent Industry Brief 1",
                snippet="summary",
                source_url="https://mp.weixin.qq.com/s/mock-1",
                account_name="AI Insight",
                discovered_at=datetime.now(UTC),
            )
        ]

        live_fetch = MagicMock()
        live_fetch.fetch_article.side_effect = FetchRequestError("fetch failed")
        mock_fetch = MagicMock()
        mock_fetch.fetch_article.return_value = FetchedArticle(
            keyword="AI Agent",
            platform="wechat",
            title="AI Agent Industry Brief 1",
            source_url="https://mp.weixin.qq.com/s/mock-1",
            account_name="AI Insight",
            publish_time=datetime.now(UTC),
            read_count=3200,
            comment_count=88,
            content_text="AI Agent article body",
            source_id="mock-1",
        )

        with (
            patch("app.services.workflow.ensure_db_initialized"),
            patch("app.services.workflow.workflow_repository") as workflow_repository,
            patch("app.services.workflow.adapter_registry") as adapter_registry,
        ):
            workflow_repository.create_job.return_value = 99
            adapter_registry.get_discovery.side_effect = lambda name: {
                "web_search_wechat": live_discovery,
                "mock_wechat_search": mock_discovery,
            }[name]
            adapter_registry.get_fetch.side_effect = lambda name: {
                "web_fetch_wechat": live_fetch,
                "mock_wechat_fetch": mock_fetch,
            }[name]

            response = WorkflowService().run_preview(request_payload)

        self.assertEqual(response.job_id, 99)
        self.assertEqual(response.platforms, ["wechat"])
        self.assertEqual(response.discovered_count, 1)
        self.assertEqual(response.fetched_count, 1)
        self.assertEqual(response.ranked_count, 1)
        mock_discovery.discover.assert_called_once_with(keyword="AI Agent", limit=2)
        mock_fetch.fetch_article.assert_called_once()
        workflow_repository.complete_job.assert_called_once()

    def test_xiaohongshu_failures_do_not_fall_back_to_wechat_mock(self) -> None:
        request_payload = WorkflowPreviewRequest(
            keywords=["AI Agent"],
            platforms=["xiaohongshu"],
            discovery_source="xiaohongshu_external_search",
            fetch_source="xiaohongshu_external_fetch",
            limit=2,
            top_k=1,
            fallback_to_mock=True,
        )
        live_discovery = MagicMock()
        live_discovery.discover.side_effect = SearchRequestError("search failed")

        with (
            patch("app.services.workflow.ensure_db_initialized"),
            patch("app.services.workflow.workflow_repository") as workflow_repository,
            patch("app.services.workflow.adapter_registry") as adapter_registry,
        ):
            workflow_repository.create_job.return_value = 101
            adapter_registry.get_discovery.side_effect = lambda name: {
                "xiaohongshu_external_search": live_discovery,
            }[name]
            adapter_registry.get_fetch.side_effect = lambda name: {}

            with self.assertRaises(SearchRequestError):
                WorkflowService().run_preview(request_payload)

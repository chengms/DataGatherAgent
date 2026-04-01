import unittest
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from app.adapters.web_fetch_live import FetchRequestError
from app.adapters.web_search_live import SearchRequestError
from app.schemas.workflow import WorkflowPreviewRequest
from app.services.workflow import WorkflowService


class WorkflowServiceTests(unittest.TestCase):
    def test_live_adapter_failures_fall_back_to_mock_sources(self) -> None:
        request_payload = WorkflowPreviewRequest(
            keywords=["AI Agent"],
            discovery_source="web_search_wechat",
            fetch_source="web_fetch_wechat",
            limit=2,
            top_k=1,
            fallback_to_mock=True,
        )
        live_discovery = MagicMock()
        live_discovery.search.side_effect = SearchRequestError("search failed")
        mock_discovery = MagicMock()
        mock_discovery.search.return_value = [
            {
                "keyword": "AI Agent",
                "source_engine": "mock_wechat_search",
                "title": "AI Agent Industry Brief 1",
                "snippet": "summary",
                "source_url": "https://mp.weixin.qq.com/s/mock-1",
                "account_name": "AI Insight",
                "discovered_at": datetime.now(UTC),
            }
        ]

        live_fetch = MagicMock()
        live_fetch.fetch.side_effect = FetchRequestError("fetch failed")
        mock_fetch = MagicMock()
        mock_fetch.fetch.return_value = {
            "keyword": "AI Agent",
            "platform": "wechat",
            "title": "AI Agent Industry Brief 1",
            "source_url": "https://mp.weixin.qq.com/s/mock-1",
            "account_name": "AI Insight",
            "publish_time": datetime.now(UTC),
            "read_count": 3200,
            "comment_count": 88,
            "content_text": "AI Agent article body",
            "source_id": "mock-1",
        }

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
        self.assertEqual(response.discovered_count, 1)
        self.assertEqual(response.fetched_count, 1)
        self.assertEqual(response.ranked_count, 1)
        mock_discovery.search.assert_called_once_with(keyword="AI Agent", limit=2)
        mock_fetch.fetch.assert_called_once()
        workflow_repository.complete_job.assert_called_once()

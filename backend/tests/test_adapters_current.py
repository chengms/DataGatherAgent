import unittest

from app.adapters.base import BaseDiscoveryAdapter, BaseFetchAdapter
from app.adapters.mock_wechat_clean import MockWechatFetchAdapter, MockWechatSearchAdapter
from app.core.exceptions import AdapterNotFoundError
from app.schemas.workflow import DiscoveryCandidate, FetchedArticle
from app.services.registry import adapter_registry


class AdapterTests(unittest.TestCase):
    def test_search_adapter_shape(self) -> None:
        adapter = MockWechatSearchAdapter()
        result = adapter.discover(keyword="AI", limit=2)
        self.assertEqual(len(result), 2)
        item = result[0]
        self.assertIsInstance(item, DiscoveryCandidate)
        self.assertEqual(item.keyword, "AI")
        self.assertEqual(item.source_engine, "mock_wechat_search")
        self.assertEqual(adapter.info.platform, "wechat")

    def test_fetch_adapter_shape(self) -> None:
        adapter = MockWechatFetchAdapter()
        article = adapter.fetch_article(
            DiscoveryCandidate(
                keyword="AI",
                source_engine="mock_wechat_search",
                title="AI Industry Brief 1",
                snippet="summary",
                source_url="https://example.com/article-1",
                account_name="AI Insight",
                discovered_at="2026-04-01T00:00:00Z",
            )
        )
        self.assertIsInstance(article, FetchedArticle)
        self.assertEqual(article.keyword, "AI")
        self.assertEqual(article.platform, "wechat")
        self.assertTrue(article.content_text)
        self.assertTrue(article.source_id)

    def test_registry_accessors(self) -> None:
        self.assertIsInstance(adapter_registry.get_discovery("mock_wechat_search"), BaseDiscoveryAdapter)
        self.assertIsInstance(adapter_registry.get_fetch("mock_wechat_fetch"), BaseFetchAdapter)
        self.assertGreater(len(adapter_registry.list_discovery_adapters()), 0)
        self.assertGreater(len(adapter_registry.list_fetch_adapters()), 0)

    def test_registry_missing_adapter_raises_domain_error(self) -> None:
        with self.assertRaises(AdapterNotFoundError):
            adapter_registry.get_discovery("missing")
        with self.assertRaises(AdapterNotFoundError):
            adapter_registry.get_fetch("missing")


if __name__ == "__main__":
    unittest.main()

import unittest

from app.adapters.base import BaseDiscoveryAdapter, BaseFetchAdapter
from app.adapters.mock_wechat_clean import MockWechatFetchAdapter, MockWechatSearchAdapter
from app.core.exceptions import AdapterNotFoundError
from app.services.registry import adapter_registry


class AdapterTests(unittest.TestCase):
    def test_search_adapter_shape(self) -> None:
        adapter = MockWechatSearchAdapter()
        result = adapter.search(keyword="AI", limit=2)
        self.assertEqual(len(result), 2)
        item = result[0]
        self.assertIn("keyword", item)
        self.assertIn("source_engine", item)
        self.assertIn("title", item)
        self.assertIn("snippet", item)
        self.assertIn("source_url", item)
        self.assertIn("account_name", item)
        self.assertIn("discovered_at", item)

    def test_fetch_adapter_shape(self) -> None:
        adapter = MockWechatFetchAdapter()
        article = adapter.fetch(
            {
                "keyword": "AI",
                "source_engine": "mock_wechat_search",
                "title": "AI Industry Brief 1",
                "snippet": "summary",
                "source_url": "https://example.com/article-1",
                "account_name": "AI Insight",
            }
        )
        self.assertEqual(article["keyword"], "AI")
        self.assertEqual(article["platform"], "wechat")
        self.assertIn("content_text", article)
        self.assertIn("source_id", article)

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

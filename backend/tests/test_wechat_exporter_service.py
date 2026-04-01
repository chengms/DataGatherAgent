import unittest
from datetime import UTC, datetime

from app.adapters.wechat_exporter_service import (
    WechatExporterFetchAdapter,
    WechatExporterSearchAdapter,
    WechatExporterServiceClient,
)
from app.schemas.workflow import DiscoveryCandidate


class FakeWechatExporterClient(WechatExporterServiceClient):
    def __init__(self) -> None:
        super().__init__(base_url="https://down.mptext.top", api_key="token")

    def search_accounts(self, keyword: str, size: int = 3) -> list[dict]:
        return [{"fakeid": "fake-1", "nickname": "AI Insight"}]

    def list_articles(self, fakeid: str, size: int = 10) -> list[dict]:
        return [
            {
                "title": "AI Weekly",
                "digest": "summary",
                "link": "https://mp.weixin.qq.com/s/demo-1",
                "nickname": "AI Insight",
            }
        ]

    def download_article(self, url: str, format_name: str = "html") -> str:
        return """
        <html>
          <body>
            <h1 id="activity-name">AI Weekly</h1>
            <span id="js_name">AI Insight</span>
            <span id="publish_time">2026-04-01</span>
            <div id="js_content">hello exporter</div>
          </body>
        </html>
        """


class WechatExporterServiceTests(unittest.TestCase):
    def test_search_adapter_builds_candidates_from_service(self) -> None:
        adapter = WechatExporterSearchAdapter(client=FakeWechatExporterClient())
        items = adapter.discover(keyword="AI", limit=1)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "AI Weekly")
        self.assertEqual(items[0].account_name, "AI Insight")

    def test_fetch_adapter_builds_article_from_downloaded_html(self) -> None:
        adapter = WechatExporterFetchAdapter(client=FakeWechatExporterClient())
        article = adapter.fetch_article(
            DiscoveryCandidate(
                keyword="AI",
                source_engine="wechat_exporter_search",
                title="AI Weekly",
                snippet="summary",
                source_url="https://mp.weixin.qq.com/s/demo-1",
                account_name="AI Insight",
                discovered_at=datetime.now(UTC),
            )
        )
        self.assertEqual(article.title, "AI Weekly")
        self.assertEqual(article.account_name, "AI Insight")
        self.assertIn("hello exporter", article.content_text)


if __name__ == "__main__":
    unittest.main()

import unittest
from datetime import UTC, datetime

from app.core.exceptions import SearchRequestError
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
        if format_name == "json":
            return """
            {
              "user_info": {
                "appmsg_bar_data": {
                  "read_num": 19450,
                  "comment_count": 782
                }
              }
            }
            """
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
    def test_service_client_extracts_articles_list_from_dict_payload(self) -> None:
        client = WechatExporterServiceClient(base_url="https://example.com", api_key="token")
        payload = {
            "base_resp": {"ret": 0, "err_msg": "ok"},
            "articles": [{"title": "AI Weekly", "link": "https://mp.weixin.qq.com/s/demo-1"}],
        }
        items = client._extract_items(payload)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "AI Weekly")

    def test_service_client_raises_clear_error_for_nonzero_base_resp(self) -> None:
        client = WechatExporterServiceClient(base_url="https://example.com", api_key="token")
        with self.assertRaises(SearchRequestError) as context:
            client._extract_items({"base_resp": {"ret": -1, "err_msg": "invalid token"}})
        self.assertEqual(context.exception.details["ret"], -1)
        self.assertEqual(context.exception.details["err_msg"], "invalid token")

    def test_service_client_marks_invalid_session_as_auth_invalid(self) -> None:
        client = WechatExporterServiceClient(base_url="https://example.com", api_key="token")
        with self.assertRaises(SearchRequestError) as context:
            client._extract_items({"base_resp": {"ret": 200003, "err_msg": "invalid session"}})
        self.assertEqual(context.exception.details["ret"], 200003)
        self.assertEqual(context.exception.details["reason"], "auth_invalid")

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
        self.assertEqual(article.read_count, 19450)
        self.assertEqual(article.comment_count, 782)
        self.assertIn("hello exporter", article.content_text)
        self.assertIn("js_content", article.content_html)

    def test_fetch_adapter_falls_back_to_html_metrics_when_json_is_unavailable(self) -> None:
        class HtmlOnlyWechatExporterClient(FakeWechatExporterClient):
            def download_article(self, url: str, format_name: str = "html") -> str:
                if format_name == "json":
                    raise SearchRequestError("metadata unavailable")
                return """
                <html>
                  <body>
                    <h1 id="activity-name">AI Weekly</h1>
                    <span id="js_name">AI Insight</span>
                    <span id="publish_time">2026-04-01</span>
                    <div id="js_content">hello exporter</div>
                    <script>
                      window.cgiData = {"read_num": 321, "comment_count": 17};
                    </script>
                  </body>
                </html>
                """

        adapter = WechatExporterFetchAdapter(client=HtmlOnlyWechatExporterClient())
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
        self.assertEqual(article.read_count, 321)
        self.assertEqual(article.comment_count, 17)


if __name__ == "__main__":
    unittest.main()

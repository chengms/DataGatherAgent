from datetime import UTC, datetime, timedelta
from hashlib import md5

from app.adapters.base import BaseDiscoveryAdapter, BaseFetchAdapter, DiscoverySourceInfo


class MockWechatSearchAdapter(BaseDiscoveryAdapter):
    info = DiscoverySourceInfo(
        name="mock_wechat_search",
        kind="search",
        description="Mock WeChat article discovery source used to validate the workflow before integrating real search adapters.",
    )

    def search(self, keyword: str, limit: int) -> list[dict]:
        now = datetime.now(UTC)
        results: list[dict] = []
        for index in range(limit):
            article_id = md5(f"{keyword}-{index}".encode("utf-8")).hexdigest()[:12]
            results.append(
                {
                    "keyword": keyword,
                    "source_engine": self.info.name,
                    "title": f"{keyword} 行业观察 {index + 1}",
                    "snippet": f"围绕 {keyword} 的公众号候选文章摘要 {index + 1}",
                    "source_url": f"https://mp.weixin.qq.com/s/{article_id}",
                    "account_name": f"{keyword}观察局",
                    "discovered_at": now - timedelta(minutes=index * 3),
                }
            )
        return results


class MockWechatFetchAdapter(BaseFetchAdapter):
    def fetch(self, candidate: dict) -> dict:
        keyword = candidate["keyword"]
        sequence = int(candidate["title"].rsplit(" ", maxsplit=1)[-1])
        publish_time = datetime.now(UTC) - timedelta(hours=sequence * 4)
        read_count = max(2000, 20000 - sequence * 550)
        comment_count = max(20, 800 - sequence * 18)
        source_id = candidate["source_url"].rstrip("/").split("/")[-1]
        return {
            "keyword": keyword,
            "platform": "wechat",
            "title": candidate["title"],
            "source_url": candidate["source_url"],
            "account_name": candidate["account_name"],
            "publish_time": publish_time,
            "read_count": read_count,
            "comment_count": comment_count,
            "content_text": (
                f"这是一篇关于 {keyword} 的示例文章，覆盖趋势、案例、行业观点和热点分析。"
                f"文章编号 {sequence}。"
            ),
            "source_id": source_id,
        }


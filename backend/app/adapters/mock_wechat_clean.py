from datetime import UTC, datetime, timedelta
from hashlib import md5

from app.adapters.base import AdapterInfo, BaseDiscoveryAdapter, BaseFetchAdapter
from app.schemas.workflow import DiscoveryCandidate, FetchedArticle


class MockWechatSearchAdapter(BaseDiscoveryAdapter):
    info = AdapterInfo(
        name="mock_wechat_search",
        kind="search",
        platform="wechat",
        description="Mock WeChat article discovery source used to validate the workflow before integrating real search adapters.",
    )

    def _discover(self, keyword: str, limit: int) -> list[DiscoveryCandidate]:
        now = datetime.now(UTC)
        results: list[DiscoveryCandidate] = []
        for index in range(limit):
            article_id = md5(f"{keyword}-{index}".encode("utf-8")).hexdigest()[:12]
            results.append(
                DiscoveryCandidate(
                    keyword=keyword,
                    source_engine=self.info.name,
                    title=f"{keyword} Industry Brief {index + 1}",
                    snippet=f"Candidate WeChat article summary for {keyword} #{index + 1}",
                    source_url=f"https://mp.weixin.qq.com/s/{article_id}",
                    account_name=f"{keyword} Insight",
                    discovered_at=now - timedelta(minutes=index * 3),
                )
            )
        return results


class MockWechatFetchAdapter(BaseFetchAdapter):
    info = AdapterInfo(
        name="mock_wechat_fetch",
        kind="fetch",
        platform="wechat",
        description="Mock WeChat article fetch used as a safe fallback when live article retrieval is unavailable.",
    )

    def _fetch_article(self, candidate: DiscoveryCandidate) -> FetchedArticle:
        keyword = candidate.keyword
        sequence = int(candidate.title.rsplit(" ", maxsplit=1)[-1])
        publish_time = datetime.now(UTC) - timedelta(hours=sequence * 4)
        read_count = max(2000, 20000 - sequence * 550)
        comment_count = max(20, 800 - sequence * 18)
        source_id = candidate.source_url.rstrip("/").split("/")[-1]
        return FetchedArticle(
            keyword=keyword,
            platform="wechat",
            title=candidate.title,
            source_url=candidate.source_url,
            account_name=candidate.account_name,
            publish_time=publish_time,
            read_count=read_count,
            comment_count=comment_count,
            content_text=(
                f"This is a mock article about {keyword}. "
                f"It contains trends, cases, viewpoints, and a short hot-topic summary. "
                f"Sequence {sequence}."
            ),
            source_id=source_id,
        )

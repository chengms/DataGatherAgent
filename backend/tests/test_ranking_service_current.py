import unittest
from datetime import UTC, datetime, timedelta

from app.schemas.workflow import FetchedArticle, RankingWeights
from app.services.ranking import ranking_service


class RankingServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.weights = RankingWeights(relevance=0.5, popularity=0.3, freshness=0.2)

    def article(
        self,
        *,
        keyword: str = "AI",
        content_text: str = "AI content",
        read_count: int = 100,
        comment_count: int = 10,
        publish_time: datetime | None = None,
    ) -> FetchedArticle:
        return FetchedArticle(
            keyword=keyword,
            platform="wechat",
            title="Test Article",
            source_url="https://example.com/article",
            account_name="AI Insight",
            publish_time=publish_time or datetime.now(UTC),
            read_count=read_count,
            comment_count=comment_count,
            content_text=content_text,
            source_id="article-1",
        )

    def test_score_basic(self) -> None:
        scored = ranking_service.score(self.article(), self.weights)
        self.assertGreater(scored.total_score, 0)

    def test_popularity_changes_score(self) -> None:
        high = ranking_service.score(self.article(read_count=10000, comment_count=500), self.weights)
        low = ranking_service.score(self.article(read_count=100, comment_count=5), self.weights)
        self.assertGreater(high.popularity_score, low.popularity_score)
        self.assertGreater(high.total_score, low.total_score)

    def test_freshness_changes_score(self) -> None:
        now = datetime.now(UTC)
        fresh = ranking_service.score(self.article(publish_time=now), self.weights)
        old = ranking_service.score(self.article(publish_time=now - timedelta(days=7)), self.weights)
        self.assertGreater(fresh.freshness_score, old.freshness_score)

    def test_weights_affect_total(self) -> None:
        article = self.article(read_count=8000, comment_count=400, content_text="generic content")
        relevance_heavy = RankingWeights(relevance=0.8, popularity=0.1, freshness=0.1)
        popularity_heavy = RankingWeights(relevance=0.1, popularity=0.8, freshness=0.1)
        self.assertNotEqual(
            ranking_service.score(article, relevance_heavy).total_score,
            ranking_service.score(article, popularity_heavy).total_score,
        )

    def test_component_sum_matches_total(self) -> None:
        scored = ranking_service.score(self.article(), self.weights)
        expected_total = round(
            scored.relevance_score * self.weights.relevance
            + scored.popularity_score * self.weights.popularity
            + scored.freshness_score * self.weights.freshness,
            4,
        )
        self.assertAlmostEqual(scored.total_score, expected_total, places=4)


if __name__ == "__main__":
    unittest.main()

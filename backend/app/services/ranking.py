from datetime import UTC, datetime

from app.schemas.workflow import FetchedArticle, RankedArticle, RankingWeights


class RankingService:
    def score(self, article: FetchedArticle, weights: RankingWeights) -> RankedArticle:
        relevance_score = self._score_relevance(article)
        popularity_score = self._score_popularity(article)
        freshness_score = self._score_freshness(article)
        total_score = (
            relevance_score * weights.relevance
            + popularity_score * weights.popularity
            + freshness_score * weights.freshness
        )
        score_reason = (
            f"相关度 {relevance_score:.2f}，热度 {popularity_score:.2f}，时效 {freshness_score:.2f}"
        )
        return RankedArticle(
            keyword=article.keyword,
            title=article.title,
            source_url=article.source_url,
            account_name=article.account_name,
            publish_time=article.publish_time,
            read_count=article.read_count,
            comment_count=article.comment_count,
            relevance_score=relevance_score,
            popularity_score=popularity_score,
            freshness_score=freshness_score,
            total_score=round(total_score, 4),
            score_reason=score_reason,
        )

    def _score_relevance(self, article: FetchedArticle) -> float:
        haystack = f"{article.title} {article.content_text}".lower()
        needle = article.keyword.lower()
        if needle in haystack:
            return 0.95
        shared_chars = len(set(needle) & set(haystack))
        return min(0.9, 0.35 + shared_chars * 0.04)

    def _score_popularity(self, article: FetchedArticle) -> float:
        read_component = min(1.0, article.read_count / 20000)
        comment_component = min(1.0, article.comment_count / 1000)
        return round(read_component * 0.8 + comment_component * 0.2, 4)

    def _score_freshness(self, article: FetchedArticle) -> float:
        now = datetime.now(UTC)
        age_hours = max(0.0, (now - article.publish_time).total_seconds() / 3600)
        return round(max(0.0, 1.0 - age_hours / 168), 4)


ranking_service = RankingService()


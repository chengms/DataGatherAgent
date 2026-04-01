from datetime import datetime
from pydantic import BaseModel, Field


class RankingWeights(BaseModel):
    relevance: float = Field(default=0.5, ge=0.0, le=1.0)
    popularity: float = Field(default=0.3, ge=0.0, le=1.0)
    freshness: float = Field(default=0.2, ge=0.0, le=1.0)


class WorkflowPreviewRequest(BaseModel):
    keywords: list[str] = Field(min_length=1)
    platform: str = "wechat"
    discovery_source: str = "mock_wechat_search"
    fetch_source: str = "mock_wechat_fetch"
    limit: int = Field(default=10, ge=1, le=100)
    top_k: int = Field(default=10, ge=1, le=50)
    time_window_days: int = Field(default=7, ge=1, le=30)
    fallback_to_mock: bool = True
    ranking: RankingWeights = Field(default_factory=RankingWeights)


class DiscoveryCandidate(BaseModel):
    keyword: str
    source_engine: str
    title: str
    snippet: str
    source_url: str
    account_name: str
    discovered_at: datetime


class FetchedArticle(BaseModel):
    keyword: str
    platform: str
    title: str
    source_url: str
    account_name: str
    publish_time: datetime
    read_count: int = 0
    comment_count: int = 0
    content_text: str
    source_id: str


class RankedArticle(BaseModel):
    keyword: str
    title: str
    source_url: str
    account_name: str
    publish_time: datetime
    read_count: int
    comment_count: int
    relevance_score: float
    popularity_score: float
    freshness_score: float
    total_score: float
    score_reason: str


class WorkflowPreviewResponse(BaseModel):
    job_id: int | None = None
    keywords: list[str]
    discovered_count: int
    fetched_count: int
    ranked_count: int
    discovery_candidates: list[DiscoveryCandidate]
    fetched_articles: list[FetchedArticle]
    hot_articles: list[RankedArticle]


class WorkflowJobSummary(BaseModel):
    id: int
    platform: str
    discovery_source: str
    fetch_source: str
    keywords_json: str
    status: str
    created_at: str
    finished_at: str | None = None
    discovered_count: int
    fetched_count: int
    ranked_count: int


class RankedArticleRecord(BaseModel):
    keyword: str
    title: str
    source_url: str
    account_name: str
    publish_time: str
    read_count: int
    comment_count: int
    relevance_score: float
    popularity_score: float
    freshness_score: float
    total_score: float
    score_reason: str
    rank_position: int


class WorkflowJobDetail(BaseModel):
    job: WorkflowJobSummary
    hot_articles: list[RankedArticleRecord]


class SourceInfoResponse(BaseModel):
    name: str
    kind: str
    platform: str
    description: str
    live: bool

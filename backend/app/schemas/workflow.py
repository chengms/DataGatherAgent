from datetime import datetime
from pydantic import BaseModel, Field


class RankingWeights(BaseModel):
    relevance: float = Field(default=0.5, ge=0.0, le=1.0)
    popularity: float = Field(default=0.3, ge=0.0, le=1.0)
    freshness: float = Field(default=0.2, ge=0.0, le=1.0)


class WorkflowPreviewRequest(BaseModel):
    keywords: list[str] = Field(min_length=1)
    platform: str = "wechat"
    platforms: list[str] = Field(default_factory=lambda: ["wechat"], min_length=1)
    discovery_source: str | None = None
    fetch_source: str | None = None
    limit: int = Field(default=10, ge=1, le=100)
    top_k: int = Field(default=10, ge=1, le=50)
    time_window_days: int = Field(default=7, ge=1, le=30)
    fallback_to_mock: bool = False
    ranking: RankingWeights = Field(default_factory=RankingWeights)

    def selected_platforms(self) -> list[str]:
        if self.platforms:
            return self.platforms
        return [self.platform]


class DiscoveryCandidate(BaseModel):
    keyword: str
    source_engine: str
    title: str
    snippet: str
    source_url: str
    account_name: str
    discovered_at: datetime


class ArticleComment(BaseModel):
    nickname: str = ""
    content: str
    publish_time: str | None = None
    like_count: int = 0
    sub_comment_count: int = 0


class FetchedArticle(BaseModel):
    keyword: str
    platform: str
    source_engine: str = ""
    content_kind: str = "article"
    title: str
    source_url: str
    account_name: str
    publish_time: datetime
    read_count: int = 0
    comment_count: int = 0
    content_text: str
    content_html: str = ""
    source_id: str
    comments: list[ArticleComment] = Field(default_factory=list)


class RankedArticle(BaseModel):
    keyword: str
    platform: str
    source_engine: str = ""
    content_kind: str = "article"
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
    platforms: list[str] = Field(default_factory=list)
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
    platform: str
    source_engine: str = ""
    content_kind: str = "article"
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


class FetchedArticleRecord(BaseModel):
    id: int
    job_id: int
    keyword: str
    platform: str
    source_engine: str
    content_kind: str
    title: str
    source_url: str
    account_name: str
    publish_time: str
    read_count: int
    comment_count: int
    content_text: str
    content_html: str = ""
    source_id: str
    comments: list[ArticleComment] = Field(default_factory=list)


class DeleteArticleResponse(BaseModel):
    id: int
    job_id: int
    title: str
    deleted: bool = True


class FetchedArticleSearchResponse(BaseModel):
    total: int
    items: list[FetchedArticleRecord]


class ExternalArticleQueryEcho(BaseModel):
    keyword: str | None = None
    platforms: list[str] = Field(default_factory=list)
    content_kind: str | None = None
    published_from: str | None = None
    published_to: str | None = None
    page: int
    page_size: int


class ExternalArticleSummary(BaseModel):
    article_id: int
    job_id: int
    keyword: str
    platform: str
    content_kind: str
    source_engine: str
    title: str
    source_url: str
    account_name: str
    publish_time: str
    read_count: int
    comment_count: int
    excerpt: str = ""
    has_html: bool = False
    data_url: str
    preview_url: str


class ExternalArticleDetailResponse(ExternalArticleSummary):
    content_text: str
    content_html: str = ""
    source_id: str
    comments: list[ArticleComment] = Field(default_factory=list)


class ExternalArticleListResponse(BaseModel):
    query: ExternalArticleQueryEcho
    total: int
    items: list[ExternalArticleSummary]


class SourceInfoResponse(BaseModel):
    name: str
    kind: str
    platform: str
    description: str
    live: bool
    service_name: str | None = None
    service_label: str | None = None
    service_online: bool = False
    service_status: str = "unknown"
    login_required: bool = False
    login_status: str = "not_required"
    login_reason: str | None = None
    runtime_state: str = "unknown"
    runtime_ready: bool = False
    status_summary: str = ""
    last_checked_at: str | None = None


class ServiceUpdateNotice(BaseModel):
    service_name: str
    status: str
    branch: str | None = None
    ahead_by: int = 0
    local_sha: str | None = None
    remote_sha: str | None = None
    summary: str = ""


class UpdateNoticeResponse(BaseModel):
    checked_at: str | None = None
    items: list[ServiceUpdateNotice] = Field(default_factory=list)


class WechatLoginSessionResponse(BaseModel):
    session_id: str | None = None
    status: str
    message: str
    qrcode_url: str | None = None
    qrcode_revision: int = 0
    auth_key_prefix: str | None = None


class PlatformLoginSessionResponse(BaseModel):
    session_id: str | None = None
    platform: str
    status: str
    message: str
    qrcode_data_url: str | None = None
    auth_key_prefix: str | None = None


class ServiceActionRequest(BaseModel):
    action: str


class ServiceActionResponse(BaseModel):
    task_id: str
    service_name: str
    action: str
    status: str
    progress: int = 0
    message: str
    service_online: bool = False
    service_status: str = "unknown"
    error: str | None = None

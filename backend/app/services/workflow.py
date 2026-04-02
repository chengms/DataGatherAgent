from app.db.init_db import ensure_db_initialized
from app.core.exceptions import FetchRequestError, JobNotFoundError, SearchRequestError
from app.schemas.workflow import (
    WorkflowJobDetail,
    WorkflowJobSummary,
    WorkflowPreviewRequest,
    WorkflowPreviewResponse,
)
from app.repositories.workflow_repository import workflow_repository
from app.services.ranking import ranking_service
from app.services.registry import adapter_registry


class WorkflowService:
    PLATFORM_STRATEGIES: dict[str, tuple[str, str]] = {
        "wechat": ("wechat_exporter_search", "wechat_exporter_fetch"),
        "xiaohongshu": ("xiaohongshu_external_search", "xiaohongshu_external_fetch"),
        "weibo": ("weibo_external_search", "weibo_external_fetch"),
        "bilibili": ("bilibili_external_search", "bilibili_external_fetch"),
        "douyin": ("douyin_external_search", "douyin_external_fetch"),
    }

    def _fallback_discovery_source(self, platform: str) -> str | None:
        if platform == "wechat":
            return "mock_wechat_search"
        return None

    def _fallback_fetch_source(self, platform: str) -> str | None:
        if platform == "wechat":
            return "mock_wechat_fetch"
        return None

    def _resolve_platforms(self, payload: WorkflowPreviewRequest) -> list[str]:
        platforms: list[str] = []
        for platform in payload.selected_platforms():
            normalized = platform.strip()
            if normalized and normalized not in platforms:
                platforms.append(normalized)
        return platforms or ["wechat"]

    def _resolve_sources_for_platform(self, payload: WorkflowPreviewRequest, platform: str) -> tuple[str, str]:
        if payload.discovery_source and payload.fetch_source and len(self._resolve_platforms(payload)) == 1:
            return payload.discovery_source, payload.fetch_source
        try:
            return self.PLATFORM_STRATEGIES[platform]
        except KeyError as exc:
            raise SearchRequestError(f"platform is not supported yet: {platform}") from exc

    def _job_platform_label(self, payload: WorkflowPreviewRequest) -> str:
        platforms = self._resolve_platforms(payload)
        return ",".join(platforms)

    def _job_source_label(self, payload: WorkflowPreviewRequest, index: int) -> str:
        if index == 0 and payload.discovery_source and payload.fetch_source and len(self._resolve_platforms(payload)) == 1:
            return payload.discovery_source if index == 0 else payload.fetch_source
        labels: list[str] = []
        for platform in self._resolve_platforms(payload):
            discovery_source, fetch_source = self._resolve_sources_for_platform(payload, platform)
            labels.append(discovery_source if index == 0 else fetch_source)
        return ",".join(labels)

    def run_preview(self, payload: WorkflowPreviewRequest) -> WorkflowPreviewResponse:
        ensure_db_initialized()
        payload.platform = self._job_platform_label(payload)
        payload.discovery_source = self._job_source_label(payload, 0)
        payload.fetch_source = self._job_source_label(payload, 1)
        job_id = workflow_repository.create_job(payload)

        discovery_candidates = []
        fetch_plan: list[tuple[str, object]] = []
        for platform in self._resolve_platforms(payload):
            discovery_source, fetch_source = self._resolve_sources_for_platform(payload, platform)
            discovery_adapter = adapter_registry.get_discovery(discovery_source)
            fetch_adapter = adapter_registry.get_fetch(fetch_source)
            for keyword in payload.keywords:
                try:
                    candidates = discovery_adapter.discover(keyword=keyword, limit=payload.limit)
                except SearchRequestError:
                    fallback_source = self._fallback_discovery_source(platform)
                    if not payload.fallback_to_mock or fallback_source is None:
                        raise
                    discovery_adapter = adapter_registry.get_discovery(fallback_source)
                    candidates = discovery_adapter.discover(
                        keyword=keyword,
                        limit=payload.limit,
                    )
                    fetch_adapter = adapter_registry.get_fetch(self._fallback_fetch_source(platform) or fetch_source)
                discovery_candidates.extend(candidates)
                fetch_plan.extend((platform, fetch_adapter, candidate) for candidate in candidates)
        workflow_repository.save_discovery_candidates(job_id, discovery_candidates)

        fetched_articles = []
        for platform, fetch_adapter, candidate in fetch_plan:
            try:
                article = fetch_adapter.fetch_article(candidate)
            except FetchRequestError:
                fallback_source = self._fallback_fetch_source(platform)
                if not payload.fallback_to_mock or fallback_source is None:
                    raise
                article = adapter_registry.get_fetch(fallback_source).fetch_article(candidate)
            fetched_articles.append(article)
        workflow_repository.save_fetched_articles(job_id, fetched_articles)

        ranked_articles = [
            ranking_service.score(article=article, weights=payload.ranking)
            for article in fetched_articles
        ]
        ranked_articles.sort(key=lambda item: item.total_score, reverse=True)
        hot_articles = ranked_articles[: payload.top_k]
        workflow_repository.save_ranked_articles(job_id, hot_articles)
        workflow_repository.complete_job(
            job_id=job_id,
            discovered_count=len(discovery_candidates),
            fetched_count=len(fetched_articles),
            ranked_count=len(hot_articles),
        )

        return WorkflowPreviewResponse(
            job_id=job_id,
            keywords=payload.keywords,
            platforms=self._resolve_platforms(payload),
            discovered_count=len(discovery_candidates),
            fetched_count=len(fetched_articles),
            ranked_count=len(hot_articles),
            discovery_candidates=discovery_candidates,
            fetched_articles=fetched_articles,
            hot_articles=hot_articles,
        )

    def list_jobs(self) -> list[WorkflowJobSummary]:
        ensure_db_initialized()
        rows = workflow_repository.list_jobs()
        return [WorkflowJobSummary.model_validate(row) for row in rows]

    def get_job_detail(self, job_id: int) -> WorkflowJobDetail:
        ensure_db_initialized()
        jobs = workflow_repository.list_jobs()
        job_row = next((item for item in jobs if item["id"] == job_id), None)
        if job_row is None:
            raise JobNotFoundError(job_id)
        ranked_rows = workflow_repository.get_job_ranked_articles(job_id)
        return WorkflowJobDetail.model_validate(
            {
                "job": job_row,
                "hot_articles": ranked_rows,
            }
        )


workflow_service = WorkflowService()

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
    def _fallback_discovery_source(self, platform: str) -> str | None:
        if platform == "wechat":
            return "mock_wechat_search"
        return None

    def _fallback_fetch_source(self, platform: str) -> str | None:
        if platform == "wechat":
            return "mock_wechat_fetch"
        return None

    def run_preview(self, payload: WorkflowPreviewRequest) -> WorkflowPreviewResponse:
        ensure_db_initialized()
        job_id = workflow_repository.create_job(payload)
        discovery_adapter = adapter_registry.get_discovery(payload.discovery_source)
        fetch_adapter = adapter_registry.get_fetch(payload.fetch_source)

        discovery_candidates = []
        for keyword in payload.keywords:
            try:
                candidates = discovery_adapter.discover(keyword=keyword, limit=payload.limit)
            except SearchRequestError:
                fallback_source = self._fallback_discovery_source(payload.platform)
                if not payload.fallback_to_mock or fallback_source is None:
                    raise
                candidates = adapter_registry.get_discovery(fallback_source).discover(
                    keyword=keyword,
                    limit=payload.limit,
                )
            discovery_candidates.extend(candidates)
        workflow_repository.save_discovery_candidates(job_id, discovery_candidates)

        fetched_articles = []
        for candidate in discovery_candidates:
            try:
                article = fetch_adapter.fetch_article(candidate)
            except FetchRequestError:
                fallback_source = self._fallback_fetch_source(payload.platform)
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

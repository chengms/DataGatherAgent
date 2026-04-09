from fastapi import APIRouter, Query

from app.schemas.workflow import (
    DeleteArticleResponse,
    FetchedArticleRecord,
    FetchedArticleSearchResponse,
    WorkflowJobDetail,
    WorkflowJobSummary,
    WorkflowPreviewRequest,
    WorkflowPreviewResponse,
)
from app.services.workflow import workflow_service


router = APIRouter()


@router.post("/preview", response_model=WorkflowPreviewResponse)
def preview_workflow(payload: WorkflowPreviewRequest) -> WorkflowPreviewResponse:
    return workflow_service.run_preview(payload)


@router.get("/jobs", response_model=list[WorkflowJobSummary])
def list_workflow_jobs() -> list[WorkflowJobSummary]:
    return workflow_service.list_jobs()


@router.get("/jobs/{job_id}", response_model=WorkflowJobDetail)
def get_workflow_job(job_id: int) -> WorkflowJobDetail:
    return workflow_service.get_job_detail(job_id)


@router.get("/articles", response_model=FetchedArticleSearchResponse)
def search_fetched_articles(
    q: str | None = Query(default=None),
    platform: str | None = Query(default=None),
    content_kind: str | None = Query(default=None),
    job_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> FetchedArticleSearchResponse:
    return workflow_service.search_fetched_articles(
        keyword=q,
        platform=platform,
        content_kind=content_kind,
        job_id=job_id,
        page=page,
        page_size=page_size,
    )


@router.get("/articles/{article_id}", response_model=FetchedArticleRecord)
def get_fetched_article(article_id: int) -> FetchedArticleRecord:
    return workflow_service.get_fetched_article(article_id)


@router.delete("/articles/{article_id}", response_model=DeleteArticleResponse)
def delete_fetched_article(article_id: int) -> DeleteArticleResponse:
    return workflow_service.delete_fetched_article(article_id)

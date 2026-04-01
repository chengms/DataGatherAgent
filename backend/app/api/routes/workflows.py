from fastapi import APIRouter

from app.schemas.workflow import (
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

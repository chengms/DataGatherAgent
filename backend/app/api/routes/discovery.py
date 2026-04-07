from fastapi import APIRouter, Query

from app.schemas.workflow import SourceInfoResponse, UpdateNoticeResponse
from app.services.platform_status import list_platform_status
from app.services.registry import adapter_registry
from app.services.update_notices import list_update_notices


router = APIRouter()


@router.get("/sources", response_model=list[SourceInfoResponse])
def list_sources(refresh: bool = Query(default=False)) -> list[SourceInfoResponse]:
    platform_status = list_platform_status(force_refresh=refresh)
    return [
        SourceInfoResponse.model_validate(
            {
                **source.info.__dict__,
                **platform_status.get(source.info.platform, {}),
            }
        )
        for source in adapter_registry.list_sources()
    ]


@router.get("/notices", response_model=UpdateNoticeResponse)
def get_update_notices() -> UpdateNoticeResponse:
    payload = list_update_notices()
    return UpdateNoticeResponse.model_validate(payload)

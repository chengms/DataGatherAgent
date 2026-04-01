from fastapi import APIRouter

from app.schemas.workflow import SourceInfoResponse
from app.services.registry import adapter_registry


router = APIRouter()


@router.get("/sources", response_model=list[SourceInfoResponse])
def list_sources() -> list[SourceInfoResponse]:
    return [
        SourceInfoResponse.model_validate(source.info.__dict__)
        for source in adapter_registry.list_sources()
    ]

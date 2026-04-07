from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.core.exceptions import NotFoundError
from app.schemas.workflow import (
    PlatformLoginSessionResponse,
    SourceInfoResponse,
    UpdateNoticeResponse,
    WechatLoginSessionResponse,
)
from app.services.platform_login import platform_login_service
from app.services.platform_status import list_platform_status
from app.services.registry import adapter_registry
from app.services.update_notices import list_update_notices
from app.services.wechat_login import wechat_login_service


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


@router.post("/wechat-login/sessions", response_model=WechatLoginSessionResponse)
def create_wechat_login_session() -> WechatLoginSessionResponse:
    payload = wechat_login_service.start_session()
    return WechatLoginSessionResponse.model_validate(payload)


@router.get("/wechat-login/sessions/{session_id}", response_model=WechatLoginSessionResponse)
def poll_wechat_login_session(session_id: str) -> WechatLoginSessionResponse:
    payload = wechat_login_service.poll_session(session_id)
    return WechatLoginSessionResponse.model_validate(payload)


@router.get("/wechat-login/sessions/{session_id}/qrcode")
def get_wechat_login_qrcode(session_id: str) -> Response:
    content, media_type = wechat_login_service.get_qrcode(session_id)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@router.delete("/wechat-login/sessions/{session_id}")
def delete_wechat_login_session(session_id: str) -> dict[str, bool]:
    wechat_login_service.discard_session(session_id)
    return {"ok": True}


@router.post("/platform-login/{platform}/sessions", response_model=PlatformLoginSessionResponse)
def create_platform_login_session(platform: str) -> PlatformLoginSessionResponse:
    payload = platform_login_service.start_session(platform)
    return PlatformLoginSessionResponse.model_validate(payload)


@router.get("/platform-login/{platform}/sessions/{session_id}", response_model=PlatformLoginSessionResponse)
def poll_platform_login_session(platform: str, session_id: str) -> PlatformLoginSessionResponse:
    payload = platform_login_service.poll_session(session_id)
    if payload.get("platform") != platform:
        raise NotFoundError("Platform login session not found", "PlatformLoginSession")
    return PlatformLoginSessionResponse.model_validate(payload)


@router.delete("/platform-login/{platform}/sessions/{session_id}")
def delete_platform_login_session(platform: str, session_id: str) -> dict[str, bool]:
    payload = platform_login_service.poll_session(session_id)
    if payload.get("platform") != platform:
        raise NotFoundError("Platform login session not found", "PlatformLoginSession")
    platform_login_service.discard_session(session_id)
    return {"ok": True}

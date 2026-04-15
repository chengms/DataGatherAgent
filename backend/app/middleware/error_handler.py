"""FastAPI exception handlers with a consistent JSON payload."""

from __future__ import annotations

from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.core.exceptions import AppException
from app.core.logging import get_logger


logger = get_logger(__name__)


class ErrorResponse:
    def __init__(
        self,
        error_code: str,
        message: str,
        status_code: int = 500,
        details: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> None:
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        self.request_id = request_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.error_code,
                "message": self.message,
                "details": self.details,
            },
            "request_id": self.request_id,
        }


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    request_id = request.headers.get("X-Request-ID", "unknown")
    logger.warning(
        "app_exception code=%s status=%s request_id=%s path=%s message=%s",
        exc.error_code,
        exc.status_code,
        request_id,
        request.url.path,
        exc.message,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error_code=exc.error_code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
            request_id=request_id,
        ).to_dict(),
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = request.headers.get("X-Request-ID", "unknown")
    logger.exception(
        "unhandled_exception type=%s request_id=%s path=%s message=%s",
        type(exc).__name__,
        request_id,
        request.url.path,
        str(exc),
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error_code="INTERNAL_ERROR",
            message="An unexpected error occurred",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details={"error_type": type(exc).__name__},
            request_id=request_id,
        ).to_dict(),
    )


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = request.headers.get("X-Request-ID", "unknown")
    logger.warning(
        "validation_error request_id=%s path=%s error=%s",
        request_id,
        request.url.path,
        str(exc),
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            error_code="INVALID_REQUEST",
            message="Request validation failed",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"validation_error": str(exc)},
            request_id=request_id,
        ).to_dict(),
    )

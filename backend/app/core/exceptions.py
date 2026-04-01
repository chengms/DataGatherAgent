"""Application exception types used by the API layer."""

from __future__ import annotations

from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    INTERNAL_ERROR = "INTERNAL_ERROR"
    INVALID_REQUEST = "INVALID_REQUEST"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    DISCOVERY_ERROR = "DISCOVERY_ERROR"
    FETCH_ERROR = "FETCH_ERROR"
    RANKING_ERROR = "RANKING_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    ADAPTER_NOT_FOUND = "ADAPTER_NOT_FOUND"
    JOB_NOT_FOUND = "JOB_NOT_FOUND"
    SEARCH_REQUEST_ERROR = "SEARCH_REQUEST_ERROR"
    FETCH_REQUEST_ERROR = "FETCH_REQUEST_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"


class AppException(Exception):
    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class ValidationError(AppException):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, ErrorCode.INVALID_REQUEST, 400, details)


class NotFoundError(AppException):
    def __init__(self, message: str, resource_type: str = "Resource") -> None:
        super().__init__(
            message,
            ErrorCode.NOT_FOUND,
            404,
            {"resource_type": resource_type},
        )


class DiscoveryError(AppException):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, ErrorCode.DISCOVERY_ERROR, 500, details)


class FetchError(AppException):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, ErrorCode.FETCH_ERROR, 500, details)


class RankingError(AppException):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, ErrorCode.RANKING_ERROR, 500, details)


class DatabaseError(AppException):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, ErrorCode.DATABASE_ERROR, 500, details)


class AdapterNotFoundError(AppException):
    def __init__(self, adapter_name: str, adapter_type: str) -> None:
        super().__init__(
            f"Adapter '{adapter_name}' of type '{adapter_type}' not found",
            ErrorCode.ADAPTER_NOT_FOUND,
            404,
            {"adapter_name": adapter_name, "adapter_type": adapter_type},
        )


class JobNotFoundError(NotFoundError):
    def __init__(self, job_id: int) -> None:
        super().__init__(f"Job with id {job_id} not found", "Job")
        self.details["job_id"] = job_id


class SearchRequestError(AppException):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, ErrorCode.SEARCH_REQUEST_ERROR, 502, details)


class FetchRequestError(AppException):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, ErrorCode.FETCH_REQUEST_ERROR, 502, details)


class NetworkError(AppException):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, ErrorCode.NETWORK_ERROR, 503, details)


class TimeoutError(AppException):
    def __init__(self, message: str, timeout_seconds: float) -> None:
        super().__init__(
            message,
            ErrorCode.TIMEOUT_ERROR,
            504,
            {"timeout_seconds": timeout_seconds},
        )

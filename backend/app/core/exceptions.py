"""Standardized Error Handling and Application Exceptions."""

from typing import Any, Optional

from fastapi import Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.app.core.logging import correlation_id_ctx, logger


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str
    details: Optional[Any] = None


class AppException(Exception):
    """Base application exception."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_SERVER_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Any] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details


class AuthenticationError(AppException):
    def __init__(self, message: str = "Authentication failed", details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="AUTHENTICATION_FAILED",
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details,
        )


class PermissionDeniedError(AppException):
    def __init__(self, message: str = "Permission denied", details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="PERMISSION_DENIED",
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class NotFoundError(AppException):
    def __init__(self, message: str = "Resource not found", details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class ValidationError(AppException):
    def __init__(self, message: str = "Validation failed", details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


class ConflictError(AppException):
    def __init__(
        self, message: str = "Conflict with existing state", details: Optional[Any] = None
    ):
        super().__init__(
            message=message,
            code="CONFLICT",
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class RateLimitExceededError(AppException):
    def __init__(self, message: str = "Rate limit exceeded", details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details=details,
        )


class BusinessRuleViolationError(AppException):
    """Raised when an action violates business governance rules (e.g. 4th attempt, unapproved send)."""

    def __init__(
        self, message: str, code: str = "BUSINESS_RULE_VIOLATION", details: Optional[Any] = None
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    request_id = correlation_id_ctx.get() or request.headers.get("X-Request-ID", "unknown")
    logger.warning(
        f"Application exception: {exc.code} - {exc.message}",
        extra={"extra_fields": {"code": exc.code, "details": exc.details}},
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "request_id": request_id,
                "details": exc.details,
            }
        },
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = correlation_id_ctx.get() or request.headers.get("X-Request-ID", "unknown")
    logger.exception(f"Unhandled server error: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred. Please contact support.",
                "request_id": request_id,
                "details": None,
            }
        },
    )

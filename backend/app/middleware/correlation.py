"""Request Correlation ID Middleware."""

import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from backend.app.core.logging import correlation_id_ctx


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware extracting or generating X-Request-ID and setting it in contextvars."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = (
            request.headers.get("X-Request-ID")
            or request.headers.get("X-Correlation-ID")
            or str(uuid.uuid4())
        )
        correlation_id_ctx.set(correlation_id)
        request.state.correlation_id = correlation_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = correlation_id
        return response

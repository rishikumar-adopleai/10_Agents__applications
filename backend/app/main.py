"""FastAPI Application Entry Point and Factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from backend.app.api.v1.router import api_router
from backend.app.core.config import settings
from backend.app.core.exceptions import (
    AppException,
    app_exception_handler,
    global_exception_handler,
)
from backend.app.core.logging import correlation_id_ctx, logger, setup_logging
from backend.app.db.base import Base
from backend.app.db.session import engine
from backend.app.middleware.correlation import CorrelationIdMiddleware
from backend.app.middleware.security_headers import SecurityHeadersMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifespan management."""
    # 1. Setup structured logging
    setup_logging(log_level=settings.LOG_LEVEL, log_format=settings.LOG_FORMAT)
    logger.info(f"Initializing {settings.APP_NAME} in '{settings.APP_ENV}' mode")

    # 2. Validate production configuration
    settings.validate_production()

    # 3. Create tables for local development / testing if using SQLite
    if settings.DATABASE_URL.startswith("sqlite"):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            for col_sql in [
                "ALTER TABLE campaigns ADD COLUMN subject VARCHAR(500)",
                "ALTER TABLE campaigns ADD COLUMN template_body TEXT",
                "ALTER TABLE campaigns ADD COLUMN product_slug VARCHAR(100)",
                "ALTER TABLE campaigns ADD COLUMN product_name VARCHAR(255)",
                "ALTER TABLE campaigns ADD COLUMN demo_url VARCHAR(500)",
                "ALTER TABLE campaigns ADD COLUMN target_companies_count INTEGER DEFAULT 0",
                "ALTER TABLE campaigns ADD COLUMN target_contacts_count INTEGER DEFAULT 0",
                "ALTER TABLE campaigns ADD COLUMN emails_sent_count INTEGER DEFAULT 0",
                "ALTER TABLE campaigns ADD COLUMN replies_count INTEGER DEFAULT 0",
                "ALTER TABLE campaigns ADD COLUMN positive_replies_count INTEGER DEFAULT 0",
                "ALTER TABLE campaigns ADD COLUMN failed_count INTEGER DEFAULT 0",
            ]:
                try:
                    await conn.execute(text(col_sql))
                except Exception:
                    pass
        logger.info("SQLite schema initialized for local/test mode")

    yield

    # Shutdown
    logger.info("Shutting down application database engine...")
    await engine.dispose()


def create_app() -> FastAPI:
    """FastAPI Application Factory."""
    app = FastAPI(
        title=settings.APP_NAME,
        version="1.0.0",
        description="Production-Grade Enterprise Sales Agent Platform integrating ten specialized AI agents.",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Middlewares (Executed in reverse order of addition)
    # 1. Security Headers
    app.add_middleware(SecurityHeadersMiddleware)

    # 2. Correlation ID
    app.add_middleware(CorrelationIdMiddleware)

    # 3. CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS
        if isinstance(settings.CORS_ORIGINS, list)
        else [settings.CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "Content-Disposition"],
    )

    # Exception Handlers
    app.add_exception_handler(AppException, app_exception_handler)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        request_id = correlation_id_ctx.get() or request.headers.get("X-Request-ID", "unknown")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Input validation failed. Please check the request parameters.",
                    "request_id": request_id,
                    "details": exc.errors(),
                }
            },
        )

    app.add_exception_handler(Exception, global_exception_handler)

    # Include API Routers under /api/v1
    app.include_router(api_router)

    return app


app = create_app()

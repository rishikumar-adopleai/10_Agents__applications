"""Health and Readiness Probes."""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db

router = APIRouter(tags=["monitoring"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """Liveness probe: verifies that the FastAPI application is alive."""
    return {"status": "ok", "service": "enterprise-sales-agent-platform"}


@router.get("/ready", status_code=status.HTTP_200_OK)
async def readiness_check(session: AsyncSession = Depends(get_db)):
    """Readiness probe: checks database and essential infrastructure connectivity."""
    db_ok = False
    try:
        await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    if db_ok:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "ready", "database": "connected"},
        )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "not_ready", "database": "disconnected"},
    )

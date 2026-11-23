"""Integration Health and Configuration Endpoints."""

from typing import List

from fastapi import APIRouter, Depends

from backend.app.api.deps import get_current_user
from backend.app.core.rbac import CurrentUser
from backend.app.integrations.base import IntegrationHealth
from backend.app.integrations.registry import integration_registry
from backend.app.schemas.common import StandardResponse

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/health", response_model=StandardResponse[List[IntegrationHealth]])
async def check_integrations_health(
    current_user: CurrentUser = Depends(get_current_user),
):
    """Query connectivity health status across all configured external integration adapters."""
    results = await integration_registry.check_all_health()
    return StandardResponse(data=results)

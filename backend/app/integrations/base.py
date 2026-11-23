"""Base Integration Adapter and Contracts."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pydantic import BaseModel


class IntegrationHealth(BaseModel):
    provider: str
    status: str  # healthy, degraded, unavailable
    latency_ms: int = 0
    details: Optional[Dict[str, Any]] = None


class BaseIntegrationAdapter(ABC):
    """Base interface for all external service integrations."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Machine identifier of the external provider."""
        pass

    @abstractmethod
    async def check_health(self) -> IntegrationHealth:
        """Verify external provider connectivity and credentials."""
        pass

"""GoHighLevel (GHL) CRM Integration Adapter."""

from typing import Any, Dict, Optional

import httpx

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.integrations.base import BaseIntegrationAdapter, IntegrationHealth


class GoHighLevelAdapter(BaseIntegrationAdapter):
    def __init__(self, access_token: Optional[str] = None, location_id: Optional[str] = None):
        self.access_token = access_token or settings.GHL_ACCESS_TOKEN
        self.location_id = location_id or settings.GHL_LOCATION_ID
        self.base_url = settings.GHL_BASE_URL

    @property
    def provider_name(self) -> str:
        return "gohighlevel"

    async def check_health(self) -> IntegrationHealth:
        if self.access_token.startswith("mock"):
            return IntegrationHealth(
                provider=self.provider_name,
                status="healthy",
                latency_ms=6,
                details={"mode": "mock"},
            )
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(
                    f"{self.base_url}/contacts/?locationId={self.location_id}&limit=1",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Version": "2021-07-28",
                    },
                )
                if res.status_code == 200:
                    return IntegrationHealth(
                        provider=self.provider_name, status="healthy", latency_ms=30
                    )
                return IntegrationHealth(provider=self.provider_name, status="degraded")
        except Exception as e:
            return IntegrationHealth(
                provider=self.provider_name, status="unavailable", details={"error": str(e)}
            )

    async def sync_contact(self, phone: str, email: str, name: str) -> Dict[str, Any]:
        """Create or update contact in GHL CRM."""
        if self.access_token.startswith("mock"):
            logger.info(f"[Mock GHL] Synced contact {phone} ({email})")
            return {"id": "mock-ghl-contact-9988", "phone": phone, "email": email, "name": name}

        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(
                f"{self.base_url}/contacts/",
                headers={"Authorization": f"Bearer {self.access_token}", "Version": "2021-07-28"},
                json={"phone": phone, "email": email, "name": name, "locationId": self.location_id},
            )
            res.raise_for_status()
            return res.json()

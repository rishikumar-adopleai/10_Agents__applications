"""HubSpot CRM Integration Adapter."""

from typing import Any, Dict, Optional

import httpx

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.integrations.base import BaseIntegrationAdapter, IntegrationHealth


class HubSpotAdapter(BaseIntegrationAdapter):
    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token or settings.HUBSPOT_ACCESS_TOKEN
        self.base_url = settings.HUBSPOT_BASE_URL

    @property
    def provider_name(self) -> str:
        return "hubspot"

    async def check_health(self) -> IntegrationHealth:
        if not settings.ENABLE_HUBSPOT or not self.access_token or self.access_token in ("mock-hubspot-token", ""):
            return IntegrationHealth(
                provider=self.provider_name,
                status="not_configured",
                latency_ms=0,
                details={"reason": "HubSpot credentials not configured or disabled via ENABLE_HUBSPOT"},
            )
        if self.access_token.startswith("mock"):
            return IntegrationHealth(
                provider=self.provider_name,
                status="not_configured",
                latency_ms=0,
                details={"reason": "Mock credentials provided in production configuration"},
            )
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(
                    f"{self.base_url}/crm/v3/objects/contacts?limit=1",
                    headers={"Authorization": f"Bearer {self.access_token}"},
                )
                if res.status_code == 200:
                    return IntegrationHealth(
                        provider=self.provider_name, status="healthy", latency_ms=25
                    )
                if res.status_code in (401, 403):
                    self._auth_failed = True
                    return IntegrationHealth(
                        provider=self.provider_name,
                        status="unauthorized",
                        details={"status_code": res.status_code, "reason": "Invalid or expired access token"},
                    )
                return IntegrationHealth(
                    provider=self.provider_name,
                    status="degraded",
                    details={"status_code": res.status_code},
                )
        except Exception as e:
            return IntegrationHealth(
                provider=self.provider_name, status="unavailable", details={"error": str(e)}
            )

    async def sync_contact(self, email: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update contact in HubSpot CRM."""
        if self.access_token.startswith("mock"):
            logger.info(f"[Mock HubSpot] Synced contact {email} with properties {properties}")
            return {"id": "mock-hs-contact-12345", "email": email, "properties": properties}

        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(
                f"{self.base_url}/crm/v3/objects/contacts",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                },
                json={"properties": {"email": email, **properties}},
            )
            res.raise_for_status()
            return res.json()

    async def fetch_company_intent(self, domain: str, account_id: str) -> Optional[Dict[str, Any]]:
        """Fetch buyer intent and engagement signals for a company domain.
        
        Strict enterprise policy:
        - Never fabricates intent based on mere CRM existence or mock fallbacks.
        - Returns None if HubSpot integration is disabled, unconfigured, unauthorized, or lacks real engagement.
        """
        if not settings.ENABLE_HUBSPOT:
            return None

        # Return None if not configured with valid real credentials or if auth previously failed
        if (
            not self.access_token
            or self.access_token in ("mock-hubspot-token", "")
            or self.access_token.startswith("mock")
            or getattr(self, "_auth_failed", False)
        ):
            return None

        # When live credentials are provided, search for company domain
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.post(
                    f"{self.base_url}/crm/v3/objects/companies/search",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "filterGroups": [
                            {
                                "filters": [
                                    {"propertyName": "domain", "operator": "EQ", "value": domain}
                                ]
                            }
                        ],
                        "properties": [
                            "name",
                            "domain",
                            "num_associated_contacts",
                            "hs_analytics_num_page_views",
                            "hs_analytics_last_visit_timestamp",
                            "recent_conversion_event_name",
                            "notes_last_updated",
                        ],
                        "limit": 1,
                    },
                )
                if res.status_code == 200:
                    results = res.json().get("results", [])
                    if results:
                        company = results[0]
                        comp_id = company.get("id")
                        props = company.get("properties", {})
                        page_views = int(props.get("hs_analytics_num_page_views") or 0)
                        last_visit = props.get("hs_analytics_last_visit_timestamp")
                        recent_conversion = props.get("recent_conversion_event_name")

                        # Positive intent requires demonstrable engagement activity, not merely existing in CRM
                        if page_views > 0 or recent_conversion:
                            fact_parts = []
                            if page_views > 0:
                                fact_parts.append(f"{page_views} website page view(s)")
                            if recent_conversion:
                                fact_parts.append(f"form conversion '{recent_conversion}'")
                            engagement_summary = " and ".join(fact_parts)

                            return {
                                "account_id": account_id,
                                "signal_type": "interest",
                                "signal_subtype": "crm_engagement",
                                "observed_fact": f"Demonstrated inbound engagement recorded in HubSpot CRM: {engagement_summary} for {domain}.",
                                "business_hypothesis": "Recent active website engagement and form activity indicates ongoing evaluation.",
                                "source_provider": "hubspot",
                                "source_url": f"https://app.hubspot.com/contacts/{comp_id}",
                                "source_record_id": str(comp_id),
                                "published_at": last_visit,
                                "verification_status": "VERIFIED",
                                "confidence": 0.85,
                                "raw_metadata": {
                                    "hubspot_company_id": comp_id,
                                    "page_views": page_views,
                                    "recent_conversion": recent_conversion,
                                    "last_visit": last_visit,
                                },
                            }
                        # Present in CRM but no active buying engagement
                        return None
                elif res.status_code in (401, 403):
                    self._auth_failed = True
                    logger.warning(
                        f"HubSpot API unauthorized ({res.status_code}). Disabling live intent lookup."
                    )
                    return None
                else:
                    logger.warning(f"HubSpot search returned HTTP {res.status_code} for {domain}")
                    return None
            return None
        except Exception as exc:
            logger.debug(f"HubSpot intent check failed for {domain}: {exc}")
            return None

"""Apollo.io Account and Contact Enrichment Adapter."""

from typing import Any, Dict, List, Optional

import httpx

from backend.app.core.config import is_configured_value, settings
from backend.app.core.logging import logger
from backend.app.integrations.base import BaseIntegrationAdapter, IntegrationHealth


class ApolloAdapter(BaseIntegrationAdapter):
    """Adapter for Apollo.io Company Search & Enrichment (Future API Integration)."""

    def __init__(self, api_key: Optional[str] = None):
        self._explicit_api_key = api_key
        self.base_url = settings.APOLLO_BASE_URL

    @property
    def api_key(self) -> Optional[str]:
        return self._explicit_api_key or settings.APOLLO_API_KEY

    @property
    def provider_name(self) -> str:
        return "apollo"

    def _is_live_enabled(self, mode: Optional[str] = None) -> bool:
        effective_mode = (mode or ("production" if settings.is_pipeline2_production else "test")).lower()
        if effective_mode == "test":
            return False
        if effective_mode == "production":
            return True
        return settings.CONTACT_PROVIDER.lower() != "mock"

    def _headers(self) -> Dict[str, str]:
        return {
            "X-Api-Key": str(self.api_key),
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
        }

    async def check_health(self) -> IntegrationHealth:
        if not self._is_live_enabled() or not is_configured_value(self.api_key):
            return IntegrationHealth(
                provider=self.provider_name,
                status="healthy",
                latency_ms=4,
                details={"mode": "mock", "configured": is_configured_value(self.api_key)},
            )
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.post(
                    f"{self.base_url}/organizations/enrich",
                    headers=self._headers(),
                    json={"domain": "example.com"},
                )
                if res.status_code in [200, 404]:
                    return IntegrationHealth(
                        provider=self.provider_name,
                        status="healthy",
                        latency_ms=40,
                        details={"mode": "production"},
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

    async def enrich_organization(
        self, domain: str, mode: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetch organization profile and buying signals from Apollo."""
        if not self._is_live_enabled(mode) or ".example" in (domain or "").lower():
            return {
                "name": domain.split(".")[0].capitalize(),
                "domain": domain,
                "estimated_num_employees": 250,
                "industry": "Software & Technology",
                "technologies": ["AWS", "Salesforce", "PostgreSQL", "React"],
            }

        if not is_configured_value(self.api_key):
            logger.error("[Apollo] Production org enrichment failed: APOLLO_API_KEY is missing or placeholder.")
            raise ValueError("APOLLO_API_KEY is missing or not configured for production mode.")

        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                res = await client.post(
                    f"{self.base_url}/organizations/enrich",
                    headers=self._headers(),
                    json={"domain": domain},
                )
                if res.status_code in (401, 403):
                    logger.error(f"[Apollo] Authentication failed on org enrichment (HTTP {res.status_code}).")
                    raise PermissionError(f"Apollo authentication failed (HTTP {res.status_code}).")
                if res.status_code == 429:
                    logger.warning("[Apollo] Rate limit exceeded on org enrichment (HTTP 429).")
                    raise RuntimeError("Apollo API rate limit exceeded (HTTP 429).")
                res.raise_for_status()
                org = res.json().get("organization") or {}
                logger.info(f"[Apollo] Enriched organization for domain='{domain}'.")
                return org
        except (ValueError, PermissionError, RuntimeError):
            raise
        except httpx.TimeoutException:
            logger.warning(f"[Apollo] Organization enrichment timed out for domain='{domain}'.")
            raise RuntimeError("Apollo API organization enrichment timed out.")
        except Exception as e:
            logger.warning(f"[Apollo] Organization enrichment failed for domain='{domain}': {type(e).__name__}")
            raise RuntimeError(f"Apollo organization enrichment error: {type(e).__name__}")

    async def search_organizations(
        self, criteria: Dict[str, Any], page: int = 1, per_page: int = 25
    ) -> Dict[str, Any]:
        """Future Apollo search endpoint for loading accounts matching approved ICP."""
        if not self.api_key or self.api_key == "mock-apollo-key" or not is_configured_value(self.api_key):
            logger.info("Apollo search called without active credentials. Ingestion relies on CSV export.")
            return {"organizations": [], "pagination": {"page": page, "total_pages": 0, "total_entries": 0}}

        payload = {
            "api_key": self.api_key,
            "q_organization_locations": [criteria.get("country", "United States")],
            "page": page,
            "per_page": min(per_page, 100),
        }
        if criteria.get("target_industries"):
            payload["organization_industry_tag_ids"] = criteria["target_industries"]
        if criteria.get("employee_min") or criteria.get("employee_max"):
            payload["organization_num_employees_ranges"] = [
                f"{criteria.get('employee_min', 1)},{criteria.get('employee_max', 100000)}"
            ]

        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(f"{self.base_url}/mixed_companies/search", json=payload)
            res.raise_for_status()
            data = res.json()
            return {
                "organizations": data.get("organizations", []),
                "pagination": data.get("pagination", {}),
            }

    @staticmethod
    def _normalize_person(person: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize an Apollo person record into Pipeline 2's contact schema."""
        first_name = (person.get("first_name") or "").strip()
        last_name = (person.get("last_name") or "").strip()
        full_name = (person.get("name") or f"{first_name} {last_name}").strip() or "Decision Maker"
        if not first_name and full_name:
            parts = full_name.split(None, 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ""

        email = person.get("email")
        phone = None
        phone_numbers = person.get("phone_numbers") or []
        if isinstance(phone_numbers, list) and phone_numbers:
            first_phone = phone_numbers[0]
            if isinstance(first_phone, dict):
                phone = first_phone.get("sanitized_number") or first_phone.get("raw_number")
            elif isinstance(first_phone, str):
                phone = first_phone

        has_method = bool(email or phone)
        email_status = (person.get("email_status") or "unknown").lower()
        return {
            "contact_id": str(person.get("id") or f"apollo-{full_name.lower().replace(' ', '-')}"),
            "first_name": first_name,
            "last_name": last_name,
            "full_name": full_name,
            "job_title": person.get("title") or "",
            "seniority": person.get("seniority") or "",
            "email": email,
            "phone": phone,
            "linkedin_url": person.get("linkedin_url"),
            "verification_status": email_status if email else "missing_email",
            "source": "apollo_live",
            "is_suppressed": False,
            "logical_outreach_attempts": 0,
            "contact_eligibility": "eligible" if has_method else "blocked_missing_address",
        }

    async def search_contacts(
        self,
        domain: str,
        role_titles: Optional[List[str]] = None,
        limit: int = 5,
        mode: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch contacts associated with a company domain from Apollo."""
        if not self._is_live_enabled(mode) or ".example" in (domain or "").lower():
            # Test mode: return empty list so local/mock fixtures are used without live network calls
            return []

        if not is_configured_value(self.api_key):
            logger.error("[Apollo] Production contact search failed: APOLLO_API_KEY is missing or placeholder.")
            raise ValueError("APOLLO_API_KEY is missing or not configured for production mode.")

        payload: Dict[str, Any] = {
            "q_organization_domains": domain,
            "page": 1,
            "per_page": limit,
        }
        if role_titles:
            payload["person_titles"] = role_titles

        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                res = await client.post(
                    f"{self.base_url}/mixed_people/search",
                    headers=self._headers(),
                    json=payload,
                )
                if res.status_code in (401, 403):
                    logger.error(f"[Apollo] Authentication failed on contact search (HTTP {res.status_code}).")
                    raise PermissionError(f"Apollo authentication failed (HTTP {res.status_code}).")
                if res.status_code == 429:
                    logger.warning("[Apollo] Rate limit exceeded on contact search (HTTP 429).")
                    raise RuntimeError("Apollo API rate limit exceeded (HTTP 429).")
                res.raise_for_status()
                people = res.json().get("people") or []
                normalized = [self._normalize_person(p) for p in people if isinstance(p, dict)]
                logger.info(f"[Apollo] Found {len(normalized)} contacts for domain='{domain}'.")
                return normalized
        except (ValueError, PermissionError, RuntimeError):
            raise
        except httpx.TimeoutException:
            logger.warning(f"[Apollo] Contact search timed out for domain='{domain}'.")
            raise RuntimeError("Apollo API contact search timed out.")
        except Exception as e:
            logger.warning(f"[Apollo] Contact search failed for domain='{domain}': {type(e).__name__}")
            raise RuntimeError(f"Apollo contact search error: {type(e).__name__}")

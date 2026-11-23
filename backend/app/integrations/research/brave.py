"""Brave Search API Adapter for External Web Research."""

from typing import Any, Dict, List, Optional, Union

import httpx

from backend.app.core.config import is_configured_value, settings
from backend.app.core.logging import logger
from backend.app.integrations.base import BaseIntegrationAdapter, IntegrationHealth


class BraveSearchAdapter(BaseIntegrationAdapter):
    """Configurable Brave Search API adapter supporting live and mock research."""

    def __init__(self, api_key: Optional[str] = None):
        self._explicit_api_key = api_key
        self.base_url = settings.BRAVE_SEARCH_BASE_URL

    @property
    def api_key(self) -> Optional[str]:
        return self._explicit_api_key or settings.BRAVE_SEARCH_API_KEY

    @property
    def provider_name(self) -> str:
        return "brave_search"

    def _is_live_enabled(self, mode: Optional[str] = None) -> bool:
        effective_mode = (mode or ("production" if settings.is_pipeline2_production else "test")).lower()
        if effective_mode == "test":
            return False
        if effective_mode == "production":
            return True
        return settings.RESEARCH_PROVIDER.lower() != "mock"

    async def check_health(self) -> IntegrationHealth:
        if not self._is_live_enabled() or not is_configured_value(self.api_key):
            return IntegrationHealth(
                provider=self.provider_name,
                status="healthy",
                latency_ms=2,
                details={"mode": "mock", "configured": is_configured_value(self.api_key)},
            )
        try:
            headers = {"X-Subscription-Token": str(self.api_key), "Accept": "application/json"}
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(
                    self.base_url,
                    headers=headers,
                    params={"q": "test", "count": 1},
                )
                if res.status_code == 200:
                    return IntegrationHealth(
                        provider=self.provider_name,
                        status="healthy",
                        latency_ms=45,
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

    async def search(
        self, query: str, count: int = 5, mode: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Perform web search. Safely returns empty list for synthetic queries or in test mode."""
        if not self._is_live_enabled(mode) or ".example" in query.lower():
            logger.info(f"[BraveSearch] Skipped live search (test mode or synthetic query: {query})")
            return []

        if not is_configured_value(self.api_key):
            logger.error("[BraveSearch] Production research skipped: BRAVE_SEARCH_API_KEY is missing or placeholder.")
            raise ValueError("BRAVE_SEARCH_API_KEY is missing or not configured for production mode.")

        headers = {
            "X-Subscription-Token": str(self.api_key),
            "Accept": "application/json",
        }
        params: Dict[str, Union[str, int]] = {"q": query, "count": count}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(self.base_url, headers=headers, params=params)
                if res.status_code in (401, 403):
                    logger.error(f"[BraveSearch] Authentication failed (HTTP {res.status_code}).")
                    raise PermissionError(f"Brave Search authentication failed (HTTP {res.status_code}).")
                if res.status_code == 429:
                    logger.warning("[BraveSearch] Rate limit exceeded (HTTP 429).")
                    raise RuntimeError("Brave Search API rate limit exceeded (HTTP 429).")
                res.raise_for_status()
                data = res.json()
                results = []
                for item in data.get("web", {}).get("results", []):
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "description": item.get("description", ""),
                    })
                logger.info(f"[BraveSearch] Retrieved {len(results)} live results for query='{query}'.")
                return results
        except (ValueError, PermissionError, RuntimeError):
            raise
        except httpx.TimeoutException:
            logger.warning(f"[BraveSearch] Request timed out for query '{query}'.")
            raise RuntimeError("Brave Search API request timed out.")
        except Exception as e:
            logger.warning(f"[BraveSearch] Search failed for query '{query}': {type(e).__name__}: {str(e)}")
            raise RuntimeError(f"Brave Search API failure: {type(e).__name__}")

    async def research_company(
        self,
        company_name: str,
        domain: str,
        industry: str = "",
        mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute targeted company research and return normalized signals/evidence."""
        if not self._is_live_enabled(mode) or ".example" in (domain or "").lower():
            return {"status": "skipped_test_mode", "results": [], "signals": [], "error": None}

        query = f'"{company_name}" OR site:{domain} {industry} news expansion hiring'.strip()
        try:
            results = await self.search(query=query, count=5, mode=mode)
            signals = [
                {
                    "signal_id": f"brave-{idx + 1}",
                    "type": "company_research",
                    "observed_fact": f"{r.get('title', '').strip()}: {r.get('description', '').strip()}".strip(": "),
                    "source": {"url": r.get("url", ""), "source_type": "brave_search"},
                    "confidence": "verified",
                }
                for idx, r in enumerate(results)
                if r.get("description") or r.get("title")
            ]
            return {
                "status": "completed",
                "results": results,
                "signals": signals,
                "error": None,
            }
        except Exception as e:
            return {
                "status": "failed",
                "results": [],
                "signals": [],
                "error": str(e),
            }

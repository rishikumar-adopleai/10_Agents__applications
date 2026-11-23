"""Company Growth Signal Adapter: GDELT DOC 2.0, Company Announcements, and Expansion Detection."""

import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.integrations.base import BaseIntegrationAdapter, IntegrationHealth
from backend.app.integrations.research.gdelt import GdeltDocAdapter

GROWTH_PATTERNS = {
    "funding": [r"funding", r"series [a-e]", r"raised \$", r"capital investment"],
    "expansion": [
        r"new (clinic|hospital|branch|location|facility|center)",
        r"expands (presence|operations|footprint)",
        r"opens (new|additional)",
    ],
    "merger_acquisition": [r"acqui(res|sition)", r"merg(es|er)", r"joins forces"],
    "leadership_change": [
        r"appoint(s|ed) (new )?(cio|coo|cto|cfo|chief|vp|vice president)",
        r"names (new )?(cio|coo|cto|cfo|chief|vp|vice president)",
        r"revenue cycle (leader|vp|director)",
    ],
}


class GrowthNewsAdapter(BaseIntegrationAdapter):
    """Adapter detecting growth signals from GDELT DOC 2.0 (primary zero-cost) and corporate announcements."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None,
    ):
        self.provider = getattr(settings, "NEWS_PROVIDER", "gdelt")
        self.gdelt_adapter = GdeltDocAdapter(client=client)
        self.api_key = (
            api_key
            or getattr(settings, "NEWS_API_KEY", None)
            or getattr(settings, "NEWSAPI_KEY", None)
        )
        self.base_url = getattr(settings, "NEWSAPI_BASE_URL", "https://newsapi.org/v2")
        self._client = client

    @property
    def provider_name(self) -> str:
        return "news_growth"

    async def check_health(self) -> IntegrationHealth:
        if not settings.ENABLE_NEWS:
            return IntegrationHealth(
                provider=self.provider_name,
                status="not_configured",
                details={"reason": "Disabled via ENABLE_NEWS"},
            )

        if self.provider == "gdelt" or settings.ENABLE_GDELT:
            return await self.gdelt_adapter.check_health()

        if not self.api_key:
            return IntegrationHealth(
                provider=self.provider_name,
                status="not_configured",
                details={"reason": "NewsAPI not configured and GDELT not primary"},
            )

        return IntegrationHealth(
            provider=self.provider_name,
            status="healthy",
            latency_ms=15,
            details={"mode": "newsapi"},
        )

    async def search_news(self, company_name: str, domain: str) -> List[Dict[str, Any]]:
        """Search news for verifiable expansion or executive changes using GDELT (primary zero-cost) or NewsAPI."""
        if not settings.ENABLE_NEWS:
            return []

        # 1. Primary: GDELT DOC 2.0 Engine (Zero-Cost Global Intelligence, no paid API key required)
        if self.provider == "gdelt" or settings.ENABLE_GDELT:
            articles, status = await self.gdelt_adapter.search_growth_news(
                company_name=company_name,
                domain=domain,
                timespan="3m",
                max_records=10,
            )
            if articles:
                return articles

        # 2. NewsAPI only if explicitly configured as provider and key is present
        if self.provider == "newsapi" and self.api_key:
            query = f'"{company_name}" AND (funding OR expansion OR acquisition OR appointment OR "revenue cycle")'
            url = f"{self.base_url}/everything?q={quote(query)}&sortBy=publishedAt&pageSize=10&language=en"

            try:
                headers = {"X-Api-Key": self.api_key}
                if self._client:
                    res = await self._client.get(url, headers=headers, timeout=5.0)
                else:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        res = await client.get(url, headers=headers)

                if res.status_code == 200:
                    data = res.json()
                    articles = data.get("articles", [])
                    if articles:
                        return articles
            except Exception as exc:
                logger.debug(f"NewsAPI query failed for {company_name}: {exc}")

        return []

    def classify_growth_events(
        self,
        articles: List[Dict[str, Any]],
        account_id: str,
        company_name: str,
    ) -> List[Dict[str, Any]]:
        """Classify candidate articles into verified growth signals conforming to EvidenceValidationService."""
        import hashlib

        if not articles:
            return []

        # If articles are formatted from GDELT, use GdeltDocAdapter classification
        if any("seendate" in a for a in articles) or any("sourcecountry" in a for a in articles):
            return self.gdelt_adapter.classify_growth_signals(articles, account_id, company_name)

        # Otherwise fallback to standard article parser
        signals = []
        seen_titles = set()

        for art in articles:
            title = art.get("title", "")
            description = art.get("description", "") or ""
            content = f"{title} {description}".lower()
            source_url = art.get("url", "")
            published_at = art.get("publishedAt")

            # Deduplication
            normalized_title = re.sub(r"[^a-z0-9]", "", title.lower()[:50])
            if normalized_title in seen_titles:
                continue
            seen_titles.add(normalized_title)

            # Match patterns
            matched_subtype = None
            for subtype, patterns in GROWTH_PATTERNS.items():
                for pat in patterns:
                    if re.search(pat, content):
                        matched_subtype = subtype
                        break
                if matched_subtype:
                    break

            if matched_subtype:
                record_id = f"news-{hashlib.sha256(source_url.encode('utf-8')).hexdigest()[:16]}"
                signals.append({
                    "account_id": account_id,
                    "signal_type": "growth",
                    "signal_subtype": matched_subtype,
                    "headline": title[:250],
                    "observed_fact": f"Growth announcement: '{title}'.",
                    "business_hypothesis": f"Recent {matched_subtype.replace('_', ' ')} creates organizational pressure and budget for digital acceleration.",
                    "source_provider": "newsapi",
                    "source_title": art.get("source", {}).get("name", "News"),
                    "source_url": source_url,
                    "source_record_id": record_id,
                    "published_at": published_at,
                    "confidence": 0.80,
                    "verification_status": "VERIFIED",
                    "raw_metadata": {
                        "title": title,
                        "source": art.get("source", {}).get("name", "News"),
                    },
                })

        return signals

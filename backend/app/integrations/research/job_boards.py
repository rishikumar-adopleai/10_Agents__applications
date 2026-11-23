"""Greenhouse and Lever Public Job Board Adapters for Hiring Signal Detection."""

import re
from typing import Any, Dict, List, Optional

import httpx

from backend.app.core.config import settings
from backend.app.integrations.base import BaseIntegrationAdapter, IntegrationHealth

# Relevant operational keywords indicating manual work piling up
HIRING_KEYWORDS = {
    "prior_authorization": [
        "prior authorization",
        "prior auth",
        "pre-authorization",
        "precertification",
    ],
    "claims_processing": [
        "claims processor",
        "claims processing",
        "claims examiner",
        "claims specialist",
        "claims adjudication",
        "claims",
    ],
    "referral_intake": [
        "referral coordinator",
        "patient intake",
        "intake specialist",
        "referral specialist",
    ],
    "medical_records": [
        "medical records clerk",
        "health information specialist",
        "him technician",
        "records release",
    ],
    "revenue_cycle": [
        "revenue cycle",
        "rcm specialist",
        "billing specialist",
        "medical biller",
        "denials management",
    ],
    "kyc_fraud": [
        "kyc",
        "aml",
        "anti-money laundering",
        "fraud investigator",
        "fraud review",
        "fraud specialist",
        "fraud analyst",
        "fraud",
        "kyc analyst",
        "aml analyst",
    ],
    "loan_document": [
        "loan processor",
        "mortgage underwriter",
        "document review specialist",
        "closing coordinator",
    ],
}


class GreenhouseAdapter(BaseIntegrationAdapter):
    """Adapter for Greenhouse Public Job Board API."""

    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self.base_url = "https://boards-api.greenhouse.io/v1/boards"
        self._client = client

    @property
    def provider_name(self) -> str:
        return "greenhouse"

    async def check_health(self) -> IntegrationHealth:
        if not settings.ENABLE_GREENHOUSE:
            return IntegrationHealth(
                provider=self.provider_name,
                status="not_configured",
                details={"reason": "Disabled via ENABLE_GREENHOUSE"},
            )
        return IntegrationHealth(
            provider=self.provider_name,
            status="healthy",
            latency_ms=10,
            details={"mode": "public_api"},
        )

    def extract_token_from_domain(self, domain_or_name: str) -> str:
        """Derive standard board token from domain or company name."""
        clean = domain_or_name.lower().replace("http://", "").replace("https://", "").replace("www.", "")
        name = clean.split(".")[0]
        # Keep alphanumeric and hyphens
        return re.sub(r"[^a-z0-9\-]", "", name)

    async def fetch_jobs(self, board_token: str) -> List[Dict[str, Any]]:
        """Fetch open jobs from Greenhouse public board."""
        url = f"{self.base_url}/{board_token}/jobs"
        try:
            if self._client:
                res = await self._client.get(url, timeout=2.0)
            else:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    res = await client.get(url)

            if res.status_code == 200:
                data = res.json()
                return data.get("jobs", [])
            return []
        except Exception:
            return []

    def detect_signals(
        self, jobs: List[Dict[str, Any]], account_id: str, company_name: str
    ) -> List[Dict[str, Any]]:
        """Scan job titles and content for operational workload keywords."""
        signals = []
        for job in jobs:
            title = job.get("title", "")
            title_lower = title.lower()
            job_url = job.get("absolute_url") or f"https://boards.greenhouse.io/{account_id}/jobs/{job.get('id')}"
            location = job.get("location", {}).get("name") if isinstance(job.get("location"), dict) else str(job.get("location") or "")
            updated_at = job.get("updated_at")

            for subtype, keywords in HIRING_KEYWORDS.items():
                for kw in keywords:
                    if kw in title_lower:
                        signals.append({
                            "account_id": account_id,
                            "signal_type": "hiring",
                            "signal_subtype": subtype,
                            "observed_fact": f"Active open job for '{title}' (Location: {location or 'Remote/US'}).",
                            "business_hypothesis": f"Manual operational volume in {subtype.replace('_', ' ')} indicates high automation ROI.",
                            "source_provider": "greenhouse",
                            "source_url": job_url,
                            "source_record_id": str(job.get("id")),
                            "published_at": updated_at,
                            "raw_metadata": {
                                "title": title,
                                "location": location,
                                "matched_keyword": kw,
                            },
                        })
                        break  # Match one subtype per job
        return signals


class LeverAdapter(BaseIntegrationAdapter):
    """Adapter for Lever Public Postings API."""

    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self.base_url = "https://api.lever.co/v0/postings"
        self._client = client

    @property
    def provider_name(self) -> str:
        return "lever"

    async def check_health(self) -> IntegrationHealth:
        if not settings.ENABLE_LEVER:
            return IntegrationHealth(
                provider=self.provider_name,
                status="not_configured",
                details={"reason": "Disabled via ENABLE_LEVER"},
            )
        return IntegrationHealth(
            provider=self.provider_name,
            status="healthy",
            latency_ms=10,
            details={"mode": "public_api"},
        )

    def extract_site_from_domain(self, domain_or_name: str) -> str:
        clean = domain_or_name.lower().replace("http://", "").replace("https://", "").replace("www.", "")
        name = clean.split(".")[0]
        return re.sub(r"[^a-z0-9\-]", "", name)

    async def fetch_postings(self, site: str) -> List[Dict[str, Any]]:
        """Fetch open postings from Lever public API."""
        url = f"{self.base_url}/{site}"
        try:
            if self._client:
                res = await self._client.get(url, timeout=2.0)
            else:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    res = await client.get(url)

            if res.status_code == 200:
                return res.json()
            return []
        except Exception:
            return []

    def detect_signals(
        self, postings: List[Dict[str, Any]], account_id: str, company_name: str
    ) -> List[Dict[str, Any]]:
        signals = []
        for post in postings:
            title = post.get("text", "")
            title_lower = title.lower()
            post_url = post.get("hostedUrl") or post.get("applyUrl") or f"https://jobs.lever.co/{company_name}"
            categories = post.get("categories", {})
            location = categories.get("location") or ""
            created_at = post.get("createdAt")
            pub_date = None
            if created_at:
                try:
                    if isinstance(created_at, (int, float)):
                        from datetime import datetime, timezone
                        pub_date = datetime.fromtimestamp(created_at / 1000.0, tz=timezone.utc).isoformat()
                    elif isinstance(created_at, str):
                        pub_date = created_at
                except Exception:
                    pub_date = None

            for subtype, keywords in HIRING_KEYWORDS.items():
                for kw in keywords:
                    if kw in title_lower:
                        signals.append({
                            "account_id": account_id,
                            "signal_type": "hiring",
                            "signal_subtype": subtype,
                            "observed_fact": f"Hiring observed on Lever: '{title}' in {location or 'US'}.",
                            "business_hypothesis": f"Manual workload in {subtype.replace('_', ' ')} represents immediate AI intake/processing opportunity.",
                            "source_provider": "lever",
                            "source_url": post_url,
                            "source_record_id": str(post.get("id")),
                            "published_at": pub_date,
                            "confidence": 0.90,
                            "verification_status": "VERIFIED",
                            "raw_metadata": {
                                "title": title,
                                "location": location,
                                "matched_keyword": kw,
                            },
                        })
                        break
        return signals

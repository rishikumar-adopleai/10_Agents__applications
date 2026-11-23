"""Configurable LLM Provider Gateway."""

import json
from typing import Any, Dict, Optional

import httpx

from backend.app.core.config import is_configured_value, settings
from backend.app.core.logging import logger
from backend.app.integrations.base import BaseIntegrationAdapter, IntegrationHealth


class LLMGateway(BaseIntegrationAdapter):
    def __init__(self):
        self.timeout = settings.AI_TIMEOUT_SECONDS

    @property
    def provider(self) -> str:
        return settings.AI_PROVIDER

    @property
    def api_key(self) -> Optional[str]:
        if is_configured_value(settings.LLM_API_KEY):
            return settings.LLM_API_KEY
        return settings.OPENAI_API_KEY

    @property
    def model(self) -> str:
        return settings.LLM_MODEL or settings.OPENAI_MODEL

    @property
    def fallback_model(self) -> str:
        return settings.OPENAI_FALLBACK_MODEL

    @property
    def provider_name(self) -> str:
        return "llm_gateway"

    def _is_live_enabled(self, mode: Optional[str] = None) -> bool:
        if not is_configured_value(self.api_key):
            return False
        if mode is not None:
            return mode.lower() == "production"
        if settings.is_pipeline2_production:
            return True
        return self.provider.lower() != "mock"

    def _build_request(self, model_name: str, system_prompt: str, user_prompt: str, response_format: Optional[str]):
        azure_endpoint = settings.AZURE_OPENAI_ENDPOINT
        payload: Dict[str, Any] = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        if response_format:
            payload["response_format"] = {"type": response_format}

        if is_configured_value(azure_endpoint):
            base = str(azure_endpoint).rstrip("/")
            url = (
                f"{base}/openai/deployments/{model_name}/chat/completions"
                f"?api-version={settings.AZURE_OPENAI_API_VERSION}"
            )
            headers = {
                "api-key": str(self.api_key),
                "Content-Type": "application/json",
            }
            return url, headers, payload

        payload["model"] = model_name
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        return url, headers, payload

    async def check_health(self) -> IntegrationHealth:
        return IntegrationHealth(
            provider=self.provider_name,
            status="healthy",
            latency_ms=10,
            details={
                "provider": "azure_openai" if is_configured_value(settings.AZURE_OPENAI_ENDPOINT) else self.provider,
                "primary_model": self.model,
                "live_configured": is_configured_value(self.api_key),
            },
        )

    async def _invoke_model(
        self,
        model_name: str,
        system_prompt: str,
        user_prompt: str,
        response_format: Optional[str],
    ) -> Dict[str, Any]:
        url, headers, payload = self._build_request(
            model_name, system_prompt, user_prompt, response_format
        )
        async with httpx.AsyncClient(timeout=float(self.timeout)) as client:
            res = await client.post(url, headers=headers, json=payload)
            if res.status_code in (401, 403):
                raise PermissionError(f"LLM provider authentication failed (HTTP {res.status_code}).")
            if res.status_code == 429:
                raise RuntimeError("LLM provider rate limit exceeded (HTTP 429).")
            res.raise_for_status()
            data = res.json()
            content = data["choices"][0]["message"]["content"]
            if response_format == "json_object":
                parsed = json.loads(content)
                return dict(parsed) if isinstance(parsed, dict) else {"content": parsed}
            return {"content": content}

    async def generate_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: Optional[str] = "json_object",
        mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate structured completion using primary or fallback model."""
        if not self._is_live_enabled(mode):
            logger.info("Using deterministic Mock LLM Gateway response")
            # If prompt requests opportunity analysis, return full structured schema
            combined = f"{system_prompt}\n{user_prompt}".lower()
            if "opportunity_analysis" in combined or "company_overview" in combined:
                return {
                    "company_overview": "Target enterprise organization operating in high-demand technical domain with active expansion signals.",
                    "verified_business_info": {
                        "operational_scale": "Enterprise tier",
                        "technology_footprint": "Modern cloud infrastructure with focus on efficiency and automation",
                    },
                    "buying_signal_analysis": "Recent observable hiring/expansion activities indicate organizational readiness for sales/operations automation.",
                    "potential_business_needs": "Streamlining inbound qualification, scaling outreach velocity, and shortening technical proposal turnaround.",
                    "relevant_service_offering": "Autonomous Enterprise Sales and Workflow Automation Platform",
                    "supporting_evidence": [
                        "Observed hiring and expansion signals from verified job/press sources",
                        "Documented enterprise growth trajectory",
                    ],
                    "suggested_contact": {
                        "rationale": "High-ranking decision maker overseeing engineering or operational execution",
                    },
                    "unverified_assumptions": [
                        "Current legacy stack integration complexity requires confirmation during discovery"
                    ],
                }

            if "outreach_draft" in combined or "draft_body" in combined or "personalized_outreach" in combined:
                return {
                    "draft_body": "Noticed your team's recent expansion. Our platform helps enterprise teams respond to opportunities within seconds. Would you be open to a 2-minute conversation next week?",
                    "reason_for_contact": "Aligning autonomous workflow automation with recent corporate expansion",
                    "call_to_action": "10-minute discovery conversation or tailored demo review",
                }

            return {
                "decision": "approved",
                "reasoning": "Inputs conform to enterprise ICP and business rules.",
                "confidence": 0.96,
            }

        if not is_configured_value(self.api_key):
            logger.error("[LLMGateway] Production LLM call failed: LLM_API_KEY/OPENAI_API_KEY is missing or placeholder.")
            raise ValueError("LLM API key is missing or not configured for production mode.")

        try:
            logger.info(f"[LLMGateway] Calling live LLM primary model='{self.model}'.")
            return await self._invoke_model(self.model, system_prompt, user_prompt, response_format)
        except PermissionError:
            logger.error(f"[LLMGateway] Authentication failed for model='{self.model}'.")
            raise
        except Exception as primary_err:
            logger.warning(
                f"[LLMGateway] Primary model '{self.model}' failed ({type(primary_err).__name__}). "
                f"Attempting fallback '{self.fallback_model}'."
            )
            if self.fallback_model and self.fallback_model != self.model:
                try:
                    return await self._invoke_model(
                        self.fallback_model, system_prompt, user_prompt, response_format
                    )
                except Exception as fb_err:
                    logger.error(
                        f"[LLMGateway] Fallback model '{self.fallback_model}' also failed ({type(fb_err).__name__})."
                    )
                    raise RuntimeError(f"LLM primary and fallback calls failed: {type(fb_err).__name__}")
            raise RuntimeError(f"LLM call failed: {type(primary_err).__name__}")

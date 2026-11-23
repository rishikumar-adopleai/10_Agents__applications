"""Demo Before Hello Agent."""

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agents.base import BaseAgent
from backend.app.models.artifacts import DemoArtifact
from backend.app.schemas.agents import (
    AgentExecutionRequest,
    AgentExecutionResult,
    AgentStatus,
    ArtifactReference,
)


class DemoBeforeHelloAgent(BaseAgent):
    @property
    def agent_id(self) -> str:
        return "demo_before_hello"

    @property
    def name(self) -> str:
        return "Demo Before Hello"

    @property
    def description(self) -> str:
        return "Creates isolated, synthetic product demonstration environments for high-priority prospects."

    async def execute(
        self,
        request: AgentExecutionRequest,
        session: AsyncSession,
    ) -> AgentExecutionResult:
        account_id = request.account_id or request.parameters.get("account_id")
        template_name = request.parameters.get("template_name", "enterprise_sales_automation_v1")

        if not account_id:
            return AgentExecutionResult(
                agent_id=self.agent_id,
                execution_id=f"exec-{uuid.uuid4().hex[:12]}",
                status=AgentStatus.TERMINAL_FAILURE,
                error_details="account_id is required to build a tailored demo",
            )

        # Build synthetic demo environment (Strict Rule: Synthetic only, no production customer data)
        synthetic_payload = {
            "mock_company": "Acme Corp Demo Workspace",
            "sample_inquiries": [
                {"lead": "Sarah Connor", "message": "Can your platform sync with our HubSpot CRM?"},
                {"lead": "Alex Murphy", "message": "What SOC2 certifications do you hold?"},
            ],
            "configured_workflows": ["lead_responder", "deal_desk"],
        }
        walkthrough_script = (
            "1. Highlight autonomous inbound message ingestion within 2 seconds.\n"
            "2. Demonstrate grounded response formulation with evidence attribution.\n"
            "3. Show one-click commercial proposal generation with pricing guardrails."
        )

        access_token = secrets.token_urlsafe(32)
        expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

        demo = DemoArtifact(
            organization_id=request.organization_id,
            account_id=account_id,
            template_name=template_name,
            synthetic_payload=synthetic_payload,
            walkthrough_script=walkthrough_script,
            access_token=access_token,
            expires_at=expires_at,
            is_validated=True,
        )
        session.add(demo)
        await session.flush()

        return AgentExecutionResult(
            agent_id=self.agent_id,
            execution_id=f"exec-{uuid.uuid4().hex[:12]}",
            status=AgentStatus.COMPLETED,
            structured_result={
                "demo_id": demo.id,
                "access_url": "https://marketplace.adople.ai/",
                "expires_at": expires_at,
                "walkthrough_script": walkthrough_script,
            },
            artifact_references=[
                ArtifactReference(
                    artifact_id=demo.id,
                    artifact_type="demo_artifact",
                    summary="Validated synthetic demo environment",
                )
            ],
            uncertainty=0.05,
            proposed_next_actions=["attach_demo_to_outreach", "notify_sales_owner"],
        )

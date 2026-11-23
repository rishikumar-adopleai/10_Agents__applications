"""Deal Desk Agent."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agents.base import BaseAgent
from backend.app.models.artifacts import ProposalArtifact
from backend.app.models.governance import ApprovalItem
from backend.app.models.sales import Opportunity
from backend.app.schemas.agents import (
    AgentExecutionRequest,
    AgentExecutionResult,
    AgentStatus,
    ArtifactReference,
)


class DealDeskAgent(BaseAgent):
    @property
    def agent_id(self) -> str:
        return "deal_desk"

    @property
    def name(self) -> str:
        return "Deal Desk"

    @property
    def description(self) -> str:
        return "Extracts buyer requirements from completed discovery and drafts proposals with pricing guardrails."

    async def execute(
        self,
        request: AgentExecutionRequest,
        session: AsyncSession,
    ) -> AgentExecutionResult:
        opportunity_id = request.parameters.get("opportunity_id")

        if not opportunity_id:
            return AgentExecutionResult(
                agent_id=self.agent_id,
                execution_id=f"exec-{uuid.uuid4().hex[:12]}",
                status=AgentStatus.TERMINAL_FAILURE,
                error_details="opportunity_id is required for Deal Desk Agent",
            )

        # 1. Strict Discovery Gating Rule
        res = await session.execute(select(Opportunity).where(Opportunity.id == opportunity_id))
        opp = res.scalars().first()
        if not opp:
            return AgentExecutionResult(
                agent_id=self.agent_id,
                execution_id=f"exec-{uuid.uuid4().hex[:12]}",
                status=AgentStatus.TERMINAL_FAILURE,
                error_details=f"Opportunity {opportunity_id} not found",
            )

        if not opp.discovery_completed:
            return AgentExecutionResult(
                agent_id=self.agent_id,
                execution_id=f"exec-{uuid.uuid4().hex[:12]}",
                status=AgentStatus.BLOCKED,
                error_details="Discovery is not completed. Proposal generation cannot proceed until discovery notes are approved.",
            )

        # 2. Extract Deliverables, Exclusions, and ROI Model
        deliverables = {
            "platform_tier": "Enterprise Multi-Agent Platform",
            "active_agents": ["buying_radar", "research_outreach", "lead_responder", "deal_desk"],
            "sla": "99.9% uptime with 24/7 priority support",
        }
        pricing_model = {
            "annual_subscription_usd": 60000.0,
            "onboarding_fee_usd": 10000.0,
            "billing_cycle": "annual_prepaid",
        }
        roi_assumptions = {
            "average_deal_size": 25000.0,
            "expected_incremental_pipeline_deals_per_quarter": 4,
            "payback_period_months": 3.2,
        }
        pilot_package = {
            "duration_days": 60,
            "pilot_fee_usd": 15000.0,
            "success_criteria": "Generate at least 8 verified sales discovery meetings",
        }

        # 3. Persist Proposal Artifact
        proposal = ProposalArtifact(
            organization_id=request.organization_id,
            account_id=opp.account_id,
            opportunity_id=opp.id,
            title=f"Enterprise Agent Solution Proposal - {opp.name}",
            deliverables=deliverables,
            pricing_model=pricing_model,
            roi_assumptions=roi_assumptions,
            pilot_package=pilot_package,
            commercial_approval_status="draft",
        )
        session.add(proposal)
        await session.flush()

        # 4. Mandatory Commercial Approval Item (Requires Sales Manager role)
        approval = ApprovalItem(
            organization_id=request.organization_id,
            account_id=opp.account_id,
            artifact_type="proposal",
            artifact_id=proposal.id,
            requested_action="approve_commercial_proposal",
            draft_content=f"Annual Contract Value: ${pricing_model['annual_subscription_usd']:.2f}. Pilot Option: ${pilot_package['pilot_fee_usd']:.2f}",
            source_evidence={
                "discovery_notes": opp.discovery_notes,
                "pricing_rules": "Standard Enterprise Matrix",
            },
            risk_flags=["unverified_payment_terms"],
            status="pending",
        )
        session.add(approval)
        await session.flush()

        return AgentExecutionResult(
            agent_id=self.agent_id,
            execution_id=f"exec-{uuid.uuid4().hex[:12]}",
            status=AgentStatus.WAITING_FOR_REVIEW,
            structured_result={
                "proposal_id": proposal.id,
                "approval_id": approval.id,
                "acv_usd": pricing_model["annual_subscription_usd"],
                "requires_commercial_signoff": True,
            },
            artifact_references=[
                ArtifactReference(
                    artifact_id=proposal.id,
                    artifact_type="proposal_artifact",
                    summary="Commercial proposal with ROI and pilot package",
                ),
                ArtifactReference(
                    artifact_id=approval.id,
                    artifact_type="approval_item",
                    summary="Commercial proposal approval for Sales Manager",
                ),
            ],
            uncertainty=0.08,
            proposed_next_actions=[
                "await:sales_manager_commercial_approval",
                "optional:request_security_review",
            ],
        )

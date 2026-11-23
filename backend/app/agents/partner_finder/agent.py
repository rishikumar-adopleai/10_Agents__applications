"""Partner Finder Agent."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agents.base import BaseAgent
from backend.app.models.governance import ApprovalItem
from backend.app.models.sales import Partner
from backend.app.schemas.agents import (
    AgentExecutionRequest,
    AgentExecutionResult,
    AgentStatus,
    ArtifactReference,
)


class PartnerFinderAgent(BaseAgent):
    @property
    def agent_id(self) -> str:
        return "partner_finder"

    @property
    def name(self) -> str:
        return "Partner Finder"

    @property
    def description(self) -> str:
        return "Discovers prospective channel and solution partners and prepares tailored partner enablement kits."

    async def execute(
        self,
        request: AgentExecutionRequest,
        session: AsyncSession,
    ) -> AgentExecutionResult:
        firm_name = request.parameters.get("firm_name", "Global Cloud Solutions LLC")
        partner_type = request.parameters.get("partner_type", "referral")
        contact_email = request.parameters.get("contact_email", "alliances@globalcloud.example.com")

        # Deduplicate Partner
        res = await session.execute(
            select(Partner).where(
                Partner.firm_name == firm_name.strip(),
                Partner.organization_id == request.organization_id,
            )
        )
        partner = res.scalars().first()
        if not partner:
            partner = Partner(
                organization_id=request.organization_id,
                firm_name=firm_name.strip(),
                partner_type=partner_type,
                tier="prospective",
                agreement_status="pending",
                contact_email=contact_email.lower().strip(),
            )
            session.add(partner)
            await session.flush()

        pitch_draft = (
            f"Dear Partner Alliances Team at {firm_name},\n\n"
            f"We have identified strong synergy between your enterprise cloud consulting practice "
            f"and our autonomous Sales Agent Platform. We offer our certified partners a 20% recurring "
            f"referral share and complete pre-configured enablement kits.\n\n"
            f"Would you be open to an introductory discussion with our Partner Director this Thursday?"
        )

        approval = ApprovalItem(
            organization_id=request.organization_id,
            account_id=partner.id,
            artifact_type="partner_pitch",
            artifact_id=partner.id,
            requested_action="send_partner_pitch_email",
            draft_content=pitch_draft,
            source_evidence={"partner_firm": firm_name, "model": partner_type},
            risk_flags=[],
            status="pending",
        )
        session.add(approval)
        await session.flush()

        return AgentExecutionResult(
            agent_id=self.agent_id,
            execution_id=f"exec-{uuid.uuid4().hex[:12]}",
            status=AgentStatus.WAITING_FOR_REVIEW,
            structured_result={
                "partner_id": partner.id,
                "approval_id": approval.id,
                "pitch_draft": pitch_draft,
                "partner_tier": partner.tier,
            },
            artifact_references=[
                ArtifactReference(
                    artifact_id=approval.id,
                    artifact_type="approval_item",
                    summary="Partner outreach pitch awaiting Partner Manager review",
                )
            ],
            uncertainty=0.08,
            proposed_next_actions=[
                "await:partner_manager_review",
                "route_referred_leads_to_lead_responder",
            ],
        )

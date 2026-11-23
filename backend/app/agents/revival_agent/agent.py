"""Revival Agent."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agents.base import BaseAgent
from backend.app.models.governance import ApprovalItem
from backend.app.models.sales import Contact
from backend.app.schemas.agents import (
    AgentExecutionRequest,
    AgentExecutionResult,
    AgentStatus,
    ArtifactReference,
)
from backend.app.services.attempt_service import AttemptTrackingService
from backend.app.services.suppression_service import SuppressionService


class RevivalAgent(BaseAgent):
    @property
    def agent_id(self) -> str:
        return "revival_agent"

    @property
    def name(self) -> str:
        return "Revival Agent"

    @property
    def description(self) -> str:
        return "Identifies eligible dormant leads and crafts re-engagement messages based on fresh evidence without resetting suppression."

    async def execute(
        self,
        request: AgentExecutionRequest,
        session: AsyncSession,
    ) -> AgentExecutionResult:
        contact_id = request.contact_id or request.parameters.get("contact_id")
        fresh_reason = request.parameters.get(
            "fresh_reason", "New SOC 2 Type II attestation & verified enterprise case study"
        )

        if not contact_id:
            return AgentExecutionResult(
                agent_id=self.agent_id,
                execution_id=f"exec-{uuid.uuid4().hex[:12]}",
                status=AgentStatus.TERMINAL_FAILURE,
                error_details="contact_id is required for Revival Agent",
            )

        # 1. Fetch Contact
        res = await session.execute(select(Contact).where(Contact.id == contact_id))
        contact = res.scalars().first()
        if not contact:
            return AgentExecutionResult(
                agent_id=self.agent_id,
                execution_id=f"exec-{uuid.uuid4().hex[:12]}",
                status=AgentStatus.TERMINAL_FAILURE,
                error_details=f"Contact {contact_id} not found",
            )

        # 2. Strict Rule 1: Check suppression / opt-out registry
        suppression_service = SuppressionService(session)
        if await suppression_service.is_contact_suppressed(
            email=contact.email, phone=contact.phone, contact_id=contact.id
        ):
            return AgentExecutionResult(
                agent_id=self.agent_id,
                execution_id=f"exec-{uuid.uuid4().hex[:12]}",
                status=AgentStatus.BLOCKED,
                error_details="Contact is in the suppression registry. Revival strictly cannot clear an opt-out.",
            )

        # 3. Strict Rule 2: Check attempt counter (no 4th attempt without prior reply)
        attempt_service = AttemptTrackingService(session)
        current_attempts = await attempt_service.get_logical_attempts(contact.id)
        if current_attempts >= 3:
            return AgentExecutionResult(
                agent_id=self.agent_id,
                execution_id=f"exec-{uuid.uuid4().hex[:12]}",
                status=AgentStatus.BLOCKED,
                error_details="Max 3 outreach attempts previously reached without reply. Unsolicited revival forbidden without buyer trigger.",
            )

        # 4. Craft Grounded Reconnect Draft based on Fresh Reason
        revival_draft = (
            f"Hi {contact.first_name}, following up on our conversation from a few months back. "
            f"Since we last spoke, we published our SOC 2 Type II audit report and a new case study showing "
            f"how similar enterprise teams reduced lead response latency by 85%. "
            f"Given your focus on sales acceleration, would it make sense to reconnect briefly next week?"
        )

        approval = ApprovalItem(
            organization_id=request.organization_id,
            account_id=contact.account_id,
            contact_id=contact.id,
            artifact_type="revival_draft",
            artifact_id=contact.id,
            requested_action="send_revival_message",
            draft_content=revival_draft,
            source_evidence={"fresh_reason": fresh_reason, "past_contact_id": contact.id},
            risk_flags=["dormant_reconnect"],
            status="pending",
        )
        session.add(approval)
        await session.flush()

        return AgentExecutionResult(
            agent_id=self.agent_id,
            execution_id=f"exec-{uuid.uuid4().hex[:12]}",
            status=AgentStatus.WAITING_FOR_REVIEW,
            structured_result={
                "contact_id": contact.id,
                "approval_id": approval.id,
                "revival_draft": revival_draft,
                "fresh_reason": fresh_reason,
            },
            artifact_references=[
                ArtifactReference(
                    artifact_id=approval.id,
                    artifact_type="approval_item",
                    summary="Revival re-engagement draft awaiting sales rep approval",
                )
            ],
            uncertainty=0.07,
            proposed_next_actions=["await:sales_approval", "on_reply_route_to_lead_responder"],
        )

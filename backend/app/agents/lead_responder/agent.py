"""24/7 Lead Responder Agent.

Conforms to Pipeline 4 Specification:
Orchestrates the 5 internal processing nodes via Pipeline4Engine:
Node 1: Ingest
Node 2: Customer Context
Node 3: Safety + Sentiment
Node 4: Memory
Node 5: Intent + Action + Draft
"""

import uuid
from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agents.base import BaseAgent
from backend.app.schemas.agents import (
    AgentExecutionRequest,
    AgentExecutionResult,
    AgentStatus,
    ArtifactReference,
)
from backend.app.services.pipeline4_engine import Pipeline4Engine


class LeadResponderAgent(BaseAgent):
    @property
    def agent_id(self) -> str:
        return "lead_responder"

    @property
    def name(self) -> str:
        return "24/7 Lead Responder"

    @property
    def description(self) -> str:
        return "24/7 Lead Responder: receives inquiries, enforces safety/sentiment, checks calendar & demos, and orchestrates actions."

    async def execute(
        self,
        request: AgentExecutionRequest,
        session: AsyncSession,
    ) -> AgentExecutionResult:
        sender = request.parameters.get("sender") or request.contact_id or "prospect@example.com"
        recipient = request.parameters.get("recipient") or "sales@adople.ai"
        body = request.parameters.get("body") or request.parameters.get("message_body") or ""
        channel = request.parameters.get("channel", "sms")
        provider = request.parameters.get("provider", "webhook")
        provider_msg_id = request.parameters.get("message_id")
        auto_dispatch = request.parameters.get("auto_dispatch", False)

        engine = Pipeline4Engine(session)
        result: Dict[str, Any] = await engine.process_inbound_message(
            sender=sender,
            recipient=recipient,
            body=body,
            channel=channel,
            provider=provider,
            provider_message_id=provider_msg_id,
            organization_id=request.organization_id,
            auto_dispatch=auto_dispatch,
        )

        exec_id = f"exec-{uuid.uuid4().hex[:12]}"

        if result.get("status") == "blocked_safety":
            return AgentExecutionResult(
                agent_id=self.agent_id,
                execution_id=exec_id,
                status=AgentStatus.BLOCKED,
                structured_result=result,
                error_details=f"Blocked by safety check: {result.get('reason')}",
            )

        if result.get("status") == "duplicate_ignored":
            return AgentExecutionResult(
                agent_id=self.agent_id,
                execution_id=exec_id,
                status=AgentStatus.SUCCESS,
                structured_result=result,
            )

        appr_id = result.get("approval_id")
        artifact_refs = []
        if appr_id:
            artifact_refs.append(
                ArtifactReference(
                    artifact_id=appr_id,
                    artifact_type="approval_item",
                    summary="Lead reply draft awaiting human review or confirmation",
                )
            )

        status = AgentStatus.WAITING_FOR_REVIEW if result.get("approval_status") == "pending" else AgentStatus.SUCCESS

        return AgentExecutionResult(
            agent_id=self.agent_id,
            execution_id=exec_id,
            status=status,
            structured_result=result,
            artifact_references=artifact_refs,
            uncertainty=0.05,
            proposed_next_actions=[result.get("node5", {}).get("proposed_next_action", "await_customer_reply")],
        )

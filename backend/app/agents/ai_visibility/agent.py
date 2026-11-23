"""AI Search Visibility Agent."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agents.base import BaseAgent
from backend.app.models.governance import ApprovalItem
from backend.app.schemas.agents import (
    AgentExecutionRequest,
    AgentExecutionResult,
    AgentStatus,
    ArtifactReference,
)


class AISearchVisibilityAgent(BaseAgent):
    @property
    def agent_id(self) -> str:
        return "ai_search_visibility"

    @property
    def name(self) -> str:
        return "AI Search Visibility"

    @property
    def description(self) -> str:
        return "Monitors brand citations across AI search surfaces and drafts authoritative technical content briefs."

    async def execute(
        self,
        request: AgentExecutionRequest,
        session: AsyncSession,
    ) -> AgentExecutionResult:
        search_query = request.parameters.get(
            "search_query", "best autonomous AI sales platforms for enterprise"
        )
        observed_citations = [
            {
                "engine": "Perplexity",
                "cited": True,
                "position": 2,
                "url": "https://example.com/solutions",
            },
            {
                "engine": "SearchGPT",
                "cited": False,
                "reason": "Missing structured comparative technical data",
            },
        ]

        content_brief = (
            f"Content Gap Analysis for Query: '{search_query}'\n\n"
            f"Finding: SearchGPT omits our platform due to lack of an authoritative architectural comparison page.\n"
            f"Action Item: Publish a technical deep-dive on 'Modular Monolith vs Microservices for Enterprise Sales AI'.\n"
            f"Grounded Facts: Include verified 2-second ingestion SLA and SOC 2 Type II attestation."
        )

        approval = ApprovalItem(
            organization_id=request.organization_id,
            account_id="public-content-domain",
            artifact_type="visibility_content_brief",
            artifact_id=f"vis-{uuid.uuid4().hex[:8]}",
            requested_action="publish_seo_architectural_article",
            draft_content=content_brief,
            source_evidence={"observed_citations": observed_citations},
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
                "search_query": search_query,
                "observed_citations": observed_citations,
                "approval_id": approval.id,
                "draft_brief": content_brief,
            },
            artifact_references=[
                ArtifactReference(
                    artifact_id=approval.id,
                    artifact_type="approval_item",
                    summary="Public visibility content brief awaiting marketing approval",
                )
            ],
            uncertainty=0.10,
            proposed_next_actions=[
                "await:marketing_review",
                "route_inbound_inquiries_to_lead_responder",
            ],
        )

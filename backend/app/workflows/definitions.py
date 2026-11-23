"""Ten Business Workflows Conforming to the Implementation Plan."""

from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agents.orchestrator import AgentOrchestrator
from backend.app.models.execution import WorkflowRun
from backend.app.schemas.agents import AgentExecutionRequest, AgentStatus
from backend.app.workflows.engine import WorkflowEngine


class PlatformWorkflows:
    """Implementations of the 10 initial platform business workflows."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.engine = WorkflowEngine(session)
        self.orchestrator = AgentOrchestrator(session)

    # 1. Account Acquisition Workflow
    async def run_account_acquisition(
        self,
        organization_id: str,
        domain: str,
        company_name: str,
    ) -> WorkflowRun:
        run = await self.engine.start_workflow(
            workflow_name="AccountAcquisitionWorkflow",
            organization_id=organization_id,
            initial_state={"domain": domain, "company_name": company_name},
        )
        req = AgentExecutionRequest(
            agent_id="buying_signal_radar",
            organization_id=organization_id,
            correlation_id=run.correlation_id,
            parameters={"domain": domain, "company_name": company_name},
        )
        result = await self.orchestrator.execute_agent(req)
        status = "completed" if result.status == AgentStatus.COMPLETED else "failed"
        return await self.engine.advance_step(
            workflow_run_id=run.id,
            next_step="buying_signal_analyzed",
            state_updates={"result": result.structured_result},
            status=status,
        )

    # 2. Research & Outreach Workflow
    async def run_research_outreach(
        self,
        organization_id: str,
        account_id: str,
        contact_id: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        task_id: Optional[str] = None,
        execution_id: Optional[str] = None,
    ) -> WorkflowRun:
        initial_params = parameters or {}
        corr_id = correlation_id or f"wf-research-{account_id}"

        # Check for existing workflow run with this correlation_id to prevent duplicate runs
        existing_run = await self.engine.repo.get_by_correlation_id(corr_id)
        if existing_run:
            if existing_run.status in ("completed", "waiting_for_approval"):
                return existing_run
            # If previous attempt failed, reset status to running and re-execute
            existing_run.status = "running"
            existing_run.error = None
            run = existing_run
        else:
            run = await self.engine.start_workflow(
                workflow_name="ResearchOutreachWorkflow",
                organization_id=organization_id,
                initial_state={"account_id": account_id, "contact_id": contact_id, **initial_params},
                correlation_id=corr_id,
            )
        req = AgentExecutionRequest(
            agent_id="research_personal_outreach",
            organization_id=organization_id,
            account_id=account_id,
            contact_id=contact_id,
            correlation_id=run.correlation_id,
            parameters=initial_params,
            task_id=task_id,
            execution_id=execution_id,
        )
        result = await self.orchestrator.execute_agent(req)

        # Map agent execution status to workflow progression step
        if result.status == AgentStatus.WAITING_FOR_REVIEW:
            next_step = "awaiting_sales_approval"
            wf_status = "waiting_for_approval"
        elif result.status == AgentStatus.WAITING_FOR_INPUT:
            next_step = "waiting_for_contact_info"
            wf_status = "waiting_for_input"
        elif result.status == AgentStatus.BLOCKED:
            next_step = "blocked_eligibility"
            wf_status = "blocked"
        elif result.status == AgentStatus.COMPLETED:
            next_step = "completed"
            wf_status = "completed"
        elif result.status == AgentStatus.RETRYABLE_FAILURE:
            next_step = "failed_retryable"
            wf_status = "failed"
        else:
            next_step = "failed_manual_intervention"
            wf_status = "failed"

        err_msg = result.error_details if wf_status == "failed" else None
        return await self.engine.advance_step(
            workflow_run_id=run.id,
            next_step=next_step,
            state_updates={"result": result.structured_result, "agent_status": result.status.value},
            status=wf_status,
            error=err_msg,
        )

    async def run_pipeline2_batch(
        self,
        organization_id: str,
        account_ids: Optional[List[str]] = None,
        use_sample_data: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Execute Pipeline 2 across multiple companies independently.
        Ensures one company's validation or processing failure does not halt others.
        """
        if not account_ids:
            from backend.app.agents.research_outreach.sample_loader import SampleDataLoader
            loader = SampleDataLoader()
            accounts = loader.get_all_sample_accounts()
            account_ids = [a["account_id"] for a in accounts]

        results = []
        for acc_id in account_ids:
            try:
                run = await self.run_research_outreach(
                    organization_id=organization_id,
                    account_id=acc_id,
                    parameters={"use_sample_data": use_sample_data},
                )
                results.append({
                    "account_id": acc_id,
                    "workflow_run_id": run.id,
                    "status": run.status,
                    "current_step": run.current_step,
                    "result": run.state_data.get("result", {}),
                    "success": True,
                })
            except Exception as e:
                results.append({
                    "account_id": acc_id,
                    "workflow_run_id": None,
                    "status": "failed",
                    "error": str(e),
                    "success": False,
                })
        return results

    # 3. Demo Request Workflow
    async def run_demo_request(
        self,
        organization_id: str,
        account_id: str,
    ) -> WorkflowRun:
        run = await self.engine.start_workflow(
            workflow_name="DemoRequestWorkflow",
            organization_id=organization_id,
            initial_state={"account_id": account_id},
        )
        req = AgentExecutionRequest(
            agent_id="demo_before_hello",
            organization_id=organization_id,
            account_id=account_id,
            correlation_id=run.correlation_id,
        )
        result = await self.orchestrator.execute_agent(req)
        return await self.engine.advance_step(
            workflow_run_id=run.id,
            next_step="demo_ready",
            state_updates={"result": result.structured_result},
            status="completed",
        )

    # 4. Inbound Response Workflow
    async def run_inbound_response(
        self,
        organization_id: str,
        conversation_id: str,
        contact_id: str,
        message_body: str,
    ) -> WorkflowRun:
        run = await self.engine.start_workflow(
            workflow_name="InboundResponseWorkflow",
            organization_id=organization_id,
            initial_state={"conversation_id": conversation_id, "contact_id": contact_id},
        )
        req = AgentExecutionRequest(
            agent_id="lead_responder",
            organization_id=organization_id,
            contact_id=contact_id,
            correlation_id=run.correlation_id,
            parameters={
                "conversation_id": conversation_id,
                "body": message_body,
                "contact_id": contact_id,
            },
        )
        result = await self.orchestrator.execute_agent(req)
        return await self.engine.advance_step(
            workflow_run_id=run.id,
            next_step="reply_awaiting_approval",
            state_updates={"result": result.structured_result},
            status="waiting_for_approval",
        )

    # 5. Meeting and Discovery Workflow
    async def run_meeting_discovery(
        self,
        organization_id: str,
        opportunity_id: str,
        notes: str,
    ) -> WorkflowRun:
        run = await self.engine.start_workflow(
            workflow_name="MeetingDiscoveryWorkflow",
            organization_id=organization_id,
            initial_state={"opportunity_id": opportunity_id},
        )
        from sqlalchemy import update

        from backend.app.models.sales import Opportunity

        stmt = (
            update(Opportunity)
            .where(Opportunity.id == opportunity_id)
            .values(discovery_completed=True, discovery_notes=notes, stage="discovery")
        )
        await self.session.execute(stmt)
        return await self.engine.advance_step(
            workflow_run_id=run.id,
            next_step="discovery_verified",
            state_updates={"discovery_completed": True, "notes": notes},
            status="completed",
        )

    # 6. Deal Proposal Workflow (Gated by discovery.completed)
    async def run_deal_proposal(
        self,
        organization_id: str,
        opportunity_id: str,
    ) -> WorkflowRun:
        run = await self.engine.start_workflow(
            workflow_name="DealProposalWorkflow",
            organization_id=organization_id,
            initial_state={"opportunity_id": opportunity_id},
        )
        req = AgentExecutionRequest(
            agent_id="deal_desk",
            organization_id=organization_id,
            correlation_id=run.correlation_id,
            parameters={"opportunity_id": opportunity_id},
        )
        result = await self.orchestrator.execute_agent(req)
        return await self.engine.advance_step(
            workflow_run_id=run.id,
            next_step="proposal_awaiting_commercial_approval",
            state_updates={"result": result.structured_result},
            status="waiting_for_approval"
            if result.status == AgentStatus.WAITING_FOR_REVIEW
            else "failed",
        )

    # 7. Security Review Workflow
    async def run_security_review(
        self,
        organization_id: str,
        account_id: str,
    ) -> WorkflowRun:
        run = await self.engine.start_workflow(
            workflow_name="SecurityReviewWorkflow",
            organization_id=organization_id,
            initial_state={"account_id": account_id},
        )
        req = AgentExecutionRequest(
            agent_id="trust_security_desk",
            organization_id=organization_id,
            account_id=account_id,
            correlation_id=run.correlation_id,
        )
        result = await self.orchestrator.execute_agent(req)
        return await self.engine.advance_step(
            workflow_run_id=run.id,
            next_step="questionnaire_awaiting_security_attestation",
            state_updates={"result": result.structured_result},
            status="waiting_for_approval",
        )

    # 8. Proof Creation Workflow (Gated by delivery verification)
    async def run_proof_creation(
        self,
        organization_id: str,
        account_id: str,
        delivery_verified: bool = True,
    ) -> WorkflowRun:
        run = await self.engine.start_workflow(
            workflow_name="ProofCreationWorkflow",
            organization_id=organization_id,
            initial_state={"account_id": account_id, "delivery_verified": delivery_verified},
        )
        req = AgentExecutionRequest(
            agent_id="proof_engine",
            organization_id=organization_id,
            account_id=account_id,
            correlation_id=run.correlation_id,
            parameters={"delivery_verified": delivery_verified},
        )
        result = await self.orchestrator.execute_agent(req)
        return await self.engine.advance_step(
            workflow_run_id=run.id,
            next_step="proof_awaiting_publication_approval",
            state_updates={"result": result.structured_result},
            status="waiting_for_approval"
            if result.status == AgentStatus.WAITING_FOR_REVIEW
            else "blocked",
        )

    # 9. Partner Acquisition Workflow
    async def run_partner_acquisition(
        self,
        organization_id: str,
        firm_name: str,
        partner_type: str = "referral",
    ) -> WorkflowRun:
        run = await self.engine.start_workflow(
            workflow_name="PartnerAcquisitionWorkflow",
            organization_id=organization_id,
            initial_state={"firm_name": firm_name},
        )
        req = AgentExecutionRequest(
            agent_id="partner_finder",
            organization_id=organization_id,
            correlation_id=run.correlation_id,
            parameters={"firm_name": firm_name, "partner_type": partner_type},
        )
        result = await self.orchestrator.execute_agent(req)
        return await self.engine.advance_step(
            workflow_run_id=run.id,
            next_step="pitch_awaiting_partner_manager_approval",
            state_updates={"result": result.structured_result},
            status="waiting_for_approval",
        )

    # 10. Revival Workflow
    async def run_revival(
        self,
        organization_id: str,
        contact_id: str,
    ) -> WorkflowRun:
        run = await self.engine.start_workflow(
            workflow_name="RevivalWorkflow",
            organization_id=organization_id,
            initial_state={"contact_id": contact_id},
        )
        req = AgentExecutionRequest(
            agent_id="revival_agent",
            organization_id=organization_id,
            contact_id=contact_id,
            correlation_id=run.correlation_id,
        )
        result = await self.orchestrator.execute_agent(req)
        return await self.engine.advance_step(
            workflow_run_id=run.id,
            next_step="reconnect_draft_awaiting_approval",
            state_updates={"result": result.structured_result},
            status="waiting_for_approval"
            if result.status == AgentStatus.WAITING_FOR_REVIEW
            else "blocked",
        )

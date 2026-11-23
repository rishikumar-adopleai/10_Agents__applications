"""Workflow Management and Trigger Endpoints."""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user
from backend.app.core.rbac import CurrentUser
from backend.app.db.session import get_db
from backend.app.repositories.execution_repo import WorkflowRunRepository
from backend.app.schemas.common import StandardResponse
from backend.app.workflows.definitions import PlatformWorkflows

router = APIRouter(prefix="/workflows", tags=["workflows"])


class StartWorkflowRequest(BaseModel):
    workflow_name: str
    parameters: Dict[str, Any]


@router.get("", response_model=StandardResponse[List[dict]])
async def list_workflow_runs(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    repo = WorkflowRunRepository(session)
    runs = await repo.list(organization_id=current_user.organization_id, limit=50)
    data = [
        {
            "id": r.id,
            "workflow_name": r.workflow_name,
            "correlation_id": r.correlation_id,
            "status": r.status,
            "current_step": r.current_step,
            "created_at": r.created_at.isoformat(),
        }
        for r in runs
    ]
    return StandardResponse(data=data)


@router.post("/start", response_model=StandardResponse[dict])
async def start_workflow(
    req: StartWorkflowRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    workflows = PlatformWorkflows(session)
    p = req.parameters
    org_id = current_user.organization_id

    run = None
    if req.workflow_name == "AccountAcquisitionWorkflow":
        run = await workflows.run_account_acquisition(
            org_id,
            p.get("domain", "acme-corp.com"),
            p.get("company_name", "Acme Corporation"),
        )
    elif req.workflow_name == "ResearchOutreachWorkflow":
        run = await workflows.run_research_outreach(
            org_id,
            p.get("account_id", "ACC-001"),
            p.get("contact_id"),
            parameters=p,
        )
    elif req.workflow_name == "DemoRequestWorkflow":
        run = await workflows.run_demo_request(org_id, p.get("account_id", "test-acc-id"))
    elif req.workflow_name == "InboundResponseWorkflow":
        run = await workflows.run_inbound_response(
            org_id,
            p.get("conversation_id", "test-conv-id"),
            p.get("contact_id", "test-contact-id"),
            p.get("message_body", "Can we schedule a call?"),
        )
    elif req.workflow_name == "DealProposalWorkflow":
        run = await workflows.run_deal_proposal(org_id, p.get("opportunity_id", "test-opp-id"))
    elif req.workflow_name == "SecurityReviewWorkflow":
        run = await workflows.run_security_review(org_id, p.get("account_id", "test-acc-id"))
    elif req.workflow_name == "ProofCreationWorkflow":
        run = await workflows.run_proof_creation(
            org_id, p.get("account_id", "test-acc-id"), delivery_verified=True
        )
    elif req.workflow_name == "PartnerAcquisitionWorkflow":
        run = await workflows.run_partner_acquisition(org_id, p.get("firm_name", "Partner Firm"))
    elif req.workflow_name == "RevivalWorkflow":
        run = await workflows.run_revival(org_id, p.get("contact_id", "test-contact-id"))
    else:
        from backend.app.core.exceptions import ValidationError

        raise ValidationError(f"Unknown workflow '{req.workflow_name}'")

    return StandardResponse(
        data={"workflow_run_id": run.id, "status": run.status, "current_step": run.current_step},
        message=f"Workflow '{req.workflow_name}' started successfully",
    )

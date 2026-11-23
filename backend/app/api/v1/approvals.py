"""Approval Center API Endpoints."""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user
from backend.app.core.rbac import CurrentUser
from backend.app.db.session import get_db
from backend.app.schemas.common import StandardResponse
from backend.app.schemas.governance import ApprovalDecisionRequest, ApprovalItemResponse
from backend.app.services.approval_service import ApprovalService

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("", response_model=StandardResponse[List[ApprovalItemResponse]])
async def list_pending_approvals(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Retrieve all pending approval items for human review in the caller's organization."""
    service = ApprovalService(session)
    items = await service.list_pending_approvals(organization_id=current_user.organization_id)
    return StandardResponse(data=[ApprovalItemResponse.model_validate(i) for i in items])


@router.post("/{approval_id}/decision", response_model=StandardResponse[ApprovalItemResponse])
async def submit_approval_decision(
    approval_id: str,
    decision_in: ApprovalDecisionRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Submit reviewer decision (approve, edit and approve, reject, etc.) on an artifact."""
    service = ApprovalService(session)
    updated_item = await service.process_decision(
        approval_id=approval_id,
        decision=decision_in.decision,
        current_user=current_user,
        edited_content=decision_in.edited_content,
        feedback=decision_in.feedback,
    )
    return StandardResponse(
        data=ApprovalItemResponse.model_validate(updated_item),
        message=f"Approval decision '{decision_in.decision}' processed successfully",
    )

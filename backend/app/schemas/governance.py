"""Governance and Approval Center Schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ApprovalItemResponse(BaseModel):
    id: str
    organization_id: str
    account_id: str
    contact_id: Optional[str] = None
    artifact_type: str
    artifact_id: str
    artifact_version: str
    requested_action: str
    draft_content: str
    source_evidence: Dict[str, Any]
    risk_flags: List[str]
    status: str
    reviewed_by_user_id: Optional[str] = None
    review_feedback: Optional[str] = None
    due_at: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ApprovalDecisionRequest(BaseModel):
    decision: str = Field(
        description="approved | edited_approved | rejected | revision_requested | taken_over"
    )
    edited_content: Optional[str] = None
    feedback: Optional[str] = None

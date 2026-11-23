"""Governance, Approval Center and Audit Trail Models."""

from typing import Optional

from sqlalchemy import JSON, Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import BaseModel, OrganizationScopedMixin


class ApprovalItem(BaseModel, OrganizationScopedMixin):
    """Centralized review request item for human approval."""

    __tablename__ = "approval_items"

    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contact_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    artifact_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # outreach_draft, lead_reply, proposal, security_answer, proof_case_study, revival_draft
    artifact_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    artifact_version: Mapped[int] = mapped_column(String(20), default="1", nullable=False)

    requested_action: Mapped[str] = mapped_column(String(100), nullable=False)
    draft_content: Mapped[str] = mapped_column(Text, nullable=False)
    source_evidence: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    risk_flags: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)

    # Status: pending, approved, edited_approved, rejected, revision_requested, taken_over, expired
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False, index=True)

    reviewed_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    review_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    due_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)


class ClientPermission(BaseModel, OrganizationScopedMixin):
    """Explicit recorded client permission for case study and proof reuse."""

    __tablename__ = "client_permissions"

    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    client_contact_name: Mapped[str] = mapped_column(String(100), nullable=False)
    logo_permitted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    quotes_permitted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metrics_permitted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allowed_audiences: Mapped[dict] = mapped_column(
        JSON, default=list, nullable=False
    )  # public, sales_only, partners
    granted_at: Mapped[str] = mapped_column(String(50), nullable=False)
    expires_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)


class PolicyVersion(BaseModel, OrganizationScopedMixin):
    """Active operating policy rules version."""

    __tablename__ = "policy_versions"

    policy_name: Mapped[str] = mapped_column(String(100), nullable=False)
    rules_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AuditEvent(BaseModel, OrganizationScopedMixin):
    """Immutable audit trail of all consequential business and agent actions."""

    __tablename__ = "audit_events"

    actor_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    actor_type: Mapped[str] = mapped_column(String(50), nullable=False)  # user, agent, system
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payload_before: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    payload_after: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)


class RetentionAction(BaseModel, OrganizationScopedMixin):
    """Data retention and compliance deletion action."""

    __tablename__ = "retention_actions"

    action_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # purge_expired_demos, delete_contact
    target_entity: Mapped[str] = mapped_column(String(100), nullable=False)
    target_id: Mapped[str] = mapped_column(String(100), nullable=False)
    executed_by: Mapped[str] = mapped_column(String(100), nullable=False)

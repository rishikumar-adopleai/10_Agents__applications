"""Buying-Signal Radar SQLAlchemy Domain Models."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import BaseModel, OrganizationScopedMixin


class IcpProfile(BaseModel, OrganizationScopedMixin):
    """Ideal Customer Profile (ICP) Configuration & Versioning."""

    __tablename__ = "icp_profiles"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="draft", nullable=False, index=True
    )  # draft, approved, active, archived
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    # Detailed criteria: country, industries, subindustries, employee bounds, use cases, etc.
    criteria: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    approved_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class RadarScanRun(BaseModel, OrganizationScopedMixin):
    """Buying-Signal Radar execution scan run audit record."""

    __tablename__ = "radar_scan_runs"

    icp_profile_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("icp_profiles.id", ondelete="SET NULL"), nullable=True
    )
    icp_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="running", nullable=False, index=True
    )  # running, completed, failed, cancelled
    trigger_type: Mapped[str] = mapped_column(
        String(50), default="manual", nullable=False
    )  # manual, scheduled
    total_accounts_evaluated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    icp_matched_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    signals_detected_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    qualified_accounts_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    shortlist_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    scoring_rubric_version: Mapped[str] = mapped_column(
        String(50), default="demo-v1", nullable=False
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class RadarPrioritizedAccount(BaseModel, OrganizationScopedMixin):
    """Daily prioritized shortlist account record with scoring and Agent 4 handoff."""

    __tablename__ = "radar_prioritized_accounts"

    scan_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("radar_scan_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    icp_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    why_now_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    why_now_reason: Mapped[str] = mapped_column(Text, nullable=False)
    primary_signal_type: Mapped[str] = mapped_column(String(100), nullable=False)
    score_breakdown: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    suggested_contact_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
    )
    contact_status: Mapped[str] = mapped_column(
        String(50), default="research_required", nullable=False
    )  # verified_contact, research_required
    agent4_task_status: Mapped[str] = mapped_column(
        String(50), default="pending_research", nullable=False, index=True
    )  # pending_research, handed_off, completed, failed
    agent4_task_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    event_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


class SignalEvidence(BaseModel, OrganizationScopedMixin):
    """Standardized verified evidence record across all 5 buying signals."""

    __tablename__ = "signal_evidences"

    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scan_run_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("radar_scan_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    signal_type: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )  # hiring, growth, regulatory, sec_filing, interest
    signal_subtype: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    observed_fact: Mapped[str] = mapped_column(Text, nullable=False)
    business_hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    source_provider: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # greenhouse, lever, newsapi, company_announcement, cms, federal_register, sec_edgar, hubspot
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    source_record_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    first_observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    last_checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    verification_status: Mapped[str] = mapped_column(
        String(50), default="VERIFIED", nullable=False, index=True
    )  # VERIFIED, NEEDS_REVIEW, UNVERIFIED, STALE, UNAVAILABLE, NOT_APPLICABLE, REJECTED
    evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    raw_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class RegulatoryRule(BaseModel, OrganizationScopedMixin):
    """Official regulatory requirement rules repository."""

    __tablename__ = "regulatory_rules"

    rule_identifier: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )  # CMS-0057-F, CMS-9115-F, etc.
    rule_title: Mapped[str] = mapped_column(String(255), nullable=False)
    issuing_authority: Mapped[str] = mapped_column(String(100), nullable=False)  # CMS, FinCEN, etc.
    official_url: Mapped[str] = mapped_column(String(500), nullable=False)
    requirement_description: Mapped[str] = mapped_column(Text, nullable=False)
    compliance_date: Mapped[str] = mapped_column(String(50), nullable=False)
    applicable_organization_types: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)
    last_reviewed_date: Mapped[str] = mapped_column(String(50), nullable=False)
    verification_status: Mapped[str] = mapped_column(
        String(50), default="VERIFIED", nullable=False
    )


class CsvImportHistory(BaseModel, OrganizationScopedMixin):
    """Audit log of Apollo CSV imports."""

    __tablename__ = "csv_import_histories"

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    imported_accounts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    imported_contacts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicate_accounts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errors_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="completed", nullable=False
    )  # preview, validated, completed, failed
    column_mapping: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    error_log: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)

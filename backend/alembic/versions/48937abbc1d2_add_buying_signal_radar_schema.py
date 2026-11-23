"""Add Buying-Signal Radar schema and extend accounts/contacts

Revision ID: 48937abbc1d2
Revises: 37826f2cbaa3
Create Date: 2026-11-17 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "48937abbc1d2"
down_revision: Union[str, None] = "37826f2cbaa3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Extend Accounts table
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.add_column(sa.Column("country", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("state", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("city", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("annual_revenue", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("apollo_id", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("why_now", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("linkedin_url", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("cik", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("short_description", sa.Text(), nullable=True))
        batch_op.create_index("ix_accounts_apollo_id", ["apollo_id"])
        batch_op.create_index("ix_accounts_cik", ["cik"])

    # 2. Extend Contacts table
    with op.batch_alter_table("contacts") as batch_op:
        batch_op.add_column(sa.Column("linkedin_url", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("apollo_id", sa.String(length=100), nullable=True))
        batch_op.create_index("ix_contacts_apollo_id", ["apollo_id"])

    # 3. ICP Profiles
    op.create_table(
        "icp_profiles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("status", sa.String(length=50), nullable=False, default="draft"),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=False),
        sa.Column("criteria", sa.JSON(), nullable=False),
        sa.Column(
            "approved_by_user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_icp_profiles_org_id", "icp_profiles", ["organization_id"])
    op.create_index("ix_icp_profiles_status", "icp_profiles", ["status"])

    # 4. Radar Scan Runs
    op.create_table(
        "radar_scan_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "icp_profile_id",
            sa.String(length=36),
            sa.ForeignKey("icp_profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("icp_version", sa.Integer(), nullable=False, default=1),
        sa.Column("status", sa.String(length=50), nullable=False, default="running"),
        sa.Column("trigger_type", sa.String(length=50), nullable=False, default="manual"),
        sa.Column("total_accounts_evaluated", sa.Integer(), nullable=False, default=0),
        sa.Column("icp_matched_count", sa.Integer(), nullable=False, default=0),
        sa.Column("signals_detected_count", sa.Integer(), nullable=False, default=0),
        sa.Column("qualified_accounts_count", sa.Integer(), nullable=False, default=0),
        sa.Column("shortlist_size", sa.Integer(), nullable=False, default=0),
        sa.Column("scoring_rubric_version", sa.String(length=50), nullable=False, default="demo-v1"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("summary_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_radar_scan_runs_org_id", "radar_scan_runs", ["organization_id"])
    op.create_index("ix_radar_scan_runs_status", "radar_scan_runs", ["status"])

    # 5. Radar Prioritized Accounts
    op.create_table(
        "radar_prioritized_accounts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "scan_run_id",
            sa.String(length=36),
            sa.ForeignKey("radar_scan_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.String(length=36),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("icp_score", sa.Float(), nullable=False, default=0.0),
        sa.Column("why_now_score", sa.Float(), nullable=False, default=0.0),
        sa.Column("total_score", sa.Float(), nullable=False, default=0.0),
        sa.Column("why_now_reason", sa.Text(), nullable=False),
        sa.Column("primary_signal_type", sa.String(length=100), nullable=False),
        sa.Column("score_breakdown", sa.JSON(), nullable=False),
        sa.Column(
            "suggested_contact_id",
            sa.String(length=36),
            sa.ForeignKey("contacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("contact_status", sa.String(length=50), nullable=False, default="research_required"),
        sa.Column("agent4_task_status", sa.String(length=50), nullable=False, default="pending_research"),
        sa.Column("agent4_task_id", sa.String(length=36), nullable=True),
        sa.Column("event_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_radar_p_accounts_scan_id", "radar_prioritized_accounts", ["scan_run_id"])
    op.create_index("ix_radar_p_accounts_account_id", "radar_prioritized_accounts", ["account_id"])

    # 6. Signal Evidence
    op.create_table(
        "signal_evidences",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.String(length=36),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "scan_run_id",
            sa.String(length=36),
            sa.ForeignKey("radar_scan_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("signal_type", sa.String(length=100), nullable=False),
        sa.Column("signal_subtype", sa.String(length=100), nullable=False),
        sa.Column("observed_fact", sa.Text(), nullable=False),
        sa.Column("business_hypothesis", sa.Text(), nullable=False),
        sa.Column("source_provider", sa.String(length=50), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=False),
        sa.Column("source_record_id", sa.String(length=255), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verification_status", sa.String(length=50), nullable=False, default="VERIFIED"),
        sa.Column("evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, default=1.0),
        sa.Column("raw_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_signal_evidences_account_id", "signal_evidences", ["account_id"])
    op.create_index("ix_signal_evidences_hash", "signal_evidences", ["evidence_hash"])
    op.create_index("ix_signal_evidences_status", "signal_evidences", ["verification_status"])

    # 7. Regulatory Rules
    op.create_table(
        "regulatory_rules",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rule_identifier", sa.String(length=100), nullable=False, unique=True),
        sa.Column("rule_title", sa.String(length=255), nullable=False),
        sa.Column("issuing_authority", sa.String(length=100), nullable=False),
        sa.Column("official_url", sa.String(length=500), nullable=False),
        sa.Column("requirement_description", sa.Text(), nullable=False),
        sa.Column("compliance_date", sa.String(length=50), nullable=False),
        sa.Column("applicable_organization_types", sa.JSON(), nullable=False),
        sa.Column("last_reviewed_date", sa.String(length=50), nullable=False),
        sa.Column("verification_status", sa.String(length=50), nullable=False, default="VERIFIED"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_regulatory_rules_identifier", "regulatory_rules", ["rule_identifier"])

    # 8. CSV Import History
    op.create_table(
        "csv_import_histories",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False, default=0),
        sa.Column("imported_accounts", sa.Integer(), nullable=False, default=0),
        sa.Column("imported_contacts", sa.Integer(), nullable=False, default=0),
        sa.Column("duplicate_accounts", sa.Integer(), nullable=False, default=0),
        sa.Column("errors_count", sa.Integer(), nullable=False, default=0),
        sa.Column("status", sa.String(length=50), nullable=False, default="completed"),
        sa.Column("column_mapping", sa.JSON(), nullable=False),
        sa.Column("error_log", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("csv_import_histories")
    op.drop_table("regulatory_rules")
    op.drop_table("signal_evidences")
    op.drop_table("radar_prioritized_accounts")
    op.drop_table("radar_scan_runs")
    op.drop_table("icp_profiles")
    with op.batch_alter_table("contacts") as batch_op:
        batch_op.drop_column("apollo_id")
        batch_op.drop_column("linkedin_url")
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.drop_column("short_description")
        batch_op.drop_column("cik")
        batch_op.drop_column("linkedin_url")
        batch_op.drop_column("why_now")
        batch_op.drop_column("apollo_id")
        batch_op.drop_column("annual_revenue")
        batch_op.drop_column("city")
        batch_op.drop_column("state")
        batch_op.drop_column("country")

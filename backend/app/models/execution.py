"""Agent Execution, Workflow State and Transactional Outbox Models."""

from typing import Optional

from sqlalchemy import JSON, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import BaseModel, OrganizationScopedMixin


class AgentTask(BaseModel, OrganizationScopedMixin):
    """Execution record for an agent task."""

    __tablename__ = "agent_tasks"

    agent_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    execution_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    workflow_run_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    # Controlled statuses: completed, waiting_for_input, waiting_for_review, blocked, retryable_failure, terminal_failure, cancelled
    status: Mapped[str] = mapped_column(
        String(50), default="waiting_for_input", nullable=False, index=True
    )

    input_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    output_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    uncertainty: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class WorkflowRun(BaseModel, OrganizationScopedMixin):
    """Durable state machine record for multi-step workflows."""

    __tablename__ = "workflow_runs"

    workflow_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    correlation_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(50), default="running", nullable=False, index=True
    )  # running, waiting_for_approval, completed, failed, cancelled
    current_step: Mapped[str] = mapped_column(String(100), nullable=False)
    state_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class DomainEvent(BaseModel, OrganizationScopedMixin):
    """Domain events generated across the platform."""

    __tablename__ = "domain_events"

    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)


class OutboxEvent(BaseModel, OrganizationScopedMixin):
    """Transactional Outbox for reliable event dispatching."""

    __tablename__ = "outbox_events"

    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="pending", nullable=False, index=True
    )  # pending, published, failed
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class IntegrationAttempt(BaseModel, OrganizationScopedMixin):
    """Auditable log of external integration calls."""

    __tablename__ = "integration_attempts"

    provider: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # apollo, hubspot, ghl, sms, microsoft, openai, s3
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # success, failure, rate_limited, timeout
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    request_snippet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_snippet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

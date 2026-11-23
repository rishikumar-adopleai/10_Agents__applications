"""Intelligence, Private Memory and Learning Lifecycle Models."""

from typing import Optional

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import BaseModel, OrganizationScopedMixin


class MemoryFact(BaseModel, OrganizationScopedMixin):
    """Atomic fact learned about a lead or company."""

    __tablename__ = "memory_facts"

    contact_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=True, index=True
    )
    account_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True, index=True
    )
    scope: Mapped[str] = mapped_column(String(50), nullable=False)  # contact, account, deal
    fact_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    fact_value: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    source_span: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class ContactMemory(BaseModel, OrganizationScopedMixin):
    """Scoped private memory for a contact to prevent cross-lead leakage."""

    __tablename__ = "contact_memories"

    contact_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("contacts.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    objections: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    last_included_message_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)


class KnowledgeVersion(BaseModel, OrganizationScopedMixin):
    """Approved enterprise business knowledge facts."""

    __tablename__ = "knowledge_versions"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # product, pricing_rules, case_studies, security_policy
    content: Mapped[Text] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ResponseFeedback(BaseModel, OrganizationScopedMixin):
    """Human corrections and feedback on agent outputs."""

    __tablename__ = "response_feedback"

    agent_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    original_draft: Mapped[str] = mapped_column(Text, nullable=False)
    human_revision: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewer_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    correction_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rating: Mapped[int] = mapped_column(Integer, default=5, nullable=False)


class LearningCandidate(BaseModel, OrganizationScopedMixin):
    """Isolated improvement candidate undergoing held-out evaluation."""

    __tablename__ = "learning_candidates"

    agent_id: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt_candidate: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="candidate", nullable=False
    )  # candidate, evaluated, rejected, released


class EvaluationRun(BaseModel, OrganizationScopedMixin):
    """Evaluation test results on held-out datasets."""

    __tablename__ = "evaluation_runs"

    agent_id: Mapped[str] = mapped_column(String(50), nullable=False)
    dataset_name: Mapped[str] = mapped_column(String(100), nullable=False)
    accuracy_score: Mapped[float] = mapped_column(Float, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    evaluation_report: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class LearningRelease(BaseModel, OrganizationScopedMixin):
    """Immutable versioned prompt and retrieval configuration bundle."""

    __tablename__ = "learning_releases"

    version: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    prompt_bundle: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approved_by_user_id: Mapped[str] = mapped_column(String(36), nullable=False)

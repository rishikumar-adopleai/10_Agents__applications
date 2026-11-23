"""Agent Execution Request and Structured Result Contracts."""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    COMPLETED = "completed"
    WAITING_FOR_INPUT = "waiting_for_input"
    WAITING_FOR_REVIEW = "waiting_for_review"
    BLOCKED = "blocked"
    RETRYABLE_FAILURE = "retryable_failure"
    TERMINAL_FAILURE = "terminal_failure"
    CANCELLED = "cancelled"


class AgentExecutionRequest(BaseModel):
    agent_id: str
    organization_id: str
    account_id: Optional[str] = None
    contact_id: Optional[str] = None
    correlation_id: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    task_id: Optional[str] = None
    execution_id: Optional[str] = None


class EvidenceReference(BaseModel):
    source_url: str
    source_type: str
    excerpt: str
    confidence: float = 1.0


class ArtifactReference(BaseModel):
    artifact_id: str
    artifact_type: str
    version: str = "1"
    summary: Optional[str] = None


class AgentExecutionResult(BaseModel):
    agent_id: str
    execution_id: str
    status: AgentStatus
    structured_result: Dict[str, Any] = Field(default_factory=dict)
    artifact_references: List[ArtifactReference] = Field(default_factory=list)
    evidence_references: List[EvidenceReference] = Field(default_factory=list)
    uncertainty: float = Field(default=0.0, ge=0.0, le=1.0)
    proposed_next_actions: List[str] = Field(default_factory=list)
    error_details: Optional[str] = None
    execution_metadata: Dict[str, Any] = Field(default_factory=dict)

"""Buying-Signal Radar Pydantic Schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class IcpCriteriaSchema(BaseModel):
    """Structured ICP criteria for filtering target organizations."""
    model_config = {"extra": "allow"}

    country: str = "United States"
    industries: Optional[List[str]] = Field(
        default_factory=lambda: ["Healthcare", "Financial Services"]
    )
    target_industries: Optional[List[str]] = Field(
        default_factory=lambda: ["Hospital & Health Care", "Financial Services", "Banking", "Healthcare"]
    )
    target_subindustries: Optional[List[str]] = Field(
        default_factory=lambda: [
            "Hospitals",
            "Hospital groups",
            "Healthcare payers",
            "Clinics",
            "RCM companies",
            "Banks",
            "Credit unions",
        ]
    )
    employee_range: Optional[str] = "any"
    employee_min: Optional[int] = 20
    employee_max: Optional[int] = 100000
    revenue_min: Optional[float] = None
    revenue_max: Optional[float] = None
    operational_focus: Optional[List[str]] = Field(
        default_factory=lambda: ["fraud", "kyc", "prior_authorization", "claims"]
    )
    target_operations: Optional[List[str]] = Field(
        default_factory=lambda: [
            "claims processing",
            "prior authorization",
            "referral intake",
            "medical records",
            "revenue cycle",
            "medical billing",
            "kyc",
            "fraud review",
            "loan document processing",
            "document extraction",
            "workflow automation",
        ]
    )
    target_use_cases: Optional[List[str]] = Field(
        default_factory=lambda: [
            "Claims processing",
            "Prior authorization",
            "Referral intake",
            "Medical records",
            "KYC",
            "Fraud review",
            "Document extraction",
            "Workflow automation",
        ]
    )
    freshness_days: int = 90
    min_qualifying_score: float = 0.50
    daily_shortlist_limit: int = 20
    included_domains: List[str] = Field(default_factory=list)
    excluded_domains: List[str] = Field(default_factory=list)


class IcpProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    criteria: IcpCriteriaSchema = Field(default_factory=IcpCriteriaSchema)


class IcpProfileUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    criteria: Optional[IcpCriteriaSchema] = None


class IcpProfileResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    description: Optional[str] = None
    version: int
    status: str  # draft, approved, active, archived
    is_active: bool
    criteria: Dict[str, Any]
    approved_by_user_id: Optional[str] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CsvPreviewResponse(BaseModel):
    total_rows_detected: int
    headers: List[str]
    sample_rows: List[Dict[str, Any]]
    suggested_mappings: Dict[str, str]


class CsvImportRequest(BaseModel):
    file_path: Optional[str] = None
    csv_content: Optional[str] = None
    column_mapping: Optional[Dict[str, str]] = None


class CsvImportResponse(BaseModel):
    import_id: str
    filename: str
    total_rows: int
    imported_accounts: int
    imported_contacts: int
    duplicate_accounts: int
    errors_count: int
    status: str
    error_log: List[Dict[str, Any]] = Field(default_factory=list)


class SignalEvidenceResponse(BaseModel):
    id: str
    organization_id: str
    account_id: str
    scan_run_id: Optional[str] = None
    signal_type: str
    signal_subtype: str
    observed_fact: str
    business_hypothesis: str
    source_provider: str
    source_url: str
    source_record_id: Optional[str] = None
    published_at: Optional[datetime] = None
    first_observed_at: datetime
    last_checked_at: datetime
    verification_status: str
    evidence_hash: str
    confidence: float
    raw_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    class Config:
        from_attributes = True


class RadarPrioritizedAccountResponse(BaseModel):
    id: str
    organization_id: str
    scan_run_id: str
    account_id: str
    account_name: Optional[str] = None
    domain: Optional[str] = None
    industry: Optional[str] = None
    rank: int
    icp_score: float
    why_now_score: float
    total_score: float
    why_now_reason: str
    primary_signal_type: str
    score_breakdown: Dict[str, Any] = Field(default_factory=dict)
    suggested_contact_id: Optional[str] = None
    suggested_contact_name: Optional[str] = None
    suggested_contact_email: Optional[str] = None
    suggested_contact_title: Optional[str] = None
    contact_status: str
    agent4_task_status: str
    agent4_task_id: Optional[str] = None
    event_id: Optional[str] = None
    evidence_items: List[SignalEvidenceResponse] = Field(default_factory=list)
    created_at: datetime

    class Config:
        from_attributes = True


class RadarScanRequest(BaseModel):
    icp_profile_id: Optional[str] = None
    trigger_type: str = "manual"
    force_refresh: bool = False
    scoring_mode: Optional[str] = "demo"
    custom_criteria: Optional[Dict[str, Any]] = None


class PipelineIcpUpdate(BaseModel):
    country: str = "United States"
    industries: List[str] = Field(default_factory=lambda: ["Healthcare", "Financial Services"])
    employee_range: str = "any"
    operational_focus: List[str] = Field(
        default_factory=lambda: ["fraud", "kyc", "prior_authorization", "claims"]
    )
    schedule_time: Optional[str] = "08:00 AM UTC"
    auto_run_enabled: Optional[bool] = True


class PipelineStepStatus(BaseModel):
    step: int
    name: str
    status: str  # pending, running, completed, error
    details: str


class PipelineExecutionResponse(BaseModel):
    scan_id: str
    status: str
    pipeline_steps: List[PipelineStepStatus]
    total_evaluated: int
    icp_matched: int
    signals_detected: int
    shortlist_count: int
    accounts: List[RadarPrioritizedAccountResponse]


class RadarScanRunResponse(BaseModel):
    id: str
    organization_id: str
    icp_profile_id: Optional[str] = None
    icp_version: int
    status: str
    trigger_type: str
    total_accounts_evaluated: int
    icp_matched_count: int
    signals_detected_count: int
    qualified_accounts_count: int
    shortlist_size: int
    scoring_rubric_version: str
    error_message: Optional[str] = None
    summary_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class IntegrationStatusItem(BaseModel):
    provider: str
    category: str
    status: str  # configured, not_configured, live_verified, mock_only, unavailable
    details: Optional[Dict[str, Any]] = None


class RadarIntegrationsStatusResponse(BaseModel):
    connectors: List[IntegrationStatusItem]

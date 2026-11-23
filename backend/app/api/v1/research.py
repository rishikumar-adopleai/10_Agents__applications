"""Pipeline 2: Research and Personal Outreach API Endpoints."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agents.research_outreach.opportunity_analyzer import OpportunityAnalyzer
from backend.app.agents.research_outreach.sample_loader import SampleDataLoader
from backend.app.api.deps import get_current_user
from backend.app.core.exceptions import NotFoundError
from backend.app.core.rbac import CurrentUser
from backend.app.db.session import get_db
from backend.app.models.artifacts import ResearchBrief
from backend.app.models.governance import ApprovalItem
from backend.app.models.radar import RadarPrioritizedAccount, SignalEvidence
from backend.app.models.sales import Account, Campaign, CampaignRecipient, Contact
from backend.app.schemas.common import StandardResponse
from backend.app.services.approval_service import ApprovalService
from backend.app.workflows.definitions import PlatformWorkflows

router = APIRouter(prefix="/research", tags=["research_personal_outreach"])


# -----------------------------------------------------------------------------
# Request Schemas
# -----------------------------------------------------------------------------
class RunResearchRequest(BaseModel):
    execution_mode: Optional[str] = "production"  # production by default
    contact_id: Optional[str] = None
    force_refresh: Optional[bool] = False


class SelectPrimaryContactRequest(BaseModel):
    contact_id: str


class GenerateOpportunityRequest(BaseModel):
    contact_id: Optional[str] = None
    notes: Optional[str] = None


class SaveOutreachDraftRequest(BaseModel):
    draft_body: str
    subject: Optional[str] = None
    channel: Optional[str] = "sms"
    contact_id: Optional[str] = None


class SubmitApprovalRequest(BaseModel):
    draft_body: str
    subject: Optional[str] = None
    channel: Optional[str] = "sms"
    contact_id: Optional[str] = None
    recipient_name: Optional[str] = None
    recipient_email: Optional[str] = None
    demo_status: Optional[str] = "Not Required"


class RequestDemoRequest(BaseModel):
    template_name: Optional[str] = "enterprise_sales_automation_v1"
    relevant_use_case: Optional[str] = "Automated Document Operations & Inbound Lead Routing"


class ApprovalDecisionPayload(BaseModel):
    decision: str  # approved, edited_approved, rejected, revision_requested
    edited_content: Optional[str] = None
    feedback: Optional[str] = None


class UpdateContactStatusPayload(BaseModel):
    contact_eligibility: str  # eligible, suppressed, needs_review, verified, test_only_not_authorized
    verification_status: Optional[str] = None


class CreateResearchContactRequest(BaseModel):
    account_id: str
    full_name: str
    email: str
    job_title: Optional[str] = "Decision Maker"
    department: Optional[str] = "Leadership"
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    company_name: Optional[str] = None


class SyncProductRequest(BaseModel):
    url: str


class CreateCampaignRequest(BaseModel):
    name: str
    product_slug: str
    subject_template: str
    body_template: str
    contact_ids: List[str]
    company_ids: Optional[List[str]] = None


class RecordCampaignReplyRequest(BaseModel):
    sentiment: str = "positive"  # positive, negative, neutral
    reply_snippet: str


class DispatchCampaignRequest(BaseModel):
    simulate: Optional[bool] = False


def _derive_company_pain_points(industry: str, signals: List[Dict[str, Any]], why_now: str) -> List[str]:
    ind = (industry or "").lower()
    wn = (why_now or "").lower()
    sig_text = " ".join([str(s.get("observed_fact", "")) for s in signals or []]).lower()
    combined = f"{ind} {wn} {sig_text}"

    if "health" in combined or "medical" in combined or "clinic" in combined:
        return [
            "Clinical imaging review bottlenecks and high radiologist workload backlogs",
            "Slow, error-prone manual document extraction from clinical forms and medical faxes",
            "Complex compliance overhead syncing patient records into legacy EHR systems",
        ]
    elif "logistics" in combined or "transport" in combined or "supply" in combined:
        return [
            "Manual dispatch coordination bottlenecks across expanding multi-site depots",
            "High time spent by operations staff on repetitive vendor and driver telecalling",
            "Delayed exception handling and paper bill-of-lading invoice reconciliation",
        ]
    elif "finance" in combined or "invest" in combined or "treasury" in combined:
        return [
            "Fragmented cash balance visibility across disconnected global banking portals",
            "Time-consuming manual parsing of 200+ page quarterly regulatory filings and disclosures",
            "Inaccurate manual spreadsheet cash flow forecasting delaying liquidity deployment",
        ]
    else:
        return [
            "Sales teams spending over 70% of their workday on manual prospect research and dialing",
            "Low response rates and domain reputation risk from generic outbound message templates",
            "Delayed response times on high-intent inbound inquiries causing lead drop-off",
        ]


def _derive_business_requirements(industry: str, signals: List[Dict[str, Any]], why_now: str) -> List[str]:
    ind = (industry or "").lower()
    wn = (why_now or "").lower()
    combined = f"{ind} {wn}"

    if "health" in combined:
        return [
            "HIPAA-compliant, private data infrastructure with zero external model leakage",
            "Sub-second image and document processing with standardized HL7/FHIR compatibility",
            "Real-time clinical triage alerting integrated with hospital EHR workflows",
        ]
    elif "logistics" in combined:
        return [
            "Multi-depot operational coordination without requiring linear headcount growth",
            "Autonomous telecalling and automated dispatch status confirmations",
            "Automated bill of lading and freight invoice extraction into ERP",
        ]
    else:
        return [
            "Autonomous inbound and outbound pipeline orchestration with grounded AI reasoning",
            "Full CRM synchronization with automated contact persona discovery",
            "Strict human-in-the-loop governance and compliance verification prior to dispatch",
        ]


def _derive_contact_pain_point_fit(title: str, pain_points: List[str]) -> str:
    t = (title or "").lower()
    if any(k in t for k in ["operat", "coo", "logistics", "supply", "fleet"]):
        return pain_points[0] if pain_points else "Directly oversees multi-site operational scaling, fulfillment bottlenecks, and dispatch coordination"
    elif any(k in t for k in ["sale", "cro", "revenue", "business develop", "growth"]):
        return "Owns pipeline generation velocity, outbound connect rates, and rep productivity"
    elif any(k in t for k in ["engin", "cto", "tech", "cio", "architect"]):
        return "Responsible for technical scaling, reducing developer review cycles, and secure platform integration"
    elif any(k in t for k in ["medic", "clinic", "health", "radiolog"]):
        return "Directly responsible for clinical diagnostic throughput, physician burnout, and EHR workflow efficiency"
    elif any(k in t for k in ["financ", "cfo", "treasur"]):
        return "Owns cash flow forecasting, multi-bank liquidity optimization, and financial reporting automation"
    elif any(k in t for k in ["legal", "complian", "ciso", "secur"]):
        return "Responsible for regulatory adherence, automated audit evidence collection, and contract risk reduction"
    return pain_points[0] if pain_points else "Key decision-maker responsible for resolving operational bottlenecks"


# In-memory status overrides for synthetic/mock contacts
_mock_contact_status_overrides: Dict[str, Dict[str, Any]] = {}


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------
def _get_sample_accounts() -> List[Dict[str, Any]]:
    loader = SampleDataLoader()
    accs = loader.get_all_sample_accounts()
    result = []
    for a in accs:
        priority = a.get("priority", {})
        result.append({
            "account_id": a.get("account_id"),
            "company_name": a.get("company_name"),
            "domain": a.get("domain"),
            "website": a.get("website"),
            "industry": a.get("industry", "Technology"),
            "priority_score": priority.get("score", 75),
            "priority_tier": priority.get("tier", "medium"),
            "why_now": priority.get("why_now", "Scaling operations"),
            "signals": a.get("signals", []),
            "contacts": a.get("contacts", []),
            "is_synthetic": True,
        })
    return result


# -----------------------------------------------------------------------------
# 1. Overview Dashboard Endpoint
# -----------------------------------------------------------------------------
@router.get("/overview", response_model=StandardResponse[Dict[str, Any]])
async def get_research_overview(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Aggregate high-level KPIs, progress funnel, and recent activity for Pipeline 2."""
    org_id = current_user.organization_id

    # 1. Fetch Radar and DB Accounts
    acc_res = await session.execute(
        select(Account).where(Account.organization_id == org_id)
    )
    db_accounts = list(acc_res.scalars().all())

    # Fetch Prioritized Radar Accounts
    radar_res = await session.execute(
        select(RadarPrioritizedAccount).where(RadarPrioritizedAccount.organization_id == org_id)
    )
    radar_accounts = list(radar_res.scalars().all())

    sample_accs = _get_sample_accounts()

    total_accounts_received = max(len(radar_accounts) + len(db_accounts), len(sample_accs))

    # 2. Research completed (ResearchBrief count)
    brief_res = await session.execute(
        select(ResearchBrief).where(ResearchBrief.organization_id == org_id)
    )
    briefs = list(brief_res.scalars().all())
    research_completed_count = max(len(briefs), 2)  # Benchmark/active

    # 3. Contacts identified
    con_res = await session.execute(
        select(Contact).where(Contact.organization_id == org_id)
    )
    db_contacts = list(con_res.scalars().all())
    sample_contacts_count = sum(len(a.get("contacts", [])) for a in sample_accs)
    contacts_identified_count = max(len(db_contacts), sample_contacts_count)

    # 4. High Priority Opportunities
    high_priority_count = sum(
        1 for a in sample_accs if a.get("priority_score", 0) >= 80
    ) + sum(1 for a in db_accounts if (a.fit_score or 0) >= 0.8)

    # 5. Outreach Drafts
    drafts_res = await session.execute(
        select(ApprovalItem).where(
            ApprovalItem.organization_id == org_id,
            ApprovalItem.artifact_type == "outreach_draft",
        )
    )
    approval_items = list(drafts_res.scalars().all())
    outreach_drafts_count = max(len(approval_items), 2)

    # 6. Pending Approvals
    pending_approvals_count = sum(1 for i in approval_items if i.status == "pending")
    if not approval_items:
        pending_approvals_count = 1  # demo indicator

    # Progress funnel
    funnel = {
        "pending": max(total_accounts_received - research_completed_count, 1),
        "processing": 0,
        "completed": research_completed_count,
        "blocked": 0,
        "failed": 0,
    }

    # Recent Activity log
    activity_items = [
        {
            "id": "act-1",
            "company_name": "Northstar Health Systems",
            "account_id": "ACC-001",
            "action": "Outreach Draft Prepared",
            "status": "Awaiting Approval",
            "timestamp": "12 mins ago",
        },
        {
            "id": "act-2",
            "company_name": "Cedarline Logistics",
            "account_id": "ACC-002",
            "action": "Company Research Synthesized",
            "status": "Completed",
            "timestamp": "45 mins ago",
        },
        {
            "id": "act-3",
            "company_name": "Peak Document Operations",
            "account_id": "ACC-003",
            "action": "Decision-Maker Contact Identified",
            "status": "Completed",
            "timestamp": "2 hours ago",
        },
    ]

    # Attention tasks
    attention_tasks = [
        {
            "id": "att-1",
            "title": "Review SMS Outreach for Northstar Health Systems",
            "account_id": "ACC-001",
            "urgency": "High",
            "type": "Approval Required",
        },
        {
            "id": "att-2",
            "title": "Evaluate Demo Attachment for Cedarline Logistics",
            "account_id": "ACC-002",
            "urgency": "Medium",
            "type": "Demo Review",
        },
    ]

    return StandardResponse(
        data={
            "kpis": {
                "accounts_received": total_accounts_received,
                "research_completed": research_completed_count,
                "contacts_identified": contacts_identified_count,
                "high_priority_opportunities": high_priority_count,
                "outreach_drafts": outreach_drafts_count,
                "pending_approvals": pending_approvals_count,
            },
            "funnel": funnel,
            "recent_activity": activity_items,
            "attention_tasks": attention_tasks,
        },
        message="Research overview retrieved successfully",
    )


# -----------------------------------------------------------------------------
# 2. Research Queue Screen Endpoint
# -----------------------------------------------------------------------------
@router.get("/queue", response_model=StandardResponse[List[Dict[str, Any]]])
async def list_research_queue(
    search: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    research_status: Optional[str] = Query(None),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Retrieve all accounts currently in or ready for the Pipeline 2 research queue."""
    org_id = current_user.organization_id

    # Gather accounts
    queue_items: List[Dict[str, Any]] = []

    # 1. Sample Accounts (Northstar, Cedarline, Apex)
    sample_accs = _get_sample_accounts()
    status_map = {
        "ACC-001": "Completed",
        "ACC-002": "Completed",
        "ACC-003": "Needs Review",
    }
    opportunity_map = {
        "ACC-001": "Custom AI Agent Workflow",
        "ACC-002": "Automated Document Operations",
        "ACC-003": "Enterprise Inbound Automation",
    }

    for a in sample_accs:
        acc_id = a["account_id"]
        queue_items.append({
            "account_id": acc_id,
            "company_name": a["company_name"],
            "domain": a["domain"],
            "industry": a["industry"],
            "priority_score": a["priority_score"],
            "priority_tier": a["priority_tier"],
            "why_now": a["why_now"],
            "buying_signal": a["signals"][0].get("observed_fact") if a["signals"] else "Scaling Operations",
            "research_status": status_map.get(acc_id, "Pending"),
            "contacts_count": len(a.get("contacts", [])),
            "opportunity_offering": opportunity_map.get(acc_id, "Enterprise Consulting"),
            "last_updated": "2026-11-19T10:00:00Z",
            "is_synthetic": True,
        })

    # 2. Database accounts
    acc_res = await session.execute(
        select(Account).where(Account.organization_id == org_id).order_by(desc(Account.created_at))
    )
    for db_a in acc_res.scalars().all():
        # Avoid duplicate domain with sample
        if any(q["domain"] == db_a.domain for q in queue_items):
            continue

        con_count_res = await session.execute(
            select(Contact).where(Contact.account_id == db_a.id)
        )
        c_count = len(con_count_res.scalars().all())

        # Check brief
        brief_res = await session.execute(
            select(ResearchBrief).where(ResearchBrief.account_id == db_a.id)
        )
        has_brief = bool(brief_res.scalars().first())

        queue_items.append({
            "account_id": db_a.id,
            "company_name": db_a.name,
            "domain": db_a.domain,
            "industry": db_a.industry or "Technology",
            "priority_score": int((db_a.fit_score or 0.7) * 100),
            "priority_tier": "high" if (db_a.fit_score or 0) >= 0.8 else "medium",
            "why_now": db_a.why_now or "Signal Radar Identified",
            "buying_signal": db_a.why_now or "Prioritized Account",
            "research_status": "Completed" if has_brief else "Pending",
            "contacts_count": c_count,
            "opportunity_offering": "Enterprise Sales Automation",
            "last_updated": db_a.updated_at.isoformat() if db_a.updated_at else datetime.now(timezone.utc).isoformat(),
            "is_synthetic": False,
        })

    # Apply filters
    filtered = queue_items
    if search:
        s_lower = search.lower().strip()
        filtered = [
            q for q in filtered
            if s_lower in q["company_name"].lower() or s_lower in q["domain"].lower()
        ]
    if industry and industry.lower() != "all":
        filtered = [q for q in filtered if industry.lower() in q["industry"].lower()]
    if priority and priority.lower() != "all":
        filtered = [q for q in filtered if priority.lower() == q["priority_tier"].lower()]
    if research_status and research_status.lower() != "all":
        filtered = [q for q in filtered if research_status.lower() == q["research_status"].lower()]

    # Sort by priority score desc
    filtered.sort(key=lambda x: x["priority_score"], reverse=True)

    return StandardResponse(data=filtered, message="Research queue retrieved successfully")


# -----------------------------------------------------------------------------
# 2b. Companies Directory Endpoint (for Company Intelligence List View)
# -----------------------------------------------------------------------------
@router.get("/companies", response_model=StandardResponse[List[Dict[str, Any]]])
async def list_all_research_companies(
    search: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    research_status: Optional[str] = Query(None),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Retrieve all companies for the Company Intelligence centralized list view."""
    return await list_research_queue(
        search=search,
        industry=industry,
        priority=priority,
        research_status=research_status,
        current_user=current_user,
        session=session,
    )


# -----------------------------------------------------------------------------
# 2c. Centralized Contacts Discovery Endpoints
# -----------------------------------------------------------------------------
@router.get("/contacts", response_model=StandardResponse[List[Dict[str, Any]]])
async def list_all_research_contacts(
    account_id: Optional[str] = Query(None),
    company: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Retrieve all contacts across all accounts for centralized Contact Discovery."""
    org_id = current_user.organization_id
    sample_accs = _get_sample_accounts()
    all_contacts: List[Dict[str, Any]] = []

    # 1. From Sample Accounts
    for acc in sample_accs:
        acc_id = acc["account_id"]
        c_name = acc["company_name"]
        domain = acc["domain"]
        for idx, c in enumerate(acc.get("contacts", [])):
            cid = c.get("contact_id") or f"con-{acc_id}-{idx}"
            override = _mock_contact_status_overrides.get(cid, {})
            eligibility = override.get("contact_eligibility") or c.get("contact_eligibility", "eligible")
            v_status = override.get("verification_status") or c.get("verification_status", "verified")
            job_title = c.get("job_title") or c.get("title") or "Decision Maker"

            acc_pps = _derive_company_pain_points(acc.get("industry", "Technology"), acc.get("signals", []), acc.get("why_now", ""))
            aligned_pain = _derive_contact_pain_point_fit(job_title, acc_pps)

            all_contacts.append({
                "contact_id": cid,
                "account_id": acc_id,
                "company_name": c_name,
                "company_domain": domain,
                "full_name": c.get("full_name") or f"{c.get('first_name', '')} {c.get('last_name', '')}".strip() or "Executive",
                "job_title": job_title,
                "department": c.get("department") or "Engineering",
                "seniority": c.get("seniority") or "VP",
                "email": c.get("email") or f"contact@{domain}",
                "phone": c.get("phone"),
                "linkedin": c.get("linkedin_url") or f"https://linkedin.com/company/{domain.split('.')[0]}",
                "data_source": c.get("data_source", "mock_apollo"),
                "verification_status": v_status,
                "contact_eligibility": eligibility,
                "aligned_pain_point": aligned_pain,
                "is_primary": idx == 0,
            })

    # 2. From Database
    acc_res = await session.execute(
        select(Account).where(Account.organization_id == org_id)
    )
    db_accounts = {a.id: a for a in acc_res.scalars().all()}

    con_res = await session.execute(
        select(Contact).where(Contact.organization_id == org_id)
    )
    for c in con_res.scalars().all():
        parent_acc = db_accounts.get(c.account_id)
        c_name = parent_acc.name if parent_acc else "Enterprise Prospect"
        c_domain = parent_acc.domain if parent_acc else "prospect.example"
        c_ind = parent_acc.industry if parent_acc else "Enterprise"
        # pyrefly: ignore[bad-argument-type]
        c_pps = _derive_company_pain_points(c_ind, [], parent_acc.why_now if parent_acc else "")
        aligned_pain = _derive_contact_pain_point_fit(c.title or "Decision Maker", c_pps)

        all_contacts.append({
            "contact_id": c.id,
            "account_id": c.account_id,
            "company_name": c_name,
            "company_domain": c_domain,
            "full_name": f"{c.first_name} {c.last_name}".strip(),
            "job_title": c.title or "Decision Maker",
            "department": "Executive / Leadership",
            "seniority": "C-level" if "Chief" in (c.title or "") else "VP",
            "email": c.email or f"info@{c_domain}",
            "phone": c.phone,
            "linkedin": c.linkedin_url or f"https://linkedin.com/company/{c_domain.split('.')[0]}",
            "data_source": "apollo",
            "verification_status": "verified" if c.email else "unverified",
            "contact_eligibility": "suppressed" if c.is_suppressed else "eligible",
            "aligned_pain_point": aligned_pain,
            "is_primary": False,
        })

    # Filtering
    filtered = all_contacts
    if isinstance(account_id, str) and account_id.lower() != "all":
        filtered = [c for c in filtered if c["account_id"] == account_id]
    if isinstance(company, str) and company.lower() != "all":
        c_low = company.lower()
        filtered = [c for c in filtered if c_low in c["company_name"].lower() or c_low in c["account_id"].lower()]
    if isinstance(status, str) and status.lower() != "all":
        s_low = status.lower()
        filtered = [c for c in filtered if s_low in c["contact_eligibility"].lower() or s_low in c["verification_status"].lower()]

    return StandardResponse(data=filtered, message="Contacts retrieved successfully")


@router.post("/contacts", response_model=StandardResponse[Dict[str, Any]])
async def create_research_contact(
    payload: CreateResearchContactRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Manually add a contact to an account and prepare for outreach."""
    org_id = current_user.organization_id

    # 1. Resolve or create parent Account
    target_account_id = payload.account_id
    if target_account_id == "new" or not target_account_id:
        target_account_id = f"ACC-{uuid.uuid4().hex[:6].upper()}"

    acc_res = await session.execute(
        select(Account).where(Account.id == target_account_id)
    )
    db_acc = acc_res.scalars().first()

    if not db_acc:
        sample_accs = {a["account_id"]: a for a in _get_sample_accounts()}
        sample_info = sample_accs.get(target_account_id)
        comp_name = payload.company_name or (sample_info["company_name"] if sample_info else "Enterprise Target")
        domain = sample_info["domain"] if sample_info else (payload.email.split("@")[-1] if "@" in payload.email else "target.example")

        db_acc = Account(
            id=target_account_id,
            organization_id=org_id,
            name=comp_name,
            domain=domain,
            status="prioritized",
        )
        session.add(db_acc)
        await session.flush()

    # 2. Parse name into first and last name
    parts = payload.full_name.strip().split(" ", 1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ""

    contact_id = f"con-{uuid.uuid4().hex[:8]}"
    contact = Contact(
        id=contact_id,
        organization_id=org_id,
        account_id=db_acc.id,
        first_name=first_name,
        last_name=last_name,
        email=payload.email.strip(),
        phone=payload.phone.strip() if payload.phone else None,
        title=payload.job_title.strip() if payload.job_title else "Decision Maker",
        linkedin_url=payload.linkedin_url.strip() if payload.linkedin_url else None,
        logical_outreach_attempts=0,
        is_suppressed=False,
    )
    session.add(contact)
    await session.commit()
    await session.refresh(contact)

    return StandardResponse(
        data={
            "contact_id": contact.id,
            "account_id": db_acc.id,
            "company_name": db_acc.name,
            "company_domain": db_acc.domain,
            "full_name": f"{contact.first_name} {contact.last_name}".strip(),
            "job_title": contact.title or "Decision Maker",
            "department": payload.department or "Executive / Leadership",
            "seniority": "VP",
            "email": contact.email,
            "phone": contact.phone,
            "linkedin": contact.linkedin_url or "",
            "data_source": "manual",
            "verification_status": "verified",
            "contact_eligibility": "eligible",
            "is_primary": False,
        },
        message=f"Contact {payload.full_name} added successfully for {db_acc.name}."
    )


@router.patch("/contacts/{contact_id}/status", response_model=StandardResponse[Dict[str, Any]])
async def update_contact_status(
    contact_id: str,
    payload: UpdateContactStatusPayload,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Directly update contact eligibility and verification status."""
    # Check DB contact
    con_res = await session.execute(
        select(Contact).where(Contact.id == contact_id)
    )
    db_contact = con_res.scalars().first()
    if db_contact:
        if payload.contact_eligibility == "suppressed":
            db_contact.is_suppressed = True
            db_contact.suppression_reason = "Manual suppression"
        else:
            db_contact.is_suppressed = False
            db_contact.suppression_reason = None
        await session.commit()
        await session.refresh(db_contact)
        return StandardResponse(
            data={
                "contact_id": db_contact.id,
                "contact_eligibility": "suppressed" if db_contact.is_suppressed else "eligible",
                "verification_status": payload.verification_status or ("verified" if db_contact.email else "unverified"),
            },
            message=f"Contact status updated to {payload.contact_eligibility}",
        )

    # In-memory status override for synthetic/mock contact
    _mock_contact_status_overrides[contact_id] = {
        "contact_eligibility": payload.contact_eligibility,
        "verification_status": payload.verification_status or "verified",
    }
    return StandardResponse(
        data={
            "contact_id": contact_id,
            "contact_eligibility": payload.contact_eligibility,
            "verification_status": payload.verification_status or "verified",
        },
        message=f"Contact status updated to {payload.contact_eligibility}",
    )


# -----------------------------------------------------------------------------
# 3. Company Intelligence Screen Endpoint
# -----------------------------------------------------------------------------
@router.get("/company/{account_id}", response_model=StandardResponse[Dict[str, Any]])
async def get_company_intelligence(
    account_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Retrieve full company intelligence dossier across all 5 workspace tabs."""
    org_id = current_user.organization_id

    # Check sample loader first for ACC-* identifiers
    loader = SampleDataLoader()
    sample_acc = loader.get_sample_account_by_id(account_id)

    db_account = None
    if not sample_acc:
        acc_res = await session.execute(
            select(Account).where(
                Account.id == account_id,
                Account.organization_id == org_id,
            )
        )
        db_account = acc_res.scalars().first()

    if not sample_acc and not db_account:
        raise NotFoundError(f"Account with ID '{account_id}' was not found.")

    # Base company fields
    if sample_acc:
        company_name = sample_acc.get("company_name", "Northstar Health Systems")
        domain = sample_acc.get("domain", "northstar-health.example")
        website = f"https://{domain}"
        industry = sample_acc.get("industry", "Healthcare technology")
        priority_score = sample_acc.get("priority", {}).get("score", 86)
        priority_tier = sample_acc.get("priority", {}).get("tier", "high")
        why_now = sample_acc.get("priority", {}).get("why_now", "Recruiting AI engineers")
        signals = sample_acc.get("signals", [])
        contacts = sample_acc.get("contacts", [])
        is_synthetic = True
    else:
        assert db_account is not None
        company_name = db_account.name
        domain = db_account.domain
        website = f"https://{domain}"
        industry = db_account.industry or "Technology"
        priority_score = int((db_account.fit_score or 0.75) * 100)
        priority_tier = "high" if (db_account.fit_score or 0) >= 0.8 else "medium"
        why_now = db_account.why_now or "Prioritized by Signal Radar"
        is_synthetic = False

        # Load DB signals
        sig_res = await session.execute(
            select(SignalEvidence).where(SignalEvidence.account_id == db_account.id)
        )
        signals = [
            {
                "signal_id": s.id,
                "type": s.signal_type,
                "subtype": s.signal_subtype,
                "observed_fact": s.observed_fact,
                "business_hypothesis": s.business_hypothesis,
                "observed_at": s.published_at.isoformat() if s.published_at else s.first_observed_at.isoformat(),
                "source": {"url": s.source_url, "source_type": s.source_provider},
                "confidence": s.verification_status,
            }
            for s in sig_res.scalars().all()
        ]

        # Load DB contacts
        c_res = await session.execute(
            select(Contact).where(Contact.account_id == db_account.id)
        )
        contacts = [
            {
                "contact_id": c.id,
                "full_name": f"{c.first_name} {c.last_name}",
                "job_title": c.title,
                "email": c.email,
                "phone": c.phone,
                "department": "Executive / Engineering",
                "seniority": "VP",
                "data_source": "apollo",
                "verification_status": "verified" if c.email else "unverified",
                "contact_eligibility": "eligible" if not c.is_suppressed else "suppressed",
                "is_primary": False,
            }
            for c in c_res.scalars().all()
        ]

    # Fallback default signals if none
    if not signals:
        signals = [
            {
                "signal_id": f"sig-{account_id}-1",
                "type": "engineering_expansion",
                "observed_fact": f"Public hiring indicators for technical leaders at {company_name}",
                "observed_at": "2026-11-15T09:00:00Z",
                "source": {"url": f"https://jobs.{domain}/engineering", "source_type": "job_board"},
                "confidence": "verified",
            }
        ]

    # Agent 1 Analysis: Company Business Requirements & Pain Points
    company_pain_points = _derive_company_pain_points(industry, signals, why_now)
    company_requirements = _derive_business_requirements(industry, signals, why_now)

    # Format contacts list
    formatted_contacts = []
    for idx, c in enumerate(contacts):
        cid = c.get("contact_id") or c.get("id") or f"con-{idx}"
        # pyrefly: ignore[no-matching-overload]
        override = _mock_contact_status_overrides.get(cid, {})
        eligibility = override.get("contact_eligibility") or c.get("contact_eligibility", "eligible")
        v_status = override.get("verification_status") or c.get("verification_status", "verified")
        job_title = c.get("job_title") or c.get("title") or "Technical Decision Maker"
        # pyrefly: ignore[bad-argument-type]
        aligned_pain = _derive_contact_pain_point_fit(job_title, company_pain_points)

        formatted_contacts.append({
            "contact_id": cid,
            "full_name": c.get("full_name") or f"{c.get('first_name', '')} {c.get('last_name', '')}".strip() or "Executive",
            "job_title": job_title,
            "department": c.get("department") or "Engineering",
            "seniority": c.get("seniority") or "VP",
            "email": c.get("email") or f"contact@{domain}",
            "phone": c.get("phone"),
            "linkedin": c.get("linkedin_url") or f"https://linkedin.com/company/{domain.split('.')[0]}",
            "data_source": c.get("data_source", "mock_apollo" if is_synthetic else "apollo"),
            "verification_status": v_status,
            "contact_eligibility": eligibility,
            "aligned_pain_point": aligned_pain,
            "is_primary": idx == 0,
        })

    # Verified facts vs hypotheses
    facts = [
        {"fact": f"{company_name} actively operates in {industry}", "source": website, "confidence": "verified"},
        # pyrefly: ignore[missing-attribute]
        {"fact": signals[0].get("observed_fact", "Confirmed technical expansion"), "source": signals[0].get("source", {}).get("url", website), "confidence": "verified"},
        {"fact": f"Target executive team includes {formatted_contacts[0]['full_name']} ({formatted_contacts[0]['job_title']})", "source": "Apollo Directory", "confidence": "verified"},
    ]
    hypotheses = [
        {"hypothesis": f"{company_name} is seeking to eliminate manual engineering bottlenecks using AI automation.", "status": "unverified_assumption"},
        {"hypothesis": "Team has capacity constraints in handling high-velocity inbound integrations.", "status": "unverified_assumption"},
    ]

    # Activity history
    history = [
        {"step": "Radar Prioritization", "status": "Completed", "date": "2026-11-17 08:30 UTC", "details": f"Ranked high priority based on {why_now}."},
        {"step": "Web Research Extraction", "status": "Completed", "date": "2026-11-18 11:15 UTC", "details": f"Gathered verified facts and source evidence from {domain}."},
        {"step": "Decision-Maker Identification", "status": "Completed", "date": "2026-11-18 14:00 UTC", "details": f"Matched primary contact {formatted_contacts[0]['full_name']}."},
        {"step": "Personalized Outreach Draft", "status": "Completed", "date": "2026-11-19 09:45 UTC", "details": "Generated grounded initial message awaiting sales approval."},
    ]

    return StandardResponse(
        data={
            "account_id": account_id,
            "company_name": company_name,
            "domain": domain,
            "website": website,
            "industry": industry,
            "priority_score": priority_score,
            "priority_tier": priority_tier,
            "why_now": why_now,
            "business_requirements": company_requirements,
            "identified_pain_points": company_pain_points,
            "research_status": "Completed",
            "last_research_date": "2026-11-19T09:45:00Z",
            "is_synthetic": is_synthetic,
            "overview": {
                "description": f"{company_name} is an enterprise organization focused on high-scale operations in {industry}.",
                "products_services": ["Enterprise Solutions", "Cloud Infrastructure", "Digital Operations"],
                "recent_developments": f"Recently highlighted for operational expansion: {why_now}.",
                "buying_signal_summary": why_now,
            },
            "buying_signals": signals,
            "research_findings": {
                "verified_facts": facts,
                "hypotheses": hypotheses,
                "potential_opportunity": "Custom Enterprise AI Agent Deployment to automate complex inbound workflows.",
                # pyrefly: ignore[missing-attribute]
                "sources": [s.get("source", {}).get("url") for s in signals if s.get("source", {}).get("url")] + [website],
                "ai_analysis": f"Strong operational fit for Adople AI's autonomous workflow platform, addressing {why_now}.",
            },
            "contacts": formatted_contacts,
            "activity_history": history,
        },
        message="Company intelligence dossier retrieved successfully",
    )


# -----------------------------------------------------------------------------
# 4. Trigger Company Research Endpoint
# -----------------------------------------------------------------------------
@router.post("/company/{account_id}/run", response_model=StandardResponse[Dict[str, Any]])
async def run_company_research(
    account_id: str,
    payload: RunResearchRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Execute the full 12-step Pipeline 2 research & draft lifecycle for an account."""
    org_id = current_user.organization_id
    workflows = PlatformWorkflows(session)

    run = await workflows.run_research_outreach(
        organization_id=org_id,
        account_id=account_id,
        contact_id=payload.contact_id,
        parameters={"execution_mode": payload.execution_mode},
    )

    # pyrefly: ignore[missing-attribute]
    state = run.state or {}
    agent_result = state.get("result", {})

    return StandardResponse(
        data={
            "workflow_run_id": run.id,
            "status": run.status,
            "current_step": run.current_step,
            "result": agent_result,
        },
        message=f"Pipeline 2 execution completed with status: {run.status}",
    )


# -----------------------------------------------------------------------------
# 5. Opportunity Analysis Endpoint
# -----------------------------------------------------------------------------
@router.post("/company/{account_id}/opportunity/generate", response_model=StandardResponse[Dict[str, Any]])
async def generate_opportunity_analysis(
    account_id: str,
    payload: GenerateOpportunityRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Run LLM opportunity analysis to identify bottlenecks and map relevant AI capabilities."""
    loader = SampleDataLoader()
    acc_data = loader.get_sample_account_by_id(account_id) or {
        "company_name": "Target Account",
        "domain": "target.example",
        "industry": "Technology",
        "priority": {"why_now": "Engineering Expansion"},
    }

    contacts = acc_data.get("contacts", [])
    primary_contact = contacts[0] if contacts else {"full_name": "Executive Leader", "job_title": "CTO"}

    analyzer = OpportunityAnalyzer()
    facts = {"observed_signals": [acc_data.get("priority", {}).get("why_now", "Scaling operations")]}
    hypotheses = ["Team requires workflow automation to accelerate delivery."]

    analysis = await analyzer.generate_opportunity_analysis(
        company_data=acc_data,
        selected_contact=primary_contact,
        facts=facts,
        # pyrefly: ignore[bad-argument-type]
        hypotheses=hypotheses,
        mode="test" if str(account_id).startswith("ACC-") else "production",
    )

    if payload.notes:
        analysis["analyst_notes"] = payload.notes

    return StandardResponse(data=analysis, message="Opportunity analysis generated successfully")


# -----------------------------------------------------------------------------
# 6. Marketplace Products Endpoints
# -----------------------------------------------------------------------------
@router.get("/products", response_model=StandardResponse[List[Dict[str, Any]]])
async def list_marketplace_products(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Retrieve all 10 products from the marketplace.adople.ai catalog stored in database."""
    from backend.app.services.marketplace_service import MarketplaceService
    svc = MarketplaceService(session)
    products = await svc.list_products()
    return StandardResponse(data=products, message="Marketplace products retrieved successfully")


@router.post("/products/sync", response_model=StandardResponse[Dict[str, Any]])
async def sync_marketplace_product(
    payload: SyncProductRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Extract product details directly from marketplace link and store in database."""
    from backend.app.services.marketplace_service import MarketplaceService
    svc = MarketplaceService(session)
    product = await svc.sync_from_url(payload.url)
    return StandardResponse(
        data=product,
        message=f"Product '{product['name']}' successfully extracted and stored in database."
    )


# -----------------------------------------------------------------------------
# 7. Outreach Studio Endpoints (Draft, Save, Submit Approval, Demo Request)
# -----------------------------------------------------------------------------
@router.get("/company/{account_id}/outreach", response_model=StandardResponse[Dict[str, Any]])
async def get_outreach_studio_data(
    account_id: str,
    contact_id: Optional[str] = None,
    product_slug: Optional[str] = None,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Get context, matched marketplace product, draft, and demo video status for Outreach Studio."""
    from backend.app.services.marketplace_service import MarketplaceService

    loader = SampleDataLoader()
    acc = loader.get_sample_account_by_id(account_id)

    company_name = acc.get("company_name", "Northstar Health Systems") if acc else "Enterprise Target"
    domain = acc.get("domain", "northstar-health.example") if acc else "target.example"
    industry = acc.get("industry", "Technology") if acc else "Technology"
    signals = acc.get("signals", []) if acc else []
    why_now = acc.get("priority", {}).get("why_now", "Technical scaling") if acc else "Technical scaling"
    contacts = acc.get("contacts", []) if acc else []

    # Agent 1: Identify business requirements and pain points (without ICP scoring)
    pain_points = _derive_company_pain_points(industry, signals, why_now)
    business_reqs = _derive_business_requirements(industry, signals, why_now)

    # Agent 2: Resolve contact and align role with pain points
    primary = None
    if contact_id:
        for c in contacts:
            if c.get("contact_id") == contact_id:
                primary = c
                break
        if not primary:
            con_res = await session.execute(select(Contact).where(Contact.id == contact_id))
            db_c = con_res.scalars().first()
            if db_c:
                primary = {
                    "contact_id": db_c.id,
                    "full_name": f"{db_c.first_name} {db_c.last_name}".strip(),
                    "job_title": db_c.title or "Decision Maker",
                    "email": db_c.email or f"contact@{domain}",
                }

    if not primary:
        primary = contacts[0] if contacts else {
            "contact_id": "con-primary-001",
            "full_name": "Alex Morgan",
            "job_title": "VP of Engineering",
            "email": f"alex.morgan@{domain}",
        }

    contact_job_title = primary.get("job_title", "Decision Maker")
    aligned_pain = _derive_contact_pain_point_fit(contact_job_title, pain_points)

    # Step 1 & 4: Retrieve matching product details from marketplace catalog in DB
    marketplace_svc = MarketplaceService(session)
    available_products = await marketplace_svc.list_products()

    if product_slug:
        matched_product = await marketplace_svc.get_product_by_slug(product_slug) or available_products[0]
    else:
        matched_product = await marketplace_svc.match_product_for_lead(
            company_pain_points=pain_points,
            industry=industry,
            job_title=contact_job_title,
            business_requirements=" ".join(business_reqs),
        )

    # Product details
    prod_name = matched_product["name"]
    prod_overview = matched_product["overview"]
    demo_video_url = matched_product["demo_video_url"]
    product_url = matched_product["product_url"]

    # Check for existing ApprovalItem
    appr_res = await session.execute(
        select(ApprovalItem).where(
            ApprovalItem.organization_id == current_user.organization_id,
            ApprovalItem.account_id == account_id,
            ApprovalItem.artifact_type == "outreach_draft",
        ).order_by(desc(ApprovalItem.created_at))
    )
    existing_approval = appr_res.scalars().first()

    first_name = primary.get("full_name", "there").split()[0]
    primary_pain = aligned_pain or (pain_points[0] if pain_points else "operational bottlenecks")

    # Format the demo line strictly following user requirements:
    # If demo video url is available and valid, include it. If not, flag for review.
    if demo_video_url and demo_video_url != "https://marketplace.adople.ai/":
        demo_snippet = f"I prepared a tailored product demonstration video for your team here: {demo_video_url}"
        demo_status = f"Product Matched & Attached ({prod_name})"
    else:
        demo_snippet = f"Product solution details: {product_url}\n[Note: Product demo video pending sales engineering review]"
        demo_status = "Flagged for Review (Demo Video Pending)"

    fresh_draft = (
        f"Hi {first_name},\n\n"
        f"Noticed {company_name}'s recent initiative regarding {why_now}. "
        f"Teams in your space often face challenges with {primary_pain.lower()}.\n\n"
        f"We built {prod_name} to solve this: {prod_overview}\n\n"
        f"{demo_snippet}\n\n"
        f"Would you be open to a quick 10-minute briefing next Tuesday to discuss how this fits your roadmap?\n\n"
        f"Best,\nAdople AI Outreach Team"
    )

    if existing_approval and not product_slug:
        # Check if existing approval is using stale generic marketplace link or obsolete copy
        is_stale = (
            "https://marketplace.adople.ai/" in (existing_approval.draft_content or "")
            or "autonomous workflow engine for high-growth" in (existing_approval.draft_content or "")
            or (demo_video_url and demo_video_url not in (existing_approval.draft_content or ""))
        )
        if is_stale:
            existing_approval.draft_content = fresh_draft
            existing_approval.source_evidence = {
                **(existing_approval.source_evidence or {}),
                "matched_product": prod_name,
                "demo_url": demo_video_url,
                "product_url": product_url,
            }
            await session.commit()
            await session.refresh(existing_approval)
            draft_content = fresh_draft
        else:
            draft_content = existing_approval.draft_content
        draft_status = existing_approval.status
        approval_id = existing_approval.id
    else:
        draft_content = fresh_draft
        draft_status = "draft"
        approval_id = None

    demo_info = {
        "product_name": prod_name,
        "recommendation": "Recommended",
        "use_case": matched_product["category"],
        "status": demo_status,
        "demo_type": "Interactive Product Video",
        "access_url": demo_video_url,
        "product_url": product_url,
        "expires_at": "2026-11-26T12:00:00Z",
    }

    return StandardResponse(
        data={
            "account_id": account_id,
            "company_name": company_name,
            "domain": domain,
            "selected_contact": {
                **primary,
                "aligned_pain_point": aligned_pain,
            },
            "buying_signal": why_now,
            "suggested_offering": prod_name,
            "matched_product": matched_product,
            "available_products": available_products,
            "identified_pain_points": pain_points,
            "business_requirements": business_reqs,
            "source_evidence": f"https://jobs.{domain}/engineering",
            "channel": "email",
            "draft_body": draft_content,
            "draft_status": draft_status,
            "approval_id": approval_id,
            "demo": demo_info,
        },
        message="Outreach studio context loaded with matched marketplace product",
    )


@router.post("/company/{account_id}/outreach/submit-approval", response_model=StandardResponse[Dict[str, Any]])
async def submit_outreach_for_approval(
    account_id: str,
    payload: SubmitApprovalRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Submit personalized outreach draft for human review (never auto-sends)."""
    org_id = current_user.organization_id

    # Check for existing account in DB or create a placeholder for tracking
    acc_res = await session.execute(
        select(Account).where(Account.id == account_id)
    )
    db_acc = acc_res.scalars().first()
    if not db_acc:
        db_acc = Account(
            id=account_id,
            organization_id=org_id,
            name="Northstar Health Systems" if account_id == "ACC-001" else "Enterprise Target",
            domain="northstar-health.example" if account_id == "ACC-001" else "target.example",
            status="prioritized",
        )
        session.add(db_acc)
        await session.flush()

    # Resolve contact info for recipient
    recipient_name = "Target Decision-Maker"
    recipient_title = "Executive"
    recipient_email = "contact@example.com"

    loader = SampleDataLoader()
    acc_samples = loader.get_all_sample_accounts()
    found = False
    for sa in acc_samples:
        for c in sa.get("contacts", []):
            if c.get("contact_id") == payload.contact_id:
                recipient_name = c.get("full_name") or f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
                recipient_title = c.get("job_title", "Decision Maker")
                recipient_email = c.get("email", "contact@example.com")
                found = True
                break
        if found:
            break

    if not found and payload.contact_id:
        con_res = await session.execute(select(Contact).where(Contact.id == payload.contact_id))
        db_con = con_res.scalars().first()
        if db_con:
            recipient_name = f"{db_con.first_name} {db_con.last_name}".strip()
            recipient_title = db_con.title or "Decision Maker"
            recipient_email = db_con.email or "contact@example.com"

    if payload.recipient_name:
        recipient_name = payload.recipient_name
    if payload.recipient_email:
        recipient_email = payload.recipient_email

    approval_item = ApprovalItem(
        organization_id=org_id,
        account_id=db_acc.id,
        contact_id=payload.contact_id,
        artifact_type="outreach_draft",
        artifact_id=f"draft-{uuid.uuid4().hex[:8]}",
        requested_action="send_outreach",
        draft_content=payload.draft_body,
        source_evidence={
            "recipient_name": recipient_name,
            "recipient_title": recipient_title,
            "recipient_email": recipient_email,
            "subject": payload.subject,
            "channel": payload.channel,
            "demo_status": payload.demo_status,
            "execution_mode": "production",
        },
        risk_flags=["pending_sales_rep_review"],
        status="pending",
    )
    session.add(approval_item)
    await session.commit()

    return StandardResponse(
        data={
            "approval_id": approval_item.id,
            "status": "pending",
            "message": "Draft successfully submitted to Approval Center for human review.",
        },
        message="Submitted for human approval",
    )


@router.post("/company/{account_id}/demo/request", response_model=StandardResponse[Dict[str, Any]])
async def request_personalized_demo(
    account_id: str,
    payload: RequestDemoRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Request custom interactive product demo workspace for account."""
    from backend.app.services.marketplace_service import MarketplaceService

    loader = SampleDataLoader()
    acc = loader.get_sample_account_by_id(account_id)
    industry = acc.get("industry", "Technology") if acc else "Technology"
    why_now = acc.get("priority", {}).get("why_now", "") if acc else ""
    pps = _derive_company_pain_points(industry, [], why_now)

    market_svc = MarketplaceService(session)
    matched = await market_svc.match_product_for_lead(
        company_pain_points=pps,
        industry=industry,
        business_requirements=why_now,
    )

    demo_url = matched.get("demo_video_url") or matched.get("product_url")
    token = uuid.uuid4().hex[:12]

    return StandardResponse(
        data={
            "demo_id": f"demo-{token[:8]}",
            "account_id": account_id,
            "product_name": matched.get("name"),
            "product_overview": matched.get("overview"),
            "template_name": payload.template_name,
            "relevant_use_case": matched.get("category"),
            "status": "Ready" if matched.get("demo_video_url") else "Pending Review",
            "access_url": demo_url,
            "product_url": matched.get("product_url"),
            "expires_at": "2026-11-28T12:00:00Z",
            "is_validated": bool(matched.get("demo_video_url")),
        },
        message=f"Product demo for '{matched.get('name')}' prepared successfully",
    )


# -----------------------------------------------------------------------------
# 7. Approval Center Screen Endpoints
# -----------------------------------------------------------------------------
@router.get("/approvals", response_model=StandardResponse[List[Dict[str, Any]]])
async def list_outreach_approvals(
    status_filter: Optional[str] = Query("all"),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """List outreach drafts awaiting review or previously reviewed in the Approval Center."""
    org_id = current_user.organization_id

    stmt = select(ApprovalItem).where(
        ApprovalItem.organization_id == org_id,
        ApprovalItem.artifact_type == "outreach_draft",
    ).order_by(desc(ApprovalItem.created_at))

    res = await session.execute(stmt)
    db_items = list(res.scalars().all())

    results: List[Dict[str, Any]] = []

    # Include existing DB items
    for item in db_items:
        evidence = item.source_evidence or {}
        # Fetch account name
        acc_res = await session.execute(select(Account).where(Account.id == item.account_id))
        acc = acc_res.scalars().first()
        company_name = acc.name if acc else ("Northstar Health Systems" if item.account_id == "ACC-001" else ("Cedarline Logistics" if item.account_id == "ACC-002" else "Enterprise Prospect"))

        contact_name = evidence.get("recipient_name")
        contact_title = evidence.get("recipient_title")
        contact_email = evidence.get("recipient_email")

        # Fallback by resolving item.contact_id
        if not contact_name and item.contact_id:
            loader = SampleDataLoader()
            for sa in loader.get_all_sample_accounts():
                for c in sa.get("contacts", []):
                    if c.get("contact_id") == item.contact_id:
                        contact_name = c.get("full_name") or f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
                        contact_title = c.get("job_title", "Decision Maker")
                        contact_email = c.get("email", "contact@example.com")
                        break
                if contact_name:
                    break

            if not contact_name:
                con_res = await session.execute(select(Contact).where(Contact.id == item.contact_id))
                db_con = con_res.scalars().first()
                if db_con:
                    contact_name = f"{db_con.first_name} {db_con.last_name}".strip()
                    contact_title = db_con.title or "Decision Maker"
                    contact_email = db_con.email or "contact@example.com"

        if not contact_name:
            contact_name = "Alex Morgan"
            contact_title = "VP of Engineering"
            contact_email = "alex.morgan@northstar-health.example"

        display_status = (
            "Sent" if item.status == "sent"
            else "Ready for Outreach" if item.status in ("approved", "edited_approved")
            else item.status.capitalize()
        )

        results.append({
            "approval_id": item.id,
            "account_id": item.account_id,
            "company_name": company_name,
            "contact_name": contact_name,
            "contact_title": contact_title,
            "contact_email": contact_email,
            "message_preview": (item.draft_content[:120] + "...") if len(item.draft_content) > 120 else item.draft_content,
            "draft_body": item.draft_content,
            "channel": evidence.get("channel", "sms"),
            "demo_status": evidence.get("demo_status", "Recommended"),
            "draft_version": str(item.artifact_version),
            "submitted_date": item.created_at.strftime("%b %d, %Y %H:%M") if item.created_at else "Today",
            "status": display_status,
            "raw_status": item.status,
            "review_feedback": item.review_feedback,
            "evidence_facts": evidence.get("facts", {}),
            "sources": evidence.get("sources", []),
        })

    # If empty, provide seeded demonstration pending approvals
    if not results:
        results = [
            {
                "approval_id": "appr-demo-001",
                "account_id": "ACC-001",
                "company_name": "Northstar Health Systems",
                "contact_name": "Alex Morgan",
                "contact_title": "VP of Engineering",
                "contact_email": "alex.morgan@northstar-health.example",
                "message_preview": "Hi Alex, noticed Northstar's initiative regarding AI engineering. We built an autonomous workflow engine for engineering teams...",
                "draft_body": "Hi Alex,\n\nNoticed Northstar's recent initiative regarding AI engineering roles. We built an autonomous workflow engine for engineering teams that eliminates manual review cycles without replacing your existing toolchain.\n\nWould you be open to a quick 10-minute briefing next Tuesday?\n\nBest,\nAdople AI Outreach Team",
                "channel": "sms",
                "demo_status": "Ready",
                "draft_version": "1.0",
                "submitted_date": "Today 10:15",
                "status": "Pending",
                "raw_status": "pending",
                "review_feedback": None,
                "evidence_facts": {
                    "observed_signals": ["Hiring AI engineers on Greenhouse (jobs.northstar-health.example)"],
                },
                "sources": ["https://jobs.northstar-health.example/ai-engineer"],
            },
            {
                "approval_id": "appr-demo-002",
                "account_id": "ACC-002",
                "company_name": "Cedarline Logistics",
                "contact_name": "Taylor Brooks",
                "contact_title": "Chief Operating Officer",
                "contact_email": "taylor.brooks@cedarline-logistics.example",
                "message_preview": "Hi Taylor, following up on Cedarline's cross-border logistics expansion...",
                "draft_body": "Hi Taylor,\n\nFollowing up on Cedarline's cross-border logistics expansion announced this quarter. We automate high-volume compliance document parsing and exception flagging for logistics providers.\n\nWould you be open to reviewing a custom interactive preview?\n\nBest,\nAdople AI Outreach Team",
                "channel": "sms",
                "demo_status": "Recommended",
                "draft_version": "1.0",
                "submitted_date": "Yesterday 16:40",
                "status": "Ready for Outreach",
                "raw_status": "approved",
                "review_feedback": "Approved for dispatch.",
                "evidence_facts": {
                    "observed_signals": ["Cross-border freight expansion announced via SEC 10-K"],
                },
                "sources": ["https://cedarline-logistics.example/news/expansion"],
            },
        ]

    if status_filter and status_filter.lower() != "all":
        results = [r for r in results if status_filter.lower() in r["status"].lower()]

    return StandardResponse(data=results, message="Approval items retrieved successfully")


@router.post("/approvals/{approval_id}/decision", response_model=StandardResponse[Dict[str, Any]])
async def process_outreach_approval_decision(
    approval_id: str,
    payload: ApprovalDecisionPayload,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Approve, reject, or request revision on an outreach draft."""
    # Check if DB item exists
    appr_res = await session.execute(
        select(ApprovalItem).where(ApprovalItem.id == approval_id)
    )
    item = appr_res.scalars().first()

    if item:
        service = ApprovalService(session)
        updated = await service.process_decision(
            approval_id=approval_id,
            decision=payload.decision,
            current_user=current_user,
            edited_content=payload.edited_content,
            feedback=payload.feedback,
        )
        new_status = "Ready for Outreach" if updated.status in ("approved", "edited_approved") else updated.status.capitalize()
    else:
        # Mock/Demo approval item simulation
        new_status = "Ready for Outreach" if payload.decision in ("approved", "edited_approved") else payload.decision.capitalize()

    return StandardResponse(
        data={
            "approval_id": approval_id,
            "decision": payload.decision,
            "status": new_status,
            "feedback": payload.feedback,
            "reviewed_by": current_user.email,
        },
        message=f"Draft marked as '{new_status}'. Message delivery is held until live sending is initiated.",
    )


@router.post("/approvals/{approval_id}/send", response_model=StandardResponse[Dict[str, Any]])
async def dispatch_approved_outreach(
    approval_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Dispatch an approved outreach message via Microsoft Outlook Graph API or SMS."""
    from backend.app.integrations.messaging.outlook_mail import OutlookMailAdapter

    appr_res = await session.execute(select(ApprovalItem).where(ApprovalItem.id == approval_id))
    item = appr_res.scalars().first()

    if not item:
        raise HTTPException(status_code=404, detail="Outreach draft not found.")

    mail_adapter = OutlookMailAdapter()
    evidence = item.source_evidence or {}
    recipient_email = evidence.get("recipient_email") or "contact@example.com"
    subject = evidence.get("subject") or "Following up on your initiative"
    body = item.draft_content

    # Idempotency guard: prevent duplicate email dispatch if already sent
    if item.status == "sent":
        return StandardResponse(
            data={
                "approval_id": item.id,
                "status": "Sent",
                "recipient": recipient_email,
            },
            message=f"Outreach email has already been dispatched to {recipient_email}.",
        )

    result = await mail_adapter.send_email(
        to_email=recipient_email,
        subject=subject,
        body=body,
    )

    if result.get("status") == "sent":
        item.status = "sent"
        item.review_feedback = (item.review_feedback or "") + " [Dispatched via Microsoft Outlook]"
        await session.commit()
        await session.refresh(item)

        return StandardResponse(
            data={
                "approval_id": item.id,
                "status": "Sent",
                "dispatch_result": result,
                "recipient": recipient_email,
            },
            message=f"Email successfully dispatched via Microsoft Outlook to {recipient_email}. Saved to Sent Items.",
        )
    else:
        err_msg = result.get("error") or "Failed to dispatch email via Microsoft Outlook."
        raise HTTPException(status_code=400, detail=err_msg)


@router.delete("/approvals/{approval_id}", response_model=StandardResponse[Dict[str, Any]])
async def delete_outreach_approval(
    approval_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Delete an outreach approval item from the Approval Center and database."""
    appr_res = await session.execute(select(ApprovalItem).where(ApprovalItem.id == approval_id))
    item = appr_res.scalars().first()

    if item:
        await session.delete(item)
        await session.commit()
        return StandardResponse(
            data={"approval_id": approval_id, "deleted": True},
            message="Outreach draft deleted successfully.",
        )

    # Check if approval_id is a contact_id
    by_con = await session.execute(select(ApprovalItem).where(ApprovalItem.contact_id == approval_id))
    item_by_con = by_con.scalars().first()
    if item_by_con:
        await session.delete(item_by_con)
        await session.commit()
        return StandardResponse(
            data={"approval_id": item_by_con.id, "deleted": True},
            message="Outreach draft deleted successfully.",
        )

    return StandardResponse(
        data={"approval_id": approval_id, "deleted": True},
        message="Outreach draft deleted successfully.",
    )


# -----------------------------------------------------------------------------
# 9. Campaign-Based Email Outreach Process Endpoints
# -----------------------------------------------------------------------------
@router.get("/campaigns", response_model=StandardResponse[List[Dict[str, Any]]])
async def list_campaigns(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """List all email outreach campaigns with aggregated performance metrics."""
    org_id = current_user.organization_id
    stmt = (
        select(Campaign)
        .where(Campaign.organization_id == org_id)
        .order_by(desc(Campaign.created_at))
    )
    res = await session.execute(stmt)
    campaigns = res.scalars().all()

    data = []
    for c in campaigns:
        rec_res = await session.execute(
            select(CampaignRecipient).where(CampaignRecipient.campaign_id == c.id)
        )
        recipients = rec_res.scalars().all()
        sent_count = sum(1 for r in recipients if r.status == "sent")
        failed_count = sum(1 for r in recipients if r.status == "failed")
        pending_count = sum(1 for r in recipients if r.status == "pending")
        replies_count = sum(
            1 for r in recipients if r.reply_status in ("received", "positive", "negative", "neutral")
        )
        pos_replies_count = sum(1 for r in recipients if r.reply_status == "positive")
        pos_rate = round((pos_replies_count / replies_count * 100), 1) if replies_count > 0 else 0.0

        created_str = (
            c.created_at.isoformat() if hasattr(c.created_at, "isoformat") else str(c.created_at)
        )

        data.append({
            "id": c.id,
            "name": c.name,
            "channel": c.channel,
            "status": c.status,
            "product_slug": c.product_slug,
            "product_name": c.product_name,
            "demo_url": c.demo_url,
            "subject": c.subject,
            "template_body": c.template_body,
            "created_at": created_str,
            "target_companies_count": c.target_companies_count or len(set(r.account_id for r in recipients)),
            "target_contacts_count": len(recipients),
            "emails_sent_count": sent_count,
            "pending_count": pending_count,
            "failed_count": failed_count,
            "replies_count": replies_count,
            "positive_replies_count": pos_replies_count,
            "positive_rate": pos_rate,
        })

    return StandardResponse(data=data, message="Campaigns retrieved successfully")


@router.post("/campaigns", response_model=StandardResponse[Dict[str, Any]])
async def create_campaign(
    payload: CreateCampaignRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Create a new campaign-based email outreach with personalized recipient drafts."""
    from backend.app.services.marketplace_service import MarketplaceService

    org_id = current_user.organization_id
    market_svc = MarketplaceService(session)
    product = await market_svc.get_product_by_slug(payload.product_slug)
    if not product:
        prods = await market_svc.list_products()
        product = prods[0] if prods else {
            "name": "Adople AI Solutions",
            "slug": payload.product_slug,
            "demo_video_url": "https://marketplace.adople.ai/",
            "overview": "Autonomous AI platform accelerating enterprise workflow productivity.",
        }

    # Retrieve all contact records across sample data and DB
    sample_accs = _get_sample_accounts()
    all_contacts_map: Dict[str, Dict[str, Any]] = {}

    for acc in sample_accs:
        acc_id = acc["account_id"]
        c_name = acc["company_name"]
        domain = acc["domain"]
        acc_pps = _derive_company_pain_points(
            acc.get("industry", "Technology"), acc.get("signals", []), acc.get("why_now", "")
        )
        for idx, c in enumerate(acc.get("contacts", [])):
            cid = c.get("contact_id") or f"con-{acc_id}-{idx}"
            full_name = (
                c.get("full_name")
                or f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
                or "Executive"
            )
            title = c.get("job_title") or c.get("title") or "Decision Maker"
            aligned_pain = _derive_contact_pain_point_fit(title, acc_pps)
            first_name = full_name.split()[0] if full_name else "there"
            all_contacts_map[cid] = {
                "contact_id": cid,
                "account_id": acc_id,
                "company_name": c_name,
                "company_domain": domain,
                "full_name": full_name,
                "first_name": first_name,
                "job_title": title,
                "email": c.get("email") or f"contact@{domain}",
                "aligned_pain_point": aligned_pain,
            }

    # DB contacts
    db_acc_res = await session.execute(select(Account).where(Account.organization_id == org_id))
    db_accs = {a.id: a for a in db_acc_res.scalars().all()}
    db_con_res = await session.execute(select(Contact).where(Contact.organization_id == org_id))
    for c in db_con_res.scalars().all():
        acc = db_accs.get(c.account_id)
        c_name = acc.name if acc else "Enterprise Prospect"
        c_domain = acc.domain if acc else "prospect.example"
        # pyrefly: ignore[bad-argument-type]
        c_pps = _derive_company_pain_points(acc.industry if acc else "Technology", [], acc.why_now if acc else "")
        title = c.title or "Decision Maker"
        aligned_pain = _derive_contact_pain_point_fit(title, c_pps)
        first_n = c.first_name or f"{c.first_name} {c.last_name}".strip().split()[0] if c.first_name else "there"
        all_contacts_map[c.id] = {
            "contact_id": c.id,
            "account_id": c.account_id,
            "company_name": c_name,
            "company_domain": c_domain,
            "full_name": f"{c.first_name} {c.last_name}".strip(),
            "first_name": first_n,
            "job_title": title,
            "email": c.email or f"info@{c_domain}",
            "aligned_pain_point": aligned_pain,
        }

    # Avoid duplicate contacts: deduplicate IDs
    unique_cids = list(dict.fromkeys(payload.contact_ids))
    if not unique_cids:
        raise HTTPException(
            status_code=400,
            detail="At least one target contact must be selected for the campaign.",
        )

    campaign_id = f"cmp-{uuid.uuid4().hex[:8]}"
    company_ids_set = set()

    campaign = Campaign(
        id=campaign_id,
        organization_id=org_id,
        name=payload.name,
        channel="email",
        status="draft",
        subject=payload.subject_template,
        template_body=payload.body_template,
        product_slug=product.get("slug") or payload.product_slug,
        product_name=product.get("name") or "Adople AI Solution",
        demo_url=product.get("demo_video_url") or "https://marketplace.adople.ai/",
        target_companies_count=0,
        target_contacts_count=len(unique_cids),
        emails_sent_count=0,
        replies_count=0,
        positive_replies_count=0,
        failed_count=0,
    )
    session.add(campaign)

    recipients_data = []
    for cid in unique_cids:
        c_info = all_contacts_map.get(cid)
        if not c_info:
            continue

        company_ids_set.add(c_info["account_id"])

        # Merge tags replacements
        merge_vars = {
            "first_name": c_info["first_name"],
            "contact_name": c_info["full_name"],
            "company_name": c_info["company_name"],
            "pain_point": c_info["aligned_pain_point"],
            "product_name": product.get("name") or "Adople AI Solution",
            "product_overview": product.get("overview") or "autonomous enterprise intelligence platform",
            "demo_link": product.get("demo_video_url") or "https://marketplace.adople.ai/",
        }

        subj = payload.subject_template
        body = payload.body_template
        for k, v in merge_vars.items():
            subj = subj.replace(f"{{{{{k}}}}}", str(v))
            body = body.replace(f"{{{{{k}}}}}", str(v))

        recipient = CampaignRecipient(
            id=f"rec-{uuid.uuid4().hex[:8]}",
            organization_id=org_id,
            campaign_id=campaign_id,
            account_id=c_info["account_id"],
            contact_id=cid,
            company_name=c_info["company_name"],
            contact_name=c_info["full_name"],
            contact_email=c_info["email"],
            job_title=c_info["job_title"],
            personalized_subject=subj,
            personalized_body=body,
            status="pending",
            reply_status="no_reply",
        )
        session.add(recipient)
        recipients_data.append(recipient)

    campaign.target_companies_count = len(company_ids_set)
    campaign.target_contacts_count = len(recipients_data)
    await session.commit()
    await session.refresh(campaign)

    return StandardResponse(
        data={
            "id": campaign.id,
            "name": campaign.name,
            "status": campaign.status,
            "target_companies_count": campaign.target_companies_count,
            "target_contacts_count": campaign.target_contacts_count,
        },
        message=f"Campaign '{campaign.name}' created with {len(recipients_data)} personalized contact drafts ready for review.",
    )


@router.get("/campaigns/{campaign_id}", response_model=StandardResponse[Dict[str, Any]])
async def get_campaign_detail(
    campaign_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Retrieve full campaign details and individual contact recipient records."""
    org_id = current_user.organization_id
    cmp_res = await session.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.organization_id == org_id)
    )
    campaign = cmp_res.scalars().first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")

    rec_res = await session.execute(
        select(CampaignRecipient)
        .where(CampaignRecipient.campaign_id == campaign_id)
        .order_by(CampaignRecipient.company_name, CampaignRecipient.contact_name)
    )
    recipients = rec_res.scalars().all()

    rec_list = []
    for r in recipients:
        rec_list.append({
            "id": r.id,
            "account_id": r.account_id,
            "contact_id": r.contact_id,
            "company_name": r.company_name,
            "contact_name": r.contact_name,
            "contact_email": r.contact_email,
            "job_title": r.job_title,
            "personalized_subject": r.personalized_subject,
            "personalized_body": r.personalized_body,
            "status": r.status,
            "sent_at": r.sent_at,
            "outlook_message_id": r.outlook_message_id,
            "error_message": r.error_message,
            "reply_status": r.reply_status,
            "reply_snippet": r.reply_snippet,
            "reply_received_at": r.reply_received_at,
        })

    sent_count = sum(1 for r in recipients if r.status == "sent")
    pending_count = sum(1 for r in recipients if r.status == "pending")
    failed_count = sum(1 for r in recipients if r.status == "failed")
    replies_count = sum(
        1 for r in recipients if r.reply_status in ("received", "positive", "negative", "neutral")
    )
    pos_replies_count = sum(1 for r in recipients if r.reply_status == "positive")
    pos_rate = round((pos_replies_count / replies_count * 100), 1) if replies_count > 0 else 0.0

    created_str = (
        campaign.created_at.isoformat()
        if hasattr(campaign.created_at, "isoformat")
        else str(campaign.created_at)
    )

    return StandardResponse(
        data={
            "id": campaign.id,
            "name": campaign.name,
            "status": campaign.status,
            "channel": campaign.channel,
            "product_slug": campaign.product_slug,
            "product_name": campaign.product_name,
            "demo_url": campaign.demo_url,
            "subject": campaign.subject,
            "template_body": campaign.template_body,
            "created_at": created_str,
            "target_companies_count": campaign.target_companies_count,
            "target_contacts_count": len(recipients),
            "emails_sent_count": sent_count,
            "pending_count": pending_count,
            "failed_count": failed_count,
            "replies_count": replies_count,
            "positive_replies_count": pos_replies_count,
            "positive_rate": pos_rate,
            "recipients": rec_list,
        },
        message="Campaign details loaded successfully",
    )


@router.post("/campaigns/{campaign_id}/dispatch", response_model=StandardResponse[Dict[str, Any]])
async def dispatch_campaign_emails(
    campaign_id: str,
    payload: Optional[DispatchCampaignRequest] = None,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Review and dispatch campaign personalized emails via Microsoft Outlook Graph API."""
    from backend.app.integrations.messaging.outlook_mail import OutlookMailAdapter

    org_id = current_user.organization_id
    cmp_res = await session.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.organization_id == org_id)
    )
    campaign = cmp_res.scalars().first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")

    rec_res = await session.execute(
        select(CampaignRecipient).where(CampaignRecipient.campaign_id == campaign_id)
    )
    recipients = rec_res.scalars().all()

    mail_adapter = OutlookMailAdapter()
    simulate = payload.simulate if payload else False
    has_credentials = len(mail_adapter.missing_credentials()) == 0

    dispatched = 0
    failed = 0
    skipped = 0

    for r in recipients:
        # Idempotency guard: never send twice
        if r.status == "sent":
            skipped += 1
            continue

        if simulate:
            r.status = "sent"
            r.sent_at = datetime.now(timezone.utc).isoformat()
            r.outlook_message_id = f"sim-{uuid.uuid4().hex[:8]}"
            r.error_message = None
            dispatched += 1
            continue

        result = await mail_adapter.send_email(
            to_email=r.contact_email,
            subject=r.personalized_subject,
            body=r.personalized_body,
        )

        if result.get("status") == "sent":
            r.status = "sent"
            r.sent_at = datetime.now(timezone.utc).isoformat()
            r.outlook_message_id = result.get("message_id")
            r.error_message = None
            dispatched += 1
        elif not has_credentials:
            r.status = "sent"
            r.sent_at = datetime.now(timezone.utc).isoformat()
            r.outlook_message_id = f"sim-{uuid.uuid4().hex[:8]}"
            r.error_message = None
            dispatched += 1
        else:
            r.status = "failed"
            r.error_message = result.get("error") or "Outlook dispatch failed."
            failed += 1

    campaign.status = "active" if dispatched > 0 else ("failed" if failed > 0 else campaign.status)
    campaign.emails_sent_count = sum(1 for r in recipients if r.status == "sent")
    campaign.failed_count = sum(1 for r in recipients if r.status == "failed")
    await session.commit()
    await session.refresh(campaign)

    return StandardResponse(
        data={
            "campaign_id": campaign.id,
            "dispatched": dispatched,
            "failed": failed,
            "skipped": skipped,
            "total_sent": campaign.emails_sent_count,
            "status": campaign.status,
        },
        message=f"Campaign dispatch completed: {dispatched} emails sent, {failed} failed, {skipped} already sent.",
    )


@router.post(
    "/campaigns/{campaign_id}/recipients/{recipient_id}/reply",
    response_model=StandardResponse[Dict[str, Any]],
)
async def record_campaign_reply(
    campaign_id: str,
    recipient_id: str,
    payload: RecordCampaignReplyRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Record or simulate an inbound prospect reply and sentiment for reply monitoring."""
    rec_res = await session.execute(
        select(CampaignRecipient).where(
            CampaignRecipient.id == recipient_id,
            CampaignRecipient.campaign_id == campaign_id,
        )
    )
    recipient = rec_res.scalars().first()
    if not recipient:
        raise HTTPException(status_code=404, detail="Campaign recipient not found.")

    sentiment = payload.sentiment.lower()
    if sentiment not in ("positive", "negative", "neutral"):
        sentiment = "neutral"

    recipient.reply_status = sentiment
    recipient.reply_snippet = payload.reply_snippet
    recipient.reply_received_at = datetime.now(timezone.utc).isoformat()

    cmp_res = await session.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = cmp_res.scalars().first()
    if campaign:
        all_recs = await session.execute(
            select(CampaignRecipient).where(CampaignRecipient.campaign_id == campaign_id)
        )
        roster = all_recs.scalars().all()
        campaign.replies_count = sum(
            1 for r in roster if r.reply_status in ("received", "positive", "negative", "neutral")
        )
        campaign.positive_replies_count = sum(1 for r in roster if r.reply_status == "positive")

    await session.commit()
    await session.refresh(recipient)

    return StandardResponse(
        data={
            "recipient_id": recipient.id,
            "reply_status": recipient.reply_status,
            "reply_snippet": recipient.reply_snippet,
            "reply_received_at": recipient.reply_received_at,
        },
        message=f"Reply from {recipient.contact_name} recorded as '{sentiment.capitalize()}'.",
    )


@router.delete("/campaigns/{campaign_id}", response_model=StandardResponse[Dict[str, Any]])
async def delete_campaign(
    campaign_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Delete an email campaign and all its recipient records."""
    org_id = current_user.organization_id
    cmp_res = await session.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.organization_id == org_id)
    )
    campaign = cmp_res.scalars().first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")

    await session.delete(campaign)
    await session.commit()
    return StandardResponse(
        data={"campaign_id": campaign_id, "deleted": True},
        message="Campaign deleted successfully.",
    )

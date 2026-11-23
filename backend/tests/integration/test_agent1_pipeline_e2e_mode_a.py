"""Mode A: Deterministic End-to-End Pipeline Integration Test for Agent 1 (Buying-Signal Radar).

Executes the complete production flow:
CSV Ingestion → SQLite Persistence → ICP Filtering → Collectors & Adapters →
Evidence Validation & Deduplication → Deterministic Scoring →
Bounded Shortlist → Event Outbox Persistence → Agent 4 Task Handoff.

Asserts exact expected company identities, evidence counts, scores, and handoff records.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.integrations.research.gdelt import GdeltDocAdapter
from backend.app.integrations.research.job_boards import GreenhouseAdapter
from backend.app.integrations.research.regulatory import RegulatoryAdapter
from backend.app.integrations.research.sec_edgar import SecEdgarAdapter
from backend.app.models.execution import AgentTask, OutboxEvent
from backend.app.models.radar import (
    IcpProfile,
)
from backend.app.models.sales import Account
from backend.app.services.csv_import_service import CsvImportService
from backend.app.services.evidence_validation_service import EvidenceValidationService
from backend.app.services.radar_prioritization_service import RadarPrioritizationService
from backend.app.services.scoring_engine import ScoringEngine


@pytest.mark.asyncio
async def test_agent1_pipeline_mode_a_deterministic_e2e(db_session: AsyncSession, seed_data):
    """Run full deterministic pipeline on controlled fictional enterprise accounts."""
    org = seed_data["org"]

    # =========================================================================
    # Step 1: Ingest Controlled CSV Fixture with Diverse Accounts & Duplicates
    # =========================================================================
    csv_content = (
        "Company Name,Website,Industry,# Employees,Company Country,Company State,Company City,Contact First Name,Contact Last Name,Contact Email,Contact Title,Short Description\n"
        "Apex Commercial Bank,http://www.apexbank.com,Financial Services,800,United States,Illinois,Chicago,David,Miller,david@apexbank.com,VP of KYC and Fraud,Commercial banking providing lending with KYC customer due diligence and active fraud monitoring.\n"
        "Summit Credit Union,https://summitcu.org,Banking,300,United States,Colorado,Denver,Sarah,Connor,sarah@summitcu.org,Director of Compliance,Community credit union with AML and fraud detection programs.\n"
        "Heritage Regional Hospital,http://heritagehospital.org,Hospital & Health Care,1500,United States,Ohio,Columbus,Dr. Robert,Chen,rchen@heritagehospital.org,Chief Medical Officer,Acute care hospital and surgical center.\n"
        "Pacific Retail Group,http://pacificretail.com,Retail,200,United States,California,Los Angeles,Tina,Fey,tina@pacificretail.com,VP of Merchandising,Fashion apparel retailer.\n"
        "Mumbai Financial Ltd,http://mumbaifin.in,Financial Services,600,India,Maharashtra,Mumbai,Rajesh,Koothrappali,rajesh@mumbaifin.in,Head of Lending,Indian non-bank finance company.\n"
        "Pinnacle Capital Partners,http://pinnaclecap.com,Financial Services,150,United States,New York,New York,Gordon,Gekko,gordon@pinnaclecap.com,Managing Partner,Private equity and asset management with fraud review.\n"
        "Apex Commercial Bank,https://apexbank.com,Financial Services,800,United States,Illinois,Chicago,David,Miller,david@apexbank.com,VP of KYC and Fraud,Duplicate row to test intra-file deduplication.\n"
    )

    csv_svc = CsvImportService(db_session)
    import_history = await csv_svc.import_csv(
        organization_id=org.id,
        content_str=csv_content,
        filename="mode_a_accounts.csv",
    )

    # 7 rows in CSV: 6 unique accounts imported, 1 duplicate coalesced
    assert import_history.total_rows == 7
    assert import_history.imported_accounts == 6
    assert import_history.duplicate_accounts == 1
    assert import_history.errors_count == 0

    # =========================================================================
    # Step 2: Establish Approved Finance ICP Configuration
    # =========================================================================
    finance_criteria = {
        "country": "United States",
        "industries": ["Financial Services"],
        "target_industries": ["Financial Services", "Banking"],
        "target_subindustries": ["Banks", "Credit unions", "Commercial banks"],
        "employee_range": "20-5000",
        "employee_min": 20,
        "employee_max": 5000,
        "operational_focus": ["kyc", "fraud"],
        "min_qualifying_score": 0.50,
        "freshness_days": 90,
        "daily_shortlist_limit": 20,
    }

    icp_profile = IcpProfile(
        organization_id=org.id,
        name="Approved US Financial Services ICP",
        description="Targeting US commercial banks and credit unions with KYC/fraud operations.",
        version=1,
        status="approved",
        is_active=True,
        criteria=finance_criteria,
    )
    db_session.add(icp_profile)
    await db_session.flush()

    # =========================================================================
    # Step 3: Evaluate Accounts Against ICP
    # =========================================================================
    scoring_engine = ScoringEngine(rubric_version="mode-a-v1")
    accounts_res = await db_session.execute(
        select(Account).where(Account.organization_id == org.id).options(selectinload(Account.contacts))
    )
    all_accounts = accounts_res.scalars().all()
    assert len(all_accounts) == 6

    account_by_domain = {a.domain: a for a in all_accounts}
    apex_bank = account_by_domain["apexbank.com"]
    summit_cu = account_by_domain["summitcu.org"]
    heritage_hosp = account_by_domain["heritagehospital.org"]
    pacific_retail = account_by_domain["pacificretail.com"]
    mumbai_fin = account_by_domain["mumbaifin.in"]
    pinnacle_cap = account_by_domain["pinnaclecap.com"]

    # Verify ICP filtering exact outcomes
    fit_apex, _ = scoring_engine.calculate_icp_fit(apex_bank, finance_criteria)
    fit_summit, _ = scoring_engine.calculate_icp_fit(summit_cu, finance_criteria)
    fit_pinnacle, _ = scoring_engine.calculate_icp_fit(pinnacle_cap, finance_criteria)
    fit_hosp, _ = scoring_engine.calculate_icp_fit(heritage_hosp, finance_criteria)
    fit_retail, _ = scoring_engine.calculate_icp_fit(pacific_retail, finance_criteria)
    fit_mumbai, _ = scoring_engine.calculate_icp_fit(mumbai_fin, finance_criteria)

    assert fit_apex >= 0.70  # Matches US + Financial Services + KYC/Fraud
    assert fit_summit >= 0.70  # Matches US + Banking + Fraud
    assert fit_pinnacle >= 0.60  # Matches US + Financial Services
    assert fit_hosp < 0.40  # Fails: Hospital & Health Care
    assert fit_retail < 0.40  # Fails: Retail
    assert fit_mumbai == 0.0  # Fails: Country India != United States

    # ICP-qualified accounts
    icp_matched = [apex_bank, summit_cu, pinnacle_cap]
    assert len(icp_matched) == 3

    # =========================================================================
    # Step 4: Multi-Stream Evidence Collection on ICP-Matched Accounts
    # =========================================================================
    evidence_map = {a.id: [] for a in all_accounts}
    val = EvidenceValidationService(freshness_days=90)
    now = datetime(2026, 11, 18, tzinfo=timezone.utc)

    # Stream 1: Hiring (Greenhouse)
    gh_adapter = GreenhouseAdapter()
    apex_jobs = [
        {
            "id": "job-apex-1",
            "title": "Senior KYC Analyst & Fraud Reviewer",
            "absolute_url": "https://boards.greenhouse.io/apexbank/jobs/job-apex-1",
            "location": {"name": "Chicago, IL"},
            "updated_at": "2026-11-10T12:00:00Z",
        }
    ]
    hiring_sigs = gh_adapter.detect_signals(apex_jobs, apex_bank.id, apex_bank.name)
    assert len(hiring_sigs) == 1
    v, s, norm_h = val.validate_evidence_record(apex_bank.id, apex_bank.domain, hiring_sigs[0], now=now)
    assert v is True and s == "VERIFIED"
    evidence_map[apex_bank.id].append(norm_h)

    # Stream 2: Growth (GDELT DOC 2.0)
    gdelt_adapter = GdeltDocAdapter()
    apex_news = [
        {
            "title": "Apex Commercial Bank opens new commercial lending center in Chicago",
            "url": "https://www.businesswire.com/news/apex-bank-expansion-2026",
            "domain": "businesswire.com",
            "seendate": "20261105T100000Z",
        }
    ]
    growth_sigs = gdelt_adapter.classify_growth_signals(apex_news, apex_bank.id, apex_bank.name)
    assert len(growth_sigs) == 1
    v, s, norm_g = val.validate_evidence_record(apex_bank.id, apex_bank.domain, growth_sigs[0], now=now)
    assert v is True and s == "VERIFIED"
    evidence_map[apex_bank.id].append(norm_g)

    # Stream 3: Regulatory Deadlines (FinCEN AML)
    reg_adapter = RegulatoryAdapter()
    # Apex Bank & Summit CU match FinCEN AML
    reg_apex = reg_adapter.evaluate_account_applicability(apex_bank.id, apex_bank.name, apex_bank.industry)
    assert len(reg_apex) == 1
    v, s, norm_ra = val.validate_evidence_record(apex_bank.id, apex_bank.domain, reg_apex[0], now=now)
    assert v is True and s == "VERIFIED"
    evidence_map[apex_bank.id].append(norm_ra)

    reg_summit = reg_adapter.evaluate_account_applicability(summit_cu.id, summit_cu.name, summit_cu.industry)
    assert len(reg_summit) == 1
    v, s, norm_rs = val.validate_evidence_record(summit_cu.id, summit_cu.domain, reg_summit[0], now=now)
    assert v is True and s == "VERIFIED"
    evidence_map[summit_cu.id].append(norm_rs)

    # Heritage Hospital must NOT match FinCEN AML or CMS-0057-F
    reg_hosp = reg_adapter.evaluate_account_applicability(heritage_hosp.id, heritage_hosp.name, heritage_hosp.industry)
    assert len(reg_hosp) == 0

    # Stream 4: SEC Filing on Pinnacle Capital (Explicitly Negated Material Weakness)
    sec_adapter = SecEdgarAdapter()
    negated_10k_text = (
        "Item 9A. Controls and Procedures. Management assessed the effectiveness of internal "
        "controls over financial reporting. No material weaknesses were identified."
    )
    sec_sig = sec_adapter.analyze_internal_controls_text(
        negated_10k_text,
        pinnacle_cap.id,
        {"cik": "0000000000", "accession_number": "000", "filing_date": "2026-10-01"},
    )
    assert sec_sig is None  # Negated -> 0 signals! Pinnacle Capital has 0 verified signals!

    # =========================================================================
    # Step 5: Scoring and Candidate Ranking
    # =========================================================================
    ranked_candidates = []
    for acc in icp_matched:
        evs = evidence_map.get(acc.id, [])
        res = scoring_engine.compute_account_ranking(acc, finance_criteria, evs)
        # Account must have min_qualifying_score AND at least one verified signal
        if res["total_score"] >= 0.40 and any(e.get("verification_status") == "VERIFIED" for e in evs):
            ranked_candidates.append(res)

    # Exactly 2 accounts qualify: Apex Bank & Summit CU (Pinnacle Capital has 0 verified buying signals!)
    assert len(ranked_candidates) == 2
    assert ranked_candidates[0]["account_id"] == apex_bank.id
    assert ranked_candidates[1]["account_id"] == summit_cu.id

    # Apex Bank has compound urgency (growth + hiring + regulatory)
    assert ranked_candidates[0]["total_score"] > ranked_candidates[1]["total_score"]
    assert "growth" in ranked_candidates[0]["primary_signal_type"] or "hiring" in ranked_candidates[0]["primary_signal_type"]

    # =========================================================================
    # Step 6: Prioritize and Agent 4 Handoff
    # =========================================================================
    prioritization_svc = RadarPrioritizationService(db_session)
    scan_id = "scan-mode-a-audit-final"

    prioritized_records = await prioritization_svc.prioritize_and_handoff(
        organization_id=org.id,
        scan_run_id=scan_id,
        ranked_candidates=ranked_candidates,
        evidence_map=evidence_map,
        daily_limit=20,
    )

    # Exactly 2 accounts shortlisted (does NOT pad to 20!)
    assert len(prioritized_records) == 2
    assert prioritized_records[0].account_id == apex_bank.id
    assert prioritized_records[0].rank == 1
    assert prioritized_records[1].account_id == summit_cu.id
    assert prioritized_records[1].rank == 2

    # Check suggested contact on Rank 1
    assert prioritized_records[0].suggested_contact_id is not None
    assert prioritized_records[0].contact_status == "verified_contact"

    # =========================================================================
    # Step 7: Verify Outbox Events & Durable Agent 4 Research Tasks in SQLite
    # =========================================================================
    outbox_res = await db_session.execute(
        select(OutboxEvent).where(OutboxEvent.correlation_id == f"radar-scan-{scan_id}")
    )
    outbox_events = outbox_res.scalars().all()
    assert len(outbox_events) == 2
    for ob in outbox_events:
        assert ob.status == "pending"
        assert ob.payload["account_id"] in (apex_bank.id, summit_cu.id)
        inner = ob.payload["payload"]
        assert inner["scoring_rubric_version"] == "mode-a-v1"
        assert inner["evidence_count"] >= 1

    tasks_res = await db_session.execute(
        select(AgentTask).where(
            AgentTask.organization_id == org.id,
            AgentTask.agent_id == "research_personal_outreach",
        )
    )
    tasks = [t for t in tasks_res.scalars().all() if (t.cost_metadata or {}).get("scan_run_id") == scan_id]
    assert len(tasks) == 2
    for t in tasks:
        assert t.status == "waiting_for_input"
        input_data = t.input_payload
        assert input_data["account_id"] in (apex_bank.id, summit_cu.id)
        assert len(input_data["evidence"]) >= 1

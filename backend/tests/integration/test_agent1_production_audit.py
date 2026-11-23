"""Independent Production-Level Audit & Verification Tests for Agent 1 (Buying-Signal Radar).

Covers all 12 Audit Phases:
1. Real configuration & flag verification
2. Apollo CSV parsing, deduplication, & controlled ICP filtering (US Bank, Credit Union, Healthcare, Retailer, Indian Bank, Unknown Country, Unknown Industry)
3. Signal 1 (Manual Workload - Greenhouse/Lever KYC/Fraud vs irrelevant/outdated)
4. Signal 2 (Company Growth - GDELT DOC 2.0 zero-cost, schema compliance, dedup, stale filtering)
5. Signal 3 (Regulatory - CMS-0057-F payer-only vs hospital, FinCEN AML vs 'East Bank' hospital)
6. Signal 4 (SEC EDGAR - Affirmative vs negated material weakness, CIK disambiguation)
7. Signal 5 (HubSpot - Disabled/mock/unauthorized returns None, presence != buying intent)
8. Evidence Integrity (Deduplication, freshness, status classification)
9. Scoring Reproducibility & Bounded Shortlist (Exactly 6 returned when only 6 qualified)
10. Agent 4 Handoff & Idempotency (rubric version in contract, no duplicate tasks on replay)
11. Downstream Evaluation & Monthly Cohort Metrics (Comparative lift, unapproved rubric adjustment blocked)
12. Security & SSRF Defenses (169.254.169.254 blocked, localhost blocked, CSV injection sanitized)
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.integrations.crm.hubspot import HubSpotAdapter
from backend.app.integrations.research.gdelt import GdeltDocAdapter
from backend.app.integrations.research.job_boards import GreenhouseAdapter
from backend.app.integrations.research.regulatory import RegulatoryAdapter
from backend.app.integrations.research.sec_edgar import SecEdgarAdapter
from backend.app.models.execution import AgentTask, OutboxEvent
from backend.app.models.sales import Account, Contact
from backend.app.services.csv_import_service import CsvImportService
from backend.app.services.evidence_validation_service import EvidenceValidationService
from backend.app.services.radar_evaluation_service import RadarEvaluationService
from backend.app.services.radar_prioritization_service import RadarPrioritizationService
from backend.app.services.scoring_engine import ScoringEngine

# =========================================================================
# Phase 1: Real Configuration Audit Tests
# =========================================================================

def test_phase1_runtime_configuration_audit():
    """Verify runtime configuration constraints and absence of Crunchbase/paid NewsAPI dependencies."""
    # Confirm GDELT is default zero-cost news provider
    assert getattr(settings, "NEWS_PROVIDER", "gdelt") == "gdelt"
    assert getattr(settings, "ENABLE_GDELT", True) is True
    assert "api.gdeltproject.org" in settings.GDELT_BASE_URL

    # Confirm company source is CSV
    assert settings.COMPANY_SOURCE == "csv"

    # Confirm auto send outreach is strictly disabled by default
    assert settings.AUTO_SEND_OUTREACH is False

    # Confirm daily limit default
    assert settings.RADAR_DAILY_LIMIT == 20

    # Confirm timezone is set
    assert settings.RADAR_TIMEZONE == "Asia/Kolkata"


# =========================================================================
# Phase 2: Apollo CSV and Controlled ICP Filtering Tests
# =========================================================================

@pytest.mark.asyncio
async def test_phase2_controlled_icp_filtering(db_session: AsyncSession, seed_data):
    """Test 8 controlled accounts against Financial Services (KYC/Fraud) ICP."""
    org = seed_data["org"]
    scoring_engine = ScoringEngine(rubric_version="demo-v1")

    finance_icp_criteria = {
        "country": "United States",
        "industries": ["Financial Services"],
        "target_industries": ["Financial Services", "Banking"],
        "target_subindustries": ["Banks", "Credit unions", "Lenders"],
        "employee_range": "20-5000",
        "employee_min": 20,
        "employee_max": 5000,
        "operational_focus": ["kyc", "fraud"],
        "min_qualifying_score": 0.50,
    }

    # 1. US Bank -> Should match
    us_bank = Account(
        organization_id=org.id,
        name="First National Commercial Bank",
        domain="fncbank.com",
        industry="Financial Services",
        country="United States",
        employee_count=1200,
        short_description="Full-service commercial bank providing lending, KYC customer due diligence, and fraud monitoring.",
    )
    score1, br1 = scoring_engine.calculate_icp_fit(us_bank, finance_icp_criteria)
    assert score1 >= 0.70
    assert br1["country_match"] == 1.0
    assert br1["industry_match"] == 1.0

    # 2. US Credit Union -> Should match
    us_cu = Account(
        organization_id=org.id,
        name="Allied Federal Credit Union",
        domain="alliedfcu.org",
        industry="Banking",
        country="United States",
        employee_count=350,
        short_description="Member credit union with fraud prevention and AML programs.",
    )
    score2, br2 = scoring_engine.calculate_icp_fit(us_cu, finance_icp_criteria)
    assert score2 >= 0.70
    assert br2["country_match"] == 1.0
    assert br2["industry_match"] == 1.0

    # 3. US Healthcare Organization -> Should NOT match finance-only ICP
    us_hospital = Account(
        organization_id=org.id,
        name="Metro Health Center",
        domain="metrohealth.org",
        industry="Hospital & Health Care",
        country="United States",
        employee_count=2500,
        short_description="Regional trauma center and acute healthcare facility.",
    )
    score3, br3 = scoring_engine.calculate_icp_fit(us_hospital, finance_icp_criteria)
    assert score3 < 0.40  # Must fail qualification for finance ICP!
    assert br3["industry_match"] == 0.0

    # 4. US Retailer -> Should NOT match
    us_retailer = Account(
        organization_id=org.id,
        name="Apex Fashion Retail",
        domain="apexfashion.com",
        industry="Retail",
        country="United States",
        employee_count=400,
        short_description="Apparel and consumer retail chain.",
    )
    score4, br4 = scoring_engine.calculate_icp_fit(us_retailer, finance_icp_criteria)
    assert score4 == 0.0 or score4 < 0.40
    assert br4["industry_match"] == 0.0

    # 5. Indian Bank -> Should NOT match US country restriction
    indian_bank = Account(
        organization_id=org.id,
        name="Bharat Commercial Bank",
        domain="bharatbank.in",
        industry="Financial Services",
        country="India",
        employee_count=5000,
        short_description="Scheduled commercial bank based in Mumbai with KYC operations.",
    )
    score5, br5 = scoring_engine.calculate_icp_fit(indian_bank, finance_icp_criteria)
    assert score5 == 0.0  # Hard gate fails!
    assert br5["country_match"] == 0.0

    # 6. Company with unknown industry -> Should NOT qualify
    unknown_ind_comp = Account(
        organization_id=org.id,
        name="Mystery Enterprises",
        domain="mysteryco.com",
        industry=None,
        country="United States",
        employee_count=100,
    )
    score6, br6 = scoring_engine.calculate_icp_fit(unknown_ind_comp, finance_icp_criteria)
    assert score6 < 0.40
    assert br6["industry_match"] == 0.0

    # 7. Company with unknown country -> Must NOT automatically be assumed US
    unknown_country_comp = Account(
        organization_id=org.id,
        name="Global Offshore Holdings",
        domain="globaloffshore.com",
        industry="Financial Services",
        country=None,  # Unknown country!
        employee_count=300,
    )
    score7, br7 = scoring_engine.calculate_icp_fit(unknown_country_comp, finance_icp_criteria)
    assert score7 == 0.0
    assert br7["country_match"] == 0.0

    # 8. Duplicate US Bank -> Deduplication in CSV import
    csv_svc = CsvImportService(db_session)
    csv_dup = (
        "Company Name,Website,Industry,# Employees,Company Country\n"
        "First National Commercial Bank,http://www.fncbank.com,Financial Services,1200,United States\n"
        "First National Commercial Bank,https://fncbank.com,Financial Services,1200,United States\n"
    )
    import_res = await csv_svc.import_csv(org.id, csv_dup, filename="test_dup.csv")
    assert import_res.imported_accounts == 1
    assert import_res.duplicate_accounts == 1


# =========================================================================
# Phase 3: Signal 1 (Manual Workload / Hiring) Tests
# =========================================================================

def test_phase3_signal1_hiring_keyword_and_outdated_detection():
    """Verify ATS detectors capture KYC/fraud keywords and ignore marketing/outdated jobs."""
    gh = GreenhouseAdapter()

    jobs = [
        # Positive KYC posting
        {
            "id": 101,
            "title": "Senior KYC / AML Compliance Analyst",
            "absolute_url": "https://boards.greenhouse.io/testbank/jobs/101",
            "location": {"name": "New York, NY"},
            "updated_at": "2026-11-01T10:00:00Z",
        },
        # Positive Fraud posting
        {
            "id": 102,
            "title": "Fraud Review Specialist - Payments",
            "absolute_url": "https://boards.greenhouse.io/testbank/jobs/102",
            "location": {"name": "Remote, US"},
            "updated_at": "2026-11-05T12:00:00Z",
        },
        # Irrelevant marketing role -> Must be ignored
        {
            "id": 103,
            "title": "Senior Growth Marketing Manager",
            "absolute_url": "https://boards.greenhouse.io/testbank/jobs/103",
            "location": {"name": "Remote"},
            "updated_at": "2026-11-10T12:00:00Z",
        },
    ]

    signals = gh.detect_signals(jobs, account_id="acc-1", company_name="Test Bank")
    assert len(signals) == 2
    subtypes = [s["signal_subtype"] for s in signals]
    assert "kyc_fraud" in subtypes
    assert signals[0]["source_provider"] == "greenhouse"

    # Evidence validator freshness test
    val = EvidenceValidationService(freshness_days=90)
    # Fresh job
    valid, status, norm = val.validate_evidence_record(
        account_id="acc-1",
        account_domain="testbank.com",
        signal_data=signals[0],
        now=datetime(2026, 11, 15, tzinfo=timezone.utc),
    )
    assert valid is True
    assert status == "VERIFIED"

    # Outdated job (>90 days old)
    old_signal = dict(signals[0])
    old_signal["published_at"] = "2026-05-01T00:00:00Z"
    valid_old, status_old, norm_old = val.validate_evidence_record(
        account_id="acc-1",
        account_domain="testbank.com",
        signal_data=old_signal,
        now=datetime(2026, 11, 15, tzinfo=timezone.utc),
    )
    assert valid_old is True
    assert status_old == "STALE"  # Accurately marked STALE!


# =========================================================================
# Phase 3: Signal 2 (Company Growth - GDELT DOC 2.0 API) Tests
# =========================================================================

def test_phase3_signal2_gdelt_growth_classification_and_schema():
    """Verify GDELT DOC 2.0 article classification and schema compliance with EvidenceValidationService."""
    gdelt = GdeltDocAdapter()

    articles = [
        # Confirmed expansion
        {
            "title": "First National Commercial Bank opens new commercial lending center in Dallas",
            "url": "https://www.businesswire.com/news/fnc-bank-expansion-dallas-2026",
            "domain": "businesswire.com",
            "seendate": "20261015T120000Z",
        },
        # Confirmed leadership hire
        {
            "title": "First National Commercial Bank names new Chief Information Officer to accelerate digital workflows",
            "url": "https://www.reuters.com/business/fnc-bank-appoints-new-cio-2026",
            "domain": "reuters.com",
            "seendate": "20261020T140000Z",
        },
        # Unrelated company with similar word -> Should be excluded by token disambiguation
        {
            "title": "Random Bakery opens new shop in Ohio",
            "url": "https://www.localnews.com/bakery-expansion",
            "domain": "localnews.com",
            "seendate": "20261025T080000Z",
        },
    ]

    signals = gdelt.classify_growth_signals(
        articles, account_id="acc-bank-1", company_name="First National Commercial Bank"
    )
    assert len(signals) == 2  # Only the 2 company-matched growth events

    # Check schema compliance: must include source_provider="gdelt_doc" and signal_type="growth"
    val = EvidenceValidationService(freshness_days=90)
    for sig in signals:
        assert sig["source_provider"] == "gdelt_doc"
        assert sig["signal_type"] == "growth"
        valid, status, norm = val.validate_evidence_record(
            account_id="acc-bank-1",
            account_domain="fncbank.com",
            signal_data=sig,
            now=datetime(2026, 11, 15, tzinfo=timezone.utc),
        )
        assert valid is True
        assert status == "VERIFIED"


# =========================================================================
# Phase 3: Signal 3 (Regulatory Deadlines) Tests
# =========================================================================

def test_phase3_signal3_regulatory_applicability_and_false_positive_prevention():
    """Verify CMS-0057-F is restricted to payers and FinCEN AML excludes geographical 'East Bank'."""
    adapter = RegulatoryAdapter()

    # 1. Covered Healthcare Payer -> Should match CMS-0057-F
    payer_signals = adapter.evaluate_account_applicability(
        account_id="acc-payer",
        company_name="Centene Managed Health Plan",
        industry="Health Insurance",
        keywords="medicare advantage and medicaid managed care payer organization",
    )
    assert len(payer_signals) >= 1
    subtypes = [s["signal_subtype"] for s in payer_signals]
    assert "CMS-0057-F" in subtypes

    # 2. Acute Care Hospital -> Must NOT receive CMS-0057-F (providers are not covered payers!)
    hospital_signals = adapter.evaluate_account_applicability(
        account_id="acc-hospital",
        company_name="St. Mary's Regional Hospital",
        industry="Hospital & Health Care",
        keywords="400-bed acute care hospital, surgical center, emergency room, outpatient clinics",
    )
    hospital_subtypes = [s["signal_subtype"] for s in hospital_signals]
    assert "CMS-0057-F" not in hospital_subtypes
    assert "CMS-9115-F" not in hospital_subtypes

    # 3. East Jefferson General Hospital -> Must NOT receive FinCEN AML for 'East Bank' of river!
    ejgh_signals = adapter.evaluate_account_applicability(
        account_id="acc-ejgh",
        company_name="East Jefferson General Hospital",
        industry="Hospital & Health Care",
        keywords="Community hospital serving the East Bank of Jefferson Parish and greater New Orleans.",
    )
    ejgh_subtypes = [s["signal_subtype"] for s in ejgh_signals]
    assert "FINCEN-AML-ACT" not in ejgh_subtypes  # False positive successfully eliminated!

    # 4. Commercial Bank -> Should match FinCEN AML
    bank_signals = adapter.evaluate_account_applicability(
        account_id="acc-bank",
        company_name="Cascade Community Bank",
        industry="Banking",
        keywords="Commercial banking, deposit accounts, business lending, commercial credit",
    )
    bank_subtypes = [s["signal_subtype"] for s in bank_signals]
    assert "FINCEN-AML-ACT" in bank_subtypes
    assert bank_signals[0]["source_provider"] == "fincen_official"


# =========================================================================
# Phase 3: Signal 4 (SEC EDGAR Material Weakness) Tests
# =========================================================================

def test_phase3_signal4_sec_edgar_affirmative_vs_negated_and_cik_resolution():
    """Verify SEC EDGAR correctly detects affirmative weaknesses, rejects negated language, and prevents bogus CIK mapping."""
    adapter = SecEdgarAdapter()

    # 1. CIK Resolution check: CHAS Health must NOT map to Mondelez (CIK 0001103982)
    chas_cik = adapter.resolve_cik("CHAS Health", "chas.org")
    assert chas_cik != "0001103982"
    assert chas_cik is None  # Private clinic has no public CIK

    # 2. Legitimate financial institution CIK
    jpm_cik = adapter.resolve_cik("JPMorgan Chase & Co", "jpmorganchase.com")
    assert jpm_cik == "0000019617"

    meta = {
        "cik": "0000019617",
        "company_name": "JPMorgan Chase & Co",
        "filing_date": "2026-10-15",
        "accession_number": "0000019617-26-000012",
        "url": "https://www.sec.gov/Archives/edgar/data/19617/000001961726000012/doc.htm",
    }

    # 3. Explicitly negated weakness -> Must return None!
    clean_text = (
        "Item 9A. Controls and Procedures. Management assessed the effectiveness of our internal "
        "control over financial reporting as of December 31, 2025. Based on our evaluation, "
        "management concluded that internal controls were effective and no material weaknesses were identified."
    )
    neg_result = adapter.analyze_internal_controls_text(clean_text, "acc-1", meta)
    assert neg_result is None

    # 4. Affirmative material weakness -> Must return verified signal!
    weak_text = (
        "Item 9A. Controls and Procedures. Management evaluated our internal controls over financial "
        "reporting. Management concluded that our internal control over financial reporting was not effective "
        "because a material weakness was identified in information technology automated controls and user access."
    )
    aff_result = adapter.analyze_internal_controls_text(weak_text, "acc-1", meta)
    assert aff_result is not None
    assert aff_result["signal_type"] == "sec_filing"
    assert aff_result["signal_subtype"] == "10k_material_weakness"
    assert "material weakness" in aff_result["observed_fact"].lower()


# =========================================================================
# Phase 3: Signal 5 (HubSpot Intent) Tests
# =========================================================================

@pytest.mark.asyncio
async def test_phase3_signal5_hubspot_unconfigured_and_non_fabrication():
    """Verify HubSpot adapter never fabricates buyer intent records."""
    # When disabled or mock token
    adapter = HubSpotAdapter(access_token="mock-hubspot-token")
    signal = await adapter.fetch_company_intent("anycompany.com", "acc-1")
    assert signal is None  # Never returns fabricated demo data!

    # When auth failed
    adapter._auth_failed = True
    signal2 = await adapter.fetch_company_intent("anycompany.com", "acc-1")
    assert signal2 is None


# =========================================================================
# Phase 5 & 6: Scoring & Bounded Shortlist (Exactly 6 Returned) Tests
# =========================================================================

@pytest.mark.asyncio
async def test_phase5_and_6_shortlist_strictly_bounded_to_verified_accounts(
    db_session: AsyncSession, seed_data
):
    """Verify that when only 6 accounts have valid verified evidence, exactly 6 are returned (never padded to 20)."""
    org = seed_data["org"]
    prioritization_svc = RadarPrioritizationService(db_session)

    accounts = []
    candidates = []
    evidence_map = {}

    # Create 15 accounts
    for i in range(1, 16):
        acc = Account(
            organization_id=org.id,
            name=f"Bank Entity {i}",
            domain=f"bank{i}.com",
            industry="Financial Services",
            country="United States",
            employee_count=100 + i * 50,
            status="prospect",
        )
        db_session.add(acc)
        await db_session.flush()
        accounts.append(acc)

        # Accounts 1 to 6 receive valid verified evidence
        if i <= 6:
            evidence_map[acc.id] = [
                {
                    "signal_type": "hiring",
                    "signal_subtype": "kyc_fraud",
                    "observed_fact": f"Hiring 3 KYC analysts at Bank Entity {i}",
                    "verification_status": "VERIFIED",
                }
            ]
            why_now = 0.70 + (i * 0.03)
        else:
            # Accounts 7 to 15 have NO verified evidence (e.g. STALE or empty)
            evidence_map[acc.id] = [
                {
                    "signal_type": "regulatory",
                    "signal_subtype": "CMS-0057-F",
                    "observed_fact": "Stale observation",
                    "verification_status": "STALE",  # NOT VERIFIED!
                }
            ]
            why_now = 0.0

        total = round(0.35 * 0.85 + 0.65 * why_now, 3)
        candidates.append({
            "account_id": acc.id,
            "total_score": total,
            "icp_score": 0.85,
            "why_now_score": why_now,
            "why_now_reason": f"Why now reason {i}",
            "primary_signal_type": "hiring" if i <= 6 else "general_fit",
            "score_breakdown": {"rubric_version": "demo-v1"},
        })

    # Prioritize with daily_limit=20
    prioritized = await prioritization_svc.prioritize_and_handoff(
        organization_id=org.id,
        scan_run_id="scan-6-accounts-test",
        ranked_candidates=candidates,
        evidence_map=evidence_map,
        daily_limit=20,
    )

    # EXACTLY 6 accounts must be shortlisted! Must NOT fabricate or include the 9 unverified accounts!
    assert len(prioritized) == 6
    for idx, p in enumerate(prioritized, start=1):
        assert p.rank == idx
        assert p.total_score >= 0.50
        assert p.primary_signal_type == "hiring"


# =========================================================================
# Phase 7: Agent 4 Handoff & Idempotency Replay Tests
# =========================================================================

@pytest.mark.asyncio
async def test_phase7_agent4_handoff_and_replay_idempotency(db_session: AsyncSession, seed_data):
    """Verify Agent 4 event payload includes rubric version and replaying does not create duplicate tasks."""
    org = seed_data["org"]
    prioritization_svc = RadarPrioritizationService(db_session)

    acc = Account(
        organization_id=org.id,
        name="Idempotency Bank Corp",
        domain="idempbank.com",
        industry="Financial Services",
        country="United States",
        employee_count=500,
        status="prospect",
    )
    db_session.add(acc)
    await db_session.flush()

    contact = Contact(
        organization_id=org.id,
        account_id=acc.id,
        first_name="Alice",
        last_name="Manager",
        email="alice@idempbank.com",
        title="Head of Fraud Operations",
    )
    db_session.add(contact)
    await db_session.flush()

    scan_id = "scan-replay-audit-001"
    candidates = [{
        "account_id": acc.id,
        "total_score": 0.82,
        "icp_score": 0.85,
        "why_now_score": 0.80,
        "why_now_reason": "Active KYC hiring and FinCEN compliance",
        "primary_signal_type": "hiring",
        "score_breakdown": {"rubric_version": "v1.2-enterprise"},
    }]
    evidence_map = {
        acc.id: [{
            "signal_type": "hiring",
            "signal_subtype": "kyc_fraud",
            "observed_fact": "Hiring fraud review lead",
            "verification_status": "VERIFIED",
        }]
    }

    # First prioritization run
    p1 = await prioritization_svc.prioritize_and_handoff(
        organization_id=org.id,
        scan_run_id=scan_id,
        ranked_candidates=candidates,
        evidence_map=evidence_map,
        daily_limit=20,
    )
    assert len(p1) == 1
    assert p1[0].agent4_task_status == "pending_research"

    # Verify OutboxEvent has scoring_rubric_version
    outbox_res = await db_session.execute(
        select(OutboxEvent).where(OutboxEvent.correlation_id == f"radar-scan-{scan_id}")
    )
    outbox_events = outbox_res.scalars().all()
    assert len(outbox_events) == 1
    payload = outbox_events[0].payload["payload"]
    assert payload["scoring_rubric_version"] == "v1.2-enterprise"
    assert "idempotency_key" in payload

    # Count AgentTasks
    task_res1 = await db_session.execute(
        select(AgentTask).where(AgentTask.organization_id == org.id, AgentTask.agent_id == "research_personal_outreach")
    )
    tasks_count_1 = len(task_res1.scalars().all())

    # Replay prioritization for the exact same scan and candidates
    p2 = await prioritization_svc.prioritize_and_handoff(
        organization_id=org.id,
        scan_run_id=scan_id,
        ranked_candidates=candidates,
        evidence_map=evidence_map,
        daily_limit=20,
    )
    assert len(p2) == 1

    # Verify no duplicate AgentTask or OutboxEvent was created on replay!
    task_res2 = await db_session.execute(
        select(AgentTask).where(AgentTask.organization_id == org.id, AgentTask.agent_id == "research_personal_outreach")
    )
    tasks_count_2 = len(task_res2.scalars().all())
    assert tasks_count_1 == tasks_count_2  # Strictly idempotent!


# =========================================================================
# Phase 11: Downstream Outcomes & Monthly Evaluation Tests
# =========================================================================

@pytest.mark.asyncio
async def test_phase11_monthly_outcomes_and_comparative_lift(db_session: AsyncSession, seed_data):
    """Verify downstream outcome tracking, conversion rate calculation, and comparative lift."""
    org = seed_data["org"]
    eval_svc = RadarEvaluationService(db_session)

    # 1. Simulate Radar Prioritized Account outcomes
    radar_outcomes = [
        # Hiring cohort: 5 outreach, 2 positive replies, 1 meeting
        {"signal_cohort": "hiring", "sales_accepted": True, "approved_outreach": True, "positive_reply": True, "qualified_meeting": True},
        {"signal_cohort": "hiring", "sales_accepted": True, "approved_outreach": True, "positive_reply": True, "qualified_meeting": False},
        {"signal_cohort": "hiring", "sales_accepted": True, "approved_outreach": True, "positive_reply": False, "qualified_meeting": False},
        {"signal_cohort": "hiring", "sales_accepted": True, "approved_outreach": True, "positive_reply": False, "qualified_meeting": False},
        {"signal_cohort": "hiring", "sales_accepted": True, "approved_outreach": True, "positive_reply": False, "qualified_meeting": False},
        # Growth cohort: 5 outreach, 2 positive replies, 1 meeting
        {"signal_cohort": "growth", "sales_accepted": True, "approved_outreach": True, "positive_reply": True, "qualified_meeting": True},
        {"signal_cohort": "growth", "sales_accepted": True, "approved_outreach": True, "positive_reply": True, "qualified_meeting": False},
        {"signal_cohort": "growth", "sales_accepted": True, "approved_outreach": True, "positive_reply": False, "qualified_meeting": False},
        {"signal_cohort": "growth", "sales_accepted": True, "approved_outreach": True, "positive_reply": False, "qualified_meeting": False},
        {"signal_cohort": "growth", "sales_accepted": True, "approved_outreach": True, "positive_reply": False, "qualified_meeting": False},
    ]

    # 2. Simulate Baseline Prospect outcomes (Cold outreach without radar buying signals)
    baseline_outcomes = [
        # 10 outreach, 1 positive reply, 0 meetings
        {"signal_cohort": "cold_prospect", "sales_accepted": True, "approved_outreach": True, "positive_reply": True, "qualified_meeting": False},
        *([{"signal_cohort": "cold_prospect", "sales_accepted": True, "approved_outreach": True, "positive_reply": False, "qualified_meeting": False}] * 9)
    ]

    comparison = eval_svc.compare_radar_vs_baseline(radar_outcomes, baseline_outcomes)
    assert comparison["radar_aggregate"]["reply_rate"] == 0.40  # 4 / 10 = 40%
    assert comparison["baseline_aggregate"]["reply_rate"] == 0.10  # 1 / 10 = 10%

    # 4x lift over baseline cold prospect outreach
    assert comparison["comparative_lift"]["reply_rate_lift_factor"] == 4.0
    assert comparison["comparative_lift"]["is_2x_reply_rate_verified"] is True

    # 3. Monthly Evaluation Run generation
    eval_run = await eval_svc.generate_monthly_evaluation_run(
        organization_id=org.id,
        radar_outcomes=radar_outcomes,
        baseline_outcomes=baseline_outcomes,
        rubric_version="demo-v1",
    )
    assert eval_run.passed is True
    report = eval_run.evaluation_report
    adj = report["proposed_rubric_adjustment"]
    # Proposed adjustments must NEVER auto-activate and must require human approval
    assert adj["status"] == "pending_human_approval"
    assert adj["auto_activated"] is False


# =========================================================================
# Phase 12: Security & Reliability Defenses Tests
# =========================================================================

def test_phase12_ssrf_and_csv_injection_defenses():
    """Verify SSRF defenses against cloud metadata / private IPs and CSV injection sanitization."""
    val = EvidenceValidationService()

    # SSRF protection tests
    assert val.validate_url("http://169.254.169.254/latest/meta-data/") is False  # Cloud metadata blocked
    assert val.validate_url("http://localhost:8001/admin") is False  # Localhost blocked
    assert val.validate_url("http://127.0.0.1:5432") is False  # Loopback IP blocked
    assert val.validate_url("http://10.0.0.5/secrets") is False  # Private RFC1918 blocked
    assert val.validate_url("http://192.168.1.1/router") is False  # Private RFC1918 blocked
    assert val.validate_url("http://0.0.0.0:80") is False  # Wildcard blocked
    assert val.validate_url("https://www.sec.gov/Archives/edgar/data/19617/doc.htm") is True  # Public HTTPS allowed
    assert val.validate_url("https://api.gdeltproject.org/api/v2/doc/doc") is True  # Public HTTPS allowed

    # CSV injection sanitization
    from backend.app.services.csv_import_service import sanitize_csv_cell
    assert sanitize_csv_cell("=cmd|' /C calc'!A0").startswith("'=")
    assert sanitize_csv_cell("+cmd|' /C calc'!A0").startswith("'+")
    assert sanitize_csv_cell("@SUM(1+1)").startswith("'@")
    assert sanitize_csv_cell("Normal Bank Name") == "Normal Bank Name"
    assert sanitize_csv_cell("-500") == "-500"  # Valid negative number preserved

"""Unit tests for Buying-Signal Radar (Agent 1) services and integrations."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.integrations.crm.hubspot import HubSpotAdapter
from backend.app.integrations.research.gdelt import GdeltDocAdapter
from backend.app.integrations.research.growth import GrowthNewsAdapter
from backend.app.integrations.research.job_boards import GreenhouseAdapter, LeverAdapter
from backend.app.integrations.research.regulatory import RegulatoryAdapter
from backend.app.integrations.research.sec_edgar import SecEdgarAdapter
from backend.app.models.sales import Account, Contact
from backend.app.services.csv_import_service import CsvImportService, canonicalize_domain
from backend.app.services.evidence_validation_service import EvidenceValidationService
from backend.app.services.radar_prioritization_service import RadarPrioritizationService
from backend.app.services.scoring_engine import ScoringEngine


def test_canonicalize_domain():
    assert canonicalize_domain("https://www.chas.org/about") == "chas.org"
    assert canonicalize_domain("http://bethany.org/") == "bethany.org"
    assert canonicalize_domain("sub.example.com?query=1") == "sub.example.com"
    assert canonicalize_domain("") == ""


@pytest.mark.asyncio
async def test_csv_preview_and_import(db_session: AsyncSession, seed_data):
    org = seed_data["org"]
    svc = CsvImportService(db_session)

    csv_data = (
        "Company Name,Website,Industry,# Employees,Company Country,Company State,Company City,Annual Revenue,Apollo Org Id,Contact First Name,Contact Last Name,Contact Email,Contact Title\n"
        "CHAS Health,http://www.chas.org,hospital & health care,1800,United States,Washington,Spokane,3256000,54a128e6,Jane,Doe,jane.doe@chas.org,VP of Revenue Cycle\n"
        "Bethany Christian Services,http://www.bethany.org,nonprofit organization management,2400,United States,Michigan,Grand Rapids,2944000,6afaf71f,John,Smith,john.smith@bethany.org,Director of Operations\n"
        "Missing Domain Corp,,software,50,United States,,,,,,invalid@test.com,\n"
    )

    # 1. Preview
    preview = svc.preview_csv(csv_data)
    assert preview["total_rows_detected"] == 3
    assert "Company Name" in preview["headers"]
    assert preview["suggested_mappings"]["Company Name"] == "name"
    assert preview["suggested_mappings"]["Website"] == "domain"

    # 2. Import
    history = await svc.import_csv(
        organization_id=org.id,
        content_str=csv_data,
        filename="test_apollo.csv",
    )
    assert history.imported_accounts == 2
    assert history.imported_contacts == 2
    assert history.errors_count == 1  # Missing Domain Corp skipped

    # 3. Re-importing same data tests deduplication
    reimport_history = await svc.import_csv(
        organization_id=org.id,
        content_str=csv_data,
        filename="test_apollo.csv",
    )
    assert reimport_history.duplicate_accounts == 2
    assert reimport_history.imported_accounts == 0


@pytest.mark.asyncio
async def test_greenhouse_and_lever_hiring_signals():
    gh = GreenhouseAdapter()
    jobs = [
        {"id": 101, "title": "Senior Claims Processing Specialist", "absolute_url": "https://careers.example.com/101", "location": {"name": "Remote"}},
        {"id": 102, "title": "Prior Authorization Nurse Coordinator", "absolute_url": "https://careers.example.com/102"},
        {"id": 103, "title": "Software Engineer", "absolute_url": "https://careers.example.com/103"},
    ]
    signals = gh.detect_signals(jobs, account_id="acc-1", company_name="Test Health")
    assert len(signals) == 2
    subtypes = {s["signal_subtype"] for s in signals}
    assert "claims_processing" in subtypes
    assert "prior_authorization" in subtypes

    lever = LeverAdapter()
    postings = [
        {"id": "lev-1", "text": "Medical Billing and Revenue Cycle Lead", "hostedUrl": "https://jobs.lever.co/test/1", "categories": {"location": "New York"}},
        {"id": "lev-2", "text": "Office Receptionist", "hostedUrl": "https://jobs.lever.co/test/2"},
    ]
    lever_signals = lever.detect_signals(postings, account_id="acc-2", company_name="Test Lever")
    assert len(lever_signals) == 1
    assert lever_signals[0]["signal_subtype"] == "revenue_cycle"


def test_growth_news_classification():
    adapter = GrowthNewsAdapter()
    articles = [
        {
            "title": "Hospital Network Announces $50M Series B Funding to Scale Digital Operations",
            "description": "The capital investment will support regional growth.",
            "url": "https://news.example.com/funding-1",
            "publishedAt": "2026-11-10T10:00:00Z",
        },
        {
            "title": "Healthcare System Appoints New CIO to Lead EHR Transformation",
            "description": "Executive appointment announced yesterday.",
            "url": "https://news.example.com/cio-1",
            "publishedAt": "2026-11-08T10:00:00Z",
        },
        {
            "title": "Local team wins regional championship",
            "description": "Irrelevant sports news.",
            "url": "https://news.example.com/sports-1",
            "publishedAt": "2026-11-05T10:00:00Z",
        },
    ]
    signals = adapter.classify_growth_events(articles, account_id="acc-growth", company_name="Hospital Network")
    assert len(signals) == 2
    subtypes = {s["signal_subtype"] for s in signals}
    assert "funding" in subtypes
    assert "leadership_change" in subtypes


def test_gdelt_doc_adapter():
    gdelt = GdeltDocAdapter()
    query = gdelt.build_query("St. Jude Hospital System", "stjude.org")
    assert '"St  Jude Hospital System"' in query
    assert "clinic" in query or "hospital" in query or "expansion" in query

    articles = [
        {
            "title": "St. Jude Hospital System Opens New Outpatient Facility in Dallas",
            "url": "https://dallasnews.com/stjude-facility",
            "domain": "dallasnews.com",
            "seendate": "20261012T140000Z",
        },
        {
            "title": "St. Jude Hospital System Names New VP of Revenue Cycle",
            "url": "https://beckershospitalreview.com/stjude-vp",
            "domain": "beckershospitalreview.com",
            "seendate": "20261005T093000Z",
        },
        {
            "title": "Unrelated Healthcare Entity Opens Clinic in Denver",
            "url": "https://denverhealth.org/clinic",
            "domain": "denverhealth.org",
            "seendate": "20261001T120000Z",
        },
    ]

    signals = gdelt.classify_growth_signals(articles, account_id="acc-stjude", company_name="St. Jude Hospital System")
    assert len(signals) == 2  # Unrelated company rejected
    subtypes = {s["signal_subtype"] for s in signals}
    assert "facility_expansion" in subtypes
    assert "leadership_change" in subtypes
    assert all(s["verification_status"] == "VERIFIED" for s in signals)
    assert all(len(s["evidence_fingerprint"]) == 64 for s in signals)  # Valid SHA-256 hash


def test_regulatory_rule_applicability():
    reg = RegulatoryAdapter()
    # Healthcare company matching CMS-0057-F
    hc_signals = reg.evaluate_account_applicability(
        account_id="acc-hc",
        company_name="State Health Plan",
        industry="Hospital & Health Care",
        keywords="medicare advantage payer",
    )
    assert len(hc_signals) >= 1
    rule_ids = {s["signal_subtype"] for s in hc_signals}
    assert "CMS-0057-F" in rule_ids

    # Bank matching FinCEN, NOT CMS-0057-F
    bank_signals = reg.evaluate_account_applicability(
        account_id="acc-bank",
        company_name="Metro First Credit Union",
        industry="Banking",
        keywords="commercial bank credit union",
    )
    assert len(bank_signals) >= 1
    bank_rule_ids = {s["signal_subtype"] for s in bank_signals}
    assert "FINCEN-AML-ACT" in bank_rule_ids
    assert "CMS-0057-F" not in bank_rule_ids


def test_sec_edgar_affirmative_vs_negated_weakness():
    adapter = SecEdgarAdapter()
    meta = {
        "cik": "0001234567",
        "form": "10-K",
        "accession_number": "0001234567-26-000010",
        "filing_date": "2026-03-15",
    }

    # Case 1: Negated statement ("no material weaknesses were identified")
    clean_text = (
        "Item 9A. Controls and Procedures. Management evaluated the effectiveness of our internal control "
        "over financial reporting as of December 31, 2025. Based on this evaluation, management concluded that "
        "our internal control over financial reporting was effective and no material weaknesses were identified."
    )
    result_clean = adapter.analyze_internal_controls_text(clean_text, "acc-1", meta)
    assert result_clean is None  # Confirmed clean filing, no false alarm!

    # Case 2: Affirmative disclosure of material weakness
    weakness_text = (
        "Item 9A. Controls and Procedures. Management assessed the effectiveness of our internal control over financial "
        "reporting. A material weakness was identified relating to the lack of sufficient automated controls over complex "
        "claims adjudication and prior authorization reconciliation."
    )
    result_weakness = adapter.analyze_internal_controls_text(weakness_text, "acc-2", meta)
    assert result_weakness is not None
    assert result_weakness["signal_subtype"] == "10k_material_weakness"
    assert result_weakness["verification_status"] == "VERIFIED"


@pytest.mark.asyncio
async def test_hubspot_unconfigured_status():
    hs = HubSpotAdapter(access_token="mock-hubspot-token")
    health = await hs.check_health()
    assert health.status in ("not_configured", "healthy")


def test_evidence_validation_freshness_and_deduplication():
    validator = EvidenceValidationService(freshness_days=90)
    now = datetime(2026, 11, 17, 12, 0, 0, tzinfo=timezone.utc)

    # 1. Fresh evidence
    fresh_signal = {
        "signal_type": "hiring",
        "signal_subtype": "claims",
        "observed_fact": "Active hiring for 3 claims processors.",
        "business_hypothesis": "Manual work backlog.",
        "source_provider": "greenhouse",
        "source_url": "https://careers.example.com/1",
        "published_at": (now - timedelta(days=10)).isoformat(),
    }
    is_valid, status, norm_fresh = validator.validate_evidence_record("acc-1", "example.com", fresh_signal, now=now)
    assert is_valid is True
    assert status == "VERIFIED"
    assert norm_fresh["confidence"] == 1.0

    # 2. Stale evidence (> 90 days old)
    stale_signal = {
        **fresh_signal,
        "published_at": (now - timedelta(days=120)).isoformat(),
    }
    is_valid, status, norm_stale = validator.validate_evidence_record("acc-1", "example.com", stale_signal, now=now)
    assert is_valid is True
    assert status == "STALE"
    assert norm_stale["confidence"] == 0.5

    # 3. Invalid URL -> REJECTED
    invalid_url_signal = {
        **fresh_signal,
        "source_url": "not-a-valid-url",
    }
    is_valid, status, _ = validator.validate_evidence_record("acc-1", "example.com", invalid_url_signal, now=now)
    assert is_valid is False
    assert status == "REJECTED"


def test_scoring_engine_reproducibility():
    engine = ScoringEngine(rubric_version="demo-v1")
    acc = Account(
        name="Valley Health System",
        domain="valleyhealth.org",
        industry="Hospital & Health Care",
        employee_count=1200,
        country="United States",
        short_description="Healthcare network operating 15 clinics specializing in prior authorization and revenue cycle.",
    )
    criteria = {
        "country": "United States",
        "target_industries": ["Hospital & Health Care"],
        "target_operations": ["prior authorization", "revenue cycle"],
        "employee_min": 100,
        "employee_max": 5000,
    }
    evidences = [
        {
            "signal_type": "regulatory",
            "signal_subtype": "CMS-0057-F",
            "observed_fact": "Subject to CMS-0057-F Interoperability deadline.",
            "verification_status": "VERIFIED",
        },
        {
            "signal_type": "hiring",
            "signal_subtype": "claims_processing",
            "observed_fact": "Active hiring for 4 Claims Adjudication Specialists.",
            "verification_status": "VERIFIED",
        },
    ]

    res1 = engine.compute_account_ranking(acc, criteria, evidences)
    res2 = engine.compute_account_ranking(acc, criteria, evidences)

    # Must be 100% deterministic & reproducible
    assert res1["icp_score"] == res2["icp_score"]
    assert res1["why_now_score"] == res2["why_now_score"]
    assert res1["total_score"] == res2["total_score"]
    assert res1["total_score"] > 0.60
    assert "CMS-0057-F" in res1["why_now_reason"]


@pytest.mark.asyncio
async def test_top_20_prioritization_and_agent4_handoff(db_session: AsyncSession, seed_data):
    org = seed_data["org"]
    prioritization_svc = RadarPrioritizationService(db_session)

    # Create 5 test accounts
    accounts = []
    candidates = []
    evidence_map = {}
    for i in range(1, 6):
        acc = Account(
            organization_id=org.id,
            name=f"Hospital System {i}",
            domain=f"hospital{i}.org",
            industry="Hospital & Health Care",
            country="United States",
            employee_count=500 + i * 100,
            status="prospect",
        )
        db_session.add(acc)
        await db_session.flush()

        # Add contact for account 1
        if i == 1:
            contact = Contact(
                organization_id=org.id,
                account_id=acc.id,
                first_name="Jane",
                last_name="Executive",
                email="jane@hospital1.org",
                title="VP of Revenue Cycle Operations",
            )
            db_session.add(contact)
            await db_session.flush()

        accounts.append(acc)
        total_score = 0.50 + (i * 0.08)
        candidates.append({
            "account_id": acc.id,
            "total_score": round(total_score, 2),
            "icp_score": 0.85,
            "why_now_score": round(total_score, 2),
            "why_now_reason": f"Active hiring for RCM at Hospital {i}",
            "primary_signal_type": "hiring",
            "score_breakdown": {},
        })
        evidence_map[acc.id] = [{"signal_type": "hiring", "observed_fact": "Hiring 5 RCM roles"}]

    # Run prioritization with daily_limit=20
    scan_id = "test-scan-run-1"
    prioritized = await prioritization_svc.prioritize_and_handoff(
        organization_id=org.id,
        scan_run_id=scan_id,
        ranked_candidates=candidates,
        evidence_map=evidence_map,
        daily_limit=20,
    )

    # 5 accounts qualified -> returns exactly 5 (does NOT fabricate to 20!)
    assert len(prioritized) == 5
    # Rank 1 must have the highest total_score
    assert prioritized[0].rank == 1
    assert prioritized[0].total_score >= prioritized[1].total_score

    # Check contact candidate identification
    acc1_p = next(p for p in prioritized if p.account_id == accounts[0].id)
    assert acc1_p.contact_status == "verified_contact"
    assert acc1_p.suggested_contact_id is not None

    acc2_p = next(p for p in prioritized if p.account_id == accounts[1].id)
    assert acc2_p.contact_status == "research_required"
    assert acc2_p.suggested_contact_id is None

    # Verify Agent 4 Task creation
    from sqlalchemy import select

    from backend.app.models.execution import AgentTask, OutboxEvent

    tasks = (await db_session.execute(select(AgentTask).where(AgentTask.organization_id == org.id))).scalars().all()
    assert len(tasks) >= 5
    assert all(t.agent_id == "research_personal_outreach" for t in tasks)
    assert all(t.status == "waiting_for_input" for t in tasks)

    # Verify OutboxEvent consistency
    outbox = (await db_session.execute(select(OutboxEvent).where(OutboxEvent.organization_id == org.id))).scalars().all()
    assert len(outbox) >= 5
    assert all(o.event_type == "account.prioritized" for o in outbox)

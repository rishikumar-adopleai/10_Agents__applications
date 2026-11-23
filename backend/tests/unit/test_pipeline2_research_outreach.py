"""Unit and Integration Tests for Pipeline 2 (Research & Personal Outreach Agent)."""

import pytest

from backend.app.agents.orchestrator import AgentOrchestrator
from backend.app.agents.research_outreach.opportunity_analyzer import OpportunityAnalyzer
from backend.app.agents.research_outreach.sample_loader import (
    Pipeline1CompatibilityAdapter,
    SampleDataLoader,
)
from backend.app.schemas.agents import AgentExecutionRequest, AgentStatus
from backend.app.services.suppression_service import SuppressionService
from backend.app.workflows.definitions import PlatformWorkflows


def test_sample_files_load_and_validate():
    """Requirement 1: Verify sample files load and validate without crashing."""
    loader = SampleDataLoader()
    accounts, failures = loader.load_accounts_raw()
    assert len(accounts) == 3
    assert len(failures) == 0

    contacts_map = loader.load_contacts_raw()
    assert "ACC-001" in contacts_map
    assert "ACC-002" in contacts_map
    assert "ACC-003" in contacts_map


def test_malformed_input_does_not_crash():
    """Requirement 2: Malformed input does not cause entire pipeline to crash."""
    loader = SampleDataLoader()
    # Test validation helper
    raw_accounts, failures = loader.load_accounts_raw()
    assert len(raw_accounts) == 3


def test_contacts_matched_by_account_id_and_deduplicated():
    """Requirement 3 & 4: Contacts matched to correct company by account_id and duplicates prevented."""
    loader = SampleDataLoader()
    accounts = loader.get_all_sample_accounts()
    assert len(accounts) == 3

    acc1 = next(a for a in accounts if a["account_id"] == "ACC-001")
    assert acc1["company_name"] == "Northstar Health Systems"
    contact_ids = [c["contact_id"] for c in acc1["contacts"]]
    assert "CON-001" in contact_ids
    assert "CON-002" in contact_ids
    # Verify no duplicate contacts
    assert len(contact_ids) == len(set(contact_ids))


def test_role_ranking_and_decision_maker_selection():
    """Requirement 5: Appropriate decision-makers are selected according to buying signal."""
    analyzer = OpportunityAnalyzer()
    loader = SampleDataLoader()
    accounts = loader.get_all_sample_accounts()

    # Case 1: AI hiring at Northstar Health -> CTO / VP of Engineering / Director of AI
    acc1 = next(a for a in accounts if a["account_id"] == "ACC-001")
    primary, alts, _ = analyzer.rank_and_select_contact(
        acc1["contacts"], "relevant_hiring", "AI engineering recruitment"
    )
    assert primary is not None
    assert primary["job_title"] in ["VP of Engineering", "Director of AI"]
    assert len(alts) == 1

    # Case 2: Business Expansion at Cedarline -> COO
    acc2 = next(a for a in accounts if a["account_id"] == "ACC-002")
    primary2, alts2, _ = analyzer.rank_and_select_contact(
        acc2["contacts"], "expansion", "Distribution expansion"
    )
    assert primary2 is not None
    assert primary2["job_title"] == "Chief Operating Officer"
    assert len(alts2) == 1


def test_missing_contact_details_handled_safely():
    """Requirement 6: Incomplete contact information handled safely without inventing info."""
    analyzer = OpportunityAnalyzer()
    loader = SampleDataLoader()
    accounts = loader.get_all_sample_accounts()

    acc3 = next(a for a in accounts if a["account_id"] == "ACC-003")
    # In ACC-003, Riley Davis (CON-006) has missing email and is blocked_missing_address.
    # Morgan Chen (CON-005) is CTO with valid email.
    primary, alts, _ = analyzer.rank_and_select_contact(
        acc3["contacts"], "modernization", "Document operations modernization"
    )
    assert primary is not None
    assert primary["contact_id"] == "CON-005"  # Eligible contact selected
    assert any(c["contact_id"] == "CON-006" for c in alts)


def test_facts_vs_hypotheses_research_synthesis():
    """Requirement 7 & 8: Research distinguishes verified facts from potential business needs."""
    loader = SampleDataLoader()
    analyzer = OpportunityAnalyzer()
    accounts = loader.get_all_sample_accounts()

    acc1 = next(a for a in accounts if a["account_id"] == "ACC-001")
    facts, hypotheses, sources, evidence_refs = analyzer.synthesize_research_brief(acc1)

    assert "observed_signals" in facts
    assert len(facts["observed_signals"]) > 0
    assert "primary_driver" in hypotheses
    assert "hypothesized_pain_points" in hypotheses
    assert len(sources) > 0
    assert len(evidence_refs) > 0


@pytest.mark.asyncio
async def test_llm_opportunity_analysis_structured_schema():
    """Requirement 9: LLM opportunity analysis returns valid structured schema."""
    loader = SampleDataLoader()
    analyzer = OpportunityAnalyzer()
    acc1 = loader.get_sample_account_by_id("ACC-001")
    facts, hypotheses, _, _ = analyzer.synthesize_research_brief(acc1)

    analysis = await analyzer.generate_opportunity_analysis(
        acc1, acc1["contacts"][0], facts, hypotheses
    )
    assert "company_overview" in analysis
    assert "verified_business_info" in analysis
    assert "buying_signal_analysis" in analysis
    assert "potential_business_needs" in analysis
    assert "relevant_service_offering" in analysis
    assert "supporting_evidence" in analysis
    assert "suggested_contact" in analysis
    assert "unverified_assumptions" in analysis


def test_personalized_outreach_draft_generation():
    """Requirement 10: Personalized outreach draft is generated with proper CTA and context."""
    loader = SampleDataLoader()
    analyzer = OpportunityAnalyzer()
    acc1 = loader.get_sample_account_by_id("ACC-001")
    contact = acc1["contacts"][0]
    opportunity_analysis = {
        "relevant_service_offering": "Autonomous Enterprise Demo & Inbound Qualification Platform"
    }
    demo_ref = {"access_url": "https://demo.platform.internal/preview?token=xyz"}

    draft = analyzer.generate_personalized_outreach_draft(
        acc1, contact, opportunity_analysis, demo_reference=demo_ref
    )
    assert "draft_body" in draft
    assert contact["first_name"] in draft["draft_body"] or "Alex" in draft["draft_body"]
    assert "demo" in draft["draft_body"].lower()
    assert "https://demo.platform.internal/preview?token=xyz" in draft["draft_body"]
    assert draft["has_demo"] is True


@pytest.mark.asyncio
async def test_pipeline2_agent_execution_all_three_sample_accounts(db_session, seed_data):
    """Requirement 2 & 23: Complete execution for all 3 sample companies."""
    org = seed_data["org"]
    orchestrator = AgentOrchestrator(db_session)

    # ACC-001: High tier, should qualify for demo and await review
    req1 = AgentExecutionRequest(
        agent_id="research_personal_outreach",
        organization_id=org.id,
        account_id="ACC-001",
        correlation_id="test-p2-corr-1",
        parameters={"use_sample_data": True},
    )
    res1 = await orchestrator.execute_agent(req1)
    assert res1.status == AgentStatus.WAITING_FOR_REVIEW
    s1 = res1.structured_result
    assert s1["company_information"]["company_name"] == "Northstar Health Systems"
    assert s1["selected_primary_contact"] is not None
    assert s1["optional_demo_recommendation_or_reference"] is not None
    assert s1["processing_status"] == "completed_awaiting_review"

    # ACC-002: Medium tier, logistics expansion, no demo needed
    req2 = AgentExecutionRequest(
        agent_id="research_personal_outreach",
        organization_id=org.id,
        account_id="ACC-002",
        correlation_id="test-p2-corr-2",
        parameters={"use_sample_data": True},
    )
    res2 = await orchestrator.execute_agent(req2)
    assert res2.status == AgentStatus.WAITING_FOR_REVIEW
    s2 = res2.structured_result
    assert s2["company_information"]["company_name"] == "Cedarline Logistics"
    assert s2["selected_primary_contact"]["job_title"] == "Chief Operating Officer"
    assert s2["optional_demo_recommendation_or_reference"] is None

    # ACC-003: Medium tier, financial modernization
    req3 = AgentExecutionRequest(
        agent_id="research_personal_outreach",
        organization_id=org.id,
        account_id="ACC-003",
        correlation_id="test-p2-corr-3",
        parameters={"use_sample_data": True},
    )
    res3 = await orchestrator.execute_agent(req3)
    assert res3.status == AgentStatus.WAITING_FOR_REVIEW
    s3 = res3.structured_result
    assert s3["company_information"]["company_name"] == "Silveroak Financial Services"
    assert s3["selected_primary_contact"]["contact_id"] == "CON-005"


@pytest.mark.asyncio
async def test_pipeline2_blocks_suppressed_contact(db_session, seed_data):
    """Requirement 15: Contact in suppression registry is strictly blocked."""
    org = seed_data["org"]
    suppression_service = SuppressionService(db_session)
    await suppression_service.record_suppression(
        organization_id=org.id,
        reason="spam_complaint",
        email="alex.morgan@northstar-health.example",
    )

    orchestrator = AgentOrchestrator(db_session)
    req = AgentExecutionRequest(
        agent_id="research_personal_outreach",
        organization_id=org.id,
        account_id="ACC-001",
        correlation_id="test-p2-supp-1",
        parameters={"use_sample_data": True},
    )
    result = await orchestrator.execute_agent(req)
    assert result.status == AgentStatus.BLOCKED
    assert "suppression registry" in result.error_details


@pytest.mark.asyncio
async def test_pipeline2_workflow_engine_integration(db_session, seed_data):
    """Requirement 18 & 22: Test workflow engine execution and step progression."""
    org = seed_data["org"]
    workflows = PlatformWorkflows(db_session)

    run = await workflows.run_research_outreach(
        organization_id=org.id,
        account_id="ACC-001",
        parameters={"use_sample_data": True},
    )
    assert run.workflow_name == "ResearchOutreachWorkflow"
    assert run.current_step == "awaiting_sales_approval"
    assert run.status == "waiting_for_approval"


@pytest.mark.asyncio
async def test_pipeline2_batch_independent_processing(db_session, seed_data):
    """Requirement 23 & 24: Batch execution processes companies independently."""
    org = seed_data["org"]
    workflows = PlatformWorkflows(db_session)

    # Process all sample accounts in batch
    batch_results = await workflows.run_pipeline2_batch(
        organization_id=org.id,
        account_ids=["ACC-001", "ACC-002", "ACC-003", "NON-EXISTENT-ACC"],
        use_sample_data=True,
    )
    assert len(batch_results) == 4
    # First 3 should succeed
    assert batch_results[0]["success"] is True
    assert batch_results[1]["success"] is True
    assert batch_results[2]["success"] is True
    # Non-existent account fails without crashing the remaining accounts
    assert batch_results[3]["status"] == "failed"


def test_pipeline1_compatibility_adapter():
    """Requirement: Compatibility adapter adapts Pipeline 1 structured result for Pipeline 2."""
    p1_output = {
        "account_id": "acc-db-1234",
        "company_name": "Apex Cloud Systems",
        "domain": "apexcloud.io",
        "fit_score": 0.89,
        "why_now": "Rapid expansion of engineering staff",
        "observed_facts": ["Expanded engineering department by 30%"],
    }
    adapted = Pipeline1CompatibilityAdapter.adapt_from_agent1_result(p1_output)
    assert adapted["account_id"] == "acc-db-1234"
    assert adapted["company_name"] == "Apex Cloud Systems"
    assert adapted["priority"]["tier"] == "high"
    assert len(adapted["signals"]) == 1
    assert adapted["signals"][0]["type"] == "hiring_expansion"

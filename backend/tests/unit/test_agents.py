"""Unit Tests for All Ten Specialized Agents."""

import pytest

from backend.app.agents.orchestrator import AgentOrchestrator
from backend.app.agents.registry import agent_registry
from backend.app.models.sales import Account, Opportunity
from backend.app.schemas.agents import AgentExecutionRequest, AgentStatus


def test_all_ten_agents_registered():
    """Verify that all ten required agent modules are registered in the system."""
    expected_agents = [
        "buying_signal_radar",
        "research_personal_outreach",
        "demo_before_hello",
        "lead_responder",
        "deal_desk",
        "trust_security_desk",
        "proof_engine",
        "ai_search_visibility",
        "partner_finder",
        "revival_agent",
    ]
    registered_ids = [a.agent_id for a in agent_registry.list_all()]
    for agent_id in expected_agents:
        assert agent_id in registered_ids
    assert len(registered_ids) >= 10


@pytest.mark.asyncio
async def test_buying_signal_radar_execution(db_session, seed_data):
    org = seed_data["org"]
    orchestrator = AgentOrchestrator(db_session)

    req = AgentExecutionRequest(
        agent_id="buying_signal_radar",
        organization_id=org.id,
        correlation_id="test-corr-1",
        parameters={"domain": "innovatech.io", "company_name": "InnovaTech Labs"},
    )
    result = await orchestrator.execute_agent(req)

    assert result.status == AgentStatus.COMPLETED
    assert result.structured_result["domain"] == "innovatech.io"
    assert result.structured_result["fit_score"] > 0.8
    assert len(result.artifact_references) > 0


@pytest.mark.asyncio
async def test_deal_desk_gated_by_discovery(db_session, seed_data):
    """Verify Deal Desk blocks proposal drafting if discovery is not completed."""
    org = seed_data["org"]
    account = Account(organization_id=org.id, name="Pending Discovery Inc", domain="pending.com")
    db_session.add(account)
    await db_session.flush()

    # Opportunity with discovery_completed = False
    opp = Opportunity(
        organization_id=org.id,
        account_id=account.id,
        name="Undiscovered Deal",
        discovery_completed=False,
    )
    db_session.add(opp)
    await db_session.flush()

    orchestrator = AgentOrchestrator(db_session)
    req = AgentExecutionRequest(
        agent_id="deal_desk",
        organization_id=org.id,
        correlation_id="test-corr-2",
        parameters={"opportunity_id": opp.id},
    )
    result = await orchestrator.execute_agent(req)
    assert result.status == AgentStatus.BLOCKED
    assert "Discovery is not completed" in result.error_details

    # Mark discovery completed -> Now Deal Desk succeeds
    opp.discovery_completed = True
    opp.discovery_notes = "Confirmed budget and timeline."
    await db_session.flush()

    result2 = await orchestrator.execute_agent(req)
    assert result2.status == AgentStatus.WAITING_FOR_REVIEW
    assert "acv_usd" in result2.structured_result
    assert result2.structured_result["requires_commercial_signoff"] is True

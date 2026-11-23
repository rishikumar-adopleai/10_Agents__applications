"""Unit and Integration Tests for Pipeline 2 Production Mode vs Test Mode."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy import select

from backend.app.agents.research_outreach.agent import ResearchOutreachAgent
from backend.app.agents.research_outreach.opportunity_analyzer import OpportunityAnalyzer
from backend.app.core.config import is_configured_value, settings
from backend.app.core.rbac import CurrentUser, RoleEnum
from backend.app.integrations.ai.gateway import LLMGateway
from backend.app.integrations.messaging.outlook_mail import OutlookMailAdapter
from backend.app.integrations.research.apollo import ApolloAdapter
from backend.app.integrations.research.brave import BraveSearchAdapter
from backend.app.models.artifacts import BuyingSignal
from backend.app.models.conversations import Conversation, Message, OutreachAttempt
from backend.app.models.sales import Account, Contact
from backend.app.schemas.agents import AgentExecutionRequest, AgentStatus
from backend.app.services.approval_service import ApprovalService
from backend.app.services.suppression_service import SuppressionService


def test_is_configured_value_rejects_placeholders_and_mocks():
    assert is_configured_value(None) is False
    assert is_configured_value("") is False
    assert is_configured_value("mock-apollo-key") is False
    assert is_configured_value("<your-brave-api-key>") is False
    assert is_configured_value("sales@yourdomain.com") is False
    assert is_configured_value("real-secret-token-12345") is True
    assert is_configured_value("outreach@adople.com") is True


def test_validate_pipeline2_production_credentials_does_not_leak_secrets(monkeypatch):
    monkeypatch.setattr(settings, "BRAVE_SEARCH_API_KEY", "BSA-super-secret-value")
    monkeypatch.setattr(settings, "APOLLO_API_KEY", "<your-apollo-api-key>")
    monkeypatch.setattr(settings, "MICROSOFT_CLIENT_SECRET", "ms-super-secret-999")

    report = settings.validate_pipeline2_production_credentials()
    assert "BRAVE_SEARCH_API_KEY" in report["configured"]
    assert "APOLLO_API_KEY" in report["missing"]
    assert "BSA-super-secret-value" not in str(report)
    assert "ms-super-secret-999" not in str(report)


@pytest.mark.asyncio
async def test_outlook_adapter_skips_in_test_mode():
    adapter = OutlookMailAdapter(
        client_id="real-client-id",
        client_secret="real-secret",
        tenant_id="real-tenant",
        sender_email="sales@adople.com",
    )
    res = await adapter.send_email(
        to_email="cto@acme.io",
        subject="Hello",
        body="Test body",
        mode="test",
    )
    assert res["status"] == "skipped_test_mode"
    assert res["error"] is None


@pytest.mark.asyncio
async def test_outlook_adapter_reports_missing_credentials_safely():
    adapter = OutlookMailAdapter(
        client_id="<azure-client-id>",
        client_secret="<azure-client-secret>",
        tenant_id="<azure-tenant-id>",
        sender_email="sales@yourdomain.com",
    )
    res = await adapter.send_email(
        to_email="cto@acme.io",
        subject="Hello",
        body="Test body",
        mode="production",
    )
    assert res["status"] == "failed"
    assert "Missing or placeholder Microsoft Outlook credentials" in res["error"]
    assert "MICROSOFT_CLIENT_ID" in res["error"]
    assert "MICROSOFT_SENDER_EMAIL" in res["error"]


@pytest.mark.asyncio
async def test_outlook_adapter_sends_email_in_production_mode():
    adapter = OutlookMailAdapter(
        client_id="11111111-1111-1111-1111-111111111111",
        client_secret="real-client-secret-value",
        tenant_id="22222222-2222-2222-2222-222222222222",
        sender_email="sales@adople.com",
    )
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 202
    mock_response.headers = {"request-id": "graph-req-001"}

    with (
        patch.object(adapter, "acquire_access_token", AsyncMock(return_value="fake-oauth-token")),
        patch("httpx.AsyncClient.post", AsyncMock(return_value=mock_response)) as mock_post,
    ):
        res = await adapter.send_email(
            to_email="cto@acme.io",
            subject="Tailored demo for Acme",
            body="Hi Jane, here is your tailored demo.",
            mode="production",
        )

    assert res["status"] == "sent"
    assert res["message_id"] == "graph-req-001"
    assert res["sender"] == "sales@adople.com"
    assert res["recipient"] == "cto@acme.io"
    mock_post.assert_awaited_once()
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["json"]["message"]["subject"] == "Tailored demo for Acme"
    assert call_kwargs["json"]["message"]["toRecipients"][0]["emailAddress"]["address"] == "cto@acme.io"


@pytest.mark.asyncio
async def test_pipeline2_production_mode_end_to_end_and_outlook_approval(
    db_session, seed_data, monkeypatch
):
    """Verify Production Mode runs live Brave, Apollo, LLM, and Outlook send on human approval."""
    org = seed_data["org"]
    rep = seed_data["sales_rep"]

    # Create a real DB account from Pipeline 1 (with no contacts yet so Apollo must enrich!)
    account = Account(
        organization_id=org.id,
        name="Acme Robotics Inc",
        domain="acmerobotics.io",
        industry="Robotics & AI",
        fit_score=0.92,
        status="prioritized",
    )
    db_session.add(account)
    await db_session.flush()

    signal = BuyingSignal(
        organization_id=org.id,
        account_id=account.id,
        signal_type="ai_hiring",
        fit_reason="Hiring 15 AI engineers to scale autonomous systems",
        fit_score=0.92,
        evidence_url="https://acmerobotics.io/careers",
        observed_at="2026-11-18T10:00:00Z",
    )
    db_session.add(signal)
    await db_session.flush()

    # Configure mock boundaries for live external adapters (simulating real API responses)
    brave = BraveSearchAdapter(api_key="BSA-live-test-key")
    brave.research_company = AsyncMock(
        return_value={
            "status": "completed",
            "results": [{"title": "Acme Series B", "url": "https://technews.io/acme", "description": "Raised $50M for AI expansion"}],
            "signals": [
                {
                    "signal_id": "brave-1",
                    "type": "company_research",
                    "observed_fact": "Acme Series B: Raised $50M for AI expansion",
                    "source": {"url": "https://technews.io/acme", "source_type": "brave_search"},
                    "confidence": "verified",
                }
            ],
            "error": None,
        }
    )

    apollo = ApolloAdapter(api_key="apollo-live-test-key")
    apollo.enrich_organization = AsyncMock(
        return_value={"industry": "Robotics & AI", "estimated_num_employees": 420}
    )
    apollo.search_contacts = AsyncMock(
        return_value=[
            {
                "contact_id": "apollo-person-1",
                "first_name": "Priya",
                "last_name": "Nair",
                "full_name": "Priya Nair",
                "job_title": "CTO",
                "seniority": "c_suite",
                "email": "priya.nair@acmerobotics.io",
                "phone": "+14155550199",
                "verification_status": "verified",
                "source": "apollo_live",
                "is_suppressed": False,
                "logical_outreach_attempts": 0,
                "contact_eligibility": "eligible",
            }
        ]
    )

    llm = LLMGateway()
    llm.generate_completion = AsyncMock(
        return_value={
            "company_overview": "Acme Robotics Inc is scaling its AI engineering team after Series B.",
            "buying_signal_analysis": "Strong AI hiring momentum combined with recent $50M funding.",
            "potential_business_needs": "Accelerating enterprise demos and inbound technical qualification.",
        }
    )

    agent = ResearchOutreachAgent(
        brave_adapter=brave,
        apollo_adapter=apollo,
        analyzer=OpportunityAnalyzer(llm_gateway=llm),
    )

    # Execute Pipeline 2 in production mode (with include_demo=False to test decoupled mode too)
    req = AgentExecutionRequest(
        agent_id="research_personal_outreach",
        organization_id=org.id,
        account_id=account.id,
        correlation_id="prod-corr-001",
        parameters={"execution_mode": "production", "include_demo": False},
    )
    result = await agent.execute(req, db_session)

    assert result.status == AgentStatus.WAITING_FOR_REVIEW
    sr = result.structured_result
    assert sr["execution_mode"] == "production"
    assert sr["stage_statuses"]["research"] == "completed"
    assert sr["stage_statuses"]["enrichment"] == "completed_added_1"
    assert sr["selected_primary_contact"]["email"] == "priya.nair@acmerobotics.io"
    assert sr["optional_demo_recommendation_or_reference"] is None  # include_demo=False respected
    assert sr["personalized_outreach_draft"]["subject"]
    assert "Priya" in sr["personalized_outreach_draft"]["draft_body"]

    # Verify newly enriched Apollo contact was persisted in DB
    db_contacts = (
        await db_session.execute(select(Contact).where(Contact.account_id == account.id))
    ).scalars().all()
    assert len(db_contacts) == 1
    assert db_contacts[0].email == "priya.nair@acmerobotics.io"

    # Now simulate Human Approval in Production Mode -> triggers Outlook email send!
    monkeypatch.setattr(settings, "PIPELINE2_EXECUTION_MODE", "production")
    mail_adapter = OutlookMailAdapter(
        client_id="11111111-1111-1111-1111-111111111111",
        client_secret="real-secret",
        tenant_id="22222222-2222-2222-2222-222222222222",
        sender_email="sales@adople.com",
    )
    mail_adapter.send_email = AsyncMock(
        return_value={
            "status": "sent",
            "provider": "microsoft_outlook",
            "sender": "sales@adople.com",
            "recipient": "priya.nair@acmerobotics.io",
            "subject": sr["personalized_outreach_draft"]["subject"],
            "message_id": "ms-graph-msg-999",
            "error": None,
        }
    )

    approval_service = ApprovalService(db_session, mail_adapter=mail_adapter)
    current_user = CurrentUser(
        id=rep.id,
        email=rep.email,
        organization_id=org.id,
        roles=[RoleEnum.SALES_REPRESENTATIVE.value],
    )
    approved = await approval_service.process_decision(
        approval_id=sr["approval_id"],
        decision="approved",
        current_user=current_user,
        feedback="Looks great, send via Outlook.",
    )

    assert approved.status == "approved"
    mail_adapter.send_email.assert_awaited_once()
    delivery = approved.source_evidence["email_delivery"]
    assert delivery["status"] == "sent"
    assert delivery["message_id"] == "ms-graph-msg-999"
    assert delivery["attempt_number"] == 1

    # Verify Conversation, outbound Message, and OutreachAttempt were recorded in DB
    convs = (await db_session.execute(select(Conversation))).scalars().all()
    msgs = (await db_session.execute(select(Message))).scalars().all()
    attempts = (await db_session.execute(select(OutreachAttempt))).scalars().all()
    assert len(convs) == 1 and convs[0].channel == "email"
    assert len(msgs) == 1 and msgs[0].direction == "outbound" and msgs[0].status == "sent"
    assert len(attempts) == 1 and attempts[0].attempt_number == 1


@pytest.mark.asyncio
async def test_test_mode_approval_never_sends_outlook_email(db_session, seed_data, monkeypatch):
    """Ensure approving a Test Mode draft NEVER sends an email even if production flag is toggled."""
    org = seed_data["org"]
    rep = seed_data["sales_rep"]

    agent = ResearchOutreachAgent()
    req = AgentExecutionRequest(
        agent_id="research_personal_outreach",
        organization_id=org.id,
        account_id="ACC-001",
        correlation_id="test-no-send-001",
        parameters={"use_sample_data": True},
    )
    res = await agent.execute(req, db_session)
    assert res.status == AgentStatus.WAITING_FOR_REVIEW
    assert res.structured_result["execution_mode"] == "test"

    mail_adapter = OutlookMailAdapter()
    mail_adapter.send_email = AsyncMock()
    approval_service = ApprovalService(db_session, mail_adapter=mail_adapter)
    current_user = CurrentUser(
        id=rep.id,
        email=rep.email,
        organization_id=org.id,
        roles=[RoleEnum.SALES_REPRESENTATIVE.value],
    )
    monkeypatch.setattr(settings, "ENABLE_MESSAGE_SENDING", True)

    approved = await approval_service.process_decision(
        approval_id=res.structured_result["approval_id"],
        decision="approved",
        current_user=current_user,
    )
    assert approved.status == "approved"
    mail_adapter.send_email.assert_not_awaited()


@pytest.mark.asyncio
async def test_production_approval_blocks_suppressed_recipient(db_session, seed_data, monkeypatch):
    """Ensure Outlook email sending is blocked if recipient was suppressed before human approval."""
    org = seed_data["org"]
    rep = seed_data["sales_rep"]

    account = Account(
        organization_id=org.id,
        name="Blocked Corp",
        domain="blockedcorp.io",
        fit_score=0.75,
        status="prioritized",
    )
    db_session.add(account)
    await db_session.flush()

    contact = Contact(
        organization_id=org.id,
        account_id=account.id,
        first_name="Sam",
        last_name="Lee",
        email="sam.lee@blockedcorp.io",
        title="CTO",
    )
    db_session.add(contact)
    await db_session.flush()

    approval_service = ApprovalService(db_session)
    approval_service.mail_adapter.send_email = AsyncMock()
    item = await approval_service.create_approval_request(
        organization_id=org.id,
        account_id=account.id,
        contact_id=contact.id,
        artifact_type="outreach_draft",
        artifact_id="brief-1",
        requested_action="send_outreach",
        draft_content="Hi Sam, quick note.",
        source_evidence={
            "execution_mode": "production",
            "recipient_email": "sam.lee@blockedcorp.io",
            "subject": "Hello Sam",
        },
    )

    # Suppress contact right before approval
    supp = SuppressionService(db_session)
    await supp.record_suppression(org.id, reason="opt_out", email="sam.lee@blockedcorp.io")

    monkeypatch.setattr(settings, "PIPELINE2_EXECUTION_MODE", "production")
    current_user = CurrentUser(
        id=rep.id,
        email=rep.email,
        organization_id=org.id,
        roles=[RoleEnum.SALES_REPRESENTATIVE.value],
    )
    approved = await approval_service.process_decision(item.id, "approved", current_user)
    assert approved.source_evidence["email_delivery"]["status"] == "blocked_suppressed"
    approval_service.mail_adapter.send_email.assert_not_awaited()

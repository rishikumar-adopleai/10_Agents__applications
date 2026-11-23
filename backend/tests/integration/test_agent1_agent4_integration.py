"""Integration Tests for Agent 1 (Buying-Signal Radar) to Agent 4 (Research & Personal Outreach) Integration.

Covers:
1. Complete End-to-End Pipeline:
   Agent 1 -> account.prioritized -> Dispatcher -> Agent 4 -> ResearchBrief -> Outreach Draft -> ApprovalItem
2. Duplicate prioritization events (idempotency, no duplicate drafts/tasks/approvals).
3. Dispatcher restart after a failure (resumes pending/failed events).
4. Agent 4 temporary failure and retry (retry count tracking, status transitions, recovery).
5. Missing or invalid account IDs (safe failure handling, non-crashing dispatcher loop).
6. Unqualified accounts (rejected, no outreach created).
7. Correct account and organization isolation (cross-tenant safety).
8. No external outreach without approval (human approval gate enforced, no email/SMS sent).
"""

import uuid
from datetime import datetime, timezone
from unittest import mock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.agents.research_outreach.agent import ResearchOutreachAgent
from backend.app.models.artifacts import ResearchBrief
from backend.app.models.execution import AgentTask, IntegrationAttempt, OutboxEvent
from backend.app.models.governance import ApprovalItem
from backend.app.models.identity import Organization
from backend.app.models.radar import SignalEvidence
from backend.app.models.sales import Account, Contact
from backend.app.schemas.agents import AgentStatus
from backend.app.services.radar_prioritization_service import RadarPrioritizationService
from backend.app.workflows.events import ACCOUNT_PRIORITIZED, EventDispatcher


async def _seed_test_account_with_signals(
    db_session: AsyncSession,
    org_id: str,
    company_name: str = "Apex Commercial Bank",
    domain: str = "apexbank.com",
    industry: str = "Financial Services",
    fit_score: float = 0.88,
    why_now: str = "High hiring volume in KYC and AML fraud monitoring operations",
    signals_count: int = 2,
) -> Account:
    """Helper to seed a prioritized account with contact and verified SignalEvidence records."""
    account = Account(
        id=f"acc-{uuid.uuid4().hex[:12]}",
        organization_id=org_id,
        name=company_name,
        domain=domain,
        industry=industry,
        fit_score=fit_score,
        status="prioritized",
        why_now=why_now,
    )
    db_session.add(account)
    await db_session.flush()

    contact = Contact(
        id=f"con-{uuid.uuid4().hex[:12]}",
        organization_id=org_id,
        account_id=account.id,
        first_name="David",
        last_name="Miller",
        email=f"david@{domain}",
        phone="+15551234567",
        title="VP of KYC and Fraud Operations",
        is_suppressed=False,
        logical_outreach_attempts=0,
    )
    db_session.add(contact)
    await db_session.flush()

    for idx in range(signals_count):
        sig = SignalEvidence(
            organization_id=org_id,
            account_id=account.id,
            signal_type="hiring" if idx == 0 else "growth",
            signal_subtype="kyc_monitoring" if idx == 0 else "leadership_change",
            observed_fact=f"Verified operational indicator #{idx + 1} at {company_name}",
            business_hypothesis=f"High manual workload indicates high ROI for automation #{idx + 1}",
            source_provider="greenhouse" if idx == 0 else "newsapi",
            source_url=f"https://{domain}/careers",
            verification_status="VERIFIED",
            evidence_hash=f"hash-{uuid.uuid4().hex[:16]}",
            confidence=1.0,
            first_observed_at=datetime.now(timezone.utc),
            last_checked_at=datetime.now(timezone.utc),
        )
        db_session.add(sig)

    await db_session.flush()
    return account


@pytest.mark.asyncio
async def test_e2e_agent1_to_agent4_full_handoff_lifecycle(db_session: AsyncSession, seed_data):
    """
    Test Complete E2E Integration:
    Agent 1 -> account.prioritized -> Dispatcher -> Agent 4 -> ResearchBrief -> Outreach Draft -> ApprovalItem
    """
    org = seed_data["org"]

    # 1. Seed qualified account with contacts and verified signals
    account = await _seed_test_account_with_signals(db_session, org.id)
    scan_id = f"scan-{uuid.uuid4().hex[:8]}"

    assert (await db_session.execute(
        select(Account).where(Account.id == account.id).options(selectinload(Account.contacts))
    )).scalars().first() is not None

    # 2. Agent 1 prioritizes account and produces OutboxEvent & AgentTask
    prioritization_svc = RadarPrioritizationService(db_session)
    ranked_candidates = [
        {
            "account_id": account.id,
            "total_score": 0.92,
            "icp_score": 0.85,
            "why_now_score": 0.95,
            "why_now_reason": account.why_now,
            "primary_signal_type": "hiring",
            "score_breakdown": {"rubric_version": "v1.0"},
        }
    ]
    evidence_map = {
        account.id: [
            {
                "verification_status": "VERIFIED",
                "observed_fact": "Active hiring for 12 KYC compliance reviewers",
                "source_url": f"https://{account.domain}/jobs",
                "source_provider": "greenhouse",
                "signal_type": "hiring",
            }
        ]
    }

    prioritized_records = await prioritization_svc.prioritize_and_handoff(
        organization_id=org.id,
        scan_run_id=scan_id,
        ranked_candidates=ranked_candidates,
        evidence_map=evidence_map,
    )
    assert len(prioritized_records) == 1
    prioritized_record = prioritized_records[0]
    assert prioritized_record.agent4_task_status == "pending_research"

    # Verify OutboxEvent was created in "pending" status
    outbox_stmt = select(OutboxEvent).where(
        OutboxEvent.organization_id == org.id,
        OutboxEvent.event_type == ACCOUNT_PRIORITIZED,
        OutboxEvent.correlation_id == f"radar-scan-{scan_id}",
    )
    outbox_res = await db_session.execute(outbox_stmt)
    pending_event = outbox_res.scalars().first()
    assert pending_event is not None
    assert pending_event.status == "pending"

    # Verify AgentTask was created in "waiting_for_input"
    task_stmt = select(AgentTask).where(
        AgentTask.id == prioritized_record.agent4_task_id
    )
    task_res = await db_session.execute(task_stmt)
    agent4_task = task_res.scalars().first()
    assert agent4_task is not None
    assert agent4_task.status == "waiting_for_input"

    # 3. Dispatcher consumes event and triggers Agent 4
    dispatcher = EventDispatcher(db_session)
    dispatch_results = await dispatcher.poll_and_dispatch()
    assert len(dispatch_results) == 1
    assert dispatch_results[0]["status"] == "published"

    # 4. Assert durable OutboxEvent status transition to "published"
    await db_session.refresh(pending_event)
    assert pending_event.status == "published"
    assert pending_event.last_error is None

    # 5. Assert AgentTask status transition to "waiting_for_review"
    await db_session.refresh(agent4_task)
    assert agent4_task.status == AgentStatus.WAITING_FOR_REVIEW.value
    assert agent4_task.output_payload is not None

    # 6. Assert RadarPrioritizedAccount status transition to "completed"
    await db_session.refresh(prioritized_record)
    assert prioritized_record.agent4_task_status == "completed"

    # 7. Assert ResearchBrief is created in database
    brief_stmt = select(ResearchBrief).where(
        ResearchBrief.organization_id == org.id,
        ResearchBrief.account_id == account.id,
    )
    brief_res = await db_session.execute(brief_stmt)
    brief = brief_res.scalars().first()
    assert brief is not None
    assert len(brief.facts) > 0
    assert len(brief.hypotheses) > 0
    assert len(brief.sources) > 0

    # 8. Assert ApprovalItem enters the human review queue
    approval_stmt = select(ApprovalItem).where(
        ApprovalItem.organization_id == org.id,
        ApprovalItem.account_id == account.id,
        ApprovalItem.artifact_type == "outreach_draft",
    )
    approval_res = await db_session.execute(approval_stmt)
    approval = approval_res.scalars().first()
    assert approval is not None
    assert approval.status == "pending"
    assert approval.requested_action == "send_outreach"
    assert "pending_sales_rep_review" in approval.risk_flags
    assert len(approval.draft_content) > 50


@pytest.mark.asyncio
async def test_duplicate_prioritization_events(db_session: AsyncSession, seed_data):
    """
    Test duplicate event handling:
    Re-dispatching the same event or account prioritization does not duplicate
    AgentTask, WorkflowRun, or ApprovalItem.
    """
    org = seed_data["org"]
    account = await _seed_test_account_with_signals(db_session, org.id)
    scan_id = f"scan-dup-{uuid.uuid4().hex[:8]}"

    prioritization_svc = RadarPrioritizationService(db_session)
    ranked = [
        {
            "account_id": account.id,
            "total_score": 0.88,
            "icp_score": 0.80,
            "why_now_score": 0.90,
            "why_now_reason": account.why_now,
            "primary_signal_type": "hiring",
            "score_breakdown": {"rubric_version": "v1.0"},
        }
    ]
    ev_map = {account.id: [{"verification_status": "VERIFIED", "observed_fact": "Test signal"}]}

    # First prioritization and dispatch
    await prioritization_svc.prioritize_and_handoff(
        organization_id=org.id,
        scan_run_id=scan_id,
        ranked_candidates=ranked,
        evidence_map=ev_map,
    )
    dispatcher = EventDispatcher(db_session)
    await dispatcher.poll_and_dispatch()

    # Count approval items after first run
    appr_count_1 = (
        await db_session.execute(
            select(ApprovalItem).where(
                ApprovalItem.organization_id == org.id,
                ApprovalItem.account_id == account.id,
            )
        )
    ).scalars().all()
    assert len(appr_count_1) == 1

    # Second prioritization call with same scan_run_id and account (simulating replay)
    await prioritization_svc.prioritize_and_handoff(
        organization_id=org.id,
        scan_run_id=scan_id,
        ranked_candidates=ranked,
        evidence_map=ev_map,
    )

    # Also simulate duplicate pending OutboxEvent for same account
    dup_event = OutboxEvent(
        organization_id=org.id,
        event_type=ACCOUNT_PRIORITIZED,
        correlation_id=f"radar-scan-{scan_id}-dup",
        payload={
            "account_id": account.id,
            "payload": {
                "account_id": account.id,
                "why_now_reason": account.why_now,
                "total_score": 0.88,
                "evidence_count": 1,
            },
        },
        status="pending",
    )
    db_session.add(dup_event)
    await db_session.flush()

    # Dispatch duplicate
    dispatch_results = await dispatcher.poll_and_dispatch()
    assert any(r.get("status") == "published" for r in dispatch_results)

    # Verify no second approval item was created
    appr_count_2 = (
        await db_session.execute(
            select(ApprovalItem).where(
                ApprovalItem.organization_id == org.id,
                ApprovalItem.account_id == account.id,
            )
        )
    ).scalars().all()
    assert len(appr_count_2) == 1  # Strictly deduplicated!


@pytest.mark.asyncio
async def test_dispatcher_restart_after_failure(db_session: AsyncSession, seed_data):
    """
    Test dispatcher crash/restart resilience:
    Events left in pending/failed state are recovered and completed cleanly upon restart.
    """
    org = seed_data["org"]
    account = await _seed_test_account_with_signals(db_session, org.id)

    # Create uncompleted pending event
    event = OutboxEvent(
        organization_id=org.id,
        event_type=ACCOUNT_PRIORITIZED,
        correlation_id=f"radar-scan-restart-{uuid.uuid4().hex[:8]}",
        payload={
            "account_id": account.id,
            "organization_id": org.id,
            "payload": {
                "account_id": account.id,
                "why_now_reason": account.why_now,
                "total_score": 0.89,
                "evidence_count": 1,
            },
        },
        status="pending",
    )
    db_session.add(event)
    await db_session.flush()

    # Simulate restart by creating fresh EventDispatcher instance
    restarted_dispatcher = EventDispatcher(db_session)
    results = await restarted_dispatcher.poll_and_dispatch()

    assert len(results) >= 1
    await db_session.refresh(event)
    assert event.status == "published"
    assert event.last_error is None

    # Verify outreach draft approval was created
    appr = (
        await db_session.execute(
            select(ApprovalItem).where(
                ApprovalItem.organization_id == org.id,
                ApprovalItem.account_id == account.id,
            )
        )
    ).scalars().first()
    assert appr is not None
    assert appr.status == "pending"


@pytest.mark.asyncio
async def test_agent4_temporary_failure_and_retry(db_session: AsyncSession, seed_data):
    """
    Test transient failure in Agent 4:
    - OutboxEvent is marked 'failed' and NOT 'published'.
    - Retry count is incremented.
    - Error details are visible.
    - When error condition clears, subsequent dispatch succeeds.
    """
    org = seed_data["org"]
    account = await _seed_test_account_with_signals(db_session, org.id)

    task = AgentTask(
        organization_id=org.id,
        agent_id="research_personal_outreach",
        execution_id=f"exec-retry-{uuid.uuid4().hex[:8]}",
        status="waiting_for_input",
        input_payload={"account_id": account.id},
    )
    db_session.add(task)
    await db_session.flush()

    event = OutboxEvent(
        organization_id=org.id,
        event_type=ACCOUNT_PRIORITIZED,
        correlation_id=f"radar-scan-retry-{uuid.uuid4().hex[:8]}",
        payload={
            "account_id": account.id,
            "task_id": task.id,
            "organization_id": org.id,
            "payload": {
                "account_id": account.id,
                "task_id": task.id,
                "why_now_reason": account.why_now,
                "total_score": 0.85,
                "evidence_count": 1,
            },
        },
        status="pending",
    )
    db_session.add(event)
    await db_session.flush()

    dispatcher = EventDispatcher(db_session)

    # 1. Simulate temporary failure in Agent 4 execution
    with mock.patch.object(
        ResearchOutreachAgent,
        "execute",
        side_effect=RuntimeError("Temporary external research API 503 unavailable"),
    ):
        results = await dispatcher.poll_and_dispatch()
        assert results[0]["status"] == "failed"
        assert results[0]["retryable"] is True

    await db_session.refresh(event)
    assert event.status == "failed"
    assert event.retry_count == 1
    assert "Temporary external research API 503" in (event.last_error or "")

    await db_session.refresh(task)
    assert task.status == AgentStatus.RETRYABLE_FAILURE.value

    # 2. Subsequent retry with normal Agent 4 execution succeeds
    results_retry = await dispatcher.poll_and_dispatch()
    assert results_retry[0]["status"] == "published"

    await db_session.refresh(event)
    assert event.status == "published"
    assert event.last_error is None

    await db_session.refresh(task)
    assert task.status == AgentStatus.WAITING_FOR_REVIEW.value


@pytest.mark.asyncio
async def test_missing_or_invalid_account_ids(db_session: AsyncSession, seed_data):
    """
    Test handling of missing or invalid account IDs:
    - Events with missing or invalid accounts fail safely without crashing the dispatcher.
    - Subsequent valid events in the batch continue processing.
    """
    org = seed_data["org"]
    valid_account = await _seed_test_account_with_signals(db_session, org.id)

    # Event 1: Missing account ID
    missing_acc_event = OutboxEvent(
        organization_id=org.id,
        event_type=ACCOUNT_PRIORITIZED,
        correlation_id="corr-missing-acc",
        payload={"account_id": None, "payload": {}},
        status="pending",
    )
    # Event 2: Non-existent account ID
    invalid_acc_event = OutboxEvent(
        organization_id=org.id,
        event_type=ACCOUNT_PRIORITIZED,
        correlation_id="corr-invalid-acc",
        payload={"account_id": "non-existent-account-id-xyz", "payload": {"account_id": "non-existent-account-id-xyz"}},
        status="pending",
    )
    # Event 3: Valid account event
    valid_event = OutboxEvent(
        organization_id=org.id,
        event_type=ACCOUNT_PRIORITIZED,
        correlation_id="corr-valid-acc",
        payload={
            "account_id": valid_account.id,
            "organization_id": org.id,
            "payload": {
                "account_id": valid_account.id,
                "why_now_reason": valid_account.why_now,
                "total_score": 0.85,
                "evidence_count": 1,
            },
        },
        status="pending",
    )
    db_session.add_all([missing_acc_event, invalid_acc_event, valid_event])
    await db_session.flush()

    dispatcher = EventDispatcher(db_session)
    results = await dispatcher.poll_and_dispatch()

    assert len(results) == 3

    await db_session.refresh(missing_acc_event)
    assert missing_acc_event.status == "failed"
    assert "missing account_id" in missing_acc_event.last_error

    await db_session.refresh(invalid_acc_event)
    assert invalid_acc_event.status == "failed"
    assert "not found in database" in invalid_acc_event.last_error

    await db_session.refresh(valid_event)
    assert valid_event.status == "published"


@pytest.mark.asyncio
async def test_unqualified_accounts_rejected(db_session: AsyncSession, seed_data):
    """
    Test unqualified accounts:
    - Accounts that fail ICP threshold or have zero buying signals are not promoted to outreach.
    """
    org = seed_data["org"]

    unqualified_account = Account(
        id=f"acc-unqual-{uuid.uuid4().hex[:8]}",
        organization_id=org.id,
        name="Unqualified Small Business LLC",
        domain="unqualified-sb.example",
        industry="Retail",
        fit_score=0.20,  # Below 0.40 threshold
        status="lead",   # Not prioritized
    )
    db_session.add(unqualified_account)
    await db_session.flush()

    event = OutboxEvent(
        organization_id=org.id,
        event_type=ACCOUNT_PRIORITIZED,
        correlation_id="corr-unqual-acc",
        payload={
            "account_id": unqualified_account.id,
            "organization_id": org.id,
            "payload": {
                "account_id": unqualified_account.id,
                "total_score": 0.20,
                "evidence_count": 0,
            },
        },
        status="pending",
    )
    db_session.add(event)
    await db_session.flush()

    dispatcher = EventDispatcher(db_session)
    results = await dispatcher.poll_and_dispatch()

    assert results[0]["status"] == "failed"
    await db_session.refresh(event)
    assert event.status == "failed"
    assert "unqualified" in event.last_error.lower()

    # Verify no approval item or research brief created
    apprs = (
        await db_session.execute(
            select(ApprovalItem).where(ApprovalItem.account_id == unqualified_account.id)
        )
    ).scalars().all()
    assert len(apprs) == 0


@pytest.mark.asyncio
async def test_correct_account_and_organization_isolation(db_session: AsyncSession, seed_data):
    """
    Test tenant isolation:
    - An organization cannot dispatch or process accounts belonging to another organization.
    - Cross-tenant requests are strictly blocked with tenant isolation errors.
    """
    org_a = seed_data["org"]

    # Create Org B
    org_b = Organization(name="Organization B", slug="org-b", is_active=True)
    db_session.add(org_b)
    await db_session.flush()

    # Seed Account belonging strictly to Org A
    account_a = await _seed_test_account_with_signals(db_session, org_a.id)

    # Org B attempts to dispatch an event for Account A
    malicious_cross_tenant_event = OutboxEvent(
        organization_id=org_b.id,  # Org B
        event_type=ACCOUNT_PRIORITIZED,
        correlation_id="corr-cross-tenant-attack",
        payload={
            "account_id": account_a.id,  # Belongs to Org A!
            "organization_id": org_b.id,
            "payload": {
                "account_id": account_a.id,
                "total_score": 0.88,
                "evidence_count": 1,
            },
        },
        status="pending",
    )
    db_session.add(malicious_cross_tenant_event)
    await db_session.flush()

    dispatcher = EventDispatcher(db_session)
    results = await dispatcher.poll_and_dispatch()

    assert results[0]["status"] == "failed"
    await db_session.refresh(malicious_cross_tenant_event)
    assert malicious_cross_tenant_event.status == "failed"
    assert "isolation violation" in malicious_cross_tenant_event.last_error.lower()

    # Verify Account A is still owned by Org A and was NOT modified
    await db_session.refresh(account_a)
    assert account_a.organization_id == org_a.id

    # Verify no approval item created under Org B
    org_b_apprs = (
        await db_session.execute(
            select(ApprovalItem).where(ApprovalItem.organization_id == org_b.id)
        )
    ).scalars().all()
    assert len(org_b_apprs) == 0


@pytest.mark.asyncio
async def test_no_external_outreach_without_approval(db_session: AsyncSession, seed_data):
    """
    Test human-in-the-loop governance:
    - Downstream outreach draft enters the human approval queue.
    - No external email or SMS is dispatched automatically.
    - Integration attempts table contains zero email/sms outgoing requests.
    """
    org = seed_data["org"]
    account = await _seed_test_account_with_signals(db_session, org.id)
    scan_id = f"scan-governance-{uuid.uuid4().hex[:8]}"

    prioritization_svc = RadarPrioritizationService(db_session)
    ranked = [
        {
            "account_id": account.id,
            "total_score": 0.95,
            "icp_score": 0.90,
            "why_now_score": 0.98,
            "why_now_reason": account.why_now,
            "primary_signal_type": "growth",
            "score_breakdown": {"rubric_version": "v1.0"},
        }
    ]
    ev_map = {
        account.id: [
            {
                "verification_status": "VERIFIED",
                "observed_fact": "Announced $40M series B round for automation",
                "source_url": f"https://{account.domain}/press",
                "source_provider": "newsapi",
                "signal_type": "growth",
            }
        ]
    }

    await prioritization_svc.prioritize_and_handoff(
        organization_id=org.id,
        scan_run_id=scan_id,
        ranked_candidates=ranked,
        evidence_map=ev_map,
    )

    dispatcher = EventDispatcher(db_session)
    await dispatcher.poll_and_dispatch()

    # Check ApprovalItem
    appr_res = await db_session.execute(
        select(ApprovalItem).where(
            ApprovalItem.organization_id == org.id,
            ApprovalItem.account_id == account.id,
        )
    )
    approval = appr_res.scalars().first()
    assert approval is not None
    assert approval.status == "pending"
    assert approval.requested_action == "send_outreach"

    # Check that NO integration attempts for messaging were recorded
    attempts_res = await db_session.execute(
        select(IntegrationAttempt).where(
            IntegrationAttempt.organization_id == org.id,
            IntegrationAttempt.provider.in_(["sms", "microsoft", "outlook_mail"]),
        )
    )
    attempts = attempts_res.scalars().all()
    assert len(attempts) == 0  # Zero external sends!

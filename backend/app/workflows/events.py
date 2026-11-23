"""Event Contracts and Event Dispatcher conforming to the Implementation Plan."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.logging import logger
from backend.app.models.execution import OutboxEvent
from backend.app.models.governance import ApprovalItem
from backend.app.models.radar import SignalEvidence
from backend.app.models.sales import Account
from backend.app.repositories.execution_repo import AgentTaskRepository, OutboxRepository
from backend.app.schemas.agents import AgentStatus
from backend.app.workflows.definitions import PlatformWorkflows


class EventContract(BaseModel):
    """Standard Event Envelope conforming to Section 5 of the Implementation Plan."""

    event_id: str
    schema_version: str = "1.0"
    event_type: str
    organization_id: str
    account_id: Optional[str] = None
    contact_id: Optional[str] = None
    workflow_id: Optional[str] = None
    task_id: Optional[str] = None
    occurred_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    correlation_id: str
    payload: Dict[str, Any] = Field(default_factory=dict)


# Standard Domain Event Names
ACCOUNT_PRIORITIZED = "account.prioritized"
RESEARCH_COMPLETED = "research.completed"
DEMO_READY = "demo.ready"
OUTREACH_APPROVED = "outreach.approved"
MESSAGE_RECEIVED = "message.received"
MEETING_CONFIRMED = "meeting.confirmed"
DISCOVERY_COMPLETED = "discovery.completed"
SECURITY_REVIEW_REQUESTED = "security_review.requested"
DELIVERY_MILESTONE_VERIFIED = "delivery_milestone.verified"
PROOF_APPROVED = "proof.approved"
REVIVAL_REVIEW_REQUESTED = "revival.review_requested"


class EventDispatcher:
    """
    Durable, idempotent Event Dispatcher consuming transactional outbox events
    and scheduling downstream platform workflows.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.outbox_repo = OutboxRepository(session)
        self.task_repo = AgentTaskRepository(session)
        self.workflows = PlatformWorkflows(session)

    async def poll_and_dispatch(
        self,
        limit: int = 50,
        max_retries: int = 3,
    ) -> List[Dict[str, Any]]:
        """Poll pending and retryable outbox events, dispatching them to configured handlers."""
        events = await self.outbox_repo.get_retryable_events(max_retries=max_retries, limit=limit)
        results = []
        for event in events:
            try:
                res = await self.dispatch_event(event)
                results.append(res)
            except Exception as exc:
                logger.exception(f"Unhandled error during dispatch of event {event.id}: {exc}")
                event.status = "failed"
                event.retry_count = (event.retry_count or 0) + 1
                event.last_error = str(exc)
                await self.outbox_repo.update(
                    event,
                    {
                        "status": "failed",
                        "retry_count": event.retry_count,
                        "last_error": event.last_error,
                    },
                )
                results.append({"status": "failed", "event_id": event.id, "error": str(exc)})
        return results

    async def dispatch_event(self, event: OutboxEvent) -> Dict[str, Any]:
        """Dispatch a single outbox event to its corresponding workflow/agent handler."""
        if event.status == "published":
            logger.info(f"Outbox event {event.id} is already published; skipping.")
            return {"status": "skipped", "reason": "already_published", "event_id": event.id}

        logger.info(f"Consuming outbox event {event.id} [type={event.event_type}]")

        if event.event_type == ACCOUNT_PRIORITIZED:
            return await self._handle_account_prioritized(event)
        else:
            logger.warning(f"No specific handler configured for event type '{event.event_type}'; marking published.")
            event.status = "published"
            await self.outbox_repo.update(event, {"status": "published"})
            return {"status": "published", "event_id": event.id, "event_type": event.event_type}

    async def _handle_account_prioritized(self, event: OutboxEvent) -> Dict[str, Any]:
        """
        Handle 'account.prioritized' event:
        1. Extract and validate envelope context (account_id, organization_id, evidence).
        2. Validate account qualification and organization-level data isolation.
        3. Check idempotency: avoid duplicate outreach actions if draft/approval already exists.
        4. Durably schedule Agent 4 (Research & Personal Outreach) via ResearchOutreachWorkflow.
        5. Update AgentTask status and mark OutboxEvent published ONLY after confirmation.
        """
        raw_payload = event.payload or {}
        # Unpack envelope: could be flat or wrapped in EventContract
        inner_payload = raw_payload.get("payload") if isinstance(raw_payload.get("payload"), dict) else raw_payload

        account_id = raw_payload.get("account_id") or inner_payload.get("account_id")
        organization_id = event.organization_id or raw_payload.get("organization_id")
        contact_id = raw_payload.get("contact_id") or inner_payload.get("contact_id")
        task_id = raw_payload.get("task_id") or inner_payload.get("task_id")
        correlation_id = event.correlation_id or raw_payload.get("correlation_id") or f"wf-radar-{account_id}"

        # 1. Envelope validation: missing account_id or organization_id
        if not account_id or not organization_id:
            err = f"Invalid account.prioritized event {event.id}: missing account_id='{account_id}' or organization_id='{organization_id}'"
            logger.error(err)
            event.status = "failed"
            event.retry_count = (event.retry_count or 0) + 1
            event.last_error = err
            await self.outbox_repo.update(
                event,
                {"status": "failed", "retry_count": event.retry_count, "last_error": err},
            )
            return {"status": "failed", "event_id": event.id, "error": err, "retryable": False}

        # 2. Database account lookup
        acc_res = await self.session.execute(
            select(Account).where(Account.id == str(account_id))
        )
        account = acc_res.scalars().first()

        if not account:
            err = f"Account '{account_id}' not found in database for event {event.id}"
            logger.error(err)
            event.status = "failed"
            event.retry_count = (event.retry_count or 0) + 1
            event.last_error = err
            await self.outbox_repo.update(
                event,
                {"status": "failed", "retry_count": event.retry_count, "last_error": err},
            )
            if task_id:
                task = await self.task_repo.get_by_id(task_id)
                if task:
                    task.status = AgentStatus.TERMINAL_FAILURE.value
                    task.error_message = err
                    await self.task_repo.update(task, {"status": task.status, "error_message": task.error_message})
            return {"status": "failed", "event_id": event.id, "error": err, "retryable": False}

        # 3. Organization-level data isolation
        if account.organization_id != organization_id:
            err = (
                f"Organization isolation violation: event organization_id='{organization_id}' "
                f"does not match account organization_id='{account.organization_id}'"
            )
            logger.error(err)
            event.status = "failed"
            event.retry_count = (event.retry_count or 0) + 1
            event.last_error = err
            await self.outbox_repo.update(
                event,
                {"status": "failed", "retry_count": event.retry_count, "last_error": err},
            )
            if task_id:
                task = await self.task_repo.get_by_id(task_id)
                if task:
                    task.status = AgentStatus.TERMINAL_FAILURE.value
                    task.error_message = err
                    await self.task_repo.update(task, {"status": task.status, "error_message": task.error_message})
            return {"status": "failed", "event_id": event.id, "error": err, "retryable": False}

        # 4. Qualification check: ensure account meets minimum threshold and has verified signal
        is_qualified = (
            account.status == "prioritized"
            or (account.fit_score is not None and account.fit_score >= 0.40)
            or inner_payload.get("evidence_count", 0) > 0
        )
        if not is_qualified:
            err = f"Account '{account_id}' is unqualified for outreach handoff (fit_score={account.fit_score}, status={account.status})"
            logger.warning(err)
            event.status = "failed"
            event.retry_count = (event.retry_count or 0) + 1
            event.last_error = err
            await self.outbox_repo.update(
                event,
                {"status": "failed", "retry_count": event.retry_count, "last_error": err},
            )
            if task_id:
                task = await self.task_repo.get_by_id(task_id)
                if task:
                    task.status = AgentStatus.TERMINAL_FAILURE.value
                    task.error_message = err
                    await self.task_repo.update(task, {"status": task.status, "error_message": task.error_message})
            return {"status": "failed", "event_id": event.id, "error": err, "retryable": False}

        # 5. Idempotency & Duplicate Outreach Prevention
        # Check if an active or approved outreach draft already exists for this account
        existing_appr = await self.session.execute(
            select(ApprovalItem).where(
                ApprovalItem.organization_id == organization_id,
                ApprovalItem.account_id == account.id,
                ApprovalItem.artifact_type == "outreach_draft",
                ApprovalItem.status.in_(["pending", "approved"]),
            )
        )
        pending_item = existing_appr.scalars().first()

        if pending_item:
            logger.info(
                f"Active outreach draft approval {pending_item.id} already exists for account '{account.id}'; "
                f"marking outbox event {event.id} published without creating duplicate outreach actions."
            )
            event.status = "published"
            event.last_error = None
            await self.outbox_repo.update(event, {"status": "published", "last_error": None})
            if task_id:
                task = await self.task_repo.get_by_id(task_id)
                if task and task.status == AgentStatus.WAITING_FOR_INPUT.value:
                    task.status = AgentStatus.WAITING_FOR_REVIEW.value
                    await self.task_repo.update(task, {"status": task.status})
            return {
                "status": "published",
                "event_id": event.id,
                "message": "Duplicate event handled idempotently; existing outreach draft preserved.",
                "approval_id": pending_item.id,
            }

        # 6. Extract evidence and parameters for Agent 4
        why_now = inner_payload.get("why_now_reason") or account.why_now
        score = inner_payload.get("total_score") or account.fit_score or 0.75
        evidence_items = inner_payload.get("evidence") or []

        # If evidence was not in payload, load from SignalEvidence table
        if not evidence_items:
            sig_res = await self.session.execute(
                select(SignalEvidence).where(
                    SignalEvidence.account_id == account.id,
                    SignalEvidence.organization_id == organization_id,
                )
            )
            db_evs = sig_res.scalars().all()
            evidence_items = [
                {
                    "signal_type": e.signal_type,
                    "signal_subtype": e.signal_subtype,
                    "observed_fact": e.observed_fact,
                    "business_hypothesis": e.business_hypothesis,
                    "source_url": e.source_url,
                    "source_provider": e.source_provider,
                    "verification_status": e.verification_status,
                }
                for e in db_evs
            ]

        # 7. Reliable Scheduling: Execute Agent 4 via ResearchOutreachWorkflow
        workflow_params = {
            "account_id": account.id,
            "company_name": account.name,
            "domain": account.domain,
            "contact_id": contact_id,
            "why_now_reason": why_now,
            "score": score,
            "evidence": evidence_items,
            "task_id": task_id,
            "execution_mode": "test" if str(account.id).startswith("ACC-") else None,
        }

        try:
            workflow_run = await self.workflows.run_research_outreach(
                organization_id=organization_id,
                account_id=account.id,
                contact_id=contact_id,
                parameters=workflow_params,
                correlation_id=correlation_id,
                task_id=task_id,
            )

            # Confirm downstream scheduling outcome
            if workflow_run.status in ("waiting_for_approval", "completed", "waiting_for_input", "blocked"):
                event.status = "published"
                event.last_error = None
                await self.outbox_repo.update(event, {"status": "published", "last_error": None})
                logger.info(
                    f"Successfully dispatched event {event.id}: scheduled Agent 4 workflow {workflow_run.id} [status={workflow_run.status}]"
                )
                return {
                    "status": "published",
                    "event_id": event.id,
                    "workflow_run_id": workflow_run.id,
                    "workflow_status": workflow_run.status,
                }
            else:
                # Execution failed
                err_details = workflow_run.error or "Workflow run ended in failed status"
                if task_id:
                    task = await self.task_repo.get_by_id(task_id)
                    if task and task.error_message:
                        err_details = task.error_message
                event.status = "failed"
                event.retry_count = (event.retry_count or 0) + 1
                event.last_error = err_details
                await self.outbox_repo.update(
                    event,
                    {
                        "status": "failed",
                        "retry_count": event.retry_count,
                        "last_error": err_details,
                    },
                )
                return {
                    "status": "failed",
                    "event_id": event.id,
                    "workflow_run_id": workflow_run.id,
                    "error": err_details,
                    "retryable": True,
                }

        except Exception as exc:
            logger.exception(f"Exception during Agent 4 scheduling for event {event.id}: {exc}")
            event.status = "failed"
            event.retry_count = (event.retry_count or 0) + 1
            event.last_error = str(exc)
            await self.outbox_repo.update(
                event,
                {
                    "status": "failed",
                    "retry_count": event.retry_count,
                    "last_error": str(exc),
                },
            )
            if task_id:
                task = await self.task_repo.get_by_id(task_id)
                if task:
                    task.status = AgentStatus.RETRYABLE_FAILURE.value
                    task.retry_count = (task.retry_count or 0) + 1
                    task.error_message = str(exc)
                    await self.task_repo.update(
                        task,
                        {
                            "status": task.status,
                            "retry_count": task.retry_count,
                            "error_message": task.error_message,
                        },
                    )
            return {"status": "failed", "event_id": event.id, "error": str(exc), "retryable": True}

"""Daily Account Prioritization, Contact Selection & Agent 4 Handoff Service."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.core.logging import logger
from backend.app.models.execution import AgentTask, DomainEvent, OutboxEvent
from backend.app.models.radar import RadarPrioritizedAccount
from backend.app.models.sales import Account, Contact
from backend.app.workflows.events import ACCOUNT_PRIORITIZED, EventContract

# Titles prioritized for outreach by detected signal
CONTACT_ROLE_PRIORITY = {
    "hiring": ["revenue cycle", "claims", "prior authorization", "billing", "operations", "coo", "cio"],
    "regulatory": ["compliance", "regulatory", "interoperability", "him", "coo", "cio", "vp"],
    "growth": ["ceo", "coo", "cro", "vp expansion", "cio", "president"],
    "sec_filing": ["cfo", "controller", "internal audit", "compliance", "cio", "coo"],
    "interest": ["marketing", "sales", "cro", "vp", "director"],
}


def _to_json_safe(val: Any) -> Any:
    """Recursively convert datetime objects to ISO strings for JSON storage."""
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, dict):
        return {k: _to_json_safe(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [_to_json_safe(x) for x in val]
    return val


class RadarPrioritizationService:
    """Ranks accounts, selects contacts, persists daily top-20 shortlist, and hands off to Agent 4."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def select_best_contact(
        self, contacts: List[Contact], primary_signal: str
    ) -> Tuple[Optional[Contact], str]:
        """Match existing contacts against the detected operational signal."""
        if not contacts:
            return None, "research_required"

        keywords = CONTACT_ROLE_PRIORITY.get(primary_signal, ["director", "vp", "chief", "head"])

        # Try to find a matching title
        for kw in keywords:
            for c in contacts:
                title = (c.title or "").lower()
                if kw in title:
                    return c, "verified_contact"

        # Fallback to first verified contact
        return contacts[0], "verified_contact"

    async def prioritize_and_handoff(
        self,
        organization_id: str,
        scan_run_id: str,
        ranked_candidates: List[Dict[str, Any]],
        evidence_map: Dict[str, List[Dict[str, Any]]],
        daily_limit: int = 20,
    ) -> List[RadarPrioritizedAccount]:
        """Select up to daily_limit accounts, record shortlist, emit event, and trigger Agent 4 task."""
        # 1. Filter strictly for qualified accounts: must match ICP AND possess at least one fresh verified buying signal
        qualified_candidates = [
            c for c in ranked_candidates
            if c.get("icp_score", 0) >= 0.40
            and any(
                e.get("verification_status", "VERIFIED") == "VERIFIED"
                for e in evidence_map.get(c["account_id"], [])
            )
        ]

        # 2. Sort by total_score descending
        sorted_candidates = sorted(
            qualified_candidates, key=lambda x: x["total_score"], reverse=True
        )

        # 3. Select up to daily_limit (strictly bounded; never artificially padded when fewer qualified accounts exist)
        top_candidates = sorted_candidates[:daily_limit]
        prioritized_accounts = []

        correlation_id = f"radar-scan-{scan_run_id}"

        for rank_idx, candidate in enumerate(top_candidates, start=1):
            account_id = candidate["account_id"]

            # Load account with contacts
            res = await self.session.execute(
                select(Account)
                .where(Account.id == account_id, Account.organization_id == organization_id)
                .options(selectinload(Account.contacts))
            )
            account = res.scalars().first()
            if not account:
                continue

            # Update account status & fit score
            account.status = "prioritized"
            account.fit_score = candidate["total_score"]
            account.why_now = candidate["why_now_reason"]

            # Select contact candidate
            selected_contact, contact_status = self.select_best_contact(
                account.contacts, candidate["primary_signal_type"]
            )
            contact_id = selected_contact.id if selected_contact else None

            # Rubric version from candidate breakdown
            rubric_version = (
                candidate.get("score_breakdown", {}).get("rubric_version")
                or "demo-v1"
            )

            # Idempotent deterministic event ID and keys
            event_id = f"evt-radar-{scan_run_id[:8]}-{account.id[:8]}"
            idempotency_key = f"radar-prioritized-{scan_run_id}-{account.id}"

            # Check for existing Agent 4 task for this scan & account to avoid duplication on replay
            existing_task_res = await self.session.execute(
                select(AgentTask).where(
                    AgentTask.organization_id == organization_id,
                    AgentTask.agent_id == "research_personal_outreach",
                )
            )
            all_agent4_tasks = existing_task_res.scalars().all()
            matched_task = next(
                (
                    t for t in all_agent4_tasks
                    if (t.input_payload or {}).get("account_id") == account.id
                    and (t.cost_metadata or {}).get("scan_run_id") == scan_run_id
                ),
                None,
            )

            if not matched_task:
                agent4_exec_id = f"exec-agent4-{uuid.uuid4().hex[:12]}"
                matched_task = AgentTask(
                    organization_id=organization_id,
                    agent_id="research_personal_outreach",
                    execution_id=agent4_exec_id,
                    status="waiting_for_input",
                    input_payload={
                        "account_id": account.id,
                        "account_name": account.name,
                        "domain": account.domain,
                        "contact_id": contact_id,
                        "contact_status": contact_status,
                        "why_now_reason": candidate["why_now_reason"],
                        "score": candidate["total_score"],
                        "scoring_rubric_version": rubric_version,
                        "evidence": _to_json_safe(evidence_map.get(account.id, [])),
                    },
                    uncertainty=0.0,
                    cost_metadata={
                        "source": "buying_signal_radar",
                        "scan_run_id": scan_run_id,
                        "idempotency_key": idempotency_key,
                    },
                )
                self.session.add(matched_task)
                await self.session.flush()

            event_contract = EventContract(
                event_id=event_id,
                event_type=ACCOUNT_PRIORITIZED,
                organization_id=organization_id,
                account_id=account.id,
                contact_id=contact_id,
                task_id=matched_task.id,
                workflow_id=f"wf-radar-{account.id}",
                correlation_id=correlation_id,
                payload={
                    "account_name": account.name,
                    "domain": account.domain,
                    "rank": rank_idx,
                    "total_score": candidate["total_score"],
                    "icp_score": candidate["icp_score"],
                    "why_now_score": candidate["why_now_score"],
                    "why_now_reason": candidate["why_now_reason"],
                    "primary_signal_type": candidate["primary_signal_type"],
                    "scoring_rubric_version": rubric_version,
                    "contact_status": contact_status,
                    "evidence_count": len(evidence_map.get(account.id, [])),
                    "idempotency_key": idempotency_key,
                    "task_id": matched_task.id,
                    "execution_id": matched_task.execution_id,
                    "evidence": _to_json_safe(evidence_map.get(account.id, [])),
                },
            )

            # Check if domain and outbox event already exists to ensure replay idempotency
            existing_outbox = await self.session.execute(
                select(OutboxEvent).where(
                    OutboxEvent.organization_id == organization_id,
                    OutboxEvent.correlation_id == correlation_id,
                    OutboxEvent.event_type == ACCOUNT_PRIORITIZED,
                )
            )
            outbox_list = existing_outbox.scalars().all()
            already_dispatched = any(
                (o.payload or {}).get("account_id") == account.id
                or (o.payload or {}).get("payload", {}).get("idempotency_key") == idempotency_key
                for o in outbox_list
            )

            if not already_dispatched:
                domain_event = DomainEvent(
                    organization_id=organization_id,
                    event_type=ACCOUNT_PRIORITIZED,
                    correlation_id=correlation_id,
                    payload=event_contract.model_dump(),
                )
                outbox_event = OutboxEvent(
                    organization_id=organization_id,
                    event_type=ACCOUNT_PRIORITIZED,
                    correlation_id=correlation_id,
                    payload=event_contract.model_dump(),
                    status="pending",
                )
                self.session.add(domain_event)
                self.session.add(outbox_event)

            # Check if Prioritized Account entry already exists
            existing_prioritized = await self.session.execute(
                select(RadarPrioritizedAccount).where(
                    RadarPrioritizedAccount.organization_id == organization_id,
                    RadarPrioritizedAccount.scan_run_id == scan_run_id,
                    RadarPrioritizedAccount.account_id == account.id,
                )
            )
            prioritized_record = existing_prioritized.scalars().first()
            if not prioritized_record:
                prioritized_record = RadarPrioritizedAccount(
                    organization_id=organization_id,
                    scan_run_id=scan_run_id,
                    account_id=account.id,
                    rank=rank_idx,
                    icp_score=candidate["icp_score"],
                    why_now_score=candidate["why_now_score"],
                    total_score=candidate["total_score"],
                    why_now_reason=candidate["why_now_reason"],
                    primary_signal_type=candidate["primary_signal_type"],
                    score_breakdown=candidate["score_breakdown"],
                    suggested_contact_id=contact_id,
                    contact_status=contact_status,
                    agent4_task_status="pending_research",
                    agent4_task_id=matched_task.id,
                    event_id=event_id,
                )
                self.session.add(prioritized_record)
            else:
                # Update ranking & score deterministically
                prioritized_record.rank = rank_idx
                prioritized_record.total_score = candidate["total_score"]
                prioritized_record.why_now_reason = candidate["why_now_reason"]
                prioritized_record.agent4_task_id = matched_task.id

            prioritized_accounts.append(prioritized_record)

        await self.session.flush()
        logger.info(
            f"Prioritization completed: selected {len(prioritized_accounts)} accounts for scan {scan_run_id}."
        )
        return prioritized_accounts

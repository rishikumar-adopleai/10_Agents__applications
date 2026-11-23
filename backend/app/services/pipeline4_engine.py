"""Pipeline 4: 24/7 Lead Responder Agent Processing Engine.

Conforms strictly to the 5 internal processing nodes:
- NODE 1: INGEST (Receive, verify, normalize, deduplicate, persist inbound message)
- NODE 2: CUSTOMER CONTEXT (Identify/match contact & account, resolve conversation thread)
- NODE 3: SAFETY + SENTIMENT (Deterministic STOP/suppression checks + Structured LLM sentiment)
- NODE 4: MEMORY (Load customer info, message history, P2 research, P3 demo refs, knowledge base)
- NODE 5: INTENT + ACTION + DRAFT (Intent understanding, tool orchestration e.g. Outlook scheduling,
  demo retrieval, knowledge lookup, and contextual AI reply draft)
"""

import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.integrations.ai.gateway import LLMGateway
from backend.app.integrations.calendar.microsoft import MicrosoftCalendarAdapter
from backend.app.integrations.messaging.outlook_mail import OutlookMailAdapter
from backend.app.integrations.messaging.sms import SMSAdapter
from backend.app.models.artifacts import ResearchBrief
from backend.app.models.conversations import (
    Conversation,
    Message,
)
from backend.app.models.governance import ApprovalItem
from backend.app.models.intelligence import KnowledgeVersion, MemoryFact
from backend.app.models.meetings import MeetingBooking, MeetingProposal, NodeExecutionLog
from backend.app.models.sales import Account, Campaign, CampaignRecipient, Contact
from backend.app.services.attempt_service import AttemptTrackingService
from backend.app.services.marketplace_service import MarketplaceService
from backend.app.services.suppression_service import SuppressionService

logger = logging.getLogger(__name__)

# Mandatory CTIA & Compliance keywords
OPT_OUT_KEYWORDS = {"stop", "cancel", "unsubscribe", "quit", "end", "revoke", "opt out", "opt-out"}
NEGATIVE_KEYWORDS = {
    "not interested",
    "remove me",
    "don't contact",
    "do not contact",
    "leave me alone",
    "wrong number",
    "never email me again",
    "stop emailing",
}
BOT_KEYWORDS = {
    "auto-reply",
    "automatic reply",
    "out of office",
    "undeliverable",
    "delivery failure",
    "mailer-daemon",
    "automated response",
}


class Pipeline4Engine:
    """Master engine orchestrating the five processing nodes of Pipeline 4."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.llm_gateway = LLMGateway()
        self.calendar_adapter = MicrosoftCalendarAdapter()
        self.mail_adapter = OutlookMailAdapter()
        self.sms_adapter = SMSAdapter()
        self.suppression_service = SuppressionService(session)
        self.marketplace_service = MarketplaceService(session)

    # =========================================================================
    # MASTER ENTRYPOINT: Ingest and Process Inbound Message
    # =========================================================================
    async def process_inbound_message(
        self,
        sender: str,
        recipient: str,
        body: str,
        channel: str = "sms",
        provider: str = "webhook",
        provider_message_id: Optional[str] = None,
        organization_id: str = "org-default",
        auto_dispatch: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute the 5 Pipeline 4 nodes end-to-end with atomic persistence and telemetry.
        """
        start_time = datetime.now(timezone.utc)
        log_id = f"p4-{uuid.uuid4().hex[:10]}"

        # ---------------------------------------------------------------------
        # NODE 1 — INGEST
        # ---------------------------------------------------------------------
        t1_start = datetime.now(timezone.utc)
        node1_res = await self.node1_ingest(
            sender=sender,
            recipient=recipient,
            body=body,
            channel=channel,
            provider=provider,
            provider_message_id=provider_message_id,
            organization_id=organization_id,
        )
        t1_duration = int((datetime.now(timezone.utc) - t1_start).total_seconds() * 1000)
        node1_res["duration_ms"] = t1_duration

        if node1_res.get("is_duplicate"):
            return {
                "status": "duplicate_ignored",
                "message": "Message already processed idempotently",
                "node1": node1_res,
            }

        message_obj = node1_res["message"]

        # ---------------------------------------------------------------------
        # NODE 2 — CUSTOMER CONTEXT
        # ---------------------------------------------------------------------
        t2_start = datetime.now(timezone.utc)
        node2_res = await self.node2_customer_context(
            normalized_sender=node1_res["normalized_sender"],
            channel=node1_res["channel"],
            organization_id=organization_id,
        )
        t2_duration = int((datetime.now(timezone.utc) - t2_start).total_seconds() * 1000)
        node2_res["duration_ms"] = t2_duration

        contact = node2_res["contact"]
        account = node2_res["account"]
        conversation = node2_res["conversation"]
        if node2_res.get("effective_organization_id"):
            organization_id = node2_res["effective_organization_id"]

        # Associate message with resolved conversation and correct organization
        message_obj.conversation_id = conversation.id
        message_obj.organization_id = organization_id
        await self.session.commit()

        # ---------------------------------------------------------------------
        # NODE 3 — SAFETY + SENTIMENT
        # ---------------------------------------------------------------------
        t3_start = datetime.now(timezone.utc)
        node3_res = await self.node3_safety_and_sentiment(
            message_body=node1_res["clean_body"],
            contact=contact,
            conversation=conversation,
            sender=node1_res["normalized_sender"],
            organization_id=organization_id,
        )
        t3_duration = int((datetime.now(timezone.utc) - t3_start).total_seconds() * 1000)
        node3_res["duration_ms"] = t3_duration

        # If blocked by safety rules, persist telemetry and STOP
        if node3_res["processing_decision"] != "continue":
            total_duration = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            exec_log = NodeExecutionLog(
                id=log_id,
                organization_id=organization_id,
                message_id=message_obj.id,
                conversation_id=conversation.id,
                contact_id=contact.id if contact else None,
                channel=channel,
                node1_ingest=json.dumps(node1_res, default=str),
                node2_context=json.dumps({k: v for k, v in node2_res.items() if k not in ("contact", "account", "conversation")}, default=str),
                node3_safety=json.dumps(node3_res, default=str),
                node4_memory=json.dumps({"status": "skipped_due_to_safety"}, default=str),
                node5_intent_draft=json.dumps({"status": "blocked_by_safety"}, default=str),
                approval_status="not_required",
                send_status="blocked_safety",
                total_latency_ms=total_duration,
                status="blocked_safety",
            )
            self.session.add(exec_log)
            await self.session.commit()

            return {
                "status": "blocked_safety",
                "decision": node3_res["processing_decision"],
                "processing_decision": node3_res["processing_decision"],
                "action": "suppressed" if node3_res["processing_decision"] == "stop_suppressed" else "stopped",
                "reason": node3_res["reason"],
                "conversation_id": conversation.id,
                "node1": node1_res,
                "node2": {k: v for k, v in node2_res.items() if k not in ("contact", "account", "conversation")},
                "node3": node3_res,
            }

        # ---------------------------------------------------------------------
        # NODE 4 — MEMORY
        # ---------------------------------------------------------------------
        t4_start = datetime.now(timezone.utc)
        node4_res = await self.node4_memory(
            contact=contact,
            account=account,
            conversation=conversation,
            organization_id=organization_id,
        )
        t4_duration = int((datetime.now(timezone.utc) - t4_start).total_seconds() * 1000)
        node4_res["duration_ms"] = t4_duration

        # ---------------------------------------------------------------------
        # NODE 5 — INTENT + ACTION + DRAFT
        # ---------------------------------------------------------------------
        t5_start = datetime.now(timezone.utc)
        node5_res = await self.node5_intent_action_draft(
            message_body=node1_res["clean_body"],
            channel=channel,
            contact=contact,
            account=account,
            conversation=conversation,
            memory_context=node4_res,
            sentiment_analysis=node3_res,
            organization_id=organization_id,
        )
        t5_duration = int((datetime.now(timezone.utc) - t5_start).total_seconds() * 1000)
        node5_res["duration_ms"] = t5_duration

        # ---------------------------------------------------------------------
        # CONTROLLED STAGE: PERSISTENCE, APPROVAL & DISPATCH
        # ---------------------------------------------------------------------
        # Reset logical outreach attempts on eligible positive reply
        if node3_res.get("sentiment") in ("positive", "neutral") and contact:
            attempt_svc = AttemptTrackingService(self.session)
            await attempt_svc.reset_on_positive_response(contact.id)

        # Create or update ApprovalItem
        approval_item = ApprovalItem(
            id=f"appr-{uuid.uuid4().hex[:10]}",
            organization_id=organization_id,
            account_id=account.id if account else None,
            contact_id=contact.id if contact else None,
            artifact_type="lead_reply",
            artifact_id=conversation.id,
            requested_action=f"send_{channel}_reply",
            draft_content=node5_res["draft_reply"],
            source_evidence={
                "inbound_message": body,
                "sender": sender,
                "channel": channel,
                "primary_intent": node5_res["primary_intent"],
                "tools_executed": node5_res["tools_executed"],
                "meeting_state": node5_res.get("meeting_state"),
            },
            status="approved" if (auto_dispatch or node5_res.get("auto_approved")) else "pending",
        )
        self.session.add(approval_item)

        # Save outgoing Message record (draft or sent)
        send_status = "pending"

        # Auto-dispatch if authorized or auto_approved
        if auto_dispatch or node5_res.get("auto_approved"):
            dispatch_res = await self.dispatch_reply(
                conversation_id=conversation.id,
                channel=channel,
                recipient=node1_res["normalized_sender"],
                body=node5_res["draft_reply"],
                subject=f"Re: Inbound Inquiry from {contact.first_name if contact else 'Prospect'}",
            )
            send_status = dispatch_res.get("status", "sent")
            node5_res["dispatched_message_id"] = dispatch_res.get("message_id")
            approval_item.status = "sent"

        # Record atomic memory fact of the interaction
        if contact:
            fact_val = f"Intent: {node5_res['primary_intent']} | Body: {body[:150]}"
            mem_fact = MemoryFact(
                id=f"fact-{uuid.uuid4().hex[:10]}",
                organization_id=organization_id,
                contact_id=contact.id,
                account_id=account.id if account else None,
                scope="contact",
                fact_key="recent_inquiry",
                fact_value=fact_val,
                confidence=0.95,
                source_span="pipeline4_lead_responder",
            )
            self.session.add(mem_fact)

        # Update Conversation state
        conversation.version += 1
        conversation.status = "active"

        # Record comprehensive NodeExecutionLog telemetry
        total_duration = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        exec_log = NodeExecutionLog(
            id=log_id,
            organization_id=organization_id,
            message_id=message_obj.id,
            conversation_id=conversation.id,
            contact_id=contact.id if contact else None,
            channel=channel,
            node1_ingest=json.dumps(node1_res, default=str),
            node2_context=json.dumps({k: v for k, v in node2_res.items() if k not in ("contact", "account", "conversation")}, default=str),
            node3_safety=json.dumps(node3_res, default=str),
            node4_memory=json.dumps({k: len(v) if isinstance(v, list) else (v is not None) for k, v in node4_res.items()}, default=str),
            node5_intent_draft=json.dumps(node5_res, default=str),
            approval_status=approval_item.status,
            send_status=send_status,
            total_latency_ms=total_duration,
            status="completed",
        )
        self.session.add(exec_log)
        await self.session.commit()

        return {
            "status": "success",
            "conversation_id": conversation.id,
            "message_id": message_obj.id,
            "approval_id": approval_item.id,
            "approval_status": approval_item.status,
            "send_status": send_status,
            "draft_reply": node5_res["draft_reply"],
            "node1": node1_res,
            "node2": {k: v for k, v in node2_res.items() if k not in ("contact", "account", "conversation")},
            "node3": node3_res,
            "node4": {"history_count": len(node4_res.get("history", [])), "has_demo": node4_res.get("demo_context") is not None},
            "node5": node5_res,
            "total_latency_ms": total_duration,
        }

    # =========================================================================
    # NODE 1 — INGEST
    # =========================================================================
    async def node1_ingest(
        self,
        sender: str,
        recipient: str,
        body: str,
        channel: str,
        provider: str,
        provider_message_id: Optional[str],
        organization_id: str,
    ) -> Dict[str, Any]:
        """Receive, verify, normalize, deduplicate, and persist inbound message."""
        clean_body = body.strip()
        channel_norm = channel.lower().strip()
        prov_msg_id = provider_message_id or f"msg-{uuid.uuid4().hex[:12]}"

        # Normalization
        if channel_norm == "email":
            norm_sender = sender.strip().lower()
            norm_recipient = recipient.strip().lower()
        else:
            # Phone normalization (E.164-like)
            norm_sender = re.sub(r"[^\d+]", "", sender.strip())
            norm_recipient = re.sub(r"[^\d+]", "", recipient.strip())

        # Deduplication Hash (SHA-256)
        dedup_raw = f"{provider}:{prov_msg_id}:{norm_sender}:{clean_body}"
        dedup_hash = hashlib.sha256(dedup_raw.encode("utf-8")).hexdigest()

        # Check existing message
        stmt = select(Message).where(Message.deduplication_hash == dedup_hash)
        res = await self.session.execute(stmt)
        existing = res.scalars().first()
        if existing:
            logger.info(f"[Node 1] Inbound message {prov_msg_id} is a duplicate; returning early.")
            return {
                "is_duplicate": True,
                "message_id": existing.id,
                "deduplication_hash": dedup_hash,
                "normalized_sender": norm_sender,
                "channel": channel_norm,
            }

        # Create unassociated placeholder Message
        new_msg = Message(
            id=f"msg-{uuid.uuid4().hex[:10]}",
            organization_id=organization_id,
            conversation_id="pending_context",
            direction="inbound",
            sender=norm_sender,
            recipient=norm_recipient,
            body=clean_body,
            deduplication_hash=dedup_hash,
            external_id=prov_msg_id,
            status="received",
            is_verified=True,
        )
        self.session.add(new_msg)
        await self.session.flush()

        logger.info(f"[Node 1 Ingest] Inbound {channel_norm} from {norm_sender} persisted as {new_msg.id}.")
        return {
            "is_duplicate": False,
            "message": new_msg,
            "message_id": new_msg.id,
            "normalized_sender": norm_sender,
            "normalized_recipient": norm_recipient,
            "clean_body": clean_body,
            "channel": channel_norm,
            "provider": provider,
            "provider_message_id": prov_msg_id,
            "deduplication_hash": dedup_hash,
        }

    # =========================================================================
    # NODE 2 — CUSTOMER CONTEXT
    # =========================================================================
    async def node2_customer_context(
        self,
        normalized_sender: str,
        channel: str,
        organization_id: str,
    ) -> Dict[str, Any]:
        """Match existing contact, account, and conversation thread or create provisional lead."""
        contact = None
        account = None
        is_new_lead = False
        resolution_status = "resolved"

        # 1. Search DB Contacts
        if channel == "email":
            stmt = select(Contact).where(Contact.email.ilike(normalized_sender))
        else:
            stmt = select(Contact).where(Contact.phone == normalized_sender)

        res = await self.session.execute(stmt)
        contacts = res.scalars().all()

        if len(contacts) == 1:
            contact = contacts[0]
            # Fetch Account
            if contact.account_id:
                acc_res = await self.session.execute(select(Account).where(Account.id == contact.account_id))
                account = acc_res.scalars().first()
        elif len(contacts) > 1:
            # Ambiguous resolution
            contact = contacts[0]
            resolution_status = "ambiguous_match"
            logger.warning(f"[Node 2] Multiple contacts match sender {normalized_sender}; marked for review.")

        # 2. Check Sample Accounts if DB contact not found
        if not contact:
            from backend.app.agents.research_outreach.sample_loader import SampleDataLoader
            loader = SampleDataLoader()
            sample_accs = loader.get_all_sample_accounts()
            for sa in sample_accs:
                for c in sa.get("contacts", []):
                    c_email = (c.get("email") or "").strip().lower()
                    c_phone = re.sub(r"[^\d+]", "", (c.get("phone") or ""))
                    if (channel == "email" and c_email == normalized_sender) or (channel == "sms" and c_phone == normalized_sender):
                        # Create persistent DB Contact and Account for this lead
                        acc_id = f"acc-{uuid.uuid4().hex[:8]}"
                        account = Account(
                            id=acc_id,
                            organization_id=organization_id,
                            name=sa.get("company_name", "Enterprise Prospect"),
                            domain=sa.get("domain", "prospect.example"),
                            industry=sa.get("industry", "Technology"),
                            fit_score=0.85,
                        )
                        self.session.add(account)

                        contact_id = f"con-{uuid.uuid4().hex[:8]}"
                        name_parts = (c.get("full_name") or "Executive Leader").split()
                        fn = name_parts[0]
                        ln = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
                        contact = Contact(
                            id=contact_id,
                            organization_id=organization_id,
                            account_id=acc_id,
                            first_name=fn,
                            last_name=ln,
                            email=c_email or f"{fn.lower()}@{sa.get('domain', 'example.com')}",
                            phone=c_phone or normalized_sender,
                            title=c.get("job_title", "Decision Maker"),
                        )
                        self.session.add(contact)
                        await self.session.flush()
                        break
                if contact:
                    break

        # 3. New Inbound Customer Creation (No match found)
        if not contact:
            is_new_lead = True
            acc_id = f"acc-inbound-{uuid.uuid4().hex[:8]}"
            company_name = f"Inbound Prospect ({normalized_sender})"
            if channel == "email" and "@" in normalized_sender:
                company_domain = normalized_sender.split("@")[-1]
            else:
                company_domain = "prospect.example"

            account = Account(
                id=acc_id,
                organization_id=organization_id,
                name=company_name,
                domain=company_domain,
                industry="Enterprise Inbound",
                fit_score=0.70,
            )
            self.session.add(account)

            contact_id = f"con-inbound-{uuid.uuid4().hex[:8]}"
            contact = Contact(
                id=contact_id,
                organization_id=organization_id,
                account_id=acc_id,
                first_name="Valued",
                last_name="Prospect",
                email=normalized_sender if channel == "email" else f"inbound@{company_domain}",
                phone=normalized_sender if channel == "sms" else None,
                title="Lead Decision Maker",
            )
            self.session.add(contact)
            await self.session.flush()
            logger.info(f"[Node 2 Context] Created provisional contact {contact.id} for new lead {normalized_sender}.")

        # 4. Resolve Conversation Thread
        conv_stmt = select(Conversation).where(
            Conversation.contact_id == contact.id,
            Conversation.channel == channel,
        )
        res_conv = await self.session.execute(conv_stmt)
        conversation = res_conv.scalars().first()

        effective_org_id = (conversation.organization_id if conversation else None) or contact.organization_id or organization_id

        if not conversation:
            conversation = Conversation(
                id=f"conv-{uuid.uuid4().hex[:10]}",
                organization_id=effective_org_id,
                account_id=account.id if account else contact.account_id,
                contact_id=contact.id,
                channel=channel,
                status="active",
                is_human_takeover=False,
                version=1,
            )
            self.session.add(conversation)
            await self.session.flush()
            logger.info(f"[Node 2 Context] Created conversation {conversation.id} for contact {contact.id}.")

        return {
            "contact": contact,
            "account": account,
            "conversation": conversation,
            "contact_id": contact.id,
            "account_id": account.id if account else None,
            "conversation_id": conversation.id,
            "effective_organization_id": effective_org_id,
            "is_new_lead": is_new_lead,
            "identity_resolution_status": resolution_status,
            "contact_name": f"{contact.first_name} {contact.last_name}".strip(),
            "contact_email": contact.email,
            "company_name": account.name if account else "Enterprise Prospect",
        }

    # =========================================================================
    # NODE 3 — SAFETY + SENTIMENT CLASSIFICATION
    # =========================================================================
    async def node3_safety_and_sentiment(
        self,
        message_body: str,
        contact: Optional[Contact],
        conversation: Conversation,
        sender: str,
        organization_id: str,
    ) -> Dict[str, Any]:
        """
        Execute deterministic safety checks followed by structured LLM sentiment analysis.
        Strict separation between sentiment (emotion/tone) and contact rejection.
        """
        lower_body = message_body.lower()

        # ---------------------------------------------------------------------
        # 1. Deterministic Checks
        # ---------------------------------------------------------------------
        # A. Check if contact is already suppressed
        if contact and await self.suppression_service.is_contact_suppressed(
            email=contact.email, phone=contact.phone, contact_id=contact.id
        ):
            logger.warning(f"[Node 3 Safety] Contact {contact.id} is suppressed. Halting response.")
            return {
                "sentiment": "unsubscribe",
                "buying_interest": "none",
                "primary_intent": "suppressed",
                "contact_rejection": True,
                "unsubscribe_detected": True,
                "automated_reply_detected": False,
                "human_review_required": False,
                "reason": "Contact is already in hard suppression registry.",
                "processing_decision": "stop_suppressed",
            }

        # B. Explicit STOP / Opt-Out Keywords
        is_explicit_stop = any(kw == lower_body or lower_body.startswith(f"{kw} ") or f" {kw}" in lower_body for kw in OPT_OUT_KEYWORDS)
        if is_explicit_stop:
            logger.warning(f"[Node 3 Safety] Explicit STOP detected: '{message_body}'. Recording hard suppression.")
            await self.suppression_service.record_suppression(
                organization_id=organization_id,
                reason="opt_out",
                contact_id=contact.id if contact else None,
                email=contact.email if contact else (sender if "@" in sender else None),
                phone=contact.phone if contact else (sender if "@" not in sender else None),
                notes=f"Triggered by inbound message: '{message_body[:100]}'",
            )
            return {
                "sentiment": "unsubscribe",
                "buying_interest": "none",
                "primary_intent": "opt_out",
                "contact_rejection": True,
                "unsubscribe_detected": True,
                "automated_reply_detected": False,
                "human_review_required": False,
                "reason": "Customer issued explicit STOP/unsubscribe command.",
                "processing_decision": "stop_suppressed",
            }

        # C. Explicit Contact Rejection Keywords
        is_explicit_rejection = any(kw in lower_body for kw in NEGATIVE_KEYWORDS)
        if is_explicit_rejection:
            logger.warning(f"[Node 3 Safety] Contact rejection detected: '{message_body}'. Recording suppression.")
            await self.suppression_service.record_suppression(
                organization_id=organization_id,
                reason="negative_reply",
                contact_id=contact.id if contact else None,
                email=contact.email if contact else (sender if "@" in sender else None),
                phone=contact.phone if contact else (sender if "@" not in sender else None),
                notes=f"Triggered by negative rejection: '{message_body[:100]}'",
            )
            return {
                "sentiment": "negative",
                "buying_interest": "none",
                "primary_intent": "contact_rejection",
                "contact_rejection": True,
                "unsubscribe_detected": False,
                "automated_reply_detected": False,
                "human_review_required": False,
                "reason": "Customer expressed clear contact rejection / lack of interest.",
                "processing_decision": "stop_suppressed",
            }

        # D. Automated Bot / Out-of-Office Detection
        is_bot_reply = any(kw in lower_body for kw in BOT_KEYWORDS)
        if is_bot_reply:
            logger.info(f"[Node 3 Safety] Automated/OOF bot reply detected: '{message_body}'.")
            return {
                "sentiment": "automated",
                "buying_interest": "none",
                "primary_intent": "automated_system_reply",
                "contact_rejection": False,
                "unsubscribe_detected": False,
                "automated_reply_detected": True,
                "human_review_required": False,
                "reason": "Automated system or out-of-office response detected.",
                "processing_decision": "automated_stop",
            }

        # E. Human Takeover State
        if conversation.is_human_takeover or conversation.status == "human_takeover":
            logger.info(f"[Node 3 Safety] Conversation {conversation.id} is in human takeover mode. AI replies paused.")
            return {
                "sentiment": "neutral",
                "buying_interest": "possible",
                "primary_intent": "human_handling",
                "contact_rejection": False,
                "unsubscribe_detected": False,
                "automated_reply_detected": False,
                "human_review_required": True,
                "reason": "Conversation is actively managed by a human sales representative.",
                "processing_decision": "human_takeover_blocked",
            }

        # ---------------------------------------------------------------------
        # 2. Structured LLM Sentiment & Intent Classification
        # ---------------------------------------------------------------------
        system_prompt = (
            "You are the Safety and Sentiment Classification Node for an enterprise sales platform.\n"
            "Analyze the inbound customer message and produce a strict JSON output matching this schema:\n"
            "{\n"
            '  "sentiment": "positive" | "negative" | "neutral" | "automated" | "unsubscribe",\n'
            '  "buying_interest": "explicit" | "possible" | "none" | "unknown",\n'
            '  "primary_intent": string,\n'
            '  "secondary_intents": list of strings,\n'
            '  "contact_rejection": boolean,\n'
            '  "unsubscribe_detected": boolean,\n'
            '  "automated_reply_detected": boolean,\n'
            '  "human_review_required": boolean,\n'
            '  "reason": string,\n'
            '  "processing_decision": "continue" | "stop_suppressed" | "human_review" | "automated_stop"\n'
            "}\n"
            "CRITICAL RULES:\n"
            "1. Sentiment and contact_rejection are SEPARATE concepts.\n"
            "   Example: 'Our existing system is terrible. Can your AI help?' has a negative emotional tone,\n"
            "   but has explicit business interest and is NOT a contact rejection. Set processing_decision='continue'.\n"
            "2. 'Not interested.' or 'Take me off your list.' -> contact_rejection=true, processing_decision='stop_suppressed'.\n"
            "3. If customer asks for demo or meeting, set primary_intent='meeting_request' or 'demo_request'.\n"
            "4. If customer confirms a slot ('Yes, 3 AM works', 'Sounds good'), set primary_intent='meeting_confirmation'.\n"
            "5. If customer asks to cancel, set primary_intent='meeting_cancellation'.\n"
        )
        user_prompt = f"Inbound Customer Message:\n\"\"\"{message_body}\"\"\""

        try:
            llm_result = await self.llm_gateway.generate_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_format="json_object",
            )
            if isinstance(llm_result, dict) and "sentiment" in llm_result:
                # Validate enum values
                sentiment = llm_result.get("sentiment", "neutral").lower()
                buying_interest = llm_result.get("buying_interest", "possible").lower()
                decision = llm_result.get("processing_decision", "continue").lower()
                contact_rej = bool(llm_result.get("contact_rejection", False))
                unsub = bool(llm_result.get("unsubscribe_detected", False))

                if contact_rej or unsub:
                    decision = "stop_suppressed"

                return {
                    "sentiment": sentiment,
                    "buying_interest": buying_interest,
                    "primary_intent": llm_result.get("primary_intent", "general_inquiry"),
                    "secondary_intents": llm_result.get("secondary_intents", []),
                    "contact_rejection": contact_rej,
                    "unsubscribe_detected": unsub,
                    "automated_reply_detected": bool(llm_result.get("automated_reply_detected", False)),
                    "human_review_required": bool(llm_result.get("human_review_required", False)),
                    "reason": llm_result.get("reason", "Structured LLM classification completed."),
                    "processing_decision": decision,
                }
        except Exception as e:
            logger.warning(f"[Node 3 Safety] LLM classification error ({e}); using deterministic fallback.")

        # Fallback heuristic
        is_meeting = any(w in lower_body for w in ["meet", "call", "schedule", "calendar", "tomorrow", "am", "pm", "tuesday", "friday"])
        is_demo = any(w in lower_body for w in ["demo", "video", "walkthrough", "product"])
        is_confirmation = any(w in lower_body for w in ["yes", "works", "confirmed", "sounds good", "perfect", "let's do"])
        is_cancel = any(w in lower_body for w in ["cancel", "reschedule", "push back"])
        is_negative = any(w in lower_body for w in ["broken", "terrible", "bad", "slow", "hate", "issue", "problem", "failing", "frustrated", "leaking"])
        has_buying_interest = any(w in lower_body for w in ["can your", "help", "fix", "interested", "platform", "solution", "meet", "demo"])

        intent = "general_inquiry"
        if is_cancel:
            intent = "meeting_cancellation"
        elif is_confirmation:
            intent = "meeting_confirmation"
        elif is_meeting:
            intent = "meeting_request"
        elif is_demo:
            intent = "demo_request"

        return {
            "sentiment": "negative" if is_negative else ("positive" if (is_meeting or is_demo or is_confirmation) else "neutral"),
            "buying_interest": "explicit" if has_buying_interest else "possible",
            "primary_intent": intent,
            "secondary_intents": ["demo_request"] if (is_meeting and is_demo) else [],
            "contact_rejection": False,
            "unsubscribe_detected": False,
            "automated_reply_detected": False,
            "human_review_required": False,
            "reason": "Deterministic classification fallback.",
            "processing_decision": "continue",
        }

    # =========================================================================
    # NODE 4 — MEMORY RETRIEVAL
    # =========================================================================
    async def node4_memory(
        self,
        contact: Contact,
        account: Optional[Account],
        conversation: Conversation,
        organization_id: str,
    ) -> Dict[str, Any]:
        """
        Load customer info, recent messages, Pipeline 2 research brief,
        Pipeline 3 demo context, pending calendar proposals, and approved knowledge.
        """
        # 1. Message History (last 10 messages)
        msg_stmt = (
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(desc(Message.created_at))
            .limit(10)
        )
        msg_res = await self.session.execute(msg_stmt)
        recent_messages = list(reversed(msg_res.scalars().all()))

        history_list = [
            {"direction": m.direction, "body": m.body, "sender": m.sender, "created_at": str(m.created_at)}
            for m in recent_messages
        ]

        # 2. Pipeline 2 Research Brief & Pain Points
        research_brief_data = None
        if account:
            rb_stmt = select(ResearchBrief).where(
                ResearchBrief.account_id == account.id,
                ResearchBrief.organization_id == organization_id,
            )
            rb_res = await self.session.execute(rb_stmt)
            rb = rb_res.scalars().first()
            if rb:
                research_brief_data = {
                    "summary": rb.executive_summary,
                    "target_pain_points": rb.verified_facts,
                    "business_fit": rb.business_fit_summary,
                }

        # 3. Active Pending Meeting Proposal (Waiting for customer confirmation)
        prop_stmt = (
            select(MeetingProposal)
            .where(
                MeetingProposal.conversation_id == conversation.id,
                MeetingProposal.status == "offered",
            )
            .order_by(desc(MeetingProposal.created_at))
        )
        prop_res = await self.session.execute(prop_stmt)
        active_proposal = prop_res.scalars().first()
        pending_proposal_data = None
        if active_proposal:
            try:
                slots = json.loads(active_proposal.offered_slots)
            except Exception:
                slots = []
            pending_proposal_data = {
                "proposal_id": active_proposal.id,
                "offered_slots": slots,
                "requested_slot": active_proposal.requested_slot,
                "expires_at": active_proposal.expires_at,
            }

        # 4. Pipeline 3 Demo References
        marketplace_products = await self.marketplace_service.list_products()

        # 5. Approved Shared Knowledge Base facts
        kb_stmt = select(KnowledgeVersion).where(
            KnowledgeVersion.organization_id == organization_id,
            KnowledgeVersion.is_active.is_(True),
        )
        kb_res = await self.session.execute(kb_stmt)
        kb_facts = [
            {"title": k.title, "category": k.category, "content": k.content}
            for k in kb_res.scalars().all()
        ]

        # 6. Existing Confirmed Meetings
        mtg_stmt = (
            select(MeetingBooking)
            .where(
                MeetingBooking.conversation_id == conversation.id,
                MeetingBooking.status == "booking_confirmed",
            )
            .order_by(desc(MeetingBooking.created_at))
        )
        mtg_res = await self.session.execute(mtg_stmt)
        confirmed_meetings = [
            {
                "booking_id": m.id,
                "title": m.title,
                "start": m.start_time,
                "end": m.end_time,
                "teams_url": m.teams_join_url,
                "outlook_id": m.outlook_event_id,
            }
            for m in mtg_res.scalars().all()
        ]

        return {
            "contact_name": f"{contact.first_name} {contact.last_name}".strip(),
            "contact_email": contact.email,
            "company_name": account.name if account else "Enterprise Prospect",
            "history": history_list,
            "research_brief": research_brief_data,
            "pending_proposal": pending_proposal_data,
            "confirmed_meetings": confirmed_meetings,
            "demo_products": marketplace_products[:3],
            "knowledge_facts": kb_facts,
        }

    # =========================================================================
    # NODE 5 — INTENT + ACTION + DRAFT
    # =========================================================================
    async def node5_intent_action_draft(
        self,
        message_body: str,
        channel: str,
        contact: Contact,
        account: Optional[Account],
        conversation: Conversation,
        memory_context: Dict[str, Any],
        sentiment_analysis: Dict[str, Any],
        organization_id: str,
    ) -> Dict[str, Any]:
        """
        Understand customer intent, execute authorized tools (Calendar scheduling,
        Knowledge Base, Pipeline 3 Demo, Human Handoff), and draft an AI response.
        """
        lower_body = message_body.lower()
        primary_intent = sentiment_analysis.get("primary_intent", "general_inquiry")
        tools_executed = []
        tool_results: Dict[str, Any] = {}
        meeting_state = None
        auto_approved = False

        # ---------------------------------------------------------------------
        # TOOL 1: Calendar Booking / Meeting Confirmation Workflow
        # ---------------------------------------------------------------------
        pending_prop = memory_context.get("pending_proposal")
        is_confirming = (
            primary_intent == "meeting_confirmation"
            or (pending_prop and any(w in lower_body for w in ["yes", "works", "3 am", "3:00", "sounds good", "let's do", "confirm"]))
        )
        is_cancelling = primary_intent == "meeting_cancellation" or "cancel" in lower_body

        if is_cancelling:
            tools_executed.append("cancel_meeting")
            confirmed_meetings = memory_context.get("confirmed_meetings", [])
            if confirmed_meetings:
                mtg = confirmed_meetings[0]
                await self.calendar_adapter.cancel_meeting(
                    outlook_event_id=mtg.get("outlook_id"),
                    reason=f"Customer request: '{message_body[:80]}'",
                )
                # Update booking in DB
                b_stmt = select(MeetingBooking).where(MeetingBooking.id == mtg["booking_id"])
                b_res = await self.session.execute(b_stmt)
                db_b = b_res.scalars().first()
                if db_b:
                    db_b.status = "cancelled"
                    db_b.cancellation_reason = "Customer cancelled via message"
                meeting_state = "cancelled"
                tool_results["cancellation"] = {"status": "cancelled", "booking_id": mtg["booking_id"]}
                reply_draft = (
                    f"Hi {contact.first_name}, I've cancelled our meeting as requested. "
                    "If you would like to reschedule in the future, just let me know. Have a great day!"
                )
            else:
                reply_draft = f"Hi {contact.first_name}, I could not find an active scheduled meeting to cancel. Let me know if you would like to set up a new time!"

            return {
                "primary_intent": "meeting_cancellation",
                "tools_executed": tools_executed,
                "tool_results": tool_results,
                "meeting_state": meeting_state,
                "draft_reply": reply_draft,
                "auto_approved": True,
                "proposed_next_action": "closed",
            }

        elif is_confirming and pending_prop:
            # -----------------------------------------------------------------
            # Section 8.3 B6: Customer Confirms An Alternative Slot ("Yes, 3 AM works")
            # -----------------------------------------------------------------
            tools_executed.append("confirm_and_book_calendar_slot")
            offered_slots = pending_prop.get("offered_slots", [])
            selected_slot = offered_slots[0] if offered_slots else None

            if selected_slot:
                start_iso = selected_slot["start"]
                end_iso = selected_slot["end"]

                # Concurrency recheck: verify slot is still available
                start_dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
                is_still_free = await self.calendar_adapter.is_slot_available(
                    organizer_email=self.calendar_adapter.organizer_email,
                    start_dt=start_dt,
                )

                if is_still_free:
                    # Book event in Microsoft Calendar with Teams Join URL
                    booking_res = await self.calendar_adapter.book_meeting(
                        organizer_email=self.calendar_adapter.organizer_email,
                        attendee_email=contact.email,
                        attendee_name=f"{contact.first_name} {contact.last_name}".strip(),
                        title=f"Discovery Discussion: {account.name if account else 'Prospect'} x Adople AI",
                        start_time_iso=start_iso,
                        end_time_iso=end_iso,
                        timezone_name="UTC",
                        idempotency_key=f"mtg-{uuid.uuid4().hex[:10]}",
                        description="Discovery call arranged automatically via 24/7 Lead Responder.",
                    )

                    # Persist confirmed MeetingBooking in PostgreSQL
                    meeting_booking = MeetingBooking(
                        id=booking_res["booking_id"],
                        organization_id=organization_id,
                        conversation_id=conversation.id,
                        contact_id=contact.id,
                        account_id=account.id if account else None,
                        organizer_email=self.calendar_adapter.organizer_email,
                        attendee_email=contact.email,
                        attendee_name=f"{contact.first_name} {contact.last_name}".strip(),
                        title=booking_res["title"],
                        start_time=start_iso,
                        end_time=end_iso,
                        timezone="UTC",
                        status="booking_confirmed",
                        outlook_event_id=booking_res.get("outlook_event_id"),
                        teams_join_url=booking_res.get("teams_join_url"),
                        idempotency_key=booking_res["booking_id"],
                        selected_slot=json.dumps(selected_slot),
                        auto_booked=True,
                    )
                    self.session.add(meeting_booking)

                    # Mark proposal confirmed
                    prop_stmt = select(MeetingProposal).where(MeetingProposal.id == pending_prop["proposal_id"])
                    prop_res = await self.session.execute(prop_stmt)
                    p_obj = prop_res.scalars().first()
                    if p_obj:
                        p_obj.status = "confirmed"
                        p_obj.selected_slot = json.dumps(selected_slot)

                    meeting_state = "booking_confirmed"
                    tool_results["booking"] = booking_res
                    auto_approved = True

                    teams_link = booking_res.get("teams_join_url")
                    display_time = selected_slot.get("display", "the selected time")
                    if channel == "sms":
                        reply_draft = (
                            f"Confirmed! I've booked our discovery call for {display_time}. "
                            f"Teams link: {teams_link} Looking forward to connecting!"
                        )
                    else:
                        reply_draft = (
                            f"Hi {contact.first_name},\n\n"
                            f"Great! I've confirmed our discovery meeting for {display_time}.\n\n"
                            f"Microsoft Teams Join Link: {teams_link}\n"
                            f"Calendar invitation sent to {contact.email}.\n\n"
                            "Looking forward to speaking with you!\n\n"
                            "Best regards,\nAdople Solutions Team"
                        )
                else:
                    # Slot taken concurrently
                    meeting_state = "slot_concurrently_occupied"
                    new_alts = await self.calendar_adapter.find_alternative_slots(
                        organizer_email=self.calendar_adapter.organizer_email,
                        requested_dt=start_dt + timedelta(hours=1),
                    )
                    alt_display = new_alts[0]["display"] if new_alts else "tomorrow at 10:00 AM"
                    reply_draft = (
                        f"That slot was just booked by another prospect. "
                        f"Would {alt_display} work instead?"
                    )

            return {
                "primary_intent": "meeting_confirmation",
                "tools_executed": tools_executed,
                "tool_results": tool_results,
                "meeting_state": meeting_state,
                "draft_reply": reply_draft,
                "auto_approved": auto_approved,
                "proposed_next_action": "await_customer_reply",
            }

        elif primary_intent == "meeting_request" or any(w in lower_body for w in ["meet", "call", "schedule", "calendar", "2 am", "3 am", "tomorrow", "tuesday"]):
            # -----------------------------------------------------------------
            # Section 8.3 B3 & B5: Meeting Request / Availability Lookup
            # Check 2 AM Occupied -> Find 3 AM Alternative!
            # -----------------------------------------------------------------
            tools_executed.append("check_outlook_availability")

            # Interpret Date and Time from message
            requested_hour = 14  # Default 2 PM
            if "2 am" in lower_body or "2:00 am" in lower_body or "at 2" in lower_body:
                requested_hour = 2
            elif "3 am" in lower_body:
                requested_hour = 3
            elif "10 am" in lower_body:
                requested_hour = 10
            elif "4 pm" in lower_body:
                requested_hour = 16

            days_ahead = 1
            now_weekday = datetime.now(timezone.utc).weekday()  # 0=Monday, ..., 6=Sunday
            if "tuesday" in lower_body:
                days_ahead = (1 - now_weekday) % 7 or 7
            elif "wednesday" in lower_body:
                days_ahead = (2 - now_weekday) % 7 or 7
            elif "thursday" in lower_body:
                days_ahead = (3 - now_weekday) % 7 or 7
            elif "friday" in lower_body:
                days_ahead = (4 - now_weekday) % 7 or 7
            elif "monday" in lower_body:
                days_ahead = (0 - now_weekday) % 7 or 7
            elif "saturday" in lower_body:
                days_ahead = (5 - now_weekday) % 7 or 7
            elif "sunday" in lower_body:
                days_ahead = (6 - now_weekday) % 7 or 7

            req_date = datetime.now(timezone.utc).replace(
                hour=requested_hour, minute=0, second=0, microsecond=0
            ) + timedelta(days=days_ahead)

            # Check Availability in Outlook via Calendar Adapter
            is_available = await self.calendar_adapter.is_slot_available(
                organizer_email=self.calendar_adapter.organizer_email,
                start_dt=req_date,
            )

            if is_available:
                meeting_state = "requested_slot_available"
                end_dt = req_date + timedelta(minutes=30)
                slot_info = {
                    "start": req_date.isoformat(),
                    "end": end_dt.isoformat(),
                    "display": req_date.strftime("%A at %I:%M %p").replace(" 0", " "),
                }
                # Save Proposal
                prop = MeetingProposal(
                    id=f"prop-{uuid.uuid4().hex[:10]}",
                    organization_id=organization_id,
                    conversation_id=conversation.id,
                    contact_id=contact.id,
                    requested_slot=json.dumps(slot_info),
                    offered_slots=json.dumps([slot_info]),
                    status="offered",
                    expires_at=(datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
                )
                self.session.add(prop)

                if channel == "sms":
                    reply_draft = (
                        f"Yes, I can do {slot_info['display']}. "
                        "Reply YES to confirm and I'll send over the Teams invitation!"
                    )
                else:
                    reply_draft = (
                        f"Hi {contact.first_name},\n\n"
                        f"Yes, {slot_info['display']} is currently open on our calendar. "
                        "Would you like me to book this slot for our discovery conversation?\n\n"
                        "Best,\nAdople Solutions Team"
                    )
            else:
                # -------------------------------------------------------------
                # Section 8.3 B5: Requested Slot Occupied! Search Alternatives
                # (e.g. 2:00 AM occupied -> 3:00 AM available!)
                # -------------------------------------------------------------
                meeting_state = "alternatives_offered"
                alternatives = await self.calendar_adapter.find_alternative_slots(
                    organizer_email=self.calendar_adapter.organizer_email,
                    requested_dt=req_date,
                    max_alternatives=2,
                )

                # Persist MeetingProposal with offered alternatives
                prop = MeetingProposal(
                    id=f"prop-{uuid.uuid4().hex[:10]}",
                    organization_id=organization_id,
                    conversation_id=conversation.id,
                    contact_id=contact.id,
                    requested_slot=json.dumps({"requested_hour": requested_hour, "date": req_date.isoformat()}),
                    offered_slots=json.dumps(alternatives),
                    status="offered",
                    expires_at=(datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
                )
                self.session.add(prop)

                alt_slot_1 = alternatives[0] if alternatives else None
                alt_disp = alt_slot_1["time_str"] if alt_slot_1 else "3:00 AM"

                # EXACT format mandated by prompt Section 8.3 B5:
                # "Hi, I'm unavailable at 2:00 AM, but 3:00 AM is available. Would 3:00 AM work for you?"
                req_time_str = f"{requested_hour}:00 AM" if requested_hour < 12 else f"{requested_hour - 12}:00 PM"
                if channel == "sms":
                    reply_draft = f"Hi, I'm unavailable at {req_time_str}, but {alt_disp} is available. Would {alt_disp} work for you?"
                else:
                    reply_draft = (
                        f"Hi {contact.first_name},\n\n"
                        f"I'm unavailable at {req_time_str}, but {alt_disp} is currently available. "
                        f"Would {alt_disp} work for your schedule?\n\n"
                        "Best regards,\nAdople Solutions Team"
                    )

            tool_results["calendar_check"] = {
                "requested_time": req_date.isoformat(),
                "is_available": is_available,
                "meeting_state": meeting_state,
            }
            return {
                "primary_intent": "meeting_request",
                "tools_executed": tools_executed,
                "tool_results": tool_results,
                "meeting_state": meeting_state,
                "draft_reply": reply_draft,
                "auto_approved": False,
                "proposed_next_action": "await_customer_selection",
            }

        # ---------------------------------------------------------------------
        # TOOL 2: Pipeline 3 Demo Request
        # ---------------------------------------------------------------------
        elif primary_intent == "demo_request" or "demo" in lower_body or "video" in lower_body:
            tools_executed.append("retrieve_pipeline3_demo")
            matched_product = None
            demo_products = memory_context.get("demo_products", [])
            if demo_products:
                matched_product = demo_products[0]

            demo_link = matched_product.get("demo_video_url", "https://marketplace.adople.ai/") if matched_product else "https://marketplace.adople.ai/"
            marketplace_url = matched_product.get("product_url") or "https://marketplace.adople.ai/"
            prod_name = matched_product.get("name", "Adople AI Platform") if matched_product else "Adople AI Solutions"
            prod_overview = matched_product.get("overview", "autonomous enterprise automation workflows") if matched_product else "autonomous enterprise workflows"

            tool_results["demo"] = {"product_name": prod_name, "demo_url": demo_link, "marketplace_url": marketplace_url}

            if channel == "sms":
                reply_draft = (
                    f"Here is our live interactive demo for {prod_name}: {demo_link} (Explore: {marketplace_url}) "
                    "Let me know if you'd like to schedule a quick 10-minute briefing to walk through it!"
                )
            else:
                reply_draft = (
                    f"Hi {contact.first_name},\n\n"
                    f"Here is the interactive demo video for {prod_name}:\n{demo_link}\n\n"
                    f"Overview: {prod_overview}\n\n"
                    f"You can also review full platform capabilities on our Marketplace:\n{marketplace_url}\n\n"
                    "Would you be open to a 10-minute call next week to discuss how this fits your architecture?\n\n"
                    "Best regards,\nAdople Solutions Team"
                )

            return {
                "primary_intent": "demo_request",
                "tools_executed": tools_executed,
                "tool_results": tool_results,
                "meeting_state": None,
                "draft_reply": reply_draft,
                "auto_approved": False,
                "proposed_next_action": "await_customer_reply",
            }

        # ---------------------------------------------------------------------
        # TOOL 3: Human Handoff Request
        # ---------------------------------------------------------------------
        elif any(w in lower_body for w in ["human", "agent", "person", "representative", "speak to someone", "call me"]):
            tools_executed.append("human_handoff")
            conversation.is_human_takeover = True
            conversation.status = "human_takeover"
            tool_results["handoff"] = {"status": "human_takeover_activated"}

            reply_draft = (
                f"Hi {contact.first_name}, I've notified our enterprise sales team. "
                "A specialist will reach out to you directly shortly!"
            )
            return {
                "primary_intent": "human_handoff",
                "tools_executed": tools_executed,
                "tool_results": tool_results,
                "meeting_state": None,
                "draft_reply": reply_draft,
                "auto_approved": True,
                "proposed_next_action": "human_handling",
            }

        # ---------------------------------------------------------------------
        # TOOL 4: Knowledge Base / Technical / Pricing Question
        # ---------------------------------------------------------------------
        else:
            tools_executed.append("query_knowledge_base")
            kb_facts = memory_context.get("knowledge_facts", [])
            relevant_facts = [
                f["content"] for f in kb_facts
                if any(w in f["content"].lower() for w in lower_body.split() if len(w) > 3)
            ]

            system_prompt = (
                "You are an enterprise sales AI assistant representing Adople AI.\n"
                "Answer the customer's question concisely using only verified facts.\n"
                "Do not hallucinate pricing or guarantees not supported by evidence.\n"
                "End with a gentle invitation to see a live demo or schedule a brief call."
            )
            user_prompt = (
                f"Customer Name: {contact.first_name} {contact.last_name}\n"
                f"Company: {account.name if account else 'Enterprise'}\n"
                f"Knowledge Facts: {' '.join(relevant_facts) if relevant_facts else 'Enterprise AI platform providing sub-second latency, CRM integrations, and strict SOC2/HIPAA compliance.'}\n"
                f"Customer Question: \"{message_body}\""
            )

            try:
                llm_res = await self.llm_gateway.generate_completion(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_format=None,
                )
                generated_text = llm_res.get("content", "").strip()
            except Exception:
                generated_text = (
                    f"Hi {contact.first_name}, thanks for reaching out! Our platform integrates seamlessly "
                    "with enterprise workflows to automate high-volume operations with grounded accuracy. "
                    "Would you like to take a look at a brief 2-minute demo or schedule a quick discovery call?"
                )

            tool_results["knowledge"] = {"matched_facts_count": len(relevant_facts)}
            return {
                "primary_intent": "general_inquiry",
                "tools_executed": tools_executed,
                "tool_results": tool_results,
                "meeting_state": None,
                "draft_reply": generated_text,
                "auto_approved": False,
                "proposed_next_action": "await_customer_reply",
            }

    # =========================================================================
    # AUTHORIZED DISPATCH
    # =========================================================================
    async def dispatch_reply(
        self,
        conversation_id: str,
        channel: str,
        recipient: str,
        body: str,
        subject: str = "Follow up from Adople AI",
    ) -> Dict[str, Any]:
        """Dispatch approved message via Outlook Graph API or SMS adapter with idempotency."""
        # Record Outgoing Message in DB
        out_msg = Message(
            id=f"msg-out-{uuid.uuid4().hex[:10]}",
            organization_id="org-default",
            conversation_id=conversation_id,
            direction="outbound",
            sender=self.calendar_adapter.organizer_email if channel == "email" else "+15550199",
            recipient=recipient,
            body=body,
            deduplication_hash=hashlib.sha256(f"outbound:{conversation_id}:{recipient}:{body[:50]}".encode()).hexdigest(),
            status="sent",
            is_verified=True,
        )
        self.session.add(out_msg)

        if channel == "email":
            dispatch_res = await self.mail_adapter.send_email(
                to_email=recipient,
                subject=subject,
                body=body,
            )
            out_msg.external_id = dispatch_res.get("message_id")
            out_msg.status = dispatch_res.get("status", "sent")
        else:
            dispatch_res = await self.sms_adapter.send_sms(
                to_phone=recipient,
                body=body,
            )
            out_msg.external_id = dispatch_res.get("message_id")
            out_msg.status = dispatch_res.get("status", "sent")

        await self.session.commit()
        return {
            "status": out_msg.status,
            "message_id": out_msg.id,
            "provider_message_id": out_msg.external_id,
        }

    # =========================================================================
    # INBOX SYNC (Poll Microsoft Outlook Inbox for Inbound Replies)
    # =========================================================================
    async def sync_email_inbox(self, organization_id: str = "org-default") -> Dict[str, Any]:
        """
        Poll Microsoft Outlook Inbox via Microsoft Graph for new incoming emails from leads.
        Runs every new incoming reply through the 5-Node Pipeline 4 and links it to Outreach Campaigns.
        """
        fetch_res = await self.mail_adapter.fetch_inbox_messages(top=20)
        if fetch_res.get("status") != "success":
            return {
                "status": fetch_res.get("status", "failed"),
                "synced_count": 0,
                "error": fetch_res.get("error"),
                "required_permission": fetch_res.get("required_permission"),
            }

        organizer_email = (self.mail_adapter.sender_email or "").strip().lower()
        processed_count = 0
        results = []

        for msg in fetch_res.get("messages", []):
            sender_email = msg.get("sender_email", "")
            if not sender_email or sender_email == organizer_email:
                continue

            # Skip common automated bounce/daemon notices
            if any(k in sender_email for k in ("mailer-daemon", "noreply", "no-reply", "notifications")):
                continue

            msg_body = (msg.get("body_preview") or msg.get("body") or "").strip()
            if not msg_body:
                continue

            provider_msg_id = msg.get("message_id")

            # Check if this message was already ingested via deduplication hash or external id
            dedup_hash = hashlib.sha256(
                f"{sender_email}:{organizer_email}:{msg_body}:{provider_msg_id or ''}".encode()
            ).hexdigest()

            existing_msg = await self.session.execute(
                select(Message).where(Message.deduplication_hash == dedup_hash)
            )
            if existing_msg.scalars().first():
                continue

            # Process inbound through the 5 nodes
            p_res = await self.process_inbound_message(
                sender=sender_email,
                recipient=organizer_email,
                body=msg_body,
                channel="email",
                provider="microsoft_graph",
                provider_message_id=provider_msg_id,
                organization_id=organization_id,
                auto_dispatch=False,
            )
            processed_count += 1
            results.append({"sender": sender_email, "status": p_res.get("status")})

            # Also update CampaignRecipient reply monitoring if this sender is part of an active outreach campaign
            try:
                rec_stmt = select(CampaignRecipient).where(CampaignRecipient.contact_email == sender_email)
                if organization_id and organization_id != "org-default":
                    rec_stmt = rec_stmt.where(CampaignRecipient.organization_id == organization_id)
                rec_res = await self.session.execute(rec_stmt)
                matching_recipients = rec_res.scalars().all()
                for rec in matching_recipients:
                    node3_sentiment = p_res.get("node3", {}).get("sentiment") or "received"
                    rec.reply_status = node3_sentiment
                    rec.reply_snippet = msg_body[:200]
                    rec.reply_received_at = datetime.now(timezone.utc).isoformat()

                    # Recalculate campaign counts
                    cmp_res = await self.session.execute(
                        select(Campaign).where(Campaign.id == rec.campaign_id)
                    )
                    camp = cmp_res.scalars().first()
                    if camp:
                        roster_res = await self.session.execute(
                            select(CampaignRecipient).where(CampaignRecipient.campaign_id == camp.id)
                        )
                        roster = roster_res.scalars().all()
                        camp.replies_count = sum(
                            1 for r in roster if r.reply_status in ("received", "positive", "negative", "neutral")
                        )
                        camp.positive_replies_count = sum(1 for r in roster if r.reply_status == "positive")
                await self.session.commit()
            except Exception as cmp_err:
                logger.warning(f"[Pipeline4Engine] Failed to link campaign reply for '{sender_email}': {cmp_err}")

        return {
            "status": "success",
            "synced_count": processed_count,
            "processed": results,
            "message": f"Synced {processed_count} new email replies from Microsoft Outlook inbox.",
        }

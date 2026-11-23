"""Central Approval Center Service."""

import hashlib
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.exceptions import (
    NotFoundError,
    PermissionDeniedError,
)
from backend.app.core.logging import logger
from backend.app.core.rbac import CurrentUser, RoleEnum
from backend.app.integrations.messaging.outlook_mail import OutlookMailAdapter
from backend.app.models.conversations import Conversation, Message
from backend.app.models.governance import ApprovalItem
from backend.app.models.sales import Contact
from backend.app.repositories.governance_repo import ApprovalRepository
from backend.app.services.attempt_service import AttemptTrackingService
from backend.app.services.suppression_service import SuppressionService


class ApprovalService:
    def __init__(
        self,
        session: AsyncSession,
        mail_adapter: Optional[OutlookMailAdapter] = None,
    ):
        self.session = session
        self.repo = ApprovalRepository(session)
        self.mail_adapter = mail_adapter or OutlookMailAdapter()

    async def create_approval_request(
        self,
        organization_id: str,
        account_id: str,
        artifact_type: str,
        artifact_id: str,
        requested_action: str,
        draft_content: str,
        contact_id: Optional[str] = None,
        source_evidence: Optional[Dict[str, Any]] = None,
        risk_flags: Optional[List[str]] = None,
        due_at: Optional[str] = None,
    ) -> ApprovalItem:
        """Create a required approval item before customer-facing transmission."""
        item = ApprovalItem(
            organization_id=organization_id,
            account_id=account_id,
            contact_id=contact_id,
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            requested_action=requested_action,
            draft_content=draft_content,
            source_evidence=source_evidence or {},
            risk_flags=risk_flags or [],
            status="pending",
            due_at=due_at,
        )
        return await self.repo.create(item)

    async def list_pending_approvals(self, organization_id: str) -> List[ApprovalItem]:
        return await self.repo.list_pending(organization_id=organization_id)

    async def get_approval_by_id(self, approval_id: str) -> ApprovalItem:
        item = await self.repo.get_by_id(approval_id)
        if not item:
            raise NotFoundError(f"Approval item {approval_id} not found")
        return item

    async def process_decision(
        self,
        approval_id: str,
        decision: str,  # approved, edited_approved, rejected, revision_requested, taken_over
        current_user: CurrentUser,
        edited_content: Optional[str] = None,
        feedback: Optional[str] = None,
    ) -> ApprovalItem:
        """Process human reviewer decision with role-based checks."""
        item = await self.get_approval_by_id(approval_id)

        # Enforce specific domain authorization rules from the plan:
        # Commercial proposals require SALES_MANAGER
        if item.artifact_type == "proposal" and decision in ["approved", "edited_approved"]:
            if not current_user.has_role(RoleEnum.SALES_MANAGER):
                raise PermissionDeniedError(
                    "Commercial proposal approvals strictly require SALES_MANAGER role.",
                    details={"artifact_type": "proposal"},
                )

        # Security attestations require SECURITY_REVIEWER
        if item.artifact_type == "security_answer" and decision in ["approved", "edited_approved"]:
            if not current_user.has_role(RoleEnum.SECURITY_REVIEWER):
                raise PermissionDeniedError(
                    "Security attestations strictly require SECURITY_REVIEWER role.",
                    details={"artifact_type": "security_answer"},
                )

        item.status = decision
        item.reviewed_by_user_id = current_user.id
        item.review_feedback = feedback
        if edited_content and decision == "edited_approved":
            item.draft_content = edited_content

        await self.repo.update(
            item,
            {
                "status": item.status,
                "reviewed_by_user_id": item.reviewed_by_user_id,
                "review_feedback": item.review_feedback,
                "draft_content": item.draft_content,
            },
        )

        # Human approval marks the outreach draft as approved (Ready for Outreach).
        # Actual dispatch occurs when the sales rep triggers explicit send action.
        if (
            item.artifact_type == "outreach_draft"
            and item.requested_action == "send_outreach"
            and decision in ("approved", "edited_approved")
        ):
            logger.info(
                f"[ApprovalService] Outreach approval_id='{item.id}' marked as '{item.status}'. "
                "Delivery held for explicit sales rep dispatch via Outlook."
            )

        return item

    async def _dispatch_approved_outreach_email(
        self,
        item: ApprovalItem,
        evidence: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Re-check compliance rules, send outreach email via Microsoft Outlook, and record audit trail."""
        db_contact: Optional[Contact] = None
        if item.contact_id:
            res = await self.session.execute(
                select(Contact).where(Contact.id == item.contact_id)
            )
            db_contact = res.scalars().first()

        recipient_email = (
            evidence.get("recipient_email")
            or (db_contact.email if db_contact else None)
            or ""
        ).strip()

        if not recipient_email:
            err = "No recipient email address found for approved outreach item."
            logger.error(f"[ApprovalService] {err} approval_id='{item.id}'")
            return {"status": "failed", "provider": "microsoft_outlook", "error": err}

        suppression_service = SuppressionService(self.session)
        if await suppression_service.is_contact_suppressed(
            email=recipient_email, contact_id=item.contact_id
        ):
            err = "Contact is on suppression registry; email dispatch blocked."
            logger.warning(f"[ApprovalService] {err} approval_id='{item.id}'")
            return {"status": "blocked_suppressed", "provider": "microsoft_outlook", "error": err}

        attempt_service = AttemptTrackingService(self.session)
        if db_contact and await attempt_service.get_logical_attempts(db_contact.id) >= 3:
            err = "Max 3 logical outreach attempts reached; 4th attempt strictly blocked."
            logger.warning(f"[ApprovalService] {err} approval_id='{item.id}'")
            return {"status": "blocked_max_attempts", "provider": "microsoft_outlook", "error": err}

        subject = str(evidence.get("subject") or "Following up on your team's initiatives")
        logger.info(
            f"[ApprovalService][production] Dispatching approved outreach approval_id='{item.id}' "
            f"to='{recipient_email}'."
        )
        delivery = await self.mail_adapter.send_email(
            to_email=recipient_email,
            subject=subject,
            body=item.draft_content,
            mode="production",
        )

        if delivery.get("status") == "sent" and db_contact:
            # Persist Conversation + outbound Message + OutreachAttempt (Rule of 3)
            conv_res = await self.session.execute(
                select(Conversation).where(
                    Conversation.organization_id == item.organization_id,
                    Conversation.account_id == item.account_id,
                    Conversation.contact_id == db_contact.id,
                    Conversation.channel == "email",
                )
            )
            conversation = conv_res.scalars().first()
            if not conversation:
                conversation = Conversation(
                    organization_id=item.organization_id,
                    account_id=item.account_id,
                    contact_id=db_contact.id,
                    channel="email",
                    status="active",
                )
                self.session.add(conversation)
                await self.session.flush()

            dedup_hash = hashlib.sha256(
                f"{item.id}:{recipient_email}:{item.draft_content}".encode("utf-8")
            ).hexdigest()
            msg = Message(
                organization_id=item.organization_id,
                conversation_id=conversation.id,
                direction="outbound",
                sender=str(delivery.get("sender") or settings.MICROSOFT_SENDER_EMAIL or ""),
                recipient=recipient_email,
                body=item.draft_content,
                deduplication_hash=dedup_hash,
                external_id=delivery.get("message_id"),
                status="sent",
                is_verified=True,
            )
            self.session.add(msg)
            await self.session.flush()

            attempt = await attempt_service.record_logical_attempt(
                organization_id=item.organization_id,
                contact_id=db_contact.id,
                channel="email",
                message_id=msg.id,
            )
            delivery["db_message_id"] = msg.id
            delivery["conversation_id"] = conversation.id
            delivery["attempt_number"] = attempt.attempt_number

        return delivery

    async def invalidate_stale_response_approval(self, contact_id: str) -> int:
        """If a lead replies with a new message, prior pending draft approvals are invalidated."""
        from sqlalchemy import update

        stmt = (
            update(ApprovalItem)
            .where(
                ApprovalItem.contact_id == contact_id,
                ApprovalItem.artifact_type == "lead_reply",
                ApprovalItem.status == "pending",
            )
            .values(
                status="expired", review_feedback="Invalidated by new incoming message from lead"
            )
        )
        result = await self.session.execute(stmt)
        # pyrefly: ignore[missing-attribute]
        return result.rowcount

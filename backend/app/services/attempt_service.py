"""Outreach Attempt Accounting and 4th Attempt Block Service."""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import BusinessRuleViolationError
from backend.app.models.conversations import OutreachAttempt
from backend.app.repositories.conversation_repo import OutreachAttemptRepository
from backend.app.repositories.sales_repo import ContactRepository

MAX_LOGICAL_ATTEMPTS = 3


class AttemptTrackingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.attempt_repo = OutreachAttemptRepository(session)
        self.contact_repo = ContactRepository(session)

    async def get_logical_attempts(self, contact_id: str) -> int:
        contact = await self.contact_repo.get_by_id(contact_id)
        if not contact:
            return 0
        return contact.logical_outreach_attempts

    async def record_logical_attempt(
        self,
        organization_id: str,
        contact_id: str,
        campaign_id: Optional[str] = None,
        channel: str = "sms",
        message_id: Optional[str] = None,
    ) -> OutreachAttempt:
        """
        Record a logical outreach attempt.
        Strict rule: If the contact already has 3 unanswered attempts, forbid the 4th attempt.
        """
        contact = await self.contact_repo.get_by_id(contact_id)
        if not contact:
            raise BusinessRuleViolationError(
                message=f"Contact {contact_id} not found",
                code="CONTACT_NOT_FOUND",
            )

        current_attempts = contact.logical_outreach_attempts
        if current_attempts >= MAX_LOGICAL_ATTEMPTS:
            raise BusinessRuleViolationError(
                message=f"Outreach limit reached. Max {MAX_LOGICAL_ATTEMPTS} attempts allowed without response. 4th attempt strictly forbidden.",
                code="MAX_ATTEMPTS_EXCEEDED",
                details={"contact_id": contact_id, "attempts": current_attempts},
            )

        # Increment logical attempt count on contact
        contact.logical_outreach_attempts = current_attempts + 1
        await self.contact_repo.update(
            contact, {"logical_outreach_attempts": contact.logical_outreach_attempts}
        )

        attempt = OutreachAttempt(
            organization_id=organization_id,
            contact_id=contact_id,
            campaign_id=campaign_id,
            attempt_number=contact.logical_outreach_attempts,
            channel=channel,
            message_id=message_id,
            status="sent",
        )
        await self.attempt_repo.create(attempt)
        return attempt

    async def reset_on_positive_response(self, contact_id: str) -> None:
        """When a lead replies with an inquiry, logical attempts can be reset."""
        contact = await self.contact_repo.get_by_id(contact_id)
        if contact:
            contact.logical_outreach_attempts = 0
            await self.contact_repo.update(contact, {"logical_outreach_attempts": 0})

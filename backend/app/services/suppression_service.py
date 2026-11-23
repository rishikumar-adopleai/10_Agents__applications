"""Suppression and Opt-Out Enforcement Service."""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import BusinessRuleViolationError
from backend.app.models.conversations import SuppressionEntry
from backend.app.repositories.conversation_repo import SuppressionRepository


class SuppressionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = SuppressionRepository(session)

    async def is_contact_suppressed(
        self,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        contact_id: Optional[str] = None,
    ) -> bool:
        """Check if contact or identifiers have an active suppression stop."""
        return await self.repo.is_suppressed(email=email, phone=phone, contact_id=contact_id)

    async def record_suppression(
        self,
        organization_id: str,
        reason: str,
        contact_id: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> SuppressionEntry:
        """Record hard suppression. Rules: Cannot be cleared by campaign or revival."""
        # Check if already suppressed
        already_suppressed = await self.is_contact_suppressed(
            email=email, phone=phone, contact_id=contact_id
        )
        if already_suppressed:
            return SuppressionEntry(
                organization_id=organization_id,
                contact_id=contact_id,
                email=email,
                phone=phone,
                reason=reason,
                notes=notes,
            )

        entry = SuppressionEntry(
            organization_id=organization_id,
            contact_id=contact_id,
            email=email.lower().strip() if email else None,
            phone=phone.strip() if phone else None,
            reason=reason,
            notes=notes,
            cannot_be_cleared_by_campaign=True,
        )
        await self.repo.create(entry)
        return entry

    async def assert_can_contact(
        self,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        contact_id: Optional[str] = None,
    ) -> None:
        """Raise BusinessRuleViolationError if recipient is suppressed."""
        if await self.is_contact_suppressed(email=email, phone=phone, contact_id=contact_id):
            raise BusinessRuleViolationError(
                message="Cannot send outreach: Contact is on the suppression/opt-out registry.",
                code="CONTACT_SUPPRESSED",
                details={"email": email, "phone": phone, "contact_id": contact_id},
            )

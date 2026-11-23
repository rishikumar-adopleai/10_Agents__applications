"""Conversation, Message, Attempt and Suppression Repositories."""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.models.conversations import (
    Conversation,
    Message,
    OutreachAttempt,
    SuppressionEntry,
)
from backend.app.repositories.base import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    def __init__(self, session: AsyncSession):
        super().__init__(Conversation, session)

    async def get_with_messages(self, conversation_id: str) -> Optional[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .options(selectinload(Conversation.messages))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_contact_channel(
        self,
        contact_id: str,
        channel: str,
        organization_id: str,
    ) -> Optional[Conversation]:
        stmt = (
            select(Conversation)
            .where(
                Conversation.contact_id == contact_id,
                Conversation.channel == channel,
                Conversation.organization_id == organization_id,
                Conversation.status != "closed",
            )
            .options(selectinload(Conversation.messages))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()


class MessageRepository(BaseRepository[Message]):
    def __init__(self, session: AsyncSession):
        super().__init__(Message, session)

    async def get_by_dedup_hash(self, hash_val: str) -> Optional[Message]:
        stmt = select(Message).where(Message.deduplication_hash == hash_val)
        result = await self.session.execute(stmt)
        return result.scalars().first()


class OutreachAttemptRepository(BaseRepository[OutreachAttempt]):
    def __init__(self, session: AsyncSession):
        super().__init__(OutreachAttempt, session)

    async def count_contact_attempts(self, contact_id: str) -> int:
        stmt = select(OutreachAttempt).where(OutreachAttempt.contact_id == contact_id)
        result = await self.session.execute(stmt)
        return len(list(result.scalars().all()))


class SuppressionRepository(BaseRepository[SuppressionEntry]):
    def __init__(self, session: AsyncSession):
        super().__init__(SuppressionEntry, session)

    async def is_suppressed(
        self,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        contact_id: Optional[str] = None,
    ) -> bool:
        """Check if contact or identifier is suppressed across any campaign."""
        conditions = []
        if email:
            conditions.append(SuppressionEntry.email == email.lower().strip())
        if phone:
            conditions.append(SuppressionEntry.phone == phone.strip())
        if contact_id:
            conditions.append(SuppressionEntry.contact_id == contact_id)

        if not conditions:
            return False

        from sqlalchemy import or_

        stmt = select(SuppressionEntry).where(or_(*conditions))
        result = await self.session.execute(stmt)
        return result.scalars().first() is not None

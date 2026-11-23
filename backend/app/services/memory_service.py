"""Scoped Lead and Account Memory Service."""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.intelligence import ContactMemory, MemoryFact


class MemoryService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_contact_memory(
        self, contact_id: str, organization_id: str
    ) -> ContactMemory:
        stmt = select(ContactMemory).where(ContactMemory.contact_id == contact_id)
        result = await self.session.execute(stmt)
        memory = result.scalars().first()
        if not memory:
            memory = ContactMemory(
                organization_id=organization_id,
                contact_id=contact_id,
                summary="",
                preferences={},
                objections={},
            )
            self.session.add(memory)
            await self.session.flush()
        return memory

    async def add_memory_fact(
        self,
        organization_id: str,
        scope: str,
        fact_key: str,
        fact_value: str,
        contact_id: Optional[str] = None,
        account_id: Optional[str] = None,
        source_span: Optional[str] = None,
        confidence: float = 1.0,
    ) -> MemoryFact:
        """Store atomic factual claim with attribution span."""
        fact = MemoryFact(
            organization_id=organization_id,
            scope=scope,
            fact_key=fact_key,
            fact_value=fact_value,
            contact_id=contact_id,
            account_id=account_id,
            source_span=source_span,
            confidence=confidence,
        )
        self.session.add(fact)
        await self.session.flush()
        return fact

    async def get_facts_for_contact(self, contact_id: str) -> List[MemoryFact]:
        stmt = select(MemoryFact).where(MemoryFact.contact_id == contact_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

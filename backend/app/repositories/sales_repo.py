"""Sales Domain Repositories."""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.models.sales import Account, Campaign, Contact, Opportunity
from backend.app.repositories.base import BaseRepository


class AccountRepository(BaseRepository[Account]):
    def __init__(self, session: AsyncSession):
        super().__init__(Account, session)

    async def get_by_domain(self, domain: str, organization_id: str) -> Optional[Account]:
        stmt = select(Account).where(
            Account.domain == domain.lower().strip(),
            Account.organization_id == organization_id,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_with_relations(self, account_id: str) -> Optional[Account]:
        stmt = (
            select(Account)
            .where(Account.id == account_id)
            .options(selectinload(Account.contacts), selectinload(Account.opportunities))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()


class ContactRepository(BaseRepository[Contact]):
    def __init__(self, session: AsyncSession):
        super().__init__(Contact, session)

    async def get_by_email(self, email: str, organization_id: str) -> Optional[Contact]:
        stmt = select(Contact).where(
            Contact.email == email.lower().strip(),
            Contact.organization_id == organization_id,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_phone(self, phone: str, organization_id: str) -> Optional[Contact]:
        stmt = select(Contact).where(
            Contact.phone == phone.strip(),
            Contact.organization_id == organization_id,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()


class OpportunityRepository(BaseRepository[Opportunity]):
    def __init__(self, session: AsyncSession):
        super().__init__(Opportunity, session)


class CampaignRepository(BaseRepository[Campaign]):
    def __init__(self, session: AsyncSession):
        super().__init__(Campaign, session)

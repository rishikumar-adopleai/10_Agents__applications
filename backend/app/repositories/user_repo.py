"""User and Role Repository."""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.models.identity import Role, User
from backend.app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession):
        super().__init__(User, session)

    async def get_by_email(self, email: str) -> Optional[User]:
        stmt = (
            select(User)
            .where(User.email == email.lower().strip())
            .options(selectinload(User.roles), selectinload(User.organization))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_with_roles(self, user_id: str) -> Optional[User]:
        stmt = (
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.roles), selectinload(User.organization))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_organization(
        self,
        organization_id: str,
        skip: int = 0,
        limit: int = 50,
        search: Optional[str] = None,
    ) -> List[User]:
        stmt = (
            select(User)
            .where(User.organization_id == organization_id)
            .options(selectinload(User.roles))
        )
        if search:
            search_pattern = f"%{search.lower()}%"
            stmt = stmt.where(
                (User.first_name.ilike(search_pattern))
                | (User.last_name.ilike(search_pattern))
                | (User.email.ilike(search_pattern))
            )
        stmt = stmt.order_by(User.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class RoleRepository(BaseRepository[Role]):
    def __init__(self, session: AsyncSession):
        super().__init__(Role, session)

    async def get_by_name(self, name: str) -> Optional[Role]:
        stmt = select(Role).where(Role.name == name)
        result = await self.session.execute(stmt)
        return result.scalars().first()

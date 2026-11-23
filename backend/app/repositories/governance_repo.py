"""Governance, Approval, Audit and Permission Repositories."""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.governance import ApprovalItem, AuditEvent, ClientPermission
from backend.app.repositories.base import BaseRepository


class ApprovalRepository(BaseRepository[ApprovalItem]):
    def __init__(self, session: AsyncSession):
        super().__init__(ApprovalItem, session)

    async def list_pending(self, organization_id: str, limit: int = 50) -> List[ApprovalItem]:
        stmt = (
            select(ApprovalItem)
            .where(
                ApprovalItem.organization_id == organization_id,
                ApprovalItem.status == "pending",
            )
            .order_by(ApprovalItem.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class AuditRepository(BaseRepository[AuditEvent]):
    def __init__(self, session: AsyncSession):
        super().__init__(AuditEvent, session)


class ClientPermissionRepository(BaseRepository[ClientPermission]):
    def __init__(self, session: AsyncSession):
        super().__init__(ClientPermission, session)

    async def get_active_permission(self, account_id: str) -> Optional[ClientPermission]:
        stmt = select(ClientPermission).where(ClientPermission.account_id == account_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

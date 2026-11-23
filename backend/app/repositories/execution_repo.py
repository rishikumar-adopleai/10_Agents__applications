"""Execution, Workflow and Outbox Repositories."""

from typing import List, Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.execution import AgentTask, OutboxEvent, WorkflowRun
from backend.app.repositories.base import BaseRepository


class AgentTaskRepository(BaseRepository[AgentTask]):
    def __init__(self, session: AsyncSession):
        super().__init__(AgentTask, session)

    async def get_by_execution_id(self, execution_id: str) -> Optional[AgentTask]:
        stmt = select(AgentTask).where(AgentTask.execution_id == execution_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()


class WorkflowRunRepository(BaseRepository[WorkflowRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(WorkflowRun, session)

    async def get_by_correlation_id(self, correlation_id: str) -> Optional[WorkflowRun]:
        stmt = select(WorkflowRun).where(WorkflowRun.correlation_id == correlation_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()


class OutboxRepository(BaseRepository[OutboxEvent]):
    def __init__(self, session: AsyncSession):
        super().__init__(OutboxEvent, session)

    async def get_pending_events(self, limit: int = 50) -> List[OutboxEvent]:
        stmt = (
            select(OutboxEvent)
            .where(OutboxEvent.status == "pending")
            .order_by(OutboxEvent.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_retryable_events(self, max_retries: int = 3, limit: int = 50) -> List[OutboxEvent]:
        stmt = (
            select(OutboxEvent)
            .where(
                or_(
                    OutboxEvent.status == "pending",
                    and_(OutboxEvent.status == "failed", OutboxEvent.retry_count < max_retries),
                )
            )
            .order_by(OutboxEvent.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

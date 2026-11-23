"""Audit Event Recording Service."""

from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.logging import correlation_id_ctx
from backend.app.models.governance import AuditEvent
from backend.app.repositories.governance_repo import AuditRepository


class AuditService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = AuditRepository(session)

    async def log_event(
        self,
        organization_id: str,
        actor_id: str,
        actor_type: str,  # user, agent, system
        action: str,
        resource_type: str,
        resource_id: str,
        payload_before: Optional[Dict[str, Any]] = None,
        payload_after: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ) -> AuditEvent:
        event = AuditEvent(
            organization_id=organization_id,
            actor_id=actor_id,
            actor_type=actor_type,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            payload_before=payload_before,
            payload_after=payload_after,
            correlation_id=correlation_id or correlation_id_ctx.get() or "system",
        )
        return await self.repo.create(event)

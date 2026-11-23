"""Celery Background Agent Execution and Outbox Dispatch Tasks."""

import asyncio
from typing import Any, Dict

from backend.app.agents.orchestrator import AgentOrchestrator
from backend.app.core.logging import logger
from backend.app.db.session import AsyncSessionLocal
from backend.app.schemas.agents import AgentExecutionRequest
from backend.app.tasks.celery_app import celery


@celery.task(bind=True, name="tasks.execute_agent_async", max_retries=3, default_retry_delay=10)
def execute_agent_async(self, request_dict: Dict[str, Any]):
    """Execute an agent task asynchronously within a Celery background worker."""
    req = AgentExecutionRequest(**request_dict)
    logger.info(f"Celery executing agent {req.agent_id} async")

    async def _run():
        async with AsyncSessionLocal() as session:
            orchestrator = AgentOrchestrator(session)
            result = await orchestrator.execute_agent(req)
            await session.commit()
            return result.model_dump()

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio

            nest_asyncio.apply()
            return loop.run_until_complete(_run())
        return asyncio.run(_run())
    except Exception as exc:
        logger.error(f"Celery task failed: {exc}. Retrying...")
        raise self.retry(exc=exc)


@celery.task(name="tasks.poll_outbox_events")
def poll_outbox_events(limit: int = 50):
    """Poll transactional outbox table and reliably dispatch pending domain events."""

    async def _poll():
        from backend.app.workflows.events import EventDispatcher

        async with AsyncSessionLocal() as session:
            dispatcher = EventDispatcher(session)
            results = await dispatcher.poll_and_dispatch(limit=limit)
            await session.commit()
            return results

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio

            nest_asyncio.apply()
            return loop.run_until_complete(_poll())
        return asyncio.run(_poll())
    except Exception as exc:
        logger.error(f"Failed to poll and dispatch outbox events: {exc}")
        raise


@celery.task(bind=True, name="tasks.dispatch_outbox_event", max_retries=3, default_retry_delay=10)
def dispatch_outbox_event(self, event_id: str):
    """Dispatch a specific outbox event asynchronously."""

    async def _run():
        from backend.app.repositories.execution_repo import OutboxRepository
        from backend.app.workflows.events import EventDispatcher

        async with AsyncSessionLocal() as session:
            repo = OutboxRepository(session)
            event = await repo.get_by_id(event_id)
            if not event:
                logger.warning(f"Outbox event {event_id} not found for async dispatch.")
                return None
            dispatcher = EventDispatcher(session)
            res = await dispatcher.dispatch_event(event)
            await session.commit()
            return res

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio

            nest_asyncio.apply()
            return loop.run_until_complete(_run())
        return asyncio.run(_run())
    except Exception as exc:
        logger.error(f"Outbox event {event_id} async dispatch failed: {exc}. Retrying...")
        raise self.retry(exc=exc)


@celery.task(name="tasks.run_daily_radar_scan")
def run_daily_radar_scan(organization_id: str, icp_profile_id: str = None):
    """Scheduled task executing the daily Buying-Signal Radar scan."""
    from backend.app.services.radar_scheduler import RadarSchedulerService

    logger.info(f"Celery triggering daily radar scan for organization: {organization_id}")
    asyncio.run(
        RadarSchedulerService.trigger_radar_scan_background(
            organization_id=organization_id,
            icp_profile_id=icp_profile_id,
            trigger_type="scheduled",
        )
    )

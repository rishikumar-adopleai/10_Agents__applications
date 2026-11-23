"""Workflow Engine and Durable State Machine."""

import uuid
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.logging import logger, workflow_id_ctx
from backend.app.models.execution import WorkflowRun
from backend.app.repositories.execution_repo import WorkflowRunRepository


class WorkflowEngine:
    """Manages multi-step workflow lifecycle and persists execution state in PostgreSQL."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = WorkflowRunRepository(session)

    async def start_workflow(
        self,
        workflow_name: str,
        organization_id: str,
        initial_state: Dict[str, Any],
        correlation_id: Optional[str] = None,
    ) -> WorkflowRun:
        corr_id = correlation_id or str(uuid.uuid4())
        workflow_id_ctx.set(corr_id)

        run = WorkflowRun(
            organization_id=organization_id,
            workflow_name=workflow_name,
            correlation_id=corr_id,
            status="running",
            current_step="initialized",
            state_data=initial_state,
        )
        await self.repo.create(run)
        logger.info(f"Started workflow '{workflow_name}' [corr={corr_id}]")
        return run

    async def advance_step(
        self,
        workflow_run_id: str,
        next_step: str,
        state_updates: Dict[str, Any],
        status: str = "running",
        error: Optional[str] = None,
    ) -> WorkflowRun:
        run = await self.repo.get_by_id(workflow_run_id)
        if not run:
            raise ValueError(f"Workflow run {workflow_run_id} not found")

        updated_state = dict(run.state_data)
        updated_state.update(state_updates)

        run.current_step = next_step
        run.status = status
        run.state_data = updated_state
        update_dict = {
            "current_step": next_step,
            "status": status,
            "state_data": updated_state,
        }
        if error:
            run.error = error
            update_dict["error"] = error
        await self.repo.update(run, update_dict)
        logger.info(
            f"Advanced workflow '{run.workflow_name}' to step '{next_step}' [status={status}]"
        )
        return run

    async def fail_workflow(
        self,
        workflow_run_id: str,
        error_message: str,
    ) -> WorkflowRun:
        run = await self.repo.get_by_id(workflow_run_id)
        if run:
            run.status = "failed"
            run.error = error_message
            await self.repo.update(run, {"status": "failed", "error": error_message})
            logger.error(f"Workflow '{run.workflow_name}' failed: {error_message}")
        return run

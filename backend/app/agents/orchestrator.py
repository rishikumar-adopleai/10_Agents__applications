"""Agent Orchestration and Execution Engine."""

import asyncio
import time
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agents.registry import agent_registry
from backend.app.core.exceptions import NotFoundError
from backend.app.core.logging import agent_execution_id_ctx, logger
from backend.app.models.execution import AgentTask, DomainEvent, OutboxEvent
from backend.app.models.radar import RadarPrioritizedAccount
from backend.app.repositories.execution_repo import AgentTaskRepository
from backend.app.schemas.agents import (
    AgentExecutionRequest,
    AgentExecutionResult,
    AgentStatus,
)


class AgentOrchestrator:
    """Orchestrates agent execution, state management, audit logging, and outbox emission."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.task_repo = AgentTaskRepository(session)

    async def execute_agent(
        self,
        request: AgentExecutionRequest,
        timeout_seconds: int = 60,
    ) -> AgentExecutionResult:
        agent = agent_registry.get(request.agent_id)
        if not agent:
            raise NotFoundError(f"Agent '{request.agent_id}' is not registered in the system")

        start_time = time.time()

        # 1. Lookup or create durable AgentTask record in PostgreSQL / SQLite
        agent_task = None
        if hasattr(request, "task_id") and request.task_id:
            agent_task = await self.task_repo.get_by_id(request.task_id)
        if not agent_task and request.parameters.get("task_id"):
            agent_task = await self.task_repo.get_by_id(request.parameters["task_id"])
        if not agent_task and hasattr(request, "execution_id") and request.execution_id:
            agent_task = await self.task_repo.get_by_execution_id(request.execution_id)
        if not agent_task and request.parameters.get("execution_id"):
            agent_task = await self.task_repo.get_by_execution_id(request.parameters["execution_id"])

        if not agent_task and request.account_id:
            scan_run_id = request.parameters.get("scan_run_id")
            existing_tasks = await self.task_repo.list(
                organization_id=request.organization_id,
                filters=[
                    AgentTask.agent_id == request.agent_id,
                    AgentTask.status == AgentStatus.WAITING_FOR_INPUT.value,
                ],
                limit=10,
            )
            for t in existing_tasks:
                if (t.input_payload or {}).get("account_id") == request.account_id:
                    if not scan_run_id or (t.cost_metadata or {}).get("scan_run_id") == scan_run_id:
                        agent_task = t
                        break

        if agent_task:
            execution_id = agent_task.execution_id
            merged_payload = dict(agent_task.input_payload or {})
            merged_payload.update(request.parameters)
            agent_task.input_payload = merged_payload
            request.parameters = merged_payload
        else:
            execution_id = f"exec-{uuid.uuid4().hex[:16]}"
            agent_task = AgentTask(
                organization_id=request.organization_id,
                agent_id=request.agent_id,
                execution_id=execution_id,
                status=AgentStatus.WAITING_FOR_INPUT.value,
                input_payload=request.parameters,
                uncertainty=0.0,
                cost_metadata={"start_time": start_time},
            )
            await self.task_repo.create(agent_task)

        agent_execution_id_ctx.set(execution_id)

        # 2. Execute with bounded timeout
        try:
            logger.info(f"Starting execution of agent {request.agent_id} [exec={execution_id}]")
            result = await asyncio.wait_for(
                agent.execute(request, self.session),
                timeout=timeout_seconds,
            )
            elapsed_ms = int((time.time() - start_time) * 1000)

            # Update AgentTask with results
            agent_task.status = result.status.value
            agent_task.output_payload = result.structured_result
            agent_task.uncertainty = result.uncertainty
            cost_meta = dict(agent_task.cost_metadata or {})
            cost_meta.update({
                "elapsed_ms": elapsed_ms,
                "timeout_seconds": timeout_seconds,
            })
            agent_task.cost_metadata = cost_meta
            await self.task_repo.update(
                agent_task,
                {
                    "status": agent_task.status,
                    "output_payload": agent_task.output_payload,
                    "uncertainty": agent_task.uncertainty,
                    "cost_metadata": agent_task.cost_metadata,
                },
            )

            # Update RadarPrioritizedAccount task status if applicable
            target_acc_id = request.account_id or (agent_task.input_payload or {}).get("account_id")
            if target_acc_id:
                stmt_p = (
                    select(RadarPrioritizedAccount)
                    .where(
                        RadarPrioritizedAccount.organization_id == request.organization_id,
                        RadarPrioritizedAccount.account_id == target_acc_id,
                    )
                    .order_by(RadarPrioritizedAccount.created_at.desc())
                )
                res_p = await self.session.execute(stmt_p)
                prioritized_record = res_p.scalars().first()
                if prioritized_record:
                    if result.status in (AgentStatus.WAITING_FOR_REVIEW, AgentStatus.COMPLETED):
                        prioritized_record.agent4_task_status = "completed"
                    elif result.status == AgentStatus.BLOCKED:
                        prioritized_record.agent4_task_status = "blocked"
                    elif result.status in (AgentStatus.RETRYABLE_FAILURE, AgentStatus.TERMINAL_FAILURE):
                        prioritized_record.agent4_task_status = "failed"
                    prioritized_record.agent4_task_id = agent_task.id

            # 3. Emit Domain Event and Outbox Event
            domain_event = DomainEvent(
                organization_id=request.organization_id,
                event_type=f"agent.{request.agent_id}.{result.status.value}",
                correlation_id=request.correlation_id,
                payload={
                    "execution_id": execution_id,
                    "agent_id": request.agent_id,
                    "status": result.status.value,
                    "account_id": request.account_id,
                    "contact_id": request.contact_id,
                    "proposed_next_actions": result.proposed_next_actions,
                },
            )
            self.session.add(domain_event)

            outbox_event = OutboxEvent(
                organization_id=request.organization_id,
                event_type=f"agent.{request.agent_id}.completed",
                correlation_id=request.correlation_id,
                payload=domain_event.payload,
                status="pending",
            )
            self.session.add(outbox_event)
            await self.session.flush()

            logger.info(
                f"Completed agent {request.agent_id} in {elapsed_ms}ms with status {result.status.value}"
            )
            return result

        except asyncio.TimeoutError:
            logger.error(f"Agent {request.agent_id} timed out after {timeout_seconds}s")
            agent_task.status = AgentStatus.RETRYABLE_FAILURE.value
            agent_task.retry_count = (agent_task.retry_count or 0) + 1
            agent_task.error_message = f"Execution exceeded timeout limit of {timeout_seconds}s"
            await self.task_repo.update(
                agent_task,
                {
                    "status": agent_task.status,
                    "retry_count": agent_task.retry_count,
                    "error_message": agent_task.error_message,
                },
            )
            return AgentExecutionResult(
                agent_id=request.agent_id,
                execution_id=execution_id,
                status=AgentStatus.RETRYABLE_FAILURE,
                error_details=f"Agent timed out after {timeout_seconds}s",
            )
        except Exception as e:
            logger.exception(f"Agent {request.agent_id} failed: {str(e)}")
            is_transient = any(
                term in str(e).lower()
                for term in ("temporary", "timeout", "connection", "rate limit", "503", "502", "retry")
            )
            agent_task.status = (
                AgentStatus.RETRYABLE_FAILURE.value if is_transient else AgentStatus.TERMINAL_FAILURE.value
            )
            agent_task.retry_count = (agent_task.retry_count or 0) + 1
            agent_task.error_message = str(e)
            await self.task_repo.update(
                agent_task,
                {
                    "status": agent_task.status,
                    "retry_count": agent_task.retry_count,
                    "error_message": agent_task.error_message,
                },
            )
            return AgentExecutionResult(
                agent_id=request.agent_id,
                execution_id=execution_id,
                status=AgentStatus.RETRYABLE_FAILURE if is_transient else AgentStatus.TERMINAL_FAILURE,
                error_details=str(e),
            )

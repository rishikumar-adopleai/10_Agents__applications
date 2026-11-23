"""Agent Tasks and Execution Endpoints."""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agents.orchestrator import AgentOrchestrator
from backend.app.agents.registry import agent_registry
from backend.app.api.deps import get_current_user
from backend.app.core.rate_limit import agent_rate_limiter
from backend.app.core.rbac import CurrentUser
from backend.app.db.session import get_db
from backend.app.models.execution import AgentTask
from backend.app.repositories.execution_repo import AgentTaskRepository
from backend.app.schemas.agents import (
    AgentExecutionRequest,
    AgentExecutionResult,
)
from backend.app.schemas.common import StandardResponse

router = APIRouter(prefix="/agent-tasks", tags=["agent-tasks"])


@router.get("", response_model=StandardResponse[List[dict]])
async def list_agent_tasks(
    agent_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """List execution records of agent tasks."""
    repo = AgentTaskRepository(session)
    filters = []
    if agent_id:
        filters.append(AgentTask.agent_id == agent_id)
    if status:
        filters.append(AgentTask.status == status)

    tasks = await repo.list(
        organization_id=current_user.organization_id,
        filters=filters,
        limit=50,
    )
    result = [
        {
            "id": t.id,
            "agent_id": t.agent_id,
            "execution_id": t.execution_id,
            "status": t.status,
            "uncertainty": t.uncertainty,
            "created_at": t.created_at.isoformat(),
        }
        for t in tasks
    ]
    return StandardResponse(data=result)


@router.get("/registered-agents", response_model=StandardResponse[List[dict]])
async def list_registered_agents(
    current_user: CurrentUser = Depends(get_current_user),
):
    """List all ten specialized platform agents and their capabilities."""
    agents = agent_registry.list_all()
    data = [
        {
            "agent_id": a.agent_id,
            "name": a.name,
            "description": a.description,
        }
        for a in agents
    ]
    return StandardResponse(data=data)


@router.post(
    "/execute",
    response_model=StandardResponse[AgentExecutionResult],
    dependencies=[Depends(agent_rate_limiter)],
)
async def execute_agent(
    request: AgentExecutionRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Trigger execution of any of the ten platform agents with deterministic security boundaries."""
    request.organization_id = current_user.organization_id
    orchestrator = AgentOrchestrator(session)
    result = await orchestrator.execute_agent(request)
    return StandardResponse(
        data=result,
        message=f"Agent '{request.agent_id}' executed with status '{result.status.value}'",
    )

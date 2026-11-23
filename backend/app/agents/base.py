"""Base Agent Abstract Interface and Contracts."""

from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.schemas.agents import AgentExecutionRequest, AgentExecutionResult


class BaseAgent(ABC):
    """Abstract Base Class for all 10 specialized platform agents."""

    @property
    @abstractmethod
    def agent_id(self) -> str:
        """Unique machine identifier for the agent."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the agent."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Concise summary of agent purpose and responsibilities."""
        pass

    @abstractmethod
    async def execute(
        self,
        request: AgentExecutionRequest,
        session: AsyncSession,
    ) -> AgentExecutionResult:
        """
        Execute agent reasoning and generation logic.
        Must return structured AgentExecutionResult with controlled AgentStatus.
        """
        pass

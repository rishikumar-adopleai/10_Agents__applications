"""Platform Agent Registry."""

from typing import Dict, List, Optional

from backend.app.agents.ai_visibility.agent import AISearchVisibilityAgent
from backend.app.agents.base import BaseAgent
from backend.app.agents.buying_radar.agent import BuyingSignalRadarAgent
from backend.app.agents.deal_desk.agent import DealDeskAgent
from backend.app.agents.demo_builder.agent import DemoBeforeHelloAgent
from backend.app.agents.lead_responder.agent import LeadResponderAgent
from backend.app.agents.partner_finder.agent import PartnerFinderAgent
from backend.app.agents.proof_engine.agent import ProofEngineAgent
from backend.app.agents.research_outreach.agent import ResearchOutreachAgent
from backend.app.agents.revival_agent.agent import RevivalAgent
from backend.app.agents.security_desk.agent import TrustSecurityDeskAgent


class AgentRegistry:
    """Singleton registry indexing all 10 specialized platform agents."""

    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}
        self._register_default_agents()

    def _register_default_agents(self) -> None:
        agents: List[BaseAgent] = [
            BuyingSignalRadarAgent(),
            ResearchOutreachAgent(),
            DemoBeforeHelloAgent(),
            LeadResponderAgent(),
            DealDeskAgent(),
            TrustSecurityDeskAgent(),
            ProofEngineAgent(),
            AISearchVisibilityAgent(),
            PartnerFinderAgent(),
            RevivalAgent(),
        ]
        for agent in agents:
            self.register(agent)

    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.agent_id] = agent

    def get(self, agent_id: str) -> Optional[BaseAgent]:
        return self._agents.get(agent_id)

    def list_all(self) -> List[BaseAgent]:
        return list(self._agents.values())


agent_registry = AgentRegistry()

"""Integration Adapters Registry."""

from typing import Dict, List, Optional

from backend.app.integrations.ai.gateway import LLMGateway
from backend.app.integrations.base import BaseIntegrationAdapter, IntegrationHealth
from backend.app.integrations.calendar.microsoft import MicrosoftCalendarAdapter
from backend.app.integrations.crm.ghl import GoHighLevelAdapter
from backend.app.integrations.crm.hubspot import HubSpotAdapter
from backend.app.integrations.messaging.outlook_mail import OutlookMailAdapter
from backend.app.integrations.messaging.sms import SMSAdapter
from backend.app.integrations.research.apollo import ApolloAdapter
from backend.app.integrations.research.brave import BraveSearchAdapter
from backend.app.integrations.research.gdelt import GdeltDocAdapter
from backend.app.integrations.research.growth import GrowthNewsAdapter
from backend.app.integrations.research.job_boards import GreenhouseAdapter, LeverAdapter
from backend.app.integrations.research.regulatory import RegulatoryAdapter
from backend.app.integrations.research.sec_edgar import SecEdgarAdapter
from backend.app.integrations.storage.s3 import ObjectStorageAdapter


class IntegrationRegistry:
    """Registry managing all active external service integration adapters."""

    def __init__(self):
        self._adapters: Dict[str, BaseIntegrationAdapter] = {
            "hubspot": HubSpotAdapter(),
            "gohighlevel": GoHighLevelAdapter(),
            "apollo": ApolloAdapter(),
            "greenhouse": GreenhouseAdapter(),
            "lever": LeverAdapter(),
            "growth_news": GrowthNewsAdapter(),
            "gdelt": GdeltDocAdapter(),
            "regulatory": RegulatoryAdapter(),
            "sec_edgar": SecEdgarAdapter(),
            "brave_search": BraveSearchAdapter(),
            "sms": SMSAdapter(),
            "outlook_mail": OutlookMailAdapter(),
            "microsoft_calendar": MicrosoftCalendarAdapter(),
            "ai": LLMGateway(),
            "storage": ObjectStorageAdapter(),
        }

    def get(self, name: str) -> Optional[BaseIntegrationAdapter]:
        return self._adapters.get(name)

    async def check_all_health(self) -> List[IntegrationHealth]:
        results = []
        for adapter in self._adapters.values():
            results.append(await adapter.check_health())
        return results


integration_registry = IntegrationRegistry()

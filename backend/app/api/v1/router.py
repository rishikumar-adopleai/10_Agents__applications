"""API v1 Router Registration."""

from fastapi import APIRouter

from backend.app.api.v1.accounts import router as accounts_router
from backend.app.api.v1.agent_tasks import router as agent_tasks_router
from backend.app.api.v1.approvals import router as approvals_router
from backend.app.api.v1.auth import router as auth_router
from backend.app.api.v1.contacts import router as contacts_router
from backend.app.api.v1.conversations import router as conversations_router
from backend.app.api.v1.integrations import router as integrations_router
from backend.app.api.v1.radar import router as radar_router
from backend.app.api.v1.research import router as research_router
from backend.app.api.v1.responder import router as responder_router
from backend.app.api.v1.users import router as users_router
from backend.app.api.v1.webhooks import router as webhooks_router
from backend.app.api.v1.workflows import router as workflows_router
from backend.app.monitoring.health import router as monitoring_router

api_router = APIRouter(prefix="/api/v1")

# Register routers
api_router.include_router(monitoring_router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(accounts_router)
api_router.include_router(contacts_router)
api_router.include_router(conversations_router)
api_router.include_router(approvals_router)
api_router.include_router(webhooks_router)
api_router.include_router(agent_tasks_router)
api_router.include_router(workflows_router)
api_router.include_router(integrations_router)
api_router.include_router(radar_router)
api_router.include_router(research_router)
api_router.include_router(responder_router)

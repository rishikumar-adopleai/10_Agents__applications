"""Conversations API Endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user
from backend.app.core.exceptions import NotFoundError
from backend.app.core.rbac import CurrentUser
from backend.app.db.session import get_db
from backend.app.repositories.conversation_repo import ConversationRepository
from backend.app.schemas.common import PaginatedResponse, StandardResponse
from backend.app.schemas.conversations import ConversationResponse

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=StandardResponse[PaginatedResponse[ConversationResponse]])
async def list_conversations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    repo = ConversationRepository(session)
    skip = (page - 1) * page_size
    conversations = await repo.list(
        organization_id=current_user.organization_id,
        skip=skip,
        limit=page_size,
    )
    total = await repo.count(organization_id=current_user.organization_id)
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    items = [ConversationResponse.model_validate(c) for c in conversations]
    return StandardResponse(
        data=PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
    )


@router.get("/{conversation_id}", response_model=StandardResponse[ConversationResponse])
async def get_conversation(
    conversation_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    repo = ConversationRepository(session)
    conv = await repo.get_with_messages(conversation_id)
    if not conv:
        raise NotFoundError(f"Conversation {conversation_id} not found")
    return StandardResponse(data=ConversationResponse.model_validate(conv))


@router.post("/{conversation_id}/takeover", response_model=StandardResponse[ConversationResponse])
async def human_takeover(
    conversation_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Initiates human takeover on a conversation, suspending autonomous responses."""
    repo = ConversationRepository(session)
    conv = await repo.get_by_id(conversation_id)
    if not conv:
        raise NotFoundError(f"Conversation {conversation_id} not found")

    conv.is_human_takeover = True
    conv.assigned_user_id = current_user.id
    conv.status = "human_takeover"
    await repo.update(
        conv,
        {
            "is_human_takeover": True,
            "assigned_user_id": current_user.id,
            "status": "human_takeover",
        },
    )
    return StandardResponse(
        data=ConversationResponse.model_validate(conv),
        message="Human takeover activated. Autonomous replies paused.",
    )

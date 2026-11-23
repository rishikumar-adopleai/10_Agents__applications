"""User Management Endpoints (Complete Reference Feature)."""

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user, require_roles
from backend.app.core.rbac import CurrentUser, RoleEnum
from backend.app.db.session import get_db
from backend.app.schemas.common import PaginatedResponse, StandardResponse
from backend.app.schemas.user import UserCreate, UserResponse, UserUpdate
from backend.app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=StandardResponse[PaginatedResponse[UserResponse]])
async def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: Optional[str] = Query(default=None),
    current_user: CurrentUser = Depends(
        require_roles(RoleEnum.ADMINISTRATOR, RoleEnum.SALES_MANAGER)
    ),
    session: AsyncSession = Depends(get_db),
):
    """List users within the caller's organization with pagination and search."""
    user_service = UserService(session)
    skip = (page - 1) * page_size
    users = await user_service.list_users(
        organization_id=current_user.organization_id,
        skip=skip,
        limit=page_size,
        search=search,
    )
    total = await user_service.count_users(organization_id=current_user.organization_id)
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    items = [UserResponse.model_validate(u) for u in users]
    paginated = PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
    return StandardResponse(data=paginated)


@router.post("", response_model=StandardResponse[UserResponse], status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    current_user: CurrentUser = Depends(require_roles(RoleEnum.ADMINISTRATOR)),
    session: AsyncSession = Depends(get_db),
):
    """Provision a new user within the caller's organization. Requires Administrator role."""
    user_service = UserService(session)
    user = await user_service.create_user(
        user_in=user_in,
        organization_id=current_user.organization_id,
    )
    return StandardResponse(
        data=UserResponse.model_validate(user),
        message="User created successfully",
    )


@router.get("/{user_id}", response_model=StandardResponse[UserResponse])
async def get_user_by_id(
    user_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Get user profile details by ID."""
    user_service = UserService(session)
    user = await user_service.get_user_by_id(user_id)
    return StandardResponse(data=UserResponse.model_validate(user))


@router.put("/{user_id}", response_model=StandardResponse[UserResponse])
async def update_user(
    user_id: str,
    user_in: UserUpdate,
    current_user: CurrentUser = Depends(require_roles(RoleEnum.ADMINISTRATOR)),
    session: AsyncSession = Depends(get_db),
):
    """Update user information and role assignments. Requires Administrator role."""
    user_service = UserService(session)
    updated_user = await user_service.update_user(user_id=user_id, user_in=user_in)
    return StandardResponse(
        data=UserResponse.model_validate(updated_user),
        message="User updated successfully",
    )


@router.delete("/{user_id}", response_model=StandardResponse[dict])
async def delete_user(
    user_id: str,
    current_user: CurrentUser = Depends(require_roles(RoleEnum.ADMINISTRATOR)),
    session: AsyncSession = Depends(get_db),
):
    """Deactivate/delete user account. Requires Administrator role."""
    user_service = UserService(session)
    deleted = await user_service.delete_user(user_id)
    return StandardResponse(data={"deleted": deleted}, message="User removed successfully")

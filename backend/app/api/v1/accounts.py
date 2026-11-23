"""Accounts API Endpoints."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user
from backend.app.core.rbac import CurrentUser
from backend.app.db.session import get_db
from backend.app.repositories.sales_repo import AccountRepository
from backend.app.schemas.common import PaginatedResponse, StandardResponse
from backend.app.schemas.sales import AccountCreate, AccountResponse

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=StandardResponse[PaginatedResponse[AccountResponse]])
async def list_accounts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    repo = AccountRepository(session)
    skip = (page - 1) * page_size
    accounts = await repo.list(
        organization_id=current_user.organization_id,
        skip=skip,
        limit=page_size,
    )
    total = await repo.count(organization_id=current_user.organization_id)
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    items = [AccountResponse.model_validate(a) for a in accounts]
    return StandardResponse(
        data=PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
    )


@router.post(
    "", response_model=StandardResponse[AccountResponse], status_code=status.HTTP_201_CREATED
)
async def create_account(
    account_in: AccountCreate,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    repo = AccountRepository(session)
    account_dict = account_in.model_dump()
    account_dict["organization_id"] = current_user.organization_id
    new_account = await repo.create(account_dict)
    return StandardResponse(
        data=AccountResponse.model_validate(new_account),
        message="Account created successfully",
    )


@router.get("/{account_id}", response_model=StandardResponse[AccountResponse])
async def get_account(
    account_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    repo = AccountRepository(session)
    account = await repo.get_by_id(account_id)
    if not account:
        from backend.app.core.exceptions import NotFoundError

        raise NotFoundError(f"Account {account_id} not found")
    return StandardResponse(data=AccountResponse.model_validate(account))

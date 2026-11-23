"""Contacts API Endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user
from backend.app.core.rbac import CurrentUser
from backend.app.db.session import get_db
from backend.app.repositories.sales_repo import ContactRepository
from backend.app.schemas.common import PaginatedResponse, StandardResponse
from backend.app.schemas.sales import ContactCreate, ContactResponse

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get("", response_model=StandardResponse[PaginatedResponse[ContactResponse]])
async def list_contacts(
    account_id: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    repo = ContactRepository(session)
    skip = (page - 1) * page_size
    filters = []
    if account_id:
        filters.append(repo.model.account_id == account_id)

    contacts = await repo.list(
        organization_id=current_user.organization_id,
        skip=skip,
        limit=page_size,
        filters=filters,
    )
    total = await repo.count(organization_id=current_user.organization_id, filters=filters)
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    items = [ContactResponse.model_validate(c) for c in contacts]
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
    "", response_model=StandardResponse[ContactResponse], status_code=status.HTTP_201_CREATED
)
async def create_contact(
    contact_in: ContactCreate,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    repo = ContactRepository(session)
    contact_dict = contact_in.model_dump()
    contact_dict["organization_id"] = current_user.organization_id
    new_contact = await repo.create(contact_dict)
    return StandardResponse(
        data=ContactResponse.model_validate(new_contact),
        message="Contact created successfully",
    )

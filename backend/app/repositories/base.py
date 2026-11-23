"""Reusable Generic Async SQLAlchemy Repository."""

from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Generic async repository providing CRUD operations."""

    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session

    async def get_by_id(self, id: str) -> Optional[ModelType]:
        """Fetch a single record by primary key."""
        result = await self.session.execute(select(self.model).where(self.model.id == id))
        return result.scalars().first()

    async def list(
        self,
        organization_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[List[Any]] = None,
        order_by: Optional[Any] = None,
    ) -> List[ModelType]:
        """Fetch a paginated list of records."""
        stmt: Select = select(self.model)

        if organization_id and hasattr(self.model, "organization_id"):
            stmt = stmt.where(self.model.organization_id == organization_id)

        if filters:
            for f in filters:
                stmt = stmt.where(f)

        if order_by is not None:
            stmt = stmt.order_by(order_by)
        elif hasattr(self.model, "created_at"):
            stmt = stmt.order_by(self.model.created_at.desc())

        stmt = stmt.offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(
        self,
        organization_id: Optional[str] = None,
        filters: Optional[List[Any]] = None,
    ) -> int:
        """Count records matching filters."""
        stmt = select(func.count(self.model.id))
        if organization_id and hasattr(self.model, "organization_id"):
            stmt = stmt.where(self.model.organization_id == organization_id)
        if filters:
            for f in filters:
                stmt = stmt.where(f)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def create(self, obj_in: Union[ModelType, Dict[str, Any]]) -> ModelType:
        """Create and persist a new record."""
        if isinstance(obj_in, dict):
            db_obj = self.model(**obj_in)
        else:
            db_obj = obj_in
        self.session.add(db_obj)
        await self.session.flush()
        return db_obj

    async def update(
        self,
        db_obj: ModelType,
        obj_in: Union[Dict[str, Any], Any],
    ) -> ModelType:
        """Update fields of an existing record."""
        if isinstance(obj_in, dict):
            update_data = obj_in
        elif hasattr(obj_in, "model_dump"):
            update_data = obj_in.model_dump(exclude_unset=True)
        else:
            update_data = obj_in.__dict__

        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)

        self.session.add(db_obj)
        await self.session.flush()
        return db_obj

    async def delete(self, id: str) -> bool:
        """Delete record by ID."""
        obj = await self.get_by_id(id)
        if obj:
            await self.session.delete(obj)
            await self.session.flush()
            return True
        return False

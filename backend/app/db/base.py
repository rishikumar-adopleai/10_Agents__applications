"""SQLAlchemy Base and Declarative Model Mixins."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy models."""

    pass


class UUIDPrimaryKeyMixin:
    """Mixin for UUID primary key stored as 36-character string."""

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )


class TimestampMixin:
    """Mixin for automatic created_at and updated_at UTC timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class OrganizationScopedMixin:
    """Mixin enforcing organization scoping on multi-tenant records."""

    @declared_attr
    def organization_id(cls) -> Mapped[str]:
        return mapped_column(
            String(36),
            ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )


class BaseModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Abstract base model with UUID primary key and timestamps."""

    __abstract__ = True

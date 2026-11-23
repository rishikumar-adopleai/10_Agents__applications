"""Identity and Access SQLAlchemy Models."""

from typing import List, Optional

from sqlalchemy import Boolean, Column, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, BaseModel, OrganizationScopedMixin


class Organization(BaseModel):
    """Tenant organization."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    users: Mapped[List["User"]] = relationship(
        "User", back_populates="organization", cascade="all, delete-orphan"
    )
    memberships: Mapped[List["Membership"]] = relationship(
        "Membership", back_populates="organization"
    )


user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", String(36), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class Role(BaseModel):
    """RBAC Role entity."""

    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    users: Mapped[List["User"]] = relationship("User", secondary=user_roles, back_populates="roles")


class User(BaseModel):
    """User account entity."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    organization: Mapped["Organization"] = relationship("Organization", back_populates="users")
    roles: Mapped[List["Role"]] = relationship(
        "Role", secondary=user_roles, back_populates="users", lazy="selectin"
    )
    memberships: Mapped[List["Membership"]] = relationship("Membership", back_populates="user")


class Membership(BaseModel, OrganizationScopedMixin):
    """User-organization membership link."""

    __tablename__ = "memberships"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role_name: Mapped[str] = mapped_column(String(50), nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="memberships")
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="memberships"
    )


class RecordGrant(BaseModel, OrganizationScopedMixin):
    """Record-level access grants (e.g. specific account or deal access)."""

    __tablename__ = "record_grants"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    record_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # account, deal, questionnaire
    record_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    permission: Mapped[str] = mapped_column(String(50), nullable=False)  # read, write, approve


class RefreshTokenRevocation(BaseModel):
    """Revoked refresh token tracking."""

    __tablename__ = "refresh_token_revocations"

    jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    expires_at: Mapped[str] = mapped_column(String(50), nullable=False)

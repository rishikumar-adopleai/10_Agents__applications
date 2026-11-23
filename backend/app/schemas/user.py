"""User and RBAC Pydantic Schemas."""

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from backend.app.core.rbac import RoleEnum


class UserRoleSchema(BaseModel):
    name: RoleEnum
    description: Optional[str] = None

    @field_validator("name", mode="before")
    @classmethod
    def normalize_role_name(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.upper()
        return v

    class Config:
        from_attributes = True


class UserBase(BaseModel):
    email: EmailStr
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    is_active: bool = True


class UserCreate(UserBase):
    password: str = Field(min_length=8, description="Plaintext password (min 8 chars)")
    organization_id: Optional[str] = None
    role_names: List[RoleEnum] = Field(default_factory=lambda: [RoleEnum.SALES_REPRESENTATIVE])


class UserUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8)
    role_names: Optional[List[RoleEnum]] = None


class UserResponse(UserBase):
    id: str
    organization_id: str
    is_superuser: bool
    roles: List[UserRoleSchema]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserFilter(BaseModel):
    search: Optional[str] = None
    role: Optional[RoleEnum] = None
    is_active: Optional[bool] = None

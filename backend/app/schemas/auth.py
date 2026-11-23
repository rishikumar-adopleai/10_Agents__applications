"""Authentication Schemas."""

from typing import Optional

from pydantic import BaseModel, EmailStr

from backend.app.schemas.user import UserResponse


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class RefreshRequest(BaseModel):
    refresh_token: Optional[str] = None  # May also be passed via HttpOnly cookie


class AuthStatusResponse(BaseModel):
    authenticated: bool
    user: Optional[UserResponse] = None

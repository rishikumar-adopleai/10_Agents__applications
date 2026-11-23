"""Authentication Endpoints."""

from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user
from backend.app.core.exceptions import AuthenticationError
from backend.app.core.rate_limit import auth_rate_limiter
from backend.app.core.rbac import CurrentUser
from backend.app.core.security import (
    clear_auth_cookies,
    generate_csrf_token,
    set_auth_cookies,
)
from backend.app.db.session import get_db
from backend.app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse
from backend.app.schemas.common import StandardResponse
from backend.app.schemas.user import UserResponse
from backend.app.services.auth_service import AuthService
from backend.app.services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=StandardResponse[TokenResponse],
    dependencies=[Depends(auth_rate_limiter)],
)
async def login(
    login_in: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
):
    """Authenticate with email and password, issuing access token and setting HttpOnly refresh cookie."""
    auth_service = AuthService(session)
    user = await auth_service.authenticate_user(login_in.email, login_in.password)
    token_response, refresh_token = await auth_service.generate_tokens_for_user(user)

    csrf_token = generate_csrf_token()
    set_auth_cookies(response=response, refresh_token=refresh_token, csrf_token=csrf_token)

    return StandardResponse(data=token_response, message="Authentication successful")


@router.post(
    "/refresh",
    response_model=StandardResponse[TokenResponse],
    dependencies=[Depends(auth_rate_limiter)],
)
async def refresh_token(
    request: Request,
    response: Response,
    refresh_in: Optional[RefreshRequest] = None,
    refresh_token_cookie: Optional[str] = Cookie(None, alias="refresh_token"),
    session: AsyncSession = Depends(get_db),
):
    """Rotate access and refresh tokens. Reads refresh token from HttpOnly cookie or body."""
    token_str = (
        refresh_in.refresh_token if refresh_in and refresh_in.refresh_token else None
    ) or refresh_token_cookie
    if not token_str:
        raise AuthenticationError("Refresh token missing")

    auth_service = AuthService(session)
    new_token_response, new_refresh_token = await auth_service.refresh_tokens(token_str)

    csrf_token = generate_csrf_token()
    set_auth_cookies(response=response, refresh_token=new_refresh_token, csrf_token=csrf_token)

    return StandardResponse(data=new_token_response, message="Token refreshed successfully")


@router.post("/logout", response_model=StandardResponse[dict])
async def logout(
    response: Response,
    refresh_token_cookie: Optional[str] = Cookie(None, alias="refresh_token"),
    session: AsyncSession = Depends(get_db),
):
    """Revoke refresh token and clear HttpOnly authentication cookies."""
    if refresh_token_cookie:
        auth_service = AuthService(session)
        await auth_service.revoke_refresh_token(refresh_token_cookie)

    clear_auth_cookies(response)
    return StandardResponse(data={"logged_out": True}, message="Successfully logged out")


@router.get("/me", response_model=StandardResponse[UserResponse])
async def get_current_user_profile(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Return the profile and permissions of the currently authenticated user."""
    user_service = UserService(session)
    user = await user_service.get_user_by_id(current_user.id)
    return StandardResponse(data=UserResponse.model_validate(user))

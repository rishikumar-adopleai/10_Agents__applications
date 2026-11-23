"""FastAPI Authentication and RBAC Dependencies."""

from typing import Optional

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import AuthenticationError, PermissionDeniedError
from backend.app.core.rbac import CurrentUser, RoleEnum
from backend.app.core.security import ACCESS_TOKEN_TYPE, decode_jwt_token
from backend.app.db.session import get_db
from backend.app.repositories.user_repo import UserRepository


async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None),
    session: AsyncSession = Depends(get_db),
) -> CurrentUser:
    """Dependency extracting and verifying the authenticated user from bearer token."""
    token: Optional[str] = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]

    if not token:
        # Fallback to access_token cookie if present
        token = request.cookies.get("access_token")

    if not token:
        raise AuthenticationError("Authorization credentials were not provided")

    payload = decode_jwt_token(token, expected_type=ACCESS_TOKEN_TYPE)
    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Token payload missing subject")

    user_repo = UserRepository(session)
    user = await user_repo.get_with_roles(user_id)
    if not user or not user.is_active:
        raise AuthenticationError("User is inactive or no longer exists")

    roles = [RoleEnum(r.name) for r in user.roles if r.name in RoleEnum.__members__]
    return CurrentUser(
        id=user.id,
        email=user.email,
        organization_id=user.organization_id,
        roles=roles,
        is_active=user.is_active,
    )


async def get_current_active_admin(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Dependency requiring Administrator role."""
    if not current_user.has_role(RoleEnum.ADMINISTRATOR):
        raise PermissionDeniedError("Administrator role required")
    return current_user


def require_roles(*allowed_roles: RoleEnum):
    """Dependency for role-based endpoint authorization."""

    async def role_checker(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not current_user.has_role(*allowed_roles):
            raise PermissionDeniedError(
                message=f"Access requires one of roles: {[r.value for r in allowed_roles]}",
                details={"user_roles": [r.value for r in current_user.roles]},
            )
        return current_user

    return role_checker

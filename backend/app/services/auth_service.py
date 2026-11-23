"""Authentication and Token Management Service."""

from typing import Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.exceptions import AuthenticationError
from backend.app.core.security import (
    REFRESH_TOKEN_TYPE,
    create_access_token,
    create_refresh_token,
    decode_jwt_token,
    verify_password,
)
from backend.app.models.identity import RefreshTokenRevocation, User
from backend.app.repositories.user_repo import UserRepository
from backend.app.schemas.auth import TokenResponse
from backend.app.schemas.user import UserResponse


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)

    async def authenticate_user(self, email: str, password: str) -> User:
        """Verify email and password, returning user if valid."""
        user = await self.user_repo.get_by_email(email)
        if not user or not user.is_active:
            raise AuthenticationError("Invalid email or password")

        if not verify_password(password, user.hashed_password):
            raise AuthenticationError("Invalid email or password")

        return user

    async def generate_tokens_for_user(self, user: User) -> Tuple[TokenResponse, str]:
        """Issue access token and refresh token for an authenticated user."""
        roles = [r.name for r in user.roles]
        access_token, _ = create_access_token(
            user_id=user.id,
            organization_id=user.organization_id,
            roles=roles,
        )
        refresh_token, _ = create_refresh_token(
            user_id=user.id,
            organization_id=user.organization_id,
        )

        user_response = UserResponse.model_validate(user)
        token_response = TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user_response,
        )
        return token_response, refresh_token

    async def refresh_tokens(self, refresh_token: str) -> Tuple[TokenResponse, str]:
        """Validate refresh token, rotate tokens, and revoke the old refresh token."""
        payload = decode_jwt_token(refresh_token, expected_type=REFRESH_TOKEN_TYPE)
        user_id = payload["sub"]
        jti = payload["jti"]

        # Check if jti was previously revoked
        revoked = await self.session.execute(
            select(RefreshTokenRevocation).where(RefreshTokenRevocation.jti == jti)
        )
        if revoked.scalars().first():
            raise AuthenticationError("Refresh token has been revoked")

        user = await self.user_repo.get_with_roles(user_id)
        if not user or not user.is_active:
            raise AuthenticationError("User not found or inactive")

        # Revoke the old refresh token (Token Rotation)
        revocation = RefreshTokenRevocation(
            jti=jti,
            user_id=user_id,
            expires_at=str(payload.get("exp")),
        )
        self.session.add(revocation)
        await self.session.flush()

        # Issue new token pair
        return await self.generate_tokens_for_user(user)

    async def revoke_refresh_token(self, refresh_token: str) -> None:
        """Revoke a refresh token on logout."""
        try:
            payload = decode_jwt_token(refresh_token, expected_type=REFRESH_TOKEN_TYPE)
            jti = payload.get("jti")
            user_id = payload.get("sub")
            if jti and user_id:
                revocation = RefreshTokenRevocation(
                    jti=jti,
                    user_id=user_id,
                    expires_at=str(payload.get("exp")),
                )
                self.session.add(revocation)
                await self.session.flush()
        except Exception:
            pass  # If token is already invalid, no-op

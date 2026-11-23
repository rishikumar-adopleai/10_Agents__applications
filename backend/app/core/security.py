"""Security utilities: Passwords, JWT Tokens, Cookies, and CSRF."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import bcrypt
import jwt
from fastapi import Response

from backend.app.core.config import settings
from backend.app.core.exceptions import AuthenticationError

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"
REFRESH_COOKIE_NAME = "refresh_token"
CSRF_COOKIE_NAME = "csrf_token"


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def create_jwt_token(
    subject: str,
    token_type: str,
    expires_delta: timedelta,
    claims: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str]:
    """Create a signed JWT token returning (token, jti)."""
    now = datetime.now(timezone.utc)
    expire = now + expires_delta
    jti = secrets.token_urlsafe(16)

    payload: Dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": expire,
        "jti": jti,
    }
    if claims:
        payload.update(claims)

    encoded_jwt = jwt.encode(payload, settings.APP_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt, jti


def create_access_token(
    user_id: str, organization_id: Optional[str] = None, roles: Optional[list] = None
) -> Tuple[str, str]:
    """Create a short-lived access token."""
    claims = {
        "org_id": organization_id,
        "roles": roles or [],
    }
    return create_jwt_token(
        subject=user_id,
        token_type=ACCESS_TOKEN_TYPE,
        expires_delta=timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
        claims=claims,
    )


def create_refresh_token(user_id: str, organization_id: Optional[str] = None) -> Tuple[str, str]:
    """Create a long-lived refresh token."""
    claims = {"org_id": organization_id}
    return create_jwt_token(
        subject=user_id,
        token_type=REFRESH_TOKEN_TYPE,
        expires_delta=timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
        claims=claims,
    )


def decode_jwt_token(token: str, expected_type: str) -> Dict[str, Any]:
    """Decode and validate a signed JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.APP_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["exp", "sub", "type", "jti"]},
        )
        if payload.get("type") != expected_type:
            raise AuthenticationError(f"Invalid token type. Expected {expected_type}")
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired")
    except jwt.PyJWTError as e:
        raise AuthenticationError(f"Invalid token: {str(e)}")


def generate_csrf_token() -> str:
    """Generate a cryptographically secure CSRF token."""
    return secrets.token_urlsafe(32)


def set_auth_cookies(
    response: Response,
    refresh_token: str,
    csrf_token: str,
) -> None:
    """Set secure HttpOnly cookies for refresh token and readable CSRF token."""
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/v1/auth",
    )
    # CSRF cookie is read by the frontend client to set X-CSRF-Token header
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    """Clear authentication and CSRF cookies on logout."""
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/api/v1/auth",
        domain=settings.COOKIE_DOMAIN,
    )
    response.delete_cookie(
        key=CSRF_COOKIE_NAME,
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )

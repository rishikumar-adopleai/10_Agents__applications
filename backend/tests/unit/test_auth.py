"""Unit Tests for Authentication and Cryptography."""

import pytest

from backend.app.core.exceptions import AuthenticationError
from backend.app.core.security import (
    ACCESS_TOKEN_TYPE,
    create_access_token,
    create_refresh_token,
    decode_jwt_token,
    hash_password,
    verify_password,
)


def test_password_hashing():
    password = "MySecurePassword2026!"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_token_generation_and_decoding():
    user_id = "user-12345"
    org_id = "org-999"
    roles = ["ADMINISTRATOR"]

    token, jti = create_access_token(user_id=user_id, organization_id=org_id, roles=roles)
    assert token is not None
    assert jti is not None

    payload = decode_jwt_token(token, expected_type=ACCESS_TOKEN_TYPE)
    assert payload["sub"] == user_id
    assert payload["org_id"] == org_id
    assert payload["roles"] == roles
    assert payload["type"] == ACCESS_TOKEN_TYPE


def test_token_type_validation_fails_on_mismatch():
    user_id = "user-12345"
    token, _ = create_refresh_token(user_id=user_id)

    with pytest.raises(AuthenticationError) as exc_info:
        # Expected access, but received refresh
        decode_jwt_token(token, expected_type=ACCESS_TOKEN_TYPE)
    assert "Invalid token type" in str(exc_info.value.message)

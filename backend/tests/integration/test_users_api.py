"""Integration Tests for Users API (Complete Reference Feature)."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_auth_login_success(client: AsyncClient, seed_data):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "Password123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "access_token" in data["data"]
    assert data["data"]["user"]["email"] == "admin@test.com"
    # HttpOnly refresh cookie was set
    assert "refresh_token" in response.cookies


@pytest.mark.asyncio
async def test_list_users_as_admin(client: AsyncClient, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.get("/api/v1/users?page=1&page_size=10", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    items = data["data"]["items"]
    assert len(items) >= 4
    assert data["data"]["page"] == 1


@pytest.mark.asyncio
async def test_create_user_as_admin(client: AsyncClient, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}
    payload = {
        "email": "new.user@test.com",
        "password": "SecurePassword123!",
        "first_name": "New",
        "last_name": "Employee",
        "role_names": ["SALES_REPRESENTATIVE"],
    }
    response = await client.post("/api/v1/users", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["data"]["email"] == "new.user@test.com"
    assert data["data"]["roles"][0]["name"] == "SALES_REPRESENTATIVE"


@pytest.mark.asyncio
async def test_create_user_forbidden_for_sales_rep(client: AsyncClient, rep_token: str):
    headers = {"Authorization": f"Bearer {rep_token}"}
    payload = {
        "email": "unauthorized.create@test.com",
        "password": "SecurePassword123!",
        "first_name": "Hacker",
        "last_name": "Attempt",
        "role_names": ["ADMINISTRATOR"],
    }
    response = await client.post("/api/v1/users", json=payload, headers=headers)
    assert response.status_code == 403
    data = response.json()
    assert data["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_update_and_delete_user(client: AsyncClient, admin_token: str, seed_data):
    headers = {"Authorization": f"Bearer {admin_token}"}
    rep = seed_data["sales_rep"]

    # Update
    update_res = await client.put(
        f"/api/v1/users/{rep.id}",
        json={"first_name": "Robert Updated"},
        headers=headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["data"]["first_name"] == "Robert Updated"

    # Delete
    del_res = await client.delete(f"/api/v1/users/{rep.id}", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["data"]["deleted"] is True

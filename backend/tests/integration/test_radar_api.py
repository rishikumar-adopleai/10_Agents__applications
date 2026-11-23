"""Integration tests for Buying-Signal Radar (Agent 1) API endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.sales import Account


@pytest.mark.asyncio
async def test_icp_lifecycle_and_rbac(
    client: AsyncClient,
    admin_token: str,
    rep_token: str,
    seed_data,
):
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    rep_headers = {"Authorization": f"Bearer {rep_token}"}

    # 1. Sales rep tries to create ICP (allowed only for manager/admin)
    create_payload = {
        "name": "Midwest Hospital Groups",
        "description": "Midwest hospital and healthcare organizations.",
        "criteria": {
            "country": "United States",
            "target_industries": ["Hospital & Health Care"],
            "employee_min": 100,
            "employee_max": 10000,
            "min_qualifying_score": 0.60,
        },
    }
    rep_res = await client.post("/api/v1/radar/icp", json=create_payload, headers=rep_headers)
    assert rep_res.status_code == 403  # RBAC enforced!

    # 2. Admin creates draft ICP
    admin_res = await client.post("/api/v1/radar/icp", json=create_payload, headers=admin_headers)
    assert admin_res.status_code == 201
    profile_data = admin_res.json()["data"]
    profile_id = profile_data["id"]
    assert profile_data["status"] == "draft"

    # 3. Rep tries to approve -> forbidden
    rep_approve_res = await client.post(f"/api/v1/radar/icp/{profile_id}/approve", headers=rep_headers)
    assert rep_approve_res.status_code == 403

    # 4. Admin approves ICP -> active
    admin_approve_res = await client.post(f"/api/v1/radar/icp/{profile_id}/approve", headers=admin_headers)
    assert admin_approve_res.status_code == 200
    approved_data = admin_approve_res.json()["data"]
    assert approved_data["status"] == "approved"
    assert approved_data["is_active"] is True

    # 5. List profiles
    list_res = await client.get("/api/v1/radar/icp", headers=admin_headers)
    assert list_res.status_code == 200
    assert len(list_res.json()["data"]) >= 1


@pytest.mark.asyncio
async def test_csv_import_api_and_preview(
    client: AsyncClient,
    admin_token: str,
):
    headers = {"Authorization": f"Bearer {admin_token}"}
    csv_content = (
        "Company Name,Website,Industry,# Employees,Company Country,Company State\n"
        "CHAS Health,http://www.chas.org,hospital & health care,1800,United States,Washington\n"
        "Grand Rapids Clinic,http://www.grclinic.org,hospital & health care,450,United States,Michigan\n"
    )

    # 1. Preview endpoint
    preview_res = await client.post(
        "/api/v1/radar/imports/preview",
        data={"raw_content": csv_content},
        headers=headers,
    )
    assert preview_res.status_code == 200
    preview_data = preview_res.json()["data"]
    assert preview_data["total_rows_detected"] == 2
    assert "Company Name" in preview_data["headers"]

    # 2. Ingest endpoint
    import_res = await client.post(
        "/api/v1/radar/imports",
        data={"raw_content": csv_content},
        headers=headers,
    )
    assert import_res.status_code == 200
    import_data = import_res.json()["data"]
    assert import_data["imported_accounts"] == 2
    assert import_data["status"] == "completed"

    # 3. Import history list
    history_res = await client.get("/api/v1/radar/imports", headers=headers)
    assert history_res.status_code == 200
    assert len(history_res.json()["data"]) >= 1


@pytest.mark.asyncio
async def test_radar_scan_and_top_accounts_e2e(
    client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
    seed_data,
):
    headers = {"Authorization": f"Bearer {admin_token}"}
    org = seed_data["org"]

    # 1. Seed candidate accounts
    acc1 = Account(
        organization_id=org.id,
        name="CHAS Health",
        domain="chas.org",
        industry="Hospital & Health Care",
        country="United States",
        employee_count=1800,
        short_description="Federally Qualified Health Center specializing in outpatient care, prior authorization, and revenue cycle.",
        status="prospect",
    )
    acc2 = Account(
        organization_id=org.id,
        name="Acme Tech Non-Target",
        domain="acmetech.io",
        industry="Software",
        country="Germany",
        employee_count=10,
        status="prospect",
    )
    db_session.add_all([acc1, acc2])
    await db_session.commit()

    # 2. Trigger Radar Scan (Run Now)
    scan_res = await client.post(
        "/api/v1/radar/scans",
        json={"scoring_mode": "demo", "trigger_type": "manual"},
        headers=headers,
    )
    assert scan_res.status_code == 200
    scan_data = scan_res.json()["data"]
    assert scan_data["status"] == "completed"
    assert scan_data["total_accounts_evaluated"] >= 2
    assert scan_data["shortlist_size"] >= 1

    # 3. Query Top Prioritized Accounts
    top_res = await client.get("/api/v1/radar/top-accounts", headers=headers)
    assert top_res.status_code == 200
    top_items = top_res.json()["data"]
    assert len(top_items) >= 1
    top_account = top_items[0]
    assert top_account["rank"] == 1
    assert "chas.org" in top_account["domain"]
    assert top_account["total_score"] > 0.50
    assert top_account["agent4_task_status"] == "pending_research"

    # 4. Query Account Evidence
    ev_res = await client.get(f"/api/v1/radar/accounts/{top_account['account_id']}/evidence", headers=headers)
    assert ev_res.status_code == 200
    ev_items = ev_res.json()["data"]
    assert len(ev_items) >= 1
    assert ev_items[0]["verification_status"] == "VERIFIED"

    # 5. Connectors Status
    status_res = await client.get("/api/v1/radar/integrations/status", headers=headers)
    assert status_res.status_code == 200
    connectors = status_res.json()["data"]["connectors"]
    providers = {c["provider"] for c in connectors}
    assert "greenhouse" in providers
    assert "regulatory_cms" in providers
    assert "sec_edgar" in providers
    assert "hubspot" in providers
    assert "apollo" in providers

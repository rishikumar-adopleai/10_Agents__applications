"""Integration Tests for Inbound Messaging Webhooks."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from backend.app.models.conversations import SuppressionEntry
from backend.app.models.sales import Contact


@pytest.mark.asyncio
async def test_inbound_sms_ingest_and_deduplication(client: AsyncClient, db_session, seed_data):
    org = seed_data["org"]
    contact = Contact(
        organization_id=org.id,
        account_id=seed_data["org"].id,
        first_name="Sam",
        last_name="Fisher",
        email="sam@splinter.com",
        phone="+15554443322",
    )
    db_session.add(contact)
    await db_session.flush()

    payload = {
        "provider": "twilio_mock",
        "message_id": "msg-unique-1001",
        "sender_phone": "+15554443322",
        "recipient_phone": "+15551234567",
        "body": "Hi, I am interested in your automated sales platform.",
    }

    # 1. First Send -> Ingested
    res1 = await client.post("/api/v1/webhooks/sms", json=payload)
    assert res1.status_code == 200
    assert res1.json()["data"]["status"] == "ingested"

    # 2. Duplicate Send -> Deduplicated and Ignored
    res2 = await client.post("/api/v1/webhooks/sms", json=payload)
    assert res2.status_code == 200
    assert res2.json()["data"]["status"] == "duplicate_ignored"


@pytest.mark.asyncio
async def test_inbound_opt_out_triggers_suppression(client: AsyncClient, db_session, seed_data):
    payload = {
        "provider": "twilio_mock",
        "message_id": "msg-opt-out-555",
        "sender_phone": "+15558889900",
        "recipient_phone": "+15551234567",
        "body": "STOP",
    }

    res = await client.post("/api/v1/webhooks/sms", json=payload)
    assert res.status_code == 200

    # Verify contact is in suppression registry
    supp_res = await db_session.execute(
        select(SuppressionEntry).where(SuppressionEntry.phone == "+15558889900")
    )
    entry = supp_res.scalars().first()
    assert entry is not None
    assert entry.reason == "opt_out"
    assert entry.cannot_be_cleared_by_campaign is True

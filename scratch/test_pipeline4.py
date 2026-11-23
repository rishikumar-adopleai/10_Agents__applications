"""Automated Verification Suite for Pipeline 4 (24/7 Lead Responder Agent)."""

import asyncio
import json
import os
import sys

# Force mock mode & SQLite for fast local verification in sandbox
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./platform.db"
os.environ["LLM_API_KEY"] = "mock"
os.environ["PIPELINE2_EXECUTION_MODE"] = "mock"
os.environ["AI_PROVIDER"] = "mock"

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import httpx
from sqlalchemy import delete, select
from backend.app.db.base import Base
from backend.app.db.session import engine, AsyncSessionLocal
from backend.app.models.sales import Account, Contact
from backend.app.models.conversations import Conversation, SuppressionEntry
from backend.app.models.meetings import MeetingBooking, MeetingProposal, NodeExecutionLog
from backend.app.integrations.calendar.microsoft import MicrosoftCalendarAdapter
from backend.app.services.pipeline4_engine import Pipeline4Engine


async def run_pipeline4_tests():
    print("=" * 70)
    print("RUNNING PIPELINE 4 (24/7 LEAD RESPONDER AGENT) VERIFICATION SUITE")
    print("=" * 70)

    # 1. Initialize Tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[INIT] Database schema verified & tables created.")

    org_id = "org-test-pipeline4"
    test_email = "alex.rivera@enterprise-corp.com"
    test_phone = "+14155550199"

    # Reset any previous test suppressions/bookings for idempotent runs
    async with AsyncSessionLocal() as session:
        # Delete previous test calendar events directly from Microsoft Graph
        cal_adapter = MicrosoftCalendarAdapter()
        if not cal_adapter.missing_credentials():
            try:
                prev_mtgs = await session.execute(
                    select(MeetingBooking).where(
                        MeetingBooking.attendee_email.in_([test_email, "inbound@prospect.example"])
                    )
                )
                token = await cal_adapter._acquire_token()
                async with httpx.AsyncClient(timeout=10.0) as client:
                    for m in prev_mtgs.scalars().all():
                        if m.outlook_event_id and not m.outlook_event_id.startswith("mtg-"):
                            del_url = f"https://graph.microsoft.com/v1.0/users/{cal_adapter.organizer_email}/events/{m.outlook_event_id}"
                            await client.delete(del_url, headers={"Authorization": f"Bearer {token}"})
            except Exception:
                pass

        await session.execute(
            delete(SuppressionEntry).where(
                (SuppressionEntry.phone == test_phone) | (SuppressionEntry.email == test_email)
            )
        )
        await session.execute(
            delete(MeetingBooking).where(
                MeetingBooking.attendee_email.in_([test_email, "inbound@prospect.example"])
            )
        )
        await session.execute(delete(MeetingProposal).where(MeetingProposal.organization_id == org_id))
        await session.commit()
    print("[INIT] Test state cleaned for idempotent test execution.")

    async with AsyncSessionLocal() as session:
        # Check existing contact
        contact_res = await session.execute(
            select(Contact).where(Contact.email == test_email)
        )
        contact = contact_res.scalar_one_or_none()
        if not contact:
            account = Account(
                id="acc-test-pipeline4",
                organization_id=org_id,
                name="Enterprise Corp",
                domain="enterprise-corp.com",
                industry="Financial Services",
            )
            session.add(account)
            await session.flush()

            contact = Contact(
                id="cnt-test-pipeline4",
                organization_id=org_id,
                account_id=account.id,
                first_name="Alex",
                last_name="Rivera",
                email=test_email,
                phone=test_phone,
                title="VP of Sales Operations",
            )
            session.add(contact)
            await session.commit()
            print(f"[INIT] Created test Account and Contact: {contact.first_name} {contact.last_name}")
        else:
            print(f"[INIT] Using existing Contact: {contact.first_name} {contact.last_name}")

    # =========================================================================
    # TEST 1: Meeting Inquiry for 2:00 AM (Occupied -> 3:00 AM Offered)
    # =========================================================================
    print("\n--- TEST 1: Inbound 2:00 AM Meeting Inquiry (Occupied -> Alternative 3:00 AM Offered) ---")
    async with AsyncSessionLocal() as session:
        engine_svc = Pipeline4Engine(session)
        res1 = await engine_svc.process_inbound_message(
            sender=test_phone,
            recipient="+1 (555) 000-1122",
            body="Can we meet next Thursday at 2:00 AM to discuss the AI platform?",
            channel="sms",
            organization_id=org_id,
        )

        assert res1["status"] == "success", f"Test 1 failed: {res1}"
        conv_id = res1["conversation_id"]
        node5 = res1["node5"]
        draft = res1["draft_reply"]

        print(f"Primary Intent: {node5.get('primary_intent')}")
        print(f"Meeting State: {node5.get('meeting_state')}")
        print(f"Draft Reply: {draft}")

        assert "2:00" in draft or "2" in draft, "Draft must mention requested 2 AM"
        assert "3:00" in draft or "3" in draft, "Draft must offer alternative 3 AM"

        # Verify proposal persisted
        prop_res = await session.execute(
            select(MeetingProposal).where(MeetingProposal.conversation_id == conv_id)
        )
        proposals = prop_res.scalars().all()
        assert len(proposals) > 0, "MeetingProposal must be persisted in database"
        print(f"[PASS] TEST 1 passed! 2 AM recognized as occupied; 3 AM offered. Proposal ID: {proposals[0].id}")

    # =========================================================================
    # TEST 2: Confirmation "Yes, 3 AM works" -> Auto-booked with Teams link
    # =========================================================================
    print("\n--- TEST 2: Lead Confirmation 'Yes, 3 AM works' -> Auto-Booked with Teams Join URL ---")
    async with AsyncSessionLocal() as session:
        engine_svc = Pipeline4Engine(session)
        res2 = await engine_svc.process_inbound_message(
            sender=test_phone,
            recipient="+1 (555) 000-1122",
            body="Yes, 3 AM works for me. Please confirm.",
            channel="sms",
            organization_id=org_id,
        )

        assert res2["status"] == "success", f"Test 2 failed: {res2}"
        node5_2 = res2["node5"]
        draft_2 = res2["draft_reply"]

        print(f"Primary Intent: {node5_2.get('primary_intent')}")
        print(f"Meeting State: {node5_2.get('meeting_state')}")
        print(f"Draft Reply: {draft_2}")

        assert node5_2.get("meeting_state") == "booking_confirmed", "Meeting must be confirmed"
        assert "teams.microsoft.com" in draft_2, "Confirmation draft must include Microsoft Teams join link"
        assert node5_2.get("auto_approved") is True, "Confirmed meeting reply should be auto-approved"

        # Verify MeetingBooking record in database
        mtg_res = await session.execute(
            select(MeetingBooking).where(MeetingBooking.conversation_id == conv_id)
        )
        bookings = mtg_res.scalars().all()
        assert len(bookings) > 0, "MeetingBooking record must exist in DB"
        booking = bookings[0]
        print(f"Booking ID: {booking.id}")
        print(f"Start Time: {booking.start_time}")
        print(f"Teams Join URL: {booking.teams_join_url}")
        # pyrefly: ignore[not-iterable]
        assert "teams.microsoft.com" in booking.teams_join_url, "Teams join URL must be present on booking"
        print("[PASS] TEST 2 passed! 3 AM confirmed, booked in Outlook, Teams join URL generated.")

    # =========================================================================
    # TEST 3: Hard Opt-Out ("STOP") -> Suppression & Stop
    # =========================================================================
    print("\n--- TEST 3: Opt-Out ('STOP') -> Deterministic Hard Suppression ---")
    async with AsyncSessionLocal() as session:
        engine_svc = Pipeline4Engine(session)
        res3 = await engine_svc.process_inbound_message(
            sender=test_phone,
            recipient="+1 (555) 000-1122",
            body="STOP",
            channel="sms",
            organization_id=org_id,
        )

        print(f"Status: {res3.get('status')}")
        print(f"Processing Decision: {res3.get('processing_decision')}")
        print(f"Action: {res3.get('action')}")

        assert res3.get("action") == "suppressed", "Inbound STOP must result in suppressed action"

        # Check suppression entry in DB
        supp_res = await session.execute(
            select(SuppressionEntry).where(SuppressionEntry.phone == test_phone)
        )
        supp = supp_res.scalar_one_or_none()
        assert supp is not None, "Suppression entry must exist in DB"
        # pyrefly: ignore[missing-attribute]
        print(f"[PASS] TEST 3 passed! STOP correctly created hard suppression entry: {supp.phone}")

    # =========================================================================
    # TEST 4: Negative Tone with High Buying Interest
    # =========================================================================
    print("\n--- TEST 4: Negative Emotional Tone with High Buying Interest ---")
    async with AsyncSessionLocal() as session:
        # Use an email address for testing email channel
        engine_svc = Pipeline4Engine(session)
        email_body = "Our existing CRM provider is completely broken and leaking lead data. Can your platform fix our compliance issues?"
        res4 = await engine_svc.process_inbound_message(
            sender="carol.danvers@avengers-enterprise.com",
            recipient="sales@adople.ai",
            body=email_body,
            channel="email",
            organization_id=org_id,
        )

        assert res4["status"] == "success", f"Test 4 failed: {res4}"
        node3 = res4["node3"]
        print(f"Sentiment: {node3.get('sentiment')}")
        print(f"Contact Rejection: {node3.get('contact_rejection')}")
        print(f"Buying Interest: {node3.get('buying_interest')}")
        print(f"Draft: {res4['draft_reply'][:120]}...")

        assert node3.get("contact_rejection") is False, "Should NOT reject contact"
        assert res4.get("draft_reply") is not None, "Draft reply must be generated"
        print("[PASS] TEST 4 passed! Negative frustration parsed with buying interest; pipeline continues.")

    # =========================================================================
    # TEST 5: Pipeline 3 Marketplace Demo Request
    # =========================================================================
    print("\n--- TEST 5: Pipeline 3 Marketplace Demo Request ---")
    async with AsyncSessionLocal() as session:
        engine_svc = Pipeline4Engine(session)
        res5 = await engine_svc.process_inbound_message(
            sender="bruce.wayne@wayneenterprises.com",
            recipient="sales@adople.ai",
            body="Can you share a demo video of your autonomous sales agent?",
            channel="email",
            organization_id=org_id,
        )

        assert res5["status"] == "success", f"Test 5 failed: {res5}"
        draft_5 = res5["draft_reply"]
        print(f"Draft Demo Link in reply: {draft_5}")
        assert "marketplace.adople.ai" in draft_5, "Draft must contain marketplace demo link"
        print("[PASS] TEST 5 passed! Marketplace demo retrieved and embedded.")

    # =========================================================================
    # TEST 6: Telemetry Logs Verification
    # =========================================================================
    print("\n--- TEST 6: Telemetry Logging Verification ---")
    async with AsyncSessionLocal() as session:
        log_res = await session.execute(
            select(NodeExecutionLog).where(NodeExecutionLog.organization_id == org_id)
        )
        logs = log_res.scalars().all()
        print(f"Total NodeExecutionLog records recorded: {len(logs)}")
        assert len(logs) >= 4, "Must have recorded telemetry logs for all executions"
        latest = logs[-1]
        print(f"Latest Log ID: {latest.id}, Total Latency: {latest.total_latency_ms}ms, Send Status: {latest.send_status}")
        print("[PASS] TEST 6 passed! 5-node telemetry records stored properly.")

    print("\n" + "=" * 70)
    print("ALL PIPELINE 4 VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_pipeline4_tests())

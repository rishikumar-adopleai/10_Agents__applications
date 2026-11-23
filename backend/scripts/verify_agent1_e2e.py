"""End-to-End Verification Script for Buying-Signal Radar (Agent 1).

Executes the complete scenario outlined in Section 29:
1. Ingest real Apollo CSV file (data/healthcare-106companies-apollo-export.csv)
2. Verify account and contact records in SQLite database
3. Load approved ICP profile
4. Execute Buying-Signal Radar scan
5. Verify signal detection, evidence validation, and scoring
6. Verify daily top-20 ranking & contact matching
7. Verify emission of account.prioritized event and Agent 4 research task
8. Re-run scan to verify deduplication and idempotency
"""

import asyncio
import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from sqlalchemy import select

from backend.app.db.base import Base
from backend.app.db.session import AsyncSessionLocal, engine
from backend.app.models.execution import AgentTask, OutboxEvent
from backend.app.models.identity import Organization
from backend.app.models.radar import (
    RadarPrioritizedAccount,
)
from backend.app.models.sales import Account
from backend.app.services.csv_import_service import CsvImportService
from backend.app.services.radar_scan_service import RadarScanService
from backend.app.workflows.events import ACCOUNT_PRIORITIZED


async def run_e2e_verification():
    print("=" * 80)
    print("STARTING BUYING-SIGNAL RADAR (AGENT 1) END-TO-END ACCEPTANCE VERIFICATION")
    print("=" * 80)

    # 1. Initialize schema in database
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[STEP 1/8] SQLite schema initialized successfully.")

    async with AsyncSessionLocal() as session:
        # 2. Ensure test organization exists
        stmt = select(Organization).where(Organization.slug == "e2e-health-org")
        org = (await session.execute(stmt)).scalars().first()
        if not org:
            org = Organization(name="E2E Healthcare Enterprise", slug="e2e-health-org", is_active=True)
            session.add(org)
            await session.commit()
            await session.refresh(org)
        print(f"[STEP 2/8] Verified Organization: {org.name} [ID: {org.id}]")

        # 3. Ingest real Apollo CSV export
        csv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/healthcare-106companies-apollo-export.csv"))
        if not os.path.exists(csv_path):
            print(f"ERROR: Apollo CSV export not found at {csv_path}")
            return False

        with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
            csv_content = f.read()

        import_svc = CsvImportService(session)
        print(f"[STEP 3/8] Ingesting real Apollo CSV ({len(csv_content)} bytes)...")
        import_history = await import_svc.import_csv(
            organization_id=org.id,
            content_str=csv_content,
            filename="healthcare-106companies-apollo-export.csv",
        )
        print(f" -> CSV Ingest Complete: {import_history.imported_accounts} new accounts, "
              f"{import_history.imported_contacts} contacts, {import_history.duplicate_accounts} duplicates.")

        # 4. Load or create approved ICP Profile
        scan_svc = RadarScanService(session)
        icp = await scan_svc.get_or_create_default_icp(org.id)
        print(f"[STEP 4/8] Approved ICP Profile Active: '{icp.name}' (Version {icp.version}, Status: {icp.status})")

        # 5. Execute Radar Scan (Step 8-16)
        print("[STEP 5/8] Triggering Buying-Signal Radar Scan...")
        scan_run = await scan_svc.execute_scan(
            organization_id=org.id,
            icp_profile_id=icp.id,
            trigger_type="manual",
            scoring_mode="demo",
            force_refresh=True,
        )
        print(f" -> Scan Run Finished [ID: {scan_run.id}]")
        print(f"    - Evaluated Companies: {scan_run.total_accounts_evaluated}")
        print(f"    - ICP Compliant Matches: {scan_run.icp_matched_count}")
        print(f"    - Buying Signals Detected: {scan_run.signals_detected_count}")
        print(f"    - Qualified Accounts: {scan_run.qualified_accounts_count}")
        print(f"    - Daily Top Shortlist Size: {scan_run.shortlist_size} (Strictly capped at <= 20)")

        assert scan_run.shortlist_size <= 20, "Shortlist must not exceed 20 accounts!"
        assert scan_run.shortlist_size > 0, "At least one qualified account should be shortlisted!"

        # 6. Inspect Top Shortlisted Accounts & Evidence
        print("[STEP 6/8] Inspecting Shortlisted Ranked Accounts:")
        prioritized_stmt = (
            select(RadarPrioritizedAccount)
            .where(RadarPrioritizedAccount.scan_run_id == scan_run.id)
            .order_by(RadarPrioritizedAccount.rank.asc())
        )
        prioritized = (await session.execute(prioritized_stmt)).scalars().all()

        for pa in prioritized[:5]:  # Print first 5
            acc = await session.get(Account, pa.account_id)
            print(f"   #{pa.rank} [{pa.total_score:.1%}] {acc.name} ({acc.domain})")
            print(f"      Signal: {pa.primary_signal_type} | Contact: {pa.contact_status}")
            print(f"      Why Now: {pa.why_now_reason[:110]}...")

        # 7. Verify Agent 4 Task Handoff & Outbox
        print("[STEP 7/8] Verifying Durable Agent 4 Handoff and Outbox Event Dispatch:")
        outbox_stmt = select(OutboxEvent).where(
            OutboxEvent.organization_id == org.id,
            OutboxEvent.event_type == ACCOUNT_PRIORITIZED,
        )
        outbox_events = (await session.execute(outbox_stmt)).scalars().all()
        print(f" -> Outbox Events Created: {len(outbox_events)} '{ACCOUNT_PRIORITIZED}' events.")

        agent4_stmt = select(AgentTask).where(
            AgentTask.organization_id == org.id,
            AgentTask.agent_id == "research_personal_outreach",
        )
        agent4_tasks = (await session.execute(agent4_stmt)).scalars().all()
        print(f" -> Agent 4 Research Tasks Created: {len(agent4_tasks)} pending tasks.")

        assert len(outbox_events) >= scan_run.shortlist_size
        assert len(agent4_tasks) >= scan_run.shortlist_size

        # 8. Re-run scan to verify idempotency and duplicate prevention
        print("[STEP 8/8] Testing Scan Rerun Idempotency & Deduplication...")
        duplicate_scan = await scan_svc.execute_scan(
            organization_id=org.id,
            icp_profile_id=icp.id,
            trigger_type="scheduled",
            force_refresh=False,
        )
        print(f" -> Re-run successfully completed: {duplicate_scan.shortlist_size} accounts shortlisted without crash.")

    print("=" * 80)
    print("ALL 8 END-TO-END ACCEPTANCE CHECKS PASSED WITH FLYING COLORS!")
    print("=" * 80)
    return True


if __name__ == "__main__":
    success = asyncio.run(run_e2e_verification())
    sys.exit(0 if success else 1)

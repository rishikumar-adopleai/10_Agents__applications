"""Seed Apollo CSV and run Radar scan for Acme Corporation."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from sqlalchemy import select

from backend.app.db.session import AsyncSessionLocal
from backend.app.models.identity import Organization
from backend.app.services.csv_import_service import CsvImportService
from backend.app.services.radar_scan_service import RadarScanService


async def main():
    async with AsyncSessionLocal() as session:
        # 1. Get Acme Corporation
        stmt = select(Organization).where(Organization.slug == "acme-corp")
        acme = (await session.execute(stmt)).scalars().first()
        if not acme:
            print("Acme Corporation not found!")
            return

        print(f"Seeding Radar data for: {acme.name} ({acme.id})")

        # 2. Ingest Apollo CSV
        csv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/healthcare-106companies-apollo-export.csv"))
        with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
            csv_content = f.read()

        csv_svc = CsvImportService(session)
        history = await csv_svc.import_csv(
            organization_id=acme.id,
            content_str=csv_content,
            filename="healthcare-106companies-apollo-export.csv",
        )
        print(f"Imported {history.imported_accounts} accounts for Acme Corporation.")

        # 3. Run Radar Scan
        scan_svc = RadarScanService(session)
        scan = await scan_svc.execute_scan(
            organization_id=acme.id,
            trigger_type="manual",
            force_refresh=True,
            scoring_mode="demo",
        )
        print(f"Scan complete! ID: {scan.id}, Shortlist: {scan.shortlist_size}")


if __name__ == "__main__":
    asyncio.run(main())

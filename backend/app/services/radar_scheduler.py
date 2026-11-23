"""Scheduling and Background Processing for Buying-Signal Radar."""

from typing import Optional

from backend.app.core.logging import logger
from backend.app.db.session import AsyncSessionLocal
from backend.app.services.radar_scan_service import RadarScanService


class RadarSchedulerService:
    """Manages scheduled and manual execution runs with SQLite single-writer safety and checkpoints."""

    @staticmethod
    async def trigger_radar_scan_background(
        organization_id: str,
        icp_profile_id: Optional[str] = None,
        trigger_type: str = "scheduled",
        scoring_mode: str = "demo",
    ) -> str:
        """Execute a radar scan in an isolated async session outside of HTTP request transactions."""
        logger.info(f"Starting background radar scan for organization {organization_id} (trigger: {trigger_type})")

        async with AsyncSessionLocal() as session:
            try:
                scan_svc = RadarScanService(session)
                scan_run = await scan_svc.execute_scan(
                    organization_id=organization_id,
                    icp_profile_id=icp_profile_id,
                    trigger_type=trigger_type,
                    scoring_mode=scoring_mode,
                )
                logger.info(f"Background radar scan {scan_run.id} finished successfully.")
                return scan_run.id
            except Exception as exc:
                logger.error(f"Background radar scan failed: {exc}")
                raise

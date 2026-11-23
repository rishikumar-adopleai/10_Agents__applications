"""Buying-Signal Radar Domain Repositories."""

from typing import List, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.radar import (
    CsvImportHistory,
    IcpProfile,
    RadarPrioritizedAccount,
    RadarScanRun,
    RegulatoryRule,
    SignalEvidence,
)
from backend.app.repositories.base import BaseRepository


class IcpProfileRepository(BaseRepository[IcpProfile]):
    def __init__(self, session: AsyncSession):
        super().__init__(IcpProfile, session)

    async def get_active_profile(self, organization_id: str) -> Optional[IcpProfile]:
        stmt = (
            select(IcpProfile)
            .where(
                IcpProfile.organization_id == organization_id,
                IcpProfile.is_active == True,
                IcpProfile.status == "approved",
            )
            .order_by(desc(IcpProfile.version))
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_latest_profile(self, organization_id: str) -> Optional[IcpProfile]:
        stmt = (
            select(IcpProfile)
            .where(IcpProfile.organization_id == organization_id)
            .order_by(desc(IcpProfile.version))
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()


class RadarScanRunRepository(BaseRepository[RadarScanRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(RadarScanRun, session)

    async def get_active_running_scan(self, organization_id: str) -> Optional[RadarScanRun]:
        stmt = select(RadarScanRun).where(
            RadarScanRun.organization_id == organization_id,
            RadarScanRun.status == "running",
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_latest_completed_scan(self, organization_id: str) -> Optional[RadarScanRun]:
        stmt = (
            select(RadarScanRun)
            .where(
                RadarScanRun.organization_id == organization_id,
                RadarScanRun.status == "completed",
            )
            .order_by(desc(RadarScanRun.created_at))
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()


class RadarPrioritizedAccountRepository(BaseRepository[RadarPrioritizedAccount]):
    def __init__(self, session: AsyncSession):
        super().__init__(RadarPrioritizedAccount, session)

    async def list_by_scan(
        self, scan_run_id: str, organization_id: str, limit: int = 20
    ) -> List[RadarPrioritizedAccount]:
        stmt = (
            select(RadarPrioritizedAccount)
            .where(
                RadarPrioritizedAccount.scan_run_id == scan_run_id,
                RadarPrioritizedAccount.organization_id == organization_id,
            )
            .order_by(RadarPrioritizedAccount.rank.asc())
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())


class SignalEvidenceRepository(BaseRepository[SignalEvidence]):
    def __init__(self, session: AsyncSession):
        super().__init__(SignalEvidence, session)

    async def get_by_hash(self, evidence_hash: str, organization_id: str) -> Optional[SignalEvidence]:
        stmt = select(SignalEvidence).where(
            SignalEvidence.evidence_hash == evidence_hash,
            SignalEvidence.organization_id == organization_id,
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def list_for_account(
        self, account_id: str, organization_id: str, status: Optional[str] = None
    ) -> List[SignalEvidence]:
        stmt = select(SignalEvidence).where(
            SignalEvidence.account_id == account_id,
            SignalEvidence.organization_id == organization_id,
        )
        if status:
            stmt = stmt.where(SignalEvidence.verification_status == status)
        stmt = stmt.order_by(desc(SignalEvidence.created_at))
        res = await self.session.execute(stmt)
        return list(res.scalars().all())


class RegulatoryRuleRepository(BaseRepository[RegulatoryRule]):
    def __init__(self, session: AsyncSession):
        super().__init__(RegulatoryRule, session)

    async def get_by_identifier(
        self, rule_identifier: str, organization_id: str
    ) -> Optional[RegulatoryRule]:
        stmt = select(RegulatoryRule).where(
            RegulatoryRule.rule_identifier == rule_identifier,
            RegulatoryRule.organization_id == organization_id,
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def list_active_rules(self, organization_id: str) -> List[RegulatoryRule]:
        stmt = select(RegulatoryRule).where(
            RegulatoryRule.organization_id == organization_id,
            RegulatoryRule.verification_status == "VERIFIED",
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())


class CsvImportHistoryRepository(BaseRepository[CsvImportHistory]):
    def __init__(self, session: AsyncSession):
        super().__init__(CsvImportHistory, session)

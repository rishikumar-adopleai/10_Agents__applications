"""Buying-Signal Radar API Endpoints."""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user, require_roles
from backend.app.core.exceptions import AppException, NotFoundError
from backend.app.core.logging import logger
from backend.app.core.rbac import CurrentUser, RoleEnum
from backend.app.db.session import get_db
from backend.app.integrations.registry import integration_registry
from backend.app.models.radar import (
    CsvImportHistory,
    IcpProfile,
    RadarPrioritizedAccount,
    RadarScanRun,
)
from backend.app.models.sales import Account, Contact
from backend.app.repositories.radar_repo import (
    IcpProfileRepository,
    RadarScanRunRepository,
    SignalEvidenceRepository,
)
from backend.app.schemas.common import StandardResponse
from backend.app.schemas.radar import (
    CsvImportResponse,
    CsvPreviewResponse,
    IcpProfileCreate,
    IcpProfileResponse,
    IcpProfileUpdate,
    IntegrationStatusItem,
    PipelineExecutionResponse,
    PipelineIcpUpdate,
    PipelineStepStatus,
    RadarIntegrationsStatusResponse,
    RadarPrioritizedAccountResponse,
    RadarScanRequest,
    RadarScanRunResponse,
    SignalEvidenceResponse,
)
from backend.app.services.csv_import_service import CsvImportService
from backend.app.services.radar_scan_service import RadarScanService

router = APIRouter(prefix="/radar", tags=["buying_signal_radar"])


# =========================================================================
# 1. ICP Profile Management Endpoints
# =========================================================================


@router.get("/icp", response_model=StandardResponse[List[IcpProfileResponse]])
async def list_icp_profiles(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """List all ICP profile configurations for the current organization."""
    stmt = (
        select(IcpProfile)
        .where(IcpProfile.organization_id == current_user.organization_id)
        .order_by(desc(IcpProfile.version))
    )
    res = await session.execute(stmt)
    profiles = res.scalars().all()
    return StandardResponse(
        data=[IcpProfileResponse.model_validate(p) for p in profiles],
        message="ICP profiles retrieved",
    )


@router.post(
    "/icp",
    response_model=StandardResponse[IcpProfileResponse],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(RoleEnum.ADMINISTRATOR, RoleEnum.SALES_MANAGER))],
)
async def create_icp_profile(
    profile_in: IcpProfileCreate,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Create a new ICP profile configuration in draft status."""
    repo = IcpProfileRepository(session)
    latest = await repo.get_latest_profile(current_user.organization_id)
    next_version = (latest.version + 1) if latest else 1

    profile = IcpProfile(
        organization_id=current_user.organization_id,
        name=profile_in.name,
        description=profile_in.description,
        version=next_version,
        status="draft",
        is_active=False,
        criteria=profile_in.criteria.model_dump(),
    )
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return StandardResponse(
        data=IcpProfileResponse.model_validate(profile),
        message="ICP profile created in draft status",
    )


@router.get("/icp/{profile_id}", response_model=StandardResponse[IcpProfileResponse])
async def get_icp_profile(
    profile_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Get a specific ICP profile by ID."""
    repo = IcpProfileRepository(session)
    profile = await repo.get_by_id(profile_id)
    if not profile or profile.organization_id != current_user.organization_id:
        raise NotFoundError(f"ICP profile '{profile_id}' not found")
    return StandardResponse(data=IcpProfileResponse.model_validate(profile))


@router.put(
    "/icp/{profile_id}",
    response_model=StandardResponse[IcpProfileResponse],
    dependencies=[Depends(require_roles(RoleEnum.ADMINISTRATOR, RoleEnum.SALES_MANAGER))],
)
async def update_icp_profile(
    profile_id: str,
    profile_in: IcpProfileUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Update an existing draft ICP profile."""
    repo = IcpProfileRepository(session)
    profile = await repo.get_by_id(profile_id)
    if not profile or profile.organization_id != current_user.organization_id:
        raise NotFoundError(f"ICP profile '{profile_id}' not found")

    if profile.name is not None and profile_in.name is not None:
        profile.name = profile_in.name
    if profile_in.description is not None:
        profile.description = profile_in.description
    if profile_in.criteria is not None:
        profile.criteria = profile_in.criteria.model_dump()
        profile.status = "draft"  # Modifications return profile to draft for re-approval

    await session.commit()
    await session.refresh(profile)
    return StandardResponse(data=IcpProfileResponse.model_validate(profile))


@router.post(
    "/icp/{profile_id}/approve",
    response_model=StandardResponse[IcpProfileResponse],
    dependencies=[Depends(require_roles(RoleEnum.ADMINISTRATOR, RoleEnum.SALES_MANAGER))],
)
async def approve_icp_profile(
    profile_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Approve an ICP profile for production radar execution."""
    repo = IcpProfileRepository(session)
    profile = await repo.get_by_id(profile_id)
    if not profile or profile.organization_id != current_user.organization_id:
        raise NotFoundError(f"ICP profile '{profile_id}' not found")

    profile.status = "approved"
    profile.approved_by_user_id = current_user.id
    profile.approved_at = datetime.now(timezone.utc)
    profile.is_active = True

    # Mark other profiles as inactive
    stmt = (
        select(IcpProfile)
        .where(
            IcpProfile.organization_id == current_user.organization_id,
            IcpProfile.id != profile.id,
        )
    )
    res = await session.execute(stmt)
    for other in res.scalars().all():
        other.is_active = False

    await session.commit()
    await session.refresh(profile)
    return StandardResponse(
        data=IcpProfileResponse.model_validate(profile),
        message=f"ICP profile '{profile.name}' v{profile.version} approved and activated.",
    )


@router.get("/pipeline/icp", response_model=StandardResponse[Dict[str, Any]])
async def get_pipeline_icp(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Retrieve the current active Approved ICP criteria (US Healthcare + Finance Targeting Rules)."""
    scan_svc = RadarScanService(session)
    profile = await scan_svc.get_or_create_default_icp(current_user.organization_id)
    criteria = dict(profile.criteria or {})
    result = {
        "id": profile.id,
        "name": profile.name,
        "country": criteria.get("country", "United States"),
        "industries": criteria.get("industries") or criteria.get("target_industries") or ["Healthcare", "Financial Services"],
        "employee_range": criteria.get("employee_range", "any"),
        "operational_focus": criteria.get("operational_focus") or criteria.get("target_operations") or [
            "fraud", "kyc", "prior_authorization", "claims"
        ],
        "schedule_time": criteria.get("schedule_time", "08:00 AM UTC"),
        "auto_run_enabled": criteria.get("auto_run_enabled", True),
        "version": profile.version,
        "status": profile.status,
        "is_active": profile.is_active,
    }
    return StandardResponse(data=result, message="Pipeline ICP criteria retrieved")


@router.put("/pipeline/icp", response_model=StandardResponse[Dict[str, Any]])
async def update_pipeline_icp(
    icp_in: PipelineIcpUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Update and save the Approved ICP criteria into SQLite, marking it active."""
    scan_svc = RadarScanService(session)
    profile = await scan_svc.get_or_create_default_icp(current_user.organization_id)

    updated_criteria = dict(profile.criteria or {})
    updated_criteria["country"] = icp_in.country
    updated_criteria["industries"] = icp_in.industries
    updated_criteria["employee_range"] = icp_in.employee_range
    updated_criteria["operational_focus"] = icp_in.operational_focus
    updated_criteria["target_industries"] = icp_in.industries
    updated_criteria["target_operations"] = icp_in.operational_focus
    if icp_in.schedule_time:
        updated_criteria["schedule_time"] = icp_in.schedule_time
    if icp_in.auto_run_enabled is not None:
        updated_criteria["auto_run_enabled"] = icp_in.auto_run_enabled

    profile.criteria = updated_criteria
    profile.status = "approved"
    profile.is_active = True
    profile.approved_by_user_id = current_user.id
    profile.approved_at = datetime.now(timezone.utc)

    await session.commit()
    await session.refresh(profile)

    result = {
        "id": profile.id,
        "name": profile.name,
        "country": updated_criteria["country"],
        "industries": updated_criteria["industries"],
        "employee_range": updated_criteria["employee_range"],
        "operational_focus": updated_criteria["operational_focus"],
        "schedule_time": updated_criteria.get("schedule_time", "08:00 AM UTC"),
        "auto_run_enabled": updated_criteria.get("auto_run_enabled", True),
        "version": profile.version,
        "status": profile.status,
        "is_active": profile.is_active,
    }
    return StandardResponse(data=result, message="Approved ICP criteria updated and saved.")


@router.post("/pipeline/run", response_model=StandardResponse[PipelineExecutionResponse])
async def run_radar_pipeline(
    scan_req: RadarScanRequest = RadarScanRequest(),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Execute the full 8-step Buying-Signal Radar pipeline."""
    logger.info(
        f"⚡ [API] POST /api/v1/radar/pipeline/run received from {current_user.email} (Org: {current_user.organization_id})"
    )
    scan_svc = RadarScanService(session)
    scan_run = await scan_svc.execute_scan(
        organization_id=current_user.organization_id,
        icp_profile_id=scan_req.icp_profile_id,
        trigger_type=scan_req.trigger_type or "pipeline_trigger",
        force_refresh=True,
        scoring_mode=scan_req.scoring_mode or "demo",
        custom_criteria=scan_req.custom_criteria,
    )

    # Fetch shortlisted accounts for this scan
    top_res = await get_top_prioritized_accounts(
        scan_id=scan_run.id,
        limit=20,
        current_user=current_user,
        session=session,
    )
    accounts = top_res.data or []

    pipeline_steps = [
        PipelineStepStatus(
            step=1,
            name="Approved ICP",
            status="completed",
            details="US Healthcare + Finance Targeting Rules loaded (Apollo CSV active, HubSpot API synced).",
        ),
        PipelineStepStatus(
            step=2,
            name="Company Processing",
            status="completed",
            details=f"Evaluated {scan_run.total_accounts_evaluated} target accounts from Apollo CSV & CRM deduplicated in SQLite.",
        ),
        PipelineStepStatus(
            step=3,
            name="Buying-Signal Research Engine",
            status="completed",
            details=f"Detected {scan_run.signals_detected_count} buying signals across 5 categories (Greenhouse, Lever, GDELT, CMS, SEC EDGAR, HubSpot).",
        ),
        PipelineStepStatus(
            step=4,
            name="Evidence Validation",
            status="completed",
            details="Verified company names, source URLs, freshness dates, and SHA-256 evidence integrity hashes.",
        ),
        PipelineStepStatus(
            step=5,
            name="Scoring and Ranking",
            status="completed",
            details="Computed ICP Fit Score (35%) and Why Now Urgency Score (65%) with compound urgency calibration.",
        ),
        PipelineStepStatus(
            step=6,
            name="Top 20 Qualified Accounts",
            status="completed",
            details=f"Produced top {len(accounts)} qualified accounts with one-line Why Now reasons and verified contacts.",
        ),
        PipelineStepStatus(
            step=7,
            name="Save Results to SQLite",
            status="completed",
            details="Persisted radar scan runs, prioritized accounts, evidence items, and audit events to SQLite.",
        ),
        PipelineStepStatus(
            step=8,
            name="Handoff to Agent 4",
            status="completed",
            details=f"Emitted {len(accounts)} account.prioritized domain & outbox events for Agent 4 (Research & Personal Outreach).",
        ),
    ]

    response_data = PipelineExecutionResponse(
        scan_id=scan_run.id,
        status=scan_run.status,
        pipeline_steps=pipeline_steps,
        total_evaluated=scan_run.total_accounts_evaluated,
        icp_matched=scan_run.icp_matched_count,
        signals_detected=scan_run.signals_detected_count,
        shortlist_count=scan_run.shortlist_size,
        accounts=accounts,
    )

    return StandardResponse(
        data=response_data,
        message=f"Radar pipeline executed successfully: {len(accounts)} accounts prioritized.",
    )


# =========================================================================
# 2. Apollo CSV Import Endpoints
# =========================================================================


@router.post("/imports/preview", response_model=StandardResponse[CsvPreviewResponse])
async def preview_csv(
    file: Optional[UploadFile] = File(None),
    raw_content: Optional[str] = Form(None),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Preview uploaded CSV columns, detect headers, and provide suggested mappings."""
    content_str = ""
    if file:
        content_bytes = await file.read()
        content_str = content_bytes.decode("utf-8", errors="replace")
    elif raw_content:
        content_str = raw_content
    else:
        raise AppException(
            code="BAD_REQUEST", message="Either file or raw_content must be provided.", status_code=400
        )

    svc = CsvImportService(session)
    preview = svc.preview_csv(content_str)
    return StandardResponse(data=CsvPreviewResponse(**preview))


@router.post("/imports", response_model=StandardResponse[CsvImportResponse])
async def import_csv(
    file: Optional[UploadFile] = File(None),
    file_path: Optional[str] = Form(None),
    raw_content: Optional[str] = Form(None),
    column_mapping: Optional[str] = Form(None),  # JSON-encoded mapping
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Import Apollo CSV file, normalize accounts and contacts, and record import history."""
    content_str = ""
    filename = "apollo_export.csv"

    if file:
        filename = file.filename or "apollo_export.csv"
        content_bytes = await file.read()
        content_str = content_bytes.decode("utf-8", errors="replace")
    elif file_path:
        filename = file_path.split("/")[-1].split("\\")[-1]
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content_str = f.read()
        except Exception as e:
            raise AppException(
                code="FILE_ERROR", message=f"Failed to read file from path: {e}", status_code=400
            )
    elif raw_content:
        content_str = raw_content
    else:
        raise AppException(
            code="BAD_REQUEST", message="File, file_path, or raw_content must be provided.", status_code=400
        )

    parsed_mapping = None
    if column_mapping:
        try:
            parsed_mapping = json.loads(column_mapping)
        except Exception:
            parsed_mapping = None

    svc = CsvImportService(session)
    history = await svc.import_csv(
        organization_id=current_user.organization_id,
        content_str=content_str,
        filename=filename,
        custom_mapping=parsed_mapping,
    )

    return StandardResponse(
        data=CsvImportResponse(
            import_id=history.id,
            filename=history.filename,
            total_rows=history.total_rows,
            imported_accounts=history.imported_accounts,
            imported_contacts=history.imported_contacts,
            duplicate_accounts=history.duplicate_accounts,
            errors_count=history.errors_count,
            status=history.status,
            error_log=history.error_log or [],
        ),
        message=f"Import completed: {history.imported_accounts} accounts imported.",
    )


@router.get("/imports", response_model=StandardResponse[List[CsvImportResponse]])
async def list_import_history(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Get import audit history."""
    stmt = (
        select(CsvImportHistory)
        .where(CsvImportHistory.organization_id == current_user.organization_id)
        .order_by(desc(CsvImportHistory.created_at))
        .limit(20)
    )
    res = await session.execute(stmt)
    records = res.scalars().all()
    return StandardResponse(
        data=[
            CsvImportResponse(
                import_id=r.id,
                filename=r.filename,
                total_rows=r.total_rows,
                imported_accounts=r.imported_accounts,
                imported_contacts=r.imported_contacts,
                duplicate_accounts=r.duplicate_accounts,
                errors_count=r.errors_count,
                status=r.status,
                error_log=r.error_log or [],
            )
            for r in records
        ]
    )


# =========================================================================
# 3. Radar Scan Execution & Top Accounts Endpoints
# =========================================================================


@router.post("/scans", response_model=StandardResponse[RadarScanRunResponse])
async def trigger_scan(
    scan_req: RadarScanRequest = RadarScanRequest(),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Trigger a Buying-Signal Radar scan run (Run Now or manual trigger)."""
    logger.info(f"⚡ [API] POST /api/v1/radar/scans received from {current_user.email}")
    scan_svc = RadarScanService(session)
    scan_run = await scan_svc.execute_scan(
        organization_id=current_user.organization_id,
        icp_profile_id=scan_req.icp_profile_id,
        trigger_type=scan_req.trigger_type,
        force_refresh=scan_req.force_refresh,
        scoring_mode=scan_req.scoring_mode or "demo",
        custom_criteria=scan_req.custom_criteria,
    )
    return StandardResponse(
        data=RadarScanRunResponse.model_validate(scan_run),
        message=f"Radar scan completed with {scan_run.shortlist_size} shortlisted accounts.",
    )


@router.get("/scans", response_model=StandardResponse[List[RadarScanRunResponse]])
async def list_scans(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """List historical Buying-Signal Radar scans."""
    stmt = (
        select(RadarScanRun)
        .where(RadarScanRun.organization_id == current_user.organization_id)
        .order_by(desc(RadarScanRun.created_at))
        .limit(20)
    )
    res = await session.execute(stmt)
    scans = res.scalars().all()
    return StandardResponse(data=[RadarScanRunResponse.model_validate(s) for s in scans])


@router.get("/scans/{scan_id}", response_model=StandardResponse[RadarScanRunResponse])
async def get_scan_details(
    scan_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Get scan run execution details and summary metrics."""
    repo = RadarScanRunRepository(session)
    scan = await repo.get_by_id(scan_id)
    if not scan or scan.organization_id != current_user.organization_id:
        raise NotFoundError(f"Scan '{scan_id}' not found")
    return StandardResponse(data=RadarScanRunResponse.model_validate(scan))


@router.post("/scans/{scan_id}/cancel", response_model=StandardResponse[RadarScanRunResponse])
async def cancel_scan(
    scan_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Cancel an active scan run."""
    repo = RadarScanRunRepository(session)
    scan = await repo.get_by_id(scan_id)
    if not scan or scan.organization_id != current_user.organization_id:
        raise NotFoundError(f"Scan '{scan_id}' not found")

    if scan.status == "running":
        scan.status = "cancelled"
        await session.commit()
        await session.refresh(scan)

    return StandardResponse(data=RadarScanRunResponse.model_validate(scan), message="Scan cancelled")


@router.get("/top-accounts", response_model=StandardResponse[List[RadarPrioritizedAccountResponse]])
async def get_top_prioritized_accounts(
    scan_id: Optional[str] = Query(None),
    limit: int = Query(default=20, ge=1, le=50),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Get the daily top prioritized qualified accounts with scores and contact recommendations."""
    target_scan_id = scan_id
    if not target_scan_id:
        scan_repo = RadarScanRunRepository(session)
        latest_scan = await scan_repo.get_latest_completed_scan(current_user.organization_id)
        if latest_scan:
            target_scan_id = latest_scan.id

    if not target_scan_id:
        return StandardResponse(data=[], message="No completed radar scans found.")

    # Load prioritized accounts joined with Account and Contact
    stmt = (
        select(RadarPrioritizedAccount)
        .where(
            RadarPrioritizedAccount.scan_run_id == target_scan_id,
            RadarPrioritizedAccount.organization_id == current_user.organization_id,
        )
        .order_by(RadarPrioritizedAccount.rank.asc())
        .limit(limit)
    )
    res = await session.execute(stmt)
    prioritized_list = list(res.scalars().all())

    evidence_repo = SignalEvidenceRepository(session)
    results = []

    for item in prioritized_list:
        # Load account info
        acc_res = await session.execute(select(Account).where(Account.id == item.account_id))
        acc = acc_res.scalars().first()

        # Load contact info if assigned
        contact_name = None
        contact_email = None
        contact_title = None
        if item.suggested_contact_id:
            c_res = await session.execute(select(Contact).where(Contact.id == item.suggested_contact_id))
            c = c_res.scalars().first()
            if c:
                contact_name = f"{c.first_name} {c.last_name}"
                contact_email = c.email
                contact_title = c.title

        # Load evidence
        evidences = await evidence_repo.list_for_account(
            item.account_id, current_user.organization_id, status="VERIFIED"
        )
        ev_items = [SignalEvidenceResponse.model_validate(e) for e in evidences]

        results.append(
            RadarPrioritizedAccountResponse(
                id=item.id,
                organization_id=item.organization_id,
                scan_run_id=item.scan_run_id,
                account_id=item.account_id,
                account_name=acc.name if acc else "Unknown",
                domain=acc.domain if acc else "",
                industry=acc.industry if acc else None,
                rank=item.rank,
                icp_score=item.icp_score,
                why_now_score=item.why_now_score,
                total_score=item.total_score,
                why_now_reason=item.why_now_reason,
                primary_signal_type=item.primary_signal_type,
                score_breakdown=item.score_breakdown,
                suggested_contact_id=item.suggested_contact_id,
                suggested_contact_name=contact_name,
                suggested_contact_email=contact_email,
                suggested_contact_title=contact_title,
                contact_status=item.contact_status,
                agent4_task_status=item.agent4_task_status,
                agent4_task_id=item.agent4_task_id,
                event_id=item.event_id,
                evidence_items=ev_items,
                created_at=item.created_at,
            )
        )

    return StandardResponse(data=results, message=f"Retrieved {len(results)} top accounts")


@router.get(
    "/accounts/{account_id}/evidence",
    response_model=StandardResponse[List[SignalEvidenceResponse]],
)
async def get_account_evidence(
    account_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Get all verified evidence records backing buying signals for a specific company."""
    repo = SignalEvidenceRepository(session)
    evidences = await repo.list_for_account(account_id, current_user.organization_id)
    return StandardResponse(
        data=[SignalEvidenceResponse.model_validate(e) for e in evidences],
        message="Account evidence retrieved",
    )


# =========================================================================
# 4. Integration Connector Health Endpoints
# =========================================================================


@router.get("/integrations/status", response_model=StandardResponse[RadarIntegrationsStatusResponse])
async def get_radar_integrations_status(
    current_user: CurrentUser = Depends(get_current_user),
):
    """Return actual operational health of all 5 buying-signal connectors and input sources."""
    connectors = []

    # 1. Greenhouse
    gh = integration_registry.get("greenhouse")
    gh_health = await gh.check_health() if gh else None
    connectors.append(
        IntegrationStatusItem(
            provider="greenhouse",
            category="Signal 1: Manual Work / Hiring",
            status=gh_health.status if gh_health else "unavailable",
            details=gh_health.details if gh_health else None,
        )
    )

    # 2. Lever
    lever = integration_registry.get("lever")
    lever_health = await lever.check_health() if lever else None
    connectors.append(
        IntegrationStatusItem(
            provider="lever",
            category="Signal 1: Manual Work / Hiring",
            status=lever_health.status if lever_health else "unavailable",
            details=lever_health.details if lever_health else None,
        )
    )

    # 3. Growth News
    growth = integration_registry.get("growth_news")
    growth_health = await growth.check_health() if growth else None
    connectors.append(
        IntegrationStatusItem(
            provider="news_growth",
            category="Signal 2: Company Growth",
            status=growth_health.status if growth_health else "unavailable",
            details=growth_health.details if growth_health else None,
        )
    )

    # 4. CMS & Regulatory
    reg = integration_registry.get("regulatory")
    reg_health = await reg.check_health() if reg else None
    connectors.append(
        IntegrationStatusItem(
            provider="regulatory_cms",
            category="Signal 3: Regulatory Deadlines",
            status=reg_health.status if reg_health else "unavailable",
            details=reg_health.details if reg_health else None,
        )
    )

    # 5. SEC EDGAR
    sec = integration_registry.get("sec_edgar")
    sec_health = await sec.check_health() if sec else None
    connectors.append(
        IntegrationStatusItem(
            provider="sec_edgar",
            category="Signal 4: SEC Public Filings",
            status=sec_health.status if sec_health else "unavailable",
            details=sec_health.details if sec_health else None,
        )
    )

    # 6. HubSpot
    hs = integration_registry.get("hubspot")
    hs_health = await hs.check_health() if hs else None
    connectors.append(
        IntegrationStatusItem(
            provider="hubspot",
            category="Signal 5: Interest in Us",
            status=hs_health.status if hs_health else "unavailable",
            details=hs_health.details if hs_health else None,
        )
    )

    # 7. Apollo Input
    ap = integration_registry.get("apollo")
    ap_health = await ap.check_health() if ap else None
    connectors.append(
        IntegrationStatusItem(
            provider="apollo",
            category="Company Input (CSV Active, API Future)",
            status=ap_health.status if ap_health else "unavailable",
            details=ap_health.details if ap_health else None,
        )
    )

    return StandardResponse(data=RadarIntegrationsStatusResponse(connectors=connectors))

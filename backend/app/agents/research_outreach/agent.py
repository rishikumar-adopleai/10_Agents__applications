"""Research and Personal Outreach Agent."""

import uuid
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agents.base import BaseAgent
from backend.app.agents.demo_builder.agent import DemoBeforeHelloAgent
from backend.app.agents.research_outreach.opportunity_analyzer import OpportunityAnalyzer
from backend.app.agents.research_outreach.sample_loader import (
    SampleDataLoader,
)
from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.integrations.research.apollo import ApolloAdapter
from backend.app.integrations.research.brave import BraveSearchAdapter
from backend.app.models.artifacts import BuyingSignal, ResearchBrief
from backend.app.models.governance import ApprovalItem
from backend.app.models.radar import SignalEvidence
from backend.app.models.sales import Account, Contact
from backend.app.schemas.agents import (
    AgentExecutionRequest,
    AgentExecutionResult,
    AgentStatus,
    ArtifactReference,
    EvidenceReference,
)
from backend.app.services.attempt_service import AttemptTrackingService
from backend.app.services.suppression_service import SuppressionService


class ResearchOutreachAgent(BaseAgent):
    """
    Pipeline 2: Research & Personal Outreach Agent.
    Implements the 12-step enterprise research and personalized outreach lifecycle.
    """

    def __init__(
        self,
        brave_adapter: Optional[BraveSearchAdapter] = None,
        apollo_adapter: Optional[ApolloAdapter] = None,
        analyzer: Optional[OpportunityAnalyzer] = None,
    ):
        self.sample_loader = SampleDataLoader()
        self.analyzer = analyzer or OpportunityAnalyzer()
        self.demo_agent = DemoBeforeHelloAgent()
        self.brave_adapter = brave_adapter or BraveSearchAdapter()
        self.apollo_adapter = apollo_adapter or ApolloAdapter()

    @property
    def agent_id(self) -> str:
        return "research_personal_outreach"

    @property
    def name(self) -> str:
        return "Research & Personal Outreach"

    @property
    def description(self) -> str:
        return (
            "Researches prioritized enterprise accounts, ranks decision-makers, "
            "analyzes business opportunities, coordinates optional demos, and drafts personalized outreach."
        )

    async def execute(
        self,
        request: AgentExecutionRequest,
        session: AsyncSession,
    ) -> AgentExecutionResult:
        execution_id = f"exec-{uuid.uuid4().hex[:12]}"
        account_id = request.account_id or request.parameters.get("account_id")
        contact_id = request.contact_id or request.parameters.get("contact_id")

        if not account_id:
            return AgentExecutionResult(
                agent_id=self.agent_id,
                execution_id=execution_id,
                status=AgentStatus.TERMINAL_FAILURE,
                error_details="account_id is required for Research & Personal Outreach",
            )

        # Resolve execution mode cleanly: preserve test mode for sample/test runs
        requested_mode = str(request.parameters.get("execution_mode") or "").strip().lower()
        if requested_mode in ("test", "production"):
            execution_mode = requested_mode
        elif request.parameters.get("use_sample_data") or str(account_id).startswith("ACC-"):
            execution_mode = "test"
        else:
            execution_mode = "production" if settings.is_pipeline2_production else "test"

        stage_statuses: Dict[str, Any] = {
            "execution_mode": execution_mode,
            "research": "pending",
            "enrichment": "pending",
            "llm_analysis": "pending",
            "outreach_draft": "pending",
        }
        logger.info(
            f"[Pipeline2][{execution_mode}] Starting execution_id='{execution_id}' account_id='{account_id}'."
        )

        # ---------------------------------------------------------------------
        # STEP 1: Receive Company Data
        # ---------------------------------------------------------------------
        company_data: Optional[Dict[str, Any]] = request.parameters.get("company_data")
        db_account: Optional[Account] = None

        if not company_data:
            # Only read synthetic sample fixtures in test mode
            is_sample_request = execution_mode == "test" and (
                str(account_id).startswith("ACC-")
                or bool(request.parameters.get("use_sample_data"))
                or settings.PIPELINE2_INPUT_MODE == "mock"
            )

            if is_sample_request:
                company_data = self.sample_loader.get_sample_account_by_id(str(account_id))

            # If not found in sample fixtures or not sample request, check database
            if not company_data:
                res = await session.execute(
                    select(Account).where(
                        Account.id == account_id,
                        Account.organization_id == request.organization_id,
                    )
                )
                db_account = res.scalars().first()

                if db_account:
                    # Fetch associated signals from SignalEvidence and BuyingSignal
                    ev_res = await session.execute(
                        select(SignalEvidence).where(
                            SignalEvidence.account_id == db_account.id,
                            SignalEvidence.organization_id == request.organization_id,
                        )
                    )
                    db_evidences = ev_res.scalars().all()

                    sig_res = await session.execute(
                        select(BuyingSignal).where(BuyingSignal.account_id == db_account.id)
                    )
                    db_signals = sig_res.scalars().all()

                    signals_list = []
                    # 1. First add SignalEvidence (primary Agent 1 evidence records)
                    for ev in db_evidences:
                        obs_at = (
                            ev.published_at.isoformat()
                            if ev.published_at
                            else ev.first_observed_at.isoformat()
                            if ev.first_observed_at
                            else None
                        )
                        signals_list.append({
                            "signal_id": ev.id,
                            "type": ev.signal_type,
                            "subtype": ev.signal_subtype,
                            "observed_fact": ev.observed_fact,
                            "business_hypothesis": ev.business_hypothesis,
                            "observed_at": obs_at,
                            "source": {"url": ev.source_url, "source_type": ev.source_provider},
                            "confidence": ev.verification_status.lower() if ev.verification_status else "verified",
                        })

                    # 2. Add legacy BuyingSignal artifacts if present
                    for s in db_signals:
                        signals_list.append({
                            "signal_id": s.id,
                            "type": s.signal_type,
                            "observed_fact": s.fit_reason,
                            "observed_at": s.observed_at,
                            "source": {"url": s.evidence_url, "source_type": "database_signal"},
                            "confidence": "verified",
                        })

                    # 3. Add passed evidence from parameters if DB evidence was empty
                    if not signals_list and request.parameters.get("evidence"):
                        for pe in request.parameters["evidence"]:
                            signals_list.append({
                                "signal_id": pe.get("id") or pe.get("evidence_hash") or f"sig-{uuid.uuid4().hex[:8]}",
                                "type": pe.get("signal_type", "growth"),
                                "subtype": pe.get("signal_subtype"),
                                "observed_fact": pe.get("observed_fact", ""),
                                "business_hypothesis": pe.get("business_hypothesis", ""),
                                "observed_at": pe.get("published_at") or pe.get("first_observed_at"),
                                "source": {"url": pe.get("source_url", ""), "source_type": pe.get("source_provider", "radar")},
                                "confidence": (pe.get("verification_status") or "verified").lower(),
                            })

                    con_res = await session.execute(
                        select(Contact).where(
                            Contact.account_id == db_account.id,
                            Contact.organization_id == request.organization_id,
                        )
                    )
                    db_contacts = con_res.scalars().all()

                    contacts_list = [
                        {
                            "contact_id": c.id,
                            "first_name": c.first_name,
                            "last_name": c.last_name,
                            "full_name": f"{c.first_name} {c.last_name}",
                            "job_title": c.title,
                            "email": c.email,
                            "phone": c.phone,
                            "is_suppressed": c.is_suppressed,
                            "logical_outreach_attempts": c.logical_outreach_attempts,
                            "contact_eligibility": "eligible" if not c.is_suppressed else "suppressed",
                        }
                        for c in db_contacts
                    ]

                    why_now_text = (
                        db_account.why_now
                        or request.parameters.get("why_now_reason")
                        or (signals_list[0]["observed_fact"] if signals_list else None)
                        or "Prioritized by Signal Radar"
                    )

                    company_data = {
                        "account_id": db_account.id,
                        "company_name": db_account.name,
                        "domain": db_account.domain,
                        "industry": db_account.industry or "Technology",
                        "priority": {
                            "score": int((db_account.fit_score or 0.7) * 100),
                            "tier": "high" if (db_account.fit_score or 0) >= 0.8 else "medium",
                            "why_now": why_now_text,
                        },
                        "signals": signals_list,
                        "contacts": contacts_list,
                        "research_status": "ready",
                        "is_synthetic": False,
                    }

        if not company_data:
            return AgentExecutionResult(
                agent_id=self.agent_id,
                execution_id=execution_id,
                status=AgentStatus.TERMINAL_FAILURE,
                error_details=f"Account with ID '{account_id}' could not be located in sample fixtures or database",
            )

        # Check tenant isolation and ensure account is persisted in DB under the caller's organization
        if not db_account:
            res_acc = await session.execute(
                select(Account).where(
                    Account.id == str(account_id),
                )
            )
            other_org_acc = res_acc.scalars().first()
            if other_org_acc and other_org_acc.organization_id != request.organization_id:
                return AgentExecutionResult(
                    agent_id=self.agent_id,
                    execution_id=execution_id,
                    status=AgentStatus.TERMINAL_FAILURE,
                    error_details=f"Account '{account_id}' does not belong to organization '{request.organization_id}'",
                )
            if execution_mode == "test" and is_sample_request:
                db_account = Account(
                    id=str(account_id),
                    organization_id=request.organization_id,
                    name=company_data.get("company_name", "Sample Company"),
                    domain=company_data.get("domain", "sample.example"),
                    industry=company_data.get("industry"),
                    fit_score=float(company_data.get("priority", {}).get("score", 70)) / 100.0,
                    status="prioritized",
                )
                session.add(db_account)
                await session.flush()

        # ---------------------------------------------------------------------
        # STEP 2: Validate and Match Company Records (Prevent Duplicate Processing)
        # ---------------------------------------------------------------------
        if not company_data.get("company_name") or not company_data.get("domain"):
            return AgentExecutionResult(
                agent_id=self.agent_id,
                execution_id=execution_id,
                status=AgentStatus.TERMINAL_FAILURE,
                error_details="Company record missing essential fields (company_name or domain)",
            )

        # Check for existing pending or approved approval to prevent duplicate outreach actions
        if db_account:
            existing_appr = await session.execute(
                select(ApprovalItem).where(
                    ApprovalItem.account_id == db_account.id,
                    ApprovalItem.organization_id == request.organization_id,
                    ApprovalItem.artifact_type == "outreach_draft",
                    ApprovalItem.status.in_(["pending", "approved"]),
                )
            )
            pending_item = existing_appr.scalars().first()
            if pending_item:
                logger.info(f"Active outreach approval item already pending for account {account_id}")
                contacts = company_data.get("contacts", [])
                primary_c = contacts[0] if contacts else {}
                return AgentExecutionResult(
                    agent_id=self.agent_id,
                    execution_id=execution_id,
                    status=AgentStatus.WAITING_FOR_REVIEW,
                    structured_result={
                        "organization_id": request.organization_id,
                        "account_id": account_id,
                        "company_information": company_data,
                        "approval_id": pending_item.id,
                        "human_approval_status": "pending",
                        "processing_status": "completed_awaiting_review",
                        "selected_primary_contact": primary_c,
                        "alternative_contacts": contacts[1:],
                        "personalized_outreach_draft": {"draft_body": pending_item.draft_content},
                        "recommended_service_offering": "Enterprise Consulting & AI Solutions",
                        "buying_signal_summary": company_data.get("priority", {}),
                        "message": "Existing outreach draft is already awaiting review; duplicate creation skipped.",
                    },
                    artifact_references=[
                        ArtifactReference(
                            artifact_id=pending_item.id,
                            artifact_type="approval_item",
                            summary="Existing pending outreach approval",
                        )
                    ],
                    proposed_next_actions=["await:human_approval"],
                )

        # ---------------------------------------------------------------------
        # STEP 3 & 4: Analyze Existing Signals & Synthesize Research Brief
        # ---------------------------------------------------------------------
        signals = list(company_data.get("signals", []))
        signal_type = signals[0].get("type", "growth") if signals else "growth"
        why_now = company_data.get("priority", {}).get("why_now", "Scaling operations")

        # Production live research via Brave Search (strictly skipped in test mode or synthetic domains)
        if execution_mode == "production" and not company_data.get("is_synthetic"):
            logger.info(
                f"[Pipeline2][production] Running live company research for domain='{company_data.get('domain')}'."
            )
            brave_res = await self.brave_adapter.research_company(
                company_name=str(company_data.get("company_name", "")),
                domain=str(company_data.get("domain", "")),
                industry=str(company_data.get("industry", "")),
                mode="production",
            )
            stage_statuses["research"] = brave_res.get("status", "failed")
            if brave_res.get("error"):
                stage_statuses["research_error"] = brave_res["error"]
                logger.warning(
                    f"[Pipeline2][production] Live research degraded for '{account_id}': {brave_res['error']}"
                )
            existing_urls = {
                str((s.get("source") or {}).get("url") or "").strip().lower() for s in signals
            }
            for new_sig in brave_res.get("signals", []):
                sig_url = str((new_sig.get("source") or {}).get("url") or "").strip().lower()
                if not sig_url or sig_url not in existing_urls:
                    signals.append(new_sig)
                    if sig_url:
                        existing_urls.add(sig_url)
            company_data["signals"] = signals
        else:
            stage_statuses["research"] = "test_mode_existing_signals"

        facts, hypotheses, sources, raw_evidence_refs = self.analyzer.synthesize_research_brief(company_data)

        # Persist ResearchBrief if DB account is present
        brief_id = f"brief-{uuid.uuid4().hex[:12]}"
        if db_account:
            brief = ResearchBrief(
                organization_id=request.organization_id,
                account_id=db_account.id,
                summary=f"Grounded enterprise research for {company_data.get('company_name')}",
                facts=facts,
                hypotheses=hypotheses,
                stakeholders={"contacts_evaluated": len(company_data.get("contacts", []))},
                sources=sources,
                version=1,
            )
            session.add(brief)
            await session.flush()
            brief_id = brief.id

        # ---------------------------------------------------------------------
        # STEP 5 & 6: Identify Contacts & Select Appropriate Decision-Maker
        # ---------------------------------------------------------------------
        contacts = list(company_data.get("contacts", []))

        # Production live enrichment via Apollo (strictly skipped in test mode or synthetic domains)
        if execution_mode == "production" and not company_data.get("is_synthetic"):
            domain = str(company_data.get("domain", ""))
            logger.info(f"[Pipeline2][production] Running Apollo enrichment for domain='{domain}'.")
            try:
                org_info = await self.apollo_adapter.enrich_organization(domain, mode="production")
                if org_info:
                    if not company_data.get("industry") and org_info.get("industry"):
                        company_data["industry"] = org_info["industry"]
                        if db_account and not db_account.industry:
                            db_account.industry = org_info["industry"]
                    if org_info.get("estimated_num_employees") and db_account and not db_account.employee_count:
                        db_account.employee_count = int(org_info["estimated_num_employees"])
            except Exception as org_err:
                logger.warning(f"[Pipeline2][production] Apollo org enrichment failed: {str(org_err)}")

            has_eligible_contact = any(
                (c.get("email") or c.get("phone")) and not c.get("is_suppressed", False)
                for c in contacts
            )
            if not has_eligible_contact or request.parameters.get("force_apollo_enrichment"):
                try:
                    target_titles = self.analyzer.get_target_role_titles(signal_type, why_now)
                    apollo_contacts = await self.apollo_adapter.search_contacts(
                        domain=domain,
                        role_titles=target_titles,
                        limit=5,
                        mode="production",
                    )
                    existing_emails = {
                        str(c.get("email") or "").strip().lower() for c in contacts if c.get("email")
                    }
                    existing_ids = {
                        str(c.get("contact_id") or c.get("id") or "") for c in contacts
                    }
                    added_count = 0
                    for ac in apollo_contacts:
                        ac_email = str(ac.get("email") or "").strip().lower()
                        ac_id = str(ac.get("contact_id") or "")
                        if (ac_email and ac_email in existing_emails) or (ac_id and ac_id in existing_ids):
                            continue
                        # Persist newly discovered contact into DB to prevent duplicates & track attempts
                        if db_account:
                            existing_db_contact = None
                            if ac_email:
                                db_c_res = await session.execute(
                                    select(Contact).where(
                                        Contact.account_id == db_account.id,
                                        Contact.email == ac_email,
                                    )
                                )
                                existing_db_contact = db_c_res.scalars().first()
                            if existing_db_contact:
                                ac["contact_id"] = existing_db_contact.id
                            else:
                                new_db_contact = Contact(
                                    organization_id=request.organization_id,
                                    account_id=db_account.id,
                                    first_name=ac.get("first_name") or "Decision",
                                    last_name=ac.get("last_name") or "Maker",
                                    email=ac_email or None,
                                    phone=ac.get("phone"),
                                    title=ac.get("job_title"),
                                    is_suppressed=False,
                                    logical_outreach_attempts=0,
                                )
                                session.add(new_db_contact)
                                await session.flush()
                                ac["contact_id"] = new_db_contact.id
                        contacts.append(ac)
                        if ac_email:
                            existing_emails.add(ac_email)
                        if ac.get("contact_id"):
                            existing_ids.add(str(ac["contact_id"]))
                        added_count += 1
                    company_data["contacts"] = contacts
                    stage_statuses["enrichment"] = f"completed_added_{added_count}"
                    logger.info(
                        f"[Pipeline2][production] Apollo enrichment added {added_count} new contacts for '{domain}'."
                    )
                except Exception as apollo_err:
                    stage_statuses["enrichment"] = "failed"
                    stage_statuses["enrichment_error"] = str(apollo_err)
                    logger.warning(
                        f"[Pipeline2][production] Apollo contact enrichment failed for '{domain}': {str(apollo_err)}"
                    )
            else:
                stage_statuses["enrichment"] = "reused_existing_db_contacts"
        else:
            stage_statuses["enrichment"] = "test_mode_existing_contacts"

        # If a specific contact_id was requested, find it
        target_contact = None
        if contact_id:
            for c in contacts:
                if str(c.get("contact_id")) == str(contact_id) or str(c.get("id")) == str(contact_id):
                    target_contact = c
                    break

        if target_contact:
            primary_contact = target_contact
            alternatives = [c for c in contacts if c != target_contact]
            selection_rationale = f"Selected requested contact ID: {contact_id}"
        else:
            primary_contact, alternatives, selection_rationale = self.analyzer.rank_and_select_contact(
                contacts, signal_type, why_now
            )

        # Handle missing or incomplete contact details safely
        if not primary_contact:
            return AgentExecutionResult(
                agent_id=self.agent_id,
                execution_id=execution_id,
                status=AgentStatus.WAITING_FOR_INPUT,
                structured_result={
                    "organization_id": request.organization_id,
                    "account_id": account_id,
                    "company_information": company_data,
                    "buying_signal_summary": {"signal_type": signal_type, "why_now": why_now},
                    "research_findings": {"facts": facts, "hypotheses": hypotheses, "sources": sources},
                    "selected_primary_contact": None,
                    "alternative_contacts": [],
                    "contact_verification_and_eligibility_status": "missing_contacts",
                    "business_opportunity_analysis": None,
                    "recommended_service_offering": None,
                    "personalized_outreach_draft": None,
                    "optional_demo_recommendation_or_reference": None,
                    "human_approval_status": "not_created",
                    "processing_status": "waiting_for_contact_info",
                    "error_details": "No eligible decision-maker contacts found for account.",
                },
                proposed_next_actions=["enrich_contacts_with_apollo"],
                error_details="No matching decision-maker contacts available.",
            )

        # ---------------------------------------------------------------------
        # Compliance & Eligibility: Check Suppression & Attempt Accounting
        # ---------------------------------------------------------------------
        suppression_service = SuppressionService(session)
        attempt_service = AttemptTrackingService(session)

        c_email = primary_contact.get("email")
        c_phone = primary_contact.get("phone")
        c_id = primary_contact.get("contact_id") or primary_contact.get("id")

        if await suppression_service.is_contact_suppressed(email=c_email, phone=c_phone, contact_id=c_id):
            return AgentExecutionResult(
                agent_id=self.agent_id,
                execution_id=execution_id,
                status=AgentStatus.BLOCKED,
                structured_result={
                    "organization_id": request.organization_id,
                    "account_id": account_id,
                    "company_information": company_data,
                    "selected_primary_contact": primary_contact,
                    "contact_verification_and_eligibility_status": "suppressed",
                    "processing_status": "blocked",
                    "error_details": "Contact is listed in suppression registry. Outreach strictly forbidden.",
                },
                error_details="Contact is in suppression registry. Outreach strictly halted.",
            )

        # Check if contact is missing all communication methods and marked blocked
        if primary_contact.get("contact_eligibility") == "blocked_missing_address" and not c_email and not c_phone:
            return AgentExecutionResult(
                agent_id=self.agent_id,
                execution_id=execution_id,
                status=AgentStatus.BLOCKED,
                structured_result={
                    "organization_id": request.organization_id,
                    "account_id": account_id,
                    "company_information": company_data,
                    "selected_primary_contact": primary_contact,
                    "contact_verification_and_eligibility_status": "blocked_missing_address",
                    "processing_status": "blocked",
                    "error_details": "Contact lacks email and phone address. Outreach cannot be dispatched.",
                },
                error_details="Primary contact lacks valid address methods.",
            )

        # Attempt accounting: rule of 3
        if c_id and not company_data.get("is_synthetic"):
            logical_attempts = await attempt_service.get_logical_attempts(str(c_id))
            if logical_attempts >= 3:
                return AgentExecutionResult(
                    agent_id=self.agent_id,
                    execution_id=execution_id,
                    status=AgentStatus.BLOCKED,
                    structured_result={
                        "organization_id": request.organization_id,
                        "account_id": account_id,
                        "selected_primary_contact": primary_contact,
                        "contact_verification_and_eligibility_status": "max_attempts_exceeded",
                        "processing_status": "blocked",
                        "error_details": "Maximum 3 logical attempts reached without response. 4th attempt forbidden.",
                    },
                    error_details="Max 3 logical outreach attempts reached without reply. 4th attempt forbidden.",
                )

        # ---------------------------------------------------------------------
        # STEP 7: Analyze Business Opportunity (LLM Integration)
        # ---------------------------------------------------------------------
        logger.info(
            f"[Pipeline2][{execution_mode}] Running LLM opportunity analysis for account_id='{account_id}'."
        )
        opportunity_analysis = await self.analyzer.generate_opportunity_analysis(
            company_data=company_data,
            selected_contact=primary_contact,
            facts=facts,
            hypotheses=hypotheses,
            mode=execution_mode,
        )
        stage_statuses["llm_analysis"] = "completed"

        # ---------------------------------------------------------------------
        # STEP 8: Decide Whether a Demo Is Needed
        # ---------------------------------------------------------------------
        include_demo_param = request.parameters.get("include_demo")
        if include_demo_param is False:
            justifies_demo, demo_template = False, None
        elif include_demo_param is True:
            justifies_demo, demo_template = True, "enterprise_sales_automation_v1"
        else:
            justifies_demo, demo_template = self.analyzer.evaluate_demo_suitability(
                company_data, opportunity_analysis
            )
        demo_reference: Optional[Dict[str, Any]] = None

        if justifies_demo:
            try:
                # If a DB account exists, invoke the real Demo Agent safely
                if db_account:
                    demo_req = AgentExecutionRequest(
                        agent_id="demo_before_hello",
                        organization_id=request.organization_id,
                        account_id=db_account.id,
                        correlation_id=request.correlation_id,
                        parameters={"template_name": demo_template},
                    )
                    demo_res = await self.demo_agent.execute(demo_req, session)
                    if demo_res.status == AgentStatus.COMPLETED:
                        demo_reference = demo_res.structured_result
                else:
                    # Synthetic / Mock adapter demo environment
                    demo_reference = {
                        "demo_id": f"demo-synth-{account_id}",
                        "access_url": "https://marketplace.adople.ai/",
                        "expires_at": "2026-11-24T12:00:00Z",
                        "template_name": demo_template,
                        "is_validated": True,
                    }
            except Exception as e:
                logger.warning(f"Demo generation encountered exception: {str(e)}. Proceeding without demo.")
                demo_reference = None

        # ---------------------------------------------------------------------
        # STEP 9 & 10: Generate and Validate Personalized Outreach Draft
        # ---------------------------------------------------------------------
        outreach_draft = self.analyzer.generate_personalized_outreach_draft(
            company_data=company_data,
            selected_contact=primary_contact,
            opportunity_analysis=opportunity_analysis,
            demo_reference=demo_reference,
        )
        stage_statuses["outreach_draft"] = "completed"

        # ---------------------------------------------------------------------
        # STEP 11: Save for Human Approval (Never auto-send before human review)
        # ---------------------------------------------------------------------
        approval_id = f"appr-{uuid.uuid4().hex[:12]}"
        if db_account:
            approval = ApprovalItem(
                organization_id=request.organization_id,
                account_id=db_account.id,
                contact_id=primary_contact.get("contact_id") or primary_contact.get("id"),
                artifact_type="outreach_draft",
                artifact_id=brief_id,
                requested_action="send_outreach",
                draft_content=outreach_draft["draft_body"],
                source_evidence={
                    "facts": facts,
                    "hypotheses": hypotheses,
                    "sources": sources,
                    "subject": outreach_draft.get("subject"),
                    "recipient_email": outreach_draft.get("recipient_email"),
                    "recipient_name": outreach_draft.get("recipient_name"),
                    "execution_mode": execution_mode,
                },
                risk_flags=["pending_sales_rep_review"],
                status="pending",
            )
            session.add(approval)
            await session.flush()
            approval_id = approval.id
            logger.info(
                f"[Pipeline2][{execution_mode}] Created approval_id='{approval_id}' "
                f"for account_id='{account_id}' awaiting human review."
            )

        # ---------------------------------------------------------------------
        # STEP 12: Complete Pipeline 2 Processing and Assemble Structured Output
        # ---------------------------------------------------------------------
        evidence_references = [
            EvidenceReference(
                source_url=ref["source_url"],
                source_type=ref["source_type"],
                excerpt=ref["excerpt"],
                confidence=ref["confidence"],
            )
            for ref in raw_evidence_refs
        ]

        artifact_references = [
            ArtifactReference(
                artifact_id=brief_id,
                artifact_type="research_brief",
                summary=f"Research brief for {company_data.get('company_name')}",
            ),
            ArtifactReference(
                artifact_id=approval_id,
                artifact_type="approval_item",
                summary="Personalized outreach draft awaiting review",
            ),
        ]
        if demo_reference and demo_reference.get("demo_id"):
            artifact_references.append(
                ArtifactReference(
                    artifact_id=demo_reference["demo_id"],
                    artifact_type="demo_artifact",
                    summary="Validated synthetic demo environment",
                )
            )

        structured_output: Dict[str, Any] = {
            "organization_id": request.organization_id,
            "account_id": account_id,
            "company_information": company_data,
            "buying_signal_summary": {
                "signal_type": signal_type,
                "why_now": why_now,
                "observed_facts": facts.get("observed_signals", []),
            },
            "research_findings": {
                "brief_id": brief_id,
                "facts": facts,
                "hypotheses": hypotheses,
                "sources": sources,
            },
            "evidence_references": [e.model_dump() for e in evidence_references],
            "selected_primary_contact": primary_contact,
            "alternative_contacts": alternatives,
            "contact_verification_and_eligibility_status": primary_contact.get(
                "verification_status", "synthetic_only"
            ),
            "business_opportunity_analysis": opportunity_analysis,
            "recommended_service_offering": opportunity_analysis.get("relevant_service_offering"),
            "personalized_outreach_draft": outreach_draft,
            "optional_demo_recommendation_or_reference": demo_reference,
            "human_approval_status": "pending",
            "approval_id": approval_id,
            "processing_status": "completed_awaiting_review",
            "selection_rationale": selection_rationale,
            "is_synthetic_test_data": company_data.get("is_synthetic", False),
            "execution_mode": execution_mode,
            "stage_statuses": stage_statuses,
            "error_details": None,
        }

        return AgentExecutionResult(
            agent_id=self.agent_id,
            execution_id=execution_id,
            status=AgentStatus.WAITING_FOR_REVIEW,
            structured_result=structured_output,
            artifact_references=artifact_references,
            evidence_references=evidence_references,
            uncertainty=0.10,
            proposed_next_actions=["await:human_approval", "optional:demo_preview"],
        )

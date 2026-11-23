"""Standalone script to execute Pipeline 2 with the sample JSON fixtures."""

import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.app.db.base import Base
from backend.app.db.session import AsyncSessionLocal, engine
from backend.app.models.identity import Organization
from backend.app.workflows.definitions import PlatformWorkflows


async def run_pipeline2_demo():
    print("=" * 80)
    print(" PIPELINE 2: RESEARCH & PERSONAL OUTREACH AGENT - SAMPLE RUN")
    print("=" * 80)

    # Ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # Prefer the primary seeded organization (acme-corp) to match API & platform users
        from sqlalchemy import select
        res = await session.execute(select(Organization).where(Organization.slug == "acme-corp"))
        org = res.scalars().first()
        if not org:
            res = await session.execute(select(Organization).where(Organization.slug == "org-demo-001"))
            org = res.scalars().first()
        if not org:
            org = Organization(name="Demo Org", slug="org-demo-001", is_active=True)
            session.add(org)
            await session.flush()

        workflows = PlatformWorkflows(session)
        account_ids = ["ACC-001", "ACC-002", "ACC-003"]

        print(f"\nProcessing {len(account_ids)} sample accounts through Pipeline 2...\n")

        for acc_id in account_ids:
            print(f">>> Running Workflow for {acc_id}...")
            wf_run = await workflows.run_research_outreach(
                organization_id=org.id,
                account_id=acc_id,
                parameters={"use_sample_data": True},
            )
            await session.commit()

            res_data = wf_run.state_data.get("result", {}) or {}
            company_info = res_data.get("company_information", {}) or {}
            contact = res_data.get("selected_primary_contact", {}) or {}
            draft = res_data.get("personalized_outreach_draft", {}) or {}
            demo = res_data.get("optional_demo_recommendation_or_reference")
            buying_summary = res_data.get("buying_signal_summary", {}) or {}

            print("-" * 80)
            print(f"Account:         {acc_id} | {company_info.get('company_name', 'N/A')} ({company_info.get('domain', 'N/A')})")
            print(f"Industry:        {company_info.get('industry', 'N/A')}")
            print(f"Buying Signal:   {buying_summary.get('signal_type', 'N/A')} - {buying_summary.get('why_now', 'N/A')}")
            print(f"Primary Contact: {contact.get('full_name', 'N/A')} | Title: {contact.get('job_title', 'N/A')}")
            print(f"Contact Email:   {contact.get('email', 'N/A')} | Eligibility: {contact.get('contact_eligibility', 'N/A')}")
            alts = [c.get('full_name') for c in (res_data.get('alternative_contacts') or []) if isinstance(c, dict)]
            print(f"Alternatives:    {alts}")
            print(f"Offering:        {res_data.get('recommended_service_offering')}")
            demo_str = f"YES ({demo.get('access_url')})" if (demo and isinstance(demo, dict) and demo.get("access_url")) else "NO (Direct Outreach)"
            print(f"Demo Attached:   {demo_str}")
            print(f"Approval Status: {res_data.get('human_approval_status')} (Approval ID: {res_data.get('approval_id')})")
            print(f"Workflow State:  Step: {wf_run.current_step} | Status: {wf_run.status}")
            print("\nGenerated Outreach Draft:")
            print(f"  \"{draft.get('draft_body')}\"")
            print("-" * 80 + "\n")

    print("Pipeline 2 sample run completed successfully.")


if __name__ == "__main__":
    asyncio.run(run_pipeline2_demo())

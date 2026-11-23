"""Marketplace Product Service for marketplace.adople.ai product catalog."""

import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.sales import MarketplaceProduct

logger = logging.getLogger(__name__)

# Predefined catalog for marketplace.adople.ai products
MARKETPLACE_PRODUCTS_SEED: List[Dict[str, Any]] = [
    {
        "name": "Adople Voice Agent",
        "slug": "voice-agent",
        "product_url": "https://marketplace.adople.ai/products/voice-agent",
        "category": "Voice AI & Customer Interaction",
        "overview": "Autonomous voice AI agent capable of conducting natural, human-like conversations in real-time, resolving inquiries, and integrating directly into enterprise CRM and ticketing systems.",
        "key_features": [
            "Sub-second speech processing latency for natural conversations",
            "Human-like inflection with dynamic objection handling",
            "Direct bidirectional CRM and ticketing updates during live calls",
            "Multi-language support with enterprise telephony SIP/VoIP integration",
        ],
        "demo_video_url": "https://marketplace.adople.ai/",
        "target_pain_points": [
            "High call center operational overhead and rising per-call costs",
            "Long customer wait times and high phone call drop rates",
            "Difficulty scaling live telephonic support across multiple timezones",
            "Manual, time-consuming post-call data logging and notes entry",
        ],
        "target_roles": [
            "Head of Customer Support",
            "VP Customer Experience",
            "Chief Operating Officer",
            "Director of Support Operations",
        ],
    },
    {
        "name": "TeleCalling Agent",
        "slug": "telecalling-agent",
        "product_url": "https://marketplace.adople.ai/products/telecalling-agent",
        "category": "Outbound Sales & Telecalling",
        "overview": "Enterprise-grade autonomous outbound calling agent designed to conduct outbound sales outreach, follow up on warm leads, qualify prospects, and book calendar appointments automatically.",
        "key_features": [
            "Autonomous outbound dialer with conversational qualifying",
            "Automated calendar booking and appointment synchronization",
            "Real-time call transcription and automated disposition scoring",
            "Strict compliance filtering with Do-Not-Call (DNC) registry checks",
        ],
        "demo_video_url": "https://marketplace.adople.ai/",
        "target_pain_points": [
            "Low outbound SDR connect rates and repetitive manual dialing",
            "High burn rate hiring and training telecalling representatives",
            "Delayed follow-up on inbound demo requests leading to lost deals",
            "Inconsistent script delivery and qualification quality across reps",
        ],
        "target_roles": [
            "VP of Sales",
            "Head of Business Development",
            "Director of Inside Sales",
            "Chief Revenue Officer",
        ],
    },
    {
        "name": "Agentic Document Extraction",
        "slug": "document-extraction",
        "product_url": "https://marketplace.adople.ai/products/document-extraction",
        "category": "Intelligent Document Processing (IDP)",
        "overview": "Advanced document intelligence engine that ingests unstructured PDFs, invoices, medical records, and faxes to extract verified, structured data with zero manual data entry.",
        "key_features": [
            "99.4% precision on multi-format tables and nested document structures",
            "Automated schema mapping directly into ERP and billing systems",
            "HIPAA & SOC2 compliant private data processing pipelines",
            "Instant automated validation with human-in-the-loop exception review",
        ],
        "demo_video_url": "https://marketplace.adople.ai/",
        "target_pain_points": [
            "Manual data entry backlogs from paper forms, faxes, and invoices",
            "High error rates and costly billing corrections in claims processing",
            "Multi-day document turnaround times bottlenecking fulfillment",
            "Siloed, non-searchable document archives that slow down audits",
        ],
        "target_roles": [
            "Head of Document Operations",
            "VP Operations",
            "Chief Information Officer",
            "Director of Finance Operations",
        ],
    },
    {
        "name": "Document Analysis & Search (Enterprise RAG)",
        "slug": "document-analysis",
        "product_url": "https://marketplace.adople.ai/products/document-analysis",
        "category": "Enterprise Knowledge Retrieval & Compliance",
        "overview": "Intelligent enterprise RAG search platform allowing teams to query thousands of contracts, compliance manuals, SOPs, and technical runbooks with exact sentence-level source citations.",
        "key_features": [
            "Sub-second semantic search across multi-depot files and contracts",
            "Exact sentence-level citation and verifiable audit provenance",
            "Role-based access control (RBAC) ensuring strict data segregation",
            "Automated policy mismatch and regulatory clause change detection",
        ],
        "demo_video_url": "https://marketplace.adople.ai/",
        "target_pain_points": [
            "Employees spending hours searching for company SOPs and procedures",
            "Severe knowledge silos across distributed regional teams",
            "Compliance risks stemming from employees using outdated policy files",
            "Difficulty auditing lengthy vendor and client contracts",
        ],
        "target_roles": [
            "Chief Information Officer",
            "Head of Compliance",
            "General Counsel",
            "VP of Operations",
        ],
    },
    {
        "name": "Agentic Data Analyst",
        "slug": "data-analyst",
        "product_url": "https://marketplace.adople.ai/products/data-analyst",
        "category": "Autonomous Business Intelligence & Analytics",
        "overview": "Autonomous data science assistant that connects directly to enterprise databases and data lakes to answer executive questions, build visual charts, and forecast trends conversationally.",
        "key_features": [
            "Natural language to SQL generation grounded in your schema",
            "Instant dynamic chart and interactive dashboard generation",
            "Proactive anomaly detection across operational and revenue metrics",
            "Self-correcting query execution guarded by safety parameters",
        ],
        "demo_video_url": "https://marketplace.adople.ai/",
        "target_pain_points": [
            "Executive and management backlog waiting on data engineering teams",
            "Slow monthly and quarterly reporting cycles delaying strategic decisions",
            "Inability for non-technical leadership to explore operational data",
            "Fragmented metrics across disparate SaaS and database silos",
        ],
        "target_roles": [
            "Chief Financial Officer",
            "VP Analytics",
            "Director of Business Intelligence",
            "Chief Operating Officer",
        ],
    },
    {
        "name": "GTM Automation",
        "slug": "gtm-automation",
        "product_url": "https://marketplace.adople.ai/products/gtm-automation",
        "category": "Go-To-Market & Revenue Acceleration",
        "overview": "End-to-end autonomous go-to-market engine that continuously monitors buying signals, enriches accounts, coordinates personalized multi-channel outreach, and keeps sales pipelines full.",
        "key_features": [
            "Real-time buying signal and market expansion radar",
            "Automated multi-contact persona discovery and email verification",
            "Dynamic personalized cold outreach generation without generic templates",
            "Seamless CRM synchronization and campaign attribution tracking",
        ],
        "demo_video_url": "https://marketplace.adople.ai/",
        "target_pain_points": [
            "Unpredictable outbound pipeline and cold lead burnout",
            "High customer acquisition costs (CAC) with low response rates",
            "Sales reps wasting 70% of their workday on manual prospect research",
            "Generic outreach blasts resulting in domain reputation penalties",
        ],
        "target_roles": [
            "Chief Revenue Officer",
            "VP Marketing",
            "Head of Growth",
            "VP Sales",
        ],
    },
    {
        "name": "SEC Analysis & Financial Document AI",
        "slug": "sec-analysis",
        "product_url": "https://marketplace.adople.ai/products/sec-analysis",
        "category": "Financial Intelligence & Regulatory Filings",
        "overview": "Specialized financial intelligence agent that monitors 10-K, 10-Q, 8-K filings, earnings transcripts, and regulatory disclosures to extract balance sheet risks and strategic shifts.",
        "key_features": [
            "Automated balance sheet and financial statement reconciliation",
            "Risk factor delta tracking between quarterly regulatory filings",
            "Earnings call transcript tone analysis and executive stance extraction",
            "Exportable valuation models and audit-ready data tables",
        ],
        "demo_video_url": "https://marketplace.adople.ai/",
        "target_pain_points": [
            "Manual parsing of dense 200+ page quarterly regulatory filings",
            "Missing critical risk factor revisions in competitor filings",
            "Delayed financial analysis for investment and credit decisions",
            "High audit preparation and external consultant costs",
        ],
        "target_roles": [
            "Chief Financial Officer",
            "VP Investor Relations",
            "Head of Risk & Compliance",
            "Managing Director of Research",
        ],
    },
    {
        "name": "Radiology AI / Clinical Imaging Assistant",
        "slug": "radiology-ai",
        "product_url": "https://marketplace.adople.ai/products/radiology-ai",
        "category": "Healthcare & Clinical Imaging Intelligence",
        "overview": "Domain-specific clinical AI assistant built to pre-screen medical imaging (X-rays, CT scans, MRIs), detect critical triage anomalies, and draft preliminary structured radiology impressions.",
        "key_features": [
            "FDA-aligned DICOM image pre-screening and priority triage",
            "Real-time alerts for acute critical findings in emergency settings",
            "Automated structured report drafting with standardized terminology",
            "HIPAA-compliant, private cloud or on-premise execution architecture",
        ],
        "demo_video_url": "https://marketplace.adople.ai/",
        "target_pain_points": [
            "Radiologist burnout and massive scan backlogs delaying diagnosis",
            "Emergency room delays when waiting for preliminary imaging reads",
            "Severe clinical staffing shortages across regional imaging centers",
            "Inconsistent report formatting complicating care team handoffs",
        ],
        "target_roles": [
            "Chief Medical Officer",
            "Director of Radiology",
            "VP of Clinical Technology",
            "Chief Information Officer",
        ],
    },
    {
        "name": "Treasury Ask (Cash & Liquidity Management)",
        "slug": "treasury-ask",
        "product_url": "https://marketplace.adople.ai/products/treasury-ask",
        "category": "Treasury & Liquidity Automation",
        "overview": "Autonomous treasury management platform that aggregates accounts across global banking partners to forecast daily cash positions, automate sweeps, and optimize working capital.",
        "key_features": [
            "Real-time cash balance aggregation across multi-national banking portals",
            "AI-driven 13-week rolling cash flow forecasting",
            "Automated liquidity sweeps and yield optimization recommendations",
            "Instant detection of banking fee discrepancies and FX variances",
        ],
        "demo_video_url": "https://marketplace.adople.ai/",
        "target_pain_points": [
            "Fragmented cash visibility across disconnected banking logins",
            "Inaccurate manual Excel cash flow forecasting prone to errors",
            "Idle cash losing out on interest yields due to delayed transfers",
            "Risk of unexpected liquidity shortfalls and costly credit line draws",
        ],
        "target_roles": [
            "Corporate Treasurer",
            "Chief Financial Officer",
            "VP Finance",
            "Director of Treasury Operations",
        ],
    },
    {
        "name": "Buddy AI & Audit Support",
        "slug": "buddy-ai",
        "product_url": "https://marketplace.adople.ai/products/buddy-ai",
        "category": "IT Governance, HR & SOC2 Audit Automation",
        "overview": "Autonomous employee enablement and security compliance assistant that automates IT/HR service requests and autonomously gathers continuous evidence for SOC2, ISO 27001, and HIPAA audits.",
        "key_features": [
            "Autonomous IT and HR ticket resolution with verified runbook actions",
            "Continuous audit evidence collection from cloud providers and GitHub",
            "Automated quarterly access reviews and permission lifecycle tracking",
            "Role-based contextual employee assistant with strict privacy gates",
        ],
        "demo_video_url": "https://marketplace.adople.ai/",
        "target_pain_points": [
            "IT helpdesk flooded with repetitive access and password tickets",
            "SOC2 and ISO 27001 audit preparation consuming weeks of engineering time",
            "Delayed new employee onboarding and manual software provisioning",
            "Human error in access revocation audits posing security risks",
        ],
        "target_roles": [
            "Chief Information Security Officer (CISO)",
            "Head of IT",
            "VP Engineering",
            "Director of Compliance",
        ],
    },
]


class MarketplaceService:
    """Service to manage marketplace products, scraping, and lead-to-product matching."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def ensure_catalog_seeded(self) -> List[MarketplaceProduct]:
        """Ensure all 10 marketplace products exist in the database."""
        res = await self.session.execute(select(MarketplaceProduct))
        existing = res.scalars().all()
        existing_slugs = {p.slug for p in existing}

        added = []
        for item in MARKETPLACE_PRODUCTS_SEED:
            if item["slug"] not in existing_slugs:
                prod = MarketplaceProduct(
                    id=f"prod-{uuid.uuid4().hex[:8]}",
                    name=item["name"],
                    slug=item["slug"],
                    product_url=item["product_url"],
                    category=item["category"],
                    overview=item["overview"],
                    key_features=json.dumps(item["key_features"]),
                    demo_video_url=item["demo_video_url"],
                    target_pain_points=json.dumps(item["target_pain_points"]),
                    target_roles=json.dumps(item["target_roles"]),
                )
                self.session.add(prod)
                added.append(prod)

        if added:
            await self.session.commit()
            logger.info(f"[MarketplaceService] Seeded {len(added)} products from marketplace.adople.ai")

        res_final = await self.session.execute(select(MarketplaceProduct))
        return list(res_final.scalars().all())

    async def list_products(self) -> List[Dict[str, Any]]:
        """List all products formatted as dictionary."""
        products = await self.ensure_catalog_seeded()
        return [self._format_product(p) for p in products]

    async def get_product_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        """Fetch a single product by slug."""
        await self.ensure_catalog_seeded()
        res = await self.session.execute(
            select(MarketplaceProduct).where(MarketplaceProduct.slug == slug)
        )
        prod = res.scalars().first()
        return self._format_product(prod) if prod else None

    async def match_product_for_lead(
        self,
        company_pain_points: List[str],
        industry: Optional[str] = None,
        job_title: Optional[str] = None,
        business_requirements: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Intelligently match the best marketplace product based on company pain points,
        industry, business requirements, and contact role.
        """
        products = await self.ensure_catalog_seeded()
        if not products:
            return self._format_product(None)

        best_score = -1
        best_product = products[0]

        combined_text = " ".join([
            " ".join(company_pain_points or []),
            industry or "",
            job_title or "",
            business_requirements or "",
        ]).lower()

        for p in products:
            score = 0
            # 1. Match against target pain points
            try:
                pps = json.loads(p.target_pain_points or "[]")
            except Exception:
                pps = []
            for pp in pps:
                for token in pp.lower().split():
                    if len(token) > 4 and token in combined_text:
                        score += 3

            # 2. Match against target roles
            try:
                roles = json.loads(p.target_roles or "[]")
            except Exception:
                roles = []
            if job_title:
                jt_clean = job_title.lower()
                for r in roles:
                    if r.lower() in jt_clean or any(word in jt_clean for word in r.lower().split() if len(word) > 4):
                        score += 4

            # 3. Domain/Industry specific boosts
            cat = p.category.lower()
            name = p.name.lower()
            if industry:
                ind = industry.lower()
                if ("health" in ind or "medical" in ind or "clinical" in ind) and ("radiology" in name or "document" in name or "health" in cat):
                    score += 5
                elif ("logistics" in ind or "transport" in ind or "supply" in ind or "warehouse" in ind) and ("document" in name or "telecalling" in name or "voice" in name or "operations" in cat):
                    score += 5
                elif ("finance" in ind or "invest" in ind or "bank" in ind) and ("treasury" in name or "sec" in name or "analyst" in name or "financial" in cat):
                    score += 5

            if score > best_score:
                best_score = score
                best_product = p

        return self._format_product(best_product)

    async def sync_from_url(self, url: str) -> Dict[str, Any]:
        """
        Extract product details from a marketplace URL and store in the database.
        """
        clean_url = url.strip()
        slug_match = re.search(r"/products?/([a-zA-Z0-9_\-]+)", clean_url)
        slug = slug_match.group(1).lower() if slug_match else f"prod-{uuid.uuid4().hex[:6]}"

        # Attempt fetch
        title = None
        overview = None
        key_features = []
        video_url = clean_url

        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                resp = await client.get(clean_url)
                if resp.status_code == 200:
                    html = resp.text
                    # Extract title tag
                    title_m = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE)
                    if title_m:
                        title = title_m.group(1).split("|")[0].split("-")[0].strip()
                    # Extract description meta tag
                    desc_m = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)["\']', html, re.IGNORECASE)
                    if desc_m:
                        overview = desc_m.group(1).strip()
                    # Look for video links (youtube, vimeo, mp4, etc.)
                    video_m = re.search(r'(https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|vimeo\.com/)[a-zA-Z0-9_\-]+)', html)
                    if video_m:
                        video_url = video_m.group(1)
        except Exception as e:
            logger.warning(f"[MarketplaceService] Live fetch failed for {clean_url}: {str(e)}. Using catalog mapping.")

        # Match against seed if not fully parsed from HTML
        seed_match = next((s for s in MARKETPLACE_PRODUCTS_SEED if s["slug"] == slug), None)
        if seed_match:
            title = title or seed_match["name"]
            overview = overview or seed_match["overview"]
            key_features = seed_match["key_features"]
            video_url = seed_match["demo_video_url"]
            category = seed_match["category"]
            target_pps = seed_match["target_pain_points"]
            target_roles = seed_match["target_roles"]
        else:
            title = title or f"Adople {slug.replace('-', ' ').title()}"
            overview = overview or "Autonomous enterprise AI agent available on marketplace.adople.ai to accelerate operational throughput."
            key_features = ["Autonomous multi-step execution", "Grounded enterprise data privacy", "Seamless CRM and ERP integrations"]
            category = "Enterprise AI Solutions"
            target_pps = ["Manual operational bottlenecks", "High administrative overhead"]
            target_roles = ["Chief Operating Officer", "VP Technology", "Director of Operations"]

        # Upsert in DB
        res = await self.session.execute(
            select(MarketplaceProduct).where(MarketplaceProduct.slug == slug)
        )
        existing = res.scalars().first()

        if existing:
            existing.name = title
            existing.product_url = clean_url
            existing.overview = overview
            existing.category = category
            existing.key_features = json.dumps(key_features)
            existing.demo_video_url = video_url
            existing.target_pain_points = json.dumps(target_pps)
            existing.target_roles = json.dumps(target_roles)
            product_obj = existing
        else:
            product_obj = MarketplaceProduct(
                id=f"prod-{uuid.uuid4().hex[:8]}",
                name=title,
                slug=slug,
                product_url=clean_url,
                category=category,
                overview=overview,
                key_features=json.dumps(key_features),
                demo_video_url=video_url,
                target_pain_points=json.dumps(target_pps),
                target_roles=json.dumps(target_roles),
            )
            self.session.add(product_obj)

        await self.session.commit()
        await self.session.refresh(product_obj)
        return self._format_product(product_obj)

    def _format_product(self, prod: Optional[MarketplaceProduct]) -> Dict[str, Any]:
        """Convert MarketplaceProduct model to serializable dictionary."""
        if not prod:
            return {
                "product_id": "prod-default",
                "name": "Adople Enterprise AI Platform",
                "slug": "enterprise-platform",
                "product_url": "https://marketplace.adople.ai/",
                "category": "Enterprise Automation",
                "overview": "Autonomous AI agent platform designed to streamline complex enterprise workflows and accelerate turnaround times.",
                "key_features": [
                    "Context-aware workflow automation",
                    "Grounded verifiable data security",
                    "Seamless ERP, CRM, and communication integrations",
                ],
                "demo_video_url": "https://marketplace.adople.ai/",
                "target_pain_points": ["Manual workflow bottlenecks", "High operational overhead"],
                "target_roles": ["Executive Leadership", "VP Operations"],
            }

        try:
            feats = json.loads(prod.key_features or "[]")
        except Exception:
            feats = []

        try:
            pps = json.loads(prod.target_pain_points or "[]")
        except Exception:
            pps = []

        try:
            roles = json.loads(prod.target_roles or "[]")
        except Exception:
            roles = []

        return {
            "product_id": prod.id,
            "name": prod.name,
            "slug": prod.slug,
            "product_url": prod.product_url,
            "category": prod.category,
            "overview": prod.overview,
            "key_features": feats,
            "demo_video_url": prod.demo_video_url,
            "target_pain_points": pps,
            "target_roles": roles,
        }

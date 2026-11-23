# Enterprise Sales Agent Platform

> Production-Grade Foundation integrating ten specialized AI agents into a unified Modular Monolith application.

## Overview

The Enterprise Sales Agent Platform connects account discovery, researched outreach, inbound conversations, proposals, security reviews, partner development, proof creation, and eligible revival through shared records and durable workflows.

### Ten Specialized Agents

1. **Buying-Signal Radar:** Discovers target companies with verified hiring/growth signals.
2. **Research & Personal Outreach:** Conducts deep account research and crafts sourced drafts (max 3 logical attempts).
3. **Demo Before Hello:** Builds isolated, synthetic data product demos for high-priority prospects.
4. **24/7 Lead Responder:** Ingests and deduplicates inbound SMS/web messages, maintains private lead memory, and books meetings.
5. **Deal Desk:** Extracts needs from completed discovery meetings to draft proposals with ROI models.
6. **Trust & Security Desk:** Answers security questionnaires from approved evidence with reviewer sign-off.
7. **Proof Engine:** Generates case studies with verified before/after metrics and client permissions.
8. **AI Search Visibility:** Monitors query visibility and prepares authoritative public content briefs.
9. **Partner Finder:** Identifies co-sell/referral partners and provides reviewed enablement kits.
10. **Revival Agent:** Reconnects with dormant leads based on fresh evidence without resetting suppression.

---

## Architecture & Technology Stack

- **Backend:** Python 3.12, FastAPI, Pydantic v2, Pydantic Settings, SQLAlchemy 2.x Async, Alembic, PostgreSQL, Redis, Celery.
- **Frontend:** React 18/19, TypeScript, Vite, Tailwind CSS, TanStack Query, React Router, Zustand, React Hook Form, Zod.
- **Infrastructure:** Docker, Docker Compose, Nginx Reverse Proxy, GitHub Actions CI.

```
React Frontend (Vite + Tailwind CSS + TanStack Query)
       |
       v
Nginx Reverse Proxy
       |
       v
FastAPI Modular Monolith
       +-- Authentication & RBAC (JWT + HttpOnly Cookies)
       +-- Agent Orchestrator & Registry (10 Specialized Agents)
       +-- Event-Driven Workflow Engine & Transactional Outbox
       +-- Typed Integrations (Apollo, HubSpot, GHL, SMS, MS Graph, S3, AI Gateway)
       +-- Repository & Service Layers
       |
  PostgreSQL (Asyncpg) <---> Redis <---> Celery Background Workers
```

---

## Quickstart & Local Development

### Prerequisites
- Python 3.12+
- Node.js 18+ and pnpm
- Docker & Docker Compose (optional for containerized setup)

### 1. Environment Setup
```bash
cp .env.example .env
```

### 2. Backend Setup
```bash
# Install Python dependencies
pip install -r backend/requirements.txt

# Run migrations
alembic -c backend/alembic.ini upgrade head

# Seed initial admin user and roles
python -m backend.scripts.seed_data

# Run FastAPI backend
python -m uvicorn backend.app.main:app --reload --port 8001
```

### 3. Frontend Setup
```bash
cd frontend
pnpm install
pnpm dev
```

Visit `http://localhost:5173` to access the application.

---

## Docker Deployment

To launch the complete platform with PostgreSQL, Redis, FastAPI, Celery, and Nginx:

```bash
docker compose up -d --build
```

Access:
- Frontend & API Proxy: `http://localhost:80`
- API Direct: `http://localhost:8001`
- API Docs: `http://localhost:8001/docs`
- Health Check: `http://localhost:8001/api/v1/health`

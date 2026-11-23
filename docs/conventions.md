# Engineering Conventions & Development Guide

## 1. Naming Conventions

### Python / Backend
- **Files & Modules:** `snake_case.py` (e.g. `lead_responder.py`, `workflow_engine.py`)
- **Classes:** `PascalCase` (e.g. `LeadResponderAgent`, `AccountRepository`)
- **Functions & Methods:** `snake_case` (e.g. `get_by_id`, `execute_task`)
- **Constants:** `UPPER_SNAKE_CASE` (e.g. `MAX_OUTREACH_ATTEMPTS`, `JWT_ALGORITHM`)
- **Schemas:** Suffix with `Create`, `Update`, `Response`, `Filter` (e.g. `UserCreate`, `UserResponse`)
- **Tables & Models:** Plural nouns for tables, Singular `PascalCase` for SQLAlchemy models (e.g. table `users`, model `User`)

### TypeScript / Frontend
- **Components & Pages:** `PascalCase.tsx` (e.g. `Button.tsx`, `UserListPage.tsx`)
- **Hooks:** `camelCase` starting with `use` (e.g. `useUsers.ts`, `useAuth.ts`)
- **Services & Utils:** `camelCase.ts` (e.g. `apiClient.ts`, `dateUtils.ts`)
- **Types & Interfaces:** `PascalCase` (e.g. `User`, `ApiResponse<T>`)

---

## 2. Monorepo Organization

```
enterprise-sales-agent-platform/
  backend/
    app/
      api/v1/          # FastAPI routers
      core/            # Config, security, rbac, errors, logging
      db/              # Base declarative, engine, session factory
      models/          # SQLAlchemy async domain models
      schemas/         # Pydantic v2 validation contracts
      repositories/    # Generic & specialized database repositories
      services/        # Business logic services & transaction managers
      agents/          # 10 modular agent definitions
      workflows/       # Workflow engine, handoffs, events
      integrations/    # CRM, SMS, Calendar, Apollo, AI adapters
      tasks/           # Celery workers and async jobs
      middleware/      # Correlation, audit, security headers
      utils/           # Formatting, date, crypto helpers
      monitoring/      # Health, readiness, metrics
    alembic/           # Database migration versions
    tests/             # Unit and integration test suites
  frontend/
    src/
      app/             # Providers, router, store setup
      features/        # Domain features (users, deals, agents, inbox, etc.)
      components/      # Reusable UI primitives (Button, Modal, Table, etc.)
      hooks/           # Cross-cutting React hooks
      lib/             # Typed API client, utility functions
      services/        # Global API services
      routes/          # Route guards and definitions
      pages/           # Top-level page wrappers
      types/           # Common TypeScript types
  docker/              # Dockerfiles for backend, frontend, worker
  nginx/               # Nginx reverse proxy configs
  docs/                # Architectural decisions and guides
```

---

## 3. How to Add a New Backend Feature

1. **Model:** Define the SQLAlchemy model in `backend/app/models/` inheriting from `BaseModel` (UUID, timestamps, org scoping).
2. **Schemas:** Create request/response Pydantic models in `backend/app/schemas/`.
3. **Repository:** Create a repository extending `BaseRepository[ModelType]` in `backend/app/repositories/`.
4. **Service:** Implement business logic in `backend/app/services/` ensuring transaction boundaries and authorization checks.
5. **Router:** Expose endpoints in `backend/app/api/v1/` with RBAC permissions (`require_roles(...)`).
6. **Tests:** Write unit tests in `backend/tests/unit/` and integration tests in `backend/tests/integration/`.

---

## 4. How to Add a New Agent

1. Create a module under `backend/app/agents/<agent_name>/`:
   - `agent.py`: Implement the `BaseAgent` interface.
   - `schemas.py`: Input, output and state schemas.
   - `prompts.py`: Grounded system and task prompts.
   - `service.py`: Domain rules and deterministic guards.
2. Register the agent in `backend/app/agents/registry.py`.
3. Add event listener in `backend/app/workflows/events.py` for automated event-driven triggers.

---

## 5. How to Add an Integration Adapter

1. Define or extend the interface in `backend/app/integrations/base.py`.
2. Implement provider-specific adapter in `backend/app/integrations/<domain>/`.
3. Provide a testable Mock implementation for credential-free local development and automated testing.
4. Register the adapter in `backend/app/integrations/registry.py`.

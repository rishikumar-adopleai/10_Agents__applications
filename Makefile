.PHONY: help install dev backend frontend worker migrate migration seed test test-backend test-frontend lint format typecheck build docker-up docker-down logs

help:
	@echo "Enterprise Sales Agent Platform - Makefile Commands"
	@echo "---------------------------------------------------"
	@echo "make install        - Install backend and frontend dependencies"
	@echo "make dev            - Run both backend and frontend concurrently"
	@echo "make backend        - Run FastAPI development server"
	@echo "make frontend       - Run Vite frontend development server"
	@echo "make worker         - Run Celery background worker"
	@echo "make migrate        - Apply database migrations"
	@echo "make migration      - Generate a new Alembic migration"
	@echo "make seed           - Seed database with initial roles, admin user and sample data"
	@echo "make test           - Run all backend and frontend tests"
	@echo "make test-backend   - Run Pytest backend test suite"
	@echo "make test-frontend  - Run Vitest frontend test suite"
	@echo "make lint           - Run Ruff and ESLint"
	@echo "make format         - Auto-format code using Ruff and Prettier"
	@echo "make typecheck      - Run Mypy and TypeScript checks"
	@echo "make build          - Build production assets for frontend and backend"
	@echo "make docker-up      - Start all services with Docker Compose"
	@echo "make docker-down    - Stop Docker Compose services"
	@echo "make logs           - View Docker Compose logs"

install:
	python -m pip install -r backend/requirements.txt
	cd frontend && pnpm install

dev:
	@echo "Starting development environment..."
	python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000 & cd frontend && pnpm dev

backend:
	python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && pnpm dev

worker:
	celery -A backend.app.tasks.celery_app.celery worker --loglevel=info

migrate:
	alembic -c backend/alembic.ini upgrade head

migration:
	alembic -c backend/alembic.ini revision --autogenerate -m "$(m)"

seed:
	python -m backend.scripts.seed_data

test: test-backend test-frontend

test-backend:
	python -m pytest backend/tests -v

test-frontend:
	cd frontend && pnpm test -- --run

lint:
	ruff check backend
	cd frontend && pnpm lint

format:
	ruff format backend
	cd frontend && pnpm format

typecheck:
	mypy backend/app
	cd frontend && pnpm typecheck

build:
	cd frontend && pnpm build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

logs:
	docker compose logs -f

.PHONY: help install dev test lint format migrate create-super-admin

help:
	@echo "M369 Support — common commands"
	@echo ""
	@echo "  make install     Install backend + frontend deps"
	@echo "  make dev         Start API + frontend (local, no Docker)"
	@echo "  make dev-docker  Start API + DB + Redis via Docker Compose"
	@echo "  make test        Run backend tests"
	@echo "  make lint        Run ruff + mypy"
	@echo "  make format      Run ruff format"
	@echo "  make migrate     Run alembic upgrade head"
	@echo "  make create-super-admin  Create first Super Admin"

install:
	cd apps/api && pip install -r requirements.txt
	cd apps/web && npm install

dev:
	@echo "Starting backend (terminal 1) and frontend (terminal 2)..."
	@echo "Run in separate terminals:"
	@echo "  cd apps/api && uvicorn app.main:app --reload --port 8000"
	@echo "  cd apps/web && npm run dev"

dev-docker:
	docker compose up -d
	@echo ""
	@echo "Services:"
	@echo "  Backend:  http://localhost:8000"
	@echo "  Frontend: http://localhost:3000 (run 'cd apps/web && npm run dev' separately)"
	@echo "  DB:       localhost:5432"
	@echo "  Redis:    localhost:6379"

test:
	cd apps/api && pytest tests/ -v

test-unit:
	cd apps/api && pytest tests/unit/ -v

test-integration:
	cd apps/api && pytest tests/integration/ -v

lint:
	cd apps/api && ruff check .
	cd apps/api && mypy app/

format:
	cd apps/api && ruff format .

migrate:
	cd apps/api && alembic upgrade head

create-super-admin:
	cd apps/api && python -m scripts.create_super_admin

build-frontend:
	cd apps/web && npm run build

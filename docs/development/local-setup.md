# Local Development Setup

## Prerequisites

- Docker 24+ and Docker Compose 2.20+
- OR: Python 3.12+, Node.js 20 LTS+, PostgreSQL 16+, Redis 7+

## Docker Compose (recommended)

```bash
cp .env.example .env
docker compose up -d
docker compose exec api alembic upgrade head
```

- Backend: http://localhost:8000
- Frontend: http://localhost:3000

## Local without Docker

### Backend

```bash
cd apps/api
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd apps/web
npm install
npm run dev
```

## Running Tests

```bash
cd apps/api
pytest tests/ -v
```

Requires real PostgreSQL — no SQLite substitution.

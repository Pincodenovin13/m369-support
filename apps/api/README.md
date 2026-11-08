# M369 Support API — FastAPI Backend

> **Path:** `apps/api/`
> **Runtime:** Python 3.12, FastAPI 0.115, SQLAlchemy 2.0, Alembic, Pydantic 2, psycopg 3
> **Parent docs:** [`/REPOSITORY_MAP.md`](../../REPOSITORY_MAP.md) · [`/STATE.md`](../../STATE.md) · [`/CONTRIBUTING.md`](../../CONTRIBUTING.md)

The FastAPI backend for M369 Support. Multi-tenant SaaS customer support platform with strict PostgreSQL Row-Level Security, six-role database separation, JWT auth with `token_version` revocation, and TOTP MFA for Super Admins.

## Quick Start

```bash
cd apps/api
pip install -r requirements-dev.txt
alembic upgrade head
python scripts/provision_sa_auth_role.py    # requires M369_SA_AUTH_PASSWORD env var
uvicorn app.main:app --reload --port 8000
```

Or via Docker Compose from the repo root:

```bash
cp .env.example .env
# Edit .env with real passwords
docker compose up -d
```

## Structure

```
apps/api/
├── app/
│   ├── main.py                 # FastAPI app factory + router registration
│   ├── api/v1/                 # HTTP route handlers (routers)
│   │   ├── auth.py             # Agency register/login/refresh/logout/me
│   │   ├── agencies.py         # Agency CRUD
│   │   ├── workspaces.py       # Workspace CRUD
│   │   ├── contacts.py         # Contact CRUD
│   │   ├── conversations.py    # Conversation lifecycle
│   │   ├── messages.py         # Messages within conversations
│   │   ├── teams.py            # Team + membership management
│   │   ├── channels.py         # Channel configuration (CRUD only)
│   │   ├── kb.py               # Knowledge Base categories + articles
│   │   ├── canned_responses.py # Templated response snippets
│   │   ├── audit_logs.py       # Agency-scoped audit log read
│   │   ├── health.py           # /health + /health/ready
│   │   └── super_admin/        # Super Admin endpoints (auth, agencies, plans, etc.)
│   ├── core/config.py          # Pydantic Settings (env var parsing)
│   ├── db/database.py          # SQLAlchemy engine/session factory + Base
│   ├── dependencies/           # get_current_user, get_current_super_admin
│   ├── middleware/tenant_context.py  # TenantContextMiddleware
│   ├── models/                 # SQLAlchemy ORM models
│   ├── schemas/                # Pydantic v2 request/response schemas
│   ├── security/               # JWT, password hashing (Argon2id), encryption
│   ├── services/               # Business logic (audit, billing, rate_limit, sa_auth)
│   ├── tenancy/                # TenantContext, set_tenant_context, TenantOwned
│   └── slugs.py                # unique_slug() utility
├── migrations/
│   ├── env.py                  # Alembic env (imports app.models for discovery)
│   └── versions/               # 16 migrations: 0001_initial → 0016_extend_login_helper_with_agency_name
├── scripts/                    # create_super_admin.py, provision_sa_auth_role.py
├── tests/
│   ├── conftest.py             # Shared pytest fixtures
│   ├── unit/                   # Pure-Python unit tests (3 files)
│   └── integration/            # Integration tests requiring PostgreSQL + Redis (15 files)
├── Dockerfile                  # API container image
├── alembic.ini                 # Alembic config
├── pyproject.toml              # ruff + mypy + pytest config
├── requirements.txt            # Runtime deps
└── requirements-dev.txt        # Dev/test deps (pytest, ruff, mypy, fakeredis)
```

## API Endpoints

64 endpoints across agency and Super Admin routers. See `/docs/architecture/overview.md` for the full router map.

## Database

- **Engine:** PostgreSQL 16
- **Migration head:** `0016_extend_login_helper_with_agency_name`
- **Tables:** 25 (14 in `models/__init__.py` + 11 in `models/phase1_extended.py`)
- **Roles:** 6 dedicated roles (`m369_app`, `m369_sa_auth`, `m369_sa_runner`, `m369_login_reader`, `m369_registration_guard`, `m369_super_admin` neutralized)
- **RLS:** ENABLE + FORCE on all 17 tenant-owned tables
- **Composite FKs:** 10 constraints preventing cross-tenant references

## Testing

```bash
cd apps/api
python3 -m pytest -q
```

- **Static test count:** 346 functions across 18 test files (3 unit + 15 integration)
- **Test execution status:** Z.ai-reported, NOT independently verified (sandbox lacks sqlalchemy). See `/STATE.md` for verification status.
- **Frontend type-check:** independently verified PASS (2026-11-08)

## Environment Variables

See [`docs/development/environment.md`](../../docs/development/environment.md) for the full list. Key vars:

| Var | Purpose |
|---|---|
| `DATABASE_URL` | m369_app role connection (RLS-enforced) |
| `DATABASE_URL_SUPER_ADMIN` | m369_sa_runner role (BYPASSRLS, Super Admin management) |
| `DATABASE_URL_SUPER_ADMIN_AUTH` | m369_sa_auth role (Super Admin login + MFA verify) |
| `JWT_SECRET_KEY` | Agency + refresh + MFA-challenge token signing |
| `JWT_SUPER_ADMIN_SECRET_KEY` | Super Admin token signing |
| `REDIS_URL` | Rate-limit backend |
| `M369_APP_PASSWORD` / `M369_SA_RUNNER_PASSWORD` / `M369_SA_AUTH_PASSWORD` | Bootstrap role passwords |

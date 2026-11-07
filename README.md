# M369 Support

> Independent, commercial, multi-tenant SaaS customer support platform.
> Built from scratch — not a fork of any existing product.

## Project Status

**Phase 1 (Foundation + Multi-Tenancy + Security Hardening)** — implementation complete. Test results are **reported by Z.ai** (the implementation agent) from a local sandbox and have **not** been independently verified. See [`STATE.md`](./STATE.md) for details, blockers, and evidence.

- **Current state:** See [`STATE.md`](./STATE.md) for completed packages, commit references, test status, blockers, and next steps.
- **Repository structure:** See [`docs/PROJECT_STRUCTURE.md`](./docs/PROJECT_STRUCTURE.md) for the complete tracked file tree and entry points.

## Repository Layout

```
m369-support/
├── apps/
│   ├── api/         FastAPI backend (Python 3.12, SQLAlchemy 2.0, Alembic)
│   ├── web/         Next.js 15 frontend (React 19, TypeScript, Tailwind)
│   └── widget/      Embeddable widget (scaffolded, future phase)
├── packages/
│   └── shared/      Shared TypeScript types (future)
├── infrastructure/  Database bootstrap SQL
├── docs/            Architecture, security, database, development docs
├── docker-compose.yml
├── .env.example
└── STATE.md         Current project state and status
```

## Quick Start (Local Development)

### Prerequisites

- Docker 24+ and Docker Compose 2.20+
- OR: Python 3.12+, Node.js 20 LTS+, PostgreSQL 16+, Redis 7+

### Docker Compose (recommended)

```bash
cp .env.example .env
# Edit .env with real passwords
docker compose up -d
# Migration + provisioning runs automatically
```

- Backend: http://localhost:8000
- Frontend: http://localhost:3000

### Manual Setup

```bash
# Backend
cd apps/api
pip install -r requirements-dev.txt
alembic upgrade head
python scripts/provision_sa_auth_role.py  # requires M369_SA_AUTH_PASSWORD env var
uvicorn app.main:app --reload

# Frontend
cd apps/web
npm install
npm run dev
```

## Documentation

### Navigation

| Document | Path | Description |
|---|---|---|
| **Project State** | [`STATE.md`](./STATE.md) | Current phase, completed packages, test status, blockers, next steps |
| **Project Structure** | [`docs/PROJECT_STRUCTURE.md`](./docs/PROJECT_STRUCTURE.md) | Complete tracked file tree, entry points, file purposes |
| **Architecture Overview** | [`docs/architecture/overview.md`](./docs/architecture/overview.md) | System architecture diagram, layers, design principles |
| **Phase 1 Scope** | [`docs/architecture/phase-1.md`](./docs/architecture/phase-1.md) | What's implemented, what's deferred, what's blocked |
| **Security: Tenant Isolation** | [`docs/security/tenant-isolation.md`](./docs/security/tenant-isolation.md) | RLS policies, tenant context, composite FKs |
| **Security: Authentication** | [`docs/security/authentication.md`](./docs/security/authentication.md) | JWT, Argon2id, token_version, MFA |
| **Security: Session Revocation** | [`docs/security/agency-session-revocation.md`](./docs/security/agency-session-revocation.md) | How token_version enables server-side logout |
| **Security: README** | [`docs/security/README.md`](./docs/security/README.md) | Security documentation index |
| **Database Schema** | [`docs/database/schema.md`](./docs/database/schema.md) | Tables, columns, constraints |
| **Local Setup** | [`docs/development/local-setup.md`](./docs/development/local-setup.md) | Step-by-step development environment setup |
| **Environment Variables** | [`docs/development/environment.md`](./docs/development/environment.md) | All env vars with descriptions |
| **Testing** | [`docs/development/testing.md`](./docs/development/testing.md) | Test architecture, how to run, what's covered |

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI 0.115, SQLAlchemy 2.0, Alembic, Pydantic 2, psycopg 3 |
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS |
| Database | PostgreSQL 16 (RLS, composite FKs, SECURITY DEFINER functions) |
| Cache/Rate Limit | Redis 7 (custom Lua INCR+EXPIRE limiter) |
| Auth | JWT (HS256, separate keys for agency/super_admin), Argon2id, TOTP MFA |
| Deployment | Docker Compose (db, redis, migration, api) |

## Testing

Test results below are **reported by Z.ai** (the implementation agent) from a local sandbox and have **not** been independently verified. See [`STATE.md`](./STATE.md) for full evidence and blockers.

```bash
# Backend (Z.ai reports 346 tests passing against real PostgreSQL 16.2)
cd apps/api
python3 -m pytest -q

# Frontend (Z.ai reports all checks passing)
cd apps/web
npm run type-check
npm run build
npm run lint
```

## License

MIT — see [`LICENSE`](./LICENSE).

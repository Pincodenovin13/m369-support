# M369 Support

> Independent, commercial, multi-tenant SaaS customer support platform.
> Built from scratch — not a fork of any existing product.

## Project Status

**Current engineering branch:** `refactor/repository-structure-unification` (HEAD `ce3d54a2df13494ee914bea2f0677dd11f736a0c`). The latest API/PostgreSQL GitHub Actions run on this exact commit completed successfully: **359 passed, 1 warning**. This is CI evidence, not production security certification. See [`STATE.md`](./STATE.md) for current evidence and limitations.

- **Current state:** See [`STATE.md`](./STATE.md) for completed packages, commit references, test status, blockers, and next steps.
- **Repository structure:** See [`REPOSITORY_MAP.md`](./REPOSITORY_MAP.md) for the authoritative file/folder responsibility map.
- **Development rules:** See [`CONTRIBUTING.md`](./CONTRIBUTING.md) for branch naming, commit conventions, PR rules, and Rule 13 (Artifact Disclosure & Delivery).

## Repository Layout

```
m369-support/
├── apps/
│   ├── api/         FastAPI backend (Python 3.12, SQLAlchemy 2.0, Alembic)
│   ├── web/         Next.js 15 frontend (React 19, TypeScript, Tailwind)
│   └── widget/      Embeddable widget [PLANNED — placeholder]
├── packages/
│   └── shared/      Shared TypeScript types [PLANNED — placeholder]
├── infrastructure/  Database bootstrap SQL
├── docs/            Architecture, security, database, development docs
├── recovery/        HISTORICAL archive only (never implementation source)
├── .github/         PR template + CI workflows
├── docker-compose.yml
├── .env.example
├── README.md        This file
├── REPOSITORY_MAP.md  Authoritative file/folder map
├── CONTRIBUTING.md    Development rules + Rule 13
└── STATE.md         Current project state and status
```

See [`REPOSITORY_MAP.md`](./REPOSITORY_MAP.md) for the full per-directory responsibility map.

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

### Canonical Documents (Root)

| Document | Path | Description |
|---|---|---|
| **Project State** | [`STATE.md`](./STATE.md) | Current phase, completed packages, test status (strict verification labels), blockers |
| **Repository Map** | [`REPOSITORY_MAP.md`](./REPOSITORY_MAP.md) | Authoritative file/folder responsibility map |
| **Contributing** | [`CONTRIBUTING.md`](./CONTRIBUTING.md) | Branch naming, commit conventions, PR rules, migration rules, Rule 13 |

### Supplementary Documentation (`docs/`)

See [`docs/README.md`](./docs/README.md) for the full documentation index. Key docs:

| Document | Path | Description |
|---|---|---|
| Architecture Overview | [`docs/architecture/overview.md`](./docs/architecture/overview.md) | System architecture diagram, layers, design principles |
| Phase 1 Scope | [`docs/architecture/phase-1.md`](./docs/architecture/phase-1.md) | What's implemented, what's deferred, what's blocked |
| Security: Tenant Isolation | [`docs/security/tenant-isolation.md`](./docs/security/tenant-isolation.md) | RLS policies, tenant context, composite FKs |
| Security: Authentication | [`docs/security/authentication.md`](./docs/security/authentication.md) | JWT, Argon2id, token_version, MFA |
| Security: Session Revocation | [`docs/security/agency-session-revocation.md`](./docs/security/agency-session-revocation.md) | How token_version enables server-side logout + refresh-token rotation |
| Database Schema | [`docs/database/schema.md`](./docs/database/schema.md) | Tables, columns, constraints |
| Local Setup | [`docs/development/local-setup.md`](./docs/development/local-setup.md) | Step-by-step development environment setup |
| Environment Variables | [`docs/development/environment.md`](./docs/development/environment.md) | All env vars with descriptions |
| Testing | [`docs/development/testing.md`](./docs/development/testing.md) | Test architecture, how to run, verification status |

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

Test results use strict evidence labels. Latest API/PostgreSQL CI: [run 42646416006](https://github.com/Pincodenovin13/m369-support/actions/runs/42646416006) — **359 passed, 1 warning**, exact commit `ce3d54a2df13494ee914bea2f0677dd11f736a0c`. Latest frontend CI: [run 42628470610](https://github.com/Pincodenovin13/m369-support/actions/runs/42628470610) — success on the current frontend code snapshot. Production Redis, deployment topology, and persistent production database remain unverified.

```bash
cd apps/api && pytest -q tests
cd apps/web && npm ci && npm run type-check && npm run lint && npm run build
```

## License

MIT — see [`LICENSE`](./LICENSE).

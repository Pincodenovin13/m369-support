# M369 Support — Repository Map

> **Status:** Authoritative file-placement map for the M369 Support repository.
> **Last updated:** 2026-11-08
> **Branch:** `refactor/repository-structure-unification`
> **Companion documents:** [`/STATE.md`](./STATE.md) (current state) · [`/CONTRIBUTING.md`](./CONTRIBUTING.md) (workflow rules)

This document is the **single authoritative source** for where files belong in the M369 Support repository. When adding a new file, consult this map to determine the correct location.

---

## Top-Level Layout

```
m369-support/
├── apps/                        # Application source code
│   ├── api/                    # FastAPI backend (Python 3.12)
│   ├── web/                    # Next.js 15 frontend (React 19 + TS)
│   └── widget/                 # Embeddable widget [PLANNED — placeholder]
├── packages/
│   └── shared/                 # Shared TS types [PLANNED — placeholder]
├── infrastructure/
│   └── database/               # PostgreSQL bootstrap SQL
├── docs/                        # Architecture, security, database, development docs
├── recovery/                    # HISTORICAL archive — not authoritative
│   └── workspace-preservation/ # Archived artifacts from prior sessions
├── .github/                     # GitHub config (PR template only; no CI workflow tracked)
├── docker-compose.yml           # Local dev orchestration (db + redis + api)
├── .env.example                 # Environment variable template (no secrets)
├── .gitignore                   # Python + Node + IDE + env patterns
├── Makefile                     # Common dev commands
├── README.md                    # Project overview + quick start
├── REPOSITORY_MAP.md            # THIS FILE
├── CONTRIBUTING.md              # Branch/commit/PR workflow rules + Rule 13
├── STATE.md                     # Current project state + verification status
└── LICENSE                      # MIT
```

---

## `apps/api/` — FastAPI Backend

| Path | Responsibility | Entry point | What belongs here | What does NOT belong |
|---|---|---|---|---|
| `apps/api/app/main.py` | FastAPI app factory; router registration; middleware setup | `create_app()` → `app` | App creation, router includes, middleware registration | Business logic, route handlers |
| `apps/api/app/api/v1/` | HTTP route handlers (routers) | Each `*.py` defines `router = APIRouter(...)` | Request/response validation, dependency injection, calling services | Direct DB writes (move to `services/`) |
| `apps/api/app/api/v1/super_admin/` | Super Admin route handlers (separate subpackage) | `auth.py`, `agencies.py`, `plans.py`, `subscriptions.py`, `payments.py`, `settings_notes_audit.py` | Super Admin endpoints only | Agency endpoints (those go in `api/v1/`) |
| `apps/api/app/core/` | App-wide configuration | `config.py:Settings` (Pydantic BaseSettings) | Settings, env var parsing, validation | Business logic, models |
| `apps/api/app/db/` | Database session factory + dependencies | `database.py:get_db`, `get_super_admin_db`, `get_super_admin_auth_db`, `Base` | SQLAlchemy engine/session setup, FastAPI dependencies | Models, migrations |
| `apps/api/app/dependencies/` | Cross-cutting FastAPI dependencies | `__init__.py:get_current_user`, `get_current_super_admin` | Auth dependencies, tenant-context deps | Route handlers |
| `apps/api/app/middleware/` | ASGI/Starlette middleware | `tenant_context.py:TenantContextMiddleware` | Request preprocessing (auth resolution, tenant context) | Business logic, route handlers |
| `apps/api/app/models/` | SQLAlchemy ORM models | `__init__.py` re-exports all models; `phase1_extended.py` has Phase 1 tables | Table definitions (grouped by domain when split) | Routes, business logic |
| `apps/api/app/schemas/` | Pydantic v2 request/response schemas | `__init__.py` re-exports common schemas; domain files: `audit.py`, `channels_kb.py`, `common.py`, `conversations.py`, `super_admin.py`, `teams.py` | Validation models, serializers | ORM models |
| `apps/api/app/security/` | JWT, password hashing, encryption | `jwt.py:create_access_token`, `create_refresh_token`, `decode_*`, `hash_password`, `verify_password` | Auth primitives | Route handlers, business logic |
| `apps/api/app/services/` | Business logic (stateless functions) | `audit.py:write_audit`, `billing.py`, `rate_limit.py`, `sa_auth.py` | Domain logic, atomic DB updates, Redis calls | Route handlers |
| `apps/api/app/tenancy/` | Tenant context primitives | `context.py:TenantContext`, `set_tenant_context`, `clear_tenant_context`, `TenantOwned` mixin | Tenant GUC management, tenant-owned mixin | Middleware, business logic |
| `apps/api/app/slugs.py` | Slug utility for unique URL-safe names | `unique_slug()` | Slug generation only | Anything else |
| `apps/api/migrations/` | Alembic config + migrations | `env.py`, `versions/0001_initial.py` through `0018_workspace_agency_fks_contacts_teams.py` | Schema migrations and explicitly validated data backfills | Application code |
| `apps/api/scripts/` | Operational scripts | `create_super_admin.py`, `provision_sa_auth_role.py` | One-off provisioning + admin scripts | Tests, application code |
| `apps/api/tests/` | Test suite | `conftest.py`, `unit/`, `integration/` | Tests only | Application code, scripts |
| `apps/api/Dockerfile` | API container image | — | Build + runtime for API service | Frontend, widget |
| `apps/api/alembic.ini` | Alembic config | — | Alembic config only | Application config |
| `apps/api/pyproject.toml` | Python project metadata (ruff, mypy, pytest config) | — | Tool config only | Application code |
| `apps/api/requirements.txt` | Runtime Python deps | — | Runtime deps only | Dev/test deps |
| `apps/api/requirements-dev.txt` | Dev/test Python deps | — | Dev/test deps only (pytest, ruff, mypy, fakeredis) | Runtime deps |

### Backend statistics (verified 2026-11-08)

| Metric | Value |
|---|---|
| Backend source files (`apps/api/app/**/*.py`) | 58 |
| Backend test/support Python files (`apps/api/tests/**/*.py`) | 24 |
| Static test function count | 350 (346 prior count + 4 new tests; not re-counted — see STATE.md) |
| Migrations | 18 (0001–0018, linear chain) |
| Database tables | 25 (14 in `models/__init__.py` + 11 in `models/phase1_extended.py`) |
| API endpoints | 64 (verified via `grep -rhE '@router\.(get\|post\|put\|patch\|delete)'`) |
| Database roles | 6 (`m369_app`, `m369_sa_auth`, `m369_sa_runner`, `m369_login_reader`, `m369_registration_guard`, `m369_super_admin` neutralized) |

---

## `apps/web/` — Next.js Frontend

| Path | Responsibility | Entry point | What belongs here |
|---|---|---|---|
| `apps/web/src/app/` | Next.js App Router pages | `layout.tsx`, `page.tsx`, `login/`, `register/`, `dashboard/` | Page components only |
| `apps/web/src/components/` | Reusable React components | `providers.tsx`, `dashboard-shell.tsx` | Presentational + client components |
| `apps/web/src/lib/` | Frontend utilities + API client | `api-client.ts`, `utils.ts` | Pure functions, fetch wrappers, type defs |
| `apps/web/src/app/globals.css` | Global Tailwind styles | Imported by root layout | Global styles only |
| `apps/web/package.json` | Frontend deps + scripts | `dev`, `build`, `start`, `lint`, `type-check` | npm config only |
| `apps/web/tsconfig.json` | TypeScript config (strict, src-layout) | — | TS config only |
| `apps/web/tailwind.config.ts` | Tailwind config | — | Tailwind config only |
| `apps/web/postcss.config.js` | PostCSS config | — | PostCSS config only |
| `apps/web/next.config.ts` | Next.js config | — | Next config only |
| `apps/web/.eslintrc.js` | ESLint config | — | Lint config only |

### Frontend statistics

| Metric | Value |
|---|---|
| Frontend source files (`apps/web/src/**/*`) | 19 |
| Frontend config files | 8 |
| Frontend test files | 0 (NOT IMPLEMENTED — Phase 1 has no frontend test suite) |
| Frontend type-check (`tsc --noEmit`) | ✅ Independently verified PASS (2026-11-08) |

---

## `apps/widget/` — Embeddable Widget

**Status:** `[PLANNED]` — placeholder only.

| Path | Responsibility | Status |
|---|---|---|
| `apps/widget/src/.gitkeep` | Placeholder marker | Contains `# Future: embeddable widget` — no source, no build config |

**Do NOT add fake widget code.** When implementation begins, it will live in `apps/widget/src/` with its own `package.json` and build config.

---

## `packages/shared/` — Shared TypeScript Types

**Status:** `[PLANNED]` — placeholder only.

| Path | Responsibility | Status |
|---|---|---|
| `packages/shared/.gitkeep` | Placeholder marker | Empty |

When the widget and web app need shared types, they will live here.

---

## `infrastructure/` — Infrastructure Configuration

| Path | Responsibility |
|---|---|
| `infrastructure/database/01-bootstrap-roles.sql` | PostgreSQL container initialization — creates 6 `m369_*` roles from env vars (passwords via `\getenv`, never hardcoded) |

---

## `docs/` — Documentation

See [`docs/README.md`](./docs/README.md) for the documentation index.

---

## `recovery/` — HISTORICAL Archive (NOT AUTHORITATIVE)

| Path | Responsibility | Status |
|---|---|---|
| `recovery/workspace-preservation/` | Historical artifacts from Z.ai workspace sessions (Nov 2-8, 2026) | ⚠️ ARCHIVED — see `recovery/workspace-preservation/README.md` for the archive notice |

**Do NOT use files in `recovery/` as implementation references.** They contain outdated architecture, superseded designs, and some files contain OpenLivery material that must never be used as M369 sources.

---

## `.github/` — GitHub Configuration

| Path | Responsibility |
|---|---|
| `.github/PULL_REQUEST_TEMPLATE.md` | Required PR sections (purpose, changed files, security impact, migration impact, tests executed, tests not executed + why, rollback, evidence, verification labels) |

---

## Root-Level Files

| File | Responsibility |
|---|---|
| `README.md` | Project overview + quick start + links to canonical docs |
| `REPOSITORY_MAP.md` | THIS FILE — file/folder responsibilities |
| `CONTRIBUTING.md` | Permanent development rules: branch naming, commit conventions, PR rules, file placement, migration rules, security review, Rule 13 (Artifact Disclosure & Delivery) |
| `STATE.md` | Current project state — Git SHAs, migration head, test results with strict verification labels, environment limitations, risks |
| `docker-compose.yml` | Local dev orchestration (db + redis + migration + api) |
| `Makefile` | Common dev command shortcuts |
| `.env.example` | Template for `.env` — no real secrets, only placeholder values |
| `.gitignore` | Python + Node + IDE + env patterns |
| `LICENSE` | MIT |

---

## File Placement Rules

1. **One responsibility per file.** A route handler file does not contain service-layer DB calls.
2. **Migrations are append-only.** Never edit a published migration. New migration = new file with `NNNN_` prefix.
3. **No business logic in routers.** Routers validate input, call a service, format output.
4. **No DB queries in `models/`.** Models define schema; queries live in services or routers.
5. **No `*.env` files committed.** Only `.env.example` is tracked.
6. **No build artifacts committed.** `node_modules/`, `.next/`, `__pycache__/`, `*.egg-info/`, `dist/`, `build/` are git-ignored.
7. **New top-level directories require an entry in this file.** If you add `infrastructure/docker/`, document it here.
8. **Test files live next to the code they test (backend) or in a `__tests__` folder (frontend, when added).** Backend: `apps/api/tests/{unit,integration}/`. Frontend: TBD when frontend tests are added.
9. **Historical artifacts go in `recovery/workspace-preservation/`** with a clear HISTORICAL/ARCHIVED notice. They must never be used as implementation references.

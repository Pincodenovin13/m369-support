# Project Structure

> Complete tree of all Git-tracked files on branch `phase-1/agency-auth-integration-closure` at commit `0fb6dc1`.
> Generated via `git ls-files` — no files invented or omitted.

---

## Root Files

```
.env.example                         Environment variable template (copy to .env)
.gitignore                           Git ignore rules (Python + Node + env)
LICENSE                              MIT license
Makefile                             Convenience targets (make dev, make test, etc.)
README.md                            Project overview + navigation
STATE.md                             Current project state, packages, blockers
docker-compose.yml                   Local dev stack (db, redis, migration, api)
```

---

## Backend — `apps/api/`

**Entry point:** `apps/api/app/main.py` → `create_app()` → FastAPI instance.
**Run:** `uvicorn app.main:app --reload` (from `apps/api/`)

```
apps/api/
├── Dockerfile                        Production Docker image
├── alembic.ini                       Alembic migration configuration
├── pyproject.toml                    Python project metadata + dependencies
├── requirements.txt                  Production dependencies (installed by Dockerfile)
├── requirements-dev.txt              Dev dependencies (pytest, ruff, fakeredis, etc.)
├── app/
│   ├── __init__.py
│   ├── main.py                       FastAPI app factory — includes all routers
│   ├── core/
│   │   └── config.py                 Settings (env vars, production guard)
│   ├── db/
│   │   └── database.py               Engines, sessions, get_db / get_super_admin_db / get_super_admin_auth_db
│   ├── dependencies/
│   │   └── __init__.py               Auth deps: get_current_user, get_super_admin_context, require_role
│   ├── middleware/
│   │   └── tenant_context.py         TenantContextMiddleware (resolves JWT → request.state)
│   ├── models/
│   │   ├── __init__.py               Core models: Agency, User, Membership, Conversation, etc.
│   │   └── phase1_extended.py        Extended models: Message, Channel, KB, Plans, Subscriptions, Payments
│   ├── schemas/
│   │   ├── __init__.py               Re-exports all schemas
│   │   ├── common.py                 PaginationParams, PaginatedResponse[T]
│   │   ├── conversations.py          Contact, Conversation, Message schemas
│   │   ├── teams.py                  Team schemas
│   │   ├── channels_kb.py            Channel, KB, CannedResponse schemas
│   │   ├── super_admin.py            SA management + billing schemas
│   │   └── audit.py                  AuditLogOut
│   ├── security/
│   │   ├── __init__.py               Re-exports
│   │   └── jwt.py                    Argon2id, JWT (agency/super_admin/mfa_challenge/refresh), Fernet
│   ├── services/
│   │   ├── __init__.py
│   │   ├── audit.py                  Agency audit log writer
│   │   ├── billing.py                Subscription lifecycle + payment verification
│   │   ├── sa_auth.py                SA brute-force, token_version bump, MFA TOTP, recovery codes
│   │   └── rate_limit.py             Custom Redis limiter (INCR+EXPIRE Lua), trusted-proxy IP
│   ├── slugs.py                      Slug generation (kebab-case, uniqueness)
│   ├── tenancy/
│   │   ├── __init__.py
│   │   └── context.py               set_tenant_context, TenantContext dataclass
│   └── api/
│       └── v1/
│           ├── __init__.py           Router registration
│           ├── auth.py              /auth/register, /login, /refresh, /logout, /me
│           ├── agencies.py          /agencies/current
│           ├── workspaces.py        /workspaces CRUD
│           ├── contacts.py          /contacts CRUD + pagination
│           ├── conversations.py     /conversations CRUD
│           ├── messages.py          /messages list + send
│           ├── teams.py             /teams + members
│           ├── channels.py          /channels CRUD
│           ├── kb.py                /kb/categories + /kb/articles
│           ├── canned_responses.py  /canned-responses CRUD
│           ├── audit_logs.py        /audit-logs (agency-scoped)
│           ├── health.py           /health, /health/ready
│           └── super_admin/
│               ├── __init__.py
│               ├── auth.py             SA login, MFA, logout, /me
│               ├── agencies.py        SA agency management
│               ├── plans.py           SA plan CRUD
│               ├── subscriptions.py   SA subscription lifecycle
│               ├── payments.py         SA payment verify/reject
│               └── settings_notes_audit.py  SA settings, agency notes, SA audit log
├── migrations/
│   ├── env.py                        Alembic environment
│   ├── script.py.mako               Migration template
│   └── versions/
│       ├── 0001_initial.py           Base schema + RLS + roles
│       ├── 0002_remove_admin_login.py
│       ├── 0003_login_helper_function.py
│       ├── 0004_fix_login_helper_acl.py
│       ├── 0005_restrict_login_helper_owner.py
│       ├── 0006_phase1_extended.py   11 new tables + plans
│       ├── 0007_fix_login_reader_acl.py
│       ├── 0008_create_sa_runner_role.py
│       ├── 0009_widen_paid_currency.py
│       ├── 0010_sa_auth_hardening.py   SA auth + MFA tables
│       ├── 0011_tenant_isolation_hardening.py  RLS + composite FKs + least-privilege
│       ├── 0012_package_b1_critical_corrections.py  FK fixes + m369_sa_auth role
│       ├── 0013_package_b1_2_final_security.py  Registration guard + role neutralization
│       └── 0014_agency_user_token_version.py  Agency session revocation
├── scripts/
│   ├── create_super_admin.py         CLI: create first Super Admin
│   └── provision_sa_auth_role.py    CLI: provision m369_sa_auth password from env
└── tests/
    ├── __init__.py
    ├── conftest.py                   Dual-connection fixtures (setup=postgres, test=m369_app)
    ├── unit/
    │   ├── __init__.py
    │   ├── test_config.py
    │   ├── test_compose_isolation.py
    │   └── test_security_and_utils.py
    └── integration/
        ├── __init__.py
        ├── test_auth_tenant_context.py
        ├── test_rls_bypass_attack.py
        ├── test_security_tenant_isolation.py
        ├── test_stage2_api_rbac.py
        ├── test_stage3_super_admin_billing.py
        ├── test_stage4_security_audit.py
        ├── test_stage5_sa_auth_hardening.py
        ├── test_stage5_package_a1_corrections.py
        ├── test_stage5_package_a2_corrections.py
        ├── test_stage5_package_a2_1_corrections.py
        ├── test_stage6_package_b_tenant_isolation.py
        ├── test_stage6_package_b1_corrections.py
        ├── test_stage6_package_b1_1_corrections.py
        ├── test_stage7_package_b1_2_final_security.py
        └── test_stage8_agency_token_revocation.py
```

---

## Frontend — `apps/web/`

**Entry point:** `apps/web/src/app/layout.tsx` → `apps/web/src/app/page.tsx`
**Run:** `npm run dev` (from `apps/web/`)

```
apps/web/
├── .eslintrc.js                      ESLint configuration
├── next.config.ts                    Next.js configuration
├── package-lock.json
├── package.json                      Dependencies (Next.js 15, React 19, Tailwind)
├── postcss.config.js
├── tailwind.config.ts                Tailwind CSS configuration
├── tsconfig.json                     TypeScript configuration
└── src/
    ├── app/
    │   ├── layout.tsx               Root layout (providers, fonts)
    │   ├── page.tsx                  Landing page
    │   ├── globals.css              Global styles + Tailwind directives
    │   ├── login/
    │   │   └── page.tsx             Login page (multi-agency selection)
    │   ├── register/
    │   │   └── page.tsx             Agency registration page
    │   └── dashboard/
    │       └── page.tsx             Agency dashboard (workspaces, role, status)
    ├── components/
    │   ├── dashboard-shell.tsx      Layout shell (header, logout, error handling)
    │   └── providers.tsx            React Query provider
    └── lib/
        ├── api-client.ts            API client (fetch, cookies, auto-refresh, ApiError)
        └── utils.ts                 Utility functions
```

---

## Widget — `apps/widget/`

```
apps/widget/
└── src/
    └── .gitkeep                     Scaffolded — not yet implemented (Phase 4+)
```

---

## Infrastructure — `infrastructure/`

```
infrastructure/
└── database/
    └── 01-bootstrap-roles.sql       PostgreSQL init script (provisions m369_app, m369_sa_runner, m369_sa_auth via \getenv)
```

---

## Shared Packages — `packages/`

```
packages/
└── shared/
    └── .gitkeep                     Scaffolded — shared TypeScript types (future)
```

---

## Documentation — `docs/`

```
docs/
├── PHASE1_BACKEND_CONTINUATION.md   Phase 1 backend continuation notes
├── PROJECT_STRUCTURE.md             This file — complete tracked file tree
├── architecture/
│   ├── overview.md                  System architecture (diagram, layers)
│   └── phase-1.md                  Phase 1 scope + implementation status
├── database/
│   └── schema.md                    Database schema documentation
├── development/
│   ├── environment.md               Environment variables
│   ├── local-setup.md               Local development setup guide
│   └── testing.md                   Testing guide
└── security/
    ├── README.md                    Security docs index
    ├── agency-session-revocation.md  Token_version revocation architecture
    ├── authentication.md            Auth flow documentation
    └── tenant-isolation.md          RLS + tenant isolation documentation
```

---

## Key Entry Points

| What | File | Command |
|---|---|---|
| Backend API | `apps/api/app/main.py` | `uvicorn app.main:app` |
| Frontend app | `apps/web/src/app/layout.tsx` | `npm run dev` |
| Migration | `apps/api/alembic.ini` | `alembic upgrade head` |
| Provisioning | `apps/api/scripts/provision_sa_auth_role.py` | `python scripts/provision_sa_auth_role.py` |
| Create Super Admin | `apps/api/scripts/create_super_admin.py` | `python scripts/create_super_admin.py` |
| Docker stack | `docker-compose.yml` | `docker compose up -d` |

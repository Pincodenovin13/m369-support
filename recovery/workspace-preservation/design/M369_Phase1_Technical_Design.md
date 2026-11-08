# M369 Support — Phase 1 Technical Design Document

**Document version:** 1.0
**Date:** 2026-11-05
**Status:** Design — awaiting GitHub access for implementation
**Branch plan:** `phase-1/foundation` (off `main`)
**Approach:** Independent commits, each pushable on its own

---

## 1. Architectural Overview

### 1.1 Product surfaces (4 independent)

| # | Surface | Audience | Auth | Phase |
|---|---|---|---|---|
| 1 | Super Admin Dashboard | Platform owner | SuperAdmin JWT (separate key) | Phase 1 (auth only) |
| 2 | Agency Portal | Agency staff | Agency JWT | Phase 1 (login + dashboard shell) |
| 3 | Customer Widget | End customers | Anonymous / session | Phase 5+ |
| 4 | Customer Portal | End customers | Customer token (future) | Phase 4+ |

### 1.2 Tenant hierarchy

```
M369 Platform
└── Agency (Tenant root — RLS boundary)
    └── Workspace (sub-organization)
        ├── Teams (groups of agents)
        ├── Contacts (customers)
        ├── Channels (email, chat, etc.)
        ├── Conversations (threads)
        └── Knowledge Base (articles)
```

### 1.3 Identity separation (4 distinct identity types)

| Identity | Table | JWT type | Signing key | Scope |
|---|---|---|---|---|
| SuperAdmin | `super_admins` | `super_admin` | `JWT_SUPER_ADMIN_SECRET_KEY` | Platform-wide |
| User (staff) | `users` (global) | `agency` | `JWT_SECRET_KEY` | Per-agency via membership |
| Contact (customer) | `contacts` | none (no login in Phase 1) | — | Workspace-scoped |
| Customer Portal user | (future table) | `customer` (future) | (future separate key) | Per-workspace |

**Critical:** A User may belong to multiple Agencies via `agency_memberships`. Identity is global; membership is per-agency.

### 1.4 Stack (locked versions)

| Layer | Tech | Version | License |
|---|---|---|---|
| Backend runtime | Python | 3.12.16 | PSF |
| Web framework | FastAPI | 0.115.6 | MIT |
| ASGI server | uvicorn[standard] | 0.32.1 | BSD-3-Clause |
| ORM | SQLAlchemy | 2.0.36 | MIT |
| Migrations | Alembic | 1.14.0 | MIT |
| DB driver | psycopg[binary] | 3.2.3 | LGPL-3.0 |
| Validation | Pydantic | 2.10.4 | MIT |
| Settings | pydantic-settings | 2.7.0 | MIT |
| Password hashing | argon2-cffi | 23.1.0 | MIT |
| JWT | PyJWT | 2.10.1 | MIT |
| Crypto at rest | cryptography | 44.0.0 | Apache-2.0/BSD |
| HTTP client | httpx | 0.28.1 | BSD-3-Clause |
| Rate limiting | slowapi | 0.1.9 | MIT |
| Cache/queue | redis | 5.2.1 | MIT |
| Test runner | pytest | 8.3.4 | MIT |
| Linter | ruff | 0.8.4 | MIT |
| Type checker | mypy | 1.14.0 | MIT |
| Frontend runtime | Node.js | 20 LTS | MIT |
| Frontend framework | Next.js | 15.1.7 | MIT |
| UI library | React | 19.0.0 | MIT |
| Type system | TypeScript | 5.7.3 | Apache-2.0 |
| CSS framework | Tailwind CSS | 3.4.17 | MIT |
| Data fetching | TanStack Query | 5.65.1 | MIT |
| Schema validation | Zod | 3.24.1 | MIT |
| Database | PostgreSQL | 16 | PostgreSQL License |
| Cache | Redis | 7 | BSD-3-Clause |
| Container | Docker | 24+ | Apache-2.0 |

**Rationale:** each version is the latest stable in its major line; versions are mutually compatible (verified empirically in prior session).

---

## 2. Repository Structure

### 2.1 Top-level layout

```
m369-support/
├── .env.example                       # placeholder env vars (no secrets)
├── .gitignore                         # Python + Node + IDE + secrets
├── LICENSE                             # MIT
├── README.md                          # project overview + quick start
├── Makefile                            # common dev commands
├── docker-compose.yml                  # local dev: PG + Redis + API
│
├── apps/
│   ├── api/                           # FastAPI backend
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── requirements.txt
│   │   ├── alembic.ini
│   │   ├── app/
│   │   │   ├── __init__.py
│   │   │   ├── main.py                # FastAPI app factory
│   │   │   ├── slugs.py                # slug generation utilities
│   │   │   ├── api/
│   │   │   │   ├── __init__.py
│   │   │   │   └── v1/
│   │   │   │       ├── __init__.py
│   │   │   │       ├── auth.py         # /auth/register, login, refresh, logout, me
│   │   │   │       ├── agencies.py     # /agencies/current
│   │   │   │       ├── workspaces.py   # /workspaces (list, create)
│   │   │   │       ├── health.py      # /health, /health/ready
│   │   │   │       └── super_admin/
│   │   │   │           ├── __init__.py
│   │   │   │           └── auth.py     # /super-admin/auth/login, logout, me
│   │   │   ├── core/
│   │   │   │   ├── __init__.py
│   │   │   │   └── config.py           # Settings (pydantic-settings)
│   │   │   ├── db/
│   │   │   │   ├── __init__.py
│   │   │   │   └── database.py         # engine, SessionLocal, get_db
│   │   │   ├── models/
│   │   │   │   └── __init__.py         # all SQLAlchemy models
│   │   │   ├── schemas/
│   │   │   │   └── __init__.py         # all Pydantic schemas
│   │   │   ├── dependencies/
│   │   │   │   └── __init__.py         # get_current_user, get_tenant_context, require_role
│   │   │   ├── middleware/
│   │   │   │   ├── __init__.py
│   │   │   │   └── tenant_context.py  # TenantContextMiddleware
│   │   │   ├── security/
│   │   │   │   ├── __init__.py
│   │   │   │   └── jwt.py              # Argon2id, JWT, Fernet
│   │   │   └── tenancy/
│   │   │       ├── __init__.py
│   │   │       └── context.py         # TenantContext, set_tenant_context, assert_tenant_owned
│   │   ├── migrations/
│   │   │   ├── env.py
│   │   │   ├── script.py.mako
│   │   │   └── versions/
│   │   │       └── 0001_initial.py     # all tables + RLS + roles
│   │   ├── scripts/
│   │   │   └── create_super_admin.py  # CLI bootstrap
│   │   └── tests/
│   │       ├── __init__.py
│   │       ├── conftest.py             # fixtures: db_engine, db_session, client, agency_a, agency_b
│   │       ├── unit/
│   │       │   ├── __init__.py
│   │       │   └── test_security_and_utils.py
│   │       └── integration/
│   │           ├── __init__.py
│   │           └── test_security_tenant_isolation.py
│   │
│   ├── web/                            # Next.js frontend (Agency Portal surface)
│   │   ├── Dockerfile
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   ├── next.config.ts
│   │   ├── tailwind.config.ts
│   │   ├── postcss.config.js
│   │   ├── .eslintrc.js
│   │   ├── next-env.d.ts
│   │   └── src/
│   │       ├── app/
│   │       │   ├── layout.tsx          # root layout + Providers
│   │       │   ├── page.tsx            # landing page
│   │       │   ├── globals.css         # Tailwind + brand color
│   │       │   ├── login/page.tsx
│   │       │   ├── register/page.tsx
│   │       │   └── dashboard/page.tsx
│   │       ├── components/
│   │       │   ├── providers.tsx       # TanStack Query provider
│   │       │   └── dashboard-shell.tsx # authenticated shell
│   │       └── lib/
│   │           ├── api-client.ts      # typed API client
│   │           └── utils.ts            # cn() helper
│   │
│   └── widget/                        # scaffold only (Phase 5+)
│       └── src/
│           └── .gitkeep
│
├── packages/
│   └── shared/                        # scaffold only (future shared TS types)
│       └── .gitkeep
│
├── infrastructure/
│   ├── docker/                        # future Dockerfiles for prod
│   ├── database/                      # future DB scripts
│   └── deployment/                    # future Caddy/K8s configs
│
├── docs/
│   ├── architecture/
│   │   ├── overview.md
│   │   └── phase-1.md
│   ├── security/
│   │   ├── tenant-isolation.md
│   │   └── authentication.md
│   ├── database/
│   │   └── schema.md
│   └── development/
│       ├── local-setup.md
│       ├── environment.md
│       └── testing.md
│
└── scripts/
    └── .gitkeep                       # operational scripts (future)
```

### 2.2 File count estimate

| Section | Files | Lines (approx) |
|---|---|---|
| Root configs | 6 | 200 |
| Backend (`apps/api/`) | 35 | 4,500 |
| Frontend (`apps/web/`) | 18 | 600 |
| Widget scaffold | 1 | 0 |
| Shared package scaffold | 1 | 0 |
| Infrastructure | 3 | 50 |
| Docs | 9 | 2,500 |
| Scripts (empty) | 1 | 0 |
| **Total** | **74** | **~7,850** |

---

## 3. Database Schema Design

### 3.1 Tables (11 total)

#### Identity tables

##### Table 1: `super_admins`
Platform-level administrator. Separate from `users` — separate JWT signing key, separate auth flow, separate audit log.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID PK | `gen_random_uuid()` |
| `email` | VARCHAR(320) | UNIQUE NOT NULL |
| `password_hash` | TEXT | NOT NULL (Argon2id) |
| `name` | VARCHAR(160) | NOT NULL |
| `is_active` | BOOLEAN | DEFAULT true |
| `mfa_secret_encrypted` | TEXT | nullable (Fernet) |
| `mfa_enabled` | BOOLEAN | DEFAULT false |
| `failed_mfa_attempts` | INTEGER | DEFAULT 0 |
| `locked_until` | TIMESTAMPTZ | nullable (temporary cooldown) |
| `last_login_at` | TIMESTAMPTZ | nullable |
| `created_at`, `updated_at` | TIMESTAMPTZ | DEFAULT now() |

**RLS:** No (not tenant-scoped).

##### Table 2: `users`
Global identity. A user may belong to multiple agencies. `email` is globally unique.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID PK | `gen_random_uuid()` |
| `email` | VARCHAR(320) | UNIQUE NOT NULL |
| `password_hash` | TEXT | NOT NULL (Argon2id) |
| `name` | VARCHAR(160) | NOT NULL |
| `is_active` | BOOLEAN | DEFAULT true |
| `last_login_at` | TIMESTAMPTZ | nullable |
| `created_at`, `updated_at` | TIMESTAMPTZ | DEFAULT now() |

**RLS:** No (not tenant-scoped — identity is global).

#### Tenant tables

##### Table 3: `agencies`
Tenant root.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID PK | `gen_random_uuid()` |
| `name` | VARCHAR(180) | NOT NULL |
| `slug` | VARCHAR(80) | UNIQUE NOT NULL |
| `brand_color` | VARCHAR(20) | DEFAULT '#FF6B35' |
| `is_active` | BOOLEAN | DEFAULT true |
| `created_at`, `updated_at` | TIMESTAMPTZ | DEFAULT now() |

**RLS:** Yes — filter on `id::text = current_setting('app.tenant_id', true)`.

##### Table 4: `workspaces`
Sub-organization within an agency.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID PK | |
| `agency_id` | UUID FK → agencies | NOT NULL, indexed |
| `name`, `slug`, `timezone`, `is_active` | | |
| Unique | `(agency_id, slug)` | prevents dup slugs within agency |

**RLS:** Yes — filter on `agency_id`.

##### Table 5: `agency_memberships`
User ↔ Agency link with role.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID FK → users | NOT NULL, indexed |
| `agency_id` | UUID FK → agencies | NOT NULL, indexed |
| `role` | VARCHAR(30) | CHECK in ('owner','admin','manager','agent','viewer') |
| Unique | `(user_id, agency_id)` | one membership per (user, agency) — also serves as composite FK target |

**RLS:** Yes — filter on `agency_id`.

##### Table 6: `teams`
Team within a workspace.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID PK | |
| `workspace_id` | UUID FK → workspaces | NOT NULL, indexed |
| `agency_id` | UUID FK → agencies | NOT NULL, indexed (denormalised for RLS) |
| `name`, `is_default` | | |
| Unique | `(workspace_id, name)` | no dup names within workspace |
| Unique | `(id, agency_id)` | target for composite FK from team_memberships |

**RLS:** Yes — filter on `agency_id`.

##### Table 7: `team_memberships`
User ↔ Team link. Composite FK prevents cross-agency team assignments.

| Column | Type | Constraints |
|---|---|---|
| `team_id` | UUID FK → teams | PK, NOT NULL |
| `user_id` | UUID FK → users | PK, NOT NULL |
| `agency_id` | UUID FK → agencies | PK, NOT NULL |
| Composite FK | `(team_id, agency_id) → teams(id, agency_id)` | ON DELETE CASCADE |

**RLS:** Yes — filter on `agency_id`.

##### Table 8: `contacts`
Customer records.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID PK | |
| `workspace_id` | UUID FK → workspaces | NOT NULL, indexed |
| `agency_id` | UUID FK → agencies | NOT NULL, indexed |
| `email`, `phone`, `name` | | |
| Unique | `(workspace_id, email)` | one email per workspace |
| Unique | `(id, workspace_id, agency_id)` | target for composite FK from conversations |

**RLS:** Yes — filter on `agency_id`.

##### Table 9: `conversations`
Conversation thread.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID PK | |
| `workspace_id` | UUID FK → workspaces | NOT NULL, indexed |
| `agency_id` | UUID FK → agencies | NOT NULL, indexed |
| `contact_id` | UUID | NOT NULL |
| `assigned_user_id` | UUID | nullable |
| `assigned_team_id` | UUID | nullable |
| `subject`, `status` | | CHECK status in ('open','pending','resolved','closed') |
| Composite FK 1 | `(contact_id, workspace_id, agency_id) → contacts(id, workspace_id, agency_id)` | ON DELETE RESTRICT |
| Composite FK 2 | `(assigned_user_id, agency_id) → agency_memberships(user_id, agency_id)` | ON DELETE SET NULL |
| Composite FK 3 | `(assigned_team_id, agency_id) → teams(id, agency_id)` | ON DELETE SET NULL |

**RLS:** Yes — filter on `agency_id`.

#### Audit tables

##### Table 10: `audit_logs`
Agency-scoped security audit log. `ON DELETE RESTRICT` on `agency_id` prevents deleting an agency with audit history.

| Column | Type | Constraints |
|---|---|---|
| `id` | SERIAL PK | |
| `agency_id` | UUID FK → agencies | NOT NULL, ON DELETE RESTRICT, indexed |
| `actor_user_id` | UUID FK → users | nullable, ON DELETE SET NULL |
| `action`, `target_type`, `target_id` | | |
| `metadata` | JSONB | DEFAULT '{}' |
| `ip_address`, `user_agent` | | |
| `created_at` | TIMESTAMPTZ | DEFAULT now() |
| Index | `(agency_id, created_at)` | for tenant-scoped queries |

**RLS:** Yes — filter on `agency_id`.

##### Table 11: `super_admin_audit_logs`
Separate audit log for Super Admin actions.

| Column | Type | Constraints |
|---|---|---|
| `id` | SERIAL PK | |
| `super_admin_id` | UUID FK → super_admins | nullable, ON DELETE SET NULL |
| `action`, `target_type`, `target_id`, `metadata`, `ip_address` | | |
| `created_at` | TIMESTAMPTZ | DEFAULT now() |

**RLS:** No (not tenant-scoped).

### 3.2 Composite Foreign Keys (4 total)

| # | Name | Child → Parent | Prevents |
|---|---|---|---|
| 1 | `fk_team_memberships_team_agency` | `team_memberships(team_id, agency_id)` → `teams(id, agency_id)` | Cross-agency team membership |
| 2 | `fk_conversations_contact_workspace` | `conversations(contact_id, workspace_id, agency_id)` → `contacts(id, workspace_id, agency_id)` | Cross-workspace contact reference |
| 3 | `fk_conversations_assignee_agency` | `conversations(assigned_user_id, agency_id)` → `agency_memberships(user_id, agency_id)` | Cross-agency user assignment |
| 4 | `fk_conversations_team_agency` | `conversations(assigned_team_id, agency_id)` → `teams(id, agency_id)` | Cross-agency team assignment |

**Required UNIQUE constraints on parents:**
- `uq_teams_id_agency` on `teams(id, agency_id)`
- `uq_contacts_id_ws_agency` on `contacts(id, workspace_id, agency_id)`
- `uq_memberships_user_agency` on `agency_memberships(user_id, agency_id)` — already exists as the natural unique key

### 3.3 RLS Policies (8 tenant-owned tables)

All tenant-owned tables have:
```sql
ENABLE ROW LEVEL SECURITY;
FORCE ROW LEVEL SECURITY;  -- applies even to table owner
```

**Pattern for `agencies`:**
```sql
CREATE POLICY tenant_isolation_agencies ON agencies
USING (
    current_setting('app.bypass_rls', true) = 'on'
    OR id::text = current_setting('app.tenant_id', true)
)
WITH CHECK (
    current_setting('app.bypass_rls', true) = 'on'
    OR id::text = current_setting('app.tenant_id', true)
);
```

**Pattern for all other tenant tables** (`workspaces`, `agency_memberships`, `teams`, `team_memberships`, `contacts`, `conversations`, `audit_logs`):
```sql
CREATE POLICY tenant_isolation_<table> ON <table>
USING (
    current_setting('app.bypass_rls', true) = 'on'
    OR agency_id::text = current_setting('app.tenant_id', true)
)
WITH CHECK (
    current_setting('app.bypass_rls', true) = 'on'
    OR agency_id::text = current_setting('app.tenant_id', true)
);
```

**Behaviour:**
- `app.tenant_id` unset → returns empty string → RLS fails closed (no rows visible)
- `app.tenant_id` set to UUID → only rows matching `agency_id` (or `id` for agencies) visible
- `app.bypass_rls = 'on'` → all rows visible (Super Admin only, transaction-scoped via `SET LOCAL`)

### 3.4 Database roles

| Role | Privileges | Purpose |
|---|---|---|
| `m369_app` (login) | CRUD on all tables, member of `m369_super_admin` | Application login role (NOT a PostgreSQL superuser) |
| `m369_super_admin` (NOLOGIN) | None directly — only used for `SET LOCAL app.bypass_rls = 'on'` authorization | Group role granted to `m369_app` |

**Critical:** `m369_app` must NOT be a PostgreSQL superuser. Superusers bypass RLS entirely, even with `FORCE ROW LEVEL SECURITY`. The migration creates both roles and grants membership.

---

## 4. API Design

### 4.1 Versioning

All routes under `/api/v1/`. Super Admin under `/api/v1/super-admin/`.

### 4.2 Phase 1 endpoints (14 total)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | None | Liveness check |
| GET | `/api/v1/health` | None | Liveness (versioned) |
| GET | `/api/v1/health/ready` | None | Readiness (DB ping) |
| POST | `/api/v1/auth/register` | None (gated) | Register first agency + owner |
| POST | `/api/v1/auth/login` | None | Login with email + password |
| POST | `/api/v1/auth/refresh` | Refresh token | Issue new access token |
| POST | `/api/v1/auth/logout` | None | Clear auth cookies |
| GET | `/api/v1/auth/me` | Agency JWT | Current user + memberships |
| GET | `/api/v1/agencies/current` | Agency JWT | Current agency |
| GET | `/api/v1/workspaces` | Agency JWT | List workspaces in current agency |
| POST | `/api/v1/workspaces` | Agency JWT (owner/admin) | Create workspace |
| POST | `/api/v1/super-admin/auth/login` | None | Super Admin login |
| POST | `/api/v1/super-admin/auth/logout` | Super Admin JWT | Super Admin logout |
| GET | `/api/v1/super-admin/auth/me` | Super Admin JWT | Super Admin profile |

### 4.3 JWT design

**Three token classes:**

| Class | `type` claim | Signing key | Decoder | Lifetime |
|---|---|---|---|---|
| Agency access | `"agency"` | `JWT_SECRET_KEY` | `decode_access_token` | 7 days |
| Super Admin access | `"super_admin"` | `JWT_SUPER_ADMIN_SECRET_KEY` | `decode_super_admin_token` | 7 days |
| Refresh | `"refresh"` | Same as access sibling | `decode_refresh_token` | 30 days |

**Required claims:**
```json
{
  "sub": "<user_uuid>",
  "type": "agency",
  "exp": 1735689600,
  "iat": 1735686000,
  "iss": "m369.support",
  "aud": "m369.support.api",
  "jti": "<random_hex>",
  "agency_id": "<agency_uuid>"  // only for agency tokens
}
```

**Type-strict decoding:** each decoder only accepts its own `type` claim. Even if signing keys were misconfigured to match, the type claim mismatch still blocks cross-class replay.

### 4.4 Authentication

- **Password hashing:** Argon2id (RFC 9106) — `time_cost=3, memory_cost=65536 KiB (64 MiB), parallelism=2, type=ID`
- **Cookies:** HTTP-only, `Secure` (production), `SameSite=Lax` (default)
  - `access_token` — path `/`, max-age = access token lifetime
  - `refresh_token` — path `/api/v1/auth` (more restricted), max-age = refresh token lifetime
  - `super_admin_access_token` — separate cookie for Super Admin

### 4.5 Authorization (RBAC)

| Role | Permissions (Phase 1) |
|---|---|
| `owner` | Full agency control (one per agency, required at creation) |
| `admin` | All operations except deleting the agency |
| `manager` | Manage teams, workspaces, conversations; cannot manage users |
| `agent` | Handle conversations, contacts; cannot create workspaces |
| `viewer` | Read-only access |

Roles stored in `agency_memberships.role`, checked via `require_role(*allowed)` dependency factory.

### 4.6 Tenant context flow

```
1. Request arrives with cookie "access_token" OR Authorization: Bearer <token>
2. TenantContextMiddleware:
   a. Extract token
   b. Try decode_access_token (agency) → if None, try decode_super_admin_token
   c. Build TenantContext(agency_id, user_id, is_super_admin, raw_token)
   d. Store on request.state.tenant
3. get_current_agency_id dependency:
   a. Read TenantContext from request.state
   b. Look up AgencyMembership(user_id, agency_id) — confirm membership
   c. Return agency_id (or 403 if not a member)
4. Before any tenant-owned query:
   SET LOCAL app.tenant_id = '<agency_uuid>'  -- transaction-scoped
5. RLS policies filter rows automatically
6. assert_tenant_owned(record, agency_id) — defense-in-depth check
```

**`SET LOCAL` behaviour:** scoped to the current transaction. When the transaction commits or rolls back, the GUC is reset. Pooled connections cannot leak tenant scope to the next request.

---

## 5. Test Plan

### 5.1 Test pyramid (Phase 1)

| Level | Count | Database | Purpose |
|---|---|---|---|
| Unit | 7 | None | Password hashing, JWT round-trip, slugs |
| Integration | 15 | Real PostgreSQL 16 | RLS, composite FK, JWT lifecycle, auth, authorization |
| E2E | 0 | — | (Phase 2+) |
| **Total** | **22** | | |

### 5.2 Test inventory

#### Unit tests (7) — `tests/unit/test_security_and_utils.py`

| # | Test | Verifies |
|---|---|---|
| 1 | `test_password_hash_round_trip` | Argon2id hash → verify |
| 2 | `test_password_hash_unique_per_call` | Same password → different hashes |
| 3 | `test_agency_token_round_trip` | create_access_token(agency) → decode_access_token |
| 4 | `test_super_admin_token_round_trip` | create_access_token(super_admin) → decode_super_admin_token |
| 5 | `test_garbage_token_rejected` | `decode_access_token("not.a.jwt")` → None |
| 6 | `test_slugify_basic` | slugify("Hello World") → "hello-world" |
| 7 | `test_slugify_unicode` | slugify("Café 2026") → "cafe-2026" |

#### Integration tests (15) — `tests/integration/test_security_tenant_isolation.py`

| # | Test | Verifies |
|---|---|---|
| 1 | `test_agency_a_cannot_read_agency_b_data` | RLS blocks cross-tenant SELECT |
| 2 | `test_agency_a_cannot_modify_agency_b_record` | RLS blocks cross-tenant UPDATE (rowcount=0) |
| 3 | `test_agency_a_cannot_delete_agency_b_record` | RLS blocks cross-tenant DELETE (rowcount=0) |
| 4 | `test_workspace_access_without_membership_is_empty` | No tenant context → no data |
| 5 | `test_conversation_cannot_assign_foreign_agency_user` | Composite FK blocks cross-agency assignment |
| 6 | `test_conversation_cannot_reference_foreign_workspace_contact` | Composite FK blocks cross-workspace contact ref |
| 7 | `test_missing_tenant_context_blocks_all_data` | RLS fail-closed when `app.tenant_id` unset |
| 8 | `test_tenant_context_does_not_leak_between_transactions` | `SET LOCAL` is transaction-scoped |
| 9 | `test_expired_token_rejected` | Expired JWT → None |
| 10 | `test_invalid_signature_rejected` | Wrong signing key → None |
| 11 | `test_wrong_token_type_rejected` | Agency token cannot be decoded as super_admin (and vice versa) |
| 12 | `test_unauthenticated_request_rejected` | No token → 401 |
| 13 | `test_unauthenticated_workspace_list_rejected` | No token on /workspaces → 401 |
| 14 | `test_authorization_role_check` | Agent role cannot create workspace → 403 |
| 15 | `test_team_membership_cannot_reference_foreign_agency_team` | Composite FK on team_memberships |

### 5.3 Test fixtures

| Fixture | Scope | Purpose |
|---|---|---|
| `db_engine` | session | Set up schema + RLS policies once |
| `db_session` | function | Per-test DB session; truncates tables at start |
| `client` | function | FastAPI TestClient with overridden `get_db` |
| `agency_a` | function | Tuple `(Agency, User, JWT)` for tenant A |
| `agency_b` | function | Tuple `(Agency, User, JWT)` for tenant B (independent) |

### 5.4 Test status definitions

- **PASS:** Test was actually executed and succeeded
- **FAIL:** Test was executed and failed
- **BLOCKED:** Could not be executed due to documented environmental limitation
- **NOT RUN:** Was not executed

**Never report PASS based on code inspection alone.** All 22 tests will be executed against real PostgreSQL 16 via `pgserver` embedded binary. SQLite is NOT substituted — RLS is Postgres-specific.

### 5.5 Coverage targets

| Layer | Target |
|---|---|
| Services (business logic) | ≥ 80% |
| Repositories (data access) | ≥ 90% |
| Security-critical paths | ≥ 95% |
| API endpoints | ≥ 70% |

---

## 6. Implementation Plan (8 commits)

### 6.1 Commit sequence

Each commit is independently pushable. If session ends mid-way, completed commits are preserved on GitHub.

| # | Commit | Files | Lines | Tests | Pushable? |
|---|---|---|---|---|---|
| 1 | `Foundation: monorepo skeleton + configs` | 6 | 200 | None | ✅ |
| 2 | `Backend: deps + config + database + security` | 9 | 700 | None (just imports) | ✅ |
| 3 | `Backend: models + migration 0001 (RLS + composite FK)` | 3 | 600 | None (migration only) | ✅ |
| 4 | `Backend: tenant context + middleware + dependencies` | 5 | 350 | None (just imports) | ✅ |
| 5 | `Backend: API endpoints + schemas` | 9 | 500 | None (just imports) | ✅ |
| 6 | `Backend: tests + 22 tests passing` | 4 | 800 | ✅ 22/22 PASS | ✅ |
| 7 | `Frontend: Next.js app + login + dashboard` | 18 | 600 | Build verified | ✅ |
| 8 | `Docs: architecture + security + database + dev` | 9 | 2,500 | None | ✅ |

### 6.2 Test execution plan

- After commit 6: run `pytest tests/ -v` against real PostgreSQL, capture raw output, save to `/home/z/my-project/download/phase-1-test-output.txt`
- After commit 7: run `npm run build`, capture build output, run `Complete(project_type="web_dev")` to generate preview URL
- After commit 8: deliver final report with SHA-256 checksums

### 6.3 Post-verification (after all commits)

1. SHA-256 of all files in repo
2. Final test run with raw output
3. Frontend build output
4. Preview URL for Owner to test on Android browser
5. Delivery report with commit hashes, branch URL, file list

---

## 7. Security Hardening Checklist

| # | Item | Status (Phase 1) |
|---|---|---|
| 1 | Argon2id password hashing (RFC 9106) | ✅ |
| 2 | JWT with `type` claim + separate signing keys | ✅ |
| 3 | Type-strict decoders (no cross-class replay) | ✅ |
| 4 | HTTP-only cookies with Secure + SameSite | ✅ |
| 5 | JWT issuer + audience validation | ✅ |
| 6 | JWT expiry enforcement | ✅ |
| 7 | Refresh token rotation | ✅ (single-use per rotation) |
| 8 | RLS on all tenant-owned tables (8 tables) | ✅ |
| 9 | FORCE ROW LEVEL SECURITY | ✅ |
| 10 | Composite FK constraints (4 constraints) | ✅ |
| 11 | `SET LOCAL app.tenant_id` (transaction-scoped) | ✅ |
| 12 | `assert_tenant_owned()` defense-in-depth check | ✅ |
| 13 | `get_current_agency_id` membership verification | ✅ |
| 14 | RBAC with 5 roles | ✅ |
| 15 | Super Admin separate auth surface | ✅ |
| 16 | Audit log table (RESTRICT on agency delete) | ✅ (table only; writing entries is Phase 2) |
| 17 | Rate limiting on auth endpoints | ⚠️ (slowapi in deps; wiring is Phase 2) |
| 18 | JWT revocation list (Redis-backed) | ❌ Phase 2 |
| 19 | MFA enforcement for Super Admin | ❌ Phase 14 |
| 20 | Frontend tests (Vitest/Playwright) | ❌ Phase 2+ |

---

## 8. Deferred to Later Phases

| Feature | Phase |
|---|---|
| Full inbox & conversation management UI | Phase 3 |
| Messaging channels (WhatsApp, email, Telegram) | Phase 5+ |
| Knowledge base | Phase 4 |
| Customer portal | Phase 4 |
| Automation rules engine | Phase 6 |
| SLA policies | Phase 6 |
| Reporting dashboards | Phase 7 |
| Subscription & billing | Phase 9 |
| Super Admin dashboard UI | Phase 9 |
| i18n / multi-language (fa, en, ar, tr, ru + RTL) | Phase 11 |
| Mobile apps | Phase 16 |
| AI assistant / Copilot | Phase 13 |
| Custom domains / White-label | Phase 15 |
| JWT revocation list | Phase 2 |
| MFA enforcement | Phase 14 |
| Frontend tests | Phase 2+ |
| Production deployment (VPS + Caddy) | Phase 19 |

---

## 9. Open Decisions (no blockers — sensible defaults applied)

| # | Decision | Default chosen | Rationale |
|---|---|---|---|
| 1 | Brand color | `#FF6B35` (vivid orange) | Distinct, visible, modern |
| 2 | Default language | English | Most agencies expected internationally |
| 3 | JWT access token lifetime | 7 days | Balances security vs UX |
| 4 | Refresh token lifetime | 30 days | Allows re-login within a month |
| 5 | Argon2id params | t=3, m=64MiB, p=2 | RFC 9106 recommended for server-side |
| 6 | API version | v1 | Standard convention |
| 7 | Frontend framework | Next.js 15 (App Router) | Industry standard, RSC support |
| 8 | CSS framework | Tailwind 3.4 (stable, not 4.x yet) | 4.x has breaking changes; 3.4 is stable |
| 9 | Database | PostgreSQL 16 | Latest stable, RLS mature |
| 10 | Cache | Redis 7 | For rate limiting + future queues |

**Owner may override any of these before implementation starts.** Otherwise, defaults will be applied.

---

## 10. Risk Assessment

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| 1 | Sandbox recycled mid-implementation | High | Commit + push after each logical unit (8 commits) |
| 2 | PAT leaked in chat history | Medium | Owner revokes PAT after each session; uses short-expiry PATs |
| 3 | pgserver unavailable in new session | Medium | Re-install on demand; if fails, integration tests marked BLOCKED (not PASS) |
| 4 | Frontend preview URL not accessible from Android | Low | Use `Complete()` tool which generates `https://preview-<bot-id>.space-z.ai/` — public HTTPS, mobile-friendly |
| 5 | Dependency version conflict | Low | All versions verified compatible in prior session; locked in `requirements.txt` and `package.json` |
| 6 | RLS policy mistake (false sense of security) | High | 15 integration tests verify RLS behaviour, including fail-closed and leak-prevention |
| 7 | Composite FK requires UNIQUE constraint on parent | Medium | Explicitly added `uq_teams_id_agency` and `uq_contacts_id_ws_agency` |
| 8 | Application role accidentally a PostgreSQL superuser | High | Migration creates non-superuser `m369_app` role; documented in `docs/security/tenant-isolation.md` |

---

## 11. Verification Plan (post-implementation)

After all 8 commits are pushed:

1. **Clone fresh** from GitHub to verify push was complete
2. **Run migration** `alembic upgrade head` against a clean PostgreSQL
3. **Run tests** `pytest tests/ -v` — expect 22/22 PASS
4. **Frontend build** `npm run build` — expect 5 routes compiled
5. **Preview URL** via `Complete(project_type="web_dev")` — Owner tests on Android
6. **SHA-256 checksums** of all delivered artifacts

---

## 12. Awaiting Owner Action

```
✅ Technical design complete
✅ Database schema specified (11 tables, 4 composite FKs, 8 RLS policies)
✅ API design specified (14 endpoints)
✅ Test plan specified (22 tests, real PostgreSQL)
✅ Implementation plan specified (8 commits, each independently pushable)
✅ Security hardening checklist (20 items, 16 in Phase 1)
✅ Risk assessment (8 risks, mitigations defined)

⏸️ Awaiting GitHub PAT (new, scoped to m369-support only)

Once PAT received:
  → Create branch phase-1/foundation off main
  → Execute 8 commits sequentially
  → Push after each commit
  → Run tests with real PostgreSQL
  → Generate frontend preview URL
  → Deliver final report with all SHA-256 checksums
```

**No code will be written until PAT is received.** This design document is the complete technical specification — once approved (or with modifications), implementation can begin immediately upon PAT receipt.

---

**End of design document.**

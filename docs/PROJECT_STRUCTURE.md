# Project Structure

> **Generated from:** `git ls-files` at commit `2e44f6b75293fae675fa8e9e4a88d64f74c32e8d`
> **Tracked files:** 132 (verified via `git ls-files | wc -l`)
> **Branch:** `phase-1/agency-auth-integration-closure`

Every file below is a Git-tracked file. No files are invented or omitted.

---

## Complete Tracked File Tree

```
.env.example
.gitignore
LICENSE
Makefile
README.md
STATE.md
apps/api/Dockerfile
apps/api/alembic.ini
apps/api/app/__init__.py
apps/api/app/api/__init__.py
apps/api/app/api/v1/__init__.py
apps/api/app/api/v1/agencies.py
apps/api/app/api/v1/audit_logs.py
apps/api/app/api/v1/auth.py
apps/api/app/api/v1/canned_responses.py
apps/api/app/api/v1/channels.py
apps/api/app/api/v1/contacts.py
apps/api/app/api/v1/conversations.py
apps/api/app/api/v1/health.py
apps/api/app/api/v1/kb.py
apps/api/app/api/v1/messages.py
apps/api/app/api/v1/super_admin/__init__.py
apps/api/app/api/v1/super_admin/agencies.py
apps/api/app/api/v1/super_admin/auth.py
apps/api/app/api/v1/super_admin/payments.py
apps/api/app/api/v1/super_admin/plans.py
apps/api/app/api/v1/super_admin/settings_notes_audit.py
apps/api/app/api/v1/super_admin/subscriptions.py
apps/api/app/api/v1/teams.py
apps/api/app/api/v1/workspaces.py
apps/api/app/core/__init__.py
apps/api/app/core/config.py
apps/api/app/db/__init__.py
apps/api/app/db/database.py
apps/api/app/dependencies/__init__.py
apps/api/app/main.py
apps/api/app/middleware/__init__.py
apps/api/app/middleware/tenant_context.py
apps/api/app/models/__init__.py
apps/api/app/models/phase1_extended.py
apps/api/app/schemas/__init__.py
apps/api/app/schemas/audit.py
apps/api/app/schemas/channels_kb.py
apps/api/app/schemas/common.py
apps/api/app/schemas/conversations.py
apps/api/app/schemas/super_admin.py
apps/api/app/schemas/teams.py
apps/api/app/security/__init__.py
apps/api/app/security/jwt.py
apps/api/app/services/__init__.py
apps/api/app/services/audit.py
apps/api/app/services/billing.py
apps/api/app/services/rate_limit.py
apps/api/app/services/sa_auth.py
apps/api/app/slugs.py
apps/api/app/tenancy/__init__.py
apps/api/app/tenancy/context.py
apps/api/migrations/env.py
apps/api/migrations/script.py.mako
apps/api/migrations/versions/0001_initial.py
apps/api/migrations/versions/0002_remove_admin_login.py
apps/api/migrations/versions/0003_login_helper_function.py
apps/api/migrations/versions/0004_fix_login_helper_acl.py
apps/api/migrations/versions/0005_restrict_login_helper_owner.py
apps/api/migrations/versions/0006_phase1_extended.py
apps/api/migrations/versions/0007_fix_login_reader_acl.py
apps/api/migrations/versions/0008_create_sa_runner_role.py
apps/api/migrations/versions/0009_widen_paid_currency.py
apps/api/migrations/versions/0010_sa_auth_hardening.py
apps/api/migrations/versions/0011_tenant_isolation_hardening.py
apps/api/migrations/versions/0012_package_b1_critical_corrections.py
apps/api/migrations/versions/0013_package_b1_2_final_security.py
apps/api/migrations/versions/0014_agency_user_token_version.py
apps/api/pyproject.toml
apps/api/requirements-dev.txt
apps/api/requirements.txt
apps/api/scripts/create_super_admin.py
apps/api/scripts/provision_sa_auth_role.py
apps/api/tests/__init__.py
apps/api/tests/conftest.py
apps/api/tests/integration/__init__.py
apps/api/tests/integration/test_auth_tenant_context.py
apps/api/tests/integration/test_rls_bypass_attack.py
apps/api/tests/integration/test_security_tenant_isolation.py
apps/api/tests/integration/test_stage2_api_rbac.py
apps/api/tests/integration/test_stage3_super_admin_billing.py
apps/api/tests/integration/test_stage4_security_audit.py
apps/api/tests/integration/test_stage5_package_a1_corrections.py
apps/api/tests/integration/test_stage5_package_a2_1_corrections.py
apps/api/tests/integration/test_stage5_package_a2_corrections.py
apps/api/tests/integration/test_stage5_sa_auth_hardening.py
apps/api/tests/integration/test_stage6_package_b1_1_corrections.py
apps/api/tests/integration/test_stage6_package_b1_corrections.py
apps/api/tests/integration/test_stage6_package_b_tenant_isolation.py
apps/api/tests/integration/test_stage7_package_b1_2_final_security.py
apps/api/tests/integration/test_stage8_agency_token_revocation.py
apps/api/tests/unit/__init__.py
apps/api/tests/unit/test_compose_isolation.py
apps/api/tests/unit/test_config.py
apps/api/tests/unit/test_security_and_utils.py
apps/web/.eslintrc.js
apps/web/next.config.ts
apps/web/package-lock.json
apps/web/package.json
apps/web/postcss.config.js
apps/web/src/app/dashboard/page.tsx
apps/web/src/app/globals.css
apps/web/src/app/layout.tsx
apps/web/src/app/login/page.tsx
apps/web/src/app/page.tsx
apps/web/src/app/register/page.tsx
apps/web/src/components/dashboard-shell.tsx
apps/web/src/components/providers.tsx
apps/web/src/lib/api-client.ts
apps/web/tailwind.config.ts
apps/web/tsconfig.json
apps/widget/src/.gitkeep
docker-compose.yml
docs/PHASE1_BACKEND_CONTINUATION.md
docs/PROJECT_STRUCTURE.md
docs/architecture/overview.md
docs/architecture/phase-1.md
docs/database/schema.md
docs/development/environment.md
docs/development/local-setup.md
docs/development/testing.md
docs/security/README.md
docs/security/agency-session-revocation.md
docs/security/authentication.md
docs/security/tenant-isolation.md
infrastructure/database/01-bootstrap-roles.sql
packages/shared/.gitkeep
```

---

## Key Directory Purposes

| Directory | Purpose |
|---|---|
| `apps/api/` | Backend — FastAPI application, migrations, tests, scripts |
| `apps/api/app/` | Application code (models, schemas, API routers, services, security) |
| `apps/api/app/api/v1/` | API v1 route handlers (agency + Super Admin endpoints) |
| `apps/api/app/api/v1/super_admin/` | Super Admin route handlers (auth, agencies, plans, subscriptions, payments, settings) |
| `apps/api/app/core/` | Configuration (settings, env vars, production guard) |
| `apps/api/app/db/` | Database engines, session factories, `get_db` / `get_super_admin_db` / `get_super_admin_auth_db` |
| `apps/api/app/dependencies/` | Auth dependencies: `get_current_user`, `get_super_admin_context`, `require_role` |
| `apps/api/app/middleware/` | `TenantContextMiddleware` (resolves JWT → `request.state`) |
| `apps/api/app/models/` | SQLAlchemy models (Agency, User, Conversation, Message, Plan, etc.) |
| `apps/api/app/schemas/` | Pydantic schemas (request/response validation) |
| `apps/api/app/security/` | Argon2id, JWT (agency/super_admin/mfa_challenge/refresh), Fernet encryption |
| `apps/api/app/services/` | Business logic (audit, billing, SA auth, rate limiting) |
| `apps/api/app/tenancy/` | Tenant context (`set_tenant_context`, `TenantContext` dataclass) |
| `apps/api/migrations/versions/` | Alembic migrations (0001–0014) |
| `apps/api/scripts/` | CLI scripts (create_super_admin, provision_sa_auth_role) |
| `apps/api/tests/` | Unit + integration tests (conftest with dual-connection fixtures) |
| `apps/web/` | Frontend — Next.js 15 application |
| `apps/web/src/app/` | Next.js App Router pages (layout, login, register, dashboard) |
| `apps/web/src/components/` | React components (dashboard-shell, providers) |
| `apps/web/src/lib/` | API client (`api-client.ts`), utilities (`utils.ts`) |
| `apps/widget/` | Embeddable widget (scaffolded, not yet implemented) |
| `infrastructure/database/` | PostgreSQL bootstrap SQL (role provisioning) |
| `packages/shared/` | Shared TypeScript types (scaffolded, future) |
| `docs/` | All project documentation |

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

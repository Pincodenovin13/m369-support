# Phase 1 — Foundation + Multi-Tenancy + Security Hardening

## Scope

Phase 1 establishes the technical foundation for M369 Support, including full
multi-tenancy, authentication, RBAC, and comprehensive security hardening.

### Implemented and Tested

- ✅ Monorepo structure (apps/api, apps/web, apps/widget, packages/, infrastructure/, docs/)
- ✅ Backend: FastAPI 0.115 + SQLAlchemy 2.0 + Alembic + Pydantic 2 + psycopg 3
- ✅ Frontend: Next.js 15 + React 19 + TypeScript + Tailwind CSS + TanStack Query
- ✅ Database schema: 25 tables (excluding alembic_version) with RLS on 16 tenant-owned tables
- ✅ 14 composite FK constraints preventing cross-tenant references
- ✅ JWT with `type` claim + separate signing keys (agency vs super_admin)
- ✅ Argon2id password hashing (RFC 9106)
- ✅ Auth flow: register, login, refresh (JSON + cookie), logout (server-side revocation), /me
- ✅ Tenant context middleware + `SET LOCAL app.tenant_id` (transaction-scoped)
- ✅ Role-based access control (owner, admin, manager, agent, viewer)
- ✅ ~80 API endpoints (agency + Super Admin)
- ✅ 346 tests executed against real PostgreSQL 16.2 — ALL PASS
- ✅ Docker Compose for local development
- ✅ CLI script for creating the first Super Admin
- ✅ Super Admin authentication with TOTP MFA (RFC 6238)
- ✅ Server-side session revocation via token_version (both agency and Super Admin)
- ✅ Brute-force protection (atomic counter, lockout, no email enumeration)
- ✅ Rate limiting (custom Redis INCR+EXPIRE Lua, per-IP + per-account, fail-closed)
- ✅ Three-role database model: m369_app (RLS), m369_sa_auth (login only), m369_sa_runner (BYPASSRLS management)
- ✅ Registration guard (SECURITY DEFINER function + advisory lock)
- ✅ m369_super_admin role neutralized (was BYPASSRLS + broad DML; now inert)
- ✅ Subscription lifecycle (trial → active → past_due → suspended → cancelled)
- ✅ Payment verification (idempotent, crypto-ready, INTEGER cents)

### Deferred

- Full inbox & conversation management UI → Phase 3
- Messaging channels → Phase 5+
- Knowledge base → Phase 4
- Customer portal → Phase 4
- Super Admin dashboard UI → Phase 9
- i18n → Phase 11
- Mobile apps → Phase 16
- AI assistant → Phase 13
- Per-device session revocation → Phase 2 (requires session table)
- Agency brute-force lockout counter → Phase 2 (rate limiting exists, no per-account lockout)
- Access token TTL split (agency vs SA) → config decision, not security issue

### Unverified (Blocked)

- Docker Compose full deployment (Docker unavailable in sandbox)
- Real Redis integration (fakeredis used for tests)
- Clean venv install (no isolated venv in sandbox)
- Reverse proxy deployment (TRUSTED_PROXY_IPS tested via mocks only)

## Test Results

| Metric | Value |
|---|---|
| Total tests | 346 |
| Passing | 346 |
| Failing | 0 |
| All run against | Real PostgreSQL 16.2 |
| Frontend type-check | ✅ PASS |
| Frontend build | ✅ PASS |
| Frontend lint | ✅ PASS |

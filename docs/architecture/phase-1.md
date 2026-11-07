# Phase 1 — Foundation + Multi-Tenancy + Security Hardening

## Scope

Phase 1 establishes the technical foundation for M369 Support, including full
multi-tenancy, authentication, RBAC, and comprehensive security hardening.

### Implemented and Z.ai-Tested

The following items are implemented and tested by Z.ai (the implementation agent)
in a local sandbox against real PostgreSQL 16.2. These results have **not** been
independently verified by a third party. See [`STATE.md`](../../STATE.md) for
the full test evidence, blockers, and verification status.

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
- ✅ Super Admin authentication with TOTP MFA (RFC 6238)
- ✅ Server-side session revocation via token_version (both agency and Super Admin)
- ✅ Brute-force protection (atomic counter, lockout, no email enumeration)
- ✅ Rate limiting (custom Redis INCR+EXPIRE Lua, per-IP + per-account, fail-closed)
- ✅ Three-role database model: m369_app (RLS), m369_sa_auth (login only), m369_sa_runner (BYPASSRLS management)
- ✅ Registration guard (SECURITY DEFINER function + advisory lock)
- ✅ m369_super_admin role neutralized (was BYPASSRLS + broad DML; now inert)
- ✅ Subscription lifecycle (trial → active → past_due → suspended → cancelled)
- ✅ Payment verification (idempotent, crypto-ready, INTEGER cents)

### Blocked (Not Independently Verified)

- Docker Compose full deployment (Docker unavailable in sandbox)
- Real Redis integration (fakeredis used for tests)
- Clean venv install (no isolated venv in sandbox)
- Reverse proxy deployment (TRUSTED_PROXY_IPS tested via mocks only)
- Independent third-party test execution (no third party has run the suite)

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

### Production Readiness

Phase 1 is **not** declared production-ready. Docker, real Redis, clean venv install,
and independent test verification remain blocked. See [`STATE.md`](../../STATE.md)
for the current blocker list.

## Z.ai-Reported Test Results

| Metric | Value | Verification |
|---|---|---|
| Backend tests | 346 passing, 0 failing | Z.ai-reported; not independently verified |
| Backend environment | PostgreSQL 16.2 (pgserver) | Z.ai sandbox |
| Frontend type-check | PASS | Z.ai-reported |
| Frontend build | PASS | Z.ai-reported |
| Frontend lint | PASS | Z.ai-reported |

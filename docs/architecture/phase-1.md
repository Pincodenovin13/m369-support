# Phase 1 — Foundation + Multi-Tenancy

## Scope

Phase 1 establishes the technical foundation for M369 Support.

### Implemented

- ✅ Monorepo structure (apps/api, apps/web, apps/widget, packages/, infrastructure/, docs/)
- ✅ Backend: FastAPI 0.115 + SQLAlchemy 2.0 + Alembic + Pydantic 2 + psycopg 3
- ✅ Frontend: Next.js 15 + React 19 + TypeScript + Tailwind CSS + TanStack Query
- ✅ Database schema: 11 tables with RLS on 8 tenant-owned tables
- ✅ 4 composite FK constraints preventing cross-tenant references
- ✅ JWT with `type` claim + separate signing keys (agency vs super_admin)
- ✅ Argon2id password hashing (RFC 9106)
- ✅ Auth flow: register, login, refresh, logout, /me
- ✅ Tenant context middleware + `SET LOCAL app.tenant_id` (transaction-scoped)
- ✅ Role-based access control (owner, admin, manager, agent, viewer)
- ✅ 14 API endpoints
- ✅ 22 tests executed against real PostgreSQL 16 (7 unit + 15 integration) — ALL PASS
- ✅ Docker Compose for local development
- ✅ CLI script for creating the first Super Admin

### Deferred

- Full inbox & conversation management UI → Phase 3
- Messaging channels → Phase 5+
- Knowledge base → Phase 4
- Customer portal → Phase 4
- Subscription & billing → Phase 9
- Super Admin dashboard UI → Phase 9
- i18n → Phase 11
- Mobile apps → Phase 16
- AI assistant → Phase 13
- JWT revocation list → Phase 2
- MFA enforcement → Phase 14

## Test Results

| Group | Count | Status |
|---|---|---|
| Unit (password hashing, JWT, slugs) | 7 | ✅ All PASS |
| Integration: cross-tenant RLS | 3 | ✅ All PASS |
| Integration: cross-tenant FK | 3 | ✅ All PASS |
| Integration: tenant context | 2 | ✅ All PASS |
| Integration: JWT lifecycle | 3 | ✅ All PASS |
| Integration: unauthenticated rejection | 2 | ✅ All PASS |
| Integration: authorization | 1 | ✅ All PASS |
| Integration: cross-tenant team | 1 | ✅ All PASS |
| **Total** | **22** | **✅ 22/22 PASS** |

All integration tests run against real PostgreSQL 16. SQLite is NOT substituted.

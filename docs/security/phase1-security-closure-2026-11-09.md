# Phase 1 Security Closure — 2026-11-09

## Decision

**Repository security CI: PASS. Production security certification: NOT CLAIMED.**

The complete API suite passed on commit `fb57c3e24d071ecb807bc64a8be330400818b4c7`.

## CI evidence

- Repository: `Pincodenovin13/m369-support`
- Branch: `refactor/repository-structure-unification`
- Commit: `fb57c3e24d071ecb807bc64a8be330400818b4c7`
- Workflow: [API PostgreSQL security tests](https://github.com/Pincodenovin13/m369-support/actions/runs/42605960342)
- Job: `postgres-tests` — completed successfully
- Command: `pytest -q tests`
- Result: **357 passed, 0 failed, 0 skipped, 1 warning**
- Runtime: 77.10 seconds; Python 3.12; PostgreSQL 16.15
- Warning: Starlette TestClient uses the deprecated `anyio.abc.BlockingPortal` alias.

## Controls verified

1. Migration `0019_signed_tenant_context_rls` uses an HMAC-signed tenant context. PostgreSQL verifies both the tenant ID and signature; unsigned or altered GUC values fail closed.
2. The signing key is held in the private `m369_private` schema. The application role cannot read it. The verifier role is NOLOGIN, NOBYPASSRLS, non-inheriting, and isolated from application role memberships.
3. Sixteen tenant tables use ENABLE + FORCE RLS and signed USING/WITH CHECK policies. `agency_notes` remains deny-all. A catalog-driven test discovers every public table with `agency_id` and rejects missing or unexpected RLS policies. The `agencies` root table is separately covered because its tenant key is `id`.
4. Adversarial PostgreSQL tests exercise tenant A/B SELECT, INSERT, UPDATE, and DELETE isolation, forged tenant context, old bypass-GUC attempts, and database role restrictions.
5. Tenant API handlers reviewed use membership/role dependencies. Super Admin management handlers reviewed use `get_super_admin_context` and a dedicated management DB connection. Authentication uses a separate least-privilege DB role.
6. Super Admin sessions are checked against active account state and `token_version`; logout revokes prior sessions. MFA challenge/recovery/TOTP replay protections are database-backed. Login, MFA verification, MFA enrollment, and MFA disable use rate-limit checks. Locked-account login now returns the same generic 401 response as an unknown account.

## Six-point closure status

| Check | Status | Notes |
|---|---|---|
| Full test suite | PASS | 357 passed, 0 failed, 0 skipped |
| Fix failures without weakening tests | PASS | No security tests removed or skipped |
| Future tenant-table RLS guard | PASS | PostgreSQL catalog-driven guard for `agency_id` tables |
| Cross-tenant CRUD attacks | PASS for exercised cases | Real PostgreSQL rows; SELECT/INSERT/UPDATE/DELETE |
| Roles, auth, Super Admin routes | PASS for reviewed controls; exhaustive object-IDOR matrix remains follow-up | Route guard review and auth/role tests; not every resource permutation fuzzed |
| Report and CI evidence | PASS | This document and linked workflow |

## Required before production launch

- Provision a unique high-entropy `M369_TENANT_CONTEXT_SECRET` outside the repository. Never reuse the CI/test value.
- Apply migration 0019 to the production database using the controlled migration identity, then inspect actual role grants, RLS flags, and policies.
- Configure and test real production Redis. CI uses test settings and a fake Redis override; production Redis operations and alerting were not exercised.
- Verify trusted proxy IPs against the real ingress topology before trusting `X-Forwarded-For`.
- Run deployment smoke tests and an independent application-level IDOR/authorization review before onboarding paying agencies.
- Migration 0019 intentionally refuses downgrade; do not restore unsigned tenant-GUC policies.

## Scope limitations

No production database, production secrets, real Redis service, reverse proxy, payment-chain integration, external penetration test, or formal compliance certification was exercised. This is a repository-level CI security pass for the exact commit above, not a guarantee for later commits or a production deployment.

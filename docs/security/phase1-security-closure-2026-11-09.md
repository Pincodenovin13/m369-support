# Phase 1 Security Closure — 2026-11-09

## Decision

**Repository security CI: PASS for the exact commit below. Production security certification: NOT CLAIMED.**

The latest complete API/PostgreSQL test suite passed on commit `772b23489a8fa930219dcd877d32b61391a1eeb9`.

## CI evidence

- Repository: `Pincodenovin13/m369-support`
- Branch: `refactor/repository-structure-unification`
- Commit: `772b23489a8fa930219dcd877d32b61391a1eeb9`
- Workflow: [API PostgreSQL security tests](https://github.com/Pincodenovin13/m369-support/actions/runs/42628735407)
- Job: `postgres-tests` — completed successfully
- Command: `pytest -q tests`
- Result: **359 passed, 0 failed, 0 skipped, 1 warning**
- Runtime: 75.48 seconds; Python 3.12.16; PostgreSQL 16.15
- Pytest warning: Starlette TestClient uses the deprecated `anyio.abc.BlockingPortal` alias.
- Workflow/runtime warning: GitHub reports that `actions/checkout@v4` and `actions/setup-python@v5` currently target Node.js 20, which is deprecated on the runner. This is an Actions maintenance warning, not a pytest failure.

## Controls represented by the current test suite

1. Migration `0019_signed_tenant_context_rls` implements an HMAC-signed tenant context. PostgreSQL verifies the tenant ID and signature; invalid or altered context fails closed.
2. The signing key is held in the private `m369_private` schema. The application role must not read it. The verifier role is NOLOGIN and NOBYPASSRLS.
3. The catalog-driven RLS guard discovers public tables with `agency_id` and rejects missing or unexpected RLS policies. Tenant tables require ENABLE + FORCE RLS and signed `USING` / `WITH CHECK` enforcement. `agency_notes` is a deliberate deny-all exception; the `agencies` root table is separately covered because its tenant key is `id`.
4. Adversarial PostgreSQL tests exercise cross-tenant SELECT, INSERT, UPDATE and DELETE cases, forged tenant context, legacy bypass-GUC attempts, and restricted database-role behavior. The latest commit adds an explicit tenant-A-to-tenant-B INSERT attack test.
5. Existing tests cover tenant authentication/RBAC and Super Admin authentication, MFA, revocation and database-role boundaries. This is not yet a complete route-by-route object-IDOR matrix; that remains an open security task.
6. The workflow runs the complete API test suite against a fresh PostgreSQL 16 service. Its successful result is evidence for this commit only.

## Six-point security checklist

| Check | Current status | Evidence / remaining work |
|---|---|---|
| Full test suite | PASS | 359 passed, 0 failed, 0 skipped |
| Fix failures without weakening tests | PASS for this run | No tests skipped; review every future change for weakened assertions |
| Automatic future-table RLS guard | PASS in CI | Catalog-driven discovery for public `agency_id` tables |
| Cross-tenant CRUD attacks | PASS for exercised cases | Includes explicit cross-tenant INSERT; expand resource/API IDOR matrix |
| PostgreSQL roles, authentication, Super Admin | PARTIAL — test coverage exists | Complete route-by-route authorization/IDOR review and production role/grant inspection |
| Report and CI evidence | PASS | This document and linked run |

## Required before production launch

- Provision a unique high-entropy `M369_TENANT_CONTEXT_SECRET` outside the repository. Never reuse the CI/test value.
- Apply migrations to the production database through a controlled migration identity, then inspect actual role attributes, memberships, grants, RLS flags and policies.
- Configure and test real production Redis. CI uses test settings; production Redis operations, alerting and failure behavior were not exercised.
- Verify trusted proxy IPs against the real ingress topology before trusting `X-Forwarded-For`.
- Complete a route-by-route object-IDOR and authorization review, including negative tests for cross-agency resource IDs and Super Admin privilege boundaries.
- Run deployment smoke tests and an independent application-level security review before onboarding paying agencies.
- Review and update deprecated GitHub Actions runtime dependencies.
- Migration 0019 intentionally refuses downgrade; do not restore unsigned tenant-GUC policies.

## Scope limitations

No production database, production secrets, real Redis service, reverse proxy, payment-chain integration, external penetration test, or formal compliance certification was exercised. This is a repository-level CI security pass for the exact commit above, not a guarantee for later commits or a production deployment.

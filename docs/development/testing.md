# Testing and Verification — Current Baseline

## Current CI evidence

### API / PostgreSQL

- Workflow: [API PostgreSQL security tests](https://github.com/Pincodenovin13/m369-support/actions/runs/42654977524)
- Commit: `cf66a4fabbc58a27424950b0f792e3f4cbc9e686`
- Command: `pytest -q tests`
- PostgreSQL: 16
- Result: **359 passed, 1 warning in 93.61s**
- Warning: Starlette TestClient references the deprecated `anyio.abc.BlockingPortal` alias.
- GitHub runner also warns that checkout/setup-python actions are running through the Node.js 20 compatibility path while the runner is moving to Node.js 24.

### Frontend

- Workflow: [Web frontend CI](https://github.com/Pincodenovin13/m369-support/actions/runs/42654983328)
- Commit: `376b3b25beba303b0fef9cd5a2b77e386c194258`
- Result: success — `npm ci`, `npm audit --audit-level=low`, `npm run type-check`, `npm run lint`, `npm run build`.
- The active HEAD after this run contains documentation and backend test changes, not frontend source changes. A frontend run is required whenever frontend source or dependencies change.

CI results are commit-specific. Do not label code PASS based only on inspection, and do not imply a CI run verified files changed after its tested commit.

## Commands

```bash
# API (PostgreSQL 16 service/database must be available)
cd apps/api
pytest -q tests

# Frontend
cd apps/web
npm ci
npm audit --audit-level=low
npm run type-check
npm run lint
npm run build
```

## Coverage and gaps

| Area | Current status |
|---|---|
| Backend unit/integration/security suite | Executed in GitHub Actions against PostgreSQL 16 |
| Dynamic RLS catalog guard | Implemented; discovers public tables with `agency_id` |
| Cross-tenant attacks | Tests cover exercised SELECT/INSERT/UPDATE/DELETE cases; continue expanding API-level IDOR matrix |
| Super Admin auth/MFA/revocation | Covered by existing backend tests; route-by-route privilege review remains open |
| Frontend type/lint/build | CI implemented |
| Frontend unit/component tests | NOT IMPLEMENTED |
| Frontend browser E2E tests | NOT IMPLEMENTED |
| Real production Redis | NOT VERIFIED |
| Docker Compose deployment | NOT VERIFIED in production-like environment |
| Persistent production database role/RLS inspection | NOT VERIFIED |
| Reverse proxy / trusted ingress | NOT VERIFIED |
| Independent external penetration test | NOT PERFORMED |

## Verification labels

- **CI-VERIFIED:** command actually ran successfully in GitHub Actions for the named commit.
- **IMPLEMENTER-REPORTED:** reported by an implementation agent but not independently checked.
- **NOT EXECUTED:** not run; reason must be stated.
- **BLOCKED:** could not run because a required environment/service was unavailable.
- **NOT IMPLEMENTED:** test or feature does not exist.

## Security test invariants

1. Never delete, skip, xfail, weaken or remove assertions from security tests to obtain a green run.
2. Preserve the dynamic RLS catalog guard; future tenant-owned tables must be discovered automatically.
3. Exercise both positive controls (tenant A can access its own row) and negative controls (tenant A cannot access tenant B).
4. Include CRUD, object-IDOR, role boundary, replay, concurrency and privilege tests as relevant.
5. Any migration touching RLS, grants, SECURITY DEFINER functions or tenant keys requires line-by-line review.
6. A green CI run is not production certification.

## Warnings and maintenance

- Fix the Starlette/AnyIO deprecation through a compatible dependency update and rerun the complete suite.
- Update GitHub Actions to supported Node.js 24-compatible action versions after compatibility verification.
- Automatic lockfile mutation workflow was removed in commit `6043cfffe0ee4642fc55c4811f6ae87c481ca9ec`; dependency updates must be explicit and reviewed. CI uses `npm ci` against the committed lockfile.

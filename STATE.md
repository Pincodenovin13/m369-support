# M369 Support — Authoritative Project State

> Last reconciled: 2026-11-09 (UTC)
> Active development branch: `refactor/repository-structure-unification`
> Active HEAD: resolve from the live GitHub branch ref; last audited application-code snapshot: `ce3d54a2df13494ee914bea2f0677dd11f736a0c`
> GitHub default branch: `test/marker` (still a one-file marker branch; NOT the development source of truth)
> Tracked files on active HEAD: 202
> Alembic head: `0020_payment_raw_amount_precision` (20 linear migrations)
> Production deployment database: NOT inspected

## 1. Source-of-truth rules

1. The active development source is the exact branch and HEAD named above.
2. This file is the canonical current-state summary. Historical reports under `recovery/` and old branch snapshots are not implementation instructions.
3. Do not develop on `test/marker`, `phase-1/foundation`, or historical checkpoint branches.
4. Do not delete branches, rewrite published history, force-push, or reapply archived patches as part of routine work.
5. Any code/schema change must be checked against the current active HEAD, not against a stale local or historical report.

## 2. Branch topology

The repository currently exposes 12 branches. Comparison of each of the 11 other branch tips against the active HEAD reports the active branch as ahead and behind by zero; each compared branch tip is an ancestor of the active HEAD. This means the visible branch tips are historical checkpoints on the same ancestry line, not currently divergent code lines.

| Branch | Tip | Classification |
|---|---|---|
| `refactor/repository-structure-unification` | Live branch tip (resolve from GitHub) | Active development |
| `test/marker` | `34d97bf4` | Default branch; one file only; stale |
| `phase-1/foundation` | `0b3139a1` | Historical checkpoint |
| `phase-1/agency-auth-integration-closure` | `5fc22ad8` | Historical checkpoint |
| `phase-1/agency-token-revocation` | `890f6a58` | Historical checkpoint |
| `phase-1/security-closure-b1-4` | `ab046a23` | Historical checkpoint |
| `phase-1/security-final-hardening` | `2b6905c8` | Historical checkpoint |
| `phase-1/security-hardening` | `b32f6242` | Historical checkpoint |
| `phase-1/tenant-isolation-b1-1` | `72dfc674` | Historical checkpoint |
| `phase-1/tenant-isolation-corrections` | `9afc2f5a` | Historical checkpoint |
| `phase-1/tenant-isolation-hardening` | `a5a3a2cb` | Historical checkpoint |
| `recovery/zai-workspace-2026-11-08` | `1c329415` | Historical recovery checkpoint |

**Required repository setting cleanup:** change GitHub's default branch from `test/marker` to `refactor/repository-structure-unification` only after the owner confirms this is the intended long-term integration branch and branch protection/required checks are configured. The current GitHub connector can inspect repository metadata but cannot change this setting. No branch was deleted or rewritten.

## 3. Current repository inventory

| Area | Current inventory |
|---|---|
| Root | `.env.example`, README, STATE, REPOSITORY_MAP, CONTRIBUTING, Makefile, Docker Compose, LICENSE |
| Backend | `apps/api/` — FastAPI application, services, schemas, security, tenancy, scripts and tests |
| Backend Python application files | 58 |
| Backend Python test/support files | 25 |
| Alembic migrations | 20, from `0001_initial` through `0020_payment_raw_amount_precision` |
| Frontend | `apps/web/` — Next.js 15 / React 19 / TypeScript |
| Frontend source files | 31 |
| Frontend App Router page files | 19 |
| Widget | `apps/widget/` — README + placeholder only; no working widget implementation |
| Shared package | `packages/shared/` — README + placeholder only; no published shared TypeScript package |
| Infrastructure | `infrastructure/database/01-bootstrap-roles.sql` |
| Docs | Architecture, database, development, security and future-capability roadmap |
| Recovery | Historical archive only; contains superseded material and explicit OpenLivery references in legacy documents |

Repeated basenames such as `README.md`, `page.tsx`, `auth.py`, `agencies.py`, and `__init__.py` occur in separate, intentional module paths. They are not evidence of duplicate files by themselves. Do not flatten or rename them without checking Python/Next.js routing and imports.

## 4. Latest CI evidence

### API / PostgreSQL

- Workflow: [API PostgreSQL security tests](https://github.com/Pincodenovin13/m369-support/actions/runs/42646416006)
- Exact commit: `ce3d54a2df13494ee914bea2f0677dd11f736a0c`
- Job: `postgres-tests`
- Command: `pytest -q tests`
- Result: **359 passed, 1 warning**, 92.52 seconds
- PostgreSQL service: 16
- Warning: Starlette TestClient uses deprecated `anyio.abc.BlockingPortal`; GitHub runner also reports Node.js 20 action-runtime deprecation for checkout/setup-python.
- No skipped count is asserted here because the captured pytest summary reports only passed count and warnings.

### Frontend

- Workflow: [Web frontend CI](https://github.com/Pincodenovin13/m369-support/actions/runs/42628470610)
- Result: success for `npm ci`, `npm audit --audit-level=low`, TypeScript, ESLint and production build.
- This run is on the dashboard frontend commit. The subsequent commits through current HEAD changed backend tests/documentation, not frontend source; frontend CI was not re-triggered by docs-only changes.

CI success is tied to the tested commit and workflow scope. It does not certify production deployment or all user workflows.

## 5. Database and tenant security baseline

- Migration chain ends at `0020_payment_raw_amount_precision`.
- Migration 0019 introduced HMAC-signed tenant context, stored verifier secret in `m369_private`, and uses a SECURITY DEFINER verifier function.
- Tenant tables use ENABLE + FORCE RLS and signed verifier policies; `agency_notes` is intentionally deny-all for ordinary tenant runtime.
- Catalog-driven tests discover public tables with `agency_id` so future tenant tables without expected RLS controls fail CI.
- Cross-tenant adversarial tests cover exercised SELECT/INSERT/UPDATE/DELETE cases; latest suite includes explicit A-to-B INSERT denial.
- Composite tenant/workspace foreign keys and restricted PostgreSQL roles provide additional isolation.
- Super Admin uses separate auth/management DB paths; its management role has BYPASSRLS and must remain narrowly permissioned.

Do not infer live production role attributes, grants, RLS policies, or secret provisioning from CI alone.

## 6. Security release gates still open

1. Complete route-by-route authorization and object-IDOR matrix for all agency and Super Admin routes.
2. Verify all PostgreSQL role memberships, effective grants, SECURITY DEFINER ownership/search_path and secret access in the actual deployment database.
3. Verify real Redis behavior, limiter fail-closed behavior, production proxy trust configuration and rate-limit keying.
4. Review request-size limits, security headers, upload/attachment handling, webhook ingress and abuse/DoS controls.
5. Run deployment smoke tests and independent security review before onboarding paying agencies.
6. Inspect and resolve CI/toolchain deprecation warnings.
7. Keep all future RLS changes covered by catalog-driven tests and hostile tenant-A/tenant-B tests.

**Security status:** repository CI pass; security closure incomplete; production security certification NOT CLAIMED.

## 7. Product delivery status

- Dashboard redesign exists and consumes workspace API data.
- Agency pages exist for contacts, conversations, conversation detail, teams, channels, canned responses and knowledge base; the frontend is not yet feature-complete.
- Separate Super Admin login/MFA and initial console pages exist.
- Frontend browser E2E tests are not implemented.
- OpenAPI-to-TypeScript generation/drift checking is still required.
- WhatsApp, Telegram, Instagram and Facebook integrations are roadmap requirements, not implemented channel integrations.
- Monthly export, Human Escalation, AI usage control, BYOAI, retention/archiving and PWA are roadmap items, not current features.

See `docs/architecture/future-capabilities-roadmap.md` for the approved planning baseline.

## 8. Known repository/workflow consistency issues

- GitHub default branch is the one-file `test/marker` branch; active code is on the branch stated above.
- Historical branches remain visible as checkpoints. They are currently ancestors of active HEAD, not divergent lines.
- Historical `recovery/workspace-preservation/` contains archived OpenLivery references. Its README explicitly marks those files as non-authoritative; do not import or reuse them.
- `.github/workflows/refresh-web-lockfile.yml` automatically regenerates and commits the web lockfile and runs `npm audit fix` after manifest changes. This is a separate mutation workflow, not the read-only `npm ci` check; review its behavior before treating dependency changes as fully manual.
- Several documentation files previously contained stale branch, migration, test-count and security claims. They are being reconciled against this state and current CI evidence.

## 9. Immediate next sequence

1. Finish repository/documentation consistency reconciliation without deleting historical evidence.
2. Resolve default-branch configuration and branch protection explicitly.
3. Continue route-by-route backend security audit and hostile tests.
4. Finish API contract/OpenAPI drift controls.
5. Continue frontend vertical slices against real API contracts.
6. Only then implement integrations, Human Escalation and monthly Export, each behind security gates.

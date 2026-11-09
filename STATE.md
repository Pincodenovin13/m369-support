# M369 Support — Authoritative Project State

> Last reconciled: 2026-11-09 (UTC)
> Active development branch: `refactor/repository-structure-unification`
> Active HEAD: resolve from live GitHub branch ref; last audited repository snapshot: `dc389d75d6a19265a6a0cb639b1ae8247abe5cd8` (this state reconciliation changes documentation only)
> GitHub default branch: `test/marker` (still a one-file marker branch; NOT the development source of truth)
> Tracked files on current active HEAD: 203
> Alembic head: `0020_payment_raw_amount_precision` (20 linear migrations)
> Production deployment database: NOT inspected
> Production deployment configuration: NOT ready; current docker-compose.yml is local-development only

## 1. Source-of-truth rules

1. The active development source is the exact branch and HEAD named above.
2. This file is the canonical current-state summary. Historical reports under `recovery/` and old branch snapshots are not implementation instructions. Exclude `recovery/**` from automated implementation discovery, dependency scans used to determine active architecture, and source imports unless performing explicit forensic review.
3. Do not develop on `test/marker`, `phase-1/foundation`, or historical checkpoint branches.
4. Do not delete branches, rewrite published history, force-push, or reapply archived patches as part of routine work.
5. Any code/schema change must be checked against the current active HEAD, not against a stale local or historical report.

## 2. Branch topology

The repository currently exposes 12 branches (verify live branch list before branch operations). Comparison of each of the 11 other branch tips against the active HEAD reports the active branch as ahead and behind by zero; each compared branch tip is an ancestor of the active HEAD. This means the visible branch tips are historical checkpoints on the same ancestry line, not currently divergent code lines.

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

A fresh API/PostgreSQL workflow ran on API README reconciliation commit `cf66a4fabbc58a27424950b0f792e3f4cbc9e686`: [run 42654977524](https://github.com/Pincodenovin13/m369-support/actions/runs/42654977524) completed successfully, **359 passed, 1 warning in 93.61s**. Application source/tests were unchanged from the previously audited tested snapshot.

### API / PostgreSQL

- Workflow: [API PostgreSQL security tests](https://github.com/Pincodenovin13/m369-support/actions/runs/42646416006)
- Exact commit: `ce3d54a2df13494ee914bea2f0677dd11f736a0c`
- Job: `postgres-tests`
- Command: `pytest -q tests`
- Result: **359 passed, 1 warning**, 92.52 seconds
- PostgreSQL service: 16
- Warning: Starlette TestClient uses deprecated `anyio.abc.BlockingPortal`; GitHub runner also reports Node.js action-runtime deprecation and Python environment `punycode` deprecation.
- No skipped count is asserted here because the captured pytest summary reports only passed count and warnings.

### Frontend

- Workflow: [Web frontend CI](https://github.com/Pincodenovin13/m369-support/actions/runs/42654983328)
- Result: success for `npm ci`, `npm audit --audit-level=low`, TypeScript, ESLint and production build.
- Latest frontend docs reconciliation triggered CI on `376b3b25beba303b0fef9cd5a2b77e386c194258`; all frontend checks completed successfully.

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
5. Implement and review a production Compose/release configuration; current Compose bind-mounts source and runs Uvicorn --reload, so it is local-only.\n6. Run deployment smoke tests and independent security review before onboarding paying agencies.
7. Inspect and resolve CI/toolchain deprecation warnings.
8. Keep all future RLS changes covered by catalog-driven tests and hostile tenant-A/tenant-B tests.

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
- `.github/workflows/refresh-web-lockfile.yml` was removed in commit `6043cfffe0ee4642fc55c4811f6ae87c481ca9ec`. Dependency changes are now explicit, reviewed changes; web CI installs the committed lockfile with `npm ci` and does not mutate/push it. No worker/queue implementation or worker directory currently exists; future background processing is a roadmap capability and should initially run on the same VPS with strict limits.
- Several documentation files previously contained stale branch, migration, test-count and security claims. They are being reconciled against this state and current CI evidence.

## 9. Deployment and cost constraints\n\n- `docs/deployment/production-operations.md` is the owner learning/runbook draft for domain, VPS, DNS, TLS, backups, updates and rollback. It is not deployment approval.\n- Initial cost target is one VPS and Docker Compose containers on that host; no separate worker VPS, managed database, Kubernetes or paid Redis cluster without measured justification.\n- Current `docker-compose.yml` is local-only: source bind mount and Uvicorn `--reload`; a hardened production configuration remains unimplemented.\n- Super Admin management DB credentials are currently injected into the API process; route-level privilege boundaries and production secret handling remain security gates.\n\n## 10. Immediate next sequence

1. Finish repository/documentation consistency reconciliation without deleting historical evidence.
2. Resolve default-branch configuration and branch protection explicitly.
3. Continue route-by-route backend security audit and hostile tests.
4. Finish API contract/OpenAPI drift controls.
5. Continue frontend vertical slices against real API contracts.
6. Only then implement integrations, Human Escalation and monthly Export, each behind security gates.

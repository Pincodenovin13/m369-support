# Repository Integrity Audit — 2026-11-09

## Scope and method

Inspected the active branch tree, all visible branch tips, GitHub default-branch metadata, current root/docs references, migration inventory, and the three GitHub Actions workflows. This is a repository-structure and consistency audit, not a line-by-line security audit of every application module.

Active branch: `refactor/repository-structure-unification`  
Audited HEAD: `ce3d54a2df13494ee914bea2f0677dd11f736a0c`

## Findings

### 1. Branch topology — no current divergent code tips detected

- Repository has 12 visible branches.
- Compared the 11 non-active branch tips to the active HEAD.
- Every comparison reported `ahead` with `behind_by = 0`; the merge base equals the compared branch tip.
- Therefore the branch tips are historical ancestors of the active HEAD, not parallel divergent code histories.
- No branch was deleted, merged, rebased or force-pushed during this audit.

**Outstanding:** GitHub default branch remains `test/marker`, whose tree contains only `MARKER.txt`. The intended active source is `refactor/repository-structure-unification`. This default-branch setting is not changeable through the available GitHub connector actions in this session. Repository owner must change it in Settings → General → Default branch after confirming branch protection and required checks.

### 2. Active tree inventory

- 202 tracked blobs at audited application/docs snapshot; one mutating lockfile workflow was subsequently removed in commit `6043cfffe0ee4642fc55c4811f6ae87c481ca9ec`.
- 58 Python application files under `apps/api/app/`.
- 25 Python test/support files under `apps/api/tests/`.
- 20 Alembic migration files, ending at `0020_payment_raw_amount_precision`.
- 31 frontend source files under `apps/web/src/`.
- 19 Next.js App Router `page.tsx` files.
- Widget and shared package are placeholders, not working packages.
- Repeated basenames exist in separate module paths. They are not duplicate files unless imports/build manifests show the same implementation copied into multiple locations.

### 3. Confirmed stale or contradictory documentation

Before reconciliation:
- `STATE.md` named `phase-1/foundation` as canonical and reported an obsolete HEAD, 19 migrations, focused 73-test run and old risk state.
- `README.md` still described backend tests as Z.ai-reported/unverified and referenced a 346-test baseline.
- `REPOSITORY_MAP.md` described 19 migrations and 19 frontend source files.
- `docs/development/testing.md` described the suite as 346 tests and not independently executed.
- `docs/architecture/overview.md` still described unsigned tenant-GUC trust as the current security boundary.
- Branch rules in `CONTRIBUTING.md` still directed work to `phase-1/foundation` and suggested deleting source branches after merge, contrary to the current integration path and preservation requirement.

These references can mislead contributors/agents even though they do not directly alter runtime behavior.

### 4. Historical recovery archive

`recovery/workspace-preservation/` contains 16 historical artifacts, including legacy design documents with OpenLivery references. Its README clearly labels the folder historical/non-authoritative and says not to use it as implementation source. The archive is not a substitute for current source code.

**Decision:** preserve the archive for provenance; do not move/delete it in this pass. All future tooling/prompts must explicitly exclude `recovery/**` from implementation discovery unless the task is historical forensic review.

### 5. Workflow observations

- `.github/workflows/api-postgres-security.yml` runs the full API test command `pytest -q tests` against PostgreSQL 16 for API, compose/env and security-doc changes. It does not run for every repository file by design.
- `.github/workflows/web-ci.yml` runs npm ci, audit, TypeScript, ESLint and production build on web changes.
- `.github/workflows/refresh-web-lockfile.yml` was removed in commit `6043cfffe0ee4642fc55c4811f6ae87c481ca9ec`. Dependency updates are explicit; web CI uses `npm ci` and does not rewrite or push lockfiles.
- API CI on audited HEAD: [run 42646416006](https://github.com/Pincodenovin13/m369-support/actions/runs/42646416006), **359 passed, 1 warning**, PostgreSQL 16, 92.52 seconds.
- Frontend CI: [run 42628470610](https://github.com/Pincodenovin13/m369-support/actions/runs/42628470610), success for the frontend source snapshot at commit `455d5b2c`. Frontend source was not changed after that run in the commits through audited HEAD.

### 6. Security and production boundary

The CI result is not a production security certification. Remaining verification includes route-by-route object-IDOR/RBAC review, actual database role/grant inspection, real Redis, trusted ingress/proxy, request-size and upload controls, production secret handling, deployment smoke tests and independent security review.

## Reconciliation actions

- Align current-state and test docs to the audited HEAD and exact CI evidence.
- Align branch workflow instructions with the active development branch.
- Preserve all historical branch refs and recovery artifacts.
- Keep the future-capability roadmap separate from implemented feature status.
- Do not alter migrations or application code as part of a documentation-only reconciliation.

## Still pending

1. Change GitHub default branch to the active integration branch after branch-protection review.
2. Decide whether to disable/replace automatic lockfile mutation.
3. Add a repository-wide CI/docs-link/structure consistency check.
4. Keep the deployment operations guide aligned with the final production topology and actual provider.
4. Continue the separate route-by-route application security audit.

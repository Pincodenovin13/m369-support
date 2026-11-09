# Contributing to M369 Support

**Status:** Current contributor policy. Applies to humans and automated agents. Last reconciled: 2026-11-09.

## 1. Source of truth and branches

- Repository: Pincodenovin13/m369-support.
- Active development/integration branch: `refactor/repository-structure-unification`.
- GitHub default branch is still `test/marker`; it is stale and is not the development source. Until the owner changes that repository setting, always target the active branch explicitly.
- Start every task from the latest live active-branch HEAD. Do not rely on a prior chat's SHA or a local clone without fetching.
- Existing `phase-1/*`, `recovery/*` and `test/marker` refs are preserved historical checkpoints. Do not delete, rewrite, rebase or force-push them.
- Do not create parallel long-lived implementation branches. Use a short-lived `feature/`, `security/`, `fix/`, `docs/` or `refactor/` branch when PR protections are active; otherwise make focused commits on the active branch only when explicitly authorized.
- Never merge or cherry-pick a historical branch merely because its name looks relevant. Compare exact trees and inspect dependencies first.

## 2. Authoritative file placement

`REPOSITORY_MAP.md` is the single source of truth for active file placement. `STATE.md` is the current status/evidence record. `docs/README.md` indexes detailed documentation.

- Backend runtime: `apps/api/app/`.
- Backend migrations: `apps/api/migrations/versions/` (append-only after publication).
- Backend tests: `apps/api/tests/unit/` and `apps/api/tests/integration/`.
- Frontend: `apps/web/src/`.
- Shared types: `packages/shared/` only when an actual consumer requires them.
- Embeddable widget: `apps/widget/` only when implementation begins; it is currently a placeholder.
- Infrastructure: `infrastructure/` and root Compose/config files.
- Architecture, security, deployment and development docs: `docs/`.
- Historical artifacts only: `recovery/workspace-preservation/`.

**Hard boundary:** exclude `recovery/**` from active source discovery, imports, builds, runtime packaging, API contract generation and automated implementation prompts. Use it only for explicitly requested historical forensics. Never copy legacy OpenLivery or superseded architecture into current M369 code.

Do not create speculative placeholder services, duplicate model/schema files, or a separate worker directory before a real feature requires it. No worker/queue implementation currently exists. If background work is later required, evaluate a bounded process/container on the same VPS before any separate server.

## 3. Change and commit discipline

- One coherent purpose per commit; do not mix unrelated security, UI, migration and dependency changes.
- Use conventional messages: `security(api): ...`, `fix(web): ...`, `feat(api): ...`, `docs(repo): ...`.
- Inspect the live tree and all affected imports/routes before moving, renaming or deleting files.
- Never edit a published Alembic migration. Add a new numbered migration and inspect upgrade/downgrade implications.
- Do not commit secrets, `.env`, private keys, local database files, caches, build outputs or generated artifacts that are not intentionally versioned.
- Run `git diff --check`, inspect the full diff and verify only intended paths changed before committing.
- Never force-push or rewrite published history.

## 4. Pull request and evidence requirements

Every PR must use `.github/PULL_REQUEST_TEMPLATE.md`. It must state:
1. purpose and exact changed paths;
2. why each logical group changed;
3. security and tenant-isolation impact;
4. migration/rollback impact;
5. exact commands actually executed and their results;
6. tests not run and why;
7. CI workflow URL and exact tested commit;
8. operational risks and production-only checks still outstanding.

Use the active branch as the comparison base, not `phase-1/foundation`. A test is PASS only if it actually ran successfully. Never delete, skip, xfail, weaken or remove security assertions to make CI green. Report warnings and skipped tests honestly.

## 5. Mandatory security review

For every backend feature, consider:
- tenant A versus tenant B isolation for SELECT, INSERT, UPDATE and DELETE;
- object-IDOR and authorization on every resource and download path;
- role escalation, membership changes and disabled/suspended accounts;
- JWT type, issuer, audience, expiry and token-version/revocation;
- PostgreSQL RLS ENABLE + FORCE, signed tenant context, USING and WITH CHECK;
- composite tenant foreign keys and unsafe joins;
- SECURITY DEFINER ownership/search_path and database grants;
- Super Admin BYPASSRLS boundaries and least privilege;
- rate-limit fail-closed behavior, request-size limits, abuse/DoS and webhook replay;
- secret storage, redaction, rotation and audit logging.

Any new tenant-owned table must be discovered by the dynamic RLS catalog guard and protected before merge. Positive controls and hostile cross-tenant tests are both required. A green CI run is not production security certification.

## 6. Frontend and API contracts

- Frontend screens must use actual backend routes and schemas; no fabricated production data or guessed payload names.
- Keep OpenAPI and TypeScript contracts aligned; add drift/contract tests before expanding feature count.
- Every user-facing flow needs loading, error, empty and success states, responsive behavior and appropriate accessibility.
- Add browser/component tests as the frontend matures; type-check/build alone do not prove user journeys work.

## 7. Dependencies and workflows

- Dependency updates must be explicit and reviewed. Update package manifest and lockfile together.
- CI uses `npm ci` to validate the committed lockfile. The automatic lockfile mutation/push workflow has been removed.
- Do not grant workflows write permissions unless the workflow has a reviewed, necessary write action.
- Pin or review third-party Actions and runtime upgrades; inspect deprecation and security warnings.

## 8. Deployment and owner handoff

Production deployment is not approved merely because CI passes. Follow `docs/deployment/production-operations.md` after production Compose, secret handling, firewall, TLS, backup/restore, monitoring and rollback are implemented and reviewed. The current root `docker-compose.yml` is local-development only; it uses a source bind mount and Uvicorn reload and must not be deployed unchanged.

The Product Owner must receive a practical walkthrough for domain purchase, VPS, DNS, HTTPS, deployment, backups, upgrades, rollback and Super Admin operations before launch. Prefer one VPS initially; do not add a separate worker host, managed database, Kubernetes or paid services without measured justification.

## 9. Artifact disclosure (Rule 13)

Every task that creates or changes files must report:
- exact paths created/modified/deleted;
- commit SHA and branch;
- whether changes are pushed to GitHub;
- CI/test evidence and exact commit tested;
- any generated files/artifacts and how to access them;
- anything intentionally left uncommitted or not delivered.

Do not claim a file is available to the owner unless it is actually committed/pushed or attached through a verified supported mechanism. Never rely on a temporary coding sandbox as the only copy of project work.

## 10. Escalation

Security uncertainty blocks release, not the test. Stop and inspect the actual schema, role grants, route dependencies and runtime behavior rather than guessing. Record unresolved risks in `STATE.md` and the relevant security document. No production security seal until all release gates have evidence and an independent review has been completed.

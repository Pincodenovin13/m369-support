<!--
  M369 Support — Pull Request Template
  Every section is required. Do not delete a section; write "N/A" with a reason if it does not apply.
  Per CONTRIBUTING.md Rule 13 (Artifact Disclosure & Delivery), include the artifact disclosure table.
-->

## Purpose

<!-- One paragraph: what does this PR do and why? -->

## Changed Files

<!-- Paste `git diff --stat phase-1/foundation...HEAD` output here -->

```text
# paste git diff --stat output
```

## Reason for Each File Change

<!-- Bulleted list, one per file or logical group -->

-

## Security Impact

<!-- "No security impact" or describe what changed.
     If this PR touches apps/api/app/security/, apps/api/app/api/v1/auth.py,
     apps/api/app/api/v1/super_admin/auth.py, apps/api/app/services/sa_auth.py,
     apps/api/app/services/rate_limit.py, apps/api/app/middleware/tenant_context.py,
     apps/api/app/tenancy/context.py, apps/api/migrations/versions/, or
     infrastructure/database/01-bootstrap-roles.sql — a security review is REQUIRED. -->

## Database Migration Impact

<!-- "No migration" or the migration filename + upgrade/downgrade summary.
     Per project rules: migrations 0001-0016 are published history. Do NOT move,
     rename, edit, squash, or regenerate them. Migration head must remain
     0016_extend_login_helper_with_agency_name. -->

## Tests Actually Executed

<!-- Exact commands + exit codes + output snippets.
     Do NOT write "tests pass" without evidence. -->

```bash
# Example:
$ cd apps/web && npx tsc --noEmit
$ echo $?
0
```

## Tests Not Executed and Why

<!-- Explicit list with reason.
     Example: "Backend tests not run — sandbox lacks sqlalchemy (ModuleNotFoundError)" -->

-

## Rollback Considerations

<!-- How to revert if something goes wrong.
     For migrations: alembic downgrade -1
     For app changes: git revert <sha> -->

## Evidence of Successful Checks

<!-- Paste actual command output. CI link if available. -->

## Verification Labels

Tick exactly one box per row:

- [ ] Backend tests: INDEPENDENTLY VERIFIED
- [ ] Backend tests: IMPLEMENTER-REPORTED only
- [ ] Backend tests: NOT EXECUTED (reason: ____ )
- [ ] Backend tests: BLOCKED BY ENVIRONMENT (reason: ____ )
- [ ] Backend tests: NOT APPLICABLE

- [ ] Frontend type-check: INDEPENDENTLY VERIFIED
- [ ] Frontend type-check: IMPLEMENTER-REPORTED only
- [ ] Frontend type-check: NOT EXECUTED (reason: ____ )
- [ ] Frontend type-check: BLOCKED BY ENVIRONMENT (reason: ____ )
- [ ] Frontend type-check: NOT APPLICABLE

- [ ] Frontend build: INDEPENDENTLY VERIFIED
- [ ] Frontend build: IMPLEMENTER-REPORTED only
- [ ] Frontend build: NOT EXECUTED (reason: ____ )
- [ ] Frontend build: BLOCKED BY ENVIRONMENT (reason: ____ )
- [ ] Frontend build: NOT APPLICABLE

- [ ] Frontend lint: INDEPENDENTLY VERIFIED
- [ ] Frontend lint: IMPLEMENTER-REPORTED only
- [ ] Frontend lint: NOT EXECUTED (reason: ____ )
- [ ] Frontend lint: BLOCKED BY ENVIRONMENT (reason: ____ )
- [ ] Frontend lint: NOT APPLICABLE

## Push Verification

- [ ] Local HEAD SHA: __________
- [ ] Remote HEAD SHA after push: __________
- [ ] SHAs match (push verified)
- [ ] GitHub commit URL: __________

<!--
  If push is BLOCKED by missing credentials, write:
  "PUSH BLOCKED — no GitHub credentials in execution environment.
   Per Rule 13 §12.3, no PAT was requested or exposed.
   Push commands documented in CONTRIBUTING.md §10.4."
-->

## Artifact Disclosure Table (per Rule 13)

<!-- List every file created or modified in this PR, with path, purpose, status, and SHA-256 (for important files). -->

| # | Full filename | Exact path | Purpose | Status | Git status | GitHub status | Downloadable? |
|---|---|---|---|---|---|---|---|
| 1 | <filename> | <path> | <purpose> | new/edited | committed/not | published/local | yes/no |
| ... | ... | ... | ... | ... | ... | ... | ... |

<!-- If no side-files were produced: "No new side-files were produced in this PR." -->

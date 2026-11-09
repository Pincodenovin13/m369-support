# Contributing to M369 Support

> **Status:** Permanent development rules. Every contributor (human or AI agent) must follow these rules. Violations block merge.
> **Last updated:** 2026-11-09

This document defines the canonical Git workflow, branch strategy, commit conventions, PR requirements, file placement rules, artifact disclosure (Rule 13), and security review process for M369 Support.

---

## 1. Branch Strategy

### 1.1 Canonical Branch

`refactor/repository-structure-unification` is the **active development/integration branch** as of 2026-11-09. New work must branch from its latest verified HEAD. `phase-1/foundation` and the other `phase-1/*` refs are historical checkpoints, not active integration targets.

> **Note on GitHub default branch:** GitHub's configured default branch is still `test/marker`, whose current tree contains only `MARKER.txt`. It is NOT the development source of truth. Changing the repository default branch to the active branch is a pending repository-admin setting change; until it is changed, always explicitly target `refactor/repository-structure-unification` in tools and PRs.

### 1.2 Branch Naming

Every branch must follow one of these prefixes:

| Prefix | Use |
|---|---|
| `feature/<short-name>` | New product feature (e.g., `feature/conversation-threading`) |
| `security/<short-name>` | Security hardening or fix (e.g., `security/agency-account-lockout`) |
| `fix/<short-name>` | Bug fix (e.g., `fix/refresh-token-race`) |
| `docs/<short-name>` | Documentation only (e.g., `docs/repository-consolidation`) |
| `refactor/<short-name>` | Code restructuring with no behavior change |
| `phase-1/<short-name>` | Reserved for the existing Phase 1 hardening branches (historical) |

### 1.3 Branch Lifecycle

1. Branch from the latest verified `refactor/repository-structure-unification` HEAD.
2. Commit focused, atomic changes.
3. Open a PR into `refactor/repository-structure-unification` (once PR-based protection is configured).
4. Preserve existing historical checkpoint/recovery branches. Do NOT delete any existing branch as part of cleanup without an explicit Product Owner decision after ancestry and artifact verification.
5. **No new long-lived feature branches.** Existing historical branches are retained as audit checkpoints; do not mistake them for active workstreams.

### 1.4 Prohibited Branch Practices

- ❌ Direct development on `phase-1/foundation` (always use a feature branch).
- ❌ Long-lived duplicate implementation branches (two branches both implementing "agency account lockout" — pick one).
- ❌ Abandoning a branch with implementation work that isn't merged or documented.
- ❌ Force-pushing any published branch (`git push --force` and `--force-with-lease` are both forbidden on shared branches).
- ❌ Rewriting, squashing, or rebasing published commit history.

---

## 2. Commit Strategy

### 2.1 Commit Message Format

```
<type>(<scope>): <short description>

<optional body — why, not what>
```

**Type** (required): `feat`, `fix`, `security`, `refactor`, `docs`, `test`, `chore`, `perf`.

**Scope** (optional, recommended): `api`, `web`, `widget`, `db`, `migration`, `infra`, `docs`, `repo`.

**Examples:**

```
security(auth): add agency account lockout with atomic counter
fix(auth): prevent concurrent refresh token reuse via atomic tver bump
test(security): add refresh rotation race regression
docs(repo): consolidate repository architecture and workflow rules
refactor(api): organize authentication dependencies
chore(deps): bump fastapi to 0.115.6
```

### 2.2 Atomic Commits

Each commit must represent **one coherent change**. Never mix:
- Security fixes with UI changes
- Documentation with code changes (unless the doc is intrinsic to the code, e.g., a docstring)
- Database migrations with application refactors
- Multiple unrelated features

### 2.3 Commit Hygiene

- ✅ Run `git diff --check` before committing (catches whitespace errors).
- ✅ Verify `git status --short` shows only intended files.
- ✅ Verify no `.env` files, no `node_modules/`, no `__pycache__/`, no `*.log` files staged.
- ❌ Never commit secrets (passwords, tokens, private keys, JWT secrets). Use `.env.example` for placeholders.
- ❌ Never commit build artifacts (`.next/`, `dist/`, `build/`).
- ❌ Never commit generated lockfiles unless deps actually changed.

---

## 3. Pull Request Rules

### 3.1 PR Template

Every PR must use `.github/PULL_REQUEST_TEMPLATE.md` (when that file exists; until it is added to the repo, replicate the structure manually). Required sections:

1. **Purpose** — one paragraph: what does this PR do and why?
2. **Exact changed files** — `git diff --stat phase-1/foundation...HEAD` output.
3. **Reason for each file change** — bulleted list, one per file or logical group.
4. **Security impact** — explicit statement: "no security impact" or a description of what changed.
5. **Database migration impact** — "no migration" or the migration filename + upgrade/downgrade summary.
6. **Tests actually executed** — exact commands run + exit codes + output snippets.
7. **Tests not executed and why** — explicit list with reason (e.g., "backend tests not run — sandbox lacks sqlalchemy").
8. **Rollback considerations** — how to revert if something goes wrong.
9. **Evidence of successful checks** — paste actual command output, not "passed".

### 3.2 PR Review Requirements

- **Code review:** at least one reviewer (human or appointed AI agent) must approve.
- **Security review:** required for any change touching `apps/api/app/security/`, `apps/api/app/api/v1/auth.py`, `apps/api/app/api/v1/super_admin/auth.py`, `apps/api/app/services/sa_auth.py`, `apps/api/app/services/rate_limit.py`, `apps/api/migrations/versions/`, `infrastructure/database/`.
- **Migration review:** any migration that touches RLS policies, role grants, or SECURITY DEFINER functions must be reviewed line-by-line.
- **Test review:** new tests must actually run in at least one environment. Tests that "pass" only because they are skipped are forbidden.

### 3.3 Merge Strategy

- **Fast-forward** preferred when the source branch is a strict descendant of the target.
- **No squash-merge** for security or migration commits — preserve the audit trail.
- **No rebase-merge** that rewrites commit SHAs — preserve published history.
- **Do not delete the source branch immediately after merge** — wait until the merge is verified on the canonical branch.

---

## 4. File Placement Rules

See `REPOSITORY_MAP.md` (when it is created) for the full file/folder responsibility map. Summary:

1. **One responsibility per file.** A route handler file does not contain service-layer DB calls.
2. **Migrations are append-only.** Never edit a published migration. New migration = new file with `NNNN_` prefix.
3. **No business logic in routers.** Routers validate input, call a service, format output.
4. **No DB queries in `models/`.** Models define schema; queries live in services or routers.
5. **No `*.env` files committed.** Only `.env.example` is tracked.
6. **No build artifacts committed.**
7. **New top-level directories require an entry in `REPOSITORY_MAP.md`.**
8. **Test files live next to the code they test.** Backend: `apps/api/tests/{unit,integration}/`. Frontend: TBD when added.

---

## 5. Migration Rules

1. **Append-only.** Never edit a published migration file. If a migration has a bug, write a new migration that fixes it.
2. **Linear chain.** `down_revision` of migration `NNNN` always points at `NNNN-1`. No branches, no merge revisions.
3. **Reversible.** Every migration must have a `downgrade()` that reverses `upgrade()`.
4. **Schema-only in Phase 1.** Data migrations are deferred — write a separate script under `apps/api/scripts/` if a data backfill is needed.
5. **Naming:** `NNNN_<short_description>.py` where NNNN is zero-padded sequential (e.g., `0017_agency_user_lockout_columns.py`).
6. **Test before push:** locally run `alembic upgrade head` then `alembic downgrade base` then `alembic upgrade head` against a fresh DB to verify both directions.
7. **Security review required** for any migration that touches RLS, role grants, or SECURITY DEFINER functions.

---

## 6. Test Requirements

### 6.1 Backend Tests

- **Unit tests** (`apps/api/tests/unit/`): pure Python, no DB. Fast. (3 files in current repo state.)
- **Integration tests** (`apps/api/tests/integration/`): require real PostgreSQL 16 + Redis 7. Verify RLS, role separation, end-to-end auth flows. (15 files in current repo state.)
- **New security code must come with tests.** Untested security code is rejected at review.
- **Test names:** `test_<thing>_<condition>` (e.g., `test_refresh_token_replay_after_rotation_rejected`).
- **No `pytest.skip` without a documented reason.** Skipped tests are tracked in STATE.md.

### 6.2 Frontend Tests

- **`[NOT IMPLEMENTED]` in Phase 1.** Adding a frontend test suite is tracked as a future task.
- Until then, frontend correctness relies on:
  - `tsc --noEmit` (independently verified PASS 2026-11-08)
  - `next lint` and `next build` (implementer-reported only; not independently verified)

### 6.3 Test Reporting

- **Never label unexecuted tests as PASS.**
- **Distinguish** in every PR: `INDEPENDENTLY VERIFIED` vs `IMPLEMENTER-REPORTED` vs `NOT EXECUTED` vs `BLOCKED BY ENVIRONMENT`.
- **Cite commands + exit codes + output snippets.** "Tests pass" without evidence is forbidden.

---

## 7. Security Review Requirements

A security review is required for any change touching:

- `apps/api/app/security/` (JWT, password hashing, encryption)
- `apps/api/app/api/v1/auth.py` or `apps/api/app/api/v1/super_admin/auth.py`
- `apps/api/app/services/sa_auth.py` or `apps/api/app/services/rate_limit.py`
- `apps/api/app/middleware/tenant_context.py`
- `apps/api/app/tenancy/context.py`
- `apps/api/migrations/versions/` (any new migration)
- `infrastructure/database/01-bootstrap-roles.sql`
- `apps/api/app/core/config.py` (security-sensitive defaults)

The review must verify:
- No secrets in defaults (config.py rejects `dev-only-*` defaults in production via `_DEV_DB_PASSWORD_FRAGMENTS` and similar lists).
- RLS policies are not weakened.
- Role grants are not broadened.
- New endpoints enforce tenant context.
- New auth flows use atomic DB updates (no read-modify-write).
- New rate-limit checks fail closed in production.

---

## 8. Code Review Requirements

- **One approval required** for non-security changes.
- **Two approvals required** for security or migration changes (or one approval from a designated security reviewer).
- **Reviewer must run the tests** if the environment supports them. If the reviewer's environment cannot run tests, the PR description must include test evidence from another environment.
- **Reviewer must read every changed line.** Skim-review is not approval.
- **Reviewer must verify the diff matches the PR description.** Surprise files in the diff block merge.

---

## 9. Prohibited Practices

| # | Prohibition |
|---|---|
| 1 | Force-push to any shared branch |
| 2 | Rewrite, squash, or rebase published commit history |
| 3 | Direct development on `phase-1/foundation` |
| 4 | Long-lived duplicate implementation branches |
| 5 | Committing `.env` files, secrets, credentials, signing keys |
| 6 | Committing build artifacts (`node_modules/`, `.next/`, `__pycache__/`, `dist/`, `build/`) |
| 7 | Editing published migration files (always append a new one) |
| 8 | Mixing unrelated changes in one commit |
| 9 | Labeling unexecuted tests as PASS |
| 10 | Using OpenLivery or any external product as an architectural reference — M369 is an independent greenfield product |
| 11 | Creating fake widget code — the widget is `[PLANNED]`, not stubbed with non-functional code |
| 12 | Claiming "pushed" based only on a successful local commit (verify the remote SHA matches) |
| 13 | Requesting or exposing a GitHub PAT in chat, logs, reports, or committed files |

---

## 10. Push Workflow

> **CRITICAL — current limitation:** The Z.ai sandbox has **NO GitHub push credentials**. `git push` fails with `fatal: could not read Username for 'https://github.com': No such device or address` (exit code 128). There is no credential helper, no PAT in the environment, no SSH key.

### 10.1 Before Every Push (run from the consolidation branch)

Run and report each command's output:

```bash
git status --short              # working tree state
git branch --show-current       # current branch
git rev-parse HEAD              # local HEAD SHA
git diff --check                # whitespace/conflict-marker errors
git diff --stat                 # change summary
```

Only proceed if `git status --short` shows only intended files and `git diff --check` is empty.

### 10.2 For Completed Work

1. **Run relevant tests** (backend if sqlalchemy available; frontend `tsc --noEmit` always).
2. **Review the final diff:** `git diff phase-1/foundation...HEAD` — verify every changed file is intended.
3. **Verify no secrets:** scan tracked files for common patterns (see §10.5 for limitations).
4. **Verify no unrelated files changed:** compare `git diff --name-only` against the PR's claimed file list.
5. **Commit only the intended files:** `git add <specific files>` — avoid `git add .` unless every untracked file is intended.
6. **Push the correct branch:** `git push origin <branch-name>`.
7. **Verify the remote SHA equals the intended commit:** `git rev-parse origin/<branch-name>` must equal `git rev-parse HEAD`.
8. **Provide the GitHub commit URL** in the PR description: `https://github.com/Pincodenovin13/m369-support/commit/<sha>`.

### 10.3 If Push Is Blocked (current state)

Per Rule 8 of the consolidation task and the Product Owner's instructions: do NOT request or expose a GitHub PAT in chat, logs, reports, or committed files. If authentication is unavailable, **stop before the push and report the exact limitation**.

The Product Owner / Technical Manager must execute the push from an environment with configured GitHub credentials.

### 10.4 Secrets Scan — Limitations (per Rule 13)

When claiming "no secrets found", the contributor must state which scan was performed and what its limitations are. Example honest claim:

> "Based on a pattern-based scan for common secret formats (Stripe `sk_live_`/`sk_test_`, AWS `AKIA...`, GitHub PAT `ghp_...`, SSH `BEGIN ... PRIVATE KEY`, and basic `password=`/`api_key=` assignments), no obvious hardcoded secrets were found in tracked files. This is NOT a comprehensive secret audit. A proper audit would require a dedicated secret-scanning tool (gitleaks/truffleHog) which is not available in this sandbox."

Patterns NOT scanned by the basic grep approach:
- JWT secrets in non-standard formats
- Generic API tokens without obvious prefixes
- Base64-encoded secrets
- Secrets split across multiple lines
- Secrets inside binary files
- Secrets in test fixtures that may look like real secrets

---

## 11. Local Development

See `docs/development/local-setup.md` for the full step-by-step setup. Quick reference:

```bash
# Backend (Python 3.12 + PostgreSQL 16 + Redis 7)
cd apps/api
pip install -r requirements-dev.txt
alembic upgrade head
python scripts/provision_sa_auth_role.py    # requires M369_SA_AUTH_PASSWORD env var
uvicorn app.main:app --reload --port 8000

# Frontend (Node 20+)
cd apps/web
npm install
npm run dev

# Docker Compose (recommended for full stack)
cp .env.example .env
# Edit .env with real passwords
docker compose up -d
```

Common commands via `Makefile`: `make help`, `make install`, `make dev`, `make dev-docker`, `make test`, `make lint`, `make migrate`, `make create-super-admin`.

---

## 12. Permanent GitHub Persistence Rules (Product Owner Mandate)

> **These 12 rules are mandated by the Product Owner and are non-negotiable.**
> They govern the prevention of work loss between local workspaces and the permanent GitHub repository at `https://github.com/Pincodenovin13/m369-support`.

1. **No meaningful change stays only in the local workspace.** Every commit that adds or modifies project code, docs, config, or migrations must be pushed to GitHub before the work is considered complete.
2. **Each completed unit is saved with a clear commit.** Atomic commits with descriptive `<type>(<scope>): <description>` messages per §2.
3. **Each valid commit is pushed immediately.** Do not batch commits across sessions — push as soon as the commit is verified locally.
4. **Every security change or migration has its own commit.** Never bundle a migration with a feature, a security fix with a doc update, etc.
5. **Before starting any new work, fetch the remote and check branch state.** `git fetch origin && git status` is mandatory before any new branch or edit.
6. **No branch is deleted without explicit Product Owner approval.** This includes stale branches, intermediate milestones, and feature branches after merge. Historical branches (e.g., `phase-1/security-closure-b1-4`) are preserved as evidence until the Product Owner explicitly approves deletion.
7. **No force-push.** `git push --force` and `git push --force-with-lease` are forbidden on shared branches. Rewriting published history is forbidden.
8. **Material changes must be visible on GitHub.** A change is not "saved" until `git rev-parse origin/<branch>` matches the local HEAD AND the commit URL on `github.com/Pincodenovin13/m369-support/commit/<sha>` is accessible.
9. **Secrets must never enter Git.** No `.env` files, no API keys, no PATs, no SSH private keys, no JWT secrets, no passwords. Use `.env.example` for placeholders. The pre-commit secrets scan must be documented with its limitations (see §10.4).
10. **Every push must be proven with the SHA and a real GitHub link.** The PR description or final report must contain: local HEAD SHA, remote HEAD SHA after push, SHAs must match, and the GitHub commit URL `https://github.com/Pincodenovin13/m369-support/commit/<sha>`.
11. **If push is not possible, the work is stopped and the limitation is reported.** No claim of "complete" or "saved" is made without a verified push. The exact failure mode (auth error, network error, rate limit, permission denied) must be captured and reported with the precise command output AND exit code (do not conflate `curl` network success with `git push` auth success).
12. **A local report never substitutes for a real GitHub push.** A "complete" status requires the commit to be visible on `github.com/Pincodenovin13/m369-support`. Until then, the status is "WORKING LOCALLY — NOT YET ON GITHUB."

### 12.1 Workflow for every future change

```
Inspect → Edit → Test → Commit → Push → Verify on GitHub
```

- **Inspect:** `git fetch origin && git status && git rev-parse HEAD`
- **Edit:** make the change with atomic intent
- **Test:** run relevant tests; record exact commands and exit codes
- **Commit:** one coherent change per commit; follow §2 message format
- **Push:** `git push origin <branch>`; capture exact output AND exit code
- **Verify on GitHub:** `git rev-parse origin/<branch>` must equal local HEAD; confirm `https://github.com/Pincodenovin13/m369-support/commit/<sha>` is accessible

### 12.2 Distinct states — do not confuse

| State | Definition |
|---|---|
| Present in workspace | File or commit exists in the local filesystem |
| Committed locally | Commit exists in `.git`; not yet on any remote |
| Pushed to remote | `git rev-parse origin/<branch>` returns the commit SHA |
| Visible on GitHub | `https://github.com/Pincodenovin13/m369-support/commit/<sha>` returns HTTP 200 |
| Merged into target branch | The commit is an ancestor of the canonical branch (`phase-1/foundation`) on GitHub |

**Only the last two states (visible on GitHub + merged into target branch) count as "saved and complete."** The first three are intermediate states and must not be reported as completion.

### 12.3 Current auth-limitation status

> **Last verified:** 2026-11-08 by Z.ai (33 authentication methods tested)
>
> The Z.ai execution environment has **NO GitHub write credentials**:
> - No `gh` CLI installed
> - No SSH keys in `~/.ssh/`
> - No GitHub token in any environment variable (`GITHUB_TOKEN`, `GH_TOKEN`, `GITHUB_PAT`, `GITHUB_AUTH_TOKEN`, `GIT_TOKEN`, `HUB_TOKEN`)
> - No git credential helper configured (system / global / local)
> - No `~/.git-credentials`, `~/.config/git/credentials`, `~/.netrc`
> - No `core.askpass` / `GIT_ASKPASS` configured
> - `sudo apt-get install gh` → password required (no sudo privileges)
> - Direct `gh` CLI binary download via curl/wget → blocked (HTTPS download returns 0 bytes; outbound binary download is restricted)
>
> **Anonymous read works** (`git ls-remote`, GitHub API GET for public repos), confirming network reachability is fine — the issue is purely authentication.
>
> **Per Rule 8 of the consolidation task and the Product Owner's instructions, no PAT is requested in chat, log, report, or committed file.**
>
> The Product Owner or Technical Manager must execute the push from an environment with GitHub credentials configured.

### 12.4 Sand-box recycling warning (added 2026-11-08)

> The Z.ai sandbox can be recycled between sessions. Per the system prompt: "The sandbox is started on demand and can be recycled between messages: everything under `/home/z/my-project/` is kept, running processes are not." However, observed behavior on 2026-11-08 showed that local git commits made in a prior session were LOST when the sandbox was recycled — the `.git` directory reverted to its earlier state, and newly-created files in `/home/z/my-project/download/patches/` were deleted.
>
> **Implication for Rule 12:** "Each valid commit is pushed immediately" is not just a workflow preference — it is a HARD REQUIREMENT for Z.ai. Local commits that are not pushed within the same session may be lost permanently. Do NOT trust that a local commit will survive to the next session.
>
> To work around this, Z.ai must:
> - Deliver completed work as patch files in `/home/z/my-project/download/` (which appears to survive recycling for files from older sessions)
> - Generate SHA-256 hashes for every delivered artifact (so integrity can be verified after recycling)
> - Re-state the full SHA + content of any work claimed in a prior session, and explicitly verify the artifact still exists on disk before claiming it is delivered

---

## 13. Artifact Disclosure & Delivery (Product Owner Mandate — Rule 13)

> **This rule is mandated by the Product Owner on 2026-11-08. It is non-negotiable and applies to ALL future tasks, phases, and reports.**
>
> **Reason:** The Product Owner uses a mobile phone and cannot easily inspect every file in the workspace's "All Files" view. Therefore, no documentation or side-output file must remain undisclosed in the report for the task that produced it.

### 13.1 Mandatory disclosure table

Whenever Z.ai (or any contributor) creates or edits a file during a task, phase, or sub-task — including but not limited to:

- `.md` and `.txt`
- `.patch` and `.diff`
- `.tar.gz` and `.zip`
- `.json` and `.yaml`
- `.log` and `.sha256`
- `.pdf` and other output files

…the contributor MUST include a table in the same task's report with the following columns:

| Required info | Description |
|---|---|
| Full filename | With extension |
| Exact path | Real path in the workspace |
| Purpose | Short description of the file's content |
| Status | New or edited |
| Git status | Committed or not committed |
| GitHub status | Published or local-only |
| Delivery possible | Downloadable attachment in chat, or NOT downloadable |

For important transferable files, also include:

| Required info | Description |
|---|---|
| Size | In bytes (and human-readable) |
| SHA-256 | For integrity verification |

### 13.2 Delivery rules

1. **If the chat platform supports file-attachment capability, deliver the file as a real attachment.** Merely announcing an internal workspace path is NOT delivery.
2. **If multiple files were produced, also create a single ZIP or TAR.GZ bundle and attach it; declare the name and status of every file inside the bundle.**
3. **If attachment capability is NOT available, explicitly write:** "The file exists in the workspace but has NOT been delivered to the Product Owner as a downloadable attachment."
4. **Never present an internal workspace path as equivalent to a download link or successful delivery.**
5. **Do not confuse temporary, test, or cache files with final deliverable files.**
6. **The disclosure table MUST appear in the end-of-task report for every task and every phase.** Even if no side-file was produced, write: "No new side-files were produced."

### 13.3 Application to this Z.ai environment (verified 2026-11-08)

| Capability | Available? | Evidence |
|---|---|---|
| `send_message` tool (for IM-mode file attachment) | ❌ NOT available | Not in this session's tool list (verified by inspecting available tools: `Task, Bash, Glob, Grep, LS, Read, Edit, MultiEdit, Write, TodoWrite, TodoRead, Skill, Complete, cron, AskUserQuestion, Outline, WebSearch, WebFetch`) |
| Files in `/home/z/my-project/download/` visible to Product Owner via gateway UI | ✅ YES | Per system prompt: "Only files here are shown to the user, anything else is invisible to them." |
| Direct chat-attachment of files in `/home/z/my-project/download/` | ❌ NOT available | No `send_message` tool in this session |
| Sandbox-recycling persistence of `/home/z/my-project/download/` files | ⚠️ PARTIAL | Files from older sessions (Nov 4-6) survived; files from a prior session in the same day (Nov 8) did NOT survive recycling |

### 13.4 Honest disclosure template

For every task report, Z.ai must include a section titled **"Artifact Disclosure Table (per Rule 13)"** with the following structure:

```markdown
## Artifact Disclosure Table (per Rule 13)

| # | Full filename | Exact path | Purpose | Status | Git status | GitHub status | Downloadable? | Size | SHA-256 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | <filename> | <path> | <purpose> | new/edited | committed/not | published/local | yes/no | <bytes> | <hash> |
| ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |

### Delivery status

- **Downloadable in chat:** ❌ NO — Z.ai's environment has no `send_message` tool to attach files directly to chat messages.
- **Visible via gateway UI:** ✅ YES — files in `/home/z/my-project/download/` are listed in the gateway's file browser.
- **Bundle delivered:** <yes/no> — if multiple files, was a single .tar.gz created?

### Files NOT delivered (if any)

(List any files that exist in the workspace but were not delivered as attachments, with the reason.)
```

If no side-files were produced:

```markdown
## Artifact Disclosure Table (per Rule 13)

No new side-files were produced in this task.
```

### 13.5 Pre-recycling delivery checklist

Before any session ends (because the sandbox may be recycled and local commits lost), Z.ai must:

1. **Generate patch files** for any unpushed commits: `git format-patch <base>..HEAD --output-directory=/home/z/my-project/download/patches/`
2. **Generate SHA-256 manifest**: `cd /home/z/my-project/download/patches && sha256sum *.patch > MANIFEST.sha256`
3. **Create a single tarball bundle**: `tar -czf /home/z/my-project/download/<task-name>-patches.tar.gz -C /home/z/my-project/download/patches .`
4. **Document the delivery** in `/home/z/my-project/download/DELIVERY_README.md` with apply instructions
5. **Include the artifact disclosure table** in the task report per §13.4
6. **Explicitly state** whether the files are downloadable as chat attachments (per §13.3, the answer is currently NO)

---

## 14. Questions and Escalation

- **Architectural questions:** open an issue labeled `question: architecture`.
- **Security questions:** open an issue labeled `security` — do NOT describe vulnerabilities in plain text; flag for private review.
- **Workflow questions:** open an issue labeled `question: workflow`.
- **Disagreements with these rules:** open a PR against `CONTRIBUTING.md` — rules are versioned with the codebase.

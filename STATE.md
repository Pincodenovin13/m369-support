# M369 Support — Project State

> **Last updated:** 2026-11-08 (UTC+8)
> **Canonical development branch:** `phase-1/foundation`
> **Current working branch:** `refactor/repository-structure-unification`
> **Recovery branch:** `recovery/zai-workspace-2026-11-08` (HEAD: `1c3294154b41e051855613416f0bc68c3901d125`)
> **Migration head (filesystem):** `0016_extend_login_helper_with_agency_name`
> **Migration head (database-applied):** UNVERIFIED — no reachable DB in audit sandbox

---

## Project Phase

**Phase 1 (Foundation + Multi-Tenancy + Security Hardening)** — implementation complete on `phase-1/security-closure-b1-4` (commit `ab046a2`). The 16 hardening commits are NOT yet merged into `phase-1/foundation` on GitHub (foundation is still at Stage 4, commit `0b3139a`). A `recovery/zai-workspace-2026-11-08` branch was created to preserve the Rule 13 documentation work + historical artifacts.

All test results below are **reported by Z.ai** (the implementation agent) from a local sandbox against a real PostgreSQL 16.2 instance. They have **not** been independently verified by a third party. The 2026-11-08 audit independently verified the frontend type-check only; backend tests could not be re-executed because the audit sandbox lacks the required Python dependencies.

---

## Completed Packages

| Package | Commit SHA | Key Deliverable |
|---|---|---|
| Stage 1 | `321ebfc` | 11 new tables (migration 0006), 4 plans seeded |
| Stage 2 | `853b557` | 27 agency endpoints + RBAC + pagination + audit logs |
| Stage 3 | `70e026f` | 26 Super Admin endpoints + billing lifecycle + payments |
| Stage 4 | `0b3139a` | 37 security audit tests, 168 total passing |
| Package A | `bde9a90` | SA auth hardening: token_version, brute-force, rate limit, TOTP MFA, migration 0010 |
| Package A.1 | `e51b7aa` | Custom Redis limiter, atomic challenge/recovery consumption, independent MFA lockout |
| Package A.2 | `88de552` | Precise TOTP replay (constraint name), savepoint, fakeredis, proxy trust boundary |
| Package A.2.1 | `b32f624` | fakeredis separated from production, XFF hardening with ipaddress validation |
| Package B | `a5a3a2c` | message_attachments agency_id + 10 composite FKs + RLS on 3 tables + least-privilege m369_sa_runner |
| Package B.1 | `9afc2f5` | FK ON DELETE corrections + dedicated m369_sa_auth role (column-level UPDATE) + m369_app fully revoked from SA tables |
| Package B.1.1 | `30b6dfd` | Provisioning script + full CRUD RLS test + effective privilege audit |
| Package B.1.1.2 | `72dfc67` | Test reliability: try/finally, returncode assertion, SQLSTATE 42501, 4×12 privilege checks |
| Package B.1.2 | `2b6905c` | Registration RLS fix (advisory lock + guard function + tenant context) + m369_super_admin neutralization + default privilege cleanup |
| Agency Token Revocation | `890f6a5` | Server-side session revocation for agency users (token_version + tver claim in JWT) |
| Package B.1.3 | `61efc4c` | Refresh cookie flow + JWT validation hardening + multi-agency login UI + dashboard fixes |
| Package B.1.3.1 | `bc2d515` | Missing frontend api-client.ts (gitignore fix) + dashboard role lookup + 401/403 separation |
| Package B.1.4 | `ab046a2` | Role cleanup + refresh-token rotation (atomic tver bump on every refresh) + frontend auth + migration 0016 |
| Rule 13 | `79b4311` (on recovery branch) | CONTRIBUTING.md with Rules 1-13 (Rule 13 = Artifact Disclosure & Delivery mandate) |

---

## Migration Chain

```
0001_initial
  → 0002_remove_admin_login
  → 0003_login_helper_function
  → 0004_fix_login_helper_acl
  → 0005_restrict_login_helper_owner
  → 0006_phase1_extended
  → 0007_fix_login_reader_acl
  → 0008_create_sa_runner_role
  → 0009_widen_paid_currency
  → 0010_sa_auth_hardening
  → 0011_tenant_isolation_hardening
  → 0012_package_b1_critical_corrections
  → 0013_package_b1_2_final_security
  → 0014_agency_user_token_version
  → 0015_revoke_super_admin_memberships_both_directions
  → 0016_extend_login_helper_with_agency_name    ← HEAD
```

**Filesystem head:** `0016_extend_login_helper_with_agency_name` (16 migrations, linear chain, verified)
**Database-applied head:** UNVERIFIED — `alembic` not run in audit sandbox; no reachable DB

---

## Test Status (strict verification labels)

| Metric | Value | Verification |
|---|---|---|
| Backend test files | 18 (3 unit + 15 integration) | INDEPENDENTLY VERIFIED (file count via `git ls-tree`) |
| Backend test functions (static count) | 346 | INDEPENDENTLY VERIFIED (count via `grep -rE 'def test_' \| wc -l`) |
| Backend test execution | 346 passing, 0 failing | Z.ai-REPORTED ONLY — NOT independently verified (sandbox lacks sqlalchemy, psycopg2, pgserver) |
| Frontend type-check (`tsc --noEmit`) | PASS (exit 0) | ✅ INDEPENDENTLY VERIFIED (2026-11-08) |
| Frontend build (`next build`) | PASS | Z.ai-REPORTED ONLY |
| Frontend lint (`next lint`) | PASS | Z.ai-REPORTED ONLY |
| Frontend test suite | 0 files | NOT IMPLEMENTED (Phase 1 has no frontend tests) |
| Docker Compose deployment | BLOCKED | Docker unavailable in sandbox |
| Real Redis integration | BLOCKED | fakeredis used for rate-limit tests |
| Clean venv install | BLOCKED | No isolated venv in sandbox |
| Reverse proxy deployment | BLOCKED | TRUSTED_PROXY_IPS tested via mocks only |
| Independent third-party test verification | BLOCKED | No third party has executed the suite |

---

## Database Roles

| Role | LOGIN | BYPASSRLS | Purpose |
|---|---|---|---|
| `m369_app` | ✅ | ❌ | Ordinary tenant operations (RLS-enforced) |
| `m369_sa_auth` | ✅ | ❌ | Super Admin login + MFA verify (column-level UPDATE) |
| `m369_sa_runner` | ✅ | ✅ | Super Admin management (BYPASSRLS, least-privilege) |
| `m369_login_reader` | ❌ | ✅ | SECURITY DEFINER function owner (login helper) |
| `m369_registration_guard` | ❌ | ✅ | Registration check function owner |
| `m369_super_admin` | ❌ | ❌ | Neutralized (was BYPASSRLS + broad DML; now inert) |

---

## Outstanding Risks (Production Readiness)

| # | Risk | Priority | Status |
|---|---|---|---|
| P0-1 | B.1.4 (16 hardening commits) NOT merged into `phase-1/foundation` on GitHub | Critical | foundation on GitHub still at Stage 4 (`0b3139a`) |
| P0-2 | No independent verification of 346 backend tests | Critical | Z.ai-reported only |
| P0-3 | No security headers (HSTS, X-Content-Type-Options, CSP, etc.) | Critical | `apps/api/app/main.py` registers only CORS + TenantContext middlewares |
| P0-4 | No request body size limits | Critical | No `max_request_size` enforcement |
| P1-1 | Agency `User` accounts have no DB-side lockout (only Redis rate limit) | Important | Asymmetric with Super Admin |
| P1-2 | No email verification flow | Important | Zero `email_verif*` references |
| P1-3 | Password policy is length-only (10/12 chars) | Important | No complexity rules |
| P1-4 | No structured logging | Important | Zero `import logging`/`structlog` |
| P1-5 | Real Redis integration never exercised | Important | fakeredis in tests |
| P1-6 | Real PostgreSQL + RLS never exercised by independent party | Important | psql not in sandbox |
| P1-7 | Reverse-proxy trusted-IP boundary not deployed | Important | No Caddy/Nginx configured |
| P2-1 | No embeddable widget | Operational | `apps/widget/src/.gitkeep` placeholder |
| P2-2 | No Knowledge Base Markdown rendering | Operational | `kb.py` sets `content_html=""` |
| P2-3 | No frontend test suite | Operational | Zero `.test.*` files |
| P2-4 | Docker Compose deployment never verified | Operational | Docker not in sandbox |
| P2-5 | GitHub default branch is `test/marker`, not `phase-1/foundation` | Operational | Requires owner approval to change |

---

## Feature Status Key

| Status | Meaning |
|---|---|
| ✅ INDEPENDENTLY VERIFIED | Verified by execution in this session (with command + exit code) |
| 🔶 IMPLEMENTER-REPORTED | Reported by Z.ai but not independently verified |
| ⏳ PLANNED | Not yet implemented |
| ❌ BLOCKED | Cannot verify due to environment limitations |
| 🚫 NOT IMPLEMENTED | Feature does not exist |

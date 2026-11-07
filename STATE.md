# M369 Support — Project State

> **Last updated:** 2026-11-07
> **Branch:** `phase-1/agency-auth-integration-closure`
> **Documentation base commit:** `0fb6dc1e5bfa8a831e8ec75172aeeb1e322e20be`
> **Current HEAD:** Same as documentation base (this is the latest commit).

---

## Project Phase

**Phase 1 (Foundation + Multi-Tenancy + Security Hardening)** — implementation complete. Test results below are **reported by Z.ai** (the implementation agent) against a local PostgreSQL 16.2 sandbox. They have **not** been independently verified by a third party. Independent verification and production deployment are pending.

---

## Completed Packages

The following packages have been implemented and pushed to GitHub on this branch. Each commit is independently reviewable.

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
| Documentation | `0fb6dc1` | STATE.md, PROJECT_STRUCTURE.md, README.md, phase-1.md updates |

---

## Migration Chain

```
0001_initial → 0002_remove_admin_login → 0003_login_helper →
0004_fix_login_helper_acl → 0005_restrict_login_helper_owner →
0006_phase1_extended → 0007_fix_login_reader_acl →
0008_create_sa_runner_role → 0009_widen_paid_currency →
0010_sa_auth_hardening → 0011_tenant_isolation_hardening →
0012_package_b1_critical_corrections → 0013_package_b1_2_final_security →
0014_agency_user_token_version
```

**Head:** `0014_agency_user_token_version`

---

## Test Status

The following results are **reported by Z.ai** (the implementation agent) from a local sandbox environment. They have **not** been independently verified by a third party. All backend tests run against a real PostgreSQL 16.2 instance via `pgserver`; rate-limit tests use `fakeredis` (not a real Redis server).

| Metric | Value | Verification |
|---|---|---|
| Backend tests — reported | 346 passing, 0 failing | Z.ai-reported; not independently verified |
| Backend environment | PostgreSQL 16.2 (pgserver) | Z.ai sandbox |
| Frontend type-check — reported | PASS (`tsc --noEmit`) | Z.ai-reported |
| Frontend build — reported | PASS (`next build`) | Z.ai-reported |
| Frontend lint — reported | PASS (`next lint`) | Z.ai-reported |
| Docker Compose deployment | ❌ BLOCKED | Docker unavailable in sandbox |
| Real Redis integration | ❌ BLOCKED | fakeredis used for rate-limit tests |
| Clean venv install | ❌ BLOCKED | No isolated venv in sandbox |
| Reverse proxy deployment | ❌ BLOCKED | TRUSTED_PROXY_IPS tested via mocks only |

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

## Current Blockers (Production Readiness)

| # | Blocker | Status | Reason |
|---|---|---|---|
| B1 | Docker Compose not verified | BLOCKED | Docker unavailable in sandbox |
| B2 | Real Redis not verified | BLOCKED | fakeredis used for rate-limit tests |
| B3 | Clean venv install not verified | BLOCKED | No isolated venv in sandbox |
| B4 | Reverse proxy not deployed | BLOCKED | TRUSTED_PROXY_IPS logic tested via mocks only |
| B5 | Independent test verification | BLOCKED | No third-party has independently executed the test suite |

---

## Next Planned Work

1. **Independent verification** — a third party should clone the repository, install dependencies, and execute the full test suite against a real PostgreSQL instance.
2. **Docker integration test** — deploy `docker compose up` with real secrets, verify migration + provisioning + API startup.
3. **Real Redis test** — verify Lua INCR+EXPIRE + fail-closed behavior against a real Redis server.
4. **Clean venv install** — `pip install -r requirements-dev.txt` in a fresh venv.
5. **Package C** — pending independent verification of Phase 1 security.
6. **Access token TTL review** — currently 7 days (shared agency + SA); safe due to token_version revocation, but consider splitting.
7. **Agency brute-force lockout** — rate limiting exists but no per-account lockout counter (unlike Super Admin).

---

## Feature Status Key

| Status | Meaning |
|---|---|
| ✅ Implemented + Z.ai-tested | Code exists; Z.ai executed tests in sandbox and reports passing |
| 🔶 Implemented | Code exists but Z.ai has not executed tests or tests are blocked |
| ⏳ Planned | Not yet implemented |
| ❌ BLOCKED | Cannot verify due to environment limitations |
| 🔍 Independently verified | A third party has confirmed by executing tests independently (none yet) |

# Testing

## Test Pyramid (Phase 1)

| Level | Files | Functions (static count) | Database | Execution status |
|---|---|---|---|---|
| Unit | 3 | (subset of 346) | None | Z.ai-REPORTED only |
| Integration | 15 | (subset of 346) | Real PostgreSQL 16 | Z.ai-REPORTED only |
| E2E | 0 | 0 | (Phase 2+) | NOT IMPLEMENTED |
| Frontend | 0 | 0 | — | NOT IMPLEMENTED |

**Total backend test files:** 18 (3 unit + 15 integration)
**Total backend test functions (static count):** 346 — verified via `grep -rE '^\s*(def \|async def )test_' apps/api/tests/ \| wc -l`

## Running Tests

```bash
cd apps/api

# All tests
pytest tests/ -v

# Unit only (no DB needed)
pytest tests/unit/ -v

# Integration (requires PostgreSQL 16 + Redis 7)
pytest tests/integration/ -v
```

## Test Status Definitions (strict labels per CONTRIBUTING.md Rule 13)

| Label | Meaning |
|---|---|
| **INDEPENDENTLY VERIFIED** | Test was actually executed by a third party (or Z.ai in the current session) and succeeded. Command + exit code + output documented. |
| **IMPLEMENTER-REPORTED** | Z.ai (the implementation agent) reported the result but it was NOT independently verified. |
| **NOT EXECUTED** | Test was not executed in the current verification session. Reason documented. |
| **BLOCKED** | Test could not be executed due to environment limitations (missing dependency, no DB, no Docker, etc.). |
| **NOT IMPLEMENTED** | The test or feature does not exist. |

**Never report PASS based on code inspection alone.** A test is PASS only if it was actually executed successfully.

## Phase 1 Verification Status

| Check | Status | Evidence |
|---|---|---|
| Backend test files count | ✅ INDEPENDENTLY VERIFIED | 18 files (3 unit + 15 integration) — verified via `git ls-tree` |
| Backend test function count (static) | ✅ INDEPENDENTLY VERIFIED | 346 functions — verified via `grep` count |
| Backend test execution (346 passing) | 🔶 IMPLEMENTER-REPORTED | Z.ai-reported 346 passing, 0 failing against real PostgreSQL 16.2. NOT independently verified — sandbox lacks sqlalchemy, psycopg2, pgserver, pytest_postgresql. |
| Frontend type-check (`tsc --noEmit`) | ✅ INDEPENDENTLY VERIFIED | Exit 0, no output — verified 2026-11-08 |
| Frontend build (`next build`) | 🔶 IMPLEMENTER-REPORTED | Z.ai-reported PASS. Not re-run. |
| Frontend lint (`next lint`) | 🔶 IMPLEMENTER-REPORTED | Z.ai-reported PASS. Not re-run. |
| Frontend test suite | 🚫 NOT IMPLEMENTED | Zero `.test.*` files; no `test` script in `package.json` |
| Docker Compose deployment | ❌ BLOCKED | Docker unavailable in sandbox |
| Real Redis integration | ❌ BLOCKED | `fakeredis` used for rate-limit tests; `redis-cli` not in sandbox |
| Clean venv install | ❌ BLOCKED | No isolated venv in sandbox |
| Reverse proxy deployment | ❌ BLOCKED | `TRUSTED_PROXY_IPS` tested via mocks only |
| Independent third-party test verification | ❌ BLOCKED | No third party has executed the suite |

## Backend Test Environment Requirements

To independently verify the 346 backend tests, a third party needs:

| Requirement | Why |
|---|---|
| Python 3.12 | Runtime version |
| PostgreSQL 16 | RLS policies, composite FKs, SECURITY DEFINER functions |
| Redis 7 | Rate-limit backend (custom atomic INCR+EXPIRE limiter) |
| `pip install -r requirements-dev.txt` | Installs: fastapi, sqlalchemy, alembic, psycopg2/3, pytest, ruff, mypy, fakeredis, argon2-cffi, pydantic, pydantic-settings, cryptography, redis, pyjwt |

See `/STATE.md` for the full environment-limitations table.

## What the Tests Cover

| Test file | Coverage |
|---|---|
| `test_stage2_api_rbac.py` | 27 agency endpoints + RBAC + pagination |
| `test_stage3_super_admin_billing.py` | 26 Super Admin endpoints + billing lifecycle |
| `test_stage4_security_audit.py` | 37 security audit tests (Stage 4) |
| `test_stage5_sa_auth_hardening.py` | Super Admin auth: token_version, brute-force, rate limit, TOTP MFA |
| `test_stage5_package_a*_corrections.py` | Custom Redis limiter, atomic challenge consumption, MFA lockout |
| `test_stage6_package_b*_tenant_isolation.py` | RLS hardening, composite FKs, role separation |
| `test_stage7_package_b1_2_final_security.py` | Registration RLS fix, m369_super_admin neutralization |
| `test_stage8_agency_token_revocation.py` | Agency token_version revocation + refresh-token rotation |
| `test_rls_bypass_attack.py` | RLS bypass attack scenarios |
| `test_security_tenant_isolation.py` | Tenant isolation + RLS verification |
| `test_auth_tenant_context.py` | Auth + tenant context integration |
| `test_config.py` (unit) | Pydantic settings validation |
| `test_security_and_utils.py` (unit) | JWT + password hashing utilities |
| `test_compose_isolation.py` (unit) | Docker Compose config isolation |

# Agency Session Revocation

## Overview

Agency users can now revoke their sessions server-side via `token_version`. This document describes the architecture, behavior, and migration path.

## Architecture

### Database Column

```sql
-- Migration 0014
ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0;
```

Every `User` row has a `token_version` integer, starting at 0.

### JWT Claims

Both access and refresh tokens carry a `tver` claim:

```json
{
  "sub": "<user-uuid>",
  "type": "agency",
  "agency_id": "<agency-uuid>",
  "tver": 0,
  ...
}
```

### Access Token Validation

In `get_current_user` (dependencies/__init__.py):

1. Decode the JWT.
2. Extract `tver` from the payload.
3. Verify it is a non-negative integer (reject `bool`).
4. Compare against `user.token_version`.
5. Mismatch → HTTP 401 "Session revoked".

### Refresh Token Validation + Refresh-Token Rotation (Package B.1.4)

In `/auth/refresh` (auth.py), the endpoint implements **refresh-token rotation** — each refresh atomically invalidates the old refresh token:

1. Decode the refresh token.
2. Extract `tver`.
3. Same validation as access token (reject if `tver` ≠ `user.token_version`).
4. Verify the user's membership for the token's `agency_id` is still active (reject with 403 if revoked).
5. **Atomically bump `token_version`** via SQL:
   ```sql
   UPDATE users SET token_version = token_version + 1 WHERE id = ? RETURNING token_version
   ```
6. Issue new access + refresh tokens with the NEW `token_version`.
7. Set new cookies on the response.

**Why rotation matters:** The old refresh token's `tver` no longer matches, so it **cannot be replayed** even if stolen. This is a race-safe atomic SQL UPDATE with RETURNING — no Python read-modify-write, no concurrency gap.

### Logout

In `/auth/logout` (auth.py):

1. Authenticate the user (via `get_current_user`).
2. Execute atomic SQL:
   ```sql
   UPDATE users SET token_version = token_version + 1 WHERE id = ? RETURNING token_version
   ```
3. Commit.
4. Delete both cookies on the same Response.

After logout, all previously-issued access AND refresh tokens are invalid.

## Behavior: Before and After Logout

| Action | Before Logout | After Logout |
|--------|--------------|--------------|
| GET /auth/me with old access token | 200 OK | 401 Session revoked |
| POST /auth/refresh with old refresh token | 200 + new tokens | 401 Invalid or revoked |
| POST /auth/logout (second time) | 204 | 401 (token already revoked) |

## Migration

- **Migration ID:** `0014_agency_user_token_version`
- **down_revision:** `0013_package_b1_2_final_security`
- **Operation:** `ADD COLUMN` (non-destructive, defaults to 0)
- **Downgrade:** `DROP COLUMN` (removes the column)

## Files Changed

| File | Change |
|------|--------|
| `apps/api/app/models/__init__.py` | Added `token_version` to `User` model |
| `apps/api/app/security/jwt.py` | `create_access_token` + `create_refresh_token` now require `token_version` for agency tokens |
| `apps/api/app/api/v1/auth.py` | `_issue_tokens_for` passes `token_version`; `refresh` validates `tver`; `logout` atomically bumps `token_version` |
| `apps/api/app/dependencies/__init__.py` | `get_current_user` validates `tver` against `user.token_version` |
| `apps/api/tests/conftest.py` | `_register_agency` passes `token_version` |
| `apps/api/tests/integration/test_stage8_agency_token_revocation.py` | 17 new tests |
| `apps/api/migrations/versions/0014_agency_user_token_version.py` | Migration |

## Test Status

⚠️ **The test results below are Z.ai-REPORTED, NOT independently verified.** Per `/STATE.md`, the audit sandbox lacks `sqlalchemy`/`psycopg2`/`pgserver`, so backend tests cannot be re-executed by a third party. These results are preserved as Z.ai's self-report from the original implementation session.

```
$ python3 -m pytest -q
344 passed in 73.53s
```

### Test IDs (Z.ai-reported)

| ID | Test | Z.ai-reported result |
|----|------|---------------------|
| ATK-01 | Access token with valid tver accepted | PASS (Z.ai-reported) |
| ATK-02 | Access token without tver rejected (401) | PASS (Z.ai-reported) |
| ATK-03 | Access token with wrong tver rejected (401) | PASS (Z.ai-reported) |
| ATK-04 | Refresh token with valid tver accepted | PASS (Z.ai-reported) |
| ATK-05 | Refresh token without tver rejected (401) | PASS (Z.ai-reported) |
| ATK-06 | Refresh token with wrong tver rejected (401) | PASS (Z.ai-reported) |
| ATK-07 | After logout, old access token → 401 | PASS (Z.ai-reported) |
| ATK-08 | After logout, old refresh token → 401 | PASS (Z.ai-reported) |
| ATK-09 | Old refresh token cannot issue new access | PASS (Z.ai-reported) |
| ATK-10 | Logout returns 204 | PASS (Z.ai-reported) |
| ATK-11 | Cookie deletion headers present | PASS (Z.ai-reported) |
| ATK-12 | Concurrent logout — token_version atomic | PASS (Z.ai-reported) |
| ATK-13 | Register produces versioned token | PASS (Z.ai-reported) |
| ATK-13b | Login produces versioned token | PASS (Z.ai-reported) |
| ATK-14 | Refresh produces versioned tokens (rotation) | PASS (Z.ai-reported) |
| ATK-15 | Super Admin auth unaffected | PASS (Z.ai-reported) |
| ATK-16 | Tenant isolation + RLS intact | PASS (Z.ai-reported) |

## Remaining Limitations

1. **Token expiry still applies**: A token with the correct `tver` but past its `exp` is still rejected (standard JWT behavior).
2. **No per-device logout**: `token_version` is global — logging out on one device revokes all devices. Per-device revocation requires a session table (Phase 2).
3. **Access token TTL unchanged**: The `jwt_access_token_minutes` setting (default 7 days) is shared between agency and Super Admin. Splitting this is a config change, not a security issue — the `tver` check makes long-lived tokens safe because they can be revoked.

## Commits

| Commit | Branch | Description |
|---|---|---|
| `890f6a5` | `phase-1/agency-token-revocation` | Initial agency token_version revocation (migration 0014) |
| `ab046a2` | `phase-1/security-closure-b1-4` | Package B.1.4: added refresh-token rotation (atomic `tver` bump on every refresh) |

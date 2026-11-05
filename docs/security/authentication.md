# Authentication & Authorization

## Password Hashing

Argon2id (RFC 9106) via `argon2-cffi`:
- `time_cost`: 3
- `memory_cost`: 65536 KiB (64 MiB)
- `parallelism`: 2
- `type`: `Type.ID` (argon2id)

## JWT — Three Token Classes

| Class | Signing Key | Type Claim | Decoder |
|---|---|---|---|
| Agency access | `JWT_SECRET_KEY` | `agency` | `decode_access_token` |
| Super Admin access | `JWT_SUPER_ADMIN_SECRET_KEY` | `super_admin` | `decode_super_admin_token` |
| Refresh | Same as access sibling | `refresh` | `decode_refresh_token` |

Type-strict decoding: each decoder only accepts its own `type` claim.

## Cookies

- HTTP-only, Secure (production), SameSite=Lax
- `access_token` — path `/`
- `refresh_token` — path `/api/v1/auth`
- `super_admin_access_token` — separate cookie

## RBAC Roles

| Role | Permissions |
|---|---|
| `owner` | Full agency control |
| `admin` | All except deleting agency |
| `manager` | Teams, workspaces, conversations |
| `agent` | Conversations, contacts |
| `viewer` | Read-only |

## API Endpoints

14 endpoints — see `apps/api/app/api/v1/`.

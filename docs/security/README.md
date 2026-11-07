# M369 Support — Security Documentation

## Phase 1 Security Hardening

This directory contains security documentation for the M369 Support platform.

## Documents

- [Agency Session Revocation](./agency-session-revocation.md) — How token_version enables server-side logout for agency users.

## Security Architecture Summary

### Three-Role Database Model

| Role | LOGIN | BYPASSRLS | Purpose |
|------|-------|-----------|---------|
| `m369_app` | ✅ | ❌ | Ordinary tenant operations (RLS-enforced) |
| `m369_sa_auth` | ✅ | ❌ | Super Admin login + MFA verify (column-level UPDATE) |
| `m369_sa_runner` | ✅ | ✅ | Super Admin management (cross-tenant) |

### Token Versioning

Both agency users (`users.token_version`) and Super Admins (`super_admins.token_version`) carry a `tver` claim in their JWT. On logout, `token_version` is atomically incremented via SQL `UPDATE ... SET token_version = token_version + 1 RETURNING`, invalidating all previously-issued tokens.

### RLS Coverage

16 tenant-owned tables have RLS ENABLE + FORCE. The `agency_notes` table has a `USING(false)` policy making it platform-private. `m369_app` has no access to Super Admin tables (revoked in migration 0012).

### Registration Guard

The `is_initial_agency_registration_open()` SECURITY DEFINER function bypasses RLS to check whether any agency exists globally. Registration uses a PostgreSQL advisory lock to prevent concurrent first-agency creation.

# Database Schema

## Tables (11)

### Identity
- `super_admins` — platform-level admin (separate from users)
- `users` — global identity (multi-agency via memberships)

### Tenant
- `agencies` — tenant root
- `workspaces` — sub-organization
- `agency_memberships` — user ↔ agency with role
- `teams` — workspace-scoped
- `team_memberships` — composite FK prevents cross-agency
- `contacts` — customer records
- `conversations` — conversation thread

### Audit
- `audit_logs` — agency-scoped (RESTRICT on delete)
- `super_admin_audit_logs` — separate

## RLS Policies

8 tenant-owned tables with `ENABLE + FORCE ROW LEVEL SECURITY`.

## Composite Foreign Keys (4)

See `docs/security/tenant-isolation.md`.

## Database Roles

- `m369_app` — application login (NOT a PostgreSQL superuser)
- `m369_super_admin` — NOLOGIN role for bypass access

## Migration

- File: `apps/api/migrations/versions/0001_initial.py`
- Revision: `0001_initial`
- Apply: `alembic upgrade head`

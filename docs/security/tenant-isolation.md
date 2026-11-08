# Tenant Isolation — How It Works

M369 Support uses **defense in depth** for tenant isolation. No single layer is trusted alone.

## Layer 1: Database RLS

Every tenant-owned table has RLS enabled with `FORCE ROW LEVEL SECURITY`.

### Policy pattern (current — NO `app.bypass_rls`)

```sql
CREATE POLICY tenant_isolation_<table> ON <table>
USING (
    <filter_column>::text = current_setting('app.tenant_id', true)
)
WITH CHECK (
    <filter_column>::text = current_setting('app.tenant_id', true)
);
```

- `USING` filters rows on SELECT, UPDATE, DELETE
- `WITH CHECK` validates rows on INSERT, UPDATE
- `current_setting('app.tenant_id', true)` returns empty string when unset → RLS fails closed
- **There is NO bypass mechanism in RLS policies.** The previous `app.bypass_rls` GUC was a security vulnerability — any database user could `SET LOCAL` it. It has been removed entirely.

### Tables with RLS (17)

| Group | Tables | Filter column |
|---|---|---|
| Initial (migration 0001) | `agencies`, `workspaces`, `agency_memberships`, `teams`, `team_memberships`, `contacts`, `conversations`, `audit_logs` | `agency_id` (or `id` for `agencies`) |
| Phase 1 extended (migration 0006) | `messages`, `channels`, `kb_categories`, `kb_articles`, `canned_responses`, `payments` | `agency_id` |
| Hardened (migration 0011) | `subscriptions`, `message_attachments`, `agency_notes` | `agency_id` |

## Layer 2: Composite Foreign Keys

10 composite FK constraints enforce that a child row's `agency_id` matches its parent's `agency_id` — preventing cross-tenant references even when an attacker knows a foreign UUID. Examples: `messages(conversation_id, agency_id) → conversations(id, agency_id)`, `message_attachments(message_id, agency_id) → messages(id, agency_id)`.

## Layer 3: Application — Tenant Context Middleware

`TenantContextMiddleware` resolves the JWT (agency or super_admin) from `Authorization: Bearer <token>` or HttpOnly cookies, stores `TenantContext` on `request.state.tenant`.

## Layer 4: `SET LOCAL app.tenant_id`

`set_tenant_context(db, agency_id)` issues `SET LOCAL app.tenant_id = '<uuid>'` on the SQLAlchemy session. `SET LOCAL` is transaction-scoped — pooled connections cannot leak tenant scope to the next request.

## Layer 5: `assert_tenant_owned()`

Fail-closed ownership check after fetching records. A record without `agency_id` is rejected, not silently returned.

## Super Admin Access (NOT a bypass)

Super Admin tokens do NOT carry `agency_id`. They see no tenant data by default. Super Admin operations use a **separate database connection** with a role that has the `BYPASSRLS` attribute (`m369_sa_runner` for management, `m369_sa_auth` for login). The `m369_app` role used by the API service is fully revoked from Super Admin tables and has NO `BYPASSRLS` privilege.

There is **no `bypass_rls_for_super_admin(db)` function** and no `app.bypass_rls` GUC. The previous bypass mechanism was a security vulnerability and has been removed.

## Database Roles (6)

| Role | LOGIN | BYPASSRLS | Purpose |
|---|---|---|---|
| `m369_app` | ✅ | ❌ | Ordinary tenant operations (RLS-enforced) — used by API service |
| `m369_sa_auth` | ✅ | ❌ | Super Admin login + MFA verify (column-level UPDATE on `super_admins`) |
| `m369_sa_runner` | ✅ | ✅ | Super Admin management (BYPASSRLS, least-privilege) |
| `m369_login_reader` | ❌ | ✅ | SECURITY DEFINER function owner (login helper) |
| `m369_registration_guard` | ❌ | ✅ | Registration check function owner |
| `m369_super_admin` | ❌ | ❌ | Neutralized (was BYPASSRLS + broad DML; now inert) |

## Verification

RLS tests are in `apps/api/tests/integration/test_security_tenant_isolation.py` and `test_rls_bypass_attack.py`. Test execution status: Z.ai-reported, NOT independently verified (sandbox lacks sqlalchemy). See `/STATE.md`.

# Tenant Isolation — How It Works

M369 Support uses **defense in depth** for tenant isolation. No single layer is trusted alone.

## Layer 1: Database RLS

Every tenant-owned table has RLS enabled with `FORCE ROW LEVEL SECURITY`.

### Policy pattern

```sql
CREATE POLICY tenant_isolation_<table> ON <table>
USING (
    current_setting('app.bypass_rls', true) = 'on'
    OR <filter_column>::text = current_setting('app.tenant_id', true)
)
WITH CHECK (
    current_setting('app.bypass_rls', true) = 'on'
    OR <filter_column>::text = current_setting('app.tenant_id', true)
);
```

- `USING` filters rows on SELECT, UPDATE, DELETE
- `WITH CHECK` validates rows on INSERT, UPDATE
- `current_setting('app.tenant_id', true)` returns empty string when unset → RLS fails closed
- `current_setting('app.bypass_rls', true) = 'on'` is the Super Admin escape hatch

### Tables with RLS (8)

| Table | Filter column |
|---|---|
| `agencies` | `id` |
| `workspaces` | `agency_id` |
| `agency_memberships` | `agency_id` |
| `teams` | `agency_id` |
| `team_memberships` | `agency_id` |
| `contacts` | `agency_id` |
| `conversations` | `agency_id` |
| `audit_logs` | `agency_id` |

## Layer 2: Composite Foreign Keys

| Constraint | Prevents |
|---|---|
| `fk_team_memberships_team_agency` | Cross-agency team assignment |
| `fk_conversations_contact_workspace` | Cross-workspace contact reference |
| `fk_conversations_assignee_agency` | Cross-agency user assignment |
| `fk_conversations_team_agency` | Cross-agency team assignment |

## Layer 3: Application — Tenant Context Middleware

Resolves JWT → `TenantContext` → stores on `request.state.tenant`.

## Layer 4: `SET LOCAL app.tenant_id`

Transaction-scoped — pooled connections cannot leak tenant scope.

## Layer 5: `assert_tenant_owned()`

Fail-closed ownership check after fetching records.

## Super Admin Bypass

Super Admin tokens do NOT carry `agency_id`. They see no tenant data by default. To access tenant data, routes must explicitly call `bypass_rls_for_super_admin(db)`.

## Verification

22 tests verify all of the above — see `apps/api/tests/integration/test_security_tenant_isolation.py`.

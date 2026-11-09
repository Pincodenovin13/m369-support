# Tenant Isolation — Current Design and Security Boundaries

M369 uses layered tenant isolation. The database schema, API authorization, and request-scoped tenant context must agree; none of these layers should be treated as a substitute for the others.

## 1. Row-Level Security

RLS is enabled and forced on **17 tables** (16 tenant-isolated + 1 platform-private):

| Group | Tables | Policy |
|---|---|---|
| Initial (0001) | `agencies`, `workspaces`, `agency_memberships`, `teams`, `team_memberships`, `contacts`, `conversations`, `audit_logs` | Tenant policy; `agencies.id` or `agency_id` |
| Extended tables (enabled by 0019) | `messages`, `channels`, `kb_categories`, `kb_articles`, `canned_responses`, `payments` | Signed tenant policy on `agency_id` |
| Hardened (0011) | `subscriptions`, `message_attachments` | Tenant policy on `agency_id` |
| Platform-private (0011) | `agency_notes` | `USING (false)` and `WITH CHECK (false)`; Super Admin runner bypasses RLS |

Therefore, **16 tables use an agency-specific RLS policy** and one platform-private table uses a deny-all policy for roles subject to RLS.

Tenant policies compare the row's agency identifier with `public.m369_current_tenant_id()`. That SECURITY DEFINER function returns a UUID only when the transaction-local `app.tenant_id` and `app.tenant_sig` settings contain a valid HMAC-SHA256 pair. Missing, malformed, forged, or mismatched context returns NULL (fail-closed). All 17 tables use both `ENABLE ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY`.

There is no `app.bypass_rls` policy or GUC-based Super Admin bypass.

## 2. Composite Foreign Keys

There are **16 composite foreign-key constraints** protecting tenant/workspace relationships:

- Initial schema (0001): `fk_team_memberships_team_agency`, `fk_conversations_contact_workspace`, `fk_conversations_assignee_agency`, `fk_conversations_team_agency`.
- Tenant hardening (0011; one FK's delete behavior corrected in 0012): `fk_channels_workspace_agency`, `fk_kb_categories_workspace_agency`, `fk_kb_categories_parent_ws_agency`, `fk_kb_articles_workspace_agency`, `fk_kb_articles_category_ws_agency`, `fk_canned_responses_workspace_agency`, `fk_conversations_workspace_agency`, `fk_payments_subscription_agency`, `fk_messages_reply_to_agency`, `fk_message_attachments_message_agency`.
- Workspace consistency correction (0018): `fk_contacts_workspace_agency`, `fk_teams_workspace_agency`.

Migration 0018 validates existing data before adding the last two constraints. It aborts rather than silently accepting mismatched contacts or teams.

## 3. Request Authentication and Tenant Context

- `TenantContextMiddleware` decodes the agency or Super Admin JWT and stores a context on `request.state`.
- `get_current_user` checks the user exists, is active, and the JWT `tver` matches the database `token_version`.
- `get_current_agency_id` verifies active membership in the agency and that the agency itself is active.
- `require_role(...)` checks the membership role for write/admin operations.
- `set_tenant_context` signs the canonical `m369:tenant:v1:<lowercase-uuid>` string and sets both GUCs transaction-locally using bound parameters. Test/helper calls do not persist across transactions by default; the authenticated request dependency explicitly opts into session restoration for post-commit refresh operations.
- The SQLAlchemy `after_begin` listener restores both the tenant UUID and its signature only when the authenticated dependency marked the session for persistence.

The API also adds explicit agency predicates to tenant queries. These predicates are defense in depth; RLS and composite constraints remain necessary.

## 4. Database Roles and Privileges

| Role | LOGIN | BYPASSRLS | Intended use |
|---|---:|---:|---|
| `m369_app` | Yes | No | Agency API runtime |
| `m369_sa_auth` | Yes | No | Super Admin login/MFA only |
| `m369_sa_runner` | Yes | Yes | Super Admin management; table grants are restricted |
| `m369_login_reader` | No | Yes | Owner of the narrowly scoped login membership function; SELECT on agencies/memberships only |
| `m369_registration_guard` | No | Yes | Owner of the initial-registration check function |
| `m369_tenant_context` | No | No | SECURITY DEFINER owner of the HMAC verifier; SELECT only on the private signing-key table |
| `m369_super_admin` | No | No | Neutralized legacy role; no active privilege path |

Migration 0017 removes `CREATE` on schema `public` from `m369_app` and `PUBLIC`, while preserving `USAGE`. The bootstrap script now grants schema `USAGE`, not `ALL`.

## 5. Important Trust Boundary — Signed Tenant Context

A raw `app.tenant_id` custom GUC is user-settable by `m369_app` and cannot be trusted on its own. Migration 0019 closes that gap for SQL injection/arbitrary SQL under the runtime role:

1. The API signs `m369:tenant:v1:<canonical-lowercase-uuid>` with HMAC-SHA256 using `M369_TENANT_CONTEXT_SECRET`.
2. PostgreSQL recomputes and compares the HMAC inside `public.m369_current_tenant_id()`.
3. The key is stored in `m369_private.tenant_context_secret`; `m369_app` has no USAGE on the private schema and no SELECT privilege on the key table.
4. The verifier is SECURITY DEFINER with fixed `search_path=pg_catalog`, owned by `m369_tenant_context` (NOLOGIN, NOBYPASSRLS), and EXECUTE is granted only to `m369_app`.
5. All 16 tenant policies use the verifier; `agency_notes` remains deny-all.

The same secret must be provisioned to the migration runner and API process. Production startup rejects a short or development key. Never put the production value in Git, logs, client code, or a message. A compromise of the API process/environment or the HMAC key can still forge context; HMAC does not defend against full API host compromise.

## 6. Verification Status

GitHub Actions run [`42589912453`](https://github.com/Pincodenovin13/m369-support/actions/runs/42589912453) executed the migration chain on PostgreSQL 16 and ran the focused tenant-isolation/security suite: **73 passed, 4 deselected, 1 warning (12.42s)**. Coverage includes valid signed access, unsigned/mismatched tenant forgery, private-key access denial, ENABLE/FORCE + verifier policy on all 16 tenant tables, cross-tenant CRUD attempts, the bypass-GUC attack tests, API RBAC/IDOR routes, and attachment RLS.

The complete backend suite was not run green in this workflow: legacy rate-limit and downgrade tests were excluded from the focused security command. The persistent deployment database and Docker Compose deployment remain unverified. Migration 0019 deliberately refuses downgrade to the unsigned-GUC security model.

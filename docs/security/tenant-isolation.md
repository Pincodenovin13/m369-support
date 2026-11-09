# Tenant Isolation — Current Design and Security Boundaries

M369 uses layered tenant isolation. The database schema, API authorization, and request-scoped tenant context must agree; none of these layers should be treated as a substitute for the others.

## 1. Row-Level Security

RLS is enabled and forced on **17 tables**:

| Group | Tables | Policy |
|---|---|---|
| Initial (0001) | `agencies`, `workspaces`, `agency_memberships`, `teams`, `team_memberships`, `contacts`, `conversations`, `audit_logs` | Tenant policy; `agencies.id` or `agency_id` |
| Extended (0006) | `messages`, `channels`, `kb_categories`, `kb_articles`, `canned_responses`, `payments` | Tenant policy on `agency_id` |
| Hardened (0011) | `subscriptions`, `message_attachments` | Tenant policy on `agency_id` |
| Platform-private (0011) | `agency_notes` | `USING (false)` and `WITH CHECK (false)`; Super Admin runner bypasses RLS |

Therefore, **16 tables use an agency-specific RLS policy** and one platform-private table uses a deny-all policy for roles subject to RLS.

Tenant policies compare the row's agency identifier with `current_setting('app.tenant_id', true)`. Missing tenant context fails closed. All listed tables use both `ENABLE ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY`.

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
- `set_tenant_context` sets `app.tenant_id` transaction-locally. The SQLAlchemy `after_begin` listener re-applies the tenant value after a transaction boundary using the validated session value.

The API also adds explicit agency predicates to tenant queries. These predicates are defense in depth; RLS and composite constraints remain necessary.

## 4. Database Roles and Privileges

| Role | LOGIN | BYPASSRLS | Intended use |
|---|---:|---:|---|
| `m369_app` | Yes | No | Agency API runtime |
| `m369_sa_auth` | Yes | No | Super Admin login/MFA only |
| `m369_sa_runner` | Yes | Yes | Super Admin management; table grants are restricted |
| `m369_login_reader` | No | Yes | Owner of the narrowly scoped login membership function; SELECT on agencies/memberships only |
| `m369_registration_guard` | No | Yes | Owner of the initial-registration check function |
| `m369_super_admin` | No | No | Neutralized legacy role; no active privilege path |

Migration 0017 removes `CREATE` on schema `public` from `m369_app` and `PUBLIC`, while preserving `USAGE`. The bootstrap script now grants schema `USAGE`, not `ALL`.

## 5. Important Trust Boundary — Tenant GUC

**RLS based on `app.tenant_id` is not, by itself, protection against an attacker who can execute arbitrary SQL as `m369_app`.** PostgreSQL custom GUCs such as `app.tenant_id` can be set by that database role. Someone with arbitrary SQL execution under the shared runtime credential could change the value and attempt to read another tenant's rows.

The current design therefore relies on the API being the trusted holder of the database credential and on preventing SQL injection. RLS protects against missing tenant filters and ordinary application query mistakes; it does not cryptographically authenticate the tenant identity to PostgreSQL. If the threat model includes arbitrary SQL execution or compromise of the runtime DB credential, a signed tenant-context verification mechanism (or a stronger per-tenant DB identity boundary) is a required follow-up before production.

The existing `test_rls_bypass_attack.py` verifies that `app.bypass_rls` cannot disable policies. It does **not** prove that `app.tenant_id` itself cannot be spoofed.

## 6. Verification Status

Migrations 0017 and 0018 and regression tests were added to the repository. Their tests have **not yet been executed** in this session. Do not treat them as passing until run against PostgreSQL 16 using the migration chain from 0001 through 0018.

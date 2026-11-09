# Database Schema — Current State

M369 Support currently defines **25 application tables** (excluding Alembic's `alembic_version`).

## Identity and Platform

- `users` — global user identity; agency membership is represented separately.
- `super_admins` — platform administrator identities.
- `super_admin_audit_logs` — platform administrator audit trail.
- `super_admin_mfa_challenges` — short-lived MFA login challenges.
- `super_admin_mfa_recovery_codes` — hashed, single-use recovery codes.
- `super_admin_used_totp_codes` — TOTP replay protection.
- `platform_settings` — platform-level settings.
- `agency_notes` — platform-private notes associated with agencies.

## Tenant and Workspace

- `agencies` — tenant root.
- `workspaces` — agency-owned workspaces.
- `agency_memberships` — user-to-agency membership and role.
- `teams` — workspace-scoped teams.
- `team_memberships` — team membership, constrained to the same agency.
- `contacts` — customer/contact records, constrained to the same agency as their workspace.
- `conversations` — support conversations, constrained to the same workspace, agency, contact, assignee and team.

## Support Operations

- `messages` — conversation messages and internal notes.
- `message_attachments` — attachments linked to messages and agencies.
- `channels` — agency communication channels.
- `kb_categories` — workspace knowledge-base categories and parent hierarchy.
- `kb_articles` — knowledge-base articles.
- `canned_responses` — reusable support responses.

## Billing and Audit

- `plans` — platform subscription plans.
- `subscriptions` — agency subscription records.
- `payments` — payment records linked to the matching agency subscription.
- `audit_logs` — agency-scoped audit trail.

## Tenant Isolation

- RLS is enabled and forced on 17 tables: 16 tenant-policy tables plus platform-private `agency_notes` with a deny-all policy for roles subject to RLS.
- There are 16 composite foreign keys. The two added by migration 0018 ensure `contacts` and `teams` cannot point to a workspace owned by another agency.
- See [Tenant Isolation](../security/tenant-isolation.md) for the exact policy groups, role boundaries, and the important limitation of a user-settable tenant GUC.

## Database Roles

- `m369_app` — agency runtime; NOSUPERUSER, NOBYPASSRLS, no schema CREATE.
- `m369_sa_auth` — Super Admin login/MFA; NOBYPASSRLS and narrowly scoped table/column grants.
- `m369_sa_runner` — Super Admin management; BYPASSRLS with restricted object grants.
- `m369_login_reader` — NOLOGIN function owner for the membership lookup.
- `m369_registration_guard` — NOLOGIN function owner for the first-agency registration check.
- `m369_super_admin` — neutralized legacy role; NOLOGIN, NOBYPASSRLS and no active grants.

## Migration Chain

The Alembic chain is linear from `0001_initial` through `0018_workspace_agency_fks_contacts_teams`. The latest two migrations:
- `0017_revoke_runtime_schema_create` — removes schema CREATE from runtime roles/PUBLIC.
- `0018_workspace_agency_fks_contacts_teams` — enforces workspace/agency consistency for contacts and teams.

Apply with `alembic upgrade head` from `apps/api/`. The database-applied revision is not confirmed by repository inspection alone.

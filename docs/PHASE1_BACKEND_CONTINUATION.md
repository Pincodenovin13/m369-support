# M369 Support — Phase 1 Backend Continuation

> **Final state after Stages 1-4.** All four stages complete. Branch
> `phase-1/foundation`. See the bottom of this file for the full
> completion summary.

## Mission: 4-Stage Backend Completion

### Stage 1 — Data Model & Database Integrity
**Status:** ✅ COMPLETE
**Commit:** `321ebfc80189f995aba7bf9e86a055eeb103c81c`
**New tables:** 11 (messages, message_attachments, channels, kb_categories, kb_articles, canned_responses, plans, subscriptions, payments, platform_settings, agency_notes)
**Migration:** 0006_phase1_extended
**Plans seeded:** 4 (starter $19, growth $49, pro $79, vip $99)
**RLS:** Enabled + FORCE on all 6 new tenant-owned tables

### Stage 2 — API, Business Logic & RBAC
**Status:** ✅ COMPLETE
**Commit:** `853b557`
**New endpoints:** 27 agency-scoped (contacts, conversations, messages, teams, channels, KB, canned responses, audit logs)
**Pagination:** `PaginatedResponse[T]{items,total,limit,offset}` with max 100/page
**RBAC:** viewer / agent / manager / admin / owner gating via `require_role(...)`
**Audit:** every mutation writes a JSONB metadata row to `audit_logs`
**Fix:** migration 0007 — restored `m369_login_reader` to SELECT-only on agencies + agency_memberships (0006 had over-granted)
**Fix:** SQLAlchemy `after_begin` event listener re-issues `SET LOCAL app.tenant_id` after commit, so `db.refresh()` doesn't fail
**Fix:** Phase 1 extended models now inherit `Base` (6 classes were missing it)
**Fix:** `AuditLog.metadata_` and `SuperAdminAuditLog.metadata_` now use JSONB (matching the migration)
**Tests:** 25 new (cross-tenant IDOR + RBAC + pagination + audit log writes + ACL regression)

### Stage 3 — Super Admin & Agency Backend + Billing
**Status:** ✅ COMPLETE
**Commit:** `70e026f`
**New endpoints:** 26 Super Admin (agencies, plans, subscriptions, payments, platform settings, agency notes, SA audit log)
**Separate engine:** `super_admin_engine` connects as `m369_sa_runner` (LOGIN, BYPASSRLS, NOSUPERUSER) — distinct from `m369_app`, password via `\getenv M369_SA_RUNNER_PASSWORD`
**Subscription lifecycle:** state machine in `services/billing.py` — `trial → active → past_due → suspended → cancelled`. Disallowed transitions return 400.
**Payment verification:** idempotent — re-verifying returns the same row, no double-counting. Terminal states (rejected, expired) cannot be re-verified (409). Raw on-chain amount + decimals + exchange_rate stored separately from base-currency `amount_paid` (INTEGER cents).
**Plan price snapshot:** frozen at subscription creation; later plan price changes do NOT propagate to existing subscriptions.
**Migrations:** 0008 creates `m369_sa_runner` role; 0009 widens `payments.paid_currency` from `String(3)` to `String(10)` so crypto codes like `USDT` are accepted
**Tests:** 31 new (token separation, agency CRUD + suspend/activate idempotency, member role changes, plan CRUD + duplicate detection, subscription lifecycle + invalid transition + price snapshot, payment idempotent verify + terminal state + txid UNIQUE + financial precision, platform settings, agency notes, SA audit log queries, m369_sa_runner role attribute + privilege verification)

### Stage 4 — Integrated Testing & Final Security Audit
**Status:** ✅ COMPLETE
**Commit:** `<fill-after-commit>`
**New tests:** 37 (cross-tenant IDOR across every new resource, JWT boundary tests, payment replay + idempotency + financial precision + USDT 6-decimals, subscription price snapshot immutability + lifecycle + partial unique index, composite FK enforcement at DB layer, RLS audit on all 14 tenant tables, privilege escalation attempts, audit log completeness, endpoint smoke for every route, migration chain completeness + total table count)
**Compose test additions:** 4 new — verify API receives `DATABASE_URL_SUPER_ADMIN`, migration service does NOT, DB service receives `M369_SA_RUNNER_PASSWORD`, SA URL credential is `m369_sa_runner` not `postgres`

## Migration Chain
```
0001_initial → 0002_remove_admin_login → 0003_login_helper →
0004_fix_login_helper_acl → 0005_restrict_login_helper_owner →
0006_phase1_extended → 0007_fix_login_reader_acl →
0008_create_sa_runner_role → 0009_widen_paid_currency
```

## Final State

| Metric | Value |
| --- | --- |
| Total tests passing | **168** |
| Total tables | **23** (22 + alembic_version) |
| Total API endpoints | **~80** (40 agency-scoped + 26 SA + 14 auth/health) |
| Migrations | **9** (0001-0009) |
| Database roles | 4: `postgres`, `m369_app`, `m369_login_reader`, `m369_sa_runner` (plus dormant `m369_super_admin`) |
| RLS policies | 14 (one per tenant-owned table) — none use `bypass_rls` GUC |
| Composite FKs | 4: messages↔conversations, conversations↔contacts, conversations↔team, conversations↔agency_memberships, team_memberships↔teams |

## Test Suite Breakdown

| File | Tests | Purpose |
| --- | --- | --- |
| `tests/unit/test_config.py` | 5 | REPO_ROOT + production guard |
| `tests/unit/test_compose_isolation.py` | 12 | Docker compose credential isolation |
| `tests/unit/test_security_and_utils.py` | 10 | Password hash, JWT round-trip, slugify |
| `tests/integration/test_rls_bypass_attack.py` | 10 | Adversarial RLS bypass regression |
| `tests/integration/test_auth_tenant_context.py` | 24 | Auth: refresh binding, multi-agency login, inactive agency, ACL verification |
| `tests/integration/test_security_tenant_isolation.py` | 15 | Cross-tenant isolation + JWT type separation |
| `tests/integration/test_stage2_api_rbac.py` | 25 | Stage 2 endpoints + RBAC + IDOR + audit |
| `tests/integration/test_stage3_super_admin_billing.py` | 31 | Super Admin + billing lifecycle + payment security |
| `tests/integration/test_stage4_security_audit.py` | 37 | Final integrated security audit |

## Outstanding Items for Phase 2

- **Payment provider integration**: Phase 1 has only the manual Super Admin verify path. Phase 2 should add an adapter interface (`PaymentProvider.verify(txid) → result`) and a webhook endpoint that ingests on-chain confirmations.
- **Markdown rendering**: KB articles store `content_md` but `content_html` is always `""`. Phase 2 should add server-side rendering (with sanitization).
- **Rate limiting**: `slowapi` is in requirements but not wired. Phase 2 should add per-IP and per-agency rate limits on auth + write endpoints.
- **Audit log retention policy**: Phase 1 keeps audit_logs forever (FK RESTRICT blocks agency deletion). Phase 2 should add a retention policy + archiver.
- **Frontend integration**: The Next.js app exists but only has login/register/dashboard. Phase 2 should add screens for conversations, contacts, KB, settings, and Super Admin console.
- **MFA**: `SuperAdmin.mfa_secret_encrypted` + `mfa_enabled` columns exist but the auth flow doesn't enforce TOTP. Phase 2 should add enrollment + verify endpoints.

## Continuation File Location

This file: `docs/PHASE1_BACKEND_CONTINUATION.md`

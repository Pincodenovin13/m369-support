> ⚠️ **ARCHIVED — LEGACY — CONTAINS OPENLIVERY MATERIAL — DO NOT USE AS M369 SOURCE**
>
> This file is a historical artifact from Nov 2, 2026. It contains references
> to OpenLivery, an external product. Per M369 project rules: "Do not use
> OpenLivery as a source, template, or architectural reference. M369 is an
> independent greenfield product."
>
> This file must NEVER be used as an M369 implementation source.
> Preserved for historical audit only.

# M369 SUPPORT — COMPLETE PROJECT HANDOFF DOCUMENT

> **آخرین به‌روزرسانی:** end of Phase 1 session
> **وضعیت فعلی:** Phase 1 COMPLETE — APPROVED WITH CONDITIONS
> **منتظر:** Phase 2 authorization از ChatGPT

---

## 🎯 Project Identity

| فیلد | مقدار |
|---|---|
| **Project Name** | M369 Support |
| **Domain** | m369support.io (آزاد — هنوز نخریده) |
| **Base** | Fork of OpenLivery (github.com/sarrazola/openlivery) |
| **License** | MIT (خالص — OpenLivery contributors) |
| **Stack** | FastAPI (Python 3.12) + Next.js 16 (React 19) + PostgreSQL 17 + Caddy v2 |
| **Brand Color** | #FF6B35 (vivid orange) |
| **Tagline** | "AI-powered customer support for every business" |
| **Baseline Commit** | `92fe562b8fdb4dce41c06d9abcf53bdfa49931b3` |
| **Phase 1 Branch** | `m369-phase1-schema` |
| **Phase 1 HEAD** | `dd2bf59f70ab115444144c2e60031d178f913304` |

---

## 👥 Team Roles

| نقش | چه کسی | وظیفه |
|---|---|---|
| **Product Owner** | مجتبی (Mojtaba) | تصمیم نهایی، تأیید انتشار، deploy روی VPS |
| **Technical Manager** | ChatGPT | معماری، scope، معیار پذیرش، audit، پرامپت‌نویسی |
| **Senior Engineer + Code Architect** | Z.ai (من) | تحلیل، طراحی، کد، تست، ممیزی مستقل |
| **Executor** | Gemini | اعمال کد در مخزن، commit، push، اجرای تست |

### قوانین مهم:
- **Z.ai نباید نقش مدیر محصول یا معمار نهایی را از ChatGPT بگیرد**
- **Z.ai فقط طبق scope که ChatGPT تعیین می‌کند کار می‌کند**
- **بدون تأیید ChatGPT، مرحله بعد شروع نمی‌شود**
- **Gemini مسئول commit/push است — Z.ai نباید ادعا کند کد اعمال شده بدون شواهد**

---

## 📜 14 Non-Negotiable Rules

1. قبل از تولید کد، ساختار واقعی فایل‌ها، مدل‌ها، APIها، سرویس‌ها را بررسی کن
2. هیچ فایل، کلاس، تابع، جدول یا API را بدون بررسی وجود واقعی فرض نکن
3. از بازنویسی کامل پروژه خودداری کن — فقط محدوده مشخص‌شده را تغییر بده
4. تغییرات باید با معماری فعلی پروژه سازگار باشند
5. Tenant Isolation، کنترل دسترسی، اعتبارسنجی ورودی در اولویت هستند
6. صرف وجود `agency_id` یا `client_id` به معنی جداسازی امن داده‌ها نیست
7. تستی که واقعاً اجرا نشده PASS اعلام نکن
8. Static inspection را با Runtime test اشتباه نگیر
9. تغییرات Database باید با Migration سازگار و قابل بازگشت باشند
10. تغییرات نباید قابلیت‌های فعلی پروژه را حذف یا خراب کنند
11. برای هر تغییر، مسیر دقیق فایل و کد کامل یا Patch ارائه کن
12. برای هر تغییر، تست‌های متناسب طراحی کن
13. هیچ Secret، Token، Password یا کلید خصوصی در کد یا گزارش قرار نده
14. اگر اطلاعات کافی نداری، حدس نزن — سؤال بپرس یا BLOCKER اعلام کن

---

## 📦 Delivery Template (هر مرحله باید شامل A-H باشد)

- **A.** تحلیل ساختار فعلی و فایل‌های مرتبط (مسیر + شماره خطوط)
- **B.** مشکلات موجود و علت فنی آن‌ها
- **C.** معماری و راهکار پیشنهادی (ارتباط با اجزای موجود)
- **D.** کد کامل یا Patch دقیق
- **E.** Migration و تست‌های لازم
- **F.** دستورالعمل اجرای دقیق برای Gemini
- **G.** معیار پذیرش و تست‌هایی که باید واقعاً اجرا شوند
- **H.** فهرست خطرات، محدودیت‌ها و موارد حل‌نشده

---

## 💰 Pricing Plans (Owner-Approved)

### فقط ماهانه (حذف ۳ماهه/سالانه):

| Plan | Price/Month | Max Seats | Conversations/Mo | AI Cost/Mo | Channels |
|---|---|---|---|---|---|
| **Starter** | $19 | 3 | 500 | $5 | Web Widget |
| **Growth** | $49 | 6 | 2,000 | $15 | + WhatsApp Cloud |
| **Pro** | $79 | 9 | 6,000 | $30 | + Email, Telegram, Custom Domain |
| **VIP** | $99 | 12 | 15,000 | $50 | + Instagram, Messenger, Whitelabel |

### Seat Model (Option A — Owner-Approved):
- ✅ فقط `User` (هر role، فعال یا غیرفعال) = Seat
- ✅ Owner جزو Seat
- ❌ `PortalUser` (هر role) = **NOT** a Seat
- ❌ `Contact` = NOT a Seat
- ❌ Unaccepted invitations = NOT counted

### Payment:
- USDT TRC-20 (Tron) + USDT BEP-20 (BSC)
- TXID UNIQUE در DB
- تأیید دستی Super Admin با TronGrid/BscScan API verification
- 7 روز trial رایگان

---

## 🌍 Languages

| زبان | کد | جهت |
|---|---|---|
| English (پیش‌فرض) | en | LTR |
| Persian (فارسی) | fa | RTL |
| Arabic (عربی) | ar | RTL |
| Turkish (Türkçe) | tr | LTR |
| Russian (Русский) | ru | LTR |

---

## 🏗️ Architecture — Three Surfaces

```
1. Super Admin Dashboard (مالک M369)
   URL: m369support.io/admin/*
   کاربر: مجتبی (با 2FA)
   وضعیت: ❌ باید ساخته بشه (Phase 2+)

2. Tenant Portal (صاحب فروشگاه + اپراتورها)
   URL: m369support.io/portal/[slug]
   کاربران: Tenant Admin + Operator (PortalUser)
   وضعیت: ✅ آماده در OpenLivery (ولی billing ناقص)

3. Web Widget (چت کارسر نهایی)
   URL: embed تو سایت مشتری
   کاربر: مشتری فروشگاه (بدون login)
   وضعیت: ✅ آماده در OpenLivery
```

### Multi-Tenant Model:
- `Agency` = Tenant ریشه (هر کسب‌وکار = یک Agency)
- `Client` = Workspace (هر Agency حداقل ۱ Client دارد)
- `User` = مدیر Tenant (role=admin)
- `PortalUser` = اپراتور (role=admin یا agent)
- `SuperAdmin` = مالک M369 (جدول مستقل — از هم جدا)
- `Contact` = مشتری نهایی (Tenant نیست)

---

## 📊 What OpenLivery Already Has (آماده)

| Feature | Status |
|---|---|
| WhatsApp Cloud API | ✅ آماده |
| Web Widget | ✅ آماده |
| Inbox unified | ✅ آماده |
| OpenRouter AI | ✅ آماده |
| Knowledge Base (PDF) | ✅ آماده |
| Custom domain + SSL | ✅ آماده |
| Reports (cost, usage) | ✅ آماده |
| Human Handoff | ✅ آماده |
| Mobile app | ✅ آماده |
| Portal (Client) | ✅ آماده |

## ❌ What We Need to Build

| # | Feature | Phase |
|---|---|---|
| 1 | Super Admin + MFA + CLI | 2 |
| 2 | Public registration (break single-agency lock) | 3 |
| 3 | Subscription lifecycle + Quota Guard | 5 |
| 4 | Crypto payment (USDT TRC20 + BEP20) | 6 |
| 5 | Multi-language (fa/ar/tr/ru + RTL) | 10 |
| 6 | Email channel | 11 |
| 7 | Telegram | 11 |
| 8 | Instagram DM | 12 |
| 9 | CSAT | 13 |
| 10 | 2FA Super Admin | 14 |
| 11 | Audit logs + Rate limiting | 14 |
| 12 | Backup strategy | 15 |

---

## 📋 Phase Progress

### ✅ Phase 0.A — Local Sandbox Setup (COMPLETE)
- OpenLivery cloned
- Branch `m369-support-initial` created
- STATE.md created
- Inventory: 40 tables, 24 routers, 52 services, 58 migrations

### ✅ Phase 0.B — Architecture Discovery (COMPLETE)
- HEAD confirmed: `92fe562b8fdb4dce41c06d9abcf53bdfa49931b3`
- Migration chain: linear, 58 files, HEAD = `0059_phone_calls`
- 8 dual-ownership tables (agency_id + client_id)
- 5 agency-only tables
- 9 client-only tables
- 18 indirect ownership tables
- Webhooks: HMAC-SHA256 + per-channel secret ✅
- Attachments: API-level authorization confirmed ✅
- Background workers: 3 safe, 1 needs `with_for_update` (reconcile_calls)

### ✅ Phase 0.C — Database Forensics (COMPLETE — APPROVED)
**Key Decisions:**
- Seat Model: Option A (User only) ✅ Owner-approved
- Plan names: Starter, Growth, Pro, VIP ✅ Owner-approved
- Subscription/Payment: Independent lifecycles ✅
- Super Admin: 3-layer singleton (advisory lock + DB singleton + password policy)
- JWT: Separate signing keys (super_admin_secret_key)
- MFA: Per-route enforcement (not middleware)
- Migration 0063 (email UNIQUE removal): BLOCKED pending Owner approval
- Migration 0065/0066 (composite FK): Optional defense-in-depth

**Confirmed Vulnerabilities:**
1. Mobile login ambiguity (Class B — Weakness, NOT exploitable)
2. users.email global unique (Class B)
3. reconcile_calls no row lock (Class B)
4. Follow-up crash-after-send (Class B)
5. decode_access_token no type check (Class B — documented only)

### ✅ Phase 1 — Schema Migrations (COMPLETE — APPROVED WITH CONDITIONS)

**3 additive migrations created:**

#### Migration 0060_super_admins (127 lines)
- `super_admins` table: email, password_hash, mfa_secret_encrypted (Fernet), mfa_enabled, is_initial (partial unique singleton), failed_mfa_attempts, locked_until (temporary only — NO permanent lockout)
- `super_admin_backup_codes` table: bcrypt code_hash + code_prefix (4 chars) for lookup, used_at (single-use)
- `super_admin_audit_logs` table: admin_id (FK SET NULL), action, target_type, target_id, metadata (JSON), ip_address
- `down_revision = "0059_phone_calls"`

#### Migration 0061_billing_tables (260 lines)
- `plans` table: 4 seeded (Starter $19, Growth $49, Pro $79, VIP $99); `max_seats` (NOT max_operators); 6 feature flags
- `subscriptions` table: status (trial/active/past_due/suspended/cancelled/superseded); partial unique `uq_subscriptions_agency_active WHERE status IN ('trial','active','past_due','suspended')`
- `crypto_payments` table: txid UNIQUE; CHECK constraint (TRC20 64hex / BEP20 0x+64hex); `verifying_lease_until`; NUMERIC(18,6) amounts; status (pending/verifying/verified/rejected/expired)
- `operator_invitations` table: client-scoped, does NOT affect seat count
- `down_revision = "0060_super_admins"`

#### Migration 0062_platform_audit_log (63 lines)
- `audit_logs` table: SEPARATE from `super_admin_audit_logs`; agency_id+user_id nullable; action, target_type, target_id, metadata, ip_address, user_agent
- `down_revision = "0061_billing_tables"`

**Tests:**
- 96 unit tests EXECUTED — ALL PASS
- PostgreSQL integration tests: BLOCKED (no PG server in Z.ai sandbox)
- No test falsely marked as PASS

**Git State:**
- Branch: `m369-phase1-schema`
- HEAD: `dd2bf59f70ab115444144c2e60031d178f913304`
- Working tree: CLEAN
- NOT pushed (not authorized)
- 0 existing files modified (git diff confirmed)

---

## 📋 Phase 1 Final Verdict

```
APPROVED WITH CONDITIONS
```

### 5 Conditions:
1. Owner confirms $19/$49/$79/$99 pricing (or approves change)
2. Owner clarifies: are Agency-scoped User invitations needed beyond PortalUser invitations?
3. PostgreSQL integration tests must be executed before production deployment
4. JWT type-check weakness (security.py:25-29) must be fixed in Phase 2
5. No push to production without Owner approval

---

## 🗺️ Phase Roadmap

| Phase | Scope | Status |
|---|---|---|
| 0.A | Sandbox setup | ✅ COMPLETE |
| 0.B | Architecture discovery | ✅ COMPLETE |
| 0.C | Database forensics | ✅ COMPLETE (APPROVED) |
| 1 | Schema migrations 0060-0062 | ✅ COMPLETE (APPROVED WITH CONDITIONS) |
| 2 | Auth hardening + Super Admin + CLI | ⏳ WAITING AUTHORIZATION |
| 3 | Multi-tenant registration (break single-agency lock) | 🔜 |
| 4 | Super Admin features + MFA | 🔜 |
| 5 | Subscription lifecycle + Quota Guard | 🔜 |
| 6 | Crypto payment (TronGrid + BscScan verification) | 🔜 |
| 7 | Composite FK backfill (optional) | 🔜 |
| 8 | Super Admin frontend | 🔜 |
| 9 | Tenant billing UI + Pricing page | 🔜 |
| 10 | i18n (fa/ar/tr/ru + RTL) | 🔜 |
| 11 | Email + Telegram channels | 🔜 |
| 12 | Instagram DM + Facebook Messenger | 🔜 |
| 13 | CSAT | 🔜 |
| 14 | Security hardening (2FA, rate limit, audit) | 🔜 |
| 15 | Backup + Deploy | 🔜 |

---

## 📊 Key Technical Findings (from Phase 0.C)

### Migration Chain (linear, verified):
```
0001_initial (ROOT)
  ↓
... (57 migrations)
  ↓
0059_phone_calls (existing HEAD)
  ↓
0060_super_admins (NEW — Phase 1)
  ↓
0061_billing_tables (NEW — Phase 1)
  ↓
0062_platform_audit_log (NEW — Phase 1, current HEAD)
```

### Database Tables (40 existing + 8 new = 48 total after Phase 1):
- 40 existing tables (unchanged)
- 8 new tables (Phase 1):
  - super_admins, super_admin_backup_codes, super_admin_audit_logs
  - plans, subscriptions, crypto_payments, operator_invitations
  - audit_logs

### Security Findings (documented, NOT fixed in Phase 1):
1. `decode_access_token` (security.py:25-29) has NO type check → portal token can be decoded as agency (but db.get(User, client_uuid) → None → 401, so NOT exploitable currently)
2. Mobile login (mobile.py:137-156) — Account Ambiguity (Class B weakness, NOT exploitable)
3. `users.email` global unique — multi-tenant issue (0063 BLOCKED pending Owner approval)
4. `reconcile_calls` (phone_calls.py:36-42) — missing `with_for_update`

---

## 💡 Key Design Decisions

### Super Admin Security:
- **Singleton enforcement:** BOTH `pg_advisory_xact_lock` AND DB partial unique index (`is_initial=true`)
- **JWT separation:** Separate `super_admin_secret_key` (NOT shared with agency)
- **MFA:** TOTP secret Fernet-encrypted; per-route enforcement (not middleware)
- **Lockout:** Temporary cooldown only (5 failed → 15min); NO automatic permanent lockout
- **Recovery:** CLI script + offline backup codes (10 codes, bcrypt-hashed, single-use)

### Subscription Lifecycle:
- States: `trial | active | past_due | suspended | cancelled | superserseded`
- Partial unique index: one active subscription per agency
- Subscription and Payment states are INDEPENDENT
- Renewal preserves remaining days (atomic: old→superseded, new→active)

### Crypto Payment:
- 5-layer verification: regex → DB UNIQUE → TronGrid/BscScan API → manual Super Admin → atomic transaction
- TXID UNIQUE across whole table (no replay)
- `verifying_lease_until` for stuck payments (scheduler recovery)
- Amounts: NUMERIC(18,6) — sufficient for USDT (TRC20=6 decimals, BEP20=18 decimals but 6 stored is enough for $19-$99)

---

## 🚦 Current State (end of this session)

```
Phase: 1 COMPLETE — APPROVED WITH CONDITIONS
Next: WAITING for ChatGPT's Phase 2 authorization prompt

Z.ai is READY to:
1. Receive Phase 2 scope from ChatGPT
2. Implement Phase 2 (auth hardening + Super Admin + CLI)
3. Run unit tests and report raw output
4. Wait for ChatGPT approval before Phase 3

Z.ai will NOT:
- Start Phase 2 without ChatGPT's explicit authorization
- Modify existing authentication/security code without separate approval
- Push to any remote
- Mark unexecuted tests as PASS
- Make product decisions on behalf of Owner
```

---

## ⚠️ Important Notes for New Session

1. **Z.ai sandbox بین session‌ها reset می‌شه** — باید OpenLivery رو دوباره clone کنه
2. **Gemini's local branch (`m369-support-initial`) در sandbox من قابل دسترسی نیست** — من فقط upstream رو می‌تونم clone کنم
3. **Phase 1 migrations در `/home/z/m369-phase1/` ذخیره شده‌اند** (نه در sandbox که reset می‌شه) — ولی این هم ممکنه بین session‌ها پاک بشه
4. **اگه sandbox پاک شد، Z.ai باید:**
   - OpenLivery رو از upstream clone کنه
   - Phase 1 migrations رو از روی commit `dd2bf59f` بازیابی کنه (اگه push شده باشه)
   - یا migrations رو دوباره بسازه (کد در این سند هست)

---

## 🎯 Quick Reference

| Item | Value |
|---|---|
| Baseline | `92fe562b8fdb4dce41c06d9abcf53bdfa49931b3` |
| Phase 1 Branch | `m369-phase1-schema` |
| Phase 1 HEAD | `dd2bf59f70ab115444144c2e60031d178f913304` |
| Migration Chain | 0059 → 0060 → 0061 → 0062 |
| Tests Executed | 96 unit tests PASS |
| Tests Blocked | All PostgreSQL integration tests |
| Files Modified | 0 existing files |
| Files Created | 3 new migration files |
| Push Status | NOT pushed |

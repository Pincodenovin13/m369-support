> ⚠️ **ARCHIVED — HISTORICAL — NOT AUTHORITATIVE**
>
> This file is a historical artifact from Nov 4, 2026. It is preserved for
> reference only and is NOT the current source of truth. For current
> architecture, see `/ARCHITECTURE.md` (when created) or `/STATE.md`.
>
> This document may contain outdated architecture or superseded designs.
> Do NOT use it as an implementation reference.

# M369 Support — معماری و طرح‌ریزی محصول (Greenfield)

**سند:** معماری مرجع نسخه MVP
**تاریخ:** 2026-11-04
**تصمیم:** ساخت محصول مستقل SaaS چندمستاجری از صفر (نه fork از OpenLivery)
**مسیر پروژه جدید:** `/home/z/my-project/m369-support/`
**وضعیت:** پیش‌نویس معماری — منتظر تأیید Owner پیش از شروع پیاده‌سازی

---

## ۰. خلاصه اجرایی

M369 Support یک پلتفرم SaaS چندمستاجری برای پشتیبانی مشتری است که از صفر ساخته می‌شود. این محصول الهام گرفته از قابلیت‌های عمومی پنج محصول مرجع (Intercom، Zendesk، Freshdesk Omni، Crisp، Help Scout) است، اما هیچ کد، برند، طراحی یا متنی از آن‌ها کپی نمی‌شود. معمار اصلی، چندمستاجری کامل در تمام لایه‌هاست (Database + API + Auth + File Storage + Background Jobs + Search + Reports + Webhooks + Notifications).

---

## ۱. جدول مقایسه قابلیت‌های پنج محصول مرجع

این مقایسه بر اساس صفحات رسمی محصولات و منابع عمومی (WebSearch در 2026-11-04) تهیه شده است. فقط قابلیت‌های عمومی و الگوهای معماری استخراج شده‌اند.

| قابلیت | Intercom | Zendesk | Freshdesk Omni | Crisp | Help Scout |
|---|---|---|---|---|---|
| **صندوق ورودی یکپارچه (Unified Inbox)** | ✅ قوی (Inbox + Fin AI) | ✅ قوی (Agent Workspace) | ✅ (Omniroute) | ✅ (Multichannel inbox) | ✅ قوی (Shared Inbox) |
| **چت آنلاین (Live Chat Widget)** | ✅ (Messenger) | ✅ (Messaging) | ✅ | ✅ (اصلی تخصص) | ✅ (Beacon) |
| **ایمیل کانال** | ✅ | ✅ | ✅ | ✅ | ✅ (اصلی تخصص) |
| **پیام‌رسان‌ها (WhatsApp/Messenger/Instagram)** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **تماس تلفنی (Voice)** | ⚠️ محدود | ✅ (Talk) | ✅ (Phone) | ❌ | ⚠️ (توسط integration) |
| **تیکتینگ (Ticketing)** | ✅ | ✅ قوی (اصلی تخصص) | ✅ | ⚠️ محدود | ✅ |
| **پایگاه دانش (KB)** | ✅ (Help Center + Knowledge Hub) | ✅ (Guide) | ✅ | ✅ | ✅ (Docs) |
| **پرتال مشتری (Customer Portal)** | ✅ | ✅ | ✅ | ⚠️ | ✅ |
| **اتوماسیون (Workflow/Rules)** | ✅ (Workflows + Series) | ✅ (Triggers + Macros) | ✅ | ✅ (Chatbot builder) | ⚠️ محدود |
| **SLA Management** | ⚠️ محدود | ✅ قوی (اصلی تخصص) | ✅ | ❌ | ⚠️ |
| **تخصیص و ارجاع (Assignment)** | ✅ (Inbox routing) | ✅ (Skills-based routing) | ✅ (Omniroute) | ✅ | ✅ |
| **یادداشت داخلی (Internal Notes)** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **پاسخ خصوصی (Private Reply)** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **گزارش‌گیری (Reports)** | ✅ | ✅ قوی (Explore) | ✅ (Analytics) | ✅ | ✅ |
| **AI Agent / Copilot** | ✅ قوی (Fin AI — 76% resolution) | ✅ (Advanced AI) | ✅ (Freddy AI) | ⚠️ محدود | ⚠️ محدود |
| **هوش مصنوعی پیشنهاد پاسخ** | ✅ (Copilot 2) | ✅ | ✅ | ✅ | ⚠️ |
| **چند برند / چند آژانس (Multi-brand)** | ⚠️ محدود | ✅ (تا ۵ help center در Professional) | ✅ | ❌ | ⚠️ |
| **مدیریت تیم‌ها و نقش‌ها** | ✅ | ✅ قوی (Custom roles) | ✅ | ✅ | ✅ |
| **CRM / مدیریت مشتری** | ✅ | ✅ ( Sunshine/Sell ) | ✅ | ✅ | ✅ (Customers) |
| **Co-browsing / Video Chat** | ❌ | ⚠️ (via integration) | ❌ | ✅ | ❌ |
| **Campaigns / Outbound** | ✅ (Outbound) | ✅ | ✅ | ✅ (Email campaigns) | ❌ |
| **App Marketplace / Integrations** | ✅ | ✅ قوی (1800+) | ✅ | ✅ | ✅ |
| **مدل قیمت‌گذاری** | $29/seat/mo | $19/agent/mo | $15/agent/mo | متغیر | $25/user/mo |

### الگوهای معماری استخراج‌شده

از بررسی پنج محصول، این الگوهای معماری مشترک استخراج می‌شوند:

۱. **Unified Inbox** — تمام محصولات مشتریان را به یک نقطه مرکزی می‌آورند.
۲. **Conversation-centric** — تیکت فقط یک view از conversation است.
۳. **Multi-channel abstraction** — کانال‌های مختلف (ایمیل، چت، پیام‌رسان) به‌صورت یکنواخت مدیریت می‌شوند.
۴. **Role-based access** — مدیر، سرپرست، کارشناس، مشاهده‌کننده.
۵. **Assignment & Routing** — قوانین تخصیص خودکار مکالمات به کارشناسان یا تیم‌ها.
۶. **Knowledge Base** — پایگاه دانش با قابلیت جستجو و self-service.
۷. **Automation Rules** — قوانین "اگر X آنگاه Y".
۸. **AI Assistant** — Copilot برای پیشنهاد پاسخ، خلاصه‌سازی، دسته‌بندی.
۹. **Reporting & Analytics** — داشبورد عملکرد، SLA، رضایت مشتری (CSAT).
۱۰. **Customer 360** — پروفایل یکپارچه مشتری با تاریخچه مکالمات.

### قابلیت‌هایی که کپی نخواهند شد

- **هیچ کد یا تصویر اختصاصی** از هیچ‌یک از پنج محصول کپی نمی‌شود.
- **برند، رنگ، نام و آیکون‌ها** کاملاً متمایز برای M369 طراحی می‌شوند.
- **API contract** و **schema دیتابیس** از ابتدا برای M369 طراحی می‌شوند.

---

## ۲. فهرست قابلیت‌های ضروری نسخه MVP

این قابلیت‌ها در MVP (فازهای ۱-۵) باید کامل و قابل تست باشند:

### ۲.۱ Foundation و Multi-Tenancy (MVP)

- ✅ پلتفرم چندمستاجری با جداسازی کامل داده‌ها در همه لایه‌ها
- ✅ Super Admin مستقل مالک پلتفرم
- ✅ ثبت‌نام آژانس‌های مستقل (Agency = Tenant)
- ✅ Workspace/Client درون هر آژانس
- ✅ احراز هویت مبتنی بر JWT با امضای جداگانه برای Super Admin و Agency
- ✅ نقش‌ها: SuperAdmin، AgencyAdmin، Manager، Agent، Viewer
- ✅ کنترل دسترسی مبتنی بر نقش (RBAC) در سطح API و Database
- ✅ Rate Limiting روی endpoints عمومی و احراز هویت
- ✅ Audit Log برای تمام عملیات حساس

### ۲.۲ مدیریت کاربران و تیم‌ها (MVP)

- ✅ CRUD کاربران آژانس (دعوت‌نامه، نقش، فعال/غیرفعال)
- ✅ CRUD تیم‌ها (نام، اعضا، ساعات کاری)
- ✅ پروفایل کاربر (نام، آواتار، تنظیمات اطلاع‌رسانی)
- ✅ Reset password و找回 password
- ✅ ۲FA اختیاری برای AgencyAdmin (Totp)

### ۲.۳ صندوق ورودی و مکالمات (MVP)

- ✅ Unified Inbox با فیلتر بر اساس کانال، وضعیت، تخصیص
- ✅ CRUD مکالمات (Conversation)
- ✅ CRUD پیام‌ها (Message) در مکالمات
- ✅ یادداشت داخلی (Internal Notes)
- ✅ تخصیص مکالمه به کارشناس یا تیم
- ✅ تغییر وضعیت مکالمه (open, pending, resolved, closed)
- ✅ برچسب‌گذاری (Tags) روی مکالمات
- ✅ پیوست فایل (Attachments)

### ۲.۴ کانال‌ها (MVP)

- ✅ **Web Widget** (چت آنلاین قابل embed در سایت مشتری)
- ✅ **ایمیل** (IMAP polling یا webhook از سرویس ایمیل)
- ✅ API webhooks برای دریافت پیام از کانال‌های خارجی

### ۲.۵ مدیریت مخاطبین (MVP)

- ✅ CRUD مخاطبین (Contact)
- ✅ پروفایل مشتری با تاریخچه مکالمات
- ✅ فیلدهای سفارشی (Custom Fields)
- ✅ جستجو و فیلتر

### ۲.۶ پایگاه دانش (MVP)

- ✅ CRUD مقالات (KB Article)
- ✅ دسته‌بندی مقالات (Categories)
- ✅ جستجو در مقالات
- ✅ پرتال مشتری برای self-service

### ۲.۷ اتوماسیون پایه (MVP)

- ✅ قوانین ساده "اگر X آنگاه Y" (Auto-assignment, Auto-tag, Auto-close)
- ✅ SLA پایه (response time, resolution time)
- ✅ Canned responses (پاسخ‌های آماده)

### ۲.۸ گزارش‌گیری (MVP)

- ✅ داشبورد عملکرد کلی
- ✅ گزارش مکالمات (تعداد، زمان پاسخ، رضایت)
- ✅ گزارش کارشناسان (volume، resolution time)
- ✅ خروجی CSV

### ۲.۹ پرتال مشتری (MVP)

- ✅ صفحه ورودی مشتری
- ✅ جستجو در پایگاه دانش
- ✅ شروع مکالمه جدید با پشتیبانی

---

## ۳. قابلیت‌هایی که به فازهای بعدی منتقل می‌شوند

### فاز ۶+ (پس از MVP):

- ⏳ **کانال پیام‌رسان** (WhatsApp Cloud API، Telegram، Facebook Messenger، Instagram DM)
- ⏳ **تماس تلفنی** (Voice channel با Twilio یا سرویس مشابه)
- ⏳ **AI Assistant پیشرفته** (Copilot با LLM، پیشنهاد پاسخ هوشمند، خلاصه‌سازی)
- ⏳ **Co-browsing** (اشتراک صفحه با مشتری)
- ⏳ **CSAT** (رضایت‌سنجی مشتری پس از تعامل)
- ⏳ **Custom Domain** برای پرتال آژانس‌ها
- ⏳ **White-label** (سفارشی‌سازی برند برای آژانس‌های VIP)
- ⏳ **Subscription و Billing** (پلن‌های پولی، پرداخت USDT)
- ⏳ **Quota Guard** (محدودیت تعداد کاربر، مکالمه، AI cost بر اساس پلن)
- ⏳ **Advanced Automation** (Workflow Builder بصری، SLA پیچیده)
- ⏳ **Integrations Marketplace** (Slack، Teams، CRM ها)
- ⏳ **i18n** چندزبانه (fa، en، ar، tr، ru + RTL)
- ⏳ **Mobile App** (iOS و Android)
- ⏳ **Push Notifications** (موبایل و وب)
- ⏳ **Audit Log Advanced** (جستجو، فیلتر، export)
- ⏳ **Backup Strategy** (Snapshot خودکار، Disaster Recovery)
- ⏳ **Search Unified** (Elasticsearch یا Meilisearch برای جستجوی کامل)

---

## ۴. معماری پیشنهادی بک‌اند و فرانت‌اند

### ۴.۱ بک‌اند (Backend)

**فناوری اصلی:**
- **Python 3.12** (زبان اصلی)
- **FastAPI 0.116.x** (Web framework)
- **SQLAlchemy 2.0.x** (ORM)
- **Alembic 1.16.x** (Migration)
- **Pydantic 2.10.x** (Validation)
- **psycopg 3.2.x** (PostgreSQL driver، binary)
- **PyJWT 2.10.x** (JWT)
- **bcrypt 4.2.x** (Password hashing)
- **uvicorn 0.32.x** (ASGI server)
- **httpx 0.28.x** (HTTP client)

**ساختار لایه‌ای (Layered Architecture):**

```
┌──────────────────────────────────────────────────────────┐
│  API Layer (FastAPI routers)                             │
│  - /api/v1/auth/*                                        │
│  - /api/v1/agencies/*                                    │
│  - /api/v1/workspaces/*                                  │
│  - /api/v1/conversations/*                               │
│  - /api/v1/contacts/*                                    │
│  - /api/v1/kb/*                                          │
│  - /api/v1/reports/*                                     │
│  - /api/v1/super-admin/* (separate auth)                 │
│  - /api/v1/widget/* (public, for embedding)             │
│  - /webhooks/* (channel callbacks, signed)              │
└──────────────────────────────────────────────────────────┘
                         ↓
┌──────────────────────────────────────────────────────────┐
│  Service Layer (Business Logic)                         │
│  - auth_service, user_service, agency_service             │
│  - conversation_service, message_service                  │
│  - contact_service, kb_service                            │
│  - automation_service, sla_service                        │
│  - report_service, audit_service                          │
│  - tenant_context (resolved per-request)                  │
└──────────────────────────────────────────────────────────┘
                         ↓
┌──────────────────────────────────────────────────────────┐
│  Repository Layer (SQLAlchemy models + queries)         │
│  - All queries enforce tenant_id filter automatically    │
└──────────────────────────────────────────────────────────┘
                         ↓
┌──────────────────────────────────────────────────────────┐
│  Database (PostgreSQL 16)                                │
│  - Row-Level Security (RLS) policies                     │
│  - Per-table tenant_id column with index                  │
│  - Foreign keys with ON DELETE RESTRICT for audit data   │
└──────────────────────────────────────────────────────────┘
```

**پیکربندی کلیدی:**
- **Async-ready** — FastAPI با async/await، SQLAlchemy 2.0 async support
- **Versioned API** — `/api/v1/...` برای backward compatibility
- **Health check** — `/health` و `/health/ready`
- **OpenAPI auto-docs** — `/docs` و `/redoc` (در production غیرفعال)
- **CORS strict** — فقط origins مجاز در settings
- **Rate limiting** — slowapi یا fastapi-limiter روی endpoints حساس

### ۴.۲ فرانت‌اند (Frontend)

**فناوری اصلی:**
- **Next.js 15.x** (App Router، React Server Components)
- **React 19.x** (UI library)
- **TypeScript 5.x** (type safety)
- **Tailwind CSS 4.x** (utility-first CSS)
- **Zod 3.x** (runtime schema validation)
- **TanStack Query 5.x** (data fetching و caching)
- **shadcn/ui** (component library، headless، customizable)

**سه Surface مستقل:**

```
1. Super Admin Dashboard (مالک M369)
   URL: m369support.io/admin/*
   Auth: Separate JWT (super_admin_secret_key)
   Features: Tenant management, billing, audit, system reports

2. Agency Portal (صاحب کسب‌وکار + اپراتورها)
   URL: m369support.io/portal/*
   Auth: Agency JWT
   Features: Inbox, conversations, contacts, KB, reports, settings

3. Customer Widget (Embed در سایت مشتری)
   URL: m369support.io/widget/* (iframe از سایت آژانس)
   Auth: Anonymous (session-based) یا Contact token
   Features: Live chat, KB search, contact form

4. Customer Portal (Self-service)
   URL: m369support.io/c/[agency-slug]/*
   Auth: Optional (anonymous یا Contact login)
   Features: KB search, submit ticket, track conversation
```

**ساختار فرانت‌اند:**
- **Monorepo** با pnpm workspaces
- **App Router** برای routing با Server Components
- **Server Actions** برای mutations (حداقل در MVP)
- **API client** مبتنی بر fetch + TanStack Query
- **i18n-ready** (در فاز ۱۰ فعال می‌شود)
- **Mobile-first responsive** طراحی

### ۴.۳ زیرساخت و DevOps

- **Docker Compose** برای local development (api، db، redis، mailhog)
- **Alembic** migrations در startup
- **Health checks** برای monitoring
- **Structured logging** (JSON logs)
- **Environment variables** برای تمام secrets

---

## ۵. طراحی اولیه دیتابیس و روابط اصلی

### ۵.۱ Tenant Resolution Strategy

هر درخواست به یک tenant تعلق دارد. Tenant به دو شکل resolve می‌شود:

۱. **Agency JWT** — در payload توکن، `agency_id` ذخیره می‌شود
۲. **Public Widget Token** — برای endpoints عمومی، `agency_id` از `widget_id` یا `domain` resolve می‌شود

### ۵.۲ نمودار ERD (Entity Relationship Diagram) — High-Level

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   super_admins   │     │     agencies     │     │    workspaces    │
│   (singleton)    │────→│   (tenant root)  │────→│   (client)       │
└──────────────────┘     └────────┬─────────┘     └────────┬─────────┘
                                  │                         │
                                  │ 1:N                     │ 1:N
                                  ▼                         ▼
                         ┌──────────────────┐     ┌──────────────────┐
                         │      users       │     │    contacts      │
                         │  (agency users)  │     │   (customers)    │
                         └────────┬─────────┘     └────────┬─────────┘
                                  │                         │
                                  │ 1:N                     │ 1:N
                                  ▼                         ▼
                         ┌──────────────────┐     ┌──────────────────┐
                         │      teams       │     │  conversations   │
                         │   (agency team)  │     │  (contact thread)│
                         └────────┬─────────┘     └────────┬─────────┘
                                  │                         │
                                  │ N:M                     │ 1:N
                                  ▼                         ▼
                         ┌──────────────────┐     ┌──────────────────┐
                         │   team_members   │     │     messages     │
                         └──────────────────┘     └──────────────────┘

┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  kb_categories   │────→│   kb_articles    │     │     tags         │
│  (workspace)     │     │   (workspace)    │     │   (workspace)    │
└──────────────────┘     └──────────────────┘     └──────────────────┘

┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  audit_logs      │     │  automation_rules│     │    sla_policies  │
│  (agency-scoped) │     │  (workspace)     │     │   (workspace)    │
└──────────────────┘     └──────────────────┘     └──────────────────┘

┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   channels       │     │     roles        │     │  audit_logs      │
│  (workspace)     │     │  (system enum)   │     │  (super_admin)   │
└──────────────────┘     └──────────────────┘     └──────────────────┘
```

### ۵.۳ جداول اصلی (Core Tables) — MVP

#### جدول‌های Tenant Management

```sql
-- Super Admin (مالک پلتفرم، singleton enforced)
super_admins (
  id UUID PK,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  mfa_secret_encrypted TEXT,        -- Fernet encrypted
  mfa_enabled BOOLEAN DEFAULT FALSE,
  is_initial BOOLEAN,               -- partial unique: WHERE is_initial = TRUE
  failed_mfa_attempts INT DEFAULT 0,
  locked_until TIMESTAMPTZ,        -- temporary cooldown only
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)

-- Agency (Tenant ریشه)
agencies (
  id UUID PK,
  name TEXT NOT NULL,
  slug TEXT UNIQUE NOT NULL,
  brand_color TEXT DEFAULT '#FF6B35',
  logo_data BYTEA,
  logo_mime TEXT,
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)

-- Workspace / Client (sub-organization within agency)
workspaces (
  id UUID PK,
  agency_id UUID NOT NULL REFERENCES agencies(id) ON DELETE RESTRICT,
  name TEXT NOT NULL,
  slug TEXT NOT NULL,
  timezone TEXT DEFAULT 'UTC',
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(agency_id, slug)
)
```

#### جدول‌های Users و Teams

```sql
-- Users (Agency-scoped)
users (
  id UUID PK,
  agency_id UUID NOT NULL REFERENCES agencies(id) ON DELETE RESTRICT,
  email TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  name TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'agent',  -- admin | manager | agent | viewer
  is_active BOOLEAN DEFAULT TRUE,
  mfa_secret_encrypted TEXT,
  mfa_enabled BOOLEAN DEFAULT FALSE,
  last_login_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(agency_id, email)             -- email unique within agency
)
-- INDEX: (agency_id), (agency_id, email), (agency_id, role, is_active)

-- Teams
teams (
  id UUID PK,
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  is_default BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(workspace_id, name)
)

team_members (
  team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role TEXT DEFAULT 'member',         -- lead | member
  PRIMARY KEY(team_id, user_id)
)
```

#### جدول‌های Conversations و Messages

```sql
-- Contacts (مخاطبین نهایی مشتری)
contacts (
  id UUID PK,
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  email TEXT,
  phone TEXT,
  name TEXT,
  avatar_url TEXT,
  attributes JSONB DEFAULT '{}',      -- custom fields
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
-- INDEX: (workspace_id, email), (workspace_id, phone)

-- Conversations
conversations (
  id UUID PK,
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  contact_id UUID REFERENCES contacts(id) ON DELETE SET NULL,
  subject TEXT,
  status TEXT NOT NULL DEFAULT 'open',  -- open | pending | resolved | closed
  priority TEXT DEFAULT 'normal',         -- low | normal | high | urgent
  assigned_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  assigned_team_id UUID REFERENCES teams(id) ON DELETE SET NULL,
  channel_id UUID REFERENCES channels(id) ON DELETE SET NULL,
  channel_type TEXT NOT NULL,             -- widget | email | whatsapp | ...
  first_message_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_message_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  resolved_at TIMESTAMPTZ,
  tags TEXT[] DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
-- INDEX: (workspace_id, status, last_message_at), (assigned_user_id, status),
--        (assigned_team_id, status), (contact_id)

-- Messages
messages (
  id UUID PK,
  conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  sender_type TEXT NOT NULL,             -- contact | agent | system | bot
  sender_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  content TEXT NOT NULL,
  content_html TEXT,                     -- rendered markdown
  is_internal BOOLEAN DEFAULT FALSE,     -- internal note
  attachments JSONB DEFAULT '[]',        -- list of attachment metadata
  external_id TEXT,                      -- for channels (e.g. wa_id)
  reply_to_message_id UUID REFERENCES messages(id) ON DELETE SET NULL,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
-- INDEX: (conversation_id, created_at)
```

#### جدول‌های Knowledge Base و Channels

```sql
-- KB Categories
kb_categories (
  id UUID PK,
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  slug TEXT NOT NULL,
  parent_id UUID REFERENCES kb_categories(id) ON DELETE CASCADE,
  position INT DEFAULT 0,
  UNIQUE(workspace_id, slug)
)

-- KB Articles
kb_articles (
  id UUID PK,
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  category_id UUID REFERENCES kb_categories(id) ON DELETE SET NULL,
  title TEXT NOT NULL,
  slug TEXT NOT NULL,
  content_md TEXT NOT NULL,              -- markdown
  content_html TEXT NOT NULL,           -- rendered
  is_published BOOLEAN DEFAULT FALSE,
  views_count INT DEFAULT 0,
  helpful_count INT DEFAULT 0,
  not_helpful_count INT DEFAULT 0,
  author_id UUID REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(workspace_id, slug)
)

-- Channels (config per channel type)
channels (
  id UUID PK,
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  type TEXT NOT NULL,                    -- widget | email | whatsapp_cloud | ...
  name TEXT NOT NULL,
  config JSONB DEFAULT '{}',             -- type-specific config
  credentials_encrypted TEXT,            -- Fernet encrypted JSON
  is_enabled BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
```

#### جدول‌های Audit و Automation

```sql
-- Audit Logs (Agency-scoped, never deleted with agency)
audit_logs (
  id BIGSERIAL PK,
  agency_id UUID NOT NULL REFERENCES agencies(id) ON DELETE RESTRICT,
  user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  action TEXT NOT NULL,                  -- e.g. "conversation.assign"
  target_type TEXT NOT NULL,
  target_id UUID,
  metadata JSONB DEFAULT '{}',
  ip_address INET,
  user_agent TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
-- INDEX: (agency_id, created_at), (user_id, created_at), (target_type, target_id)

-- Super Admin Audit Logs (separate, never mixed)
super_admin_audit_logs (
  id BIGSERIAL PK,
  super_admin_id UUID REFERENCES super_admins(id) ON DELETE SET NULL,
  action TEXT NOT NULL,
  target_type TEXT,
  target_id UUID,
  metadata JSONB DEFAULT '{}',
  ip_address INET,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)

-- Automation Rules
automation_rules (
  id UUID PK,
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  trigger_event TEXT NOT NULL,           -- conversation_created | message_received | ...
  conditions JSONB NOT NULL,             -- [{field, op, value}, ...]
  actions JSONB NOT NULL,                -- [{type, params}, ...]
  is_enabled BOOLEAN DEFAULT TRUE,
  priority INT DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)

-- SLA Policies
sla_policies (
  id UUID PK,
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  priority TEXT NOT NULL,
  response_time_minutes INT,
  resolution_time_minutes INT,
  conditions JSONB DEFAULT '{}',
  is_enabled BOOLEAN DEFAULT TRUE
)
```

#### جدول‌های Tags و Attachments

```sql
-- Tags (workspace-scoped)
tags (
  id UUID PK,
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  color TEXT DEFAULT '#6b7280',
  UNIQUE(workspace_id, name)
)

-- Attachments (metadata + content stored in object storage)
attachments (
  id UUID PK,
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  message_id UUID REFERENCES messages(id) ON DELETE CASCADE,
  filename TEXT NOT NULL,
  mime_type TEXT NOT NULL,
  size_bytes BIGINT NOT NULL,
  storage_key TEXT NOT NULL,             -- path in object storage
  storage_backend TEXT DEFAULT 'local',   -- local | s3 | ...
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
```

### ۵.۴ Row-Level Security (RLS) Policies

برای defense-in-depth، تمام جداول tenant-owned با RLS policies محافظت می‌شوند. این کار در فاز ۱ پیاده‌سازی می‌شود:

```sql
-- Example: enable RLS on conversations
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_conversations ON conversations
  USING (workspace_id IN (
    SELECT id FROM workspaces WHERE agency_id = current_setting('app.tenant_id')::uuid
  ));
```

**Application responsibility:** قبل از هر query، `SET app.tenant_id = '<agency_id>'` در session تنظیم می‌شود. این کار در middleware انجام می‌شود.

---

## ۶. روش دقیق جداسازی Tenantها

### ۶.۱ لایه Database

| روش | پیاده‌سازی |
|---|---|
| ** ستون `agency_id` در همه جداول tenant-owned** | تمام جداول دارای فیلد agency_id یا workspace_id (که به agency_id متصل است) هستند |
| **Row-Level Security (RLS) policies** | PostgreSQL RLS فعال می‌شود تا حتی در صورت فراموشی application layer، queryها به tenant دیگر نرسند |
| **Foreign Keys با `ON DELETE RESTRICT`** | برای داده‌های audit و حساس، حذف agency مسدود می‌شود تا data integrity حفظ شود |
| **Indexes ترکیبی `(agency_id, ...)`** | تمام query‌های پرکاربرد با composite index بهینه می‌شوند |

### ۶.۲ لایه API

| روش | پیاده‌سازی |
|---|---|
| **Tenant Context Middleware** | در هر درخواست، `tenant_id` از JWT استخراج شده و در `request.state.tenant_id` قرار می‌گیرد |
| **`get_current_agency_id` dependency** | تمام endpoints tenant-scoped به این dependency وابسته‌اند |
| **`assert_tenant_owned(record, agency_id)` helper** | قبل از بازگرداندن یا تغییر هر رکورد، ownership بررسی می‌شود |
| **Query helpers** | تمام queries به‌طور خودکار `WHERE agency_id = :tenant_id` را اضافه می‌کنند (در Repository layer) |
| **Fail-closed behavior** | اگر tenant_id نتواند resolve شود، 401 برمی‌گردد (نه 200 با داده اشتباه) |

### ۶.۳ لایه Authentication / Authorization

| روش | پیاده‌سازی |
|---|---|
| **JWT با `type` claim** | توکن‌های agency با `type=agency`، توکن‌های super admin با `type=super_admin`، توکن‌های widget با `type=widget` |
| **Separate signing keys** | `secret_key` برای agency، `super_admin_secret_key` برای super admin، `widget_secret_key` برای widget |
| **Strict type checking** | هر decoder فقط نوع خود را می‌پذیرد (نه مثل OpenLivery که cross-accept داشت) |
| **Role-based access control (RBAC)** | ۵ نقش: super_admin، agency_admin، manager، agent، viewer |
| **Permission keys** | به جای چک مستقیم نقش، permission keys چک می‌شوند (مثلاً `conversation.assign`) |
| **Rate limiting** | روی endpoints احراز هویت (login، register، password reset) و endpoints عمومی (widget) |

### ۶.۴ لایه File Storage

| روش | پیاده‌سازی |
|---|---|
| **Storage key با tenant prefix** | تمام فایل‌ها با مسیر `tenants/<agency_id>/workspaces/<workspace_id>/attachments/<file_id>` ذخیره می‌شوند |
| **Pre-signed URLs** | برای download، URLs موقت با انقضا صادر می‌شوند |
| **Auth check قبل از serve** | حتی با pre-signed URL، ownership چک می‌شود |
| **Storage backend abstraction** | interface که local file system یا S3-compatible را پشتیبانی می‌کند |

### ۶.۵ لایه Background Jobs

| روش | پیاده‌سازی |
|---|---|
| **Tenant context در job** | هر job در payload خود `tenant_id` دارد و قبل از اجرا `SET app.tenant_id` می‌کند |
| **Per-tenant rate limits** | برای fairness بین tenants |
| **Job isolation** | یک job tenant A هرگز به داده‌های tenant B دسترسی ندارد (fail-closed) |
| **Async tasks** | با ARQ یا similar، با tenant_id در task signature |

### ۶.۶ لایه Search

| روش | پیاده‌سازی |
|---|---|
| **Tenant filter در همه queries** | تمام search queries با `agency_id = :tenant_id` فیلتر می‌شوند |
| **Index names با tenant prefix** | اگر از Elasticsearch استفاده شود (post-MVP) |
| **MVP: PostgreSQL full-text search** | با `tsvector` و `ts_query`، scoped به tenant |

### ۶.۷ لایه Reports

| روش | پیاده‌سازی |
|---|---|
| **Pre-aggregated per tenant** | داشبوردها از داده‌های همان tenant محاسبه می‌شوند |
| **No cross-tenant aggregation** | هیچ گزارشی داده‌های tenant‌های مختلف را ترکیب نمی‌کند (مگر در super admin dashboard) |
| **Materialized views** | برای performance، materialized views با tenant_id column |

### ۶.۸ لایه Webhooks

| روش | پیاده‌سازی |
|---|---|
| **Per-channel secret** | هر channel webhook با HMAC-SHA256 و secret اختصاصی امضا می‌شود |
| **Channel resolution با ownership** | Webhook ابتدا channel را با `id + agency_id` پیدا می‌کند (نه فقط id) |
| **Tenant context propagation** | پس از verify، tenant_id از channel استخراج شده و در context قرار می‌گیرد |

### ۶.۹ لایه Notifications

| روش | پیاده‌سازی |
|---|---|
| **Tenant-scoped notification queue** | notification‌ها در صف tenant-specific قرار می‌گیرند |
| **User-scoped preferences** | هر کاربر تنظیمات اطلاع‌رسانی خود را دارد (درون tenant) |
| **No cross-tenant notifications** | یک notification هرگز به کاربر tenant دیگر ارسال نمی‌شود |

### ۶.۱۰ قانون کلی

> **هیچ‌کدام از این لایه‌ها به تنهایی کافی نیست. Defense-in-depth الزامی است. اگر یک لایه شکست بخورد، لایه بعدی جلوی leak را می‌گیرد.**

---

## ۷. ساختار پوشه‌ها و فایل‌های پروژه جدید

مسیر پروژه: `/home/z/my-project/m369-support/`

```
m369-support/
├── README.md
├── LICENSE                                  # MIT
├── docker-compose.yml                       # Local dev: api, db, redis, mailhog
├── docker-compose.test.yml                 # Test environment
├── .env.example
├── .gitignore
├── .editorconfig
├── Makefile                                 # Common commands
├── pyproject.toml                           # Python project config (ruff, mypy, pytest)
│
├── apps/
│   ├── api/                                 # Backend (FastAPI)
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── requirements.txt
│   │   ├── alembic.ini
│   │   ├── app/
│   │   │   ├── __init__.py
│   │   │   ├── main.py                      # FastAPI app
│   │   │   ├── config.py                    # Settings via pydantic-settings
│   │   │   ├── database.py                  # Engine, SessionLocal, get_db
│   │   │   ├── deps.py                      # get_current_user, get_current_agency_id
│   │   │   ├── tenant.py                    # tenant context, assert_tenant_owned
│   │   │   ├── security.py                  # JWT, password hashing
│   │   │   ├── permissions.py               # Permission keys + check helpers
│   │   │   ├── ratelimit.py                 # Rate limiting
│   │   │   ├── audit.py                     # Audit log helpers
│   │   │   ├── exceptions.py                # Custom exceptions
│   │   │   │
│   │   │   ├── models/                      # SQLAlchemy models (one file per domain)
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py                  # Base, mixins (TimestampMixin, TenantMixin)
│   │   │   │   ├── tenant.py                # Agency, Workspace
│   │   │   │   ├── user.py                  # User, Team, TeamMember
│   │   │   │   ├── conversation.py          # Contact, Conversation, Message
│   │   │   │   ├── knowledge.py             # KBCategory, KBArticle
│   │   │   │   ├── channel.py               # Channel
│   │   │   │   ├── automation.py            # AutomationRule, SLAPolicy
│   │   │   │   ├── super_admin.py           # SuperAdmin, SuperAdminAuditLog
│   │   │   │   └── audit.py                 # AuditLog
│   │   │   │
│   │   │   ├── schemas/                     # Pydantic schemas (one file per domain)
│   │   │   │   ├── __init__.py
│   │   │   │   ├── auth.py
│   │   │   │   ├── tenant.py
│   │   │   │   ├── user.py
│   │   │   │   ├── conversation.py
│   │   │   │   ├── knowledge.py
│   │   │   │   ├── channel.py
│   │   │   │   └── ...
│   │   │   │
│   │   │   ├── routers/                     # API endpoints (versioned /api/v1)
│   │   │   │   ├── __init__.py
│   │   │   │   ├── v1/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── auth.py              # /auth/register, /auth/login, /auth/me
│   │   │   │   │   ├── agencies.py          # /agencies/*
│   │   │   │   │   ├── workspaces.py        # /workspaces/*
│   │   │   │   │   ├── users.py             # /users/*
│   │   │   │   │   ├── teams.py             # /teams/*
│   │   │   │   │   ├── contacts.py          # /contacts/*
│   │   │   │   │   ├── conversations.py     # /conversations/*
│   │   │   │   │   ├── messages.py          # /conversations/{id}/messages/*
│   │   │   │   │   ├── kb.py                # /kb/categories, /kb/articles
│   │   │   │   │   ├── channels.py          # /channels/*
│   │   │   │   │   ├── automation.py        # /automation/rules/*
│   │   │   │   │   ├── sla.py               # /sla/policies/*
│   │   │   │   │   ├── tags.py              # /tags/*
│   │   │   │   │   ├── reports.py           # /reports/*
│   │   │   │   │   ├── audit.py             # /audit/logs
│   │   │   │   │   └── ...
│   │   │   │   ├── super_admin/             # /admin/* (separate auth)
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── auth.py              # /admin/auth/login (with MFA)
│   │   │   │   │   ├── agencies.py          # /admin/agencies/*
│   │   │   │   │   ├── audit.py             # /admin/audit/*
│   │   │   │   │   └── ...
│   │   │   │   ├── widget/                  # /widget/* (public, for embeds)
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── chat.py              # /widget/{public_id}/messages
│   │   │   │   │   └── ...
│   │   │   │   └── webhooks/                # /webhooks/* (channel callbacks)
│   │   │   │       ├── __init__.py
│   │   │   │       ├── email.py             # /webhooks/email
│   │   │   │       └── ...
│   │   │   │
│   │   │   ├── services/                    # Business logic
│   │   │   │   ├── __init__.py
│   │   │   │   ├── auth_service.py
│   │   │   │   ├── user_service.py
│   │   │   │   ├── agency_service.py
│   │   │   │   ├── conversation_service.py
│   │   │   │   ├── message_service.py
│   │   │   │   ├── contact_service.py
│   │   │   │   ├── kb_service.py
│   │   │   │   ├── channel_service.py
│   │   │   │   ├── automation_service.py
│   │   │   │   ├── sla_service.py
│   │   │   │   ├── audit_service.py
│   │   │   │   └── ...
│   │   │   │
│   │   │   ├── repositories/                # Data access layer (always tenant-scoped)
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py                  # BaseRepository with tenant_id filter
│   │   │   │   ├── user_repo.py
│   │   │   │   ├── conversation_repo.py
│   │   │   │   └── ...
│   │   │   │
│   │   │   ├── middleware/                   # FastAPI middleware
│   │   │   │   ├── __init__.py
│   │   │   │   ├── tenant_context.py        # Resolves and sets tenant_id
│   │   │   │   ├── audit_log.py             # Logs API actions
│   │   │   │   └── ...
│   │   │   │
│   │   │   └── utils/                        # Shared utilities
│   │   │       ├── __init__.py
│   │   │       ├── crypto.py                # Fernet encryption helpers
│   │   │       ├── pagination.py
│   │   │       ├── slugs.py
│   │   │       └── ...
│   │   │
│   │   ├── migrations/                      # Alembic
│   │   │   ├── env.py
│   │   │   ├── script.py.mako
│   │   │   └── versions/
│   │   │       ├── 0001_initial.py          # Super admins + agencies + users
│   │   │       ├── 0002_workspaces.py
│   │   │       ├── 0003_teams.py
│   │   │       ├── 0004_contacts_conversations_messages.py
│   │   │       ├── 0005_knowledge_base.py
│   │   │       ├── 0006_channels.py
│   │   │       ├── 0007_automation_sla.py
│   │   │       ├── 0008_audit_logs.py
│   │   │       ├── 0009_tags_attachments.py
│   │   │       └── 0010_rls_policies.py     # Enable RLS
│   │   │
│   │   ├── tests/
│   │   │   ├── __init__.py
│   │   │   ├── conftest.py                  # Fixtures: client, db, authenticated_client, ...
│   │   │   ├── unit/                        # Pure unit tests (no DB)
│   │   │   │   ├── test_tenant.py
│   │   │   │   ├── test_security.py
│   │   │   │   ├── test_permissions.py
│   │   │   │   └── ...
│   │   │   ├── integration/                 # DB-integration tests
│   │   │   │   ├── test_auth_flow.py
│   │   │   │   ├── test_tenant_isolation.py
│   │   │   │   ├── test_conversations.py
│   │   │   │   └── ...
│   │   │   └── e2e/                          # End-to-end tests
│   │   │       └── test_full_signup_flow.py
│   │   │
│   │   └── scripts/                          # CLI scripts
│   │       ├── create_super_admin.py
│   │       ├── reset_password.py
│   │       └── ...
│   │
│   ├── web/                                  # Frontend (Next.js)
│   │   ├── Dockerfile
│   │   ├── package.json
│   │   ├── next.config.ts
│   │   ├── tailwind.config.ts
│   │   ├── tsconfig.json
│   │   ├── app/                              # App Router
│   │   │   ├── (auth)/                       # Auth pages group
│   │   │   │   ├── login/page.tsx
│   │   │   │   ├── register/page.tsx
│   │   │   │   └── ...
│   │   │   ├── (portal)/                     # Agency Portal group
│   │   │   │   ├── layout.tsx
│   │   │   │   ├── inbox/page.tsx
│   │   │   │   ├── conversations/[id]/page.tsx
│   │   │   │   ├── contacts/page.tsx
│   │   │   │   ├── knowledge-base/page.tsx
│   │   │   │   ├── reports/page.tsx
│   │   │   │   ├── settings/page.tsx
│   │   │   │   └── ...
│   │   │   ├── (admin)/                      # Super Admin group
│   │   │   │   ├── layout.tsx
│   │   │   │   ├── agencies/page.tsx
│   │   │   │   ├── audit/page.tsx
│   │   │   │   └── ...
│   │   │   ├── (customer)/                   # Customer portal
│   │   │   │   └── c/[agencySlug]/page.tsx
│   │   │   └── api/                          # Next.js API routes (if needed)
│   │   │
│   │   ├── components/                       # Reusable React components
│   │   │   ├── ui/                           # shadcn/ui base components
│   │   │   ├── inbox/
│   │   │   ├── conversations/
│   │   │   └── ...
│   │   │
│   │   ├── lib/                              # Client-side utilities
│   │   │   ├── api-client.ts
│   │   │   ├── auth.ts
│   │   │   └── ...
│   │   │
│   │   ├── hooks/                            # React hooks
│   │   │   ├── use-conversations.ts
│   │   │   └── ...
│   │   │
│   │   ├── stores/                           # Zustand stores (UI state)
│   │   │   └── ...
│   │   │
│   │   ├── types/                            # TypeScript types
│   │   │   └── api.ts                        # Generated from OpenAPI
│   │   │
│   │   └── public/
│   │       ├── widget.js                     # Standalone widget script
│   │       └── ...
│   │
│   └── widget/                               # Standalone embeddable widget
│       ├── package.json
│       ├── vite.config.ts
│       ├── src/
│       │   ├── main.tsx
│       │   ├── App.tsx
│       │   └── ...
│       └── ...
│
├── packages/                                 # Shared packages (monorepo)
│   ├── shared-types/                         # Shared TypeScript types
│   └── api-spec/                             # OpenAPI spec source
│
├── docker/                                   # Docker configs
│   ├── postgres/
│   │   └── init.sql
│   └── ...
│
├── docs/                                     # Documentation
│   ├── architecture.md
│   ├── api.md
│   ├── deployment.md
│   └── ...
│
└── .github/                                  # CI/CD
    └── workflows/
        ├── test.yml
        └── lint.yml
```

---

## ۸. برنامه فازبندی پیاده‌سازی با ترتیب وابستگی‌ها

### فاز ۱: Foundation و Multi-Tenancy (هسته)

**مدت تخمینی:** ۱-۲ هفته

**خروجی‌ها:**
- ✅ ساختار پروژه اولیه (Docker Compose, pyproject.toml, package.json)
- ✅ Database schema برای tenants, users, workspaces
- ✅ Migrations 0001-0003
- ✅ Auth system (register, login, JWT)
- ✅ Tenant Context Middleware
- ✅ `assert_tenant_owned` helper
- ✅ Permission system (RBAC)
- ✅ Audit logging infrastructure
- ✅ Rate limiting
- ✅ Health endpoints
- ✅ Tests: tenant isolation، auth flow، permission check

**وابستگی‌ها:** هیچ (این فاز پایه است)

### فاز ۲: مدیریت کاربران و تیم‌ها

**مدت تخمینی:** ۱ هفته

**خروجی‌ها:**
- ✅ CRUD users (با invite flow)
- ✅ CRUD teams + team_members
- ✅ User profile + avatar upload
- ✅ Password reset flow
- ✅ Optional 2FA (TOTP)
- ✅ Frontend: Users management page، Teams page

**وابستگی‌ها:** فاز ۱ کامل

### فاز ۳: صندوق ورودی و مکالمات

**مدت تخمینی:** ۲-۳ هفته

**خروجی‌ها:**
- ✅ CRUD contacts
- ✅ CRUD conversations + messages
- ✅ Internal notes
- ✅ Assignment (user/team)
- ✅ Status changes (open, pending, resolved, closed)
- ✅ Tags
- ✅ Attachments (with file storage abstraction)
- ✅ Frontend: Inbox UI، Conversation detail، Composer

**وابستگی‌ها:** فاز ۱ + فاز ۲

### فاز ۴: پایگاه دانش و پرتال مشتری

**مدت تخمینی:** ۱-۲ هفته

**خروجی‌ها:**
- ✅ CRUD KB categories + articles
- ✅ Markdown rendering
- ✅ Full-text search (PostgreSQL tsvector)
- ✅ Customer portal (KB search + submit ticket)
- ✅ Frontend: KB admin، Customer portal

**وابستگی‌ها:** فاز ۱ + فاز ۳

### فاز ۵: کانال Web Widget

**مدت تخمینی:** ۱-۲ هفته

**خروجی‌ها:**
- ✅ Embeddable widget (vanilla JS، iframe-based)
- ✅ Real-time chat (WebSocket یا polling)
- ✅ Widget configuration (color، position، greeting)
- ✅ Offline mode (form submission)
- ✅ Frontend: Widget config page

**وابستگی‌ها:** فاز ۳

### فاز ۶: اتوماسیون و SLA

**مدت تخمینی:** ۲ هفته

**خروجی‌ها:**
- ✅ Automation rules engine (conditions + actions)
- ✅ SLA policies (response time، resolution time)
- ✅ Canned responses
- ✅ Frontend: Automation builder، SLA config

**وابستگی‌ها:** فاز ۳

### فاز ۷: گزارش‌گیری

**مدت تخمینی:** ۱-۲ هفته

**خروجی‌ها:**
- ✅ Dashboard با KPIs (volume، response time، resolution rate)
- ✅ Reports (conversations، agents، SLA)
- ✅ CSV export
- ✅ Frontend: Reports pages، Dashboard

**وابستگی‌ها:** فاز ۳ + فاز ۶

### فاز ۸: کانال ایمیل

**مدت تخمینی:** ۱-۲ هفته

**خروجی‌ها:**
- ✅ IMAP polling یا email webhook integration
- ✅ Outbound email (SMTP یا service like Resend)
- ✅ Email-to-conversation mapping
- ✅ Frontend: Email channel config

**وابستگی‌ها:** فاز ۳

### فاز ۹: Super Admin Dashboard

**مدت تخمینی:** ۱-۲ هفته

**خروجی‌ها:**
- ✅ Super admin auth (separate JWT، MFA required)
- ✅ Agency management (CRUD، suspend، activate)
- ✅ System-wide audit logs
- ✅ System reports (cross-tenant، anonymized)
- ✅ Frontend: Super admin pages

**وابستگی‌ها:** فاز ۱ + فاز ۳

### فاز ۱۰: Subscription و Billing

**مدت تخمینی:** ۲-۳ هفته

**خروجی‌ها:**
- ✅ Plans table (Starter، Growth، Pro، VIP)
- ✅ Subscriptions (lifecycle: trial، active، past_due، suspended، cancelled)
- ✅ Crypto payments (USDT TRC20 + BEP20) با manual verification
- ✅ Quota guard (max users، conversations، AI cost)
- ✅ Frontend: Pricing page، Billing dashboard

**وابستگی‌ها:** فاز ۹

### فاز‌های بعدی (Post-MVP):

- فاز ۱۱: i18n چندزبانه (fa، en، ar، tr، ru + RTL)
- فاز ۱۲: کانال پیام‌رسان (WhatsApp Cloud، Telegram)
- فاز ۱۳: AI Assistant (Copilot با LLM)
- فاز ۱۴: CSAT و NPS
- فاز ۱۵: Custom Domain + White-label
- فاز ۱۶: Mobile App (iOS، Android)
- فاز ۱۷: Advanced Search (Elasticsearch)
- فاز ۱۸: Backup و Disaster Recovery
- فاز ۱۹: Production Deployment (VPS با Caddy v2)

---

## ۹. انتخاب نسخه‌های پایدار و فهرست وابستگی‌ها و مجوزهایشان

### ۹.۱ بک‌اند (Python)

| پکیج | نسخه پیشنهادی | آخرین stable تأیید شده | مجوز | کاربرد |
|---|---|---|---|---|
| `python` | 3.12.16 | 3.12.16 (نصب شده) | PSF License | زبان اصلی |
| `fastapi` | 0.116.0 | 0.162.0 (آخرین) | MIT | Web framework |
| `uvicorn[standard]` | 0.32.1 | 0.54.0 | BSD-3-Clause | ASGI server |
| `sqlalchemy` | 2.0.57 | 2.1.8 (آخرین) | MIT | ORM |
| `alembic` | 1.16.5 | 1.20.1 | MIT | Migrations |
| `pydantic` | 2.10.6 | 2.14.2 | MIT | Validation |
| `pydantic-settings` | 2.10.x | 2.10.x | MIT | Settings |
| `psycopg[binary]` | 3.2.13 | 3.3.8 | LGPL-3.0 | PostgreSQL driver |
| `pyjwt` | 2.10.1 | 2.15.1 | MIT | JWT |
| `bcrypt` | 4.2.1 | 5.0.0 | Apache-2.0 | Password hashing |
| `python-multipart` | 0.0.20 | 0.0.33 | Apache-2.0 | Form data |
| `email-validator` | 2.2.x | 2.2.x | BSD-3-Clause | Email validation |
| `httpx` | 0.28.1 | 0.28.1 | BSD-3-Clause | HTTP client |
| `cryptography` | 4.x stable | 50.0.0 | Apache-2.0/BSD | Crypto (Fernet) |
| `argon2-cffi` | 23.x | 23.x | MIT | Argon2 (alt to bcrypt) |
| `slowapi` | 0.1.9 | 0.1.9 | MIT | Rate limiting |
| `arq` | 0.26.x | 0.26.x | MIT | Async job queue |
| `redis` | 5.x | 5.x | MIT | Cache/queue backend |
| `pytest` | 8.3.5 | 9.2.0 | MIT | Testing |
| `pytest-asyncio` | 0.24.x | 0.24.x | MIT | Async tests |
| `pytest-cov` | 6.x | 7.0.0 | MIT | Coverage |
| `ruff` | 0.8.x | 0.8.x | MIT | Linter + formatter |
| `mypy` | 1.13.x | 1.13.x | MIT | Type checker |

**توضیح انتخاب نسخه‌ها:** به‌جای آخرین absolute version، آخرین نسخه پایدار major line انتخاب شده تا از breaking changes اجتناب شود.

### ۹.۲ فرانت‌اند (Node)

| پکیج | نسخه پیشنهادی | آخرین stable تأیید شده | مجوز | کاربرد |
|---|---|---|---|---|
| `node` | 20 LTS | 24.x (نصب شده 24.22.2) | MIT | Runtime |
| `next` | 15.x | 16.4.5 | MIT | React framework |
| `react` | 19.x | 19.3.1 | MIT | UI library |
| `react-dom` | 19.x | 19.3.1 | MIT | React DOM |
| `typescript` | 5.x | 7.0.2 | Apache-2.0 | Type system |
| `tailwindcss` | 4.x | 4.3.4 | MIT | CSS framework |
| `zod` | 3.x | 4.6.7 | MIT | Schema validation |
| `@tanstack/react-query` | 5.x | 5.105.3 | MIT | Data fetching |
| `@radix-ui/react-*` | 1.x | latest | MIT | Headless components |
| `class-variance-authority` | 0.7.x | 0.7.x | Apache-2.0 | Variant management |
| `clsx` | 2.x | 2.x | MIT | Class composition |
| `tailwind-merge` | 2.x | 2.x | MIT | Tailwind class merging |
| `lucide-react` | 0.4xx | latest | ISC | Icons |
| `eslint` | 9.x | 9.x | MIT | Linter |
| `prettier` | 3.x | 3.x | MIT | Formatter |

### ۹.۳ Database و Infrastructure

| ابزار | نسخه | مجوز | کاربرد |
|---|---|---|---|
| PostgreSQL | 16.x | PostgreSQL License | Database |
| Redis | 7.x | BSD-3-Clause | Cache + queue |
| Docker | 24.x | Apache-2.0 | Containerization |
| Docker Compose | 2.x | Apache-2.0 | Local dev |
| Caddy | 2.x | Apache-2.0 | Reverse proxy (production) |

### ۹.۴ توسعه و تست

| ابزار | نسخه | مجوز | کاربرد |
|---|---|---|---|
| `git` | 2.x | GPL-2.0 | Version control |
| `pre-commit` | 3.x | MIT | Git hooks |
| `pip-tools` | 7.x | BSD-3-Clause | Dependency pinning |
| `pnpm` | 9.x | MIT | Package manager (frontend) |

---

## ۱۰. روش تست امنیتی و عملکردی هر فاز

### ۱۰.۱ تست‌های امنیتی (Security Testing)

#### Unit Tests (هر فاز)

- **Tenant Isolation Tests:**
  - Agency A نمی‌تواند داده‌های Agency B را بخواند
  - Agency A نمی‌تواند داده‌های Agency B را تغییر دهد یا حذف کند
  - بدون tenant context → 401 Unauthorized
  - با tenant context نامعتبر → 401 Unauthorized

- **Auth Tests:**
  - JWT type confusion rejection (agency token به عنوان super admin یا widget)
  - JWT expiry enforcement
  - JWT signature verification
  - Password hash verification (bcrypt)

- **Permission Tests:**
  - Agent نمی‌تواند کاربر ایجاد کند (فقط admin/manager)
  - Viewer نمی‌تواند مکالمه را تغییر دهد
  - Cross-workspace access blocked

#### Integration Tests (هر فاز)

- **Real PostgreSQL** با RLS فعال
- **Cross-tenant data leak attempts** با دو agency واقعی
- **Webhook signature verification** با HMAC-SHA256
- **File storage access** با pre-signed URLs

#### PenTest ممیزی (هر فاز بحرانی)

- Static analysis با `ruff` و `bandit`
- Dependency vulnerability scan با `pip-audit` و `npm audit`
- Manual code review توسط ChatGPT قبل از merge

### ۱۰.۲ تست‌های عملکردی (Functional Testing)

#### Unit Tests (هر فاز)

- **Business Logic Tests:**
  - مثلاً: SLA calculation، automation rule execution
  - هر سرویس با mock dependencies

- **Schema Validation Tests:**
  - Pydantic schemas با invalid input
  - API endpoints با malformed payload

#### Integration Tests (هر فاز)

- **End-to-End flows:**
  - Sign-up → First conversation → Resolve → Close
  - Contact creation → Multiple conversations → Merge contacts
  - KB article creation → Publish → Customer search → View

- **API contract tests:**
  - All endpoints documented در OpenAPI
  - Status codes و error formats consistent

#### E2E Tests (مرحله پایانی هر فاز)

- **Browser-based** با Playwright یا Cypress
- **Real user workflows** در محیط staging
- **Visual regression** برای صفحات کلیدی

### ۱۰.۳ تست‌های عملکرد (Performance Testing)

- **Database query analysis** با `EXPLAIN ANALYZE` روی queries پرکاربرد
- **Load testing** با Locust یا k6 روی endpoints کلیدی
- **Connection pool monitoring**
- **Slow query log** در PostgreSQL

### ۱۰.۴ تست CI/CD

- **هر commit** → `ruff check`، `mypy`، `pytest unit`
- **هر PR** → integration tests + coverage report
- **هر merge به main** → build Docker images

### ۱۰.۵ Coverage اهداف

| لایه | هدف coverage |
|---|---|
| Services (business logic) | ≥ ۸۰% |
| Repositories (data access) | ≥ ۹۰% |
| Security-critical paths | ≥ ۹۵% |
| API endpoints | ≥ ۷۰% |
| Frontend components | ≥ ۶۰% |

### ۱۰.۶ قوانین تست (مهم)

- ✅ هیچ تستی PASS اعلام نشود مگر واقعاً اجرا شده باشد
- ✅ خروجی خام تست‌ها در هر delivery ذخیره شود
- ✅ Integration tests با PostgreSQL واقعی، نه SQLite mock
- ✅ Cross-tenant isolation tests در هر فاز پرکاربرد
- ✅ Tests BLOCKED شوند اگر پیش‌نیازها (مثل PG) در دسترس نباشند — نه PASS

---

## ۱۱. موارد نیاز پیش از شروع پیاده‌سازی

### ۱۱.۱ تصمیمات محصولی مورد نیاز از Owner

| # | تصمیم | توضیح |
|---|---|---|
| ۱ | تأیید نام محصول | "M369 Support" به‌عنوان نام رسمی |
| ۲ | تأیید برند رنگ | `#FF6B35` (vivid orange) به‌عنوان brand color |
| ۳ | تأیید زبان پیش‌فرض | انگلیسی یا فارسی برای MVP |
| ۴ | تأیید قیمت‌گذاری | آیا قیمت‌گذاری در MVP گنجانده شود یا به فاز ۱۰ منتقل شود؟ |
| ۵ | انتخاب ستون secure secret storage | آیا از environment variables کافی است یا نیاز به Vault دارد؟ |
| ۶ | آدرس دامنه | m369support.io یا چیز دیگر |

### ۱۱.۲ تصمیمات فنی مورد نیاز از ChatGPT

| # | تصمیم | توضیح |
|---|---|---|
| ۱ | تأیید معماری | این معماری کلی مورد تأیید است؟ |
| ۲ | تأیید stack فناوری | آیا FastAPI + Next.js + PostgreSQL پذیرفته است؟ |
| ۳ | تأیید ترتیب فازها | آیا ترتیب فاز ۱-۱۰ درست است؟ |
| ۴ | اولویت اول فاز | آیا فاز ۱ (Foundation) اولویت اول است؟ |
| ۵ | تأیید استفاده از RLS | آیا PostgreSQL RLS استفاده شود یا فقط application-level؟ |

### ۱۱.۳ مواردی که BLOCKED هستند

- **هیچ کدنویسی شروع نمی‌شود** تا Owner و ChatGPT این موارد را تأیید کنند
- **هیچ فایلی در `/home/z/my-project/m369-support/` ساخته نمی‌شود** مگر پس از تأیید معماری
- **هیچ فایلی در OpenLivery repo (`/home/z/my-project/m369-repo/`) دست نمی‌خورد** (طبق Rule 1 از تصمیم Owner)

---

## ۱۲. خلاصه نهایی

این سند یک معماری کامل و مستقل برای ساخت M369 Support به‌عنوان یک SaaS چندمستاجری ارائه می‌دهد. نکات کلیدی:

۱. **آموزش از ۵ محصول مرجع** بدون کپی کد/برند/طراحی.
۲. **معماری layered** با tenant isolation در همه لایه‌ها (defense-in-depth).
۳. **PostgreSQL RLS** به‌عنوان خط دفاعی پایانی.
۴. **JWT با type claim و signing keys جدا** برای هر سطح دسترسی.
۵. **مهاجرت از OpenLivery متوقف شد** — پروژه از صفر شروع می‌شود.
۶. **۱۰ فاز** برای رسیدن به MVP کامل + فازهای بعدی برای قابلیت‌های پیشرفته.
۷. **نسخه‌های پایدار** انتخاب شده‌اند (نه bleeding edge).
۸. **تست‌ها در هر فاز** با قوانین سختگیرانه (هیچ PASS بدون اجرا).

**منتظر تأیید Owner و ChatGPT هستم** پیش از شروع فاز ۱ (Foundation).

---

**پایان سند**

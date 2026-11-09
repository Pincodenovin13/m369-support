# Architecture Overview

## System Architecture

M369 Support is a multi-tenant SaaS customer support platform built as a modular monolith. The architecture prioritises tenant isolation at every layer — defense in depth is non-negotiable.

```
┌─────────────────────────────────────────────────────────────────┐
│  Frontend (Next.js 15)                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ Agency      │  │ Super Admin │  │ Customer Widget (future)│ │
│  │ Portal      │  │ Dashboard   │  │ + Customer Portal       │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ (HTTP, cookies)
┌─────────────────────────────────────────────────────────────────┐
│  FastAPI Backend (Python 3.12)                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  API Layer (routers) /api/v1                              │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Signed Tenant Context (per-request, transaction-scoped)  │  │
│  │  SET LOCAL tenant_id + HMAC signature → DB verifier/RLS   │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Service Layer (business logic)                          │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  PostgreSQL 16                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Row-Level Security on all tenant-owned tables            │  │
│  │  Composite FK constraints prevent cross-tenant references │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Tenant Hierarchy

```
M369 Platform
  └── Agency (tenant root)
       └── Workspace
            ├── Teams
            ├── Contacts
            ├── Channels (future)
            ├── Conversations
            └── Knowledge Base (future)
```

## Identity Separation

| Identity | Auth Surface | JWT Type | Signing Key |
|---|---|---|---|
| Agency User | Agency Portal | `agency` | `JWT_SECRET_KEY` |
| Super Admin | Super Admin Dashboard | `super_admin` | `JWT_SUPER_ADMIN_SECRET_KEY` |
| Customer (future) | Widget / Customer Portal | `customer` (future) | (future) |

JWT decoders are type-strict: a `super_admin` token can never be decoded as an `agency` token and vice versa.

## Defense-in-Depth Tenant Isolation

1. **Database RLS** — 17 RLS-protected tables (16 tenant-scoped + 1 platform-private), fail-closed when `app.tenant_id` unset
2. **Composite FK constraints** — 16 constraints prevent cross-tenant references, including workspace/agency checks for contacts and teams
3. **TenantContextMiddleware** — resolves JWT, builds `TenantContext`
4. **`SET LOCAL app.tenant_id`** — transaction-scoped, no leak across pooled connections
5. **`assert_tenant_owned()`** — application-level ownership check, fail-closed (404)

See `docs/security/tenant-isolation.md` for details.


**Current security boundary:** tenant RLS policies use `public.m369_current_tenant_id()` to verify the transaction-local `app.tenant_id` and `app.tenant_sig` pair with HMAC-SHA256. An arbitrary SQL caller running as `m369_app` cannot forge another tenant context without the signing secret. The secret is stored in the private schema and is not readable by the runtime role. Compromise of the API process or signing secret remains in the threat model. This implementation is covered by PostgreSQL 16 CI; production role/grant/secret provisioning still requires deployment verification. See [tenant isolation](../security/tenant-isolation.md).

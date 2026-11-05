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
│  │  Tenant Context (per-request, transaction-scoped)         │  │
│  │  SET LOCAL app.tenant_id = '<uuid>' → RLS filters rows    │  │
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

1. **Database RLS** — all 8 tenant-owned tables, fail-closed when `app.tenant_id` unset
2. **Composite FK constraints** — 4 constraints prevent cross-tenant references
3. **TenantContextMiddleware** — resolves JWT, builds `TenantContext`
4. **`SET LOCAL app.tenant_id`** — transaction-scoped, no leak across pooled connections
5. **`assert_tenant_owned()`** — application-level ownership check, fail-closed (404)

See `docs/security/tenant-isolation.md` for details.

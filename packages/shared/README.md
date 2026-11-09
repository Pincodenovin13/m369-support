# M369 Support Shared — Shared TypeScript Types

> **Path:** `packages/shared/`
> **Status:** ⚠️ `[PLANNED]` — NOT IMPLEMENTED
> **Parent docs:** [`/REPOSITORY_MAP.md`](../../REPOSITORY_MAP.md) · [`/STATE.md`](../../STATE.md)

Shared TypeScript types for the M369 Support monorepo. This is a future package.

## Current State

This directory currently contains only a placeholder:

```
packages/shared/
└── .gitkeep
```

**No source code, no package.json, no tsconfig.** The shared types package is planned but not yet needed (the web app and widget do not currently share types).

## When Implementation Begins

When the widget and web app need to share TypeScript types (e.g., API contract types), they will live here:

```
packages/shared/
├── src/
│   ├── index.ts          # Re-exports all types
│   ├── api.ts            # API request/response types
│   ├── models.ts         # Domain model types (Agency, User, Workspace, etc.)
│   └── auth.ts           # Auth-related types (token claims, roles)
├── package.json
└── tsconfig.json
```

## Do NOT Add Fake Types

Until the web app and widget actually need shared types, this README and the `.gitkeep` placeholder are the only files in this directory. Adding speculative types would create maintenance burden without clear ownership.

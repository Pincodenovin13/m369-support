# M369 Support Web — Next.js Frontend

> **Path:** `apps/web/`
> **Runtime:** Next.js 15.1, React 19, TypeScript 5.7, Tailwind CSS 3.4.17, TanStack Query v5
> **Parent docs:** [`/REPOSITORY_MAP.md`](../../REPOSITORY_MAP.md) · [`/STATE.md`](../../STATE.md)

The Next.js frontend for M369 Support. Provides the Agency Portal (login, dashboard, workspace list) and will host the Super Admin Console (Phase 9).

## Quick Start

```bash
cd apps/web
npm install
npm run dev          # http://localhost:3000
```

## Scripts

| Script | Purpose |
|---|---|
| `npm run dev` | Start dev server with HMR |
| `npm run build` | Production build |
| `npm run start` | Start production server |
| `npm run lint` | ESLint (`eslint src --ext .ts,.tsx`) |
| `npm run type-check` | `tsc --noEmit` |

## Structure

```
apps/web/
├── src/
│   ├── app/                    # Next.js App Router pages
│   │   ├── layout.tsx          # Root layout
│   │   ├── page.tsx            # Landing page (/)
│   │   ├── globals.css         # Global Tailwind styles
│   │   ├── login/page.tsx      # Email + password + multi-agency selection
│   │   ├── register/page.tsx   # First-agency self-registration
│   │   └── dashboard/page.tsx  # Workspace list + agency info (auth required)
│   ├── components/             # Reusable React components
│   │   ├── providers.tsx       # TanStack Query provider
│   │   └── dashboard-shell.tsx # Dashboard layout shell
│   └── lib/                    # Frontend utilities
│       ├── api-client.ts       # Single API client (cookie-based auth, 401 auto-refresh)
│       └── utils.ts             # Misc utilities
├── package.json                # Deps + scripts
├── tsconfig.json               # TypeScript config (strict, src-layout)
├── tailwind.config.ts          # Tailwind config
├── postcss.config.js           # PostCSS config
├── next.config.ts              # Next.js config
└── .eslintrc.js                # ESLint config
```

## Auth Flow

1. **Login** (`/login`): email + password. If user belongs to multiple agencies, server returns 400 with `available_agencies` list; user selects one and resubmits.
2. **Auth tokens**: stored in HttpOnly cookies (`access_token`, `refresh_token`).
3. **401 handling**: `api-client.ts` auto-calls `/auth/refresh` on 401 (except for login/register/logout/refresh) and retries the original request once.
4. **Dashboard** (`/dashboard`): fetches `/auth/me`, `/agencies/current`, `/workspaces`. On 401, redirects to `/login`.

## Verification Status

| Check | Status |
|---|---|
| `npm run type-check` (`tsc --noEmit`) | ✅ GitHub Actions PASS (2026-11-09) |
| `npm run lint` (`eslint src --ext .ts,.tsx`) | ✅ GitHub Actions PASS (2026-11-09) |
| `npm run build` (`next build`) | CI-enforced on every frontend change |
| Frontend test suite | ❌ NOT IMPLEMENTED — Phase 1 has no frontend tests |

See `/STATE.md` for the full verification status with strict labels.

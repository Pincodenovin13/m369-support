# Frontend + Backend Parallel Delivery Plan

## Goal

Build the Agency Portal and Super Admin Console in parallel with backend hardening without allowing the UI to invent API behavior or weaken tenant authorization. The backend remains the source of truth for identity, agency scope, RBAC, billing, and data validation.

## Current repository baseline (2026-11-09)

- Frontend: `apps/web/`, Next.js 15.5.29 (security-maintenance line), React 19.0.1, TypeScript 5.7, Tailwind CSS 3.4.17, TanStack Query 5.65.1.
- Backend: `apps/api/`, FastAPI, PostgreSQL, Alembic, signed tenant context and RLS migration 0019.
- Existing UI routes: `/`, `/login`, `/register`, `/dashboard`, `/contacts`, `/conversations`, `/conversations/[id]`, `/teams`, `/channels`, `/canned-responses`, `/kb`.
- Existing backend routers also expose Super Admin auth, agencies, plans, subscriptions, payments, settings, notes, and audit endpoints. A complete Super Admin UI is not yet present.
- `.github/workflows/web-ci.yml` now runs lockfile reconciliation, `npm ci`, dependency audit, TypeScript type-check, ESLint, and a production Next.js build on frontend changes.
- `.github/workflows/refresh-web-lockfile.yml` regenerates and commits the dependency lockfile after pinned manifest changes; it uses a branch-restricted workflow token and does not run for pull requests.

## Parallel workstreams

### Workstream A — Backend contract and security

1. Keep tenant isolation, signed context, database privileges, auth, and Super Admin separation as hard gates.
2. Document each endpoint's method, path, request schema, response schema, pagination, error codes, authentication requirement, and required role.
3. Treat the backend OpenAPI schema and Pydantic models as authoritative. Do not silently change API response shapes to suit a page.
4. Any API contract change must include backend tests and a coordinated frontend type/client update in the same pull request or a clearly linked pair of commits.
5. Keep Super Admin routes and credentials separate from agency-user API client state and cookies.

### Workstream B — Frontend product delivery

1. Stabilize shared foundations first: typed API client, session state, route protection, error/loading/empty states, responsive shell, accessible components, and design tokens.
2. Complete the agency workspace UI in vertical slices: inbox/conversation details, contacts, teams/members, channels, canned replies, knowledge base, workspace/agency settings, and billing views.
3. Build the Super Admin Console as a separate protected application area with separate auth/session handling and explicit permission checks. Never infer Super Admin access from agency membership.
4. Use mobile-first responsive layouts; test narrow mobile, tablet, laptop, and desktop breakpoints.
5. Add component/unit tests and browser-level critical-path tests before declaring a UI slice complete.


## Frontend foundation CI evidence — 2026-11-09

- Tested commit: `a6e3f13eaee2b3c0029accbe43e6fe108e76669e`
- Workflow: [Web frontend CI](https://github.com/Pincodenovin13/m369-support/actions/runs/42615796288)
- Result: **success** — dependency install, dependency audit, TypeScript, ESLint, and production build all passed.
- Dependency audit: **0 vulnerabilities** after updating the pinned manifest and regenerating the lockfile.
- Lockfile commit: `cb9a74bd95f5` (`chore(web): refresh dependency lockfile`).
- Verified stack: Next.js 15.5.29, React 19.0.1, PostCSS 8.5.32, Node.js 20.20.2 in CI.
- The current frontend still has no browser-level end-to-end test suite. The production build passing does not prove every user workflow works against a deployed API.

## Integration defects found and corrected in the first frontend slice

The first backend/frontend contract review found real mismatches. These were corrected in the shared API client and the affected pages:

- Contacts now sends `search`, matching the FastAPI query parameter (instead of `q`).
- Teams now loads the agency's workspaces and requires an explicit selected workspace for creation. It no longer derives a workspace from `teams[0]`, so the zero-team case is supported. Member-fetch failures are shown instead of silently presented as zero members.
- Messages now lists through `GET /messages?conversation_id=...` and sends `content` / `is_internal`; the page reads `content`, `sender_user_id`, and `is_internal` according to the backend response schema.
- Canned Responses now uses backend fields `shortcut`, `content`, and `created_at` rather than nonexistent `title`, `body`, and `updated_at`.
- Knowledge Base now uses the backend article response fields and displays `created_at`; it does not expect nonexistent `content_html` or `updated_at`.

Remaining integration work:

- Generate frontend API types from the backend OpenAPI schema and add a CI drift check. Manual TypeScript interfaces can drift again if not checked automatically.
- Knowledge Base currently displays Markdown as plain text. Keep this safe behavior until a renderer is added with raw HTML disabled and URL sanitization; never inject untrusted HTML.
- The agency portal still needs create/edit flows and permission-aware UI for several resource types. The current slice is not a feature-complete product.

## Quality gates

A frontend feature is not complete until all applicable checks pass:

- `npm ci`
- `npm run type-check`
- `npm run lint`
- `npm run build`
- automated tests for loading, empty, error, permission-denied, and successful states
- backend integration tests for any changed API contract
- manual responsive review at mobile/tablet/desktop sizes
- no tenant identifiers trusted from client-controlled data; the backend must derive tenant scope from authenticated signed context
- no secret, access token, refresh token, or Super Admin credential stored in browser localStorage/sessionStorage

## Delivery sequence

1. **Foundation gate:** make frontend CI green and fix configuration defects before broad UI work.
2. **Contract gate:** produce a machine-checkable API schema and detect frontend/backend drift.
3. **Agency portal slices:** finish each screen end-to-end against tested backend endpoints.
4. **Super Admin slice:** separate login/session, dashboard, agency management, plans/subscriptions, payments, settings, notes, and audit views.
5. **Release gate:** run backend PostgreSQL security suite and frontend CI together; deploy only when both are green.

## Branch and change safety

- Work on `refactor/repository-structure-unification` until a reviewed branch/PR strategy is adopted.
- Do not delete branches, rewrite history, or merge unrelated work to speed delivery.
- Keep each feature scoped and independently reviewable. Do not bundle broad folder moves with API or security changes.
- CI evidence must identify the exact commit SHA. A previous passing commit does not certify later code.

## Completion rule

A page being visible is not completion. It must use the real API contract, enforce the correct role and tenant scope server-side, handle failure states, work responsively, and pass automated checks. Production readiness additionally requires deployment verification and operational monitoring.

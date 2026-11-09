# Frontend + Backend Parallel Delivery Plan

## Goal

Build the Agency Portal and Super Admin Console in parallel with backend hardening without allowing the UI to invent API behavior or weaken tenant authorization. The backend remains the source of truth for identity, agency scope, RBAC, billing, and data validation.

## Current repository baseline (2026-11-09)

- Frontend: `apps/web/`, Next.js 15.1.7, React 19, TypeScript 5.7, Tailwind CSS 3.4.17, TanStack Query 5.65.1.
- Backend: `apps/api/`, FastAPI, PostgreSQL, Alembic, signed tenant context and RLS migration 0019.
- Existing UI routes: `/`, `/login`, `/register`, `/dashboard`, `/contacts`, `/conversations`, `/conversations/[id]`, `/teams`, `/channels`, `/canned-responses`, `/kb`.
- Existing backend routers also expose Super Admin auth, agencies, plans, subscriptions, payments, settings, notes, and audit endpoints. A complete Super Admin UI is not yet present.
- Frontend checks were previously not enforced by CI. `.github/workflows/web-ci.yml` now runs `npm ci`, TypeScript type-check, ESLint, and a production Next.js build on frontend changes.

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

## Known integration risks to resolve before feature expansion

- `apps/web/src/app/contacts/page.tsx` sends query parameter `q`; verify backend expects `search` or `q`, then standardize both sides with a contract test.
- `apps/web/src/app/teams/page.tsx` derives the workspace for team creation from `teams[0]`. This fails when the agency has zero teams. Use an explicit selected/current workspace from the workspace API instead.
- The same teams page catches member-list failures and displays an empty member list. Show a visible partial-load error instead of masking authorization or network failures.
- Knowledge Base rendering currently displays Markdown as plain text. Do not inject untrusted HTML. Adopt a safe Markdown renderer with raw HTML disabled and URL sanitization, or return trusted sanitized HTML from the backend under a documented policy.
- `apps/web/src/lib/api-client.ts` defines frontend types manually. Add automated schema drift checking from the backend OpenAPI document before relying on these types for new features.
- Review all API routes and client methods together. The presence of a TypeScript method does not prove that its URL, payload, return shape, or permission behavior matches the backend.

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

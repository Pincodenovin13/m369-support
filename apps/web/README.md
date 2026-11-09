# M369 Support Web

**Location:** `apps/web/`  
**Stack:** Next.js 15, React 19, TypeScript and Tailwind CSS.

The web app contains the agency portal and the initial Super Admin console. It is not yet feature-complete; consult root `STATE.md` for current implementation status.

## Local development

```bash
cd apps/web
npm ci
npm run dev
```

Production checks:

```bash
npm ci
npm audit --audit-level=low
npm run type-check
npm run lint
npm run build
```

## Structure

- `src/app/`: App Router pages.
- `src/components/`: shared UI components and shells.
- `src/hooks/`: authentication and state hooks.
- `src/lib/`: API clients and utilities.
- `package.json` and `package-lock.json`: dependency manifest and exact lock.

CI uses `npm ci` and validates the committed lockfile. There is no automatic lockfile rewrite or `npm audit fix` push workflow. Dependency updates must be deliberate, reviewed, tested and committed together with the matching lockfile.

## API contract

Do not invent frontend payloads or mock production records. Align screens to the backend route/schema or a generated OpenAPI contract. Add contract tests and frontend browser tests as those flows are implemented.

## Verification

See `docs/development/testing.md` and root `STATE.md`. Frontend type-check, lint and build passing does not mean all screens or user journeys are complete.

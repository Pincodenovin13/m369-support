# M369 Support API

**Location:** `apps/api/`  
**Runtime:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic 2, psycopg 3.

This is the active FastAPI backend. The authoritative migration chain is `0001_initial` through `0020_payment_raw_amount_precision` (20 linear migrations). Do not use the historical migration count or schema description copied into older recovery artifacts.

## Source layout

- `app/api/v1/`: HTTP routers; `super_admin/` contains platform-admin routes.
- `app/core/`: runtime configuration.
- `app/db/`: SQLAlchemy engines and DB sessions, including separated Super Admin paths.
- `app/dependencies/`: authentication, authorization and request dependencies.
- `app/middleware/`: request middleware.
- `app/models/`: ORM models.
- `app/schemas/`: request/response schemas.
- `app/security/`: JWT, password and security primitives.
- `app/services/`: domain services.
- `app/tenancy/`: signed tenant-context primitives.
- `migrations/versions/`: append-only Alembic history.
- `tests/unit/` and `tests/integration/`: test suite.
- `scripts/`: explicit operational/provisioning commands.

## Local development

From repository root:

```bash
cp .env.example .env
# Set unique local-only secrets/passwords in .env.
docker compose up -d
```

Or run manually after PostgreSQL and Redis are available:

```bash
cd apps/api
pip install -r requirements-dev.txt
alembic upgrade head
pytest -q tests
```

Do not point local development or tests at a production database.

## Security boundary

Tenant access depends on signed tenant context and PostgreSQL RLS. Do not introduce a tenant-owned table without the catalog-driven RLS guard, FORCE RLS, signed USING/WITH CHECK policy, tenant-scoped foreign keys where applicable, and adversarial cross-tenant tests.

Super Admin management uses a separate privileged database path. Its BYPASSRLS capability is highly sensitive and must not be exposed to tenant-facing routes or background tasks by default.

## Current verification

See root `STATE.md` and `docs/development/testing.md` for exact workflow IDs, commit SHAs, results and outstanding release gates. CI success is not production certification.

## Deployment

Production VPS, domain, DNS, TLS, backup, upgrade and rollback instructions are maintained in `docs/deployment/production-operations.md`. Do not deploy until the production security release gates are satisfied.

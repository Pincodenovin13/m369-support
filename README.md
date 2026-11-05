# M369 Support

> Independent, commercial, multi-tenant SaaS customer support platform.
> Built from scratch — not a fork of any existing product.

## Project Status

**Phase 1 (Foundation + Multi-Tenancy)** — see `docs/architecture/phase-1.md`.

## Repository Layout

```
m369-support/
├── apps/
│   ├── api/         FastAPI backend (Python 3.12)
│   ├── web/         Next.js 15 frontend (agency portal surface)
│   └── widget/      Embeddable widget (scaffolded, future phase)
├── packages/
│   └── shared/      Shared TypeScript types (future)
├── infrastructure/  Docker, database, deployment configs
├── docs/            Architecture, security, database docs
├── tests/           Cross-app integration, security, e2e tests
└── scripts/         Operational scripts
```

## Quick Start (Local Development)

### Prerequisites

- Docker 24+ and Docker Compose 2.20+
- OR: Python 3.12+, Node.js 20 LTS+, PostgreSQL 16+, Redis 7+

### Docker Compose (recommended)

```bash
cp .env.example .env
docker compose up -d
docker compose exec api alembic upgrade head
```

- Backend: http://localhost:8000
- Frontend: http://localhost:3000

## Documentation

- Architecture: `docs/architecture/overview.md`
- Phase 1 scope: `docs/architecture/phase-1.md`
- Tenant isolation: `docs/security/tenant-isolation.md`
- Authentication: `docs/security/authentication.md`
- Database schema: `docs/database/schema.md`
- Local setup: `docs/development/local-setup.md`
- Environment variables: `docs/development/environment.md`
- Testing: `docs/development/testing.md`

## License

MIT — see `LICENSE`.

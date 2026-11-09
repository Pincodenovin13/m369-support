# M369 Support — Documentation Index

> Last updated: 2026-11-09
> Canonical project state: [STATE.md](../STATE.md)
> Active development branch: `refactor/repository-structure-unification`

The repository-root documents are authoritative. Supplementary documents under `docs/` provide focused architecture, security and development detail. Historical files under `recovery/` are not implementation references.

## Canonical root documents

| Document | Path | Purpose |
|---|---|---|
| Project state | [STATE.md](../STATE.md) | Current branch/HEAD, CI evidence, migration head, blockers and risks |
| Repository map | [REPOSITORY_MAP.md](../REPOSITORY_MAP.md) | File/folder ownership and placement |
| Contributing | [CONTRIBUTING.md](../CONTRIBUTING.md) | Branching, commits, PR, migrations, security review and Rule 13 |
| Project overview | [README.md](../README.md) | Product overview, setup and quick start |

## Architecture

| Document | Path | Purpose |
|---|---|---|
| Architecture overview | [overview.md](architecture/overview.md) | System layers, tenant hierarchy and security boundaries |
| Phase 1 scope | [phase-1.md](architecture/phase-1.md) | Implemented, deferred and blocked Phase 1 scope |
| Future capabilities roadmap | [future-capabilities-roadmap.md](architecture/future-capabilities-roadmap.md) | WhatsApp/Telegram/Instagram/Facebook, monthly export, escalation, AI controls, retention and PWA; planning only |

## Security

| Document | Path | Purpose |
|---|---|---|
| Security index | [security/README.md](security/README.md) | Security architecture index |
| Security closure evidence | [phase1-security-closure-2026-11-09.md](security/phase1-security-closure-2026-11-09.md) | PostgreSQL CI evidence and production limitations |
| Tenant isolation | [tenant-isolation.md](security/tenant-isolation.md) | Signed tenant context, RLS, roles and composite FKs |
| Authentication | [authentication.md](security/authentication.md) | JWT, Argon2id, MFA and authorization |
| Agency session revocation | [agency-session-revocation.md](security/agency-session-revocation.md) | Server-side session revocation and refresh rotation |

## Database

| Document | Path | Purpose |
|---|---|---|
| Schema | [schema.md](database/schema.md) | Tables, constraints and migration details |

## Development

| Document | Path | Purpose |
|---|---|---|
| Repository integrity audit | [repository-integrity-audit-2026-11-09.md](repository-integrity-audit-2026-11-09.md) | Branch/tree/docs/CI consistency audit |
| Testing | [testing.md](development/testing.md) | Exact CI evidence, commands and test gaps |
| Frontend parallel delivery | [frontend-parallel-delivery.md](development/frontend-parallel-delivery.md) | API contract and frontend delivery sequence |
| Local setup | [local-setup.md](development/local-setup.md) | Developer setup |
| Environment variables | [environment.md](development/environment.md) | Environment configuration |

## Historical archive

`recovery/workspace-preservation/` is preserved for provenance only. It contains superseded artifacts and legacy references. Do not use it as source code, architecture guidance or current status evidence.

## Documentation rules

1. Update root canonical documents when branch, state, structure, security or workflow facts change.
2. Update the relevant deep-dive document and this index when adding/removing documentation.
3. Do not rewrite historical artifacts as if they were current.
4. Every claim about test success must identify the exact workflow, commit and command.
5. A green CI run is not production security certification.

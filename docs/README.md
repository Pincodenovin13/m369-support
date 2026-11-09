# M369 Support — Documentation Index

> **Last updated:** 2026-11-08
> **Companion documents:** [`/STATE.md`](../STATE.md) · [`/REPOSITORY_MAP.md`](../REPOSITORY_MAP.md) · [`/CONTRIBUTING.md`](../CONTRIBUTING.md)

This is the index for all M369 Support documentation. The **canonical** project documents live at the repository root; the files in this `docs/` folder are supplementary deep-dives.

---

## Canonical Documents (Repository Root)

These are the authoritative sources of truth. When in doubt, consult these first.

| Document | Path | Purpose |
|---|---|---|
| **STATE.md** | [`/STATE.md`](../STATE.md) | Current project state — Git SHAs, migration head, test results with strict verification labels, environment limitations, risks |
| **REPOSITORY_MAP.md** | [`/REPOSITORY_MAP.md`](../REPOSITORY_MAP.md) | Authoritative file/folder responsibility map |
| **CONTRIBUTING.md** | [`/CONTRIBUTING.md`](../CONTRIBUTING.md) | Permanent development rules: branch naming, commit conventions, PR rules, file placement, migration rules, security review, Rule 13 (Artifact Disclosure & Delivery) |
| **README.md** | [`/README.md`](../README.md) | Project overview + quick start + links to canonical docs |

---

## Supplementary Documentation (`docs/`)

### Architecture

| Future Capabilities Roadmap | [`docs/architecture/future-capabilities-roadmap.md`](./architecture/future-capabilities-roadmap.md) | Planned integrations, monthly export, escalation, AI controls, retention and PWA; planning only |

| Document | Path | Description |
|---|---|---|
| Architecture overview | [`docs/architecture/overview.md`](./architecture/overview.md) | ASCII system diagram, tenant hierarchy, design principles |
| Phase 1 scope | [`docs/architecture/phase-1.md`](./architecture/phase-1.md) | What's implemented, what's deferred, what's blocked |

### Security

| Phase 1 Security Closure | [`docs/security/phase1-security-closure-2026-11-09.md`](./security/phase1-security-closure-2026-11-09.md) | Latest PostgreSQL CI evidence and production security limitations |

| Document | Path | Description |
|---|---|---|
| Security README | [`docs/security/README.md`](./security/README.md) | Security documentation index |
| Authentication | [`docs/security/authentication.md`](./security/authentication.md) | JWT, Argon2id, token_version, MFA, roles, lockout |
| Tenant isolation | [`docs/security/tenant-isolation.md`](./security/tenant-isolation.md) | RLS policies, tenant context, composite FKs |
| Session revocation | [`docs/security/agency-session-revocation.md`](./security/agency-session-revocation.md) | How `token_version` enables server-side logout and refresh-token rotation |

### Database

| Document | Path | Description |
|---|---|---|
| Database schema | [`docs/database/schema.md`](./database/schema.md) | Tables, columns, constraints, migration head |

### Development

| Document | Path | Description |
|---|---|---|
| Local setup | [`docs/development/local-setup.md`](./development/local-setup.md) | Step-by-step local dev environment setup |
| Environment variables | [`docs/development/environment.md`](./development/environment.md) | All env vars with descriptions |
| Testing | [`docs/development/testing.md`](./development/testing.md) | Test architecture, how to run, what's covered, verification status |

---

## Historical Archive (NOT AUTHORITATIVE)

The `recovery/workspace-preservation/` folder contains historical artifacts from Z.ai workspace sessions. These are **NOT** current documentation and must not be used as implementation references. See [`recovery/workspace-preservation/README.md`](../recovery/workspace-preservation/README.md) for the archive notice.

---

## How to Update Documentation

1. **Canonical docs** (root): update when the project state, structure, or rules change. These are the source of truth.
2. **Supplementary docs** (`docs/`): update when a deep-dive topic changes. Cross-reference the canonical docs.
3. **Historical archive** (`recovery/`): do NOT update. Add new historical artifacts with a clear HISTORICAL/ARCHIVED notice.
4. **Per Rule 13** (in `CONTRIBUTING.md`): every documentation change must be disclosed in the task report's artifact disclosure table.

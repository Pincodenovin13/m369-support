# Production Operations Guide — M369 Support

Status: planning and learning guide, not deployment approval. Do not onboard paying customers until security release gates in STATE.md are closed.

## 1. What must be purchased

| Item | Purpose | Low-cost starting point |
|---|---|---|
| Domain | Public business address | One domain from a reputable registrar |
| VPS | Linux server with public IP | One appropriately sized VPS, selected after load estimates |
| DNS | Maps domain to VPS | Registrar DNS or a DNS provider; usually no extra hosting fee |
| HTTPS | Encrypts browser/API traffic | Automated Let's Encrypt certificate; normally no certificate purchase |
| PostgreSQL | Main application database | Same VPS initially, isolated container and private network |
| Redis | Rate-limit/cache service if required | Same VPS initially; no separate paid Redis by default |
| Backups | Disaster recovery | Encrypted off-server storage and tested restores |
| Email | Verification, reset and notifications | Add a transactional provider when those flows are ready |
| Object storage | Attachments and exports | Add only when required; private bucket and lifecycle controls |

A domain is not a server. A VPS is not a domain. This Docker-based application does not initially require traditional shared hosting.

## 2. Cost-conscious first deployment

Initial target: one VPS, Docker Compose, one domain, no Kubernetes, no managed database, no paid Redis cluster, and no separate worker VPS.

Run reverse proxy/TLS, Next.js, FastAPI, PostgreSQL and required Redis as separate containers on the same VPS. Migration and provisioning run as controlled one-shot tasks, not public services.

Export generation, monthly scheduling and webhook retries may need background processing. Do not buy another server for this at launch. First evaluate a resource-limited worker process/container on the same VPS. It must establish signed tenant context and must never use the Super Admin BYPASSRLS database connection. Apply concurrency, time, memory, file-size and per-agency quotas. Heavy exports must not run inside HTTP requests or starve the API/database. A separate worker host is considered only after measured load justifies it.

A single VPS is economical but is not high availability: a host failure can take the service offline until restored.

## 3. Select a VPS based on evidence

Before purchase, estimate agencies, seats, daily conversations/messages, attachment volume, data retention, database growth and target-market latency. Compare provider region, privacy/data-processing terms, CPU, RAM, SSD performance, traffic, snapshots, recovery support and permitted payment methods. Use load tests and PostgreSQL metrics to choose capacity; do not buy solely on the lowest advertised price. No exact server size or vendor is approved by this draft.

## 4. Domain, DNS, HTTPS and host security

1. Register the domain in a business-controlled account; enable MFA and registrar lock.
2. Rent a VPS in an appropriate region and record its public IP.
3. Point app/API DNS records to the VPS; exact records depend on the final reverse-proxy setup.
4. Expose only required public ports (normally 80/443 and tightly restricted SSH). PostgreSQL and Redis must never be public.
5. Configure reverse proxy, automated TLS renewal, security headers, trusted proxy settings and strict API CORS/origin rules.
6. Restrict SSH using keys; disable password login where supported. Never share private keys.

## 5. Production secrets

Generate unique high-entropy production secrets. Never reuse test/CI values. Keep production environment files outside Git and web roots, with restrictive file permissions. Keep application, Super Admin auth, privileged management and migration credentials separated as designed. Tenant-facing API and ordinary background jobs must not receive BYPASSRLS access. Redact secrets from logs and responses. Document rotation and recovery. Never paste secrets into GitHub, chat or tickets.

## 6. Backup and recovery

Automate encrypted PostgreSQL backups to storage independent of the VPS. Define retention, cost alerts, checksums, recovery point objective and recovery time objective. Perform periodic restore drills in an isolated environment. Verify that backups can be decrypted and restored. Backups of application data and recovery of encryption keys/configuration must be planned separately and securely. An agency downloading its own export does not replace M369 disaster-recovery backups.

## 7. Safe update procedure

1. Review the exact release commit/tag and its diff.
2. Confirm CI passed for that exact commit.
3. Review every migration; published migrations are append-only.
4. Take and verify a fresh database backup before risky releases/migrations.
5. Deploy pinned release artifacts; do not deploy arbitrary latest tags.
6. Run migrations as a controlled one-shot step with migration credentials.
7. Deploy API and web, then run health/readiness and smoke tests.
8. Observe logs, errors, connections, disk, memory and CPU.
9. If checks fail, stop rollout and follow rollback/recovery instructions.

Rolling back application code does not automatically reverse a database migration. Prefer backward-compatible expand/migrate/contract migrations. Destructive schema changes require a separate data-recovery plan.

## 8. Keep recurring costs low

Start with one VPS; avoid Kubernetes, multiple nodes and managed premium services until measured traffic or uptime needs justify them. Use log rotation, database connection limits, bounded worker concurrency, export quotas, storage alerts and monthly invoice reviews. Dependency updates must be deliberate and reviewed. The automatic lockfile mutation/push workflow has been removed; web CI uses npm ci against the committed lockfile.

## 9. Super Admin management goals

The console should eventually manage agencies, memberships, seat limits, plans, entitlements, prices, subscriptions, payment reconciliation, channel status, export quotas/jobs, AI quotas/usage, maintenance notices and audit events. All actions require role checks and audit logs. High-risk actions require re-authentication/MFA, reason capture and sometimes dual approval. Never expose arbitrary SQL, raw secrets, shell access or unrestricted host/file controls in the panel. Super Admin cannot safely replace all infrastructure administration.

## 10. Owner training before launch

We will walk through the selected provider and actual screens: buying/renewing the domain; renting and securing VPS; DNS and HTTPS; secrets and deployment; health/log/resource checks; backups and restore; updates and rollback; and managing agencies/plans/payments/limits from Super Admin. Do not purchase anything based only on this draft. Choose vendor, region and size after security, load and budget reviews.

## 11. Production launch checklist

- [ ] Route-by-route RBAC and object-IDOR review complete.
- [ ] Production PostgreSQL role/grant/RLS inspection complete.
- [ ] Production secrets generated, stored and rotation tested.
- [ ] Redis/rate-limit fail-closed behavior and trusted proxy verified.
- [ ] Upload, webhook, request-size and DoS controls reviewed.
- [ ] HTTPS, firewall, SSH and admin MFA verified.
- [ ] Backup restore drill passed.
- [ ] Migration and rollback/recovery runbook tested.
- [ ] Monitoring, alerts, log rotation and disk thresholds configured.
- [ ] Privacy, terms, retention, data-processing and target-market legal obligations reviewed.
- [ ] Independent security review/penetration test completed before meaningful paid onboarding.

This guide does not claim production security certification.

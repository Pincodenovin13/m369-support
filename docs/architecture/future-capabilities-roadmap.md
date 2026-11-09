# M369 Support — Future Capabilities and Product Architecture Roadmap

**Status:** Accepted as a planning baseline; not an implementation claim.  
**Owner:** Product / Engineering  
**Security rule:** No feature may bypass tenant isolation, authorization, auditability, or the security release gates.

This roadmap preserves customer-feedback-driven requirements while the current engineering track continues to close backend security and API-contract gaps. Pricing examples below are provisional and must not overwrite existing plan seeds or production configuration.

## 1. Product principles

1. Security and tenant isolation take priority over feature speed.
2. Every agency owns and controls access to its own workspace data.
3. Agency-specific configuration, credentials, exports, usage and integrations must be tenant-scoped.
4. Super Admin controls plan definitions, entitlements, limits and prices; frontend code must not hardcode commercial rules.
5. New frontend features consume documented, tested API contracts. No fabricated demo data in production screens.
6. Features are released in small phases with migrations, rollback/recovery planning, tests, CI evidence and audit events.

## 2. Omnichannel integrations

Required channels:
- WhatsApp
- Telegram
- Instagram
- Facebook

Architecture direction:
- A common channel/provider interface with provider-specific adapters.
- Per-agency channel connections and encrypted credentials/tokens.
- Webhook signature/authenticity verification, replay protection, idempotent event ingestion and bounded retries.
- Strict tenant resolution from verified provider connection records; never trust a tenant ID supplied by an inbound webhook payload alone.
- Per-provider permission scopes, token rotation/revocation, health status and reconnect flows.
- Rate limits, payload size limits, secret redaction and audit events.
- Explicit mapping of external identities, conversations, message delivery states and attachments.
- Provider policy/API limitations must be checked before committing to feature promises.

Do not build four isolated implementations that duplicate message ingestion and security logic. First establish the shared channel contract and webhook threat model; then integrate providers incrementally.

## 3. Monthly agency data export

### Product intent

Give each agency a reliable recurring way to obtain its own data, improve customer trust and support portability. Monthly export is a plan entitlement and commercial differentiator.

### Provisional plan behavior

| Entitlement | Standard plan proposal | Premium plan proposal |
|---|---|---|
| Staff seats | Up to 3 | Up to 6 |
| Price example | 29 USDT per seat / month | About 150 USDT per agency / month |
| Monthly export | Included at no extra charge | Available as a separately priced monthly add-on |
| Other features | Core feature set | Expanded feature set |

These are examples from product discussion, not approved prices. The meaning of per-seat versus per-agency billing, billing currency, tax/fees, add-on renewal, failed payment behavior, proration and cancellation must be finalized before implementation. Do not silently alter existing Starter/Growth/Pro/VIP seed values.

### Technical requirements

- Reuse the existing plan/subscription system; model export as a versioned entitlement/add-on, not a second plan catalogue.
- Export job lifecycle: requested, queued, running, completed, failed, expired, cancelled.
- Background worker; no long-running ZIP generation in an HTTP request.
- Tenant-scoped snapshot and signed tenant context in worker execution.
- Permission check for requester, agency and download; prevent cross-tenant job-ID/ZIP access.
- ZIP may contain documented CSV datasets and permitted attachments. Define schema/version and export manifest.
- CSV formula-injection protection, safe filenames, archive path traversal protection and attachment malware/content handling.
- Private encrypted object storage, short-lived download authorization, expiry and deletion policy.
- Idempotency, request quotas, output size limits, audit trail, retries and restore/verification tests.
- Monthly scheduling must use an explicit agency timezone and billing-cycle policy; missed runs need safe retry semantics.
- Exporting data does not itself delete it from the live database. Retention/deletion is a separate, legally reviewed policy. Never promise that M369 has no further data responsibility merely because an export was downloaded.

## 4. Human escalation

- Add an explicit conversation state transition for AI-to-human escalation.
- Reuse existing conversation assignment fields where appropriate; do not duplicate them.
- Persist immutable escalation events and reason/source metadata.
- Atomically mute AI and assign/route the conversation.
- Check agency membership, operator permissions, workload/availability and concurrent assignment races.
- Notify the appropriate operator/team through a reliable event/outbox path.
- AI unmute requires explicit permission, valid conversation state and audit event.
- Add the customer-facing “Talk to a human” action only after the backend contract is stable.

## 5. AI usage and quota control

- Append-only usage ledger with agency, provider, model, feature, request/idempotency identity, units and cost metadata.
- Central usage service; decorators may assist but must not be the enforcement boundary.
- Atomic quota reservation before provider invocation, followed by settlement/refund for actual usage.
- Prevent parallel requests from overspending an agency quota.
- Define modes such as full, hybrid and suggestions-only as explicit server-side policy.
- Suggestions-only must have a documented cost model; cached/rule-based suggestions are not equivalent to a live model call.
- Usage dashboard reads authoritative backend totals and limits.
- AI credit top-ups require idempotent payment reconciliation and auditable ledger entries.

## 6. BYOAI (agency-provided model credentials)

- Provider interface for response generation, suggestions, summarization, sentiment analysis and health checks.
- Start with providers justified by customer demand; add custom endpoints only with strict outbound network controls.
- Encrypt credentials with envelope/KMS-style key management, redact logs, restrict reads, support rotation and deletion.
- Never return secrets in API responses or expose them to browser code.
- Defend custom provider URLs against SSRF, private/link-local metadata access, DNS rebinding and redirect abuse.
- Add timeouts, bounded retries, circuit breakers and provider-specific rate limits.
- Self-hosted models are deferred until infrastructure economics justify them.

## 7. Database growth, archiving and retention

- Collect table growth, write volume, query latency and query plans before partitioning.
- Consider BRIN only for large append-heavy tables whose physical order correlates with the indexed timestamp; verify with real query plans.
- Do not partition core relational tables casually: account for primary/unique keys, composite tenant foreign keys, RLS and query patterns.
- Any object-storage archive needs encryption, checksum verification, idempotent job state, restore tests and deletion only after verified archival.
- Define platform retention floors and agency-configurable options, with legal holds and separate retention for messages, attachments, audit, billing and payment records.
- Per-agency deletion must be tenant-scoped and batched; dropping a shared monthly partition is not a substitute for per-agency retention.

## 8. Mobile, responsive and PWA

- Mobile-first responsive design across narrow phones, tablets, laptops and wide desktops.
- Use flexible breakpoints and layouts, not rigid device-only assumptions.
- Touch targets around 44 CSS px where practical; account for safe areas and virtual keyboard viewport changes.
- Provide accessible loading, error, empty and success states.
- PWA installation can follow once authentication, session expiry and cache policy are defined.
- Do not cache private conversations or attachments by default. Offline writes require an explicit sync, conflict-resolution and threat model.

## 9. Delivery sequence and security gates

### Gate 0 — Current track: security closure
- Keep the PostgreSQL/RLS suite green without weakening tests.
- Complete route-by-route authorization and object-IDOR matrix.
- Verify role grants, migration behavior, Super Admin auth/MFA/revocation and rate limits.
- Inspect CI warnings and workflow coverage.
- Record production-only controls that cannot be proven in CI.
- Do not claim production security certification without production evidence and independent review.

### Gate 1 — API contracts and core support UI
- Document OpenAPI schemas and generate or validate frontend types.
- Fix known frontend/backend mismatches before adding screens.
- Continue dashboard, inbox, conversation detail, contacts, teams and knowledge base against real API data.
- Add contract tests and CI drift detection.

### Gate 2 — Channel foundation and integrations
- Define common channel model, provider connection lifecycle, webhook security and message normalization.
- Add providers incrementally: Telegram/WhatsApp/Instagram/Facebook, based on API access and policy feasibility.
- Each provider requires tenant-isolation, webhook replay, credential secrecy and permission tests.

### Gate 3 — Human escalation
- Backend state machine, atomic assignment, audit/outbox and hostile concurrency tests.
- Then customer widget and operator UI.

### Gate 4 — Export entitlement and monthly export
- Finalize plan entitlements and premium add-on billing.
- Implement export jobs/worker/storage/download lifecycle and cross-tenant ZIP attack tests.
- Add monthly scheduling, export notifications, expiry and documented export format.

### Gate 5 — AI usage control and BYOAI
- Quota ledger and atomic reservation/settlement before enabling paid AI usage.
- Then provider credentials and provider adapters.

### Gate 6 — Retention, archive, database optimization and PWA
- Implement only against measured growth, approved retention/legal policy and restore evidence.
- Introduce PWA caching only after security review.

## 10. Definition of done for every capability

A capability is not complete until it has:
- documented API and data ownership;
- migration and rollback/recovery analysis;
- tenant-scoped authorization on every read/write/download path;
- adversarial cross-tenant tests, including IDOR and concurrency where relevant;
- secret, rate-limit, replay and abuse controls as applicable;
- auditability and operational failure handling;
- frontend contract tests and responsive/accessibility checks where UI exists;
- successful CI evidence tied to an exact commit;
- documented production-only verification still required.

**Non-negotiable:** no feature may be used to bypass or postpone the security release gates.

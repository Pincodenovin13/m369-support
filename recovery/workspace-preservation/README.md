# Recovery — Workspace Preservation (HISTORICAL ARCHIVE)

> ⚠️ **ARCHIVED — HISTORICAL — NOT AUTHORITATIVE**
>
> This folder contains **historical artifacts** from Z.ai workspace sessions
> (Nov 2-8, 2026). These files are preserved for reference only and are
> **NOT the current source of truth** for the M369 Support project.
>
> - For current project state: see [`/STATE.md`](../../STATE.md)
> - For current architecture: see [`/ARCHITECTURE.md`](../../ARCHITECTURE.md) (when created)
> - For current file map: see [`/REPOSITORY_MAP.md`](../../REPOSITORY_MAP.md)
> - For current development rules: see [`/CONTRIBUTING.md`](../../CONTRIBUTING.md)
>
> **Do NOT use files in this folder as implementation references.** They may
> contain outdated architecture, superseded designs, or references to
> external products that must never be used as M369 sources.

---

## Branch provenance

| Field | Value |
|---|---|
| Original branch | `recovery/zai-workspace-2026-11-08` |
| Parent branch | `phase-1/security-closure-b1-4` (commit `ab046a2`) |
| Created | 2026-11-08 (UTC+8) |
| Rule 13 commit | `79b4311` (cherry-pick of `ab62f29` from lost `docs/rule-13-artifact-disclosure` branch) |
| Preservation folder commit | `2518c85` |
| Missing-patches fix commit | `1c32941` |

## Structure (16 files total)

```
recovery/workspace-preservation/
├── README.md                                  ← THIS FILE (historical archive notice)
├── patches/                                   ← 5 HISTORICAL patch files
│   ├── 0001-Stage-2-...patch                   (commit 853b557 — already on foundation)
│   ├── 0002-Stage-3-...patch                   (commit 70e026f — already on foundation)
│   ├── 0003-Stage-4-...patch                   (commit 0b3139a — already on foundation)
│   ├── m369-multitenancy-foundation.patch      (Nov 3 foundation patch — historical)
│   └── m369-multitenancy-foundation.patch.sha256
├── reports/                                   ← 2 HISTORICAL snapshot reports
│   ├── DELIVERY_README.md                      (Nov 8 delivery instructions — snapshot)
│   └── INVENTORY.md                            (Nov 8 inventory — snapshot)
├── design/                                    ← 4 HISTORICAL design docs
│   ├── M369_Architecture_Proposal.md            (Nov 4 — superseded)
│   ├── M369_HANDOFF.md                         (Nov 2 — ⚠️ LEGACY: contains OpenLivery material)
│   ├── M369_Multitenancy_Foundation_Report.md  (Nov 3 — ⚠️ LEGACY: contains OpenLivery material)
│   └── M369_Phase1_Technical_Design.md         (Nov 5 — superseded)
└── test-output/                               ← 4 HISTORICAL test outputs
    ├── phase-1-test-output.txt                 (Nov 5 — Z.ai-reported, not independently verified)
    ├── phase-1-remediation-test-output.txt     (Nov 5 — Z.ai-reported)
    ├── test_env_metadata.txt                   (Nov 3 — sandbox environment snapshot)
    └── test_tenant_foundation_raw_output.txt   (Nov 3 — raw test output)
```

## File-by-file historical status

### `patches/` — HISTORICAL, DO NOT REAPPLY

| File | Status | Reason |
|---|---|---|
| `0001-Stage-2-API-business-logic-RBAC-migration-0007-ACL-f.patch` | ✅ Already integrated | Commit `853b557` is on `origin/phase-1/foundation` and `origin/phase-1/security-closure-b1-4`. Reapplying would cause conflicts. |
| `0002-Stage-3-Super-Admin-backend-subscription-billing-fou.patch` | ✅ Already integrated | Commit `70e026f` is on foundation and B.1.4. |
| `0003-Stage-4-integrated-testing-final-security-audit.patch` | ✅ Already integrated | Commit `0b3139a` is the foundation HEAD. |
| `m369-multitenancy-foundation.patch` | ✅ Superseded | Nov 3 foundation work; the actual implementation lives in `apps/api/app/`. Preserved for history only. |
| `m369-multitenancy-foundation.patch.sha256` | ✅ Manifest | SHA-256 for the above patch. |

**Do NOT reapply any of these patches.** They are preserved as historical evidence of the development sequence, not as pending work.

### `reports/` — HISTORICAL SNAPSHOTS, NOT CURRENT STATUS

| File | Status | Reason |
|---|---|---|
| `DELIVERY_README.md` | 📸 Snapshot | Nov 8 delivery instructions for the Rule 13 patch. The patch was successfully applied as commit `79b4311` on the `recovery/zai-workspace-2026-11-08` branch. This report is no longer actionable. |
| `INVENTORY.md` | 📸 Snapshot | Nov 8 inventory of Z.ai's workspace artifacts. The counts and SHAs in this report reflect the state at the time of writing, NOT the current repository state. |

### `design/` — HISTORICAL, SOME LEGACY

| File | Status | Reason |
|---|---|---|
| `M369_Architecture_Proposal.md` | 📸 Superseded | Nov 4 early architecture proposal. Superseded by the actual implementation in `apps/api/app/`. |
| `M369_HANDOFF.md` | ⚠️ **LEGACY — OpenLivery material** | Nov 2 handoff document. **Contains references to OpenLivery**, an external product. Per M369 project rules: "Do not use OpenLivery as a source, template, or architectural reference. M369 is an independent greenfield product." This file must NEVER be used as an M369 implementation source. Preserved for historical audit only. |
| `M369_Multitenancy_Foundation_Report.md` | ⚠️ **LEGACY — OpenLivery material** | Nov 3 foundation report. **Contains references to OpenLivery.** Same prohibition as `M369_HANDOFF.md`. |
| `M369_Phase1_Technical_Design.md` | 📸 Superseded | Nov 5 technical design. Superseded by actual implementation. |

### `test-output/` — HISTORICAL EVIDENCE, NOT PROOF OF CURRENT EXECUTION

| File | Status | Reason |
|---|---|---|
| `phase-1-test-output.txt` | 📸 Z.ai-reported | Nov 5 test output. **Z.ai-reported, not independently verified.** Does NOT prove current test execution. |
| `phase-1-remediation-test-output.txt` | 📸 Z.ai-reported | Nov 5 remediation test output. Same caveat. |
| `test_env_metadata.txt` | 📸 Snapshot | Nov 3 sandbox environment metadata. |
| `test_tenant_foundation_raw_output.txt` | 📸 Z.ai-reported | Nov 3 raw test output. Same caveat. |

**These test outputs are historical evidence of prior Z.ai test runs, NOT proof that tests currently pass.** Current test status is documented in `/STATE.md`.

## What is NOT in this folder (and why)

| Excluded file | Reason |
|---|---|
| `m369-multitenancy-foundation-files/` (6 `.new` draft files) | Superseded draft source files from Nov 3. The actual implementation lives in `apps/api/app/`. Including these `.new` drafts would create duplicate/contradictory code. |
| `m369-phase1-audit.bundle` (git bundle) | Already on GitHub at `origin/phase-1/foundation`. Including a git bundle inside the repo is redundant — the bundle's content IS the foundation branch. |
| `m369-phase1-stage4-source.zip` (source snapshot) | Already on GitHub at `origin/phase-1/foundation`. Including a zip snapshot of source code would duplicate what's already tracked in `apps/`. |
| `_capability_test.zip`, `git_head_at_test.txt`, download `README.md` | Test/scratch files from Nov 2-5 with no lasting value (sandbox capability probe, 41-byte HEAD snapshot, 34-byte placeholder). |
| `patches-rule-13/` subdir (Rule 13 patch) | Already cherry-picked as commit `79b4311` onto the recovery branch. Including the patch file would duplicate the commit's content. |
| `m369-rule-13-patch.tar.gz`, `m369-rule-13-recovery.bundle`, `m369-full-recovery-bundle.tar.gz` | Bundles of the Rule 13 commit, which is already on the recovery branch as commit `79b4311`. Including them would be redundant. |

## Relationship to the Rule 13 commit

The original Rule 13 commit was made on branch `docs/rule-13-artifact-disclosure` at SHA `ab62f29e3997934ab1df8f9ec1c3294b31066c6d`. Due to sandbox recycling, that branch was lost (along with 4 other consolidation commits from the same session). The `recovery/zai-workspace-2026-11-08` branch recreates the Rule 13 work via cherry-pick, producing commit `79b4311` with identical content (same tree SHA `97e5381ab437780f811a5986cdcae9fd6524c194`) but a different commit SHA (because cherry-pick changes the parent).

## Separation from production source code

This `recovery/` folder is **separate from production source code**. It does NOT contain:
- Backend source (lives in `apps/api/app/`)
- Frontend source (lives in `apps/web/src/`)
- Migrations (lives in `apps/api/migrations/versions/`)
- Tests (lives in `apps/api/tests/`)
- Infrastructure (lives in `infrastructure/`)
- Current documentation (lives in `docs/`)

The `recovery/` folder exists solely to preserve historical artifacts that have reference value but no natural home in the main project structure.

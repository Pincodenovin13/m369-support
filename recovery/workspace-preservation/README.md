# Recovery — Workspace Preservation (2026-11-08)

> **Branch:** `recovery/zai-workspace-2026-11-08`
> **Created:** 2026-11-08 (UTC+8)
> **Purpose:** Preserve useful Z.ai workspace artifacts that do not have a natural home in the main project structure.
> **Parent branch:** `phase-1/security-closure-b1-4` (commit `ab046a2`)

## What this folder contains

This folder holds reports, supplementary documentation, useful patches, and other artifacts produced by Z.ai during prior sessions (Nov 2-8, 2026) that have lasting reference value but do not belong in the main `apps/`, `docs/`, `infrastructure/`, or `packages/` trees.

### Structure

```
recovery/workspace-preservation/
├── README.md                          ← THIS FILE
├── patches/                           ← Patch files from prior sessions
│   ├── 0001-Stage-2-API-business-logic-RBAC-migration-0007-ACL-f.patch
│   ├── 0002-Stage-3-Super-Admin-backend-subscription-billing-fou.patch
│   ├── 0003-Stage-4-integrated-testing-final-security-audit.patch
│   ├── m369-multitenancy-foundation.patch
│   └── m369-multitenancy-foundation.patch.sha256
├── reports/                           ← Delivery + inventory reports
│   ├── DELIVERY_README.md
│   └── INVENTORY.md
├── design/                            ← Early architecture/design docs (superseded by current docs/)
│   ├── M369_Architecture_Proposal.md
│   ├── M369_HANDOFF.md
│   ├── M369_Multitenancy_Foundation_Report.md
│   └── M369_Phase1_Technical_Design.md
└── test-output/                      ← Test run outputs from prior sessions
    ├── phase-1-test-output.txt
    ├── phase-1-remediation-test-output.txt
    ├── test_env_metadata.txt
    └── test_tenant_foundation_raw_output.txt
```

## What is NOT in this folder (and why)

| Excluded file | Reason |
|---|---|
| `m369-multitenancy-foundation-files/` (6 `.new` draft files) | Superseded draft source files from Nov 3. The actual implementation lives in `apps/api/app/`. Including these `.new` drafts would create duplicate/contradictory code. |
| `m369-phase1-audit.bundle` (git bundle) | Already on GitHub at `origin/phase-1/foundation`. Including a git bundle inside the repo is redundant — the bundle's content IS the foundation branch. |
| `m369-phase1-stage4-source.zip` (source snapshot) | Already on GitHub at `origin/phase-1/foundation`. Including a zip snapshot of source code would duplicate what's already tracked in `apps/`. |
| `_capability_test.zip`, `git_head_at_test.txt`, download `README.md` | Test/scratch files from Nov 2-5 with no lasting value (sandbox capability probe, 41-byte HEAD snapshot, 34-byte placeholder). |
| `patches-rule-13/` subdir (Rule 13 patch) | Already cherry-picked as commit `79b4311` onto this branch. Including the patch file would duplicate the commit's content. |
| `m369-rule-13-patch.tar.gz`, `m369-rule-13-recovery.bundle`, `m369-full-recovery-bundle.tar.gz` | Bundles of the Rule 13 commit, which is already on this branch as commit `79b4311`. Including them would be redundant. |

## Branch structure

This branch (`recovery/zai-workspace-2026-11-08`) was created from `phase-1/security-closure-b1-4` at commit `ab046a2` (B.1.4 — the latest existing hardening commit on GitHub). It contains:

1. **Commit `79b4311`** — Cherry-pick of the Rule 13 commit (`ab62f29` from the prior session's `docs/rule-13-artifact-disclosure` branch). Adds `CONTRIBUTING.md` to the repository root with Rules 1-13 (Rule 13 = Artifact Disclosure & Delivery mandate).
2. **Commit `<next>`** — Adds this `recovery/workspace-preservation/` folder with the categorized artifacts listed above.

The branch does NOT modify:
- `phase-1/foundation` (the canonical development branch)
- `phase-1/security-closure-b1-4` (the B.1.4 hardening branch)
- Any other historical branch
- Any existing source code, migration, test, or configuration file

## Relationship to the Rule 13 commit

The original Rule 13 commit was made on branch `docs/rule-13-artifact-disclosure` at SHA `ab62f29e3997934ab1df8f9ec1c3294b31066c6d`. Due to sandbox recycling, that branch was lost (along with 4 other consolidation commits from the same session). This branch recreates the Rule 13 work via cherry-pick, producing a new commit `79b4311` with identical content (same tree SHA `97e5381ab437780f811a5986cdcae9fd6524c194`) but a different commit SHA (because cherry-pick changes the parent).

## Verification

- `CONTRIBUTING.md` at repo root: ✅ present (27989 bytes, 487 lines)
- Rule 13 mentioned in `CONTRIBUTING.md`: ✅ 6 occurrences (headings, body, references)
- `recovery/workspace-preservation/` at repo root: ✅ present (5 patches, 2 reports, 4 design docs, 4 test-output files)
- No source code duplicated: ✅ (only reports, patches, and design docs are in the preservation folder)
- No secrets, `.env` files, cache, dependencies, or build artifacts: ✅

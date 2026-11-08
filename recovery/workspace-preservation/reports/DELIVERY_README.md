> ⚠️ **ARCHIVED — HISTORICAL SNAPSHOT — NOT CURRENT STATUS**
>
> This file is a snapshot from Nov 8, 2026. The Rule 13 patch it describes has
> been successfully applied as commit `79b4311` on the
> `recovery/zai-workspace-2026-11-08` branch. This report is no longer
> actionable. For current state, see `/STATE.md`.

# M369 Support — Rule 13 Patch Delivery

> **Delivery date:** 2026-11-08 (UTC+8)
> **Source:** Z.ai execution environment (sandbox without GitHub write credentials)
> **Destination:** Product Owner / Technical Manager (machine with GitHub credentials)
> **Repository:** https://github.com/Pincodenovin13/m369-support
> **Canonical development branch:** `phase-1/foundation` (currently on GitHub at Stage 4 — `0b3139a`)

## What this delivery contains

This delivery contains ONE patch file representing ONE atomic commit that adds **Rule 13 — Artifact Disclosure & Delivery** to the project's `CONTRIBUTING.md`. This rule is mandated by the Product Owner on 2026-11-08.

**Important context (sandbox-recycling disclosure):** A prior session in this same day produced 5 consolidation commits (ARCHITECTURE.md, CONTRIBUTING.md, REPOSITORY_MAP.md, STATE.md updates, .github/ workflow files). Those commits and their patch files were LOST when the Z.ai sandbox was recycled between sessions. This delivery contains only the Rule 13 addition, which is the explicit task requested in the current Product Owner message. The full consolidation work can be redone in a separate task if the Product Owner wishes.

## Files in this delivery

| # | Full filename | Path | Size | SHA-256 | Purpose |
|---|---|---|---|---|---|
| 1 | `001-docs-contributing-add-rule-13-artifact-disclosure.patch` | `/home/z/my-project/download/patches-rule-13/001-docs-contributing-add-rule-13-artifact-disclosure.patch` | 31049 bytes | `cf92679b27e8b5d8e89319c15a0821b4582df4d0f1a53c37b5ada278cf7570a2` | Patch adding Rule 13 to a new CONTRIBUTING.md |
| 2 | `MANIFEST.sha256` | `/home/z/my-project/download/patches-rule-13/MANIFEST.sha256` | 99 bytes | (contains the above hash) | SHA-256 integrity manifest |
| 3 | `m369-rule-13-patch.tar.gz` | `/home/z/my-project/download/m369-rule-13-patch.tar.gz` | 12120 bytes | `44b1716e1cb6fdd34824785745627ca536da2eb70b49a42a998de1fc905162c1` | Single-file bundle of patch + manifest |
| 4 | `DELIVERY_README.md` | `/home/z/my-project/download/DELIVERY_README.md` | (this file) | n/a | Apply instructions + artifact disclosure |

## Patch integrity verification

The patch was verified to apply cleanly via isolated worktree test on 2026-11-08:

```bash
$ git worktree add /tmp/rule-13-test ab046a2
$ cd /tmp/rule-13-test
$ git am /home/z/my-project/download/patches-rule-13/001-docs-contributing-add-rule-13-artifact-disclosure.patch
Applying: docs(contributing): add Rule 13 — Artifact Disclosure & Delivery (Product Owner mandate)
EXIT=0
```

**Important note about commit SHAs:** The patch was originally committed on the `docs/rule-13-artifact-disclosure` branch with SHA `ab62f29e3997934ab1df8f9ec1c3294b31066c6d`. When the Product Owner applies the patch via `git am`, the resulting commit will have a DIFFERENT SHA (e.g., `f9b596482fe57391db90b763be8df3fe973408b9` in the worktree test) because `git am` recomputes the commit SHA based on the committer's identity and timestamp at apply time. **This is expected behavior** — the patch CONTENT (the file changes) is identical (verified: tree SHA `97e5381ab437780f811a5986cdcae9fd6524c194` matches in both the original commit and the worktree-applied commit).

The SHA of the patch file itself (`cf92679b27e8b5d8e89319c15a0821b4582df4d0f1a53c37b5ada278cf7570a2`) is what should be verified — not the resulting commit SHA.

## How to apply (Option A — recommended)

From a machine with GitHub credentials configured for `Pincodenovin13/m369-support`:

```bash
# 1. Clone the repository (or fetch if already cloned)
git clone https://github.com/Pincodenovin13/m369-support.git
cd m369-support
git fetch origin

# 2. Verify B.1.4 is on remote and matches expected SHA
git rev-parse origin/phase-1/security-closure-b1-4
# Expected: ab046a23bf92a3526766a3bc7a027903af034646

# 3. Check out B.1.4 as the starting point for a new docs branch
git checkout -b docs/rule-13-artifact-disclosure origin/phase-1/security-closure-b1-4

# 4. Verify the patch file's SHA-256 matches the manifest
sha256sum /path/to/patches-rule-13/001-docs-contributing-add-rule-13-artifact-disclosure.patch
# Expected: cf92679b27e8b5d8e89319c15a0821b4582df4d0f1a53c37b5ada278cf7570a2

# 5. Apply the patch
git am /path/to/patches-rule-13/001-docs-contributing-add-rule-13-artifact-disclosure.patch
# Expected output:
# Applying: docs(contributing): add Rule 13 — Artifact Disclosure & Delivery (Product Owner mandate)

# 6. Verify the resulting commit (note: SHA will differ from the original ab62f29 because git am recomputes SHA)
git log --oneline -1
# Expected: <new-sha> docs(contributing): add Rule 13 — Artifact Disclosure & Delivery (Product Owner mandate)

# 7. Verify CONTRIBUTING.md was created and contains Rule 13
grep -c "Rule 13" CONTRIBUTING.md
# Expected: multiple matches (the rule appears in headings, body, and references)

# 8. Push the docs branch to GitHub
git push origin docs/rule-13-artifact-disclosure

# 9. Optionally open a PR on GitHub:
#    https://github.com/Pincodenovin13/m369-support/compare/phase-1/foundation...docs/rule-13-artifact-disclosure
#    Title: "docs(contributing): add Rule 13 — Artifact Disclosure & Delivery (Product Owner mandate)"

# 10. After PR review, fast-forward foundation:
git checkout phase-1/foundation
git merge --ff-only docs/rule-13-artifact-disclosure
git push origin phase-1/foundation

# 11. Verify SHAs match
git rev-parse phase-1/foundation
git rev-parse origin/phase-1/foundation
# These must be identical

# 12. Confirm the commit is visible on GitHub
# Open in browser: https://github.com/Pincodenovin13/m369-support/commit/<new-sha>
```

## What this patch does NOT change

Per the Product Owner's instruction ("فعلاً هیچ Feature، Migration یا تغییر امنیتی جدیدی پیاده‌سازی نکن"):
- ❌ No new feature implemented
- ❌ No new migration created
- ❌ No security behavior modified
- ❌ No database policy changed
- ❌ No application code modified

The patch only:
- ✅ Creates a new file `CONTRIBUTING.md` at the repository root
- ✅ Documents Rule 13 (Artifact Disclosure & Delivery) plus Rules 1–12 for completeness
- ✅ Documents the sandbox-recycling warning (§12.4) and the auth-limitation status (§12.3, §13.3)

## Important caveats

### 1. Sandbox recycling loss (2026-11-08 incident)

The Z.ai sandbox was recycled between sessions on 2026-11-08. A prior session in the same day produced 5 consolidation commits (adding ARCHITECTURE.md, the original CONTRIBUTING.md, REPOSITORY_MAP.md, updated STATE.md/README.md, and `.github/` workflow files). **Those commits and their patch files were LOST** when the sandbox was recycled. The current delivery contains ONLY the Rule 13 commit, applied on top of the original `phase-1/security-closure-b1-4` HEAD (`ab046a2`).

If the Product Owner wants the full consolidation work redone, please issue a separate task. The 5 lost commits can be reconstructed from the prior session's reports (which document their content in detail).

### 2. No chat-attachment capability

Per Rule 13 §13.3, the Z.ai environment does NOT have a `send_message` tool available in this session. Files in `/home/z/my-project/download/` are visible to the Product Owner via the gateway UI's file browser, but they CANNOT be attached directly as downloadable files in chat messages. The Product Owner must access the files through the gateway UI's download folder.

### 3. Patch SHA differs from commit SHA

The patch file SHA-256 (`cf92679b27e8b5d8e89319c15a0821b4582df4d0f1a53c37b5ada278cf7570a2`) is the integrity hash of the patch FILE itself. The original commit SHA on Z.ai's local branch is `ab62f29e3997934ab1df8f9ec1c3294b31066c6d`. When the Product Owner applies the patch via `git am`, the resulting commit will have a DIFFERENT SHA because `git am` recomputes the SHA based on the committer's identity at apply time. This is expected behavior — the patch CONTENT is identical (verified by tree SHA `97e5381ab437780f811a5986cdcae9fd6524c194`).

### 4. Default branch on GitHub is `test/marker`, not `phase-1/foundation`

Verified 2026-11-08 via `git ls-remote --symref origin HEAD` (returns `ref: refs/heads/test/marker HEAD`) and via the public GitHub HTML page metadata (`"defaultBranch":"test/marker"`). The previous report's claim of "main" as default branch was incorrect. Changing the default branch is out of scope for this task.

## After successful push

Update `STATE.md` (in a separate commit if needed) to reflect:
- Rule 13 has been added to CONTRIBUTING.md
- The new commit SHA on `phase-1/foundation` on GitHub
- The GitHub commit URL `https://github.com/Pincodenovin13/m369-support/commit/<new-sha>`

## Contact

For questions about patch contents or to request re-delivery, contact Z.ai.
For push execution, the Product Owner / Technical Manager must use a credentialed GitHub environment.

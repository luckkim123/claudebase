# Upstream patches

Local patches applied to vendored plugin code (anything claudebase ships
to `~/.claude/plugins/cache/`). Each entry records:

- **Target** — exact file and approximate line
- **Patch** — what changes
- **Why** — what the upstream behavior breaks and how the patch fixes it
- **Applied by** — script that owns the patch (must be idempotent)
- **Removal condition** — what upstream change would let us delete the patch

Patches here are a last resort. Prefer upstream PRs. Patches that have
been upstream-accepted but not yet released stay listed with a note.

## OMC post-tool-verifier "fix before continuing" freeze

- **Target**: `~/.claude/plugins/cache/omc/oh-my-claudecode/<ver>/scripts/post-tool-verifier.mjs` (around line 905)
- **Patch**: gate the `detectBashFailure(toolOutput)` branch behind `QUIET_LEVEL < 2`.

  ```javascript
  // before:
  } else if (detectBashFailure(toolOutput)) {

  // after:
  } else if (QUIET_LEVEL < 2 && detectBashFailure(toolOutput)) {
  ```

- **Why**: The branch emits a system reminder containing the literal phrase **"fix before continuing"**. Claude parses that phrase as a pause-gate and stops mid-task after every Bash error, requiring the user to intervene. The companion line at `~:906` (background-detection message) already had this gate; the patch unifies them so `OMC_QUIET=2` silences both.

  Root-cause evidence: `.omc/reviews/session-freeze-investigation.md` (2026-05-24). The phrase is the trigger, not the bash failure itself — same Bash error with the gate active produces no freeze.

- **Applied by**: `installer/scripts/patch_omc_freeze.sh`. Idempotent via marker (`QUIET_LEVEL < 2 && detectBashFailure`). Called from `installer/install.sh` step 6.5.

- **Removal condition**: Upstream OMC ships a release where the message is either gated by a `QUIET_LEVEL` check at the source, or rephrased to not contain "fix before continuing" / "before continuing" / equivalent pause-gate language. Verify by removing the patch on one machine and watching for the freeze pattern across 10+ Bash errors.

- **First applied**: 2026-05-24 (claude-settings repo). Extracted from `install.sh` into its own script: 2026-05-29 (P1 G4.1).

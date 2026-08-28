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

## OMC `.omc` scatter in non-git trees (getOmcRoot marker-ascent) — RETIRED 2026-08-29

> **Retired**: the removal condition below was met by OMC **5.0.1**. `getOmcRoot()` now
> finds the non-git project boundary itself — `findWorkspaceRoot()` climbs for
> `.omc-workspace` with a `$HOME` stop-guard, and `resolveNonGitStateAnchor()` handles
> the marker-less case; the resolution order `OMC_STATE_DIR > workspace marker > git >
> cwd` is documented at the top of `worktree-paths.js`. The patch's anchor line no
> longer exists (upstream replaced it with a ternary and inserted a non-git branch
> before the return), so it WARNed and `.bak`-restored on every install.
>
> Removed: `installer/scripts/patch_omc_statedir.sh`,
> `runtime/omc-patches/_claudebase-omc-ascent.cjs`, `patch_omc_statedir()` in
> `installer/lib/omc.sh`, and its call in `installer/install.sh`.
>
> One behavioural difference was accepted: this patch also honoured `.omcroot`,
> `.git` and `CLAUDE.md` as markers and anchored at the project root, whereas
> upstream honours only `.omc-workspace` and otherwise collapses to `$HOME`. Both
> stop the scatter; upstream just converges somewhere else when no marker exists.
> The record below is kept for that history.

- **Target**: `~/.claude/plugins/cache/omc/oh-my-claudecode/<ver>/dist/lib/worktree-paths.js`, `getOmcRoot()` default fallback (around line 195) + a `createRequire` shim after the import block.
- **Patch**: a 2-point edit that gives the git-less case a project-boundary fallback.

  ```javascript
  // top of file, after the import block:
  import { createRequire as _cbCreateRequire } from 'module';
  const _cbRequire = _cbCreateRequire(import.meta.url); /* claudebase-ascent */

  // getOmcRoot() default fallback — before:
  const root = worktreeRoot || getWorktreeRoot() || process.cwd();
  // after (ONLY this anchor, pinned by the next line `return join(root, OmcPaths.ROOT)`):
  const root = worktreeRoot || getWorktreeRoot() || _cbRequire('./_claudebase-omc-ascent.cjs').ascendToMarker(process.cwd()) || process.cwd();
  ```

  A companion CJS helper `_claudebase-omc-ascent.cjs` (source: `runtime/omc-patches/`) is copied next to the module; `ascendToMarker` climbs for a marker (`.omcroot` > `.git` > `CLAUDE.md` > `.claude/CLAUDE.md`), stopping at `$HOME` / filesystem root, returning `null` when none found.

- **Why**: `getOmcRoot` falls back to `process.cwd()` when not in a git repo (`getWorktreeRoot()` returns null). git repos normalize to the repo root via `git rev-parse --show-toplevel`, so their `.omc` converges to one dir — but a non-git tree (docs/slides/notes workspaces, iCloud/Desktop folders) has no such boundary, so `.omc` scatters across every visited subfolder. The patch gives the git-less case the symmetric behavior: ascend for a project marker and converge there. **git repos are untouched** (the ascent runs only when `getWorktreeRoot()` is null) → zero regression. When no marker is found, it returns null and OMC keeps its own cwd fallback → never widens blast radius.

  Design + verification: `docs/specs/2026-05-31-omc-statedir-marker-ascent/design.md`. Verified live: workspace subfolders converge to `workspace/.omc`; claudebase (git) unchanged.

- **Applied by**: `installer/scripts/patch_omc_statedir.sh`. Idempotent via marker (`_cbRequire`) for the JS rewrite; the helper `.cjs` is refreshed on every run (its logic can change between versions). Graceful-fail: missing anchor → WARNING + `.bak` restore, install continues. `node --check` validated. Called from `installer/install.sh` after `patch_omc_bash_freeze`.

- **Removal condition**: Upstream OMC ships a release where `getOmcRoot` finds a non-git project boundary itself (marker ascent or equivalent) before falling back to `process.cwd()`. Verify by removing the patch and confirming a non-git workspace's `.omc` still converges to one root across several visited subfolders. (This patch is also the reference implementation for that upstream PR.)

- **First applied**: 2026-05-31 (claudebase repo).

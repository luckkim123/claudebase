# Changelog

All user-visible changes to this repo. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased] — 2026-06-02 — recommendation ≠ approval guard

Fixes a behavioral failure where abandoning the empty-`AskUserQuestion` tool was misread as authorization to *do the work*. In a live session the model recommended a place name (KIOST), the user replied "that's correct, but…" (verifying the fact, not approving the action), and the model started editing on an unmade decision — drawing a sharp rebuke. Root cause: the abandon/retry guidance said "state a prose recommendation and **proceed**", and "proceed" was read as "begin edits" rather than "continue the conversation".

### Changed
- `runtime/hooks/askuserquestion_retry.py` — `REASON_ABANDON` and `REASON_RETRY` (and their docstring/comment mirrors) no longer say "proceed with that recommended option". They now say: present the recommendation in prose, then **WAIT for the user**; abandoning the *tool* does not authorize doing the *work* on a decision the user has not made; a user confirming a guessed fact is not a "yes, proceed". The only continue-without-waiting case is a trivial sub-choice inside already-approved work, and even then the model must state the assumption it is proceeding on.
- `config/CLAUDE.md` — the "Complete tool payloads" bullet's two "and proceed" phrasings reworded to "continue the conversation … not start doing the work". Added a dedicated bullet next to the self-scheduled-wakeup rule: **"A recommendation is not approval; confirming a fact is not a 'yes, do it'"** — covering both the tool-abandon≠work-authorization trap and the "you guessed right ≠ consent" trap, with the tell ("about to write 진행합니다 right after a fact-only acknowledgement").

### Added
- `tests/hooks/test_askuserquestion_retry.py::test_three_in_a_row_forces_abandon` — regression guard asserting the abandon message contains "wait" and a "not authorize"/"not a 'yes" clause, and that the old "proceed with that recommended option" wording is gone. **85 tests total, all passing.**

## [Unreleased] — 2026-05-29 — P1 hardening

Second post-standardize cycle. Focused on **internal quality, safety nets, and SSOT cleanup** rather than user-visible features. The 220-LOC `sync_plugins` bash function moves into a unit-tested Python module; CI starts running on every push; the installer's idempotency contract is now machine-checked by a smoke test.

### Added
- `installer/marketplace-metadata.json` — installer-only SSOT for marketplace OS gates (`os`) and post-install hooks (`post_install`). Keeps undocumented fields out of `config/settings.json`'s `extraKnownMarketplaces`.
- `installer/scripts/plugin_sync.py` — replaces 220 LOC of bash + embedded Python heredoc in `install.sh`. Two-phase design: pure `plan()` over filesystem inputs + `apply()` for side effects. 13 unit tests in `tests/installer/`.
- `installer/scripts/patch_omc_freeze.sh` — extracted from `install.sh`. The OMC `post-tool-verifier.mjs` sed-patch now lives in its own script.
- `docs/upstream-patches.md` — registry of local patches to vendored plugin code, with removal conditions for each.
- `tests/` — pytest suite covering all four `runtime/hooks/` scripts (`askuserquestion-guard`, `fix_surrogate`, `merge-project-hook`, `omc-reference-emit`) plus `plugin_sync`. **31 tests total**.
- `tests/smoke/test_install_idempotent.sh` — gates the "two runs = zero actions" invariant from `docs/ARCHITECTURE.md`. Detected the `install_omc_hud` regression that the previous grep patterns missed.
- `.github/workflows/ci.yml` — lint (ruff + shellcheck) + matrix tests (ubuntu + macos) + smoke on every push and PR.
- `docs/specs/<topic>/{design,plan}.md` per-topic spec folder convention; existing specs migrated via `git mv`.
- `docs/specs/2026-05-29-install-sh-modularization/design.md` — handoff design for P3 (installer modularization).
- `docs/specs/P4-todo.md` — backlog for P4 (CLAUDE.md hardening, `rules/` split investigation).

### Removed
- `runtime/hooks/routing-verdict-reminder.py` — dead code. Its role (per-turn routing nudge) was absorbed by the omha meta-harness's `<omha-routing>` UserPromptSubmit injector. `grep -r` across the repo confirmed zero references before deletion.

### Changed
- `installer/install.sh` 589 → ~405 LOC. `sync_plugins()` now a thin Python delegate. OMC freeze patch extracted. `install_omc_hud()` now idempotent (skips cp when destination already byte-matches the template + customization marker — fix for a regression caught by the smoke test).
- `.gitignore` now ignores `.omc/` runtime state wholesale (previously partial).
- `config/settings.json` gains a `SessionStart` `SURROGATE_AUTO_REPAIR_ON_START` hook (companion to the existing `Stop` hook).
- `runtime/hooks/merge-project-hook.py` docstring documents the single-marker / single-event limitation (M7).
- `docs/ARCHITECTURE.md` notes the new spec folder convention.

### Verification
- `installer/install.sh && installer/install.sh` — second run prints zero `linked:` / `rendered:` / `installing:` / `installed HUD:` / `applied:` lines (machine-checked by smoke).
- `python3 -m pytest tests/ -v` — 31 passed.
- `bash tests/smoke/test_install_idempotent.sh` — PASS.

### Notes
- `routing-verdict-reminder.py` deletion is recoverable via git history if its role ever needs to be reintroduced outside omha.
- `marketplace-metadata.json` is consumed only by `plugin_sync.py`; Claude Code itself never reads it. Keep `extraKnownMarketplaces` in `settings.json` as the canonical source for repo/url.

---

## [Unreleased] — 2026-05-29 — claudebase standardize

First standardized release. Repo renamed `claude-settings` → `claudebase` and reorganized by purpose for public-facing reuse.

### Added
- `docs/ARCHITECTURE.md` — directory model, symlink mechanism, plugin sync, secrets, drift detection
- `docs/CHANGELOG.md` — this file
- `docs/CONTRIBUTING.md` — fork-friendly PR guide
- `LICENSE` — MIT
- Source-by-purpose top-level layout: `config/`, `runtime/`, `installer/`, alongside existing `docs/`, `platform/`, `shell/`, `secrets/`, `templates/`

### Removed
- `agents/paper-*.md` (6 agents) — replaced by `oh-my-scholar` plugin
- `skills/paper-write/` — replaced by `oh-my-scholar` plugin
- `skills/using-omc/` + its hooks fragment — role absorbed by omha's ROUTE injector hook
- `docs/ppt-skills.md` — `ppt-*` skills migrated to `oh-my-docs` plugin (earlier commit `e43e8b3`)
- Committed `.bak` files — `.gitignore` already covers them
- `install.sh` / `install.ps1` backup logic — symlink overwrite is safe, redundant under idempotency contract

### Changed
- Repository renamed: `claude-settings` → `claudebase` (GitHub auto-redirects old URL)
- Directory restructure (all `git mv`, history preserved):
  - `claude/{settings.json,CLAUDE.md,mcp.template.json}` → `config/`
  - `claude/hooks/` → `runtime/hooks/`
  - `claude/scripts/` → `installer/scripts/`
  - `agents/`, `skills/` → `runtime/`
  - `install.sh`, `install.ps1` → `installer/`
  - `specs/` merged into `docs/specs/`
- Installer entrypoint: `./install.sh` → `./installer/install.sh`
- `REPO_DIR` resolution in `installer/install.{sh,ps1}` now walks one directory up to handle the new layout
- README slimmed to a quick-start (details moved to `docs/ARCHITECTURE.md`)

### Migration

Existing users on a machine that already has `~/claude-settings`:

```bash
cd ~/claude-settings
git pull
installer/install.sh    # picks up new layout, re-links symlinks if needed
installer/install.sh    # second run should be 0 actions
```

GitHub auto-redirects the old `claude-settings` URL, so no `git remote set-url` is strictly required, but recommended for clarity:

```bash
git remote set-url origin https://github.com/luckkim123/claudebase.git
```

Optional: rename the local clone too:

```bash
mv ~/claude-settings ~/claudebase
cd ~/claudebase
installer/install.sh    # re-points symlinks to the new path
```

New install: see `README.md`.

### Pre-claudebase tag

The state immediately before this standardize cycle is tagged `pre-claudebase-standardize-2026-05-29` for rollback.

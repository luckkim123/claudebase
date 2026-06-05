# Changelog

All user-visible changes to this repo. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased] — 2026-06-05 — opt-in `--update` for plugin sync

`installer/scripts/plugin_sync.py` only ever *installed* missing plugins; an
already-user-scope plugin returned `Action.OK` (no-op), so a newer marketplace
commit was never picked up — exactly why the freshly-pushed omp routing card
didn't reach the cache until a manual `/plugin` reinstall. Step 4f of the
sync skill already called this out for `omc` specifically ("install.sh never
upgrades an already-installed plugin"); this generalizes the fix to every
enabled user-scope plugin via an **opt-in** `--update` flag, without touching
install.sh's idempotency contract.

The flag does **not** decide staleness itself — `claude plugin update` is
idempotent and no-ops when a plugin is already current (verified live
2026-06-05: re-running it printed `already at the latest version` and left the
installed SHA + timestamp untouched). Self-comparing marketplace-mirror SHAs was
rejected as the detection mechanism because a mirror's `.git` tracks the
*marketplace manifest* repo, not each contained plugin's code repo — so a
multi-plugin marketplace (e.g. claude-plugins-official) would mis-judge. Letting
the CLI judge keeps the "never clobber a current plugin" guarantee.

### Added
- `installer/scripts/plugin_sync.py` — `Action.UPDATE` and a `plan_actions(..., update_candidates=False)` flag. When set, a user-scope plugin that would be `OK` is re-labelled `UPDATE` (only `OK→UPDATE`; `INSTALL`/`REINSTALL`/`SKIP_OS` are untouched — you can't update what isn't installed and a scope fix takes priority). `apply()` handles `UPDATE` with `claude plugin update <plugin>` (dry-run logs `would update`); the summary line now reports `N updated`. New `--update` CLI flag; without it, a one-line advisory reports the candidate count (`re-run with --update`) — never a false "N updates available" claim, since only the CLI knows what's stale.
- `runtime/skills/sync-claudebase/SKILL.md` — new **step 4g** ("Other plugins up-to-date?") with the detect-then-ask flow: show `plugin_sync.py --dry-run --update` candidates, ask the user, then `--apply --update`. Same governance as 4e/4f (never auto-apply). Added a 4g pointer in step 4f, a `Plugin updates (4g)` row in the outputs table, and the live-verified idempotency note.
- `tests/installer/test_plugin_sync.py` — 5 new tests: default keeps user-scope `OK` (idempotency regression guard), `--update` re-labels to `UPDATE`, `--update` leaves INSTALL/REINSTALL alone, dry-run `apply` emits `would update` without a subprocess, and the summary counts updates separately. **104 tests total, all passing** (was 99; +5).

### Notes
- `claude plugin update` prints "restart required to apply" — the skill tells the user to relaunch the session if any plugin was actually refreshed.
- Design decisions (CLI-delegated detection, opt-in not auto, `--dry-run` as the "ask" channel) were taken interactively with the user; the "never let latest updates get erased" constraint drove the idempotency-first approach.

## [Unreleased] — 2026-06-05 — harden the AskUserQuestion empty-call guards

External research (GitHub `anthropics/claude-code` #64150 / #64774 / #65247) confirmed the empty-`questions` `AskUserQuestion` failure is a **model-side emission defect** on large-context Opus 4.8 (1.5% vs 0% on Opus 4.7 / Sonnet 4.6), worsened by large injected context — not a settings or plugin bug, and not directly caused by OMC (whose bridge only reads the payload to notify). The defect is upstream and unfixable here; these are recovery/mitigation improvements to the two existing guards. Model inference is unaffected — the hooks run only at turn-end / on an actual empty call.

### Changed
- `runtime/hooks/askuserquestion_retry.py` — four hardenings: (1) tail-scan window raised 40→200 physical JSONL lines so a busy turn's rejection isn't missed; (2) a genuine human turn between two empty calls now **breaks** the consecutive-empty streak (a user answering between unrelated failures is no longer escalated toward abandon) — bare-string-content rejections are still counted, not mistaken for a human turn; (3) cross-shape session counter folds the PreToolUse guard's denies with this hook's own rejections per `session_id` and escalates to abandon at threshold 5 (counting the in-flight failure) even when the tail streak is low; (4) the retry-stage reason now also points to `/compact`.
- `runtime/hooks/askuserquestion-guard.py` — every deny now appends a best-effort telemetry record to `.omc/logs/askuserquestion_guard.jsonl` (signal `denied_askuserquestion`) so the Stop hook can count failures across shapes. Logging never changes the deny decision and never raises.

### Added
- `runtime/hooks/askuserquestion_stats.py` — manual aggregator that folds both logs into a human summary (total / guard-denies / retry-rejections / abandon-events / by-session). Not wired into any hook → zero per-turn cost; read-only over the logs.
- `tests/hooks/test_askuserquestion_stats.py` (4 tests) plus new cases in `test_askuserquestion_retry.py` and `test_askuserquestion_guard.py` covering the window, human-turn streak break, bare-string rejection, cross-shape count, in-flight-threshold off-by-one, and `/compact` in the retry reason. **Independent code review (feature-dev:code-reviewer) caught two real bugs — the in-flight off-by-one and the bare-string false-positive — both fixed with regression tests before commit. 99 tests total, all passing.**

### Notes
- Known latent issue (not fixed; fail-open so no correctness risk): the guard/retry logs are unbounded and `_session_failure_count` rescans both on every Stop. On a machine with weeks of long sessions this grows; revisit with log rotation if it becomes noticeable.

## [Unreleased] — 2026-06-05 — split rule WHY out of the loaded CLAUDE.md

`config/CLAUDE.md` (symlinked to `~/.claude/CLAUDE.md`, loaded into every session on every machine and project) had accumulated four `Operational Limits` bullets where the *behavioral rule* and its *debug history* lived in one paragraph — issue numbers, hook markers, transcript evidence, incident dates inline. One bullet was **3,457 chars**. This split the **why** out to an unloaded file and added a contract so it cannot re-accumulate.

### Added
- `docs/operating-rationale.md` — the **why** behind each `Operational Limits` rule (issue numbers, hook design, transcript evidence, incident dates), with one `## <anchor>` section per rule. Not loaded into any session, so the expensive context lives here instead of in `CLAUDE.md`. Four sections moved verbatim: `complete-tool-payloads`, `no-leaked-toolcall-markup`, `self-scheduled-wakeup-not-instruction`, `recommendation-not-approval`.
- `config/CLAUDE.md` → `### Adding an Operational Limit` — the contract that keeps the file lean: a rule is **one action-only bullet ≤350 chars**; the *why* goes to `docs/operating-rationale.md` and is linked with `↪ rationale: …#<anchor>`. Before writing a sentence: "instruction or explanation-of-why?"

### Changed
- `config/CLAUDE.md` — four bloated bullets compressed to action-only (each now 529–681 chars, was up to 3,457), each carrying a `↪ rationale:` link. **No information lost** — every cut sentence moved to `operating-rationale.md`. Untouched: `3-Strike`, `15-Min`, `Deletion Safety`, `Multi-session git` (already action-only or all-procedure). Net: **33,014 → 28,445 chars (−4,569, ≈14%)** off every session's loaded context.

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

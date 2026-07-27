# Changelog

All user-visible changes to this repo. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased] — 2026-07-26 — opt-in: `headroom` token compression, AI-usage fitting loop, optional plugins

Three opt-in additions, all per-machine and absent from the lab-forced
`config/settings.json` — nothing here runs in `install.sh`.

### Added
- **`headroom` token compression (opt-in).** README subsection + `sync-claudebase` step 4j (detect-then-ask `pip install "headroom-ai[all]"`; Python ≥3.10). `headroom wrap claude` routes Claude Code through a local, on-machine compression proxy that cuts *dynamic* input tokens (docs ~20 %, JSON 60–95 %) with the same answers. The npm `headroom-ai` is SDK-only; the CLI ships via pip.
- **`docs/ai-usage-fitting.md`** — a weekly loop to cut input tokens without losing answer quality: audit always-on injection (static) vs tool/file output (dynamic), turn repeated judgments into terse gated rules, compress the dynamic half with headroom, and review savings % **and** answer quality together. `config/CLAUDE.md` → Workflow gets a one-line pointer.
- **Optional personal plugins (opt-in)** via `sync-claudebase` step 4k (detect-then-ask, per plugin): `remotion`, `ui-ux-pro-max`, `marketing-skills`, `claude-mem`. Declared in README + `templates/settings.local.example.json`; **not** enabled lab-wide and their marketplaces are not registered in `config/settings.json` — enabled only on explicit yes at user scope.

### Changed
- **`headroom`: install ≠ activation, documented and detected.** The original write-up read as if `pip install` were enough. It is not — compression only happens when Claude Code is *launched* through the proxy, so a plain `claude` bypasses it silently. README now names the tell (`headroom doctor` reporting `proxy: not reachable` + `no wrap marker found` + `no savings recorded yet` = never used on this machine), and `sync-claudebase` step 4j now runs `headroom doctor` instead of stopping at `command -v`, so the sweep reports an installed-but-never-routed machine instead of calling it present and moving on. Found on a machine that had installed headroom the same day and was still running every session uncompressed.
- **`headroom`: the env route, and why `doctor`'s `claude` row lies about it.** The previous text offered only `headroom wrap claude`, which has no hook point when a container entrypoint or harness spawns `claude` for you — there the only route is `"env": {"ANTHROPIC_BASE_URL": "http://127.0.0.1:8787"}` in **`settings.local.json`** (never `config/settings.json`: it is symlinked and synced, so the proxy URL would reach machines with no proxy running and fail every request there). `headroom doctor` reads `~/.claude/settings.json` only and never merges `settings.local.json`, so a correctly-routed machine gets a permanent false `⚠ claude: not routed`. README + step 4j now pair the rows (`proxy: pass` + non-zero `savings` = routing fine, warning is a false negative), name the authoritative check (a new `claude` process incrementing `/stats` → `.summary.api_requests`), and carry the caveat that a dead proxy with this env set fails every request.
- **`headroom`: routing costs Remote Control and the 1M context window — now stated wherever the choice is offered.** Every previous mention priced the two routes only by undo cost and by the dead-proxy failure mode, leaving the decisive trade invisible: Claude Code gates `/rc` **and** the 1M window on the base URL, client-side, so pointing it at `127.0.0.1:8787` silently disables both (upstream #746/#1158, which `headroom doctor` names in its own output). This is not an env-route quirk — `headroom wrap claude` sets the same variable for its child and costs the same for the session it wraps, so compression and RC + 1M are mutually exclusive, full stop. README, step 4j, and `templates/settings.local.example.json` now carry the trade at the point of choice, recommend leaving routing off on machines driven remotely or running a 1M-context model, and note that the MCP tools (`headroom_compress`/`headroom_retrieve`) survive either choice but are on-demand only — they cannot shrink a tool result that has already landed in the context, so they do not substitute for the proxy. Found on a machine where `/rc` and 1M had been dead for days with the env block as the unsuspected cause.
- **`headroom`: one proxy port per machine (`18787+`), and never the default `8787` on more than one.** With several machines on one tailnet the default collides in a way that reads as a working setup: VS Code Remote-SSH auto-forwards a remote machine's listening ports to the *same* local port, so opening a remote window silently makes `localhost:8787` the **other** machine's proxy. A local persistent deployment bound there then cannot bind and keepalive-respawns forever (`last exit code = 3`) while `headroom install status` reports `healthy`, because the forward answers the health probe — the status command cannot tell whose proxy replied. README + `templates/settings.local.example.json` now carry the allocation rule (pick any free number in the `18787+` block, then settle ownership with `lsof -nP -iTCP:<port> -sTCP:LISTEN` — deliberately **not** a central table of machines: the port is per-machine state, a synced list of it both leaks machine names into every checkout and goes stale exactly when it matters, and the socket check catches a forward that a stale list would have called free), the two invariants that hold at any scale (bind `127.0.0.1` only — `0.0.0.0` on a tailnet publishes an unauthenticated credential-forwarding proxy to every node; and point `ANTHROPIC_BASE_URL` at `127.0.0.1:<own port>`, never a tailnet address), and the note that `headroom install apply --preset persistent-service` is what survives a reboot while the env route makes `headroom wrap` redundant. Port stays per-machine state in `settings.local.json`, out of the synced `config/settings.json`.

- **`headroom`: fidelity loss is mostly `--mode token`, so the fix is the mode, not the off switch.** The previous guidance had one remedy for corrupted tool output — stop routing. Reading the flag surface shows a cheaper one: `token` mode is documented as "prior turns may be rewritten for max savings", and in it `protect_recent_reads_fraction` defaults to `0.3`, leaving everything but the most recent ~30% of `Read`/`Grep` results silently compressible. The default `cache` mode freezes prior turns to win the provider prefix cache instead — which is where most of the money already is (one machine: 11.2% from compression against a far larger cache-read credit over the same window). README + `docs/ai-usage-fitting.md` now prescribe `--mode cache --protect-tool-results Read,Grep,Glob,Bash,Edit,Write,WebFetch,NotebookEdit` before the off switch, note that passing `--protect-tool-results` is what resets that `0.3` to `0.0`, and record that a persistent deployment carries the mode in **three** places in `~/.headroom/deploy/<profile>/manifest.json` (`proxy_mode`, `base_env.HEADROOM_MODE`, and the `proxy_args` array) that must be edited together, since `headroom install restart` keeps the old flags without complaint if the file does not parse. Also documented the gap no flag closes: `--protect-tool-results` covers tool results, but a brief **pasted into the chat** is a user message, so long specs must be written to a file and passed by path to survive intact. Found on a machine whose proxy had been running `--mode token` while the docs assumed the conservative default.

### Fixed
- **`omx` silently stuck two minor versions behind, with every `install.sh` reinstalling into the wrong environment.** `resolve_omx_python` probed bare `python3.1x` names, which resolve to the SYSTEM interpreter — but when omx-core lives in a dedicated venv (an image that pre-installs it to `/opt/omx-venv`), that interpreter's site-packages has no `omx_core`. The idempotency check therefore read `broken` on every run, and the reinstall it triggered targeted an environment the CLI does not use, failing on a `pip` that cannot do PEP 660 editable installs. Net effect: `omx` worked (so nothing looked broken) while reporting **0.7.5** against a plugin cache holding **0.9.0**, pinned to a source dir that no longer existed, and each sync printed a reinstall WARNING that never closed the gap. Fix: probe the installed `omx` shim's shebang interpreter first, so the idempotency check, the install, and the CLI all point at one environment. Verified on the affected machine — `broken` → `stale` → reinstall to 0.9.0 → subsequent runs skip silently.

### Notes
- A non-editable install fallback for that PEP 660 failure was written, then **removed after measuring it**: on the affected pip, `pip install <dir>` produces a bogus `UNKNOWN-0.0.0` distribution containing no `omx_core`, so the fallback would have reported success while installing nothing. The interpreter fix alone resolves the observed case; a machine with no `omx` shim yet still gets the pre-existing WARNING, which is the honest outcome.
- `install.ps1` is deliberately unchanged — it carries no omx logic at all (the CLI is not installed on Windows), so there is no counterpart to mirror under the "behaviorally equivalent" rule.
- `claude-mem` injects prior-session context at session start — it *adds* to the always-on input that headroom does not compress, and overlaps the existing memory stack (`MEMORY.md`, OMC wiki, omp secretary). Flagged in the fitting doc + step 4k as the loop's first measured subject (measure net effect before keeping).
- The static baseline behind the fitting doc was measured on the maintainer's machine 2026-07-25 (routing ~25 KB/turn, `MEMORY.md` 31.7 KB/session) and is illustrative, not universal.

## [Unreleased] — 2026-07-16 — opt-in: `claude` CLI fullscreen renderer (leak-free, per-machine)

New opt-in installer step + `shell/claude-mouse.sh`: wraps the `claude` command
with `CLAUDE_CODE_NO_FLICKER=1` so it launches into the fullscreen renderer —
no flicker, flat memory in long conversations, and in-app mouse scroll and
selection. Default **No** — this is the single marker-guarded exception to
claudebase's symlink-only, never-touch-rc model.

**Why an rc env var and not `/tui fullscreen`.** Upstream calls the `tui`
setting and `CLAUDE_CODE_NO_FLICKER` equivalent, but `/tui` persists `tui` into
`~/.claude/settings.json`, which claudebase symlinks to the *tracked*
`config/settings.json` — so the pref leaks into the synced repo on every use.
That is the recurring per-machine-key leak `654484a` and `8904b63` are about; an
rc env var is per-machine by construction and cannot leak.

### Added
- `shell/claude-mouse.sh` — sourceable `claude()` wrapper (`CLAUDE_CODE_NO_FLICKER=1` + `CLAUDE_CODE_SCROLL_SPEED=3`; `command claude` avoids recursion).
- `installer/lib/claude_mouse.sh` — `maybe_enable_claude_mouse`: opt-in prompt (default No, `INSTALL_CLAUDE_MOUSE=1` forces yes), appends one `# claudebase:claude-mouse`-marked `source` line to the login shell's rc (`~/.zshrc` / `~/.bashrc`). Idempotent: marker present → pure no-op.
- `installer/install.sh` — wires the step after the viewer opt-in.

### Notes
- File/marker names (`claude-mouse`) are **historical** — this began as a `CLAUDE_CODE_DISABLE_MOUSE=1` mouse-capture opt-out for drag-select (anthropics/claude-code#66957, #63054; tmux#337). Kept as-is so already-installed rc lines keep resolving; a rename would silently no-op them on other machines.
- Why `DISABLE_MOUSE` was dropped: its documented cost is losing "wheel scrolling inside Claude Code", and fullscreen's alternate screen buffer leaves tmux/terminal scrollback empty (verified: tmux `history_size=0`). Together they removed *every* way to scroll back — mouse-off hands the wheel to tmux, fullscreen leaves tmux nothing to scroll. Fullscreen's own capture is also strictly better than the native selection the opt-out protected: click-drag selects and auto-copies on mouse release (and to the tmux paste buffer inside tmux). One-off native selection: hold `Shift` (VS Code / most terminals), `Fn` (Terminal.app), `Option` (iTerm2).
- `CLAUDE_CODE_SCROLL_SPEED=3`: the VS Code integrated terminal sends exactly one wheel event per notch with no multiplier; `3` matches vim's default. Drop it on terminals that already amplify (Ghostty, iTerm2 with faster scrolling).
- Tradeoff: fullscreen gives up the terminal's native scrollback, so `Cmd+f` and tmux copy mode can't see the conversation. Use `Ctrl+o` transcript mode (then `[` writes it back to native scrollback, `/` searches). Revert by deleting the marked rc line.
- Requires tmux `set -g mouse on` for wheel scrolling (already set in `tmux/.tmux.conf`). Incompatible with iTerm2's `tmux -CC` integration mode.
- `install.ps1`: documented no-op (mirrors the existing tmux convenience-tool no-op) — unverified on native Windows Terminal, where upstream warns about stale-cell artifacts. Upgrade path noted inline.
- Fullscreen is an upstream **research preview**; behavior may change.

## [Unreleased] — 2026-06-17 — drop 5 redundant official plugins (superseded by OMC / superpowers / gh)

Removed 5 official plugins that were never used (`pluginUsage: 0`) and whose
capabilities are already covered by higher-tier tools in the stack: OMC's
agents, superpowers, and the `gh` CLI. Trimmed `enabledPlugins` 19 → 14.

### Removed
- `enabledPlugins` (config/settings.json) — dropped `feature-dev`, `pr-review-toolkit`, `code-simplifier`, `commit-commands`, `code-review` (all `@claude-plugins-official`). feature-dev/pr-review-toolkit/code-simplifier overlap OMC's `architect`/`code-reviewer`/`security-reviewer`/`code-simplifier` agents; commit-commands overlaps OMC `git-master` + `gh`; code-review (the `/code-review ultra` entry point) dropped per explicit user decision.
- `requiredPlugins` (config/settings.critical.json) — same 5 removed from the shrink-guard manifest so `settings_verify.py` stays green (verified `exit=0`).

### Notes
- Kept: `axlabs-mckinsey-pptx` (McKinsey-template decks — omd does not cover this), `oh-my-experiments@heroacademia` (may use), `context7` + both LSP plugins (auto-invoked backends).

## [Unreleased] — 2026-06-17 — viewer install: register via .vsix (was invisible) + Cursor-`code` guard

The `claude-code-viewer` extension installed by `lib/viewer.sh` was never loading
in VSCode. Two root causes, both found during a live install debug session: the
old path **copied the built tree into `~/.vscode/extensions/<id>/` but never
registered it in VSCode's `extensions.json` cache**, so the extension was on disk
yet invisible to VSCode; and the hardcoded install-dir id `luckkim123.claude-
code-viewer-0.1.0` **mismatched the repo's real `package.json` publisher**
(`local-dev`), which the manual copy path can't reconcile. Separately, the `code`
on PATH was **Cursor's CLI (v3.x), not VSCode's**, so the viewer would have
landed where VSCode can't see it.

### Changed
- `installer/lib/viewer.sh` — install path switched from "copy built tree into the extensions dir" to **package a real `.vsix` (`npx @vscode/vsce package --no-dependencies`) and install via `code --install-extension --force`**. VSCode now owns the `extensions.json` registration and the install-dir name (`<publisher>.<name>-<version>` = `local-dev.claude-code-viewer-0.1.0`), so the extension actually loads. Verified end-to-end on a clean install + idempotent second run (silent `up to date`).
- `installer/lib/viewer.sh` — `VIEWER_EXT_ID` corrected from `luckkim123.claude-code-viewer-0.1.0` to **`local-dev.claude-code-viewer`** (the repo's true `<publisher>.<name>`); install-state is now detected via `code --list-extensions` (VSCode's own truth) instead of a guessed dir.
- `installer/lib/viewer.sh` — new `_viewer_resolve_code` guard: a `code` on PATH is trusted only if `code --version` reports a **1.x VSCode** version; a Cursor `code` (3.x) is ignored and the standard `/Applications/Visual Studio Code.app` CLI is probed as fallback. Tooling check now also requires `npx`.
- `installer/lib/viewer.sh` — the built-from SHA is tracked at a **fixed sidecar** (`~/.vscode/extensions/.claude-code-viewer.installed-sha`) instead of inside the ext dir, since VSCode (not us) now names that dir.

### Added
- `runtime/skills/sync-claudebase/SKILL.md` (step 5) — **heads-up that the viewer opt-in prompt fires during install.sh**: tells the user the prompt exists (so an interactive sync isn't reflexively answered No), notes it's skipped silently non-interactively, and documents the `INSTALL_VIEWER=1` override + the real-VSCode-`code` requirement.

### Notes
- Scope check (distributed repo): viewer install is already opt-in / personal-dev-tool gated, so this only fixes a broken mechanism that ships to all machines — no per-machine quirk added. The Cursor-vs-VSCode `code` ambiguity is a general macOS hazard, not workspace-specific.

## [Unreleased] — 2026-06-12 — tool-call rationale: issue lineage + fixed AskUserQuestion variant

A user surfaced four GitHub issues (`anthropics/claude-code` #5219 / #895,
`anthropics/claude-agent-sdk-python` #113, `gsd-build/get-shit-done` #743) and
asked for an analysis, plus an update to the claudebase defenses that already
cover this. Investigation confirmed all four are variants of one root cause
already documented here (the model emitting tool-call JSON that violates the
schema), but the existing rationale was missing the authoritative paper trail:
the *oldest* report, the *official* Anthropic triage quote, the cross-tool
type-mismatch family, and — importantly — the one variant that was a real CLI
bug and has since been *fixed*, which the prior "no CLI fix" framing obscured.

### Added
- `docs/operating-rationale.md#complete-tool-payloads` — new **Issue lineage + official triage** paragraph: names the oldest open report (#895, 2025-04), quotes collaborator `ltawfik`'s explicit "model-side … CLI validation correctly catches this … self-correct on retry" verdict from #5219, notes the identical SDK cross-file (#113, closed stale), and lists the cross-tool type-mismatch family (Read #30197 / Edit #31379 / TodoWrite #30955 / Skill #30893 / AskUserQuestion gsd #743) so they're treated as one family, not separate bugs.
- `docs/operating-rationale.md#complete-tool-payloads` — new **"One variant WAS a real CLI bug and IS fixed"** paragraph: the AskUserQuestion auto-allow bug (interactive tools silently auto-allowed when listed in a skill's `allowed-tools`, returning empty answers → model guesses) was fixed in **Claude Code 2.1.69**. Gives a two-pronged triage — missing-field/wrong-type = model-side (`/compact`); empty-but-accepted = the fixed auto-allow bug (update CC).
- `docs/operating-rationale.md#no-leaked-toolcall-markup` — Triggers list gained item **(g) third-party API proxies**: multiple #895 reporters saw the failure *only* through non-official gateways; have users confirm against the first-party endpoint before chasing a model/CLI cause.

### Notes
- Docs-only change to an existing rationale file; no rules added to `config/CLAUDE.md` (the two governing rules — *Complete tool payloads*, *Don't leak tool-call markup* — and their three Stop/PreToolUse guard hooks already existed and were unchanged). This is evidence boosting, not a new defense.
- Scope check passed for a distributed repo: the tool-call emission failure is a universal model/CLI phenomenon, not a workspace-specific quirk, so it belongs in claudebase rather than a project store.
- No issue numbers already cited in the file were duplicated; all 7 newly added (#895, #5219, #113, #30197, #31379, #30955, #30893, gsd #743) were absent before.

## [Unreleased] — 2026-06-05 — sync skill: dirty-tree triage + non-owner path

A live sync run hit a gap: the working tree was dirty (`config/CLAUDE.md`, the
`~/.claude/CLAUDE.md` symlink target, had a 1-line uncommitted learning written
by another session) **and** `origin` was behind. The skill's only guidance was
pre-flight "if dirty, stop and surface to the user" — but the dirty change
turned out to be the *draft* of an incoming commit (`2e59219`, same topic, but
with code + tests), i.e. already absorbed by `origin`. The correct action was
patch-backup + discard, not stop. Worse, blanket-stopping on dirty strands a
**non-owner** (someone who received this clone but can't push `origin`): they'd
be told to "decide" on a change they should simply drop, with no documented way
to keep a *genuinely unique* change either, since they can't upstream it.

The fix is procedural — classify the dirty change before deciding, and give the
non-owner an out-of-tree path so they're never forced to choose between losing
their change and blocking sync forever.

### Added
- `runtime/skills/sync-claudebase/SKILL.md` — new **Step 1.5 (Dirty working-tree triage)** between fetch and analyze. For each dirty tracked file: read the local diff, compare it against `origin/main` (and the incoming commit subjects), then branch — **ABSORBED/superseded** → patch-backup (`git diff > /tmp/...patch`) + `git checkout --` + continue; **UNIQUE & worth keeping** → *then* the pre-flight "stop and surface" applies, split by push authority (owner: commit-then-pull-then-step-8-gate; non-owner: preserve as a patch/branch, `checkout --` to unblock `--ff-only`, forward to the owner or re-apply after pull); **UNIQUE but disposable** → confirm + discard. The recurring trigger (another session edits `config/CLAUDE.md` in place) is named explicitly so the dirty state isn't misread as this run's doing.

### Changed
- `runtime/skills/sync-claudebase/SKILL.md` — pre-flight dirty bullet reworded from a flat "stop and surface" to "dirty ≠ automatically stop → go to Step 1.5"; step-8 push gate gained a **Non-owner clones** paragraph (a denied `git push` is not "stuck" — forward the commit as a patch/PR, don't loop); two new Red-flags rows ("dirty → stop" and "discard so `--ff-only` works") each redirect to Step 1.5 classification.

### Notes
- Why this matters for distributed clones specifically: the owner can always commit→push to preserve a unique change, so for them "stop and ask" is sufficient. A non-owner cannot — which is the case the user flagged ("다른 사람은 push도 마음대로 할 수 없잖아"). Step 1.5's non-owner branch is the part that didn't exist before.
- Docs/skill-only change; no code, no tests touched. The triage procedure is the same sequence verified live in the sync run that surfaced the gap (patch-backup → `checkout --` → `pull --ff-only` succeeded).

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

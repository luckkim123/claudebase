---
name: sync-claudebase
description: 'Use when syncing the personal claudebase (historically claude-settings) repo across machines — pulling new commits, investigating cross-machine plugin drift, re-running installer/install.sh, or auditing whether the local machine matches the repo''s intended state. Triggers on phrases like "claude-settings 동기화", "claudebase 동기화", "settings sync", "plugin drift", "install.sh 다시", "settings.local.json", or after returning to a machine that''s been offline. Walks the fetch → diff → drift-check → install → verify → bug-triage cycle. Asks before any non-idempotent action (commits, pushes, new-file writes, cross-repo template adoption).'
triggers:
  - "/sync-claudebase"
  - "sync-claudebase"
  - "sync-claude-settings"
  - "claude-settings 동기화"
  - "claudebase 동기화"
  - "settings sync"
  - "plugin drift"
  - "install.sh 다시"
  - "settings.local.json"
  - "settings 머신 sync"
  - "claudebase 머신"
---

# sync-claudebase

Walks the analysis-and-apply loop for the personal `claudebase` repo (historically `claude-settings` — see note below) across machines. Built from the cycle that revealed the `mcp.json` idempotency bug and the 6-plugin drift on the obsidian-vault Mac (2026-05-02).

This skill is **rigid** — follow the procedure in order. The procedure exists because I previously skipped step 6 (post-install verification) and missed an idempotency regression for a full day.

**Repo / local clone naming**: The GitHub repo was renamed `claude-settings` → `claudebase` on 2026-05-29, and the canonical local clone path is now `~/claudebase`. Hooks in `config/settings.json` reference `~/claudebase/runtime/hooks/...` by absolute path, so a clone that still lives at `~/claude-settings` will have **broken hooks** until renamed. The first sync step below detects and fixes this. Resolve the path once at the start of a run:

```bash
CLAUDEBASE_ROOT="${CLAUDEBASE_ROOT:-$HOME/claudebase}"   # canonical; override only if cloned elsewhere
# Legacy-clone detection: old ~/claude-settings around but ~/claudebase isn't.
# DO NOT auto-rename+install here — a dirty legacy clone (uncommitted edits)
# must trip the pre-flight "stop on dirty" gate first, not get silently moved
# and re-installed. Detect, then hand off to the user.
if [ ! -d "$CLAUDEBASE_ROOT/.git" ] && [ -d "$HOME/claude-settings/.git" ]; then
  if [ -n "$(git -C "$HOME/claude-settings" status --porcelain 2>/dev/null)" ]; then
    echo "STOP: legacy clone ~/claude-settings exists AND is dirty (uncommitted changes)."
    echo "      Surface the dirty files to the user and let them decide:"
    echo "      commit → rename, discard → rename, or trash → re-clone to ~/claudebase."
    git -C "$HOME/claude-settings" status -sb
    exit 1
  fi
  # Clean legacy clone → safe to rename in place (no uncommitted work to lose).
  echo "renaming legacy clone: ~/claude-settings -> ~/claudebase"
  mv "$HOME/claude-settings" "$HOME/claudebase"
  git -C "$HOME/claudebase" worktree repair 2>/dev/null || true
  CLAUDEBASE_ROOT="$HOME/claudebase"
  "$CLAUDEBASE_ROOT/installer/install.sh"   # re-link symlinks + fix hook paths under the new path
fi
[ -d "$CLAUDEBASE_ROOT/.git" ] || { echo "no claudebase repo at $CLAUDEBASE_ROOT"; exit 1; }
```

> **Why the dirty guard (2026-06-01).** The original version of this block
> renamed + re-installed unconditionally whenever a legacy clone was found.
> On a machine where `~/claude-settings/claude/CLAUDE.md` had an uncommitted
> edit, that auto-path ran `install.sh` on a dirty tree — exactly what the
> pre-flight gate below forbids. The fix: a clean legacy clone renames
> silently (nothing to lose); a **dirty** one stops and surfaces the diff so
> the user picks commit / discard / trash-and-re-clone. Discovered while
> migrating the obsidian-vault Mac: the legacy clone was dirty, so the run
> bailed here and the user chose trash-and-re-clone to `~/claudebase`.

Everywhere the procedure says `cd ~/claudebase && ...`, read that as `cd "$CLAUDEBASE_ROOT" && ...`.

## Pre-flight (abort if any fails)

- `~/claudebase/` is a git repo with `origin` set
- `claude` CLI on PATH (otherwise the plugin-sync sub-step skips with a warning, which is fine but flag it)
- `~/claudebase/` working tree is clean — if dirty, **do not pull and do not run install.sh on a dirty tree**. But "dirty" is not automatically "stop": a tracked file like `config/CLAUDE.md` (symlinked to `~/.claude/CLAUDE.md`) is routinely edited in place by a *different* session writing a learning, so the working tree is dirty through no action of this run. Go to **Step 1.5 (Dirty working-tree triage)** to classify the change before deciding — only a change that is genuinely the user's to keep stops the run for a human.
- (Informational, not a gate) This run also sweeps **personal harness source repos** listed in `~/.claude/settings.local.json`'s `personalRepos` key (e.g. `/root/oh-my-experiments`) for fetch-drift — see **Step 4i**. Absent/empty list → skipped as "none configured"; `/workspace/*` project repos are deliberately out of scope.

## Procedure

### 1. Fetch incoming

```bash
cd ~/claudebase && git fetch && git status -sb
```

- `0 ahead, 0 behind` → no incoming. Skip step 2 + 3, jump to step 4 (drift checks still run).
- Behind only → list incoming commits: `git log --oneline HEAD..@{u}`.
- Ahead only → unpushed local commits already exist. Surface them; do not pull-rebase silently.
- Diverged → bail to user. Do not auto-merge.

### 1.5. Dirty working-tree triage (only if pre-flight found a dirty tree)

A dirty tree on a **distributed clone** is the common case this step exists for: another session on this machine edited a tracked file in place (most often `config/CLAUDE.md` ← `~/.claude/CLAUDE.md`, where learnings get written), so the change is real but may already be obsolete. **Never blanket-stop on dirty, and never blanket-discard.** Classify first, because the right action differs and a *non-owner* (a person who received this clone but cannot push to `origin`) can be left stuck if you stop on a change that should simply be dropped.

For each dirty tracked file (`git status --porcelain`):

1. **Read the local diff** — `git diff <file>`. Understand what the uncommitted change actually says.
2. **Compare against the incoming commits** — does `origin/main` already contain this change, or a superseding version of it?
   ```bash
   # Pick a distinctive phrase from your local diff's added line, then:
   git show origin/main:config/CLAUDE.md | grep -qF "<distinctive phrase>" \
     && echo "ABSORBED: origin already has it (or a superset)" \
     || echo "UNIQUE: origin does not have this change"
   ```
   Also skim the incoming commit subjects (`git log --oneline HEAD..@{u}`) — a local 1-line note is frequently the *draft* of a fuller incoming commit (same topic, but incoming adds code + tests). If the incoming commit supersedes the local note, the local note is redundant.
3. **Decide by classification:**
   - **ABSORBED / superseded** → the local change adds nothing origin doesn't already have. **Back it up to a patch first** (recoverable, per the Deletion-Safety rule), then discard so `git pull --ff-only` can proceed:
     ```bash
     git diff <file> > /tmp/claudebase-local-$(basename <file>)-$(date +%Y%m%d-%H%M%S).patch
     git checkout -- <file>
     ```
     State in the summary that the change was absorbed and where the backup patch is. Then continue to step 2 (analyze) → step 3 (pull).
   - **UNIQUE and worth keeping** → this is genuinely the user's content. **Now** the pre-flight "stop and surface to the user" applies — show the diff and let the user decide. Branch on push authority:
     - **Owner (can push `origin`)** → offer: commit the change locally now (so the tree is clean), then `git pull --ff-only` (or rebase the new commit onto incoming if they diverge), and push at the step-8 gate.
     - **Non-owner (cannot push `origin`)** → committing locally is fine for *their* clone, but it will make them diverge from `origin` on the next sync and they cannot upstream it. Guide them instead: keep the change as a **patch file** (`git diff <file> > ~/my-claudebase-change.patch`) or a local branch, `git checkout --` the tracked file so `--ff-only` works, then either (a) send the patch to the repo owner to merge, or (b) re-apply the patch after each pull if it's a personal-machine tweak. The point: a non-owner is never forced to choose between "lose my change" and "block forever" — preserve it out-of-tree and keep syncing.
   - **UNIQUE but disposable** (scratch edit, debug print, abandoned experiment) → confirm with the user it's disposable, then discard as in the ABSORBED path (patch-backup is cheap insurance even here).

**Known pattern — `config/settings.json` per-machine key leak (`model`/`effortLevel`/`alwaysThinkingEnabled`/`tui`/`theme`).** If the dirty diff in `config/settings.json` touches any of these five keys, this is **not** a fresh UNIQUE decision to put to the user — it's an already-settled convention violation. Commit `654484a` ("move per-machine prefs out of synced settings.json") established that these keys live in `settings.local.json` only; `templates/settings.local.example.json`'s own `_comment` spells out the same rule; and commit `b70396a` shows this exact leak already recurred once (reintroduced by a ponytail revert). The likely cause is a live session writing `/config` changes directly into the symlinked `~/.claude/settings.json`, which resolves to this tracked file. Handle it without asking:

```bash
# For each of model/effortLevel/alwaysThinkingEnabled/tui/theme present in the
# config/settings.json diff: merge its value into settings.local.json (only if
# absent there — never clobber an existing local override), back up the full
# diff to a patch (cheap insurance), then revert config/settings.json.
git diff config/settings.json > /tmp/claudebase-local-settings-leak-$(date +%Y%m%d-%H%M%S).patch
git checkout -- config/settings.json
```
Then edit `~/.claude/settings.local.json` (the merge target) to add whichever of the five keys were missing there, using the leaked value. Report the auto-fix in the sync summary ("settings.json per-machine leak: moved `<keys>` to settings.local.json") — don't gate this specific, already-decided pattern behind `AskUserQuestion`. A dirty diff touching *other* keys still falls through to the general ABSORBED/UNIQUE/disposable triage above.

### 2. Analyze the incoming diff

For each new commit (`git show --stat <sha>`), classify which subsystem it touches:

| Path touched | Implication |
|---|---|
| `installer/install.sh` / `installer/install.ps1` | Re-run `installer/install.sh --verbose` after pull (step 5). Both files should change together — flag if only one did. |
| `config/settings.json` | `enabledPlugins` may have shifted. Step 4b/4c will catch it. |
| `config/mcp.template.json` | New `${VAR}` may need adding to `secrets.env`. Step 4d will catch unresolved placeholders. |
| `templates/*` | Template only — not auto-applied. Holds for step 9 (adoption decision). |
| `shell/tmux.conf` | Reload step needed: `tmux source-file ~/.tmux.conf` after install. If `tmux`/clipboard tool is missing, step 5's `INSTALL_TOOLS=1` installs it. |
| `runtime/skills/*` | New skill added — re-running installer/install.sh symlinks it. Mention to user so they re-launch the session to pick it up. |

### 3. Pull

```bash
git pull --ff-only
```

If non-FF, bail. Never `--rebase` autonomously when local commits exist.

### 4. Drift checks (always run, even if step 1 found 0 incoming)

**4a. Symlinks intact**

```bash
# All three primary symlinks — settings.json, CLAUDE.md, tmux.conf.
# CLAUDE.md became a symlink target when config moved to config/CLAUDE.md;
# omitting it here is how a broken CLAUDE.md link slips through (it broke
# alongside the other two during the ~/claude-settings → ~/claudebase move).
for f in ~/.claude/settings.json ~/.claude/CLAUDE.md ~/.tmux.conf; do
  printf '%-35s -> %s' "$f" "$(readlink "$f" 2>/dev/null || echo '(not a symlink)')"
  [ -e "$f" ] && echo "  [OK]" || echo "  [BROKEN — target missing]"
done
```

All three should resolve into `~/claudebase/` and show `[OK]`. A `[BROKEN]`
line means the target moved (e.g. a leftover link into the old
`~/claude-settings`); step 5 (install.sh) re-links it.

**4b. Plugins forward (common pool installed?)**

```bash
jq -r '.enabledPlugins | keys[]' ~/claudebase/config/settings.json | sort > /tmp/enabled.txt
jq -r '.plugins | keys[]' ~/.claude/plugins/installed_plugins.json | sort > /tmp/installed.txt
comm -23 /tmp/enabled.txt /tmp/installed.txt
```

Empty = good. Non-empty = step 5's `sync_plugins` will install them.

**Marketplace cold-start race (expect on a fresh clone).** `plugin_sync.py`'s
`apply()` runs `claude plugin install` once per plugin with **no retry** — on
`rc != 0` it logs `WARNING: failed to install: <plugin>` and moves on
(verified in `installer/scripts/plugin_sync.py`). For a **git-source**
marketplace (`heroacademia`, `omx`) that was *just added* in the same run, the
first install can fail because the marketplace metadata hasn't finished
fetching yet. This is **not** a real failure — it's eventually-consistent:
each re-run of install.sh installs one more, so the WARNINGs shrink to zero
over 2–3 passes (observed 2026-06-01: `oh-my-docs@heroacademia` failed on pass
1 & 2, succeeded on pass 3 / direct `claude plugin install`). So:

- Don't report a first-pass `WARNING: failed to install` as a drift finding.
- Re-run install.sh (step 5/6 already do this) until `plugin sync: … 0 fixed`.
- Only a plugin that **still** fails after the tree has converged (`0 fixed`
  but the plugin is still absent from `installed_plugins.json`) is a genuine
  problem worth surfacing — try a direct `claude plugin install <id>` to see
  the real error.

**4c. Plugins reverse (extras unaccounted for?)**

```bash
comm -13 /tmp/enabled.txt /tmp/installed.txt
```

Each entry = a plugin user-installed on this machine but not in the common pool. For each such plugin:

- Check `~/.claude/settings.local.json` for an entry. If present → fine, machine extra is registered.
- If `settings.local.json` doesn't exist OR doesn't list the plugin → **ask user**: "Plugin X is installed but not registered. Per-machine (add to settings.local.json), or promote to common (edit repo settings.json)?"
- Default recommendation: per-machine. Promote to common only when the user confirms the same plugin is wanted on every machine they use (CLAUDE.md "Plugin reconciliation" rule).
- install.sh is **warn-only** for reverse drift and never removes a plugin the recipient installed themselves — kept plugins just log `plugin drift (kept): ...`. The installer only *adds* the plugins claudebase recommends; it never uninstalls (there is no prune flag). To remove a machine extra, the user uninstalls it themselves with `claude plugin uninstall`.

**4d. mcp.json secrets clean**

```bash
# Real placeholders only — excludes `"$comment"` JSON keys
tpl_vars=$(grep -oE '\$\{[A-Z_][A-Z0-9_]*\}' ~/claudebase/config/mcp.template.json | sort -u)
if [ -z "$tpl_vars" ]; then
  echo "(4d) no \${VAR} placeholders in template — check vacuous, skipping"
else
  echo "(4d) template placeholders: $tpl_vars"
  unresolved=$(grep -oE '\$\{[A-Z_][A-Z0-9_]*\}' ~/.claude/mcp.json | sort -u)
  [ -n "$unresolved" ] && echo "UNRESOLVED in rendered mcp.json: $unresolved" || echo "(4d) all placeholders resolved"
fi
```

If unresolved appears, prompt user to add the missing secret to `secrets/secrets.env` and re-run install.sh. The skip path keeps the check honest until the user actually adds an MCP server with placeholders — previously this passed vacuously on empty `globalServers: {}`.

**4e. claude CLI version up-to-date?**

```bash
current="$(claude --version 2>/dev/null | awk '{print $1}')"
latest="$(npm view @anthropic-ai/claude-code version 2>/dev/null)"
[[ "$current" == "$latest" ]] && echo "current ($current)" || echo "drift: $current → $latest"
```

If `claude` not on PATH, skip silently — pre-flight already flagged it.

If versions differ, surface the gap and ask before upgrading. install.sh does **not** upgrade the CLI itself — this is a separate, non-idempotent action that needs user confirmation.

Probe whether sudo is needed before showing the upgrade command (don't guess from path patterns — Homebrew prefixes like `/opt/homebrew` are user-writable despite being outside `$HOME`):

```bash
prefix="$(npm config get prefix)"
if [[ -w "$prefix/lib/node_modules" && -w "$prefix/bin" ]]; then
  echo "upgrade: npm i -g @anthropic-ai/claude-code"
else
  echo "upgrade: sudo npm i -g @anthropic-ai/claude-code"
fi
```

**Why this runs before step 5 (not after):** install.sh's plugin-sync invokes `claude plugin install`, which uses the on-PATH `claude`. Running plugin sync against a stale CLI silently uses old plugin metadata — a quiet way to drift.

After upgrade, re-run `claude --version` to confirm and then proceed to step 5. If the upgrade fails (network, permission, npm registry), surface the error and continue to step 5 anyway — old CLI is better than no install.

**ENOTEMPTY trap (2026-05-19 ksm_Obsidian session).** Upgrading `claude` from inside a running claude session can fail with `ENOTEMPTY: directory not empty, rename '.../claude-code' -> '.../.claude-code-XXXXXX'`. npm renames the existing dir to a hidden temp name before installing the new one, and the current claude process holds files open inside it so the rename aborts mid-flight. The orphaned `.claude-code-XXXXXX` temp dir then blocks future upgrade attempts even after the original session ends. Fix: `rm -rf /opt/homebrew/lib/node_modules/@anthropic-ai/.claude-code-*` (or the equivalent path on your npm prefix), then retry `npm i -g @anthropic-ai/claude-code`. The live `claude-code/` dir is *not* touched by this — only the orphaned temp. Verified safe on 2.1.143 → 2.1.144 with an active session still running.

**4f. OMC plugin version up-to-date?**

The plugin sync in install.sh only *registers* OMC (`claude plugin install` when missing); it never *upgrades* an already-installed plugin — verified in `install.sh` (`current == user` → `ok++` and skip; no version comparison). So OMC version drift is independent of install.sh and must be checked separately here. (This step stays OMC-specific because `omc update` syncs three things at once — plugin + npm CLI + CLAUDE.md; the generic `claude plugin update` path for *every other* plugin is step 4g.)

```bash
current="$(omc --version 2>/dev/null)"
# `omc update --check` checks without installing (verified: `omc update --help`
# lists `-c, --check  Only check for updates, do not install`).
latest="$(omc update --check 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | tail -1)"
if [[ -z "$current" ]]; then
  echo "(4f) omc CLI not on PATH — skip (install.sh step 5 installs it if missing)"
elif [[ -z "$latest" || "$current" == "$latest" ]]; then
  echo "(4f) OMC up-to-date ($current)"
else
  echo "(4f) OMC drift: $current → $latest"
fi
```

If versions differ, **surface the gap and ask before upgrading** — same governance as step 4e's claude CLI upgrade. `omc update` is non-idempotent (syncs plugin + npm package + CLAUDE.md together, per the OMC update banner), so it is NOT auto-run. On user confirmation:

```bash
omc update
```

**Post-update verification** (version bump alone ≠ healthy — same "applied ≠ verified" discipline as step 6). `omc update` touches three things at once (plugin, npm package, CLAUDE.md), so the most likely failure is a *conflict* between them, not a missing binary:

```bash
new="$(omc --version 2>/dev/null)"
[[ "$new" == "$latest" ]] && echo "(4f) version applied: $new" \
                          || echo "(4f) WARNING: expected $latest, got ${new:-<none>}"
# `omc doctor conflicts` checks plugin coexistence + config conflicts — exactly
# what a mid-session plugin/CLAUDE.md re-sync can break (verified: `omc doctor --help`).
omc doctor conflicts 2>&1 | tail -20
```

Note: `omc doctor conflicts` may report pre-existing warnings unrelated to the update (e.g. unknown fields in `.omc-config.json`, no MCP registry — both present on a healthy 4.14.0 as of 2026-05-24). So the signal is **new** conflicts that appear *after* the update, not the mere presence of warnings. If `omc doctor conflicts` surfaces something that wasn't there before, report it and run `/oh-my-claudecode:omc-setup` as the doctor suggests — do NOT auto-fix config conflicts (they may need a judgment call). If the version didn't bump to `$latest`, the update half-applied — re-run `omc update --force`, or `omc update --clean` to purge stale plugin cache, then re-check.

**Why ask, don't auto-run:** `omc update` rewrites the canonical `CLAUDE.md` and re-syncs the plugin while *this* session has them loaded. A mid-session plugin/CLAUDE.md swap can desync the running session's tool registry and skill list. Treat it like the claude CLI upgrade in 4e: confirm, then ideally restart the session to pick up the new plugin cleanly. If `omc update` fails (network, npm), surface the error and continue to step 5 — a stale OMC is better than a half-applied one.

**4g. Other plugins up-to-date? (detect-then-ask via `--update`)**

4f handles `omc` specifically. Every *other* enabled user-scope plugin
(superpowers, the heroacademia family, axlabs, the official plugins) has the
same drift property: `install.sh`'s plugin sync only *installs* missing ones, it
never *updates* an already-installed one. `plugin_sync.py --update` closes that
gap. Crucially it does **not** decide staleness itself — `claude plugin update`
is idempotent and no-ops when a plugin is already at the latest commit (verified
2026-06-05: re-running it printed `already at the latest version` and left the
installed SHA + timestamp untouched). So this step is **safe to offer every
sync** with zero risk of clobbering current plugins.

First show the candidate set without acting (dry-run asks the CLI, not us):

```bash
cd ~/claudebase && python3 installer/scripts/plugin_sync.py --dry-run --update \
  | grep -E 'would update'
```

This lists every enabled user-scope plugin `claude plugin update` *would* touch
— but remember the CLI no-ops the ones already current, so the real effect is
"refresh whatever is stale." **Ask the user** before applying, same governance
as 4e/4f (detect-then-ask, never auto-apply):

> "N user-scope plugins can be checked for updates. Run `claude plugin update` on
> them now? (already-current ones are skipped automatically.)"

On yes:

```bash
cd ~/claudebase && python3 installer/scripts/plugin_sync.py --apply --update
```

The summary line reports `… N updated …` — that N is how many the CLI actually
refreshed (stale ones), not the candidate count. `claude plugin update` notes
"restart required to apply", so tell the user to relaunch the session if any
plugin was actually updated. If a plugin fails to update (network, bad
marketplace), `apply()` logs `WARNING: failed to update: <plugin>` and continues
— surface it but don't abort the rest.

**Why opt-in, not folded into step 5's install.sh:** keeping `--update` off the
default install path preserves install.sh's idempotency contract (a second run
prints zero action lines — step 6 depends on this). Bundling auto-update would
make every install non-idempotent and could swap a plugin's commit at a moment
the user didn't choose. Detect-then-ask keeps the choice explicit.

**4h. HUD wrapper integrity (syntax valid + customization present?)**

`install_omc_hud()` (`installer/lib/omc.sh`) self-heals a broken
`~/.claude/hud/omc-hud.mjs` as of 2026-07-09 (it now gates its skip-condition
on `node --check`, not just presence of the customization marker), so step 5
below will already fix a broken wrapper. This check exists to **report** that
drift explicitly in the sync summary rather than let it pass silently inside
install.sh's log noise — a wrapper that was broken (e.g. `/oh-my-claudecode:hud
setup` run standalone, outside install.sh, which just `cp`s the raw template
and never re-applies `hud-customize.sh`) is worth surfacing to the user even
though step 5 will repair it.

```bash
CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
WRAPPER="$CONFIG_DIR/hud/omc-hud.mjs"
MARKER="OMC HUD local customization"

if [[ ! -f "$WRAPPER" ]]; then
  echo "(4h) HUD wrapper not installed yet — step 5 will install it"
elif ! node --check "$WRAPPER" >/dev/null 2>&1; then
  echo "(4h) HUD wrapper BROKEN (syntax error) — step 5 will auto-repair"
  node --check "$WRAPPER" 2>&1 | head -5
elif ! grep -qF "$MARKER" "$WRAPPER"; then
  echo "(4h) HUD wrapper valid but missing local customization — step 5 will re-apply"
else
  echo "(4h) HUD wrapper OK (valid + customized)"
fi
```

If this reports BROKEN or missing customization, note it in the sync summary
under Drift findings — even though step 5's `install_omc_hud()` repairs it
automatically, the user should know their HUD was silently degraded (likely
cause: someone ran `/oh-my-claudecode:hud setup` or `omc-setup` directly,
bypassing `install.sh` — see Red flags). After step 5 runs, re-check this same
command to confirm the repair actually landed; if it's still BROKEN, that's a
genuine regression worth step 7 triage (not a stale-cache false negative,
since `node --check` reads the file fresh every time).

**4i. Personal harness repos up-to-date? (fetch-drift sweep, ask-then-pull)**

`~/claudebase` is not the only repo the user may develop. Personal
harness/plugin **source** repos can live outside `~/claudebase` — e.g. a dev
checkout of `oh-my-experiments` at `/root/oh-my-experiments`. This sweep keeps
such a checkout current so a developer's local edits sit on top of the latest
`main` instead of drifting silently (observed 2026-07-11: a local
`oh-my-experiments` `main` was **39 commits behind** origin, `v0.4.0` vs origin
`v0.6.0`, noticed only by an ad-hoc "what version is omx").

**This sweep is a developer convenience, NOT how the tools get installed.** Do
not read a stale-clone finding as "the CLI is broken". The `omx` CLI is
installed from the omx-core BUNDLED IN THE PLUGIN CACHE
(`installer/lib/omx.sh::resolve_omx_source`, which falls back to
`~/.claude/plugins/cache/heroacademia/oh-my-experiments/<ver>/omx-core`), so a
normal user who never clones the repo still gets a working, marketplace-current
`omx` on every `install.sh` (step 5). A dev checkout, when present, wins that
resolution so local edits take effect — which is exactly what this sweep keeps
fresh. So the sweep matters only for machines that carry a dev checkout; on a
clone-free machine it is correctly a no-op and the CLI is still current.

**Registry — user-maintained list in `settings.local.json` (no auto-discovery).**
Mirror the established `projectTargets` pattern (`installer/lib/project_hooks.sh`
reads a gitignored per-machine list from `~/.claude/settings.local.json`) — a
new `personalRepos` key, a JSON array of repo paths (`~` allowed). It is
per-machine on purpose: which harness repos exist and where they live differs
by machine, so the list must **not** be committed into the shared repo (a
committed `config/personal-repos.txt` would tell every machine to sweep a path
that may not exist there). There is **no hardcoded fallback**: an absent or
empty list means "none configured" — the sweep is skipped and the summary says
so. Registering a repo is an explicit user act, in keeping with this skill's
no-auto-magic style (same reason it never auto-promotes per-machine plugins).

```bash
CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
# One entry per array line; expand a leading ~ ; drop blank lines so an empty/
# missing personalRepos key yields ZERO elements (not one empty string —
# `print('\n'.join([]))` emits a lone newline that mapfile would store as a
# single empty element, making the "0 configured" check misfire).
mapfile -t PERSONAL_REPOS < <(
  python3 -c "import json,sys
d=json.load(open('$CONFIG_DIR/settings.local.json'))
[print(x) for x in d.get('personalRepos',[])]" 2>/dev/null \
    | while IFS= read -r p; do [ -n "$p" ] && printf '%s\n' "${p/#\~/$HOME}"; done
)
if [ ${#PERSONAL_REPOS[@]} -eq 0 ]; then
  echo "(4i) no personalRepos configured in settings.local.json — sweep skipped"
fi
```

**Do NOT auto-discover** by scanning `~/` for git repos with a `luckkim123`
origin — too broad (it would sweep unrelated cloned repos), and it would rope in
the `/workspace/*` UUV RL stack (isaaclab, marinelab, constrained-albc,
marinegym), which is a **different governance domain**: those have their own git
workflow rules in `/workspace/.claude/rules/02-operations.md` (baseline-tag +
`exp/<topic>` branch discipline, explicit-path staging) and must never be
fetch-swept by this skill. The registry excludes them by simply not listing them
(and the user should not list them). See Red flags.

**For each `repo` in `PERSONAL_REPOS`** (skip silently if `$repo/.git` is
absent — a listed path that isn't a repo on this machine is not an error), mirror
the Step 1 ahead/behind logic exactly:

```bash
for repo in "${PERSONAL_REPOS[@]}"; do
  [ -d "$repo/.git" ] || { echo "(4i) $repo: not a git repo here — skip"; continue; }
  git -C "$repo" fetch --quiet
  echo "=== $repo ==="; git -C "$repo" status -sb | head -1
  git -C "$repo" status --porcelain | head -1   # empty => clean tree
done
```

Classify per repo (identical governance tiers to Step 1 + Step 4e/4f/4g —
**detect, then ask, never auto-pull** a repo this skill doesn't structurally own):

- **`0 ahead, 0 behind`** → up to date. Nothing to do.
- **Behind only + clean tree** → list incoming (`git -C "$repo" log --oneline
  HEAD..@{u}`), then **ask the user** before pulling — same AskUserQuestion-tier
  gate as 4e/4f: "`<repo>` is N commits behind origin. Pull `--ff-only` now?"
  On yes: `git -C "$repo" pull --ff-only`. Never silently auto-pull — unlike
  `~/claudebase` itself (which this skill owns end-to-end), these are
  independently-released repos, so the pull is always user-confirmed.
- **Behind + dirty tree** → do **not** discard uncommitted work. Run the same
  Step 1.5 triage reasoning (read the diff, decide ABSORBED / UNIQUE /
  disposable) *or*, if that is too heavy for a repo this skill doesn't own,
  explicitly report "`<repo>`: behind but tree is dirty — resolve manually" and
  leave it. Either way, never `git checkout --`/`stash`/`pull` over someone's
  uncommitted changes in one of these repos automatically.
- **Ahead only** → local unpushed commits exist. Surface them (`git -C "$repo"
  log --oneline @{u}..HEAD`); do NOT push (same push-gate as step 8, per-repo).
- **Diverged** → bail to user for that repo. Never auto-merge.

**Non-goal — do not install/build inside these repos.** This step only syncs git
state. Do NOT run `pip install -e` (or any build) for a swept repo even after a
pull — a partial editable reinstall after a branch/state change is a known
failure mode (`feedback_editable_install_namespace` memory). If a pull lands new
code that *needs* a reinstall (e.g. omx-core's `console_scripts` changed), the
step **surfaces** that as a follow-up for the user to run, but does not execute
it. Same push-gate as step 8: this sweep never pushes in any repo.

**4j. `headroom` token-compression CLI present? (detect-then-ask install)**

`headroom` (opt-in — see README "Token compression via headroom") wraps Claude
Code through a local compression proxy to cut input tokens. It's a per-machine
pip tool that `install.sh` does **not** install, so a freshly-synced machine may
be missing it. Detect and offer, never auto-install (pip is non-idempotent and
needs Python >=3.10):

```bash
if command -v headroom >/dev/null 2>&1; then
  echo "(4j) headroom present: $(headroom --version 2>/dev/null)"
else
  echo "(4j) headroom not installed"
fi
```

If missing, **ask** (same governance as 4e/4f — detect-then-ask, never
auto-apply):

> "`headroom` (token-compression proxy for `claude`) isn't installed on this
> machine. Install it now? (`pip install "headroom-ai[all]"`, needs Python >=3.10)"

On yes, install with a Python >=3.10 interpreter (macOS system `python3` is 3.9 —
prefer a real `python3.1x`; add `--break-system-packages` only if the chosen
interpreter is PEP-668 externally-managed):

```bash
PY="$(command -v python3.13 || command -v python3.12 || command -v python3.11 || echo python3)"
"$PY" -m pip install "headroom-ai[all]"
headroom doctor      # confirm the integration after install
```

Then remind the user it's opt-in per launch — `headroom wrap claude` (not a
persistent wrapper; it sets `ANTHROPIC_BASE_URL` to the local proxy only for
that session). Report the outcome in the summary.

**Why ask, not auto:** pip install is non-idempotent and pulls a large
dependency set, and headroom changes how `claude` launches. Folding it into
step 5's install.sh would break that step's idempotency contract — same reason
`--update` (4g) stays opt-in.

**4k. Optional personal plugins enabled? (detect-then-ask, per plugin)**

Four non-core plugins are opt-in personal extras — deliberately **not** in
`config/settings.json` (never forced lab-wide) and their marketplaces **not** in
`extraKnownMarketplaces` (so `install.sh`'s plugin sync won't register them; it
resolves marketplaces from `config/settings.json` only — `plugin_sync.py`
`_marketplace_source_arg`). That means the *only* place they get enabled is here,
on explicit yes. Candidates:

| Plugin | Marketplace add ref | Install target |
|:---|:---|:---|
| `remotion` | `remotion-dev/claude-code-plugin` | `remotion@remotion` |
| `ui-ux-pro-max` | `nextlevelbuilder/ui-ux-pro-max-skill` | `ui-ux-pro-max@ui-ux-pro-max-skill` |
| `marketing-skills` | `coreyhaines31/marketingskills` | `marketing-skills@marketingskills` |
| `claude-mem` | `thedotmack/claude-mem` | `claude-mem@claude-mem` |

Detect which are already installed:

```bash
claude plugin list 2>/dev/null | grep -E 'remotion|ui-ux-pro-max|marketing-skills|claude-mem' \
  || echo "(4k) none of the optional extras installed"
```

**Ask per plugin** for each missing one (they serve different purposes — video,
design, marketing, memory — the user may want some and not others):

> "Optional plugin `<name>` (<what it is>) isn't enabled. Add it now?"

On yes:

```bash
claude plugin marketplace add <marketplace-ref>       # note the marketplace NAME it reports
claude plugin install <plugin>@<marketplace-name> -s user
```

Then record it in `~/.claude/settings.local.json` `enabledPlugins` (e.g.
`"remotion@remotion": true`) so future syncs don't flag it as reverse drift
(4g / `find_drift`). The `@<marketplace-name>` suffix must match the name the
marketplace declares in its `marketplace.json` — usually the repo name, but
verify from the `marketplace add` output (e.g. `coreyhaines31/marketingskills`'s
marketplace name is `marketingskills`). Adding entries to `settings.local.json`
is fine; deleting/restructuring it needs a yes (same rule as the Red-flags
table). Tell the user to **restart** Claude Code afterward — `claude plugin
install` notes "restart required".

**Caution — `claude-mem`:** it injects prior-session context at session start,
which *adds* to the always-on input that headroom (4j) is cutting, and overlaps
the existing memory stack (`MEMORY.md`, OMC wiki, omp secretary). Offer it as a
measured experiment, not a default — see `docs/ai-usage-fitting.md`.

### 5. Run installer

```bash
cd ~/claudebase && INSTALL_TOOLS=1 installer/install.sh --verbose
```

Idempotent — safe to run unconditionally. Capture full output for step 6.

**Why `INSTALL_TOOLS=1` (convenience-tool opt-in).** With this env var set,
install.sh best-effort installs the two convenience tools `tmux.conf`'s
mouse-copy depends on — `tmux` itself and a clipboard helper (Linux X11 →
`xclip`, Wayland → `wl-clipboard`; macOS `pbcopy` is built-in so nothing is
installed). Without a clipboard tool, tmux.conf's `$COPY_CMD` copy-pipe expands
to nothing and drag/`y` selections never reach the system clipboard — the exact
"tmux copy doesn't work" symptom. It is **opt-in, idempotent, and
non-interactive-safe**: an already-present tool is a silent skip (so a second
run still prints zero action lines — step 6's contract holds), and when sudo
would be needed but no passwordless sudo is available, it falls back to the same
warn-only hint as `jq`/`gemini` (never a blocking sudo prompt). So include it
by default in an interactive sync; **omit it** (plain `installer/install.sh
--verbose`) only if you specifically want the pure warn-only behavior. `jq` and
`gemini` stay warn-only regardless — they are not uniformly apt-installable.

**Heads-up — the viewer opt-in prompt fires here.** install.sh calls
`maybe_install_viewer` (lib/viewer.sh) during this step. On a machine where the
`claude-code-viewer` VSCode extension is *not* installed it prints an opt-in
prompt (default **No**); where it's installed and a newer remote exists it asks
to update. **Tell the user this prompt exists** so an interactive sync doesn't
get answered No by reflex when they actually want it — and note it is **skipped
silently in a non-interactive run** (piped stdin / CI), so a non-interactive
sync never installs the viewer. To install it non-interactively, re-run with
`INSTALL_VIEWER=1 installer/install.sh`. The viewer needs `git`, `npm`, `npx`,
and a **real VSCode `code` CLI** (a Cursor `code` on PATH is detected and
ignored — install path is `npx @vscode/vsce package` → `code --install-extension`).

### 6. Post-install verification (CRITICAL — this is the step I previously skipped)

Run install.sh **a second time** and check:

- `mcp.json` line says `unchanged (skip)`, NOT `rendered:` (otherwise: idempotency regression — go to step 7)
- Symlink lines all say `already linked` in verbose mode (otherwise: relink churn)
- Plugin sync line: `0 fixed, 0 updated`. The `drift-kept` count may be non-zero — that's expected when reverse drift exists (warn-only is the default; the installer never removes a recipient's own plugins). A `fixed` count that never drops to 0 across passes is a real regression → step 7.
- Zero new directories under `~/.claude/.backup-*` from the past minute. Use a portable ISO timestamp — `bfs` (the find on recent macOS) rejects `"1 minute ago"`:
  ```bash
  REF=$(date -u -v-1M +'%Y-%m-%dT%H:%M:%SZ' 2>/dev/null \
        || date -u -d '1 minute ago' +'%Y-%m-%dT%H:%M:%SZ')
  find ~/.claude -maxdepth 1 -name '.backup-*' -newermt "$REF"
  ```

If any check fails → step 7. If all pass → step 8.

### 7. Bug triage (only if step 6 found regressions)

- Diagnose. Read the relevant section of `install.sh`.
- Fix in `install.sh` AND `install.ps1` together (CLAUDE.md "behaviorally equivalent" rule). If you can't mirror to install.ps1 (e.g. logic doesn't translate), explicitly note the divergence in the commit message.
- Local commit autonomously, conventional-commits format: `fix(install): <one-line>` with body explaining root cause + fix + verification.
- Re-run step 6 to confirm the fix.
- Hold local commit for step 8.

### 8. Push gate

If `git log --oneline @{u}..HEAD` shows local commits:

- List them to the user
- Ask explicitly: "Push N commit(s) to origin/main? (CLAUDE.md requires explicit confirmation)"
- On yes: `git push origin main`
- On no: leave for user

Never push autonomously, even in auto mode. CLAUDE.md governance overrides auto mode.

**Non-owner clones (no push access to `origin`).** If `git push` would fail because this is a distributed clone the user does not own, do NOT treat that as "stuck". The push gate is for the *owner*; a non-owner who ended up with a local commit (e.g. a unique change preserved in Step 1.5) keeps it on their own clone and forwards it to the repo owner as a patch (`git format-patch -1` / `git diff`) or a PR. Surface that path instead of looping on a denied push.

### 9. Template adoption (only if step 2 flagged a `templates/` change)

For each new template:

- Show the user what's new + what it's for
- Ask: "Adopt in <project> now, or leave for later?"
- On yes:
  - `cp <template> <project>/.claude/rules/<name>.md`
  - **Stage ONLY the new file** — `git add <project>/.claude/rules/<name>.md`. Never `git add -A` in someone else's repo.
  - Commit with `docs: adopt <name> rule from claudebase template` body referencing the source SHA.
  - Do NOT push — that repo's remote is separate (often org-owned) and outside this skill's authority.

## Red flags (STOP if you catch yourself thinking these)

| Thought | Reality |
|---|---|
| "Auto mode is on, I can push" | CLAUDE.md "Push only on explicit instruction" wins. Auto mode says so itself: "shared systems still need explicit user confirmation." |
| "I'll amend the previous commit to bundle the fix" | CLAUDE.md "Do not amend or force-push commits already on origin/main." |
| "These per-machine extras might also help on the other machine — promote to common" | "Plugin reconciliation": wait until the *other* machine actually adopts. Ask before promoting. |
| "settings.local.json is per-machine, I can rewrite it" | The user owns this file. Adding entries is fine; deleting/restructuring needs a yes. |
| "install.sh changed, I'll skip install.ps1 since I can't test on Windows" | Mirror the change anyway. Note "untested on Windows" in the commit body — but mirror. The "behaviorally equivalent" rule has no test-availability exception. |
| "The other repo has uncommitted changes, I'll stash before adopting the template" | Never `git stash` someone else's tree. Stage only the file you're adding (step 9). |
| "Skip the second install.sh run — first one passed" | That's exactly how the mcp.json idempotency bug went undetected for a day. Step 6 is non-negotiable. |
| "I'll auto-upgrade the claude CLI silently" | Non-idempotent. Plugin metadata or APIs can break across major versions and brick the current session. Step 4e requires user confirmation, same as commit/push. |
| "OMC drift detected, I'll just run `omc update`" | Non-idempotent — it rewrites CLAUDE.md and re-syncs the plugin mid-session. Step 4f requires user confirmation, same as 4e. Detect-then-ask, never auto-apply. |
| "Tree is dirty → stop, the user must decide" | Not always. A tracked file (esp. `config/CLAUDE.md`) is often dirtied by another session writing a learning, and the change may already be in `origin`. Run Step 1.5 triage first: ABSORBED → patch-backup + discard; UNIQUE → *then* stop and ask. Blanket-stopping leaves a non-owner wedged on a change they should just drop. |
| "Dirty change conflicts with the pull → discard it so `--ff-only` works" | Only after Step 1.5 classifies it as ABSORBED/disposable. A UNIQUE change is the user's content — back it up to a patch and surface it; a non-owner preserves it out-of-tree (patch/branch), never silently loses it. |
| "There's a `@old-marketplace` drift — I'll just `claude plugin uninstall <name>@old` to clear it" | `claude plugin uninstall` is **suffix-blind**: it matches the bare plugin name and removes whatever entry it finds — so `uninstall oh-my-experiments@omx` deletes the *enabled* `oh-my-experiments@heroacademia` from `config/settings.json` instead, breaking a healthy plugin (observed 2026-06-12). install.sh is warn-only and never uninstalls, so it won't clear this for you — if the same base name is enabled under a new marketplace, excise the stale entry from `installed_plugins.json` by hand rather than via the CLI. If you ever do run the CLI uninstall, diff `config/settings.json` immediately and `git checkout --` any wrongful enabled-plugin deletion. |
| "HUD shows `[OMC] Starting...`, I'll just re-copy the canonical template to fix it" | That IS the bug, not the fix. `/oh-my-claudecode:hud setup`'s own SKILL.md instructs a bare `cp` from the plugin's template — it does not know about claudebase's `hud-customize.sh` local patch layer, so a standalone `hud setup` (outside `install.sh`) silently drops the user's dir:/branch:/model:/effort: customization. Diagnose with step 4h first: if the marker is present but `node --check` fails, it is very likely a *duplicated* customize pass, not upstream corruption — run `installer/install.sh` (which re-copies the raw template AND re-applies `hud-customize.sh` in one atomic step) instead of hand-copying the template. |
| "I'll just fetch/pull every git repo I can find under `~/`" (step 4i) | Too broad. The sweep is **registry-driven only** (`personalRepos` in `settings.local.json`) — auto-discovery would rope in unrelated cloned repos and, worse, the `/workspace/*` UUV RL stack, which has its own git discipline (`/workspace/.claude/rules/02-operations.md`) and is a different governance domain. If a repo isn't in `personalRepos`, it isn't swept. Never widen the sweep to a directory scan. |
| "Repo 4i is behind — I'll pull it like I pull `~/claudebase`" | No. `~/claudebase` is the only repo this skill owns end-to-end (auto-pull after triage). A `personalRepos` entry is an independently-released repo — behind-only + clean still requires an explicit ask before `--ff-only`, and dirty/ahead/diverged never auto-anything. Detect-then-ask, per repo, same tier as 4e/4f. |
| "Pulled new omx-core code in 4i — I'll `pip install -e` it to finish the job" | Out of scope. 4i syncs git state only; a partial editable reinstall after a state change is a known failure mode (`feedback_editable_install_namespace`). Surface "needs reinstall" as a follow-up for the user; never run the build yourself. |
| "config/settings.json has a stray `model`/`effortLevel` key, I'll ask the user whether to commit it or keep it local" | Already decided — see Step 1.5's "Known pattern" callout. `654484a` + `templates/settings.local.example.json` settle this: those keys are per-machine-only, full stop. Move them to `settings.local.json` and revert the tracked file; don't spend an `AskUserQuestion` re-litigating a convention the repo's own history already answered. Check `git log --grep` for precedent before asking about *any* ambiguous tracked-file drift, not just this one. |

## Outputs the user expects after a run

A short summary table:

| | |
|---|---|
| Incoming commits applied | `<sha range or "none">` |
| Drift findings | `<list, or "none">` |
| HUD wrapper (4h) | `<"OK" / "was BROKEN, auto-repaired by step 5" / "missing customization, re-applied">` |
| Personal harness repos (4i) | per swept repo: `<repo>: up to date / X behind (pulled to Y) / X behind (pull deferred) / behind but tree dirty (manual) / N ahead (unpushed) / diverged (needs manual resolution)` — or "none configured" |
| claude CLI version | `<current — or "X → Y (upgraded)" / "X → Y (deferred)">` |
| OMC version | `<current — or "X → Y (updated)" / "X → Y (deferred)">` |
| Plugin updates (4g) | `<"N refreshed" / "offered, deferred" / "none stale">` |
| headroom CLI (4j) | `<"present (vX)" / "installed" / "offered, declined" / "not installed">` |
| Optional plugins (4k) | `<per plugin: enabled / offered, declined / already present — or "none offered">` |
| Actions taken | `<commits, file writes, install runs>` |
| Local commits awaiting push | `<list, or "none">` — with explicit ask if non-empty |
| Adoption questions | `<list, or "none">` |

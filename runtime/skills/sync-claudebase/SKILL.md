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
- `~/claudebase/` working tree is clean — if dirty, **stop and surface the dirty files to the user**. Do not pull, do not run install.sh on a dirty tree.

## Procedure

### 1. Fetch incoming

```bash
cd ~/claudebase && git fetch && git status -sb
```

- `0 ahead, 0 behind` → no incoming. Skip step 2 + 3, jump to step 4 (drift checks still run).
- Behind only → list incoming commits: `git log --oneline HEAD..@{u}`.
- Ahead only → unpushed local commits already exist. Surface them; do not pull-rebase silently.
- Diverged → bail to user. Do not auto-merge.

### 2. Analyze the incoming diff

For each new commit (`git show --stat <sha>`), classify which subsystem it touches:

| Path touched | Implication |
|---|---|
| `installer/install.sh` / `installer/install.ps1` | Re-run `installer/install.sh --verbose` after pull (step 5). Both files should change together — flag if only one did. |
| `config/settings.json` | `enabledPlugins` may have shifted. Step 4b/4c will catch it. |
| `config/mcp.template.json` | New `${VAR}` may need adding to `secrets.env`. Step 4d will catch unresolved placeholders. |
| `templates/*` | Template only — not auto-applied. Holds for step 9 (adoption decision). |
| `shell/tmux.conf` | Reload step needed: `tmux source-file ~/.tmux.conf` after install. |
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
- If `settings.local.json` doesn't exist OR doesn't list the plugin → **ask user**: "Plugin X is installed but not registered. Per-machine (add to settings.local.json), promote to common (edit repo settings.json), or uninstall (re-run install.sh with `--prune-plugins`)?"
- Default recommendation: per-machine. Promote to common only when the user confirms the same plugin is wanted on every machine they use (CLAUDE.md "Plugin reconciliation" rule).
- install.sh defaults to **warn-only** for reverse drift — kept plugins log `plugin drift (kept): ...`. Removal needs the explicit `--prune-plugins` flag, so a pool-trim on machine A never silently uninstalls on machine B.

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

### 5. Run installer

```bash
cd ~/claudebase && installer/install.sh --verbose
```

Idempotent — safe to run unconditionally. Capture full output for step 6.

### 6. Post-install verification (CRITICAL — this is the step I previously skipped)

Run install.sh **a second time** and check:

- `mcp.json` line says `unchanged (skip)`, NOT `rendered:` (otherwise: idempotency regression — go to step 7)
- Symlink lines all say `already linked` in verbose mode (otherwise: relink churn)
- Plugin sync line: `0 fixed, 0 removed, 0 failed`. The `kept` count may be non-zero — that's expected when reverse drift exists and `--prune-plugins` was not passed (warn-only is the default).
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

## Outputs the user expects after a run

A short summary table:

| | |
|---|---|
| Incoming commits applied | `<sha range or "none">` |
| Drift findings | `<list, or "none">` |
| claude CLI version | `<current — or "X → Y (upgraded)" / "X → Y (deferred)">` |
| OMC version | `<current — or "X → Y (updated)" / "X → Y (deferred)">` |
| Plugin updates (4g) | `<"N refreshed" / "offered, deferred" / "none stale">` |
| Actions taken | `<commits, file writes, install runs>` |
| Local commits awaiting push | `<list, or "none">` — with explicit ask if non-empty |
| Adoption questions | `<list, or "none">` |

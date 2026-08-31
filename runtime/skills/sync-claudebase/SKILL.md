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

## Push authority (resolve ONCE, before any push-related step)

`claudebase` is **luckkim123's distribution repo**: most machines running this skill received a *read-only clone* and cannot push to `origin`. The whole skill already branches on "owner vs non-owner" (Step 1.5, Step 8), but nothing actually *detects* which you are — so on a non-owner machine the run can still fall into the owner path and ask "push N commits?", a question the user can't act on. Detect once up front and carry the result through every push-related decision:

```bash
# Does THIS clone have push access to origin? --dry-run pushes nothing —
# it only exercises auth + ref-advertisement, so it is safe to probe.
#
# IMPORTANT: probe with a NON-CONFLICTING ref, not `HEAD` (a bare local
# branch name). `push --dry-run origin HEAD` fails for TWO unrelated
# reasons that look identical from the exit code alone:
#   1. genuine auth/permission failure (no push access)
#   2. non-fast-forward rejection (local HEAD is simply behind origin)
# An owner whose local branch has drifted behind origin (the common case
# after skipping a sync for a while) hits (2) and gets misclassified as
# non-owner — exactly the false negative that shipped in the first version
# of this probe. Push the remote's OWN tip back at itself instead: this can
# never be non-fast-forward (source == destination's current value), so a
# rejection here can only mean a real auth failure.
remote_main="$(git -C "$CLAUDEBASE_ROOT" ls-remote origin refs/heads/main | cut -f1)"
# Braces around ${remote_main} are load-bearing in zsh: an unbraced
# "$remote_main:refs/..." is parsed as the `:r` history/parameter
# modifier (strips to the "root", eating the leading `r` of `refs`),
# silently mangling the refspec into a bogus ref name. bash never had
# this problem, but this snippet is copy-pasted into whatever shell the
# user's terminal runs — brace it so it's correct in both.
if [ -n "$remote_main" ] && git -C "$CLAUDEBASE_ROOT" push --dry-run origin "${remote_main}:refs/heads/main" >/dev/null 2>&1; then
  CB_PUSH_AUTH=owner
else
  CB_PUSH_AUTH=non-owner
fi
echo "push authority: $CB_PUSH_AUTH"
```

- `owner` → the push gate (Step 8) and the "commit locally" offer in Step 1.5 apply as written.
- `non-owner` → **never phrase a push as an option.** A local commit that arises (Step 7's autonomous `fix(install:)` commit, or a UNIQUE change preserved in Step 1.5) stays on this clone; forward it to the repo owner as a patch (`git format-patch -1`) or a PR. Do not ask "push N commits?" — the user cannot, and being asked reads as the skill pushing them toward an action they can't take. Surface the patch/PR path instead.

If the probe is inconclusive (no network, `origin` unreachable, `ls-remote` returns nothing), treat as **non-owner** for this run — the safe default is to not offer a push you can't verify will succeed.

> **Why not `HEAD`? (2026-07-13 regression fix).** The original probe used
> `push --dry-run origin HEAD`, which folds "no auth" and "local branch is
> behind" into the same failure. Caught live: an owning machine whose local
> `main` was 8 commits behind `origin/main` got `CB_PUSH_AUTH=non-owner` from
> this exact bug, immediately after the same probe had shipped as the "fix"
> for push-authority misdetection. Verified fix: pushing `origin/main`'s own
> tip back at `refs/heads/main` is a true no-op (`Everything up-to-date`) when
> auth is fine, regardless of how far behind the local branch is — it only
> fails on a genuine permission error.

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
   - **UNIQUE and worth keeping** → this is genuinely the user's content. **Now** the pre-flight "stop and surface to the user" applies — show the diff and let the user decide. Branch on `CB_PUSH_AUTH` (already resolved in Pre-flight — don't re-probe):
     - **Owner (`CB_PUSH_AUTH=owner`)** → offer: commit the change locally now (so the tree is clean), then `git pull --ff-only` (or rebase the new commit onto incoming if they diverge), and push at the step-8 gate.
     - **Non-owner (`CB_PUSH_AUTH=non-owner`)** → committing locally is fine for *their* clone, but it will make them diverge from `origin` on the next sync and they cannot upstream it. Guide them instead: keep the change as a **patch file** (`git diff <file> > ~/my-claudebase-change.patch`) or a local branch, `git checkout --` the tracked file so `--ff-only` works, then either (a) send the patch to the repo owner to merge, or (b) re-apply the patch after each pull if it's a personal-machine tweak. The point: a non-owner is never forced to choose between "lose my change" and "block forever" — preserve it out-of-tree and keep syncing.
   - **UNIQUE but disposable** (scratch edit, debug print, abandoned experiment) → confirm with the user it's disposable, then discard as in the ABSORBED path (patch-backup is cheap insurance even here).

**Known pattern — `config/settings.json` per-machine key leak (`model`/`effortLevel`/`tui`/`theme`).** If the dirty diff in `config/settings.json` touches any of these four keys, this is **not** a fresh UNIQUE decision to put to the user — it's an already-settled convention violation. Commit `654484a` ("move per-machine prefs out of synced settings.json") established that these keys live in `settings.local.json` only; `templates/settings.local.example.json`'s own `_comment` spells out the same rule; and commit `b70396a` shows this exact leak already recurred once (reintroduced by a ponytail revert). The likely cause is a live session writing `/config` changes directly into the symlinked `~/.claude/settings.json`, which resolves to this tracked file. Handle it without asking:

**`alwaysThinkingEnabled` is NOT on this list — it is a deliberate baseline pin (`0ece959`), so never revert it out.** `654484a` originally grouped it with the four per-machine prefs, but `0ece959` promoted it to the universal baseline on purpose: `effortLevel: xhigh` is only legal while thinking is on, and effort stays machine-local, so the enabling half has to be universal or an `xhigh` machine 400s. Reverting it out of `config/settings.json` is therefore a regression, not a cleanup. Note the CLI erases it from the *rendered* file on its own — `/config`'s thinking toggle writes `undefined` when turning thinking **on** (`{alwaysThinkingEnabled: F ? void 0 : !1}`), so the key legitimately vanishes from `~/.claude/settings.json`. That disappearance is harmless (absent = on) and is **not** a leak to chase.

```bash
# For each of model/effortLevel/tui/theme present in the
# config/settings.json diff: merge its value into settings.local.json (only if
# absent there — never clobber an existing local override), back up the full
# diff to a patch (cheap insurance), then revert config/settings.json.
git diff config/settings.json > /tmp/claudebase-local-settings-leak-$(date +%Y%m%d-%H%M%S).patch
git checkout -- config/settings.json
```
Then edit `~/.claude/settings.local.json` (the merge target) to add whichever of the five keys were missing there, using the leaked value. Report the auto-fix in the sync summary ("settings.json per-machine leak: moved `<keys>` to settings.local.json") — don't gate this specific, already-decided pattern behind `AskUserQuestion`. A dirty diff touching *other* keys still falls through to the general ABSORBED/UNIQUE/disposable triage above.

**This leak pattern should now be extinct — if it fires, the machine has not migrated.** Since `installer/scripts/render_settings.py` landed, `~/.claude/settings.json` is a *rendered* file rather than a symlink into the repo, so CLI writes no longer reach `config/settings.json` at all. A dirty baseline therefore means this machine is still on the old symlink layout: run `installer/install.sh` to migrate it (the render replaces the symlink, and captures whatever the CLI left behind into `settings.local.json`), then re-check.

**Until it has migrated, never blanket-revert when the diff also carries `enabledPlugins` / `extraKnownMarketplaces` (2026-07-27, measured).** `git checkout -- config/settings.json` reverts the *whole file*, and under the symlink layout that file was the only place Claude Code read user-scope plugin enablement from — so a blanket revert silently disabled every optional personal plugin (4k) in the same stroke. Verified live: all four 4k plugins plus `typescript-lsp` sat at `Status: ✘ disabled` for two days after exactly this sweep, while `settings.local.json` still listed them `true`. Check the diff before reverting:

```bash
# Blanket revert is safe ONLY if the diff touches nothing but the five pref keys.
git diff config/settings.json | grep -E '^\+' | grep -E 'enabledPlugins|extraKnownMarketplaces|@' \
  && echo "STOP: diff carries plugin state — remove only the pref keys, do NOT git checkout" \
  || git checkout -- config/settings.json
```

When it does carry plugin state, delete just the leaked pref keys from `~/.claude/settings.json` and leave the plugin entries in place, then confirm nothing was collaterally disabled:

```bash
claude plugin list | grep -A3 -E 'remotion|ui-ux-pro-max|marketing-skills|claude-mem' | grep Status
# every one the user opted into must read "enabled", not "disabled"
```

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

The summary line reports `… N updated …` — that N is the **candidate** count,
not how many were actually refreshed. `apply()` increments
`counts[Action.UPDATE]` while building the plan and afterwards checks the CLI's
return code only for *failure*, so a plugin the CLI no-ops because it is already
current still counts. N therefore equals the number of enabled plugins on every
run. Read it as "N were asked", never as "N were stale". `claude plugin update`
notes "restart required to apply", so tell the user to relaunch the session if
any plugin was actually updated. If a plugin fails to update (network, bad
marketplace), `apply()` logs `WARNING: failed to update: <plugin>` and continues
— surface it but don't abort the rest.

**If this dies on `FileNotFoundError: 'claude'`, just re-run it — 4f is why.**
`omc update` reinstalls its npm package, and npm relinks the whole global bin
directory while it works. Running 4g in the seconds after 4f can therefore find
`claude` briefly absent, and the run aborts on the first `claude plugin update`
with a raw traceback (observed 2026-08-10: `skip marketplace ensure: 'claude'
not in PATH`, then `FileNotFoundError`). Nothing is broken and nothing is
half-applied — the script fails before mutating anything. Confirm the binary is
back (`claude --version`) and re-run the same command; it completed all 18
plugins on the retry. This is reachable by following the skill exactly, since
4f runs immediately before 4g.

Do **not** "diagnose" this by inspecting `/usr/bin/claude`: on Linux the package
legitimately ships its binary as `bin/claude.exe` (that is the `bin` mapping in
`@anthropic-ai/claude-code`'s own `package.json`), so a symlink pointing at a
`.exe` is correct and not the fault.

**claude-mem worker after an upgrade — kill it; a session relaunch is not
enough.** `claude-mem` runs one background worker on a fixed port
(`CLAUDE_MEM_WORKER_PORT` in `~/.claude-mem/settings.json`, default `37701`)
shared across every host that has it enabled (Claude Desktop, the VS Code
extension, the terminal CLI). When a sync bumps its version the *old* worker
keeps running and squatting the port; claude-mem sees the version mismatch but
**cannot kill a worker a different host spawned** (the PID file reads `null`, so
it only logs `Stale worker is serving the port but the PID file does not
identify it`). It then reports `worker unreachable` and, after
`CLAUDE_MEM_HOOK_FAIL_LOUD_THRESHOLD` (3) consecutive hooks, **blocks every
prompt loudly**. Relaunching the session does *not* fix it — the stale daemon
outlives the session. So **only if `claude-mem` was among the N updated**, kill
the stale worker so the next hook respawns the new version:

```bash
port=$(python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.claude-mem/settings.json'))).get('CLAUDE_MEM_WORKER_PORT','37701'))" 2>/dev/null || echo 37701)
pid=$(lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null)
[ -n "$pid" ] && kill "$pid" && echo "claude-mem: killed stale worker pid $pid on :$port (respawns fresh next hook)"
echo '{"consecutiveFailures":0,"lastFailureAt":0}' > ~/.claude-mem/state/hook-failures.json 2>/dev/null || true  # clear the loud-fail counter
```

Don't run it when claude-mem did *not* update — killing a healthy same-version
worker just forces a needless respawn.

**The same collision across containers, where the recipe above cannot run.** A
machine running two or more containers with `--network host` shares one loopback
between them while keeping filesystems and PID namespaces separate — so each
container carries its *own* plugin cache, its own version, and its own
`~/.claude-mem/`, yet they all contend for the single worker port. The container
whose plugin updates first finds a foreign older worker squatting the port and
blocks, and it cannot clear it: `kill` does not cross a PID namespace, and the
owner is unresolvable from inside anyway. Measured 2026-08-21 on `stonefish_dev`
(v13.15.3) against `marinelab-isaaclab` (v13.14.0, worker up 7 days) — `lsof`,
`ss`, `netstat`, and `fuser` are all absent in the container, and a `/proc` scan
finds no owner for the socket; only `/proc/net/tcp` shows the port at all, and
that is the shared *net* namespace talking, not the container's own processes.

**The block also hides its own cure** — it fires at `UserPromptSubmit`, so
`/sync-claudebase`, the skill carrying the kill recipe, never starts. The prompt
that surfaced this was `/sync-claudebase` itself. Clear it from *outside* the
container:

```bash
docker top <container> | grep worker-service   # host PID of the squatting worker
kill <pid>                                     # next hook respawns the new version
```

The durable fix is one port per environment: give each host-network container a
distinct `CLAUDE_MEM_WORKER_PORT` in its own `~/.claude-mem/settings.json`. Don't
read the `37701` fallback in the recipe above as the port actually in play —
the containers measured here carried `37700`. Read the file.

**This step no longer decides anything — step 5 updates regardless (55880cc).**
`installer/lib/plugins.sh` now appends `--update` unconditionally, because
without it `plugin_sync` labels every already-installed plugin OK and never moves
its version (measured: `oh-my-orchestrator` sat at 0.16.0 while 0.17–0.19 had
shipped). So a "no" here is overridden minutes later by step 5, and asking as if
it were a gate misrepresents what the run will do. Keep 4g as a **preview** —
show the `--dry-run --update` candidate list so the user sees what step 5 is
about to touch, and say plainly that step 5 does it either way. The only real
choice left is to skip step 5 entirely, which is not what this question offers.

*(Superseded rationale, kept for the record: `--update` used to be opt-in
precisely so install.sh stayed idempotent — a second run printed zero action
lines. 55880cc traded that contract for currency. See step 6, which no longer
expects `0 updated`.)*

**MCP servers are not plugins** and `claude plugin update` does not reach
them — they are step 4j.

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

**4j. MCP servers up-to-date?**

4f and 4g cover plugins. MCP servers are the gap, and they are a harder one:
**there is no `claude mcp update`** — verified 2026-08-10, `claude mcp --help`
lists `add`, `add-json`, `get`, `list`, `login`, `logout`, `remove`,
`reset-project-choices`, `serve` and nothing else. A server is just a command
someone wired into a config file, so whatever installed it decides how it
upgrades. Nothing enumerates them for you, which is how a server sits nine minor
versions behind for months without a single line of output saying so (tokensave
was on v7.0.2 against v7.9.0 when this step was written; it was removed from this
repo on 2026-08-25 — see 4m — but the lesson it taught is why this step exists).

So the step is: enumerate, classify by launch command, apply the matching check.

```bash
cd <the project you are syncing> && python3 ~/claudebase/installer/scripts/mcp_inventory.py
```

Detection only — it never upgrades. It reads `~/.claude.json` (user scope *and*
every `projects[*].mcpServers`) plus the current directory's `.mcp.json`, so run
it from a project to see that project's servers. Classification:

| Launch command | Kind | Check |
|:---|:---|:---|
| `uvx <pkg>` , or a path resolving into `.../uv/tools/<pkg>/` | uv | `uv tool list --outdated` (verified: `--outdated` is a real `uv tool list` flag) |
| `npx -y <pkg>` , `bunx` | npx | none — refetched every launch, so always latest and never pinned |
| any other absolute path | binary | ask the tool itself: `--version`, then its own upgrade verb |
| `https://…` | remote | claude.ai connector; the server is theirs, only the auth can go stale |

**Resolve the symlink before classifying.** A uv-installed server is launched
through `~/.local/bin/<cmd>`, which looks like a plain binary until `realpath`
lands in the uv tool directory — and only that path carries the PyPI name, which
need not match the command. graphify's package is `graphifyy`; classifying on the
command alone both misses the uv upgrade path and reports the wrong package name.

Same governance as 4e/4f/4g — **surface the gap and ask, never auto-upgrade**:

```bash
uv tool upgrade <pkg>     # uv-managed
<tool> upgrade            # self-updating binary, if it has such a verb
```

**A version bump is not the end of it — re-run the server's own installer.**
Verified on tokensave 7.0.2 → 7.9.0 (2026-08-10, before its removal): the upgrade succeeded and the
binary reported 7.9.0, but every subsequent tool call printed `81 new tokensave
tool(s) not yet permitted`. New tools ship with a new version and land outside
the permission list written at install time. The fix is the tool's own
reconfigure step (there, `tokensave reinstall`); a session restart does not do it.

Two things to know before running one of those reconfigure steps:

- **Prefer a wildcard permission when the tool offers one.** `tokensave reinstall
  --wildcard-permissions` writes a single `mcp__tokensave__*` entry instead of
  enumerating every tool; the explicit form would have put ~250 lines into
  `permissions.allow`, and would need rewriting on every future version.
- **They write into `~/.claude/` — check what they touched.** These installers
  configure "MCP server, permissions, hooks, prompt rules", which means
  `~/.claude/settings.json` (rendered by *this* repo — a foreign write can drop
  keys) and potentially `~/.claude/CLAUDE.md` (a **symlink to
  `config/CLAUDE.md`**, so a write there follows the link and ships to every
  machine — the same trap documented for `graphify install --project`). Take a
  checksum first, and verify after:

```bash
shasum ~/claudebase/config/CLAUDE.md            # before, and again after
python3 ~/claudebase/installer/lib/settings_verify.py ~/.claude/settings.json
git -C ~/claudebase status --short              # must show no new config/ changes
```

tokensave passed this on 2026-08-10 — it wrote its rules to a separate
`~/.claude/rules/tokensave.md` and left `config/CLAUDE.md` byte-identical. That
is the outcome to confirm, not to assume.

**Adding a new MCP server later?** Nothing here is per-server — the classifier
keys off the launch command, so a server added tomorrow is picked up by the same
run with no edit to this skill. Extend the table only if a genuinely new *kind*
of launcher appears (a `docker run` server, say). If a new server's installer
writes into `~/.claude/`, add it to the checksum list above.

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
| `claude-mem` | `thedotmack/claude-mem` | `claude-mem@thedotmack` |

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
(4g / `find_drift`).

**That record alone does NOT make it active everywhere.** Claude Code honours
exactly ONE `settings.local.json` — the nearest one. In a project that ships its
own `.claude/settings.local.json` with an `enabledPlugins` map, that map fully
REPLACES the home-level one (no per-key merge), so the plugin is silently
disabled there — no error, and `plugin_sync` only prints a WARNING. Entries in
the shared `config/settings.json` are immune (they always merge in). So for a
plugin the user wants everywhere, the lab-wide `config/settings.json` is the
only place that works; for a personal opt-in, re-declare it in each project's
own `settings.local.json`. Confirm with `claude plugin list` run FROM the
project directory — running it from `$HOME` shows it enabled and hides the
problem. (Verified 2026-07-27: claude-mem's SessionStart banner was missing in
one project for exactly this reason.)

The `@<marketplace-name>` suffix must match the name the
marketplace declares in its `marketplace.json` — usually the repo name, but
verify from the `marketplace add` output (e.g. `coreyhaines31/marketingskills`'s
marketplace name is `marketingskills`, and `thedotmack/claude-mem`'s is
`thedotmack`, **not** `claude-mem`). Adding entries to `settings.local.json`
is fine; deleting/restructuring it needs a yes (same rule as the Red-flags
table). Tell the user to **restart** Claude Code afterward — `claude plugin
install` notes "restart required".

**Recording it there is load-bearing, and it applies at render time — not
instantly (2026-07-27).** Claude Code's setting sources are exactly `user` /
`project` / `local` (`claude --setting-sources`), where `local` means the
*project's* `.claude/settings.local.json`. There is no user-scope
`settings.local.json` source — invalid JSON in `~/.claude/settings.local.json`
produces no CLI error at all, because the file is never parsed. What makes the
entry above real is `installer/scripts/render_settings.py`, which merges it into
`~/.claude/settings.json` on every `install.sh` run (step 5). So the order
matters: install the plugin, record it here, **then run install.sh**, and only
then is it enabled for the next session.

`claude plugin install/enable -s user` writes into the rendered
`~/.claude/settings.json` directly, which is enough for the current session; the
next render captures it back into `settings.local.json` so it is not lost. Either
way, verify rather than assume:

```bash
claude plugin list | grep -A3 '<plugin>@<marketplace>' | grep Status   # must read "enabled"
```

"Installed" is not "enabled": `plugin list` reports both, and all four 4k extras
were found installed-but-disabled two days after a sweep because the only record
of them was in a file nothing read.

**Caution — `claude-mem`:** it injects prior-session context at session start,
which *adds* to the always-on input on every session, and overlaps
the existing memory stack (`MEMORY.md`, OMC wiki, omp secretary). Offer it as a
measured experiment, not a default — see `docs/ai-usage-fitting.md`.

**Prerequisite check — `claude-mem` needs the `bun` runtime (2026-07-27 gap,
found live).** `claude-mem`'s own `hooks/hooks.json` routes every hook
(`SessionStart`, `PostToolUse`, `Stop`, etc.) through `scripts/bun-runner.js`,
which requires the `bun` binary. Run this check whether `claude-mem` is newly
offered above OR **already installed** — "installed" only means the plugin
directory + hook manifest exist, not that the hooks can execute. Verified live:
plugin installed 2026-07-25, zero observation/DB data anywhere on disk two days
later — every hook invocation was silently failing on `bun: command not found`.

```bash
if command -v bun >/dev/null 2>&1 || [ -x "$HOME/.bun/bin/bun" ]; then
  echo "(4k) bun present — claude-mem hooks can run"
else
  echo "(4k) claude-mem is installed (or being installed) but bun is MISSING"
fi
```

If `claude-mem` is installed/being installed and `bun` is missing, **ask** (same
detect-then-ask governance as the rest of this section):

> "`claude-mem`은 hook 실행에 `bun` 런타임이 필요한데 이 머신엔 없습니다.
> 설치할까요? (`curl -fsSL https://bun.sh/install | bash` — Homebrew tap
> 경로는 Xcode/CLT가 오래된 머신에서 실패할 수 있음, 실측 확인됨)"

On yes:

```bash
curl -fsSL https://bun.sh/install | bash
```

**Then add the PATH export to `~/.zprofile`, not just the installer's default
`~/.zshrc`.** `claude-mem`'s hook commands resolve PATH via
`$SHELL -lc 'echo $PATH'` — a login-but-non-interactive invocation. zsh sources
`.zprofile` for that, but **not** `.zshrc` (interactive-only by zsh's own
design). The bun installer only appends to `.zshrc`, so a bare install leaves
the hook's own PATH-resolution trick unable to find it — verified live:
`zsh -lc 'command -v bun'` failed until the export was duplicated into
`.zprofile`.

```bash
grep -q 'BUN_INSTALL' ~/.zprofile 2>/dev/null || cat >> ~/.zprofile <<'EOF'

export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$PATH"
EOF
zsh -lc 'command -v bun && bun --version'   # must print a path + version
```

Tell the user hooks take effect from the **next** session (`SessionStart` fires
once per session start) — this sync cannot backfill data for the current one.

**4l. Code graphs for THIS project? (detect-then-ask, once per project)**

`install.sh` puts the graph CLI on the machine but decides nothing about which
*repo* gets a graph, and `runtime/hooks/graph-offer.sh` — the only automatic
prompt — is shown once per project and then never again. A project whose graph
is code-only stays silent about graphify's prose pass forever. Measured on the
obsidian vault 2026-08-11, back when a second tool's index also short-circuited
the hook: an index present since 08-03, no `graph.json` anywhere, the hook's own
marker never written, and `/graphify` never once surfaced. That second tool is
gone as of 2026-08-29 and the short-circuit with it, but the once-per-project
contract remains — a sync is a deliberate invocation, so it is the right place
to close the hole from the other side.

**The project here is the session's working directory, not `~/claudebase`.**
Every other step `cd`s into the repo being synced; this one must not.

```bash
PROJ="${CLAUDE_PROJECT_DIR:-$PWD}"          # where the user invoked the sync
gout="${GRAPHIFY_OUT:-graphify-out}"
gfy=no; gjson=""
for d in "$gout" .graphify graphify-out; do
  [ -f "$PROJ/$d/graph.json" ] && { gjson="$PROJ/$d/graph.json"; gfy=yes; break; }
done
md=$(git -C "$PROJ" ls-files 2>/dev/null | grep -ci '\.md$')
code=$(git -C "$PROJ" ls-files 2>/dev/null \
  | grep -icE '\.(py|js|jsx|ts|tsx|go|rs|java|kt|c|h|cc|cpp|hpp|rb|php|swift|sh|bash|cs|scala|lua)$')

# A graph.json is NOT evidence the prose is in it. The free AST pass emits zero
# nodes for markdown, and graph-refresh.sh builds exactly that pass — so a
# code-only graph is indistinguishable from a full one by file existence alone.
# Count the markdown nodes instead; that is the number the prose question turns
# on. Measured on the obsidian vault 2026-08-11: graph.json present, 1,017
# nodes, 728 .py + 140 .json + 85 .cpp + 36 .sh, and **0** from .md — while 822
# markdown files sat tracked and unindexed.
gfy_md=0
[ -n "$gjson" ] && gfy_md=$(python3 -c "
import json, sys
g = json.load(open(sys.argv[1]))
print(sum(1 for x in g.get('nodes', []) if (x.get('source_file') or '').endswith('.md')))
" "$gjson" 2>/dev/null || echo 0)

echo "(4l) $PROJ — graphify=$gfy (md nodes: $gfy_md) | tracked: ${code} code, ${md} md"
```

Report that line in the Outputs table **every** run — state costs nothing, and a
user who merely sees `graphify=no` has already learned the thing this step
exists for. Whether to *ask* is gated once per project, mirroring the hook's
contract (marker written when the question is emitted, so ignoring it answers):

```bash
git_dir="$(git -C "$PROJ" rev-parse --git-dir 2>/dev/null)"
case "$git_dir" in
  "")  marker="$HOME/.claude/graph-offered/$(basename "$PROJ")-$(printf '%s' "$PROJ" | cksum | cut -d' ' -f1).sync" ;;
  /*)  marker="$git_dir/claudebase-graph-sync-asked" ;;
  *)   marker="$PROJ/$git_dir/claudebase-graph-sync-asked" ;;
esac
[ -e "$marker" ] && echo "(4l) already asked for this project — report state, do not ask again"
```

Marker absent → ask with `AskUserQuestion`, as **two separate decisions**. They
differ by three orders of magnitude in cost, and bundling them makes a user
decline a five-second build to avoid a five-hour one:

- **`gfy=no` with `code` ≥ 20** → the free tree-sitter build.
  Offline, seconds, one command: `graph-init`. Nothing to weigh; just offer it.
- **`gfy_md` = 0 with a substantial `md` count (≥50)** → graphify's prose
  semantic pass, the one nothing else ever names. Note the trigger is the
  markdown-node count, **not** `gfy`: a code-only graph built by
  `graph-refresh.sh` sets `gfy=yes` while leaving every note invisible, so
  gating on file existence would skip exactly the repos that need this most.
  Put the price *in the question* so a yes is informed: it runs an LLM per
  chunk, `--max-concurrency` is forced to 1 on the `claude-cli` backend, and one
  774-note vault measured 5.3 min/chunk across 58 chunks — about five hours.
  `graph-init` does **not** cover this; markdown yields zero tree-sitter nodes
  no matter how healthy the resulting node count looks.

**Never run the semantic pass from inside the sync.** Hand the user `/graphify`
and let them start it deliberately — a sync that blocks for hours is a sync
nobody finishes, and step 9.5 cannot audit a run that never returns. Running
`graph-init` on a yes is fine, but read its exit code: **2** means a vendored
tree filled the graph, and that result must be purged (`graph-init --purge`),
never kept — an empty-shell graph is worse than none, because the PreToolUse
guards then force every session to consult it.

Write the marker once the question has been put to the user:

```bash
mkdir -p "$(dirname "$marker")" && date -u +%Y-%m-%dT%H:%M:%SZ >"$marker"
```

**4m. tokensave 잔재? (detect-then-ask, once per machine)**

tokensave was removed from this repo on **2026-08-25** — nothing routed to it. It
was wired as a user-scope MCP server, three hooks, and a per-repo SQLite index, so
a machine that installed it before that date still carries all of it: `install.sh`
stops *installing* it but cannot uninstall what is already there. This step finds
the leftovers and asks once.

Why it earns a step of its own rather than a line in 4j: 4j classifies servers it
finds in the config and asks about *upgrading* them. A server the repo no longer
ships is not an upgrade question, and 4j would keep proposing one forever.

```bash
tk_bin="$(command -v tokensave 2>/dev/null || true)"
[ -n "$tk_bin" ] || { [ -x "$HOME/.local/bin/tokensave" ] && tk_bin="$HOME/.local/bin/tokensave"; }
tk_mcp=$(python3 - <<'PY'
import json, os
p = os.path.expanduser("~/.claude.json")
try: d = json.load(open(p))
except Exception: raise SystemExit(print("unreadable"))
hits = ["user"] if "tokensave" in (d.get("mcpServers") or {}) else []
hits += [k for k, v in (d.get("projects") or {}).items()
         if "tokensave" in (v.get("mcpServers") or {})]
print(",".join(hits) or "none")
PY
)
tk_rules=no; [ -f "$HOME/.claude/rules/tokensave.md" ] && tk_rules=yes
tk_local=no; grep -q tokensave "$HOME/.claude/settings.local.json" 2>/dev/null && tk_local=yes
tk_hooks=$(grep -c tokensave "$HOME/.claude/settings.json" 2>/dev/null || echo 0)
tk_idx=$(find "$HOME" -maxdepth 4 -name .tokensave -type d 2>/dev/null | grep -v '/\.Trash/' | tr '\n' ' ')
tk_proc=$(ps -eo comm | grep -cx tokensave || true)

echo "(4m) binary=${tk_bin:-none} mcp=$tk_mcp rules=$tk_rules settings.local=$tk_local rendered-hits=$tk_hooks proc=$tk_proc"
echo "(4m) indexes: ${tk_idx:-none}"
```

Everything `none`/`no`/`0` → report the line and move on; this machine is clean.
Any hit → **ask with `AskUserQuestion`** (one question: remove the leftovers, or
keep tokensave as a machine-local tool). Removal is not urgent — an unregistered
binary costs nothing — so a "keep" answer is legitimate and needs no argument.

On a yes, in this order (measured on macOS 2026-08-25 while doing exactly this):

```bash
claude mcp remove tokensave --scope user     # → "Removed MCP server tokensave from user config"
brew uninstall tokensave                     # macOS (175.8 MB); Linux: cargo uninstall tokensave
brew untap aovestdipaperino/tap              # macOS only, optional — the tap serves nothing else
trash ~/.tokensave <each path from tk_idx>   # 45 MB across 3 repos on the machine measured
```

Three traps, all measured:

- **`pkill -f 'tokensave serve'` does not kill them.** Two attempts left all three
  processes at unchanged `etime`; `-f` also matches the invoking shell's own
  command line, which is most of why the result is unreadable. What worked was
  killing by PID off an exact-name match:
  `ps -eo pid,comm | awk '$2=="tokensave" {print $1}' | xargs kill`. They are
  children of live sessions and die on their own when those sessions end, so this
  is optional cleanup, not a prerequisite.
- **Clean `settings.local.json` and `settings.json` in the SAME pass, before the
  next render.** On the machine measured, `settings.local.json` carried a full
  `GATEGUARD_EXEMPT_GLOBS` string plus two security-review strings naming
  `.tokensave`. Cleaning only that file and re-rendering put all three **back**:
  `render_settings.plan` computes `diff_overrides(existing, expected)` against the
  still-dirty rendered file and captures the difference as a fresh per-machine
  override. Only `hooks` is exempt (`BASELINE_OWNED_KEYS`), which is why the three
  hook entries went away on the first render and these strings did not. Edit both
  files, then run install.sh, then re-grep both — measured clean on the third
  render, 2026-08-25.
- **`~/.claude/rules/tokensave.md`** is where tokensave's own installer wrote its
  prompt rules (documented in 4j). Absent on the machine measured — check anyway,
  and delete it with the rest.

Report the `(4m)` lines in the Outputs table every run, same contract as 4l.

**4n. om\* 스토어 census 와 drift (두 계측기 — 명령을 공유하지 않는다)**

The om\* harnesses are consolidating their per-harness state stores (`.omp`,
`.oms`, `.omd`, `.omha`, `.orchestration`) into one `.hq/` root per anchor.
Spec: `oh-my-orchestrator` `skills/harness/references/store-spec.md`. The tool
is `runtime/bin/migrate-om-store.sh` in this repo; it is dry-run by default and
never deletes without a typed terminal confirmation, so both commands below are
safe to run on any machine.

This step exists because the migration is **per machine**. A repo can be fully
cut over in git and still leave a machine sitting on an un-migrated legacy store
— or worse, one that is still being written to while the deployed hooks read the
new store. Neither condition produces an error anywhere.

```bash
CB="${CLAUDEBASE_DIR:-$HOME/claudebase}"
bash "$CB/runtime/bin/migrate-om-store.sh" census                 # (4n-a) roster
```

`census` is the **roster** instrument: the store-spec §9 fixed `find` at
unbounded depth (a `-maxdepth 6` variant missed three real anchors at depths
7–8), crossed with `git ls-files` for the tracked count. Exclusions are
*patterns*, not a count — the plugin cache grows one `.omha` per deployed
version (2 when §9.2 was written, 5 by 2026-08-28), so any roster pinned to a
number goes stale on the next release. Report the `in scope` / `excluded by
pattern` line plus any row whose GATE column reads `legacy` (an anchor with no
`.hq/.anchor` yet).

```bash
for a in "$HOME/ksm_Obsidian" "$HOME/claudebase" "$HOME/Desktop/workspace"; do
  [ -d "$a" ] && bash "$CB/runtime/bin/migrate-om-store.sh" drift "$a"
done                                                              # (4n-b) split-brain
```

`drift` is the **split-brain** instrument, and it deliberately shares no command
with census. Its discovery is the ledger — `.hq/config/migrated.jsonl` — and its
comparison is legacy-file mtime against that ledger's ISO timestamp. Exit 5
means at least one legacy file was written *after* this anchor was migrated,
i.e. something on this machine is still writing to the old path.

Why two instruments rather than one: each is blind exactly where the other
sees. Census walks directories, so it finds an anchor nobody has ever migrated
but cannot tell a live legacy store from a dormant one. Drift reads the ledger,
so it judges liveness but is silent on an anchor that has no ledger row at all.
Sharing a command between them would collapse both into a single detector with
one blind spot and no way to notice.

```bash
for a in "$HOME/ksm_Obsidian" "$HOME/claudebase" "$HOME/workspace"; do
  [ -d "$a" ] && bash "$CB/runtime/bin/migrate-om-store.sh" audit "$a"
done                                                              # (4n-c) config drift
```

`audit` is the **configuration** instrument, and it is here because store-spec
§5 (four `.gitignore` lines) and §2 (three `merge=union` attributes) are the
*seed* for a new anchor — nothing re-applies them to an anchor that already
exists. Every finding in the 2026-08-31 round was that gap: `stonefish_ws` was
seeded from a two-line §5 and committed `hq`'s write lock; this repo and the
vault never picked up `**/.harness.lock/` when omo 0.21.0 added it, and had not
noticed only because no long-running harness session has run here yet; the
vault's `merge=union` rule pointed at a legacy path for three days after the
purge deleted it. Exit 7 means the anchor's git config no longer matches the
spec it was built from.

It probes **behaviour** (`git check-ignore` / `check-attr`), never line text —
a rule inherited from a parent `.gitignore` is equally valid, and text matching
would fail a correct anchor while passing a wrong one. Two of its probes are
*negative*: `config/migrated.jsonl` and `community/INDEX.md` must **not** be
ignored, because a repo ignoring `.hq/` wholesale satisfies every positive check
while hiding the tracked layers. An empty `.hq/` is skipped as "not an anchor"
(measured on the `oh-my-orchestrator` checkout, where a leftover empty directory
produced two false failures).

Exit 7 is usually safe to fix during a sync — adding an ignore line for a file
that does not exist yet untracks nothing — but **check `git status --porcelain`
for `D` lines before committing**, because widening an ignore rule over a file
that is already tracked does remove it.

**Stated limits — do not report a clean run as full coverage.** Drift cannot
see an ignored layer (nothing dates the write) or a no-git anchor
(`~/Desktop/workspace` and its five nested anchors are iCloud, store-spec §8);
those are covered only by the `tar` hashes `migrate-om-store.sh apply` writes to
`~/.claude/hq-snapshots/`. Census cannot see an anchor outside `$HOME`.

On a `legacy` row or a drift exit 5, **ask** with `AskUserQuestion` — do not
migrate as part of a sync. The move is a phase of an in-flight campaign with a
per-anchor user gate (store-spec §7); a sync's job here is to *report* that this
machine is behind, not to advance it.

**4o. code-review-graph 잔재? (detect-then-ask, once per machine)**

`code-review-graph` was removed from this repo on **2026-08-29**, and the reason
was not that it was tried and found wanting — **nothing bound to it.** The three
integration layers differ enormously in how strongly they get consulted, and only
the `PreToolUse` hook is binding; `graphify-guard.sh` named graphify's CLI and no
hook ever named CRG's. Keeping CRG would have meant writing that guard from
scratch; keeping graphify meant deleting CRG. Same shape as 4m, one tool along.

It was wired as a per-project MCP server, a per-repo SQLite index, and a
`.code-review-graphignore`, so a machine that installed it before that date still
carries all of it: `install.sh` stops *installing* it but cannot uninstall what is
already there. Same reason this is its own step rather than a line in 4j — a
server the repo no longer ships is not an upgrade question, and 4j would keep
proposing one forever.

```bash
crg_bin="$(command -v code-review-graph 2>/dev/null || true)"
[ -n "$crg_bin" ] || { [ -x "$HOME/.local/bin/code-review-graph" ] && crg_bin="$HOME/.local/bin/code-review-graph"; }
crg_mcp=$(python3 - <<'PY'
import json, os
p = os.path.expanduser("~/.claude.json")
try: d = json.load(open(p))
except Exception: raise SystemExit(print("unreadable"))
hits = ["user"] if "code-review-graph" in (d.get("mcpServers") or {}) else []
hits += [k for k, v in (d.get("projects") or {}).items()
         if "code-review-graph" in (v.get("mcpServers") or {})]
print(",".join(hits) or "none")
PY
)
crg_local=no; grep -q code-review-graph "$HOME/.claude/settings.local.json" 2>/dev/null && crg_local=yes
crg_hooks=$(grep -c code-review-graph "$HOME/.claude/settings.json" 2>/dev/null || echo 0)
crg_idx=$(find "$HOME" -maxdepth 4 -name .code-review-graph -type d 2>/dev/null | grep -v '/\.Trash/' | tr '\n' ' ')
crg_ign=$(find "$HOME" -maxdepth 4 -name .code-review-graphignore 2>/dev/null | grep -v '/\.Trash/' | tr '\n' ' ')
crg_rules=$(find "$HOME" -maxdepth 5 -path '*/.claude/rules/code-review-graph.md' 2>/dev/null | tr '\n' ' ')
crg_githooks=$(find "$HOME" -maxdepth 4 -path '*/.git/hooks/pre-commit' 2>/dev/null \
  | while read -r f; do grep -ql code-review-graph "$f" 2>/dev/null && printf '%s ' "$f"; done)

echo "(4o) binary=${crg_bin:-none} mcp=$crg_mcp settings.local=$crg_local rendered-hits=$crg_hooks"
echo "(4o) indexes: ${crg_idx:-none}"
echo "(4o) ignore files: ${crg_ign:-none} | rules docs: ${crg_rules:-none}"
echo "(4o) git hooks: ${crg_githooks:-none}"
```

**The git hook is the one that undoes the cleanup, so check it before the index.**
CRG's installer writes `<repo>/.git/hooks/pre-commit` calling `code-review-graph
update`, and `.git/hooks/` is neither tracked nor reachable by any of the other
probes above. Measured on the vault 2026-08-29, in this exact order: the index was
trashed, the removal was committed, and **the commit's own pre-commit hook rebuilt
the index from scratch** — 182 files, 30,969 nodes, schema migrated v1→v9, all of
it printed as INFO on a commit that was removing the tool. Nothing errored. Delete
the hook first, then the index; the reverse order silently reverses itself.

Everything `none`/`no`/`0` → report the lines and move on; this machine is clean.
Any hit → **ask with `AskUserQuestion`** (one question: remove the leftovers, or
keep CRG as a machine-local tool). An unregistered binary costs nothing, so a
"keep" answer is legitimate and needs no argument — but say what a keep means:
nothing in this repo routes to it any more, so it is a tool the user drives by
hand.

On a yes, in this order:

```bash
trash <each path from crg_githooks>                   # FIRST — see above
claude mcp remove code-review-graph --scope project   # per-project; --scope user if 4o said "user"
uv tool uninstall code-review-graph
trash <each path from crg_idx> <each path from crg_ign> <each path from crg_rules>
```

Three things to carry over from 4m, because they are the same traps one tool along:

- **A per-project MCP server lives in the project's `.mcp.json`, not just
  `~/.claude.json`.** The detection above reads `~/.claude.json`; a repo carrying
  its own `.mcp.json` needs `grep -l code-review-graph */.mcp.json` from wherever
  the user keeps repos, and that file is usually **tracked**, so removing the
  entry is a commit in that repo, not a machine-local edit.
- **Clean `settings.local.json` and `settings.json` in the SAME pass, before the
  next render.** `render_settings.plan` diffs against the still-dirty rendered
  file and captures the difference as a fresh per-machine override, so cleaning
  one file and re-rendering puts the string back. `GATEGUARD_EXEMPT_GLOBS` is the
  one that carried `.code-review-graph/**`.
- **Deleting the index goes through `trash`.** User rule "Deletion Safety". The
  indexes are gitignored and regenerable in seconds *by a tool that is being
  uninstalled* — which is exactly the case where a recoverable path matters.

Report the `(4o)` lines in the Outputs table every run, same contract as 4m.

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
- Plugin sync line: `0 fixed`. **Do not also expect `0 updated` — that is no longer reachable.** Since 55880cc, `installer/lib/plugins.sh` appends `--update` unconditionally, and `apply()` increments `counts[Action.UPDATE]` when the plan is built rather than when a plugin actually moves, so `updated` equals the enabled-plugin count on every run — a second, fully no-op pass included (measured 2026-08-31: 18 then 19, the extra being the plugin the first pass installed). Reading that as a regression sends a healthy machine to step 7. The `drift-kept` count may be non-zero — that's expected when reverse drift exists (warn-only is the default; the installer never removes a recipient's own plugins). A `fixed` count that never drops to 0 across passes is a real regression → step 7.
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

Branch on `CB_PUSH_AUTH` (resolved in Pre-flight — **do not re-decide it here**).

**If `CB_PUSH_AUTH=non-owner`:** skip the push gate entirely. If `git log --oneline @{u}..HEAD` shows local commits, do NOT ask "push?" — the user can't. List the commits and surface the forward path instead: keep them on this clone and send to the repo owner as a patch (`git format-patch -1` / `git diff`) or a PR. This is the common case on a distributed clone — being asked to push a repo you don't own is exactly the friction this branch removes.

**If `CB_PUSH_AUTH=owner`** and `git log --oneline @{u}..HEAD` shows local commits:

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

Three things bite between the `cp` and the commit (all three hit on 2026-08-10):

- **The target may gitignore `.claude/` wholesale.** Then the adopted rule file
  cannot be committed, and that is the repo's own decision — per-project Claude
  config stays local there. Check first, and when it is ignored, leave the file
  untracked rather than reaching for `git add -f`; say so in the commit body for
  whatever *is* committable. `git -C <repo> check-ignore -v <path>` answers it in
  one call.
- **`git commit -- <paths>` cannot commit an untracked file.** The paths form is
  the right tool under concurrency (it ignores whatever another session has
  staged), but a brand-new file fails with `error: pathspec '<x>' did not match
  any file(s) known to git` — and the commit does *not* happen, so re-read HEAD
  before assuming it did. `git add <paths>` first, then `git commit -- <paths>`.
- **The target may be a pristine vendored fork**, where adding any of our files
  to the tracked tree is the thing the project forbids. Adopting is still
  possible: write the file, and add it to `<repo>/.git/info/exclude` — a
  local-only ignore that leaves the tracked tree byte-identical to upstream.
  Verify with `git -C <repo> status --porcelain | wc -l` reading `0`.

### 9.5. Pre-completion ask audit (MANDATORY — run before writing the Outputs summary)

This step exists because of a real failure (2026-08-03, obsidian-vault Mac):
the optional-plugins sub-step (4k) and an install.sh WARNING about a missing
optional CLI tool (`code-review-graph`, needs `uv`) were both detected and
even diagnosed in depth — then only written into the Outputs table as a
prose note ("not proposed", "warn-only, skip"). The run was reported
**complete** with two live decisions still open, silently defaulted to
"skip". The user had to notice the gap and demand both be asked before
either got surfaced — on a less attentive machine this would have shipped
with claude-mem and code-review-graph permanently un-offered, no one the
wiser.

**A summary-table mention is NOT a substitute for asking.** Disclosure ≠
consent — a decision buried as one row in a nine-row table is easy to skim
past, and the user can only redirect a choice they were actually asked
about. Before writing the Outputs table, walk this checklist. For each item,
either (a) an actual `AskUserQuestion` call (or, in a harness without one,
an explicit prose question that blocks completion until answered) happened
in *this* run, or (b) the item is genuinely not applicable — there is no
third option, and "I mentioned it in the summary" is not (b).

- [ ] 4e (claude CLI upgrade) — asked if drift found, or N/A (no drift)
- [ ] 4f (OMC upgrade) — asked if drift found, or N/A (no drift)
- [ ] 4g (other plugin updates) — asked if candidates found, or N/A (0 candidates)
- [ ] 4j (MCP server updates) — inventory run, and asked per stale server, or
      N/A (none stale). There is no `claude mcp update` and nothing else in this
      skill enumerates MCP servers, so an unchecked box here is how one goes
      nine minor versions behind without a single line of output saying so.
- [ ] 4k (each of the 4 optional plugins) — asked **individually, one
      question per missing plugin**, or N/A (already installed/enabled).
      "Not proposed because it seemed unwanted" is not N/A — that judgment
      call belongs to the user, not to this skill. This is the exact box
      that got silently unchecked in the 2026-08-03 incident.
- [ ] Any `[install] WARNING: ... not found ...` / `... is missing ...` line
      in the install.sh output about an optional tool it can auto-install —
      this list is intentionally NOT closed (install.sh grows new optional
      deps over time: `jq`, `gemini`, `bun`, `code-review-graph`, whatever
      comes next). Treat every such WARNING as a detect-then-ask candidate
      by default, same governance tier as 4e/4f/4g, unless it is already a
      documented warn-only informational case named elsewhere in this skill
      (e.g. the marketplace cold-start race in 4b). Asked, or N/A (no such
      WARNING appeared).
- [ ] 4l (code graphs for this project) — the state line reported in the
      Outputs table **always**, plus an actual question for each missing
      graph, or N/A (nothing missing, or the once-per-project marker was
      already set). "This project already has a graph" is not N/A: the hook
      that would otherwise ask stops dead at the first graph it finds, which
      is precisely why a repo can carry CRG for months while its owner has
      never heard of `/graphify`.
- [ ] 4n (om\* store census / drift) — asked if `census` printed any row
      whose GATE reads `legacy`, or if `drift` exited 5 on any anchor; or
      N/A (`in scope: 0` / all anchored **and** drift clean on every anchor
      probed). The Outputs table's `4n` row is *disclosure*, not the ask —
      §4n's own rule is that a sync **reports** that this machine is behind
      and never migrates on its own, which only holds if the user is
      actually asked what to do about it. A machine can sit un-migrated
      indefinitely while every run says "complete", because neither
      instrument errors and the owner may not know the migration exists.
- [ ] Step 9 template adoption — asked if `templates/` changed, or N/A

If any box can't be checked yet, **ask now** — do not write the Outputs
table first on the theory that you'll circle back to it. The Outputs table
is written *after* every open item on this list has actually been asked,
never as a way of discharging the obligation to ask.

**A yes to an optional tool needs one more install.sh run.** Installing the
tool is not the same as wiring it in: `uv`, `cargo` and friends are
*prerequisites* install.sh checks for, and the things that depend on them
(`graphify`, the `arxiv` MCP registration) are
installed in the same pass that found the prerequisite missing — so they were
skipped. Install the prerequisite, then run install.sh **again** and confirm
the WARNING is gone before reporting the item as handled:

```bash
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"   # uv / cargo shims
cd ~/claudebase && INSTALL_TOOLS=1 installer/install.sh --verbose 2>&1 \
  | grep -E '^\[install\] (WARNING|install(ing|ed))'
```

Measured 2026-08-10: after `uv` and `cargo` went in, the third pass installed
`graphify` and (then still shipped) `tokensave` and registered both MCP servers. Stopping at the
second pass would have left the user with the tool on disk, nothing using it,
and a run reported complete. Note this pass is *expected* to print action
lines — it is not a step-6 idempotency check, and does not invalidate the one
already done.

## Red flags (STOP if you catch yourself thinking these)

| Thought | Reality |
|---|---|
| "Auto mode is on, I can push" | CLAUDE.md "Push only on explicit instruction" wins. Auto mode says so itself: "shared systems still need explicit user confirmation." |
| "There's a local commit, I'll ask the user to push it" | Only if `CB_PUSH_AUTH=owner`. `claudebase` is a *distribution* repo — most machines are non-owner clones that can't push `origin`. Asking a non-owner "push N commits?" pushes them toward an action they can't take. Resolve `CB_PUSH_AUTH` in Pre-flight; on non-owner, surface the patch/PR forward-path, never a push prompt. |
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
| "They said yes to `uv`/`cargo`, it installed cleanly, that item is done" | Installing the prerequisite is not installing the thing that needed it. install.sh skipped `graphify`/the MCP registrations in the pass that found the prerequisite missing, so they are still absent — run install.sh once more and confirm the WARNING is gone. Reporting "installed" off the prerequisite alone leaves the tool on disk with nothing wired to it (measured 2026-08-10). |
| "I'll note this optional plugin / install.sh WARNING in the Outputs summary instead of asking" | That's disclosure, not consent — the user can't redirect a decision they were never actually asked about, and a row in a nine-row table is easy to skim past. This exact shortcut (4k's optional plugins + a `code-review-graph`/`uv` WARNING both downgraded to summary notes) shipped a run reported "complete" with two live decisions silently defaulted to "skip" (2026-08-03). Run the Step 9.5 pre-completion ask audit before writing the Outputs table — every detect-then-ask item needs an actual question, not a mention. |
| "This project already has a code graph, so 4l has nothing to report" | Having *a* graph says nothing about having the *right* one. The two tools answer different questions and **both** free passes contribute **zero nodes** for markdown, so a prose repo with a healthy-looking CRG index has no index of its notes at all — and since tokensave's removal (2026-08-25) nothing indexes prose for free at all. `graph-offer.sh` makes exactly this mistake by design — it exits on the first graph it finds — which is why a vault carried CRG from 08-03 to 08-11 while `/graphify` was never once named to its owner. Report both states every run; ask about the missing ones. |

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
| MCP servers (4j) | per server: `<name>: up to date / X → Y (upgraded) / X → Y (deferred) / always-latest (npx) / remote` — plus `reconfigure run: <tool>` if a version bump needed one |
| Optional plugins (4k) | `<per plugin: enabled / offered, declined / already present — or "none offered">` |
| Code graphs, this project (4l) | `CRG=<yes/no> graphify=<yes/no>` + `<"built" / "offered, declined" / "already asked (marker set)" / "nothing missing">` |
| tokensave leftovers (4m) | the two `(4m)` lines + `<"removed" / "offered, declined" / "clean">` |
| om\* store census / drift (4n) | `in scope: N, excluded: M` + `<"all anchored" / "K legacy rows: …">` + `<"drift clean" / "SPLIT-BRAIN in …">` — report both, never fold one into the other |
| Actions taken | `<commits, file writes, install runs>` |
| Local commits awaiting push | `<list, or "none">` — with explicit ask if non-empty |
| Adoption questions | `<list, or "none">` |

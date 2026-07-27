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

`headroom` (opt-in — see `docs/headroom.md` in claudebase) wraps Claude
Code through a local compression proxy to cut input tokens. It's a per-machine
pip tool that `install.sh` does **not** install, so a freshly-synced machine may
be missing it. Detect and offer, never auto-install (pip is non-idempotent and
needs Python >=3.10):

```bash
if command -v headroom >/dev/null 2>&1; then
  echo "(4j) headroom present: $(headroom --version 2>/dev/null)"
  headroom doctor 2>&1 || true   # present != active — read the proxy/wrap_marker/savings rows
else
  echo "(4j) headroom not installed"
fi
```

**Present is not active — check both.** `pip install` puts the CLI on the machine
but changes nothing about how `claude` launches, so the common state is
*installed and never routed*: `command -v headroom` succeeds while every request
still bypasses the proxy. `headroom doctor` names it — `proxy: not reachable` +
`wrap_marker: no wrap marker found` + `savings: no savings recorded yet` together
mean the tool has never been used on this machine. Report that in the summary
(installed but inactive) rather than treating a successful `command -v` as done;
the fix is a launch-time `headroom wrap claude`, not a reinstall.

**`claude: not routed` alone is NOT proof of inactive — but check whether this
machine has been re-rendered first.** `check_claude_routing` reads
`~/.claude/settings.json` only (`headroom/cli/doctor.py`) and never opens
`settings.local.json`. Since `installer/scripts/render_settings.py` landed, the
installer merges the two, so on a machine that has run `install.sh` since adding
the env block, `~/.claude/settings.json` *does* contain the proxy URL and doctor
reports it accurately. The false negative survives only where the render has not
run yet — and there the env block is not routing anything either, so the fix is
the same: run `installer/install.sh`.

`settings.local.json` remains **the correct place to write it**: `config/settings.json`
is synced to every machine and would ship the proxy URL to hosts with no proxy
running. Read the rows together before concluding:

| doctor rows | verdict |
|:---|:---|
| `proxy: not reachable` + `savings: no savings recorded yet` | genuinely never used |
| `proxy: pass` + `savings: pass` (non-zero, "last request just now") | **routing fine** — the `claude` warn is a false negative |

The authoritative check is whether a NEW `claude` process increments the proxy's
request counter (`curl -s http://127.0.0.1:8787/stats` → `.summary.api_requests`
before/after) — `savings` being non-zero is the same evidence after the fact.
Report "active via settings.local.json (doctor's claude row is a false negative
on a machine that has not re-rendered)", not "installed but inactive".

Caveat to carry into the summary: with this env set, a **dead proxy fails every
request**. The proxy is not a service — it dies with the container/host, so
`headroom proxy` must be running. Rollback is deleting the `env` block.

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

Then point at the two ways to actually route through it, and pick by how
`claude` gets launched on this machine:

| Launch style | How to route |
|:---|:---|
| Human types `claude` in a terminal | `headroom wrap claude` — per-launch, nothing persisted, easiest to undo |
| `claude` is started by something else (container entrypoint, harness, daemon) | `"env": {"ANTHROPIC_BASE_URL": "http://127.0.0.1:8787"}` in **`settings.local.json`**, then `installer/install.sh` to render it, + a running `headroom proxy` |

There is no wrap point to hook when a harness spawns `claude` for you, so the
env route is the only option there — and it must go in `settings.local.json`,
never `config/settings.json` (a synced file: the proxy URL would ship to every
machine and break the ones with no proxy running).

**Name what routing costs before the user picks either row: Remote Control and
the 1M context window both stop working.** Claude Code gates them on the base URL
client-side, so *any* routing disables them — `wrap` included, since it sets the
same variable for its child — for as long as it is in effect (upstream
#746/#1158). Compression and RC + 1M cannot both be on. On a machine driven
remotely, or one running a 1M-context model, the honest recommendation is to
leave it unrouted and reach for `headroom wrap claude` only on the sessions that
want compression. Report the outcome in the summary.

**If the user does route, check the port before anything else: one port per
machine, from the `18787+` block, never the default `8787` on two machines.**
VS Code Remote-SSH forwards a remote machine's listening ports to the *same*
local port, so a second machine on the default finds `localhost:8787` already
answering — with the **other** machine's proxy. A persistent deployment bound
there cannot bind and keepalive-respawns forever (`last exit code = 3`) while
`headroom install status` still reports `healthy`, because the forward answers
the health probe. So `status: healthy` is not proof the local proxy is the one
replying — confirm with `lsof -nP -iTCP:<port> -sTCP:LISTEN` that a `Python`
process owns the socket, not the editor's helper. There is no central allocation
list — the port is per-machine state, so pick any free number in the block and
let that `lsof` check settle ownership; it catches a forward that a stale list
would have called free. Record the choice in this machine's own
`settings.local.json`. Bind `127.0.0.1` only (on a flat overlay network — Tailscale,
WireGuard, ZeroTier — `0.0.0.0` publishes an unauthenticated
credential-forwarding proxy to every node), and point `ANTHROPIC_BASE_URL` at
this machine's own loopback, never another host's address.

**If present, check whether it is stale (same detect-then-ask gate).** `install.sh`
never installs or upgrades headroom, so a machine can sit on an old version
indefinitely. Compare against PyPI using the interpreter that owns the installed CLI:

```bash
# Derive the interpreter from the installed CLI's shebang — do NOT reuse the
# python3.1x probe from the install path above. headroom often lives in its own
# venv (e.g. ~/.claude/.headroom-venv), so probing picks an interpreter that has
# no headroom-ai and the check silently reports "up to date".
HPY="$(sed -n '1s|^#!||p' "$(command -v headroom)")"
if "$HPY" -m pip show headroom-ai >/dev/null 2>&1; then
  "$HPY" -m pip list --outdated 2>/dev/null | grep -i '^headroom-ai' \
    || echo "(4j) headroom up to date"
else
  echo "(4j) cannot resolve headroom's interpreter — check the upgrade manually"
fi
```

If a newer version shows, **ask** before upgrading — never auto-run it (same reason as
the install gate below):

> "`headroom` is on vX, vY is available. Upgrade now? (`pip install -U "headroom-ai[all]"`)"

On yes: `"$HPY" -m pip install -U "headroom-ai[all]"`, then `headroom doctor`. **Restart the
proxy before reading the result** — a running `headroom proxy` keeps serving the old code
until it is restarted, so doctor's `version` row (which compares the live proxy against the
installed package) reports a mismatch that is stale-process, not a real drift. Report the
outcome in the summary.


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
which *adds* to the always-on input that headroom (4j) is cutting, and overlaps
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
| headroom CLI (4j) | `<"active (vX, routed via settings.local.json)" / "present (vX) but never routed" / "installed" / "upgraded vX -> vY" / "upgrade offered, deferred" / "offered, declined" / "not installed">` |
| Optional plugins (4k) | `<per plugin: enabled / offered, declined / already present — or "none offered">` |
| Actions taken | `<commits, file writes, install runs>` |
| Local commits awaiting push | `<list, or "none">` — with explicit ask if non-empty |
| Adoption questions | `<list, or "none">` |

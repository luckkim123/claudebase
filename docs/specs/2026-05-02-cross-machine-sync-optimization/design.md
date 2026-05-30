# Cross-machine sync optimization (2026-05-02)

## Context

Two machines diverged: a Linux workstation (PKRC sonar work) and macOS (TS/Linear work). Each enabled different plugins, and the linux machine accumulated several tmux improvements (`focus-events`, `escape-time`, `tmux-256color`, OSC52, etc.). This spec records the reconciliation that brings both into the canonical repo while keeping each machine's specifics local.

## Decisions

### Plugin split: intersection-as-common + per-machine `settings.local.json`

- **Common (`claude/settings.json`)** = the 15 plugins both machines had enabled. These are explicitly proven multi-machine-useful.
- **Per-machine** = `~/.claude/settings.local.json` (already gitignored via `*.local.json`). Claude Code merges this on top of the common file by `enabledPlugins` key. Local can also disable a common plugin (`"name": false`).
- **Linux extras** (added on this machine's local): `agent-sdk-dev`, `asana`, `plugin-dev`, `remember`, `atomic-agents`, `data-engineering`.
- **macOS migration** (must be done by hand on the other machine after `git pull`): create `~/.claude/settings.local.json` with `typescript-lsp` and `linear`. Documented in README troubleshooting.

Rationale: union risks unused-plugin hooks firing everywhere; either-side-wins risks losing the other machine's curated set. Intersection keeps the common file as a *minimum guarantee* rather than a guess.

### tmux.conf: repo as base + 7 additions

The repo already has the more sophisticated config (cross-platform `COPY_CMD`/`PASTE_CMD`, OSC52, `focus-events`, `escape-time`, `history-limit`, double/triple-click branching, `BASH_SILENCE_DEPRECATION_WARNING`). We adopt repo as base and merge in the linux machine's nice-to-haves:

1. `default-terminal "tmux-256color"` (replaces `screen-256color`)
2. `terminal-overrides ",*256col*:Tc"` (broader than `xterm-256color`-only)
3. `renumber-windows on`
4. Splits and `new-window` inherit `#{pane_current_path}`
5. `prefix + r` to reload config
6. `status-right` includes session name and date

### `permissions.defaultMode=auto` promoted to common

Linux had it, repo did not. Without promotion, the next pull on the other machine would silently drop it.

### install.sh refinements

- Skip backup + relink when target is already a symlink to the correct source (idempotency).
- Replace `eval "$@"` with bash-array execution in the `run` helper (small injection-surface reduction).
- Auto-create `platform/{macos,linux,windows}/.gitkeep` so the `[[ -f $REPO_DIR/platform/$PLATFORM/install.sh ]]` branch in install.sh has a real directory to look in.
- Print a hint about `settings.local.json` after install if it doesn't exist.

The core structure (idempotent, symlink-or-copy, `--dry-run`, timestamped backups) stays.

### New docs

- `README.md` gains a "Per-machine local plugins" section + macOS migration note.
- `templates/settings.local.example.json` shows the local-overrides shape.
- `CLAUDE.md` at repo root: rules for Claude Code working *in this repo* (no real secrets in commits, commit conventions, push only on explicit instruction).

## Out of scope

- MCP server changes (no servers configured currently).
- Plugin marketplace tracking beyond `enabledPlugins` (per existing rule #7).
- Project-level `.claude/` directories — those live in each project's repo.

## Migration steps (this machine)

1. Clone repo to `~/claude-settings` (re-clone, since `/tmp` copy was for inspection).
2. Apply edits in repo per sections above.
3. Run `./install.sh` → symlinks `~/.claude/settings.json` and `~/.tmux.conf`.
4. Create `~/.claude/settings.local.json` with the six linux-only plugins.
5. Verify: `tmux source ~/.tmux.conf`, `tmux show-options -sg | grep focus-events` (= on), Claude Code restart and check that linux-only plugins still load.

## Migration steps (other machine, when next pulled)

1. `cd ~/claude-settings && git pull`
2. Create `~/.claude/settings.local.json`:
   ```json
   {
     "enabledPlugins": {
       "typescript-lsp@claude-plugins-official": true,
       "linear@claude-plugins-official": true
     }
   }
   ```
3. Restart Claude Code.

## Risks

| Risk | Mitigation |
|---|---|
| Other machine forgets to add `settings.local.json` after pull → loses 2 plugins | README troubleshooting section. The plugins remain installed in `~/.claude/plugins/`, just not enabled. |
| Linux `~/.tmux.conf` overwritten on install | `install.sh` auto-backs up to `~/.claude/.backup-YYYYMMDD-HHMMSS/`. |
| `permissions.defaultMode=auto` surprise on machines that hadn't enabled auto mode | Documented in commit message; can be overridden in local. |

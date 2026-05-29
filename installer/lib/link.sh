# shellcheck shell=bash
# installer/lib/link.sh — filesystem symlinking primitives + their callers.
#
# Source order: after lib/args.sh (needs COPY_MODE, CLAUDE_HOME, DRY_RUN) and
# lib/log.sh (needs log/debug/run).
#
# Primitives:
#   remove_if_exists TARGET            — rm -f if TARGET exists, no backup
#   already_linked TARGET SRC          — true iff TARGET is a symlink → SRC
#   link_or_copy SRC DEST              — symlink (or cp -R when --copy)
#
# Wrappers (each one corresponds to a numbered stage in install.sh):
#   link_settings_and_md               — stage 1+2+2b: ~/.claude/{,settings.json,CLAUDE.md}
#   link_tmux_conf                     — stage 4: ~/.tmux.conf
#   link_skills_and_agents             — stages 4b+4c: per-skill and per-agent links
#
# Stage 3 (mcp.json render) is NOT here — it's in lib/secrets.sh because the
# template substitution is the real concern, not the linking.

remove_if_exists() {
  # Clear a path so a fresh symlink (or rendered file) can be placed there.
  # No backup is made — recovery is via git history. See repo CLAUDE.md
  # ("Idempotency is non-negotiable" / "Don'ts: backups in install").
  local target="$1"
  if [[ -L "$target" ]] || [[ -e "$target" ]]; then
    run rm -f "$target"
  fi
}

# already_linked TARGET SRC — true if TARGET is a symlink resolving to SRC
already_linked() {
  local target="$1" src="$2"
  [[ -L "$target" && "$(readlink "$target")" == "$src" ]]
}

link_or_copy() {
  local src="$1" dest="$2"
  [[ -e "$src" ]] || { log "skip (missing source): $src"; return; }
  if [[ $COPY_MODE -eq 0 ]] && already_linked "$dest" "$src"; then
    debug "already linked: $dest -> $src (skip)"
    return
  fi
  remove_if_exists "$dest"
  if [[ $COPY_MODE -eq 1 ]]; then
    run cp -R "$src" "$dest"
    log "copied:  $dest"
  else
    run ln -s "$src" "$dest"
    log "linked:  $dest -> $src"
  fi
}

# Stage 1+2+2b — ~/.claude/{,settings.json,CLAUDE.md}.
link_settings_and_md() {
  [[ -d "$CLAUDE_HOME" ]] || run mkdir -p "$CLAUDE_HOME"
  link_or_copy "$REPO_DIR/config/settings.json" "$CLAUDE_HOME/settings.json"
  link_or_copy "$REPO_DIR/config/CLAUDE.md"     "$CLAUDE_HOME/CLAUDE.md"
}

# Stage 4 — shell config (Unix only).
link_tmux_conf() {
  [[ -f "$REPO_DIR/shell/tmux.conf" ]] && link_or_copy "$REPO_DIR/shell/tmux.conf" "$HOME/.tmux.conf"
}

# Stage 4b+4c — symlink each user-scope skill subdir and each agent .md so we
# don't clobber user-managed entries under ~/.claude/{skills,agents}/.
link_skills_and_agents() {
  if [[ -d "$REPO_DIR/runtime/skills" ]]; then
    run mkdir -p "$CLAUDE_HOME/skills"
    for skill_dir in "$REPO_DIR/runtime/skills"/*/; do
      [[ -d "$skill_dir" ]] || continue
      local skill_name="${skill_dir%/}"; skill_name="${skill_name##*/}"
      link_or_copy "${skill_dir%/}" "$CLAUDE_HOME/skills/$skill_name"
    done
  fi
  if [[ -d "$REPO_DIR/runtime/agents" ]]; then
    run mkdir -p "$CLAUDE_HOME/agents"
    for agent_file in "$REPO_DIR/runtime/agents"/*.md; do
      [[ -f "$agent_file" ]] || continue
      local agent_name="${agent_file##*/}"
      link_or_copy "$agent_file" "$CLAUDE_HOME/agents/$agent_name"
    done
  fi
}

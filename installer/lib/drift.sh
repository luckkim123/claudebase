# shellcheck shell=bash
# installer/lib/drift.sh — post-install diagnostic: warn when Claude Code has
# auto-modified the symlinked config/settings.json so the user can review.
#
# Source order: after lib/log.sh.
#
# Exposes:
#   check_settings_drift   — print a one-line drift notice if the worktree
#                            shows uncommitted changes to config/settings.json.
#
# Why: config/settings.json is symlinked into $CLAUDE_HOME, so the Claude CLI
# writes straight back into the repo when it auto-formats or persists new
# settings. The user decides to commit, discard, or update the canonical file.
# This is a warning only — never fails the installer.

check_settings_drift() {
  command -v git >/dev/null 2>&1 || return 0
  [[ -d "$REPO_DIR/.git" ]] || return 0
  if [[ -n "$(git -C "$REPO_DIR" status --porcelain config/settings.json 2>/dev/null)" ]]; then
    log "drift: config/settings.json modified by Claude CLI — review with: git -C $REPO_DIR diff config/settings.json"
  fi
}

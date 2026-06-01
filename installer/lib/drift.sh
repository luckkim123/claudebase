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

  # (a) Soft drift notice — any uncommitted change (formatting, a deliberate edit).
  if [[ -n "$(git -C "$REPO_DIR" status --porcelain config/settings.json 2>/dev/null)" ]]; then
    log "drift: config/settings.json modified by Claude CLI — review with: git -C $REPO_DIR diff config/settings.json"
  fi

  # (b) CRITICAL content-integrity check — a shrink that DROPPED critical keys is
  # categorically worse than a formatting drift. Reuse the SAME manifest +
  # validator the pre-commit hook uses (one implementation, no disagreement).
  local verify py
  verify="$REPO_DIR/installer/lib/settings_verify.py"
  py="$(command -v python3 || command -v python || true)"
  if [[ -n "$py" && -f "$verify" ]]; then
    if ! "$py" "$verify" "$REPO_DIR/config/settings.json" >/dev/null 2>&1; then
      log "CRITICAL: config/settings.json is MISSING critical keys (CLI shrink). Details:"
      "$py" "$verify" "$REPO_DIR/config/settings.json" 2>&1 | sed 's/^/         /' || true
      log "         restore with: $REPO_DIR/installer/bin/restore-settings.sh"
    fi
  fi
}

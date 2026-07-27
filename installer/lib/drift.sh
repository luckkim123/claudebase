# shellcheck shell=bash
# installer/lib/drift.sh — post-install diagnostic: warn when config/settings.json
# has been modified outside a deliberate edit, so the user can review.
#
# Source order: after lib/log.sh.
#
# Exposes:
#   check_settings_drift   — print a one-line drift notice if the worktree
#                            shows uncommitted changes to config/settings.json.
#
# Why: $CLAUDE_HOME/settings.json used to be a symlink at this file, so the
# Claude CLI wrote straight back into the repo whenever it persisted a setting.
# lib/link.sh now RENDERS that path instead (see render_settings), which is what
# keeps personal preferences out of the tracked baseline — so a dirty baseline
# today usually means the machine is still on the old symlink layout and needs
# one install.sh run to migrate. The user decides to commit, discard, or update
# the canonical file. This is a warning only — never fails the installer.

check_settings_drift() {
  command -v git >/dev/null 2>&1 || return 0
  [[ -d "$REPO_DIR/.git" ]] || return 0

  # (a) Soft drift notice — any uncommitted change (formatting, a deliberate edit).
  if [[ -n "$(git -C "$REPO_DIR" status --porcelain config/settings.json 2>/dev/null)" ]]; then
    log "drift: config/settings.json is dirty — if this machine still symlinks ~/.claude/settings.json, re-run install.sh to migrate; review with: git -C $REPO_DIR diff config/settings.json"
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

# shellcheck shell=bash
# installer/lib/claude_mouse.sh — OPT-IN: make the `claude` CLI launch with the
# fullscreen renderer (CLAUDE_CODE_NO_FLICKER=1). See README +
# shell/claude-mouse.sh. Name is historical (was a mouse-capture opt-out until
# 2026-07-16); kept so installed rc lines keep resolving.
#
# Source order: after lib/args.sh (DRY_RUN) and lib/log.sh (log/debug/run).
#
# Exposes:
#   maybe_enable_claude_mouse  — offer to add a `source shell/claude-mouse.sh`
#                                line to the user's login-shell rc.
#
# Why opt-in (default No) AND why this is the ONE rc-append exception:
# it must be a `claude()` shell function *sourced* by the login shell — the
# alternative, `/tui fullscreen`, persists the pref into ~/.claude/settings.json
# — which claudebase used to symlink at the tracked config/settings.json (the
# recurring per-machine leak of 654484a / 8904b63). That path is rendered now,
# so `tui` is captured into settings.local.json instead of the lab baseline, but
# it still only takes effect next session; and tmux.conf can't set the claude
# process's env. claudebase is otherwise symlink-only and never mutates the
# user's rc; this is the single, marker-guarded exception. Fullscreen is an
# upstream research preview and trades away the terminal's native scrollback (a
# real tradeoff), so default No and ask once — same spirit as lib/viewer.sh.
#
# Idempotency (repo rule #5): once the marked line exists, a re-run finds the
# marker and is a pure no-op. Non-interactive runs skip silently unless
# INSTALL_CLAUDE_MOUSE=1 forces yes.

CLAUDE_MOUSE_MARKER="claudebase:claude-mouse"

# Echo the login shell's rc path (zsh/bash), or return 1 if we don't handle it.
_claude_mouse_rc() {
  case "$(basename "${SHELL:-}")" in
    zsh)  printf '%s\n' "$HOME/.zshrc" ;;
    bash) printf '%s\n' "$HOME/.bashrc" ;;
    *)    return 1 ;;
  esac
}

maybe_enable_claude_mouse() {
  local snippet="$REPO_DIR/shell/claude-mouse.sh"
  [[ -f "$snippet" ]] || { debug "claude-mouse: no $snippet (skip)"; return; }

  local rc=""
  rc="$(_claude_mouse_rc)" || { debug "claude-mouse: unhandled shell '${SHELL:-}' (skip)"; return; }

  # Already wired → pure no-op (idempotency contract).
  if [[ -f "$rc" ]] && grep -q "$CLAUDE_MOUSE_MARKER" "$rc"; then
    debug "claude-mouse: already enabled in $rc (skip)"
    return
  fi

  # Opt-in gate: forced by env, else prompt (default No), else silent skip.
  if [[ "${INSTALL_CLAUDE_MOUSE:-}" != "1" ]]; then
    [[ -t 0 ]] || { debug "claude-mouse: non-interactive, skipping opt-in prompt"; return; }
    local reply=""
    printf '[install] Optional: launch the claude CLI with the fullscreen renderer (no flicker + in-app mouse scroll/select; gives up the terminal'"'"'s native scrollback)? [y/N] '
    read -r reply || reply=""
    case "$reply" in
      y|Y|yes|YES) ;;
      *) log "claude-mouse: skipped (re-run with INSTALL_CLAUDE_MOUSE=1 to enable non-interactively)"; return ;;
    esac
  fi

  if [[ ${DRY_RUN:-0} -eq 1 ]]; then
    log "[dry-run] would append a marked 'source $snippet' line to $rc"
    return
  fi

  # Single mutation: append the marked source line. The marker makes every
  # later run a no-op, and revert = delete these two lines.
  {
    printf '\n# %s — fullscreen renderer for the claude CLI\n' "$CLAUDE_MOUSE_MARKER"
    printf '[ -f "%s" ] && source "%s"\n' "$snippet" "$snippet"
  } >> "$rc"
  log "claude-mouse: enabled in $rc (open a new shell to apply)"
}

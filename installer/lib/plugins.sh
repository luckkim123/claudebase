# shellcheck shell=bash
# installer/lib/plugins.sh — thin wrapper around installer/scripts/plugin_sync.py.
#
# Source order: after lib/args.sh (DRY_RUN) and lib/log.sh.
#
# Exposes:
#   sync_plugins   — invoke plugin_sync.py with --apply / --dry-run,
#                    prefixing each line of its output with [install].
#
# Why bash forwards only: the Python module owns the Action/Decision logic and
# the marketplace/OS-gate metadata lookup (tested under
# tests/installer/test_plugin_sync.py). Bash here is just argv mapping and
# missing-binary skip handling.

sync_plugins() {
  if ! command -v claude >/dev/null 2>&1; then
    log "skip plugin sync: 'claude' not in PATH (install Claude Code, then re-run)"
    return
  fi
  if ! command -v python3 >/dev/null 2>&1; then
    log "skip plugin sync: 'python3' not available"
    return
  fi
  local args=(--apply)
  [[ $DRY_RUN -eq 1 ]] && args=(--dry-run)
  # --update is passed unconditionally: without it plugin_sync labels every
  # already-installed plugin OK and never moves its version, so a machine that
  # ran install.sh a year ago and runs it again today keeps the year-old copy.
  # Measured 2026-08-31: oh-my-orchestrator sat at 0.16.0 on this machine while
  # 0.17/0.18/0.19.0 had all shipped, because presence was the only thing
  # checked. `claude plugin update` is idempotent -- a no-op when current -- so
  # the cost of always asking is one CLI round trip per enabled plugin, and the
  # cost of not asking is a silently stale harness.
  args+=(--update)
  python3 "$REPO_DIR/installer/scripts/plugin_sync.py" "${args[@]}" 2>&1 \
    | while IFS= read -r line; do log "$line"; done
}

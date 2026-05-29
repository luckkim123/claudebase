# shellcheck shell=bash
# installer/lib/plugins.sh — thin wrapper around installer/scripts/plugin_sync.py.
#
# Source order: after lib/args.sh (DRY_RUN, PRUNE_PLUGINS) and lib/log.sh.
#
# Exposes:
#   sync_plugins   — invoke plugin_sync.py with --apply / --dry-run / --prune,
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
  [[ $PRUNE_PLUGINS -eq 1 ]] && args+=(--prune)
  python3 "$REPO_DIR/installer/scripts/plugin_sync.py" "${args[@]}" 2>&1 \
    | while IFS= read -r line; do log "$line"; done
}

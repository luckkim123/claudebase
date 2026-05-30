# shellcheck shell=bash
# installer/lib/log.sh — logging + dry-run command wrapper.
#
# Source order: must be sourced AFTER lib/args.sh (which exports DRY_RUN and
# VERBOSE) but before any other lib/*.sh module. The orchestrator pins this.
#
# Exposes:
#   log MSG       — single-line "[install] MSG" to stdout
#   debug MSG     — "[debug]   MSG" only when VERBOSE=1
#   run CMD ARG…  — execute CMD as an array; prints "[dry-run] …" if DRY_RUN=1

log()   { printf '[install] %s\n' "$*"; }
debug() { [[ ${VERBOSE:-0} -eq 1 ]] && printf '[debug]   %s\n' "$*" || true; }

# run COMMAND ARG... — executes a command as an array (no eval, no shell metachar surprises)
run() {
  if [[ ${DRY_RUN:-0} -eq 1 ]]; then
    printf '[dry-run] '
    printf '%q ' "$@"
    printf '\n'
  else
    "$@"
  fi
}

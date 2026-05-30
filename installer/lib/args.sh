# shellcheck shell=bash
# installer/lib/args.sh — argument parsing, OS detection, env constants.
#
# Source order: must be sourced FIRST (before lib/log.sh). The orchestrator
# pins this — every other module depends on the exports below.
#
# Exports:
#   COPY_MODE, DRY_RUN, VERBOSE, PRUNE_PLUGINS  — int flags (0/1)
#   OS                                           — uname -s output
#   PLATFORM                                     — "macos" | "linux"
#   CLAUDE_HOME                                  — user-scope Claude home ($HOME/.claude)
#
# Caller contract: orchestrator must define $0_USAGE_FILE (path to the file
# whose lines 2-7 are the --help body) before sourcing this file. install.sh
# sets it to "${BASH_SOURCE[0]}" so the existing sed-based help still works
# without hardcoding install.sh in the module.

parse_args() {
  COPY_MODE=0
  DRY_RUN=0
  VERBOSE=0
  PRUNE_PLUGINS=0

  for arg in "$@"; do
    case "$arg" in
      --copy) COPY_MODE=1 ;;
      --dry-run) DRY_RUN=1 ;;
      --verbose) VERBOSE=1 ;;
      --prune-plugins) PRUNE_PLUGINS=1 ;;
      -h|--help) sed -n '2,7p' "${ARGS_USAGE_FILE:-$0}"; exit 0 ;;
      *) echo "Unknown arg: $arg" >&2; exit 1 ;;
    esac
  done
}

detect_platform() {
  OS="$(uname -s)"
  case "$OS" in
    Darwin) PLATFORM="macos" ;;
    Linux)  PLATFORM="linux" ;;
    *) echo "Unsupported OS: $OS — use install.ps1 on Windows" >&2; exit 1 ;;
  esac
}

# CLAUDE_HOME is the symlink/target root for every user-scope artifact the
# installer manages. Override via env if you need a non-default location.
: "${CLAUDE_HOME:=$HOME/.claude}"

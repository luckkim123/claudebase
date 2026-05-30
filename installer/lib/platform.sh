# shellcheck shell=bash
# installer/lib/platform.sh — dispatch to platform/<os>/install.sh.
#
# Source order: after lib/args.sh (needs $PLATFORM) and lib/log.sh (needs run/log).
#
# Exposes:
#   run_platform_installer   — bash $REPO_DIR/platform/$PLATFORM/install.sh if present.

run_platform_installer() {
  local platform_installer="$REPO_DIR/platform/$PLATFORM/install.sh"
  if [[ -f "$platform_installer" ]]; then
    log "running platform installer: $PLATFORM"
    run bash "$platform_installer"
  fi
}

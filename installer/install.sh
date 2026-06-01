#!/usr/bin/env bash
# claudebase installer (macOS / Linux)
# Usage: ./install.sh [--copy] [--dry-run] [--verbose] [--prune-plugins]
#   --copy            Copy files instead of symlinking (less convenient for sync)
#   --dry-run         Show actions without executing
#   --verbose         Print extra detail (idempotent skips, resolved secrets count)
#   --prune-plugins   Uninstall user-scope plugins not in any enabledPlugins
#                     (default: warn only — keeps drift-kept plugins installed)

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Arg parsing + platform detection extracted to installer/lib/args.sh (P3).
# ARGS_USAGE_FILE lets --help still read this file's lines 2-7.
ARGS_USAGE_FILE="${BASH_SOURCE[0]}"
# shellcheck source=lib/args.sh
source "$REPO_DIR/installer/lib/args.sh"
parse_args "$@"
detect_platform

# Runtime dependency probe extracted to installer/lib/deps.sh (P3-T4).
# shellcheck source=lib/deps.sh
source "$REPO_DIR/installer/lib/deps.sh"
check_runtime_deps

# log/debug/run extracted to installer/lib/log.sh (P3 modularization).
# shellcheck source=lib/log.sh
source "$REPO_DIR/installer/lib/log.sh"

# Linking primitives + stages 1+2+2b extracted to lib/link.sh (P3-T3).
# shellcheck source=lib/link.sh
source "$REPO_DIR/installer/lib/link.sh"
link_settings_and_md

# Stage 3 (mcp.json render + secrets.env literal parser) → lib/secrets.sh (P3-T5).
# shellcheck source=lib/secrets.sh
source "$REPO_DIR/installer/lib/secrets.sh"
render_mcp_json

# Stages 4 + 4b + 4c handled by lib/link.sh helpers.
link_tmux_conf
link_skills_and_agents

# Stages 5 / 5b / 6 → lib/platform.sh, lib/project_hooks.sh, lib/plugins.sh (P3-T6/T7/T8).
# shellcheck source=lib/platform.sh
source "$REPO_DIR/installer/lib/platform.sh"
# shellcheck source=lib/project_hooks.sh
source "$REPO_DIR/installer/lib/project_hooks.sh"
# shellcheck source=lib/plugins.sh
source "$REPO_DIR/installer/lib/plugins.sh"
run_platform_installer
deploy_project_hooks
sync_plugins

# OMC freeze patch + statedir-ascent patch + HUD wrapper → lib/omc.sh (P3-T9).
# shellcheck source=lib/omc.sh
source "$REPO_DIR/installer/lib/omc.sh"
patch_omc_bash_freeze
# Re-enabled 2026-06-01 as POINT D (design §9): the broken point C patched
# resolveToWorktreeRoot and threw "[OMC] HUD error" (it fed a value above the
# #576 trusted-root boundary into validateWorkingDirectory). Point D patches
# ONLY getOmcRoot's argument — ascendToMarker(worktreeRoot) first — so .omc
# converges to the marker root while resolveToWorktreeRoot stays stock and the
# security boundary is untouched. Verified by reproducing the real HUD load
# graph (not just isolated node -e) + 5 regression scenarios. See
# docs/specs/2026-05-31-omc-statedir-marker-ascent/design.md §9.
patch_omc_statedir

# 7. local-overrides hint
LOCAL_FILE="$CLAUDE_HOME/settings.local.json"
if [[ ! -e "$LOCAL_FILE" ]]; then
  log "hint: no $LOCAL_FILE — see templates/settings.local.example.json for per-machine plugin overrides"
fi

maybe_install_omc_hud

# Stage 9 → lib/drift.sh (P3-T10).
# shellcheck source=lib/drift.sh
source "$REPO_DIR/installer/lib/drift.sh"
check_settings_drift

log "done."

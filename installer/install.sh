#!/usr/bin/env bash
# claudebase installer (macOS / Linux)
# Usage: ./install.sh [--copy] [--dry-run] [--verbose]
#   --copy            Copy files instead of symlinking (less convenient for sync)
#   --dry-run         Show actions without executing
#   --verbose         Print extra detail (idempotent skips, resolved secrets count)

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

# Opt-in convenience-tool install (INSTALL_TOOLS=1): tmux + clipboard helper so
# tmux.conf's mouse-copy works out of the box. No-op without the env var, so the
# default path stays warn-only + idempotent. Needs log/debug/run, hence here
# (after log.sh) rather than next to check_runtime_deps above.
ensure_convenience_tools

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

# Optional opt-in: claude-code-viewer VSCode extension → lib/viewer.sh.
# Default No; prompts only on first install or when a remote update exists.
# shellcheck source=lib/viewer.sh
source "$REPO_DIR/installer/lib/viewer.sh"
maybe_install_viewer

# Idempotent editable (re)install of the omx-core CLI → lib/omx.sh. Re-pins the
# editable install to the current oh-my-experiments checkout so a moved repo
# (e.g. /workspace -> /root) self-heals here instead of leaving `omx` broken
# with ModuleNotFoundError. Skips silently when already correctly pinned.
# shellcheck source=lib/omx.sh
source "$REPO_DIR/installer/lib/omx.sh"
ensure_omx_install

# Prune stale plugin-cache versions → lib/plugin_cache.sh. Marketplace
# auto-update fetches new versions but never deletes the old ones, so the cache
# grows without bound (e.g. omc 4.14.1 + 4.14.4 + 4.14.5). Keep only the newest
# SemVer dir per plugin; leave non-SemVer (git-sha) pins untouched.
# shellcheck source=lib/plugin_cache.sh
source "$REPO_DIR/installer/lib/plugin_cache.sh"
prune_plugin_cache

# 8. settings-shrink guard: point this clone's git hooks at the tracked
# installer/githooks dir so the pre-commit guard (which blocks committing a
# CLI-shrunk config/settings.json) is active on every machine. .git/hooks alone
# is per-clone + untracked, so without this the guard would be silently absent
# on fresh clones. See docs/specs/2026-06-01-settings-shrink-guard/.
if command -v git >/dev/null 2>&1 && [[ -d "$REPO_DIR/.git" ]]; then
  if [[ "$(git -C "$REPO_DIR" config --local --get core.hooksPath 2>/dev/null)" != "installer/githooks" ]]; then
    git -C "$REPO_DIR" config --local core.hooksPath installer/githooks
    log "linked git hooks: core.hooksPath -> installer/githooks (settings-shrink guard active)"
  fi
fi

# Stage 9 → lib/drift.sh (P3-T10).
# shellcheck source=lib/drift.sh
source "$REPO_DIR/installer/lib/drift.sh"
check_settings_drift

log "done."

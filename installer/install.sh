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

# Stages 4 + 4b + 4c + 4d + 4e handled by lib/link.sh helpers.
link_tmux_conf
link_skills_and_agents
link_output_styles
# 4e runs last so it judges what the link stages just refreshed: a renamed skill
# (old link now dangling, new link freshly made) settles in a single run.
prune_stale_links

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

# Optional opt-in: launch the `claude` CLI with the fullscreen renderer
# (sources shell/claude-mouse.sh from the login-shell rc).
# Default No; the single marker-guarded exception to the symlink-only, never-
# touch-rc model. See lib/claude_mouse.sh header for why rc-append is required.
# shellcheck source=lib/claude_mouse.sh
source "$REPO_DIR/installer/lib/claude_mouse.sh"
maybe_enable_claude_mouse

# Vendor-CLI probe for oh-my-orchestrator → lib/orchestrator_vendors.sh. Its
# role→backend table is tracked and shared, so it cannot know what any one
# machine has; the answer belongs in a machine-local file. Opt-in, marker-guarded.
# shellcheck source=lib/orchestrator_vendors.sh
source "$REPO_DIR/installer/lib/orchestrator_vendors.sh"
maybe_record_orchestrator_vendors

# Idempotent editable (re)install of the omx-core CLI → lib/omx.sh. Re-pins the
# editable install to the current oh-my-experiments checkout so a moved repo
# (e.g. /workspace -> /root) self-heals here instead of leaving `omx` broken
# with ModuleNotFoundError. Skips silently when already correctly pinned.
# shellcheck source=lib/omx.sh
source "$REPO_DIR/installer/lib/omx.sh"
ensure_omx_install

# Idempotent install of the two code-graph CLIs → deps.sh.
# code-review-graph (github.com/tirth8205/code-review-graph) answers structural
# queries over a SQLite index via MCP; graphify (github.com/Graphify-Labs/graphify,
# PyPI "graphifyy") builds a whole-corpus knowledge graph and exports artifacts.
# Complementary, not redundant — routing rules in templates/project-code-review-graph.md.
# None of them builds a graph here: that is a per-repo decision.
# tokensave was the third until 2026-08-25; removed for zero routing (6 MCP calls
# in 10,813 over 22 days) — see docs/CHANGELOG.md.
ensure_code_review_graph
ensure_graphify

# graphify ships its own /graphify skill — the chunked-extraction BUILD runbook,
# not documentation. Linked from the installed package (never vendored) so it
# tracks the installed version instead of going stale in this repo. Needs
# link_or_copy + CLAUDE_HOME, hence here rather than beside check_runtime_deps.
ensure_graphify_skill

# `graph-init` on PATH → deps.sh. The verb graph-offer.sh points at: exclusions,
# both free builds, and the vendored-tree check, in one command. Must run after
# the CLI installs above, since it is what those CLIs get driven by.
ensure_graph_init

# tmux wrapper for Orca Agent Teams → deps.sh. No-op on machines without Orca.
ensure_tmux_teams_shim

# Say the three CLIs exist, once per machine → deps.sh. graph-offer.sh is the
# only other automatic mention and it short-circuits in any project that already
# has one graph, so without this a user can carry all three for months and never
# learn `/graphify` is there. Printed, not prompted; after ensure_graph_init so
# the verb it names already resolves.
graph_cli_intro_note

# Register user-scope MCP servers with the CLI. This is separate from
# render_mcp_json above because Claude Code does NOT read ~/.claude/mcp.json —
# user-scope servers live in ~/.claude.json, reachable only via `claude mcp add`
# (measured 2026-08-10; see config/mcp.template.json). Runs after the installs
# above so a freshly-installed binary resolves to an absolute path. Idempotent:
# a server already registered is left untouched, never re-added.
if [[ $DRY_RUN -eq 1 ]]; then
  run python3 "$REPO_DIR/installer/scripts/register_mcp.py" --config "$CLAUDE_HOME/mcp.json" --dry-run
else
  python3 "$REPO_DIR/installer/scripts/register_mcp.py" --config "$CLAUDE_HOME/mcp.json" || true
fi

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

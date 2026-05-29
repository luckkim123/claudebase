#!/usr/bin/env bash
# claude-settings installer (macOS / Linux)
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

# 6.5. OMC bash-failure freeze workaround
#      Gate post-tool-verifier.mjs:905 (Command failed → "fix before continuing")
#      behind QUIET_LEVEL < 2 so OMC_QUIET=2 silences it, matching the pattern
#      already used on line 906 for the background-detection message.
#      Root cause (2026-05-24 investigation): "before continuing" is parsed as
#      a pause gate by the model, freezing the session after every Bash error.
#      Idempotent — checks for the already-patched marker before applying.
#      See .omc/reviews/session-freeze-investigation.md for evidence.
patch_omc_bash_freeze() {
  local omc_root="$CLAUDE_HOME/plugins/cache/omc/oh-my-claudecode"
  if [[ ! -d "$omc_root" ]]; then
    debug "skip omc bash-freeze patch: $omc_root not present"
    return
  fi
  local patched=0 skipped=0
  while IFS= read -r verifier; do
    [[ -f "$verifier" ]] || continue
    if grep -q 'QUIET_LEVEL < 2 && detectBashFailure' "$verifier" 2>/dev/null; then
      skipped=$((skipped + 1))
      continue
    fi
    if [[ $DRY_RUN -eq 1 ]]; then
      log "would patch omc bash-freeze in: $verifier"
      patched=$((patched + 1))
    else
      # In-place sed: gate the bash-failure message behind QUIET_LEVEL < 2.
      # macOS BSD sed needs '' after -i; GNU sed accepts -i alone — handle both.
      # BSD sed (macOS) does not support \s — use literal space class.
      if sed --version >/dev/null 2>&1; then
        sed -i -E 's|^(  *)\} else if \(detectBashFailure\(toolOutput\)\) \{|\1} else if (QUIET_LEVEL < 2 \&\& detectBashFailure(toolOutput)) {|' "$verifier"
      else
        sed -i '' -E 's|^(  *)\} else if \(detectBashFailure\(toolOutput\)\) \{|\1} else if (QUIET_LEVEL < 2 \&\& detectBashFailure(toolOutput)) {|' "$verifier"
      fi
      if grep -q 'QUIET_LEVEL < 2 && detectBashFailure' "$verifier" 2>/dev/null; then
        patched=$((patched + 1))
      else
        log "WARNING: omc bash-freeze patch did not apply to $verifier"
      fi
    fi
  done < <(find "$omc_root" -path '*/scripts/post-tool-verifier.mjs' -type f 2>/dev/null)
  log "omc bash-freeze patch: patched=$patched, already-patched=$skipped (set OMC_QUIET=2 to silence)"
}
patch_omc_bash_freeze

# 7. local-overrides hint
LOCAL_FILE="$CLAUDE_HOME/settings.local.json"
if [[ ! -e "$LOCAL_FILE" ]]; then
  log "hint: no $LOCAL_FILE — see templates/settings.local.example.json for per-machine plugin overrides"
fi

# 8. oh-my-claudecode HUD setup
#    The HUD wrapper is two file copies + chmod (see the `hud` skill's setup
#    steps), generated directly from the plugin's canonical template instead
#    of waiting for a live `/oh-my-claudecode:hud setup`.
#    Idempotency (2026-05-29, G2.4): skip cp if destination already byte-matches
#    template + customization marker. The previous version regenerated every
#    install, which broke the "two runs = zero actions" contract — the smoke
#    test introduced in G3.2 would now catch a regression here.
install_omc_hud() {
  local omc_root="$CLAUDE_HOME/plugins/cache/omc/oh-my-claudecode"
  # Pick the highest installed version dir that actually ships the template.
  local tmpl="" cfgdir=""
  if [[ -d "$omc_root" ]]; then
    local ver
    for ver in $(ls -1 "$omc_root" 2>/dev/null | grep -E '^[0-9]+\.[0-9]+\.[0-9]+' | sort -rV); do
      if [[ -f "$omc_root/$ver/scripts/lib/hud-wrapper-template.txt" ]]; then
        tmpl="$omc_root/$ver/scripts/lib/hud-wrapper-template.txt"
        cfgdir="$omc_root/$ver/scripts/lib/config-dir.mjs"
        break
      fi
    done
  fi

  if [[ -z "$tmpl" ]]; then
    log "next: open Claude Code and run '/oh-my-claudecode:omc-setup' to finish HUD install (template not found in plugin cache)"
    return
  fi

  if [[ $DRY_RUN -eq 1 ]]; then
    log "would install HUD wrapper from $tmpl"
    return
  fi

  local dest="$CLAUDE_HOME/hud/omc-hud.mjs"
  local dest_cfg="$CLAUDE_HOME/hud/lib/config-dir.mjs"
  local customization_marker="OMC HUD local customization"

  # Skip when dest already contains the customization marker AND config-dir.mjs
  # byte-matches the template's companion. The marker is the truth that
  # hud-customize.sh has already applied; if it's there, the wrapper is the
  # patched form we want (not the raw template), and re-copying would clobber
  # it. We check config-dir.mjs separately because it's never customized.
  if [[ -f "$dest" ]] \
     && grep -qF "$customization_marker" "$dest" \
     && [[ -f "$dest_cfg" ]] \
     && cmp -s "$cfgdir" "$dest_cfg"; then
    debug "HUD wrapper up to date (skip)"
    return
  fi

  mkdir -p "$CLAUDE_HOME/hud/lib"
  cp "$tmpl" "$dest"
  cp "$cfgdir" "$dest_cfg"
  chmod 755 "$dest"
  # Drop any legacy script left by older OMC versions.
  [[ -f "$CLAUDE_HOME/hud/omc-hud.js" ]] && rm -f "$CLAUDE_HOME/hud/omc-hud.js"
  log "installed HUD wrapper -> $dest"

  # Re-apply local HUD customization (line1: cyan dir:/branch:, lowercase
  # model:). The fresh copy above dropped any prior customization, so
  # hud-customize.sh re-injects it. Its own marker check still applies.
  bash "$REPO_DIR/installer/scripts/hud-customize.sh" 2>&1 | while IFS= read -r line; do log "$line"; done
}
if python3 -c "import json; d=json.load(open('$CLAUDE_HOME/settings.json')); exit(0 if d.get('enabledPlugins', {}).get('oh-my-claudecode@omc') else 1)" 2>/dev/null; then
  install_omc_hud
fi

# 9. settings.json drift check (warn-only)
#    settings.json is symlinked, so the Claude Code CLI writes straight back
#    into the repo when it auto-formats or persists new settings. Surface this
#    so the user can decide to commit, discard, or update the canonical file.
if command -v git >/dev/null 2>&1; then
  if [[ -d "$REPO_DIR/.git" ]]; then
    if [[ -n "$(git -C "$REPO_DIR" status --porcelain config/settings.json 2>/dev/null)" ]]; then
      log "drift: config/settings.json modified by Claude CLI — review with: git -C $REPO_DIR diff config/settings.json"
    fi
  fi
fi

log "done."

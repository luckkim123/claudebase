# shellcheck shell=bash
# installer/lib/omc.sh — OMC-specific install steps (freeze patch + HUD wrapper).
#
# Source order: after lib/args.sh (DRY_RUN, CLAUDE_HOME) and lib/log.sh.
#
# Exposes:
#   patch_omc_bash_freeze   — delegate to installer/scripts/patch_omc_freeze.sh
#                             (which OMC reinstall re-applies on every claudebase
#                             install). See docs/upstream-patches.md for the
#                             upstream fix condition.
#   patch_omc_statedir      — delegate to installer/scripts/patch_omc_statedir.sh
#                             (marker-ascent so .omc converges in non-git trees).
#                             Same reinstall-reapply lifecycle. See
#                             docs/upstream-patches.md.
#   install_omc_hud         — copy hud wrapper + config-dir.mjs from the highest
#                             versioned plugin cache and re-apply local cyan
#                             dir:/branch: customization via hud-customize.sh.
#
# Idempotency notes:
# - patch_omc_freeze.sh checks the patched-marker string before applying.
# - install_omc_hud skips when both the destination contains the customization
#   marker AND config-dir.mjs byte-matches the template's companion (G2.4).
#   The previous version regenerated every install; the smoke test now guards.

patch_omc_bash_freeze() {
  local script="$REPO_DIR/installer/scripts/patch_omc_freeze.sh"
  [[ -f "$script" ]] || { debug "skip omc bash-freeze patch: script missing at $script"; return 0; }
  # Forward DRY_RUN as an env var so the script's own check honors it.
  DRY_RUN="$DRY_RUN" bash "$script" 2>&1 | while IFS= read -r line; do log "$line"; done
}

patch_omc_statedir() {
  local script="$REPO_DIR/installer/scripts/patch_omc_statedir.sh"
  [[ -f "$script" ]] || { debug "skip omc statedir-ascent patch: script missing at $script"; return 0; }
  # Forward DRY_RUN as an env var so the script's own check honors it.
  DRY_RUN="$DRY_RUN" bash "$script" 2>&1 | while IFS= read -r line; do log "$line"; done
}

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

# Gate: only install HUD when oh-my-claudecode@omc is in enabledPlugins.
maybe_install_omc_hud() {
  if python3 -c "import json; d=json.load(open('$CLAUDE_HOME/settings.json')); exit(0 if d.get('enabledPlugins', {}).get('oh-my-claudecode@omc') else 1)" 2>/dev/null; then
    install_omc_hud
  fi
}

# shellcheck shell=bash
# installer/lib/viewer.sh — OPT-IN install/update of the claude-code-viewer VSCode extension.
#
# Source order: after lib/args.sh (DRY_RUN) and lib/log.sh (log/run).
#
# Exposes:
#   maybe_install_viewer   — install (first time) or offer to update the viewer.
#
# Why opt-in (default No): claudebase ships to EVERY machine, but this viewer is
# a personal dev tool, not universal config. Forcing it on every clone would
# violate the "no per-machine quirk in the distributed repo" rule. So we ask
# once, default No, and only install when the human says yes (or sets
# INSTALL_VIEWER=1). Non-interactive runs (CI, piped stdin) skip silently —
# same spirit as lib/plugins.sh skipping when a binary is absent.
#
# Prompt policy (per user 2026-06-05):
#   - not installed        → opt-in prompt (default No)
#   - installed, up to date → SILENT skip (never nag)
#   - installed, remote has new commits → "update?" prompt (default No)
# We compare the remote HEAD SHA (cheap `git ls-remote`, no clone) against the
# SHA recorded at install time in $ext_dir/.installed-sha. SHA (not the manifest
# version) so a content change without a version bump is still detected.
#
# No vsce/.vsix: the viewer has no packager (only `npm run build` via esbuild),
# so we use the supported "load from extensions dir" path — clone, build, then
# COPY the built tree into ~/.vscode/extensions/<id>/. Copy (not symlink) because
# VSCode has known symlink-in-extensions-dir issues (microsoft/vscode#34627).

VIEWER_REPO_URL="https://github.com/luckkim123/claude-code-viewer.git"
VIEWER_EXT_ID="luckkim123.claude-code-viewer-0.1.0"

maybe_install_viewer() {
  local ext_dir="$HOME/.vscode/extensions/$VIEWER_EXT_ID"
  local installed=0
  [[ -d "$ext_dir" ]] && installed=1

  # Resolve remote HEAD SHA up front (cheap, no clone). Empty if git absent or
  # the network call fails — we degrade gracefully below.
  local remote_sha=""
  if command -v git >/dev/null 2>&1; then
    remote_sha="$(git ls-remote "$VIEWER_REPO_URL" HEAD 2>/dev/null | awk '{print $1}')"
  fi

  if [[ $installed -eq 1 ]]; then
    # Up to date (or can't tell) → SILENT skip, never nag.
    local installed_sha=""
    [[ -f "$ext_dir/.installed-sha" ]] && installed_sha="$(cat "$ext_dir/.installed-sha" 2>/dev/null)"
    if [[ -z "$remote_sha" || "$remote_sha" == "$installed_sha" ]]; then
      debug "viewer: up to date (skip)"
      return
    fi
    # A newer remote exists → ask to update (unless forced / non-interactive).
    if [[ "${INSTALL_VIEWER:-}" != "1" ]]; then
      [[ -t 0 ]] || { debug "viewer: update available but non-interactive (skip)"; return; }
      local reply=""
      printf '[install] claude-code-viewer has an update available. Update? [y/N] '
      read -r reply || reply=""
      case "$reply" in
        y|Y|yes|YES) ;;
        *) log "viewer: update skipped"; return ;;
      esac
    fi
  else
    # First-time install → opt-in prompt (default No), unless forced.
    if [[ "${INSTALL_VIEWER:-}" != "1" ]]; then
      [[ -t 0 ]] || { debug "viewer: non-interactive shell, skipping opt-in prompt"; return; }
      local reply=""
      printf '[install] Optional: install the claude-code-viewer VSCode extension? [y/N] '
      read -r reply || reply=""
      case "$reply" in
        y|Y|yes|YES) ;;
        *) log "viewer: skipped (re-run with INSTALL_VIEWER=1 to install non-interactively)"; return ;;
      esac
    fi
  fi

  # Required tooling — skip with a clear note if any is missing (plugins.sh pattern).
  local missing=()
  command -v git  >/dev/null 2>&1 || missing+=(git)
  command -v npm  >/dev/null 2>&1 || missing+=(npm)
  command -v code >/dev/null 2>&1 || missing+=("code (VSCode CLI)")
  if (( ${#missing[@]} > 0 )); then
    log "viewer: skip, missing: ${missing[*]}"
    return
  fi

  if [[ ${DRY_RUN:-0} -eq 1 ]]; then
    log "[dry-run] would clone $VIEWER_REPO_URL, npm install + build, copy to $ext_dir"
    return
  fi

  local tmp
  tmp="$(mktemp -d)" || { log "viewer: mktemp failed, skip"; return; }
  log "viewer: cloning $VIEWER_REPO_URL"
  if ! git clone --depth 1 "$VIEWER_REPO_URL" "$tmp/src" >/dev/null 2>&1; then
    log "viewer: clone failed, skip"; rm -rf "$tmp"; return
  fi
  # Record the exact SHA we built from, for next run's update check.
  local built_sha
  built_sha="$(git -C "$tmp/src" rev-parse HEAD 2>/dev/null)"
  log "viewer: npm install + build (this may take a minute)"
  if ! ( cd "$tmp/src" && npm install >/dev/null 2>&1 && npm run build >/dev/null 2>&1 ); then
    log "viewer: build failed, skip"; rm -rf "$tmp"; return
  fi
  # Fresh copy: clear any prior install so removed files don't linger.
  rm -rf "$ext_dir"
  mkdir -p "$ext_dir"
  cp -R "$tmp/src/." "$ext_dir/"
  [[ -n "$built_sha" ]] && printf '%s\n' "$built_sha" > "$ext_dir/.installed-sha"
  rm -rf "$tmp"
  log "viewer: installed to $ext_dir (restart VSCode to activate)"
}

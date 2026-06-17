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
# SHA recorded at install time in $VIEWER_SHA_FILE. SHA (not the manifest
# version) so a content change without a version bump is still detected.
#
# Install path — `.vsix` via `code --install-extension` (changed 2026-06-17):
# previously we copied the built tree into ~/.vscode/extensions/<id>/ directly,
# but that left the extension UNREGISTERED in VSCode's extensions.json cache, so
# VSCode never loaded it (the build was on disk but invisible). We now package a
# real .vsix (`npx @vscode/vsce package`) and let `code --install-extension`
# register it the supported way — VSCode owns the extensions.json entry and the
# install-dir name (`<publisher>.<name>-<version>`, e.g. local-dev.claude-code-
# viewer-0.1.0). Because we no longer control that dir name, the install SHA is
# tracked at a fixed sidecar path ($VIEWER_SHA_FILE), not inside the ext dir.
#
# `code` must be REAL VSCode, not Cursor: on macOS a `code` on PATH frequently
# points at Cursor's CLI (which reports a 3.x version and manages ~/.cursor/
# extensions, not ~/.vscode). Installing the viewer through Cursor's `code` would
# put it where VSCode can't see it. So we verify `code --version`'s first line is
# a 1.x VSCode version before trusting it; otherwise we skip with a clear note.

VIEWER_REPO_URL="https://github.com/luckkim123/claude-code-viewer.git"
# Extension identity = <publisher>.<name> from the repo's package.json. Kept here
# so the update check / uninstall can address it; VSCode derives the install-dir
# name itself from the packaged .vsix.
VIEWER_EXT_ID="local-dev.claude-code-viewer"
# Fixed sidecar for the built-from SHA — independent of the (VSCode-chosen) ext dir.
VIEWER_SHA_FILE="$HOME/.vscode/extensions/.claude-code-viewer.installed-sha"

# Echo a real VSCode `code` binary path, or nothing if none is trustworthy.
# A `code` on PATH may be Cursor's (version 3.x) — VSCode's is 1.x. We accept the
# PATH one only if its version is 1.x; otherwise we probe the standard VSCode.app
# CLI location as a fallback before giving up.
_viewer_resolve_code() {
  local candidate
  for candidate in \
    "$(command -v code 2>/dev/null)" \
    "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"; do
    [[ -n "$candidate" && -x "$candidate" ]] || continue
    # First line of `code --version` is the VSCode version (1.x for real VSCode).
    case "$("$candidate" --version 2>/dev/null | head -1)" in
      1.*) printf '%s\n' "$candidate"; return 0 ;;
    esac
  done
  return 1
}

maybe_install_viewer() {
  local installed=0
  # "installed" = VSCode reports the extension id in its list (source of truth),
  # not a guessed dir. Resolve a real `code` first; if none, we can't tell, so we
  # treat it as a missing-tool skip below.
  local code_bin=""
  code_bin="$(_viewer_resolve_code)" || code_bin=""
  if [[ -n "$code_bin" ]] && "$code_bin" --list-extensions 2>/dev/null | grep -qix "$VIEWER_EXT_ID"; then
    installed=1
  fi

  # Resolve remote HEAD SHA up front (cheap, no clone). Empty if git absent or
  # the network call fails — we degrade gracefully below.
  local remote_sha=""
  if command -v git >/dev/null 2>&1; then
    remote_sha="$(git ls-remote "$VIEWER_REPO_URL" HEAD 2>/dev/null | awk '{print $1}')"
  fi

  if [[ $installed -eq 1 ]]; then
    # Up to date (or can't tell) → SILENT skip, never nag.
    local installed_sha=""
    [[ -f "$VIEWER_SHA_FILE" ]] && installed_sha="$(cat "$VIEWER_SHA_FILE" 2>/dev/null)"
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
  command -v npx  >/dev/null 2>&1 || missing+=(npx)
  [[ -n "$code_bin" ]] || missing+=("code (real VSCode CLI — a Cursor 'code' on PATH is ignored)")
  if (( ${#missing[@]} > 0 )); then
    log "viewer: skip, missing: ${missing[*]}"
    return
  fi

  if [[ ${DRY_RUN:-0} -eq 1 ]]; then
    log "[dry-run] would clone $VIEWER_REPO_URL, npm install + build, vsce package, code --install-extension"
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
  # Package a real .vsix so VSCode registers it properly. --no-dependencies: the
  # build already bundled everything via esbuild, so vsce need not re-resolve npm
  # deps (and won't choke on the absence of a packaging-time devDependency tree).
  log "viewer: packaging .vsix (npx @vscode/vsce)"
  local vsix="$tmp/claude-code-viewer.vsix"
  if ! ( cd "$tmp/src" && npx --yes @vscode/vsce package --no-dependencies -o "$vsix" >/dev/null 2>&1 ); then
    log "viewer: vsce package failed, skip"; rm -rf "$tmp"; return
  fi
  log "viewer: installing via code --install-extension"
  if ! "$code_bin" --install-extension "$vsix" --force >/dev/null 2>&1; then
    log "viewer: code --install-extension failed, skip"; rm -rf "$tmp"; return
  fi
  [[ -n "$built_sha" ]] && printf '%s\n' "$built_sha" > "$VIEWER_SHA_FILE"
  rm -rf "$tmp"
  log "viewer: installed (restart VSCode to activate)"
}

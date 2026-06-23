# shellcheck shell=bash
# installer/lib/deps.sh — runtime dependency probe.
#
# Source order: after lib/args.sh (needs $PLATFORM).
#
# Warn-only contract (default): prints WARNING + install hint per missing tool,
# never auto-installs and never exits. install.sh remains idempotent because
# every warning is the same line on every run.
#
# Opt-in auto-install (INSTALL_TOOLS=1): the *convenience* tools tmux + a
# clipboard helper are best-effort installed when missing. Idempotency is still
# preserved — an already-present tool prints the same "present (skip)" line on
# every run, and when sudo would be needed but isn't available we fall back to
# the warn-only hint (never a blocking sudo prompt), so a non-interactive / CI
# sync is safe. jq/gemini stay warn-only regardless: they are not always
# apt-installable (gemini is npm) and the user may want a specific provenance.
#
# Exposed:
#   check_runtime_deps   — probe jq, gemini CLI, nano banana extension.
#   ensure_convenience_tools  — opt-in best-effort install of tmux + clipboard.

check_runtime_deps() {
  # jq — required by the statusLine command in claude/settings.json; without
  # it the status line silently renders as literal template text (e.g. "ctx:%").
  if ! command -v jq >/dev/null 2>&1; then
    printf '[install] WARNING: "jq" not found — statusLine will degrade silently\n'
    case "$PLATFORM" in
      macos) printf '[install]   install: brew install jq\n' ;;
      linux) printf '[install]   install: sudo apt-get install -y jq  (Debian/Ubuntu)\n' ;;
    esac
  fi

  # gemini CLI — required by the gen-image skill (Google nano banana image
  # generation). Without it /gen-image falls back to direct REST API calls
  # which work but bypass the MCP tool path documented in the skill.
  if ! command -v gemini >/dev/null 2>&1; then
    printf '[install] WARNING: "gemini" CLI not found — gen-image skill needs it\n'
    case "$PLATFORM" in
      macos) printf '[install]   install: brew install gemini-cli  (or: npm install -g @google/gemini-cli)\n' ;;
      linux) printf '[install]   install: npm install -g @google/gemini-cli\n' ;;
    esac
  else
    # gemini present — also verify the nano banana extension is installed.
    # The extension exposes the mcp_nanobanana_generate_image tool the
    # gen-image skill expects. Without it the skill silently degrades to
    # text-only Gemini responses.
    if [[ ! -d "$HOME/.gemini/extensions/nanobanana" ]]; then
      printf '[install] WARNING: nano banana extension missing — gen-image MCP path disabled\n'
      printf '[install]   install: gemini extensions install https://github.com/gemini-cli-extensions/nanobanana\n'
    fi
  fi
}

# --- opt-in convenience-tool auto-install (INSTALL_TOOLS=1) ------------------
#
# tmux + a clipboard helper make tmux.conf's mouse-copy bindings work; without a
# clipboard tool the copy-pipe path (`$COPY_CMD` in shell/tmux.conf) expands to
# nothing and selections never reach the system clipboard. These are pure
# convenience, so install is opt-in and best-effort: present → skip (idempotent),
# missing + installable without a sudo prompt → install, missing + sudo needed
# but unavailable → same warn-only hint as the default path.

# _pkg_mgr — echo the package manager available on this machine, or "" if none.
_pkg_mgr() {
  case "$PLATFORM" in
    macos) command -v brew    >/dev/null 2>&1 && { echo brew;    return; } ;;
    linux)
      command -v apt-get >/dev/null 2>&1 && { echo apt-get; return; }
      command -v dnf     >/dev/null 2>&1 && { echo dnf;     return; }
      command -v pacman  >/dev/null 2>&1 && { echo pacman;  return; }
      ;;
  esac
  echo ""
}

# _sudo_prefix — echo the command prefix needed to install as the package
# manager requires: "" if already privileged enough, "sudo" if a passwordless
# sudo is available, or "NO" when elevation is needed but cannot be obtained
# non-interactively (caller then falls back to the hint instead of blocking on
# a password prompt). brew must NOT run under sudo, so it is always "".
_sudo_prefix() {
  local mgr="$1"
  [[ "$mgr" == brew ]] && { echo ""; return; }
  [[ "$(id -u)" == "0" ]] && { echo ""; return; }
  if command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
    echo "sudo"
  else
    echo "NO"
  fi
}

# _install_cmd MGR PKG — echo the install command for PKG under MGR (no sudo).
_install_cmd() {
  case "$1" in
    apt-get) echo "apt-get install -y $2" ;;
    dnf)     echo "dnf install -y $2" ;;
    pacman)  echo "pacman -S --noconfirm $2" ;;
    brew)    echo "brew install $2" ;;
  esac
}

# ensure_tool BIN PKG [LABEL] — best-effort install of PKG (providing command
# BIN). Idempotent + same-line-every-run: present → one skip line; missing →
# install (or warn-hint if sudo unavailable). LABEL defaults to BIN.
ensure_tool() {
  local bin="$1" pkg="$2" label="${3:-$1}" mgr sudo_pfx cmd
  if command -v "$bin" >/dev/null 2>&1; then
    debug "$label present (skip)"
    return 0
  fi
  mgr="$(_pkg_mgr)"
  if [[ -z "$mgr" ]]; then
    printf '[install] WARNING: "%s" not found and no known package manager — install manually\n' "$label"
    return 0
  fi
  cmd="$(_install_cmd "$mgr" "$pkg")"
  sudo_pfx="$(_sudo_prefix "$mgr")"
  if [[ "$sudo_pfx" == "NO" ]]; then
    printf '[install] WARNING: "%s" not found — needs elevation, no passwordless sudo\n' "$label"
    printf '[install]   install: sudo %s\n' "$cmd"
    return 0
  fi
  log "installing $label: ${sudo_pfx:+sudo }$cmd"
  # shellcheck disable=SC2086  # $cmd is our own fixed string, word-split intended.
  if run ${sudo_pfx:+sudo} $cmd; then
    # In dry-run nothing actually ran, so skip the post-check (it would always
    # "fail" and emit a misleading WARNING).
    [[ ${DRY_RUN:-0} -eq 1 ]] && return 0
    command -v "$bin" >/dev/null 2>&1 \
      && log "$label installed" \
      || printf '[install] WARNING: %s install ran but %s still missing\n' "$label" "$bin"
  else
    printf '[install] WARNING: %s install failed — install manually: %s\n' "$label" "$cmd"
  fi
}

# ensure_clipboard_tool — install the right clipboard helper for this machine.
# macOS ships pbcopy/pbpaste in the base system, so nothing to install there.
# Linux: Wayland session → wl-clipboard (wl-copy), else X11 → xclip. shell/
# tmux.conf's $COPY_CMD already prefers wl-copy then xclip then xsel, so either
# one satisfies it.
ensure_clipboard_tool() {
  if [[ "$PLATFORM" == macos ]]; then
    debug "clipboard: macOS pbcopy is built-in (skip)"
    return 0
  fi
  if command -v wl-copy >/dev/null 2>&1 || command -v xclip >/dev/null 2>&1 || command -v xsel >/dev/null 2>&1; then
    debug "clipboard tool present (skip)"
    return 0
  fi
  if [[ -n "${WAYLAND_DISPLAY:-}" ]]; then
    ensure_tool wl-copy wl-clipboard "wl-clipboard (Wayland clipboard)"
  else
    ensure_tool xclip xclip "xclip (X11 clipboard)"
  fi
}

# ensure_convenience_tools — orchestrates the opt-in installs. No-op unless
# INSTALL_TOOLS=1, so the default install path keeps the pure warn-only contract.
ensure_convenience_tools() {
  [[ "${INSTALL_TOOLS:-0}" == "1" ]] || return 0
  ensure_tool tmux tmux
  ensure_clipboard_tool
}

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
#   ensure_code_review_graph  — uv tool install of the code-review-graph CLI.
#   ensure_graphify           — uv tool install of the graphify CLI (pkg: graphifyy).
#   ensure_graphify_skill     — link graphify's own SKILL.md to user scope.
#   ensure_tokensave          — brew (macOS) / cargo (Linux) install of tokensave.
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

# --- code-graph CLIs via uv (code-review-graph, graphify) -------------------
#
# Both are installed unconditionally rather than gated behind INSTALL_TOOLS: uv
# resolves its own Python, so there is no sudo and no platform branching. Warn-
# and-skip if uv itself is missing — same contract as jq/gemini above.
#
# Per-project setup is deliberately NOT run here (no `build`, no graph, no
# per-repo MCP wiring): which repos carry a graph is a per-repo decision, made
# inside each project that wants one. See templates/project-code-review-graph.md
# for the routing rules and the per-project `.mcp.json` snippet.

# _bin_present BIN — is BIN on PATH, or present in ~/.local/bin?
# uv tool install (and tokensave's own installer) put shims in ~/.local/bin,
# which some shells (this user's .zshrc has the export commented out) never put
# on PATH — check the known install dir too, same pattern as the
# sync-claudebase skill's bun check.
_bin_present() {
  command -v "$1" >/dev/null 2>&1 || [[ -x "$HOME/.local/bin/$1" ]]
}

# ensure_uv_tool BIN PKG [LABEL] — idempotent `uv tool install` of PKG providing
# command BIN. Same-line-every-run: present → one skip line; missing → install.
# LABEL defaults to BIN (they differ when the PyPI name is not the command name).
ensure_uv_tool() {
  local bin="$1" pkg="$2" label="${3:-$1}"
  if _bin_present "$bin"; then
    debug "$label present (skip)"
    return 0
  fi
  if ! command -v uv >/dev/null 2>&1; then
    printf '[install] WARNING: "%s" not found and uv is missing\n' "$label"
    printf '[install]   install uv: https://docs.astral.sh/uv/getting-started/installation/\n'
    return 0
  fi
  log "installing $label via uv tool install $pkg"
  if run uv tool install "$pkg"; then
    # In dry-run nothing actually ran, so skip the post-check (it would always
    # "fail" and emit a misleading WARNING) — same guard as ensure_tool below.
    [[ ${DRY_RUN:-0} -eq 1 ]] && return 0
    _bin_present "$bin" \
      && log "$label installed" \
      || printf '[install] WARNING: %s install ran but binary still missing — check ~/.local/bin\n' "$label"
  else
    printf '[install] WARNING: uv tool install %s failed\n' "$pkg"
  fi
}

# ensure_code_review_graph — the code-review-graph CLI, github.com/tirth8205/code-review-graph.
ensure_code_review_graph() {
  ensure_uv_tool code-review-graph code-review-graph
}

# ensure_graphify — the graphify CLI, github.com/Graphify-Labs/graphify. The PyPI
# distribution is "graphifyy" (two y's) while the command stays `graphify`.
#
# The [mcp] extra is not optional in practice: the wheel always installs the
# `graphify-mcp` shim, but without the extra it dies on
# `ModuleNotFoundError: No module named 'mcp'` the moment a client connects —
# a broken server that looks installed. The extra costs two packages (mcp,
# starlette) and makes the per-project .mcp.json entry actually work.
#
# Always pass --project when running `graphify install` on a claudebase machine.
# Without it, install.py writes its CLAUDE.md block with Path.write_text into
# ~/.claude/CLAUDE.md; write_text follows the symlink this installer places
# there, so a machine-local tool install edits the repo's own config/CLAUDE.md
# in place and ships to every other machine on the next sync. With --project all
# three artifacts (skill, CLAUDE.md block, PreToolUse hooks) land under the
# project's own .claude/, which is where they belong anyway — the hooks are
# project-scoped in graphify regardless. See templates/project-code-review-graph.md.

# _graphify_mcp_ready — is the [mcp] extra actually importable in graphify's
# uv-managed environment? `command -v graphify-mcp` is not enough: the shim ships
# unconditionally, so a graphifyy installed without the extra passes every
# presence check and only fails when a client connects.
_graphify_mcp_ready() {
  local py="$HOME/.local/share/uv/tools/graphifyy/bin/python"
  [[ -x "$py" ]] && "$py" -c 'import mcp' >/dev/null 2>&1
}

# ensure_tokensave — the tokensave CLI, github.com/aovestdipaperino/tokensave
# (MIT). The third graph, and the only one that indexes markdown without an LLM
# pass, which is why it earns a place next to the two uv tools.
#
# Not a uv tool: it is a Rust binary, so macOS gets the tap (a ~155 MB download,
# but seconds) and Linux falls back to `cargo install`, which COMPILES 34
# tree-sitter grammars and takes many minutes — hence the explicit log line
# rather than a silent stall. No cargo, no install: a prebuilt binary from the
# releases page is the manual path, and the warning names it.
#
# MCP registration is NOT done here — installer/scripts/register_mcp.py owns it,
# because ~/.claude/mcp.json is not a file Claude Code reads.
ensure_tokensave() {
  if _bin_present tokensave; then
    debug "tokensave present (skip)"
    return 0
  fi
  case "$PLATFORM" in
    macos)
      if ! command -v brew >/dev/null 2>&1; then
        printf '[install] WARNING: "tokensave" not found and brew is missing\n'
        printf '[install]   install: https://github.com/aovestdipaperino/tokensave/releases/latest\n'
        return 0
      fi
      log "installing tokensave via brew (tap: aovestdipaperino/tap)"
      run brew install aovestdipaperino/tap/tokensave \
        || printf '[install] WARNING: brew install tokensave failed\n'
      ;;
    linux)
      if ! command -v cargo >/dev/null 2>&1; then
        printf '[install] WARNING: "tokensave" not found and cargo is missing\n'
        printf '[install]   install: https://github.com/aovestdipaperino/tokensave/releases/latest\n'
        return 0
      fi
      log "installing tokensave via cargo (compiles from source — expect several minutes)"
      run cargo install tokensave \
        || printf '[install] WARNING: cargo install tokensave failed\n'
      ;;
  esac
  [[ ${DRY_RUN:-0} -eq 1 ]] && return 0
  _bin_present tokensave \
    && log "tokensave installed" \
    || printf '[install] WARNING: tokensave install ran but binary still missing\n'
}

# _graphify_pkg_dir — path of the installed graphify package, or non-zero.
_graphify_pkg_dir() {
  local py="$HOME/.local/share/uv/tools/graphifyy/bin/python"
  [[ -x "$py" ]] || return 1
  "$py" -c 'import graphify, os; print(os.path.dirname(graphify.__file__))' 2>/dev/null
}

# _graphify_out_dir — the GRAPHIFY_OUT this machine will use, from the baseline
# settings. Falls back to graphify's own default when unset or unreadable.
_graphify_out_dir() {
  python3 - "$REPO_DIR/config/settings.json" <<'PY' 2>/dev/null || echo "graphify-out"
import json, sys
try:
    with open(sys.argv[1], encoding="utf-8") as fh:
        print((json.load(fh).get("env") or {}).get("GRAPHIFY_OUT") or "graphify-out")
except Exception:
    print("graphify-out")
PY
}

# ensure_graphify_skill — install graphify's own SKILL.md at user scope,
# rewritten for this machine's GRAPHIFY_OUT.
#
# RENDERED from the installed package rather than vendored into runtime/skills/:
# the file is 41 KB of build runbook that ships with graphify and changes with
# it, so a copy in this repo would be a second source of truth going stale on
# every upgrade. The package stays the SSOT.
#
# Rendered rather than symlinked because the shipped skill hardcodes the literal
# `graphify-out` in 88 places and never reads GRAPHIFY_OUT, while the CLI does
# (graphify/paths.py). Left as-is the two halves of one tool disagree: the skill
# would `mkdir -p graphify-out` and look for graphify-out/graph.json while the
# CLI writes elsewhere — and its "graph already exists, just query it" fast path
# keys on that same missing file, so every run would fall through to a rebuild.
#
# Cost of rendering over linking: an upgraded graphify does not refresh the copy
# by itself. Re-running install.sh does — the render is compared byte-for-byte
# and rewritten when the package's skill.md changed — and the generated banner
# carries the source version so a mismatch is visible rather than silent.
#
# The skill is worth exposing at all because it is not documentation but the
# *build* procedure (chunked semantic extraction dispatched to subagents).
# Querying needs only the CLI/MCP/hook; building through the skill parallelises
# the chunks, where `graphify extract --backend claude-cli` is pinned to 1.
#
# Not done via `graphify install`, which also writes ~/.claude/CLAUDE.md through
# a symlink into this repo's config/CLAUDE.md (see the note above).
ensure_graphify_skill() {
  local pkg src dst out ver
  pkg="$(_graphify_pkg_dir)" || { debug "graphify package not found (skip skill)"; return 0; }
  src="$pkg/skill.md"
  [[ -f "$src" ]] || { debug "graphify skill.md absent (skip)"; return 0; }
  out="$(_graphify_out_dir)"
  local gbin
  gbin="$(command -v graphify 2>/dev/null || true)"
  [[ -n "$gbin" ]] || gbin="$HOME/.local/bin/graphify"
  ver="$([[ -x "$gbin" ]] && "$gbin" --version 2>/dev/null | awk '{print $2}')"
  [[ -n "$ver" ]] || ver="unknown"
  dst="$CLAUDE_HOME/skills/graphify/SKILL.md"

  if [[ "$out" == "graphify-out" ]]; then
    # No rewrite needed — link so an upgrade is picked up with no install run.
    run mkdir -p "$(dirname "$dst")"
    link_or_copy "$src" "$dst"
    # skill.md delegates its heavier flows (the extraction prompt, --update,
    # query, exports) to a references/ dir. Linking skill.md alone leaves
    # Step 3's semantic pass unable to load its own prompt. Note the dir does
    # NOT sit beside skill.md: that is at the package root while references
    # are per-platform under skills/<platform>/.
    local refs="$pkg/skills/claude/references"
    [[ -d "$refs" ]] || refs="$pkg/references"
    [[ -d "$refs" ]] && link_or_copy "$refs" "$(dirname "$dst")/references"
    return 0
  fi

  local dry=()
  [[ ${DRY_RUN:-0} -eq 1 ]] && dry=(--dry-run)
  # ${dry[@]+...} guard, not a bare "${dry[@]}": macOS ships bash 3.2 (3.2.57
  # here), where expanding an EMPTY array under `set -u` is itself an
  # unbound-variable error — so the guard is needed exactly on the non-dry path,
  # the common one. This branch only became reachable when GRAPHIFY_OUT moved to
  # .graphify; measured 2026-08-10, install.sh exited 1 here on every non-dry
  # run, skipping stages 6+ (this line is 124, prune is 51 — which is why the
  # earlier stages looked healthy).
  python3 "$REPO_DIR/installer/scripts/render_graphify_skill.py" \
    --src "$src" --dst "$dst" --out-dir "$out" --source-version "$ver" ${dry[@]+"${dry[@]}"} \
    || printf '[install] WARNING: graphify skill render failed — skill may reference the wrong output dir\n'
}

# ensure_graph_init — put `graph-init` on PATH.
#
# runtime/bin/graph-init.sh is the one command that gives a project its graphs:
# exclusions, both free builds, and the vendored-tree check that decides whether
# the result is worth keeping. graph-offer.sh names it as a bare verb, so it has
# to resolve without the session knowing where this checkout lives — hence a
# link in ~/.local/bin, the same directory uv drops its shims in and the one
# both graph hooks already fall back to when a shell has not exported it.
#
# Before this existed the offer hook carried the whole procedure as prose and
# every session re-derived it into four commands by hand. That is the failure
# being fixed here, so the link is not optional decoration: without it the hook
# names a verb that does not exist.
ensure_graph_init() {
  local src="$REPO_DIR/runtime/bin/graph-init.sh"
  [[ -f "$src" ]] || { debug "graph-init source missing (skip)"; return 0; }
  # Modes survive git but not every extraction path — cheap and idempotent.
  run chmod +x "$src"
  run mkdir -p "$HOME/.local/bin"
  link_or_copy "$src" "$HOME/.local/bin/graph-init"
}

ensure_graphify() {
  ensure_uv_tool graphify "graphifyy[mcp]" graphify
  # Self-heal machines that installed graphifyy before the extra was pinned here:
  # the presence check above skips them, so the broken MCP server would persist
  # forever. One --force reinstall fixes it and every later run is silent again.
  _graphify_mcp_ready && return 0
  command -v uv >/dev/null 2>&1 || return 0
  log "graphify present without the [mcp] extra — reinstalling to repair graphify-mcp"
  run uv tool install --force "graphifyy[mcp]" \
    || printf '[install] WARNING: graphify [mcp] reinstall failed — graphify-mcp will not start\n'
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

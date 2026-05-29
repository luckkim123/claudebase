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
COPY_MODE=0
DRY_RUN=0
VERBOSE=0
PRUNE_PLUGINS=0

for arg in "$@"; do
  case "$arg" in
    --copy) COPY_MODE=1 ;;
    --dry-run) DRY_RUN=1 ;;
    --verbose) VERBOSE=1 ;;
    --prune-plugins) PRUNE_PLUGINS=1 ;;
    -h|--help) sed -n '2,7p' "$0"; exit 0 ;;
    *) echo "Unknown arg: $arg" >&2; exit 1 ;;
  esac
done

OS="$(uname -s)"
case "$OS" in
  Darwin) PLATFORM="macos" ;;
  Linux)  PLATFORM="linux" ;;
  *) echo "Unsupported OS: $OS — use install.ps1 on Windows" >&2; exit 1 ;;
esac

CLAUDE_HOME="$HOME/.claude"

# Runtime dependency check — warn-only so install.sh remains idempotent.
# Each block checks one optional dependency and emits a single WARNING line
# plus an installation hint when missing. Nothing is auto-installed — the user
# decides whether to run the suggested command.
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
check_runtime_deps

log()   { printf '[install] %s\n' "$*"; }
debug() { [[ $VERBOSE -eq 1 ]] && printf '[debug]   %s\n' "$*" || true; }

# run COMMAND ARG... — executes a command as an array (no eval, no shell metachar surprises)
run() {
  if [[ $DRY_RUN -eq 1 ]]; then
    printf '[dry-run] '
    printf '%q ' "$@"
    printf '\n'
  else
    "$@"
  fi
}

remove_if_exists() {
  # Clear a path so a fresh symlink (or rendered file) can be placed there.
  # No backup is made — recovery is via git history. See repo CLAUDE.md
  # ("Idempotency is non-negotiable" / "Don'ts: backups in install").
  local target="$1"
  if [[ -L "$target" ]] || [[ -e "$target" ]]; then
    run rm -f "$target"
  fi
}

# already_linked TARGET SRC — true if TARGET is a symlink resolving to SRC
already_linked() {
  local target="$1" src="$2"
  [[ -L "$target" && "$(readlink "$target")" == "$src" ]]
}

link_or_copy() {
  local src="$1" dest="$2"
  [[ -e "$src" ]] || { log "skip (missing source): $src"; return; }
  if [[ $COPY_MODE -eq 0 ]] && already_linked "$dest" "$src"; then
    debug "already linked: $dest -> $src (skip)"
    return
  fi
  remove_if_exists "$dest"
  if [[ $COPY_MODE -eq 1 ]]; then
    run cp -R "$src" "$dest"
    log "copied:  $dest"
  else
    run ln -s "$src" "$dest"
    log "linked:  $dest -> $src"
  fi
}

# 1. ~/.claude/
[[ -d "$CLAUDE_HOME" ]] || run mkdir -p "$CLAUDE_HOME"

# 2. user-level settings.json
link_or_copy "$REPO_DIR/config/settings.json" "$CLAUDE_HOME/settings.json"

# 2b. user-level CLAUDE.md — universal behavioral rules applied across all projects
link_or_copy "$REPO_DIR/config/CLAUDE.md" "$CLAUDE_HOME/CLAUDE.md"

# 3. mcp.json — render template (substitute ${VAR} from secrets.env if present).
#    Idempotent: skip rewrite when rendered content matches the existing file.
SECRETS_FILE="$REPO_DIR/secrets/secrets.env"
TEMPLATE="$REPO_DIR/config/mcp.template.json"
if [[ -f "$TEMPLATE" ]]; then
  if [[ $DRY_RUN -eq 1 ]]; then
    log "would render: $CLAUDE_HOME/mcp.json"
  else
    content="$(cat "$TEMPLATE")"
    if [[ -f "$SECRETS_FILE" ]]; then
      # M3: parse secrets.env as literal strings — do NOT use `set -a; source`
      # which would shell-expand values like `SK=sk-foo$abc` into wrong strings.
      # Values are read verbatim; surrounding quotes (single or double) are stripped
      # but no parameter expansion or command substitution is performed.
      resolved=0
      while IFS= read -r line || [ -n "$line" ]; do
        [[ "$line" =~ ^[[:space:]]*$  ]] && continue   # blank
        [[ "$line" =~ ^[[:space:]]*#  ]] && continue   # comment
        key="${line%%=*}"
        value="${line#*=}"
        key="${key// /}"
        [[ -z "$key" ]] && continue
        # Strip surrounding double or single quotes (but NOT shell-expand $vars)
        value="${value%\"}"; value="${value#\"}"
        value="${value%\'}"; value="${value#\'}"
        if [[ "$content" == *"\${${key}}"* ]]; then
          content="${content//\$\{${key}\}/${value}}"
          resolved=$((resolved + 1))
        fi
      done < "$SECRETS_FILE"
      debug "resolved $resolved \${VAR} placeholder(s) from secrets.env"
    fi
    if [[ "$content" == *'${'* ]]; then
      log "WARNING: unresolved \${...} placeholders remain in mcp.json — check secrets/secrets.env"
    fi
    if [[ -f "$CLAUDE_HOME/mcp.json" ]] && [[ "$content" == "$(cat "$CLAUDE_HOME/mcp.json")" ]]; then
      debug "mcp.json unchanged (skip)"
    else
      remove_if_exists "$CLAUDE_HOME/mcp.json"
      printf '%s\n' "$content" > "$CLAUDE_HOME/mcp.json"
      chmod 600 "$CLAUDE_HOME/mcp.json"
      log "rendered: $CLAUDE_HOME/mcp.json (perm 600)"
    fi
  fi
fi

# 4. shell config (Unix only)
[[ -f "$REPO_DIR/shell/tmux.conf" ]] && link_or_copy "$REPO_DIR/shell/tmux.conf" "$HOME/.tmux.conf"

# 4b. user-scope skills — symlink each subdirectory individually so we don't
#     clobber any other skills the user has under ~/.claude/skills/.
if [[ -d "$REPO_DIR/runtime/skills" ]]; then
  run mkdir -p "$CLAUDE_HOME/skills"
  for skill_dir in "$REPO_DIR/runtime/skills"/*/; do
    [[ -d "$skill_dir" ]] || continue
    skill_name="${skill_dir%/}"; skill_name="${skill_name##*/}"
    link_or_copy "${skill_dir%/}" "$CLAUDE_HOME/skills/$skill_name"
  done
fi

# 4c. user-scope agents — symlink each .md individually so we don't clobber
#     any other agents the user has under ~/.claude/agents/.
if [[ -d "$REPO_DIR/runtime/agents" ]]; then
  run mkdir -p "$CLAUDE_HOME/agents"
  for agent_file in "$REPO_DIR/runtime/agents"/*.md; do
    [[ -f "$agent_file" ]] || continue
    agent_name="${agent_file##*/}"
    link_or_copy "$agent_file" "$CLAUDE_HOME/agents/$agent_name"
  done
fi

# 5. platform-specific extra steps
PLATFORM_INSTALLER="$REPO_DIR/platform/$PLATFORM/install.sh"
if [[ -f "$PLATFORM_INSTALLER" ]]; then
  log "running platform installer: $PLATFORM"
  run bash "$PLATFORM_INSTALLER"
fi

# 5b. project-scope hook deployment — merge OMC reference auto-loader into
#     each known project's .claude/settings.json. Idempotent: re-runs detect
#     and replace the existing entry via marker string. Silently skips
#     projects that don't exist on this machine.
HOOK_FRAGMENT="$REPO_DIR/runtime/hooks/omc-reference-loader.json"
HOOK_MERGER="$REPO_DIR/runtime/hooks/merge-project-hook.py"
HOOK_MARKER="OMC_REFERENCE_AUTO_LOAD"
# M4: PROJECT_TARGETS read from ~/.claude/settings.local.json (gitignored) so
# machine-specific paths are not baked into the shared repo. The key is
# "projectTargets": ["~/Desktop/workspace", "~/ksm_Obsidian"]. Tilde is
# expanded to $HOME. Falls back to the previous hardcoded list on first run
# (before settings.local.json exists) for backward compatibility.
PROJECT_TARGETS=()
if [ -f "$CLAUDE_HOME/settings.local.json" ]; then
  while IFS= read -r p; do
    expanded="${p/#\~/$HOME}"
    [ -d "$expanded" ] && PROJECT_TARGETS+=("$expanded")
  done < <(python3 -c "import json,sys; d=json.load(open('$CLAUDE_HOME/settings.local.json')); print('\n'.join(d.get('projectTargets',[])))" 2>/dev/null || true)
fi
# Fallback to previous defaults if settings.local.json missing or has no projectTargets.
if [ ${#PROJECT_TARGETS[@]} -eq 0 ]; then
  PROJECT_TARGETS=("$HOME/Desktop/workspace" "$HOME/ksm_Obsidian")
fi
if [[ -f "$HOOK_FRAGMENT" && -f "$HOOK_MERGER" ]]; then
  for project_root in "${PROJECT_TARGETS[@]}"; do
    [[ -d "$project_root" ]] || { debug "skip project hook: $project_root not present"; continue; }
    project_claude="$project_root/.claude"
    run mkdir -p "$project_claude"
    target_file="$project_claude/settings.json"
    if [[ $DRY_RUN -eq 1 ]]; then
      log "would merge OMC hook into: $target_file"
    else
      output=$(python3 "$HOOK_MERGER" "$HOOK_FRAGMENT" "$target_file" "$HOOK_MARKER" 2>&1)
      rc=$?
      case $rc in
        0) log "project hook: $output" ;;
        2) debug "skip project hook: parent missing for $target_file" ;;
        *) log "WARNING: project hook merge failed (rc=$rc) for $target_file: $output" ;;
      esac
    fi
  done
else
  debug "skip project hook deployment: fragment or merger missing"
fi

# 6. plugin sync — delegate to installer/scripts/plugin_sync.py.
#    The Python module owns the decision logic (Action enum + Decision dataclass)
#    and the marketplace/OS-gate metadata lookup. Bash here only forwards flags
#    and prefixes each output line with the [install] tag. See plugin_sync.py
#    docstring for the full contract. Tested under tests/installer/test_plugin_sync.py.
sync_plugins() {
  if ! command -v claude >/dev/null 2>&1; then
    log "skip plugin sync: 'claude' not in PATH (install Claude Code, then re-run)"
    return
  fi
  if ! command -v python3 >/dev/null 2>&1; then
    log "skip plugin sync: 'python3' not available"
    return
  fi
  local args=(--apply)
  [[ $DRY_RUN -eq 1 ]] && args=(--dry-run)
  [[ $PRUNE_PLUGINS -eq 1 ]] && args+=(--prune)
  python3 "$REPO_DIR/installer/scripts/plugin_sync.py" "${args[@]}" 2>&1 \
    | while IFS= read -r line; do log "$line"; done
}
sync_plugins

# 6.5. OMC bash-failure freeze workaround
#      Delegated to installer/scripts/patch_omc_freeze.sh + docs/upstream-patches.md
#      since P1 G4.1 (2026-05-29). The script owns the marker check, BSD/GNU sed
#      branch, and the find loop. See docs/upstream-patches.md for the why and
#      the removal condition.
if [[ -x "$REPO_DIR/installer/scripts/patch_omc_freeze.sh" ]]; then
  DRY_RUN="$DRY_RUN" bash "$REPO_DIR/installer/scripts/patch_omc_freeze.sh" 2>&1 \
    | while IFS= read -r line; do log "$line"; done
fi

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

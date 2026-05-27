#!/usr/bin/env bash
# claude-settings installer (macOS / Linux)
# Usage: ./install.sh [--copy] [--dry-run] [--verbose] [--prune-plugins]
#   --copy            Copy files instead of symlinking (less convenient for sync)
#   --dry-run         Show actions without executing
#   --verbose         Print extra detail (idempotent skips, resolved secrets count)
#   --prune-plugins   Uninstall user-scope plugins not in any enabledPlugins
#                     (default: warn only — keeps drift-kept plugins installed)

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
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
BACKUP_DIR="$CLAUDE_HOME/.backup-$(date +%Y%m%d-%H%M%S)"

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

backup_if_needed() {
  local target="$1"
  if [[ -L "$target" ]]; then
    run rm "$target"
  elif [[ -e "$target" ]]; then
    run mkdir -p "$BACKUP_DIR"
    run mv "$target" "$BACKUP_DIR/"
    log "backed up: $target -> $BACKUP_DIR/"
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
  backup_if_needed "$dest"
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
link_or_copy "$REPO_DIR/claude/settings.json" "$CLAUDE_HOME/settings.json"

# 2b. user-level CLAUDE.md — universal behavioral rules applied across all projects
link_or_copy "$REPO_DIR/claude/CLAUDE.md" "$CLAUDE_HOME/CLAUDE.md"

# 3. mcp.json — render template (substitute ${VAR} from secrets.env if present).
#    Idempotent: skip backup + rewrite when rendered content matches the existing file.
SECRETS_FILE="$REPO_DIR/secrets/secrets.env"
TEMPLATE="$REPO_DIR/claude/mcp.template.json"
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
      backup_if_needed "$CLAUDE_HOME/mcp.json"
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
if [[ -d "$REPO_DIR/skills" ]]; then
  run mkdir -p "$CLAUDE_HOME/skills"
  for skill_dir in "$REPO_DIR/skills"/*/; do
    [[ -d "$skill_dir" ]] || continue
    skill_name="${skill_dir%/}"; skill_name="${skill_name##*/}"
    link_or_copy "${skill_dir%/}" "$CLAUDE_HOME/skills/$skill_name"
  done
fi

# 4c. user-scope agents — symlink each .md individually so we don't clobber
#     any other agents the user has under ~/.claude/agents/.
if [[ -d "$REPO_DIR/agents" ]]; then
  run mkdir -p "$CLAUDE_HOME/agents"
  for agent_file in "$REPO_DIR/agents"/*.md; do
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
HOOK_FRAGMENT="$REPO_DIR/claude/hooks/omc-reference-loader.json"
HOOK_MERGER="$REPO_DIR/claude/hooks/merge-project-hook.py"
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

# 5c. user-scope using-omc routing loader — merge into ~/.claude/settings.json so
#     the OMC routing rule is resident in every session (not just project targets,
#     unlike the project-scoped omc-reference catalog loader above). Idempotent via
#     marker USING_OMC_AUTO_LOAD. Reuses the same target-agnostic HOOK_MERGER.
USING_OMC_FRAGMENT="$REPO_DIR/claude/hooks/using-omc-loader.json"
USING_OMC_MARKER="USING_OMC_AUTO_LOAD"
if [[ -f "$USING_OMC_FRAGMENT" && -f "$HOOK_MERGER" ]]; then
  if [[ $DRY_RUN -eq 1 ]]; then
    log "would merge using-omc loader into: $CLAUDE_HOME/settings.json"
  else
    output=$(python3 "$HOOK_MERGER" "$USING_OMC_FRAGMENT" "$CLAUDE_HOME/settings.json" "$USING_OMC_MARKER" 2>&1)
    rc=$?
    case $rc in
      0) log "using-omc hook: $output" ;;
      2) debug "skip using-omc hook: $CLAUDE_HOME/settings.json parent missing" ;;
      *) log "WARNING: using-omc hook merge failed (rc=$rc): $output" ;;
    esac
  fi
else
  debug "skip using-omc hook: fragment or merger missing"
fi

# 6. plugin sync — ensure every enabledPlugin in settings.json is installed at
#    user scope. Idempotent: plugins already at user scope are skipped; ones
#    registered at project/local scope (or with stale "unknown" version) are
#    uninstalled and reinstalled at user scope. Skips cleanly if `claude` or
#    `python3` is unavailable (e.g. before Claude Code is installed).
sync_plugins() {
  if ! command -v claude >/dev/null 2>&1; then
    log "skip plugin sync: 'claude' not in PATH (install Claude Code, then re-run)"
    return
  fi
  if ! command -v python3 >/dev/null 2>&1; then
    log "skip plugin sync: 'python3' not available"
    return
  fi

  # Single python pass — emit one line per plugin: name TAB scope TAB enabled TAB is_installed
  # Collapses 4 separate heredocs (H2/M2/OPT1) into one invocation; reads both
  # settings.json (enabledPlugins) and installed_plugins.json in one pass.
  # Output format (tab-separated per line):
  #   <plugin_name> \t <installed_scope|none> \t enabled   (for enabled plugins)
  #   <plugin_name> \t <installed_scope>       \t installed (for user-scope installed-only)
  local py_output
  py_output="$(CLAUDE_HOME="$CLAUDE_HOME" python3 - <<'PY' 2>/dev/null
import json, os, sys, traceback

claude_home = os.environ["CLAUDE_HOME"]

# Parse settings.json
try:
    d = json.load(open(os.path.join(claude_home, "settings.json")))
    enabled_map = {k: v for k, v in d.get("enabledPlugins", {}).items() if v}
except Exception as e:
    import traceback
    print(f"[install] WARNING: settings.json parse failed: {e}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    enabled_map = {}

# Parse installed_plugins.json
try:
    ip = os.path.join(claude_home, "plugins", "installed_plugins.json")
    installed = json.load(open(ip)) if os.path.exists(ip) else {}
    installed_plugins = installed.get("plugins", {})
except Exception:
    installed_plugins = {}

# Emit enabled plugins with their installed scope
for plugin_name in enabled_map:
    entries = installed_plugins.get(plugin_name, [])
    scope = entries[0].get("scope", "none") if entries else "none"
    print(f"{plugin_name}\t{scope}\tenabled")

# Parse settings.local.json for drift detection
try:
    lp = os.path.join(claude_home, "settings.local.json")
    if os.path.exists(lp):
        dl = json.load(open(lp))
        for k, v in dl.get("enabledPlugins", {}).items():
            if v and k not in enabled_map:
                entries = installed_plugins.get(k, [])
                scope = entries[0].get("scope", "none") if entries else "none"
                print(f"{k}\t{scope}\tlocal")
except Exception:
    pass

# Emit user-scope installed plugins not in enabled (for drift detection)
for name, entries in installed_plugins.items():
    for e in entries:
        if e.get("scope") == "user":
            print(f"{name}\tuser\tinstalled")
            break
PY
)" || true

  # Extract just enabled plugin names for the marketplace checks and main loop
  local enabled
  enabled="$(printf '%s\n' "$py_output" | awk -F'\t' '$3=="enabled" {print $1}')"

  if [[ -z "$enabled" ]]; then
    debug "no enabledPlugins to sync"
    return
  fi

  # Marketplace-exists check. `claude plugin marketplace list` prints entries
  # as `  ❯ <name>` followed by `    Source: ...` — we extract just the names.
  # Previous per-marketplace grep patterns were inconsistent (^name vs name vs
  # \bname\b), causing the axlabs branch to re-add on every run because the
  # leading "  ❯ " prefix never matched `^axlabs`.
  # OPT6: cache once so we don't re-invoke claude for each marketplace check.
  local MARKETPLACES
  MARKETPLACES="$(claude plugin marketplace list 2>/dev/null | awk '/❯/ {print $2}')" || MARKETPLACES=""
  marketplace_exists() {
    local name="$1"
    echo "$MARKETPLACES" | grep -qx "$name"
  }

  # Ensure canonical marketplace exists if any plugin references it
  if echo "$enabled" | grep -q "@claude-plugins-official"; then
    if ! marketplace_exists "claude-plugins-official"; then
      log "adding marketplace: anthropics/claude-plugins-official"
      run claude plugin marketplace add anthropics/claude-plugins-official >/dev/null 2>&1 \
        || log "  WARNING: failed to add marketplace; check network"
    fi
  fi

  # AX Labs marketplace (mckinsey-pptx for ppt-academic skill)
  if echo "$enabled" | grep -q "@axlabs"; then
    if ! marketplace_exists "axlabs"; then
      log "adding marketplace: seulee26/mckinsey-pptx (axlabs)"
      run claude plugin marketplace add seulee26/mckinsey-pptx >/dev/null 2>&1 \
        || log "  WARNING: failed to add axlabs marketplace; check network"
    fi
  fi

  # OMC marketplace (Yeachan-Heo/oh-my-claudecode — multi-agent orchestration)
  if echo "$enabled" | grep -q "@omc"; then
    if ! marketplace_exists "omc"; then
      log "adding marketplace: Yeachan-Heo/oh-my-claudecode (omc)"
      run claude plugin marketplace add Yeachan-Heo/oh-my-claudecode >/dev/null 2>&1 \
        || log "  WARNING: failed to add omc marketplace; check network"
    fi

    # OMC shell CLI (oh-my-claude-sisyphus) — required for `omc team` / tmux pane workers.
    # Plugin alone only provides slash commands; the shell `omc` binary is a separate npm package.
    if ! command -v omc >/dev/null 2>&1; then
      if command -v npm >/dev/null 2>&1; then
        log "installing omc shell CLI: npm i -g oh-my-claude-sisyphus@latest"
        run npm i -g oh-my-claude-sisyphus@latest >/dev/null 2>&1 \
          || log "  WARNING: failed to install oh-my-claude-sisyphus; run manually"
      else
        log "  WARNING: npm not found; skipping omc shell CLI install"
      fi
    fi
  fi

  # heroacademia marketplace (luckkim123/oh-my-heroacademia — personal meta-harness;
  # publishes own-code plugins like oh-my-docs). Plugin entries use commit-SHA
  # versioning (no version field), so `marketplace update heroacademia` picks up
  # pushes without manual bumps. Git source clones over SSH — needs a GitHub SSH key
  # on this machine (or `gh auth setup-git`); not configured here to avoid touching
  # the user's global git config.
  # OS gate: OMD is document work (pptx/docx/xlsx/hwpx) that targets macOS; Linux is
  # not a document-authoring environment here, so skip it. Windows is handled by
  # install.ps1, not this script ($PLATFORM is only ever macos/linux here).
  if echo "$enabled" | grep -q "@heroacademia"; then
    if [[ "$PLATFORM" != "macos" ]]; then
      log "skipping heroacademia (OMD): document work targets macOS; PLATFORM=$PLATFORM"
    elif ! marketplace_exists "heroacademia"; then
      log "adding marketplace: luckkim123/oh-my-heroacademia (heroacademia)"
      run claude plugin marketplace add https://github.com/luckkim123/oh-my-heroacademia.git >/dev/null 2>&1 \
        || log "  WARNING: failed to add heroacademia marketplace; check network/SSH key"
    fi
  fi

  local plugin current ok=0 fixed=0 failed=0
  while IFS= read -r plugin || [[ -n "$plugin" ]]; do
    [[ -z "$plugin" ]] && continue
    # Look up installed scope from py_output (tab-separated: name\tscope\ttype).
    # Use grep+awk instead of associative array for bash 3 compatibility.
    current="$(printf '%s\n' "$py_output" \
      | awk -F'\t' -v p="$plugin" '$1==p && $3=="enabled" {print $2; exit}')"
    [[ -z "$current" ]] && current="none"
    if [[ "$current" == "user" ]]; then
      debug "plugin OK (user): $plugin"
      ok=$((ok+1))
      continue
    fi
    if [[ $DRY_RUN -eq 1 ]]; then
      log "would re-register at user scope: $plugin (currently: $current)"
      continue
    fi
    if [[ "$current" != "none" && "$current" != "user" ]]; then
      claude plugin uninstall -s "$current" -y "$plugin" >/dev/null 2>&1 || true
    fi
    if claude plugin install -s user "$plugin" >/dev/null 2>&1; then
      log "plugin reinstalled (user): $plugin"
      fixed=$((fixed+1))
    else
      log "  WARNING: failed to install: $plugin"
      failed=$((failed+1))
    fi
  done <<< "$enabled"

  # Reverse drift: detect user-scope plugins not in enabledPlugins of either
  # settings.json (common) or settings.local.json (per-machine). Default action
  # is WARN ONLY — uninstall requires explicit --prune-plugins. Rationale:
  # trimming the common pool on machine A would otherwise silently uninstall
  # those plugins on machine B during the next sync, surprising the user.
  # The warn-only default invites the user to either register as per-machine
  # in settings.local.json or re-run install.sh --prune-plugins to remove.

  # Use py_output for both enabled_local and installed_user (already computed above).
  local enabled_local
  enabled_local="$(printf '%s\n' "$py_output" | awk -F'\t' '$3=="local" {print $1}')"

  local expected
  expected="$(printf '%s\n%s\n' "$enabled" "$enabled_local" | sort -u | sed '/^$/d')"

  local installed_user
  installed_user="$(printf '%s\n' "$py_output" | awk -F'\t' '$2=="user" && $3=="installed" {print $1}')"

  local drift removed=0 kept=0
  drift="$(comm -23 <(printf '%s\n' "$installed_user" | sort -u | sed '/^$/d') \
                    <(printf '%s\n' "$expected"       | sort -u | sed '/^$/d'))"

  while IFS= read -r plugin || [[ -n "$plugin" ]]; do
    [[ -z "$plugin" ]] && continue
    if [[ $PRUNE_PLUGINS -eq 0 ]]; then
      log "plugin drift (kept): $plugin — register in settings.local.json or re-run with --prune-plugins to remove"
      kept=$((kept+1))
      continue
    fi
    if [[ $DRY_RUN -eq 1 ]]; then
      log "would uninstall (not in any enabledPlugins): $plugin"
      continue
    fi
    if claude plugin uninstall -s user -y "$plugin" >/dev/null 2>&1; then
      log "plugin uninstalled (drift): $plugin"
      removed=$((removed+1))
    else
      log "  WARNING: failed to uninstall: $plugin"
    fi
  done <<< "$drift"

  log "plugin sync: $ok already user-scope, $fixed fixed, $removed removed, $kept drift-kept, $failed failed"
}
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
#    The HUD wrapper is just two file copies + chmod (see the `hud` skill's
#    setup steps), so we generate it directly from the plugin's canonical
#    template instead of waiting for a live `/oh-my-claudecode:hud setup`.
#    Idempotent: regenerated every install, then re-customized below.
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

  mkdir -p "$CLAUDE_HOME/hud/lib"
  cp "$tmpl" "$CLAUDE_HOME/hud/omc-hud.mjs"
  cp "$cfgdir" "$CLAUDE_HOME/hud/lib/config-dir.mjs"
  chmod 755 "$CLAUDE_HOME/hud/omc-hud.mjs"
  # Drop any legacy script left by older OMC versions.
  [[ -f "$CLAUDE_HOME/hud/omc-hud.js" ]] && rm -f "$CLAUDE_HOME/hud/omc-hud.js"
  log "installed HUD wrapper -> $CLAUDE_HOME/hud/omc-hud.mjs"

  # Re-apply local HUD customization (line1: cyan dir:/branch:, lowercase
  # model:). The fresh copy above always drops it, so this re-injects it.
  bash "$REPO_DIR/claude/scripts/hud-customize.sh" 2>&1 | while IFS= read -r line; do log "$line"; done
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
    if [[ -n "$(git -C "$REPO_DIR" status --porcelain claude/settings.json 2>/dev/null)" ]]; then
      log "drift: claude/settings.json modified by Claude CLI — review with: git -C $REPO_DIR diff claude/settings.json"
    fi
  fi
fi

log "done. backup dir created only if a non-symlink file was overwritten."

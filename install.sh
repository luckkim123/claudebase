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
# `jq` is required by the statusLine command in claude/settings.json; without
# it the status line silently renders as literal template text (e.g. "ctx:%").
check_runtime_deps() {
  command -v jq >/dev/null 2>&1 && return
  printf '[install] WARNING: "jq" not found — statusLine will degrade silently\n'
  case "$PLATFORM" in
    macos) printf '[install]   install: brew install jq\n' ;;
    linux) printf '[install]   install: sudo apt-get install -y jq  (Debian/Ubuntu)\n' ;;
  esac
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
      set -a; source "$SECRETS_FILE"; set +a
      resolved=0
      while IFS='=' read -r key _; do
        [[ -z "$key" || "$key" =~ ^[[:space:]]*# ]] && continue
        key="${key// /}"
        value="${!key:-}"
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
    skill_name="$(basename "$skill_dir")"
    link_or_copy "${skill_dir%/}" "$CLAUDE_HOME/skills/$skill_name"
  done
fi

# 4c. user-scope agents — symlink each .md individually so we don't clobber
#     any other agents the user has under ~/.claude/agents/.
if [[ -d "$REPO_DIR/agents" ]]; then
  run mkdir -p "$CLAUDE_HOME/agents"
  for agent_file in "$REPO_DIR/agents"/*.md; do
    [[ -f "$agent_file" ]] || continue
    agent_name="$(basename "$agent_file")"
    link_or_copy "$agent_file" "$CLAUDE_HOME/agents/$agent_name"
  done
fi

# 5. platform-specific extra steps
PLATFORM_INSTALLER="$REPO_DIR/platform/$PLATFORM/install.sh"
if [[ -f "$PLATFORM_INSTALLER" ]]; then
  log "running platform installer: $PLATFORM"
  run bash "$PLATFORM_INSTALLER"
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

  local enabled
  enabled="$(CLAUDE_HOME="$CLAUDE_HOME" python3 - <<'PY' 2>/dev/null
import json, os
try:
    d = json.load(open(os.path.join(os.environ["CLAUDE_HOME"], "settings.json")))
    for k, v in d.get("enabledPlugins", {}).items():
        if v:
            print(k)
except Exception:
    pass
PY
)" || true

  if [[ -z "$enabled" ]]; then
    debug "no enabledPlugins to sync"
    return
  fi

  # Marketplace-exists check. `claude plugin marketplace list` prints entries
  # as `  ❯ <name>` followed by `    Source: ...` — we extract just the names.
  # Previous per-marketplace grep patterns were inconsistent (^name vs name vs
  # \bname\b), causing the axlabs branch to re-add on every run because the
  # leading "  ❯ " prefix never matched `^axlabs`.
  marketplace_exists() {
    local name="$1"
    claude plugin marketplace list 2>/dev/null \
      | awk '/❯/ {print $2}' \
      | grep -qx "$name"
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

  local plugin current ok=0 fixed=0 failed=0
  while IFS= read -r plugin || [[ -n "$plugin" ]]; do
    [[ -z "$plugin" ]] && continue
    current="$(PLUGIN="$plugin" CLAUDE_HOME="$CLAUDE_HOME" python3 - <<'PY' 2>/dev/null
import json, os
try:
    d = json.load(open(os.path.join(os.environ["CLAUDE_HOME"], "plugins", "installed_plugins.json")))
    es = d.get("plugins", {}).get(os.environ["PLUGIN"], [])
    print(es[0].get("scope", "") if es else "none")
except Exception:
    print("none")
PY
)"
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
  local enabled_local
  enabled_local="$(CLAUDE_HOME="$CLAUDE_HOME" python3 - <<'PY' 2>/dev/null
import json, os
p = os.path.join(os.environ["CLAUDE_HOME"], "settings.local.json")
if os.path.exists(p):
    try:
        d = json.load(open(p))
        for k, v in d.get("enabledPlugins", {}).items():
            if v:
                print(k)
    except Exception:
        pass
PY
)" || true

  local expected
  expected="$(printf '%s\n%s\n' "$enabled" "$enabled_local" | sort -u | sed '/^$/d')"

  local installed_user
  installed_user="$(CLAUDE_HOME="$CLAUDE_HOME" python3 - <<'PY' 2>/dev/null
import json, os
p = os.path.join(os.environ["CLAUDE_HOME"], "plugins", "installed_plugins.json")
try:
    d = json.load(open(p))
    for name, entries in d.get("plugins", {}).items():
        for e in entries:
            if e.get("scope") == "user":
                print(name)
                break
except Exception:
    pass
PY
)"

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

# 7. local-overrides hint
LOCAL_FILE="$CLAUDE_HOME/settings.local.json"
if [[ ! -e "$LOCAL_FILE" ]]; then
  log "hint: no $LOCAL_FILE — see templates/settings.local.example.json for per-machine plugin overrides"
fi

# 8. oh-my-claudecode HUD setup hint
#    OMC's HUD statusline is installed lazily on first /oh-my-claudecode:hud or
#    /omc-setup invocation. Auto-running it here would require a live Claude Code
#    session, so we only print the next step instead of automating it.
if python3 -c "import json; d=json.load(open('$CLAUDE_HOME/settings.json')); exit(0 if d.get('enabledPlugins', {}).get('oh-my-claudecode@omc') else 1)" 2>/dev/null; then
  if [[ ! -f "$CLAUDE_HOME/hud/omc-hud.mjs" ]]; then
    log "next: open Claude Code and run '/oh-my-claudecode:omc-setup' to finish HUD install"
  fi
fi

# 9. settings.json drift check (warn-only)
#    settings.json is symlinked, so the Claude Code CLI writes straight back
#    into the repo when it auto-formats or persists new settings. Surface this
#    so the user can decide to commit, discard, or update the canonical file.
if command -v git >/dev/null 2>&1; then
  if [[ -n "$(git -C "$REPO_DIR" status --porcelain claude/settings.json 2>/dev/null)" ]]; then
    log "drift: claude/settings.json modified by Claude CLI — review with: git -C $REPO_DIR diff claude/settings.json"
  fi
fi

log "done. backup dir created only if a non-symlink file was overwritten."

# shellcheck shell=bash
# installer/lib/secrets.sh — render mcp.template.json with secrets.env values.
#
# Source order: after lib/log.sh and lib/link.sh (uses log/debug/remove_if_exists).
#
# Exposes:
#   render_mcp_json   — substitute ${VAR} from secrets/secrets.env, write
#                       $CLAUDE_HOME/mcp.json with perm 600. Idempotent: skip
#                       rewrite when content matches existing file.
#
# Security notes:
# - M3: secrets.env is parsed as LITERAL strings — no `set -a; source` because
#   shell-expansion would mangle values like `SK=sk-foo$abc`. Surrounding
#   single/double quotes are stripped but no $VAR or $(...) expansion runs.
# - Final mcp.json is chmod 600 so other users on the box can't read API keys.
# - Unresolved ${...} placeholders trigger a WARNING but DO NOT fail the
#   install — secrets/secrets.env is optional on fresh machines.

render_mcp_json() {
  local SECRETS_FILE="$REPO_DIR/secrets/secrets.env"
  local TEMPLATE="$REPO_DIR/config/mcp.template.json"
  [[ -f "$TEMPLATE" ]] || return 0

  if [[ $DRY_RUN -eq 1 ]]; then
    log "would render: $CLAUDE_HOME/mcp.json"
    return 0
  fi

  local content
  content="$(cat "$TEMPLATE")"

  if [[ -f "$SECRETS_FILE" ]]; then
    local resolved=0 line key value
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
}

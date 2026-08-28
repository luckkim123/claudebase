# shellcheck shell=bash
# installer/lib/project_hooks.sh — merge OMC reference auto-loader into each
# known project's .claude/settings.json.
#
# Source order: after lib/args.sh (needs CLAUDE_HOME, DRY_RUN) and lib/log.sh.
#
# Exposes:
#   deploy_project_hooks   — for each PROJECT_TARGETS entry, invoke
#                            merge-project-hook.py; silently skip missing dirs.
#
# Idempotency: the python merger detects the marker string OMC_REFERENCE_AUTO_LOAD
# and replaces the existing entry, so re-runs are zero-action.
#
# M4 origin: PROJECT_TARGETS read from ~/.claude/settings.local.json (gitignored)
# so machine-specific paths are not baked into this repo.
#
# There is deliberately NO fallback list. This repo is public, and this function
# creates `<target>/.claude/` and writes settings.json into it — so any default
# would make a stranger's install write into an unrelated directory that merely
# happens to share the name. (The removed default was `~/workspace` and
# `~/ksm_Obsidian`; `~/workspace` in particular is a common directory name.)
# With no projectTargets configured, this stage is a no-op.

deploy_project_hooks() {
  local HOOK_FRAGMENT="$REPO_DIR/runtime/hooks/omc-reference-loader.json"
  local HOOK_MERGER="$REPO_DIR/runtime/hooks/merge-project-hook.py"
  local HOOK_MARKER="OMC_REFERENCE_AUTO_LOAD"

  local PROJECT_TARGETS=()
  if [ -f "$CLAUDE_HOME/settings.local.json" ]; then
    local p expanded
    while IFS= read -r p; do
      expanded="${p/#\~/$HOME}"
      [ -d "$expanded" ] && PROJECT_TARGETS+=("$expanded")
    done < <(python3 -c "import json,sys; d=json.load(open('$CLAUDE_HOME/settings.local.json')); print('\n'.join(d.get('projectTargets',[])))" 2>/dev/null || true)
  fi
  # No fallback by design — see the header note. Nothing configured, nothing to do.
  if [ ${#PROJECT_TARGETS[@]} -eq 0 ]; then
    debug "skip project hook deployment: no projectTargets in $CLAUDE_HOME/settings.local.json"
    return 0
  fi

  if [[ ! -f "$HOOK_FRAGMENT" || ! -f "$HOOK_MERGER" ]]; then
    debug "skip project hook deployment: fragment or merger missing"
    return 0
  fi

  local project_root project_claude target_file output rc
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
}

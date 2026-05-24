#!/bin/bash
# omc_status.sh - One-shot ground-truth status check for all omc team workers
#
# Background:
#   The main agent has repeatedly misjudged worker state by reading only
#   one signal (pane capture or list-tasks alone). This script reads BOTH
#   sources of truth for each team and presents them side by side.
#
# What it reports per team:
#   - From omc team api list-tasks (filters out stderr lines): each task id,
#     status, subject, optional claim/lease info.
#   - From tmux capture-pane on the worker's pane: last 5 lines (to spot
#     errors, idle state, or thinking spinners).
#
# Usage:
#   omc_status.sh                                  # auto-detect all teams in cwd
#   omc_status.sh <team_state_dir> [<pane_id>]    # check a specific team
#
# Example:
#   cd /path/to/working
#   omc_status.sh                                  # scans .omc/state/team/* + w*_state/.omc/state/team/*
#   omc_status.sh ./w4_state 0:1.0                 # specific team in w4_state, pane 0:1.0
#
# Exit codes:
#   0 always (this is a read-only diagnostic; absence of teams reported as message)

set -uo pipefail
shopt -s nullglob

scan_team_dir() {
  local state_dir="$1"
  local pane_id="${2:-}"

  if [[ ! -d "$state_dir/.omc/state/team" ]]; then
    return
  fi

  for team_path in "$state_dir/.omc/state/team"/*/; do
    [[ -d "$team_path" ]] || continue
    local team_name="$(basename "$team_path")"
    echo "========================================"
    echo "TEAM: $team_name"
    echo "  state_dir: $state_dir"
    echo "  pane: ${pane_id:-(unknown)}"
    echo "----------------------------------------"

    # list-tasks with retry on empty response
    local input="{\"team_name\":\"$team_name\"}"
    local raw
    raw=$(cd "$state_dir" && omc team api list-tasks --input "$input" --json 2>&1 || true)
    local json_line
    json_line=$(echo "$raw" | grep '^{' | head -1)

    if [[ -z "$json_line" ]]; then
      echo "  TASKS: (no JSON response — retry)"
      sleep 1
      raw=$(cd "$state_dir" && omc team api list-tasks --input "$input" --json 2>&1 || true)
      json_line=$(echo "$raw" | grep '^{' | head -1)
    fi

    if [[ -n "$json_line" ]]; then
      python3 - "$json_line" <<'PYEOF'
import json, sys
try:
    d = json.loads(sys.argv[1])
    tasks = d.get("data", {}).get("tasks", [])
    if not tasks:
        print("  TASKS: (none — state may be wiped by orphan-cleanup)")
    else:
        for t in tasks:
            tid = t.get("id", "?")
            st = t.get("status", "?")
            sub = (t.get("subject", "") or "")[:60]
            ver = t.get("version", "?")
            claim = t.get("claim", None)
            line = f"  task #{tid}  [{st}]  v{ver}  {sub}"
            if claim and st == "in_progress":
                line += f"  (claimed until {claim.get('leased_until','')})"
            print(line)
except Exception as e:
    print(f"  TASKS: PARSE_ERROR {e}")
    print(f"    raw: {sys.argv[1][:200]}")
PYEOF
    else
      echo "  TASKS: (no JSON response after retry — omc CLI unreachable?)"
    fi

    # pane capture
    if [[ -n "$pane_id" ]]; then
      echo "  PANE last 5 lines:"
      tmux capture-pane -pt "$pane_id" -S -10 2>/dev/null | tail -5 | sed 's/^/    | /' || echo "    (capture failed)"
    fi
    echo ""
  done
}

if [[ $# -ge 1 ]]; then
  scan_team_dir "$1" "${2:-}"
  exit 0
fi

# Auto-detect mode
echo "=== omc_status.sh — autodetect teams under cwd: $(pwd) ==="
echo ""

# Look for .omc state in cwd
if [[ -d ".omc/state/team" ]]; then
  scan_team_dir "."
fi

# Look for w*_state/.omc/state/team
for sd in w*_state; do
  [[ -d "$sd/.omc/state/team" ]] && scan_team_dir "$sd"
done

# Optionally pair with tmux panes
echo "========================================"
echo "TMUX PANES (for cross-reference):"
tmux list-panes -a -F "  #{window_index}.#{pane_index}  cwd=#{pane_current_path}  title=[#{pane_title}]" 2>&1 | head -20

#!/bin/bash
# omc_monitor.sh - 3-signal monitor for omc team tasks
#
# Polls status + task version + tmux pane content hash to detect:
#   - normal completion (status=completed)
#   - failure (status=failed)
#   - stale freeze (in_progress with no version change AND no pane activity)
#
# Usage:
#   bash omc_monitor.sh <team_name> <task_id> <pane_id> [stale_threshold_sec] [cwd]
#
# Exit codes:
#   0 = task completed normally
#   1 = task transitioned to failed
#   2 = task stale (frozen N sec in in_progress)
#   3 = invalid args / setup error
#
# Notes:
#   - Logs every polling iteration to stdout for visibility.
#   - Stale counter only accumulates in 'in_progress' (pending/empty reset).
#   - Default threshold 300s (5min) — 180s false-positives on long-thinking workers.
#   - Avoid zsh read-only variable names ($status, $hash) in this script.
#   - Use shebang #!/bin/bash explicitly to bypass zsh eval quoting issues.

TEAM="${1:-}"
ID="${2:-}"
PANE="${3:-}"
STALE_THRESHOLD="${4:-300}"
CWD="${5:-$PWD}"

if [ -z "$TEAM" ] || [ -z "$ID" ] || [ -z "$PANE" ]; then
  echo "[ERR] usage: $0 <team> <id> <pane> [stale_sec] [cwd]"
  exit 3
fi

cd "$CWD" || { echo "[ERR] cd $CWD failed"; exit 3; }

echo "[INFO $(date +%H:%M:%S)] monitor start: team=$TEAM task=$ID pane=$PANE stale=${STALE_THRESHOLD}s cwd=$CWD"

prev_version=""
prev_hash=""
stale_count=0
iter=0

while true; do
  iter=$((iter + 1))
  resp=$(omc team api read-task --input "{\"team_name\":\"$TEAM\",\"task_id\":\"$ID\"}" --json 2>/dev/null)
  task_status=$(echo "$resp" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("data",{}).get("task",{}).get("status",""))' 2>/dev/null)
  version=$(echo "$resp" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("data",{}).get("task",{}).get("version",0))' 2>/dev/null)

  echo "[POLL $(date +%H:%M:%S) iter=$iter] status=$task_status version=$version stale=${stale_count}s"

  case "$task_status" in
    completed)
      echo "[ALERT-DONE] task=$ID completed at $(date +%H:%M:%S) (after $iter polls)"
      exit 0
      ;;
    failed)
      echo "[ALERT-FAIL] task=$ID failed at $(date +%H:%M:%S)"
      exit 1
      ;;
    pending)
      stale_count=0
      sleep 30
      continue
      ;;
    in_progress)
      # below stale check
      ;;
    *)
      # empty or unknown - api may be transient, reset and continue
      stale_count=0
      sleep 30
      continue
      ;;
  esac

  pane_hash=$(tmux capture-pane -pt "$PANE" -p 2>/dev/null | md5sum | cut -d' ' -f1)
  if [ "$version" = "$prev_version" ] && [ "$pane_hash" = "$prev_hash" ]; then
    stale_count=$((stale_count + 30))
    if [ $stale_count -ge $STALE_THRESHOLD ]; then
      echo "[ALERT-STALE] task=$ID frozen ${stale_count}s in in_progress — pane=$PANE need nudge at $(date +%H:%M:%S)"
      exit 2
    fi
  else
    stale_count=0
  fi
  prev_version="$version"
  prev_hash="$pane_hash"
  sleep 30
done

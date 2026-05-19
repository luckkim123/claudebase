#!/bin/bash
# omc_monitor.sh v2 - Multi-signal monitor for omc team tasks (or pane-direct workers).
#
# Detects:
#   ALERT-DONE       — task.status=completed (or deliverable file appeared)
#   ALERT-FAIL       — task.status=failed
#   ALERT-STALE      — in_progress with no version change AND no pane activity for STALE_SEC
#   ALERT-CONFIRM    — worker is waiting for main confirm (V3 dry-run pause)  ← NEW v2
#   ALERT-TYPED-NOOP — user typed into pane but didn't press Enter            ← NEW v2
#
# Usage:
#   bash omc_monitor.sh <team_name> <task_id> <pane_id> [stale_sec=300] [cwd=PWD] [deliverable_glob]
#
# If team_name="-" or task_id="-", skips omc API polling (pane-only mode for pane-direct workers).
# If deliverable_glob set, additionally exits ALERT-DONE when matching file appears.
#
# Exit codes:
#   0  ALERT-DONE
#   1  ALERT-FAIL
#   2  ALERT-STALE
#   3  invalid args
#   4  ALERT-CONFIRM (worker awaiting confirm)
#   5  ALERT-TYPED-NOOP (user typed but no Enter)
#
# Notes:
#   - Pane hash strips thinking-progress lines (Cogitated/Crunched/Embellishing/Precipitating/Brewed/Cooked/Churned)
#     so heartbeat counters don't reset stale detector (CLAUDE.md trap #4).
#   - Confirm-pending detection has TWO paths:
#       PRIMARY = explicit sentinel `<<AWAITING_MAIN_CONFIRM>>` / `<<WORKER_STOPPED>>` / `<<WORKER_BLOCKED>>`
#                 emitted by worker (deterministic — dispatcher must require this in task spec)
#       FALLBACK = natural-language heuristics ("STOP — awaiting", "Decisions needed", etc.)
#   - Polling interval 15s default (override via POLL_INTERVAL env var).
#     Reduced from 30s — confirm-pending detection should fire fast.
#   - Confirm/typed-noop alerts fire once and exit (re-arm by caller).

TEAM="${1:-}"
ID="${2:-}"
PANE="${3:-}"
STALE_THRESHOLD="${4:-300}"
CWD="${5:-$PWD}"
DELIVERABLE="${6:-}"

if [ -z "$PANE" ]; then
  echo "[ERR] usage: $0 <team|-> <task_id|-> <pane> [stale_sec] [cwd] [deliverable_path_or_glob]"
  exit 3
fi

cd "$CWD" || { echo "[ERR] cd $CWD failed"; exit 3; }

PANE_ONLY=0
if [ "$TEAM" = "-" ] || [ "$ID" = "-" ]; then
  PANE_ONLY=1
fi

# Record monitor start epoch — only files NEWER than this count as fresh deliverables
# (prevents false-DONE on pre-existing files like a clean cp before patches apply).
MONITOR_START_EPOCH=$(date +%s)

echo "[INFO $(date +%H:%M:%S)] monitor v2 start: team=$TEAM task=$ID pane=$PANE stale=${STALE_THRESHOLD}s cwd=$CWD pane_only=$PANE_ONLY deliverable=${DELIVERABLE:-none} start_epoch=$MONITOR_START_EPOCH"

prev_version=""
prev_hash=""
stale_count=0
iter=0

# ── Confirm-pending detection ─────────────────────────────────────────────────
# PRIMARY signal: explicit sentinel injected by dispatcher (deterministic, no false positives)
#   Worker is required to emit one of these tokens at confirm-pending state.
#   Dispatcher must inject "Output sentinel `<<AWAITING_MAIN_CONFIRM>>` when ..." in task spec.
SENTINEL_CONFIRM='<<AWAITING_MAIN_CONFIRM>>'
SENTINEL_STOP='<<WORKER_STOPPED>>'
SENTINEL_BLOCKED='<<WORKER_BLOCKED>>'
SENTINEL_PATTERN='<<AWAITING_MAIN_CONFIRM>>|<<WORKER_STOPPED>>|<<WORKER_BLOCKED>>'

# FALLBACK: natural-language heuristics (lower priority — best-effort for workers
# that don't emit sentinels yet). Case-insensitive grep -iE.
CONFIRM_PATTERNS='STOP[[:space:]]*[—–-][[:space:]]*[Aa]waiting|[Aa]waiting[[:space:]]+(main[[:space:]]+)?confirm|[Aa]waiting[[:space:]]+your|Decisions[[:space:]]+needed|STOPPING[[:space:]]*[—–-]|STOP\.[[:space:]]+Will[[:space:]]+not|Apply.*\?[[:space:]]*✅|proceed\?[[:space:]]*✅|✅[[:space:]]*/[[:space:]]*❌|please[[:space:]]+confirm|shall[[:space:]]+I[[:space:]]+proceed|proceed[[:space:]]+신호[[:space:]]+필요|확인[[:space:]]+(필요|요청)|승인[[:space:]]+(필요|대기)|G2[[:space:]]+진행[[:space:]]+전.*필요'

# Regex for thinking-heartbeat lines to strip from hash (CLAUDE.md trap #4)
THINKING_FILTER='Cogitated|Crunched|Embellishing|Precipitating|Brewed|Cooked|Churned|Synthesizing|Pondered'

# Detect "user typed at prompt but no Enter" — a "❯ <text>" line where <text> is non-trivial.
# Claude TUI separates the ❯ marker from typed text using a NO-BREAK SPACE (U+00A0, c2 a0),
# NOT an ASCII space, so we must use perl -CSD with a Unicode-aware class instead of
# grep's [[:space:]] (POSIX-locale → ASCII only).
detect_typed_noop() {
  local capture
  capture=$(tmux capture-pane -pt "$PANE" -p 2>/dev/null)
  # Strip ANSI escapes, drop blank lines, look at the last 8 non-empty lines,
  # then test for "❯<any whitespace>+<at least 3 non-whitespace chars>".
  echo "$capture" \
    | sed -E 's/\x1b\[[0-9;]*[A-Za-z]//g' \
    | grep -v '^[[:space:]]*$' \
    | tail -8 \
    | perl -CSD -ne 'exit 0 if /❯\s+\S{3,}/; END{exit 1}' && return 0
  return 1
}

while true; do
  iter=$((iter + 1))

  # ── Deliverable file check (mtime > monitor start) ──
  # Only counts files freshly modified AFTER monitor start, so a pre-existing
  # or cp-copied file from G1 doesn't fire ALERT-DONE prematurely.
  if [ -n "$DELIVERABLE" ]; then
    for f in $(compgen -G "$DELIVERABLE" 2>/dev/null); do
      f_mtime=$(stat -f %m "$f" 2>/dev/null || stat -c %Y "$f" 2>/dev/null)
      if [ -n "$f_mtime" ] && [ "$f_mtime" -gt "$MONITOR_START_EPOCH" ]; then
        echo "[ALERT-DONE] fresh deliverable matched at $(date +%H:%M:%S) iter=$iter: $f (mtime=$f_mtime > start=$MONITOR_START_EPOCH)"
        exit 0
      fi
    done
  fi

  # ── Team/task status check (skip in pane-only mode) ─
  if [ $PANE_ONLY -eq 0 ]; then
    resp=$(omc team api read-task --input "{\"team_name\":\"$TEAM\",\"task_id\":\"$ID\"}" --json 2>/dev/null)
    task_status=$(echo "$resp" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("data",{}).get("task",{}).get("status",""))' 2>/dev/null)
    version=$(echo "$resp" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("data",{}).get("task",{}).get("version",0))' 2>/dev/null)

    case "$task_status" in
      completed) echo "[ALERT-DONE] task=$ID completed at $(date +%H:%M:%S) iter=$iter"; exit 0 ;;
      failed)    echo "[ALERT-FAIL] task=$ID failed at $(date +%H:%M:%S) iter=$iter"; exit 1 ;;
      pending)   stale_count=0; sleep 30; continue ;;
      in_progress) ;;   # check pane below
      *) stale_count=0; sleep 30; continue ;;
    esac
  else
    task_status="(pane-only)"
    version="$iter"   # use iter as proxy so version always changes — pane hash is the real signal
  fi

  # ── Pane capture + hash (strip thinking heartbeats) ─
  pane_raw=$(tmux capture-pane -pt "$PANE" -p 2>/dev/null)
  pane_hash=$(echo "$pane_raw" | grep -vE "$THINKING_FILTER" | md5sum | cut -d' ' -f1)

  # ── Typed-no-Enter check (highest priority — actionable by Enter) ──
  if detect_typed_noop; then
    echo "[ALERT-TYPED-NOOP] task=$ID user typed at prompt but no Enter sent at $(date +%H:%M:%S) iter=$iter — pane=$PANE"
    exit 5
  fi

  # ── Confirm-pending pattern (V3 dry-run pause) ─────
  # Only look at the last ~30 lines of pane (recent state), not scrollback —
  # old G1 plan text persists in scrollback after user confirms, causing
  # false ALERT-CONFIRM. Recent activity always lives at the bottom.
  pane_tail=$(echo "$pane_raw" | tail -30)

  # PRIMARY: explicit sentinel from worker (deterministic, no false positive)
  if echo "$pane_tail" | grep -qE "$SENTINEL_PATTERN"; then
    matched=$(echo "$pane_tail" | grep -oE "$SENTINEL_PATTERN" | tail -1)
    echo "[ALERT-CONFIRM] task=$ID sentinel=$matched at $(date +%H:%M:%S) iter=$iter — pane=$PANE"
    exit 4
  fi

  # FALLBACK: natural-language heuristics
  if echo "$pane_tail" | grep -qiE "$CONFIRM_PATTERNS"; then
    echo "[ALERT-CONFIRM] task=$ID worker awaiting main confirm (heuristic) at $(date +%H:%M:%S) iter=$iter — pane=$PANE"
    exit 4
  fi

  echo "[POLL $(date +%H:%M:%S) iter=$iter] status=$task_status version=$version stale=${stale_count}s hash=${pane_hash:0:8}"

  # ── Stale detection ────────────────────────────────
  if [ "$version" = "$prev_version" ] && [ "$pane_hash" = "$prev_hash" ]; then
    stale_count=$((stale_count + 30))
    if [ $stale_count -ge $STALE_THRESHOLD ]; then
      echo "[ALERT-STALE] task=$ID frozen ${stale_count}s — pane=$PANE need nudge at $(date +%H:%M:%S)"
      exit 2
    fi
  else
    stale_count=0
  fi
  prev_version="$version"
  prev_hash="$pane_hash"
  sleep "${POLL_INTERVAL:-15}"
done

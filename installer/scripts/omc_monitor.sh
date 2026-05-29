#!/bin/bash
# omc_monitor.sh v3.4 - Multi-signal monitor for omc team tasks (or pane-direct workers).
#
# Dependencies: bash, tmux, python3, sed, awk, grep, perl (for detect_typed_noop with -CSD UTF-8 flag).
#
# v3.4 (2026-05-21, same session as v3.3): edge-triggered sentinel matching.
#   v3.3 still fired ALERT-CONFIRM on iter=2 when monitor restarted while
#   worker's plan output (containing the literal sentinel `[[CONFIRM_PENDING]]`
#   in the dry-run plan block) was still scrolled into tail-15 window — the
#   pane snapshot looked identical to "fresh sentinel" because the plan was
#   the most recent worker output.
#   Fix: track previous-iter sentinel md5 hash, only alert when current hash
#   differs (= position/content changed between cycles = fresh emission).
#   Stale tokens from past plan output produce stable hash → no alert.
#
# v3.3 (2026-05-21): two false-positive fixes from Raion Robotics interview prep
#   session — main session embedded "[[WORKER_STOPPED]]" literal inside its
#   confirm-OK message to worker (as a "build failure escape clause"), which
#   landed in the pane and was matched by sentinel grep on iter=1 immediately
#   after re-starting monitor. Also, scrollback drift: post-confirm sentinel
#   tokens persisted in scrollback longer than tail-30 expected.
#   Fixes:
#     - tail window 30 → 15 lines (sentinel emit always lands at very bottom)
#     - iter=1 skip sentinel/heuristic match (lets scrollback drift past first
#       window; only real fresh emission matches from iter=2 onward)
#   See claude/CLAUDE.md → "함정: Dispatcher self-leak — confirm 메시지 본문에
#   sentinel literal 박기" rule (added same session).
#
# v3.2 (2026-05-20): heuristic CONFIRM_PATTERNS tightened — Korean phrases
#   "확인 필요" / "결정 필요" / "의도 확인 필요" caused false-positives when
#   workers wrote them as descriptive prose in plan/analysis output
#   (e.g., "이 부분은 사용자 결정 필요"). Now only matches when accompanied
#   by explicit synchronization markers (✅/❌, "proceed", "STOP", emoji checkbox).
#   Also: MONITOR_NO_HEURISTIC=1 env var disables heuristic fallback entirely
#   for plan-writing workers where prose false-positives are the norm.
#
# v3.1 (2026-05-20): added square-bracket sentinels [[CONFIRM_PENDING]] / [[WORKER_STOPPED]] /
#   [[WORKER_BLOCKED]] to avoid angle-bracket self-leak in worker prose (W2 image generator
#   was emitting empty `<>` after seeing `<<AWAITING_MAIN_CONFIRM>>` in task description).
#   Both styles match (OR) for backward compat.
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

# ── Portable MD5 shim (H1: macOS ships `md5`, not `md5sum`) ──────────────────
# `md5sum` exists on Linux and macOS+coreutils; `md5` exists on stock macOS.
# Output format differs: md5sum prints "<hash>  <file>", md5 prints "MD5 (<file>) = <hash>".
# md5_hash() normalises both to just the hex digest string.
MD5_CMD=$(command -v md5sum 2>/dev/null || command -v md5 2>/dev/null || true)
if [ -z "$MD5_CMD" ]; then
  echo "[ERR] no md5sum or md5 available — cannot compute pane hash" >&2
  exit 3
fi
md5_hash() {
  if [[ "$MD5_CMD" == *md5sum* ]]; then
    "$MD5_CMD" | awk '{print $1}'       # md5sum: first field is hash
  else
    "$MD5_CMD" | awk '{print $NF}'      # macOS md5: last field is hash
  fi
}

# ── ANSI escape strip helper (M1: apply once before sentinel/heuristic grep) ──
# Claude TUI wraps output in colour escapes; strip them so sentinel literals
# (e.g. [[CONFIRM_PENDING]]) are not obscured by embedded \e[...m sequences.
strip_ansi() { sed -E 's/\x1b\[[0-9;]*[A-Za-z]//g'; }

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
#   Dispatcher must inject sentinel rule in task spec.
#
#   Two styles supported (both matched by SENTINEL_PATTERN):
#     - angle-bracket (legacy, v3.0):   <<AWAITING_MAIN_CONFIRM>>  <<WORKER_STOPPED>>  <<WORKER_BLOCKED>>
#     - square-bracket (preferred, v3.1+): [[CONFIRM_PENDING]]  [[WORKER_STOPPED]]  [[WORKER_BLOCKED]]
#   Square-bracket avoids the "empty <> leak" trap (workers seeing angle sentinel in task
#   description sometimes emit a degenerate `<>` in their own prose). See CLAUDE.md "Sentinel
#   self-leak — angle bracket self-confusion" subsection.
SENTINEL_CONFIRM='<<AWAITING_MAIN_CONFIRM>>'
SENTINEL_STOP='<<WORKER_STOPPED>>'
SENTINEL_BLOCKED='<<WORKER_BLOCKED>>'
SENTINEL_PATTERN='<<AWAITING_MAIN_CONFIRM>>|<<WORKER_STOPPED>>|<<WORKER_BLOCKED>>|\[\[CONFIRM_PENDING\]\]|\[\[WORKER_STOPPED\]\]|\[\[WORKER_BLOCKED\]\]'

# FALLBACK: natural-language heuristics (lower priority — best-effort for workers
# that don't emit sentinels yet). Case-insensitive grep -iE.
#
# v3.2 IMPORTANT: removed bare "확인 필요" / "결정 필요" / "G2 진행 전.*필요" — these
# Korean phrases appear in worker plan/analysis prose as descriptive labels (e.g.,
# "이 부분은 사용자 결정 필요") and caused false-positive ALERT-CONFIRM during plan
# writing. Only explicit synchronization markers retained: ✅/❌ pairs, explicit
# "STOP" patterns, "shall I proceed" / "please confirm" English imperatives.
# For plan-writing workers, set MONITOR_NO_HEURISTIC=1 to disable heuristic entirely.
CONFIRM_PATTERNS='STOP[[:space:]]*[—–-][[:space:]]*[Aa]waiting|[Aa]waiting[[:space:]]+(main[[:space:]]+)?confirm|Decisions[[:space:]]+needed|STOPPING[[:space:]]*[—–-]|STOP\.[[:space:]]+Will[[:space:]]+not|Apply.*\?[[:space:]]*✅|proceed\?[[:space:]]*✅|✅[[:space:]]*/[[:space:]]*❌|please[[:space:]]+confirm|shall[[:space:]]+I[[:space:]]+proceed'

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
    # OPT3: single python3 invocation (tab-separated) instead of 3 separate calls.
    IFS=$'\t' read -r task_status version < <(echo "$resp" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    t = d.get('data', {}).get('task', {})
    print(f\"{t.get('status','')}\t{t.get('version',0)}\")
except Exception:
    print('\t0')
" 2>/dev/null) || true

    case "$task_status" in
      completed) echo "[ALERT-DONE] task=$ID completed at $(date +%H:%M:%S) iter=$iter"; exit 0 ;;
      failed)    echo "[ALERT-FAIL] task=$ID failed at $(date +%H:%M:%S) iter=$iter"; exit 1 ;;
      pending)   stale_count=0; sleep "${POLL_INTERVAL:-15}"; continue ;;
      in_progress) ;;   # check pane below
      *) stale_count=0; sleep "${POLL_INTERVAL:-15}"; continue ;;
    esac
  else
    task_status="(pane-only)"
    version="$iter"   # use iter as proxy so version always changes — pane hash is the real signal
  fi

  # ── Pane capture + hash (strip thinking heartbeats) ─
  pane_raw=$(tmux capture-pane -pt "$PANE" -p 2>/dev/null)
  # M1: strip ANSI escapes once here; reuse pane_clean for both hash and sentinel grep.
  pane_clean=$(echo "$pane_raw" | strip_ansi)
  pane_hash=$(echo "$pane_clean" | grep -vE "$THINKING_FILTER" | md5_hash)

  # ── Typed-no-Enter check (highest priority — actionable by Enter) ──
  if detect_typed_noop; then
    echo "[ALERT-TYPED-NOOP] task=$ID user typed at prompt but no Enter sent at $(date +%H:%M:%S) iter=$iter — pane=$PANE"
    exit 5
  fi

  # ── Confirm-pending pattern (V3 dry-run pause) ─────
  # Only look at the last ~15 lines of pane (v3.3: tightened from 30) —
  # worker sentinel emit always lands at very bottom (tail 5 lines max);
  # tail 30 included scrollback drift that matched stale sentinel tokens
  # from past confirm messages (CLAUDE.md trap #5).
  #
  # v3.3: skip sentinel/heuristic matching on iter=1 — when monitor restarts
  # right after a confirm round-trip, the just-sent "[[WORKER_STOPPED]]" or
  # similar literal embedded in the user's confirm message body is still
  # in tail-15 window. Wait one poll cycle (15s) for drift, only match
  # fresh emissions from iter=2 onward.
  #
  # v3.4 (2026-05-21): edge-triggered matching — keep prev sentinel hash, only
  # alert when current sentinel match is DIFFERENT from previous (= fresh
  # emission). v3.3 still fired on iter=2 when worker plan body contained
  # the sentinel literal (e.g., worker echoed "[[CONFIRM_PENDING]]" in plan
  # output, but main session restarted monitor — iter=2 saw same stale
  # token and fired again). Edge-trigger fixes this: alert only when
  # sentinel position/content changes between polling cycles.
  # M1: use pane_clean (ANSI-stripped) for tail and all grep checks.
  pane_tail=$(echo "$pane_clean" | tail -15)
  sentinel_hash=$(echo "$pane_tail" | grep -oE "$SENTINEL_PATTERN" | md5_hash)

  if [ "$iter" -ge 2 ]; then
    # PRIMARY: explicit sentinel from worker (deterministic, no false positive)
    # Edge-triggered: only alert when sentinel hash differs from previous iter
    # (catches fresh emissions, ignores stale plan-body sentinels).
    if echo "$pane_tail" | grep -qE "$SENTINEL_PATTERN" && \
       [ "$sentinel_hash" != "$prev_sentinel_hash" ]; then
      matched=$(echo "$pane_tail" | grep -oE "$SENTINEL_PATTERN" | tail -1)
      echo "[ALERT-CONFIRM] task=$ID sentinel=$matched at $(date +%H:%M:%S) iter=$iter — pane=$PANE"
      exit 4
    fi

    # FALLBACK: natural-language heuristics (skipped when MONITOR_NO_HEURISTIC=1)
    # Disable when worker is writing plan/analysis prose where "결정 필요" style
    # phrases naturally occur (v3.2 trap — worker plan body false-positive).
    if [ "${MONITOR_NO_HEURISTIC:-0}" != "1" ]; then
      if echo "$pane_tail" | grep -qiE "$CONFIRM_PATTERNS"; then
        echo "[ALERT-CONFIRM] task=$ID worker awaiting main confirm (heuristic) at $(date +%H:%M:%S) iter=$iter — pane=$PANE"
        exit 4
      fi
    fi
  fi

  # Remember sentinel hash for next iter edge-detection
  prev_sentinel_hash="$sentinel_hash"

  echo "[POLL $(date +%H:%M:%S) iter=$iter] status=$task_status version=$version stale=${stale_count}s hash=${pane_hash:0:8}"

  # ── Stale detection ────────────────────────────────
  if [ "$version" = "$prev_version" ] && [ "$pane_hash" = "$prev_hash" ]; then
    stale_count=$((stale_count + ${POLL_INTERVAL:-15}))
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

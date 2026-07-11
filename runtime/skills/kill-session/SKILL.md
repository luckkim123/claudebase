---
name: kill-session
description: 'Use when the user wants to terminate AND remove the CURRENT background session it is invoked in — clearing it from the `claude agents` background-job list so it stops lingering as a stopped/done entry. Triggers on "/kill-session", "이 세션 삭제", "이 세션 종료하고 지워", "background session 삭제", "kill this session", "remove this background session", "이 백그라운드 세션 없애줘". Only ever touches the session it runs in (identified by $CLAUDE_JOB_DIR) — never other sessions. This is irreversible: the in-progress conversation ends where it stands and cannot be resumed.'
triggers:
  - "/kill-session"
  - "kill-session"
  - "이 세션 삭제"
  - "이 세션 종료하고 지워"
  - "이 세션 없애"
  - "이 백그라운드 세션 삭제"
  - "이 백그라운드 세션 없애"
  - "background session 삭제"
  - "kill this session"
  - "remove this background session"
  - "delete this session"
---

# kill-session

Terminate and delete the **current** background session — the one this skill is invoked in — so it disappears from the `claude agents` background-job list instead of lingering as a `stopped`/`done` entry.

## Scope guarantee (the whole point of this skill)

This skill acts on **exactly one** session: the one it runs in, identified by the `$CLAUDE_JOB_DIR` environment variable that Claude Code injects per session (e.g. `/root/.claude/jobs/5e51adfe`). It never enumerates, selects, or deletes any other session. If you ever find yourself computing a target from anything other than `$CLAUDE_JOB_DIR`, stop — that is a different task (bulk cleanup), not this skill.

## Why a plain `rm` is not enough

The background daemon owns a **respawn record**: each job dir holds a `state.json` with `respawnFlags`, and the daemon keeps a rendezvous socket at `/tmp/cc-daemon-*/*/rv/<id>.sock`. If you delete the job dir while the session process is still alive, the daemon can re-materialize the entry from that record. So the correct order is: **remove the respawn record first, then kill the owning process last.** The kill must be the final action because it ends this very session.

## Preconditions

- **Must be a background session.** If `$CLAUDE_JOB_DIR` is empty/unset, this is an interactive session, not a background job — do not run the deletion. Tell the user this command only works inside a background session and stop.
- **Confirm with the user first.** This is irreversible: the current conversation terminates where it stands and cannot be resumed. State that plainly and get a yes before proceeding (skip only if the user's invoking message already made the intent explicit, e.g. "종료하고 지워줘").

## Procedure

Run this as a single Bash call. It resolves its own pid from the authoritative `claude agents --json` mapping (job id → pid), removes the respawn record, then kills its own process tree last.

```bash
set -u
JOB_DIR="${CLAUDE_JOB_DIR:-}"
if [ -z "$JOB_DIR" ] || [ ! -d "$JOB_DIR" ]; then
  echo "Not a background session (\$CLAUDE_JOB_DIR unset or missing) — nothing to delete."
  exit 0
fi
ID="$(basename "$JOB_DIR")"

# 1. Resolve OUR pid from the daemon's own view (id -> pid). Authoritative.
PID="$(claude agents --json 2>/dev/null | python3 -c "
import json,sys
tgt='$ID'
try:
    for a in json.load(sys.stdin):
        if a.get('id')==tgt:
            print(a.get('pid') or ''); break
except Exception:
    pass
")"

# 2. Remove the respawn record FIRST so the daemon can't re-materialize us.
rm -rf "$JOB_DIR"
# Rendezvous socket (best-effort; ignore if the layout differs).
rm -f /tmp/cc-daemon-*/*/rv/"$ID".sock 2>/dev/null || true

echo "Removed background session $ID (job dir + rendezvous socket)."

# 3. Kill our own process LAST. This ends the session — nothing runs after it.
if [ -n "$PID" ]; then
  kill "$PID" 2>/dev/null || true
else
  # Fallback: no pid from the daemon view — terminate our own process group.
  kill -- -"$(ps -o pgid= -p $$ | tr -d ' ')" 2>/dev/null || true
fi
```

## After running

The Bash call ends the session mid-response, so there is no "after" to narrate — the kill is the last thing that happens. If for some reason the process survives (e.g. `kill` was blocked), report that the job dir was removed but the process is still alive, and the user should terminate it from the `claude agents` view.

## What this skill is NOT

- **Not bulk cleanup.** Deleting many stopped/done sessions is a separate manual task — enumerate `~/.claude/jobs/*/state.json`, keep only live ones (cross-check `claude agents --json` for `status: busy`/live pids), and `rm -rf` the rest. Do that directly, not through this skill.
- **Not for interactive sessions.** Those have no `$CLAUDE_JOB_DIR` and are managed by closing the terminal.

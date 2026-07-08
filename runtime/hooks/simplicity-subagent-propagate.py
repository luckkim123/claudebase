#!/usr/bin/env python3
"""Forward the session's temporary Simplicity-mode override into a starting subagent.

The other half of simplicity-mode-tracker.py. A subagent spawned via Task
re-reads CLAUDE.md on its own (per Claude Code's own subagent context setup),
so the *static* Simplicity First ladder already reaches it with no help from
this hook. What it does NOT get is this parent session's *SessionStart-time*
hook output — that additionalContext is parent-thread-only. A session-local
override written by simplicity-mode-tracker.py (e.g. "/simplicity ultra" typed
five turns ago) is exactly that kind of state, so without this hook a spawned
subagent would silently fall back to the CLAUDE.md default while the parent
thread is running in a different mode.

What it does (SubagentStart, matcher: "*"):
  - Reads {cwd, session_id} from stdin.
  - Looks up .omc/state/sessions/{session_id}/simplicity-mode.json.
  - No file (mode is "full", the default) -> no-op, exit 0, no output.
  - File present -> emit the level as one line of additionalContext, same
    wording simplicity-mode-tracker.py used when the mode was set, so the
    subagent sees an identical instruction to what the parent session got.

Fails open: any parse error or IO failure is swallowed and the hook exits 0
with no output.
"""
import json
import os
import sys

LEVEL_NOTE = {
    "lite": "Build what's asked; name the simpler alternative in one line, let the user pick.",
    "ultra": "YAGNI extremist for this session: challenge the requirement itself before building, deletion over addition, shortest possible diff.",
    "off": "Ladder suspended for this session — build the requested version without questioning scope.",
}


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0

    cwd = payload.get("cwd")
    session_id = payload.get("session_id")
    path = os.path.join(cwd or ".", ".omc", "state", "sessions", session_id or "unknown", "simplicity-mode.json")

    try:
        with open(path, "r", encoding="utf-8") as f:
            level = json.load(f).get("level")
    except Exception:
        return 0

    if level not in LEVEL_NOTE:
        return 0

    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SubagentStart",
            "additionalContext": f"SIMPLICITY MODE (inherited from parent session) — level: {level}. {LEVEL_NOTE[level]}",
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())

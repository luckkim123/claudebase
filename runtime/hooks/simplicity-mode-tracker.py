#!/usr/bin/env python3
"""Track a session-scoped intensity override for the CLAUDE.md Simplicity First ladder.

Background (adapted from an idea in DietrichGebert/ponytail, MIT — see
runtime/skills/simplicity-*/SKILL.md for the origin note; this hook is our own
implementation against our own state layout, not a port of ponytail's code):

  `~/.claude/CLAUDE.md` already defines the Simplicity First ladder as an
  always-on rule (loaded every session via the CLAUDE.md hierarchy — no hook
  needed for the static text). What that file CANNOT express is a *session-local,
  temporary* intensity change: "just for this task, be extreme about it (ultra)"
  or "just for this task, build the full version without questioning it (off)".
  That kind of state has to live outside CLAUDE.md (a file edit would leak into
  every future session) and has to be readable by subagents, which don't see
  this parent thread's hook-injected additionalContext (SessionStart's output is
  parent-thread-only; see simplicity-subagent-propagate.py for the other half).

  This hook is the write side: it watches UserPromptSubmit for a `/simplicity
  <level>` command and persists the level to a session-scoped state file. It
  does not itself change any behavior — persistent-mode text injection is out
  of scope here (CLAUDE.md's ladder is already always-on); this only exists so
  simplicity-subagent-propagate.py has something to read and forward.

What it does (UserPromptSubmit, matcher: "*"):
  - Reads {prompt, session_id} from stdin.
  - If the prompt is exactly `/simplicity [lite|full|ultra|off]` (whitespace-
    insensitive, case-insensitive), writes the level to
    .omc/state/sessions/{session_id}/simplicity-mode.json and emits a one-line
    confirmation via additionalContext.
  - `/simplicity` with no argument reports the current level instead of
    changing it.
  - Anything else: no-op, exit 0, no output — never touches unrelated prompts.

Fails open: any parse error or IO failure is swallowed and the hook exits 0
with no output, exactly like the sibling guards in this directory.
"""
import json
import os
import re
import sys

VALID_LEVELS = ("lite", "full", "ultra", "off")
COMMAND_RE = re.compile(r"^/simplicity(?:\s+(\w+))?\s*$", re.IGNORECASE)

LEVEL_NOTE = {
    "lite": "Build what's asked; name the simpler alternative in one line, let the user pick.",
    "full": "Default — the CLAUDE.md Simplicity First ladder applies as written.",
    "ultra": "YAGNI extremist for this session: challenge the requirement itself before building, deletion over addition, shortest possible diff.",
    "off": "Ladder suspended for this session — build the requested version without questioning scope.",
}


def _state_path(cwd: str, session_id: str) -> str:
    return os.path.join(cwd or ".", ".omc", "state", "sessions", session_id or "unknown", "simplicity-mode.json")


def _read_level(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f).get("level")
    except Exception:
        return None


def _write_level(path: str, level: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"level": level}, f)


def _emit(text: str) -> None:
    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": text,
        }
    }))


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0

    prompt = payload.get("prompt")
    if not isinstance(prompt, str):
        return 0

    m = COMMAND_RE.match(prompt.strip())
    if not m:
        return 0

    cwd = payload.get("cwd")
    session_id = payload.get("session_id")
    path = _state_path(cwd, session_id)

    arg = (m.group(1) or "").lower()
    if not arg:
        current = _read_level(path) or "full"
        _emit(f"SIMPLICITY MODE — current session level: {current}. {LEVEL_NOTE.get(current, '')}")
        return 0

    if arg not in VALID_LEVELS:
        _emit(f"SIMPLICITY MODE — unknown level '{arg}'. Use one of: {', '.join(VALID_LEVELS)}.")
        return 0

    try:
        if arg == "full":
            # "full" is the CLAUDE.md default — clearing the override file
            # keeps subagent propagation a no-op instead of forwarding a
            # redundant "full" line every time.
            try:
                os.remove(path)
            except FileNotFoundError:
                pass
        else:
            _write_level(path, arg)
    except Exception:
        pass

    _emit(f"SIMPLICITY MODE CHANGED — level: {arg} (this session only). {LEVEL_NOTE[arg]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

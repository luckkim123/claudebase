#!/usr/bin/env python3
"""Recover from an empty AskUserQuestion call by forcing an immediate retry.

Failure mode this hook addresses (diagnosed 2026-05-31 from transcript
9d4b2a74 — the SAME session that proved PreToolUse cannot catch this):

  The model emits `AskUserQuestion` with no `questions` array (tool_input is
  empty). The harness's BUILT-IN input-schema validator rejects it with
  `InputValidationError: 'questions' is missing` and the turn is wasted.

Why this is a Stop hook and NOT PreToolUse (verified, not assumed):
  A PreToolUse hook (askuserquestion-guard.py) was already registered for
  AskUserQuestion. A logging probe inserted into it on 2026-05-31 produced
  NO log entry when an empty call was made — proof that the harness's schema
  validator runs BEFORE PreToolUse and rejects the missing-`questions` call
  before any hook fires. PreToolUse is structurally too late for this case;
  the guard hook can only catch `questions: []` (empty array) and lone
  surrogates, which DO reach it. The only enforceable lever for a fully
  empty call is POST-HOC, exactly like detect_malformed_toolcall.py: after
  the turn, inspect what happened and block the Stop to force a retry.

How the empty call is observed (verified from transcript 9d4b2a74):
  The failure lands as a `tool_result` content block with `is_error: true`
  whose text contains the harness error
  `InputValidationError: AskUserQuestion failed ... 'questions' is missing`
  (line 836: is_error=True). It does NOT appear in the assistant text tail,
  so the detect_malformed approach (last_assistant_message) cannot see it.
  We therefore read `transcript_path` (an official Stop-hook stdin field per
  code.claude.com/docs/en/hooks) and scan the tail of the JSONL for that
  exact error.

GATE verification (reused from detect_malformed_toolcall.py, live v2.1.158):
  - `decision: "block"` + `reason` is fed back to the model next request
    (detect_malformed proved this works — its block reason changed model
    output). Official docs do not document the injection, but the sibling
    hook is live proof on this machine.
  - `stop_hook_active` is present at runtime (undocumented but used by
    detect_malformed); gating on it caps the loop at exactly one extra turn.

Discipline (mirrors detect_malformed_toolcall.py / askuserquestion-guard.py):
  - Never block on a hook bug: any exception / malformed stdin / unreadable
    transcript -> exit 0, allow the stop. A detector must not wedge a session.
  - Always exit 0; the decision travels in the JSON body, not the code.
  - Log every detection to .omc/logs/ for telemetry.

Hook event: Stop (no matcher)
Idempotent marker in the settings command field: ASKUSERQUESTION_RETRY_GUARD
"""
from __future__ import annotations

import json
import os
import sys

# The exact harness error text for a fully empty AskUserQuestion call. Both
# tokens must be present so we never trip on an unrelated validation error.
_ERR_TOOL = "AskUserQuestion"
_ERR_MISSING = "questions"
_ERR_PHRASE = "is missing"  # "The required parameter `questions` is missing"

REASON = (
    "Your last AskUserQuestion call was REJECTED by the harness: the "
    "`questions` array was missing (you emitted the call with an empty "
    "input). The turn was wasted. A PreToolUse hook cannot stop this — the "
    "schema validator runs first — so you must not let it happen again.\n"
    "Re-issue the call correctly NOW:\n"
    "1. Write the questions as prose in your reply body FIRST — each "
    "question text, its header (<=12 chars), its 2-4 options "
    "(label + description), and multiSelect true/false. The tokens must "
    "exist in your output before they can go in the tool call.\n"
    "2. Only after that prose exists, call AskUserQuestion with the SAME "
    "content in the `questions` array. Every question object needs all four "
    "fields: question, header, options (>=2), multiSelect.\n"
    "3. If there is an obvious recommended choice, do NOT call "
    "AskUserQuestion at all — state the recommendation in prose and proceed; "
    "the user can interrupt. AskUserQuestion is for genuine branch decisions."
)


def _tail_tool_results(transcript_path: str, max_lines: int = 40) -> list:
    """Return tool_result content-blocks from the last `max_lines` of the
    transcript JSONL, newest last. Best-effort; returns [] on any problem."""
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except (OSError, UnicodeDecodeError):
        return []
    results = []
    for line in lines[-max_lines:]:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        content = (obj.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                results.append(block)
    return results


def _result_text(block: dict) -> str:
    """Flatten a tool_result's content to a single string."""
    c = block.get("content", "")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return " ".join(
            part.get("text", "") for part in c if isinstance(part, dict)
        )
    return ""


def _is_empty_askuserquestion_error(block: dict) -> bool:
    """True iff this tool_result is the harness rejection of an empty
    AskUserQuestion call (missing `questions`)."""
    if not block.get("is_error"):
        return False
    text = _result_text(block)
    return _ERR_TOOL in text and _ERR_MISSING in text and _ERR_PHRASE in text


def _looks_like_empty_call(transcript_path: str) -> bool:
    """True iff the most recent tool_result in the transcript is an empty
    AskUserQuestion rejection. Anchored to the LAST tool_result so an older,
    already-recovered failure earlier in the session never re-triggers."""
    results = _tail_tool_results(transcript_path)
    if not results:
        return False
    return _is_empty_askuserquestion_error(results[-1])


def _log(cwd: str, record: dict) -> None:
    """Best-effort telemetry. Never raises."""
    try:
        log_dir = os.path.join(cwd or ".", ".omc", "logs")
        os.makedirs(log_dir, exist_ok=True)
        path = os.path.join(log_dir, "askuserquestion_retry.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _block(reason: str) -> int:
    sys.stdout.write(json.dumps({"decision": "block", "reason": reason}))
    return 0


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0  # never block on a hook bug

    if payload.get("hook_event_name") != "Stop":
        return 0

    transcript_path = payload.get("transcript_path")
    if not isinstance(transcript_path, str) or not transcript_path:
        return 0  # no transcript to inspect -> allow stop

    if not _looks_like_empty_call(transcript_path):
        return 0  # last tool_result is not an empty-call rejection -> allow

    cwd = payload.get("cwd") or os.getcwd()
    already_firing = payload.get("stop_hook_active") is True

    _log(
        cwd,
        {
            "session_id": payload.get("session_id"),
            "signal": "empty_askuserquestion",
            "stop_hook_active": already_firing,
            "blocked": not already_firing,
        },
    )

    # Loop guard: if this Stop is the re-fire after our own block, do NOT block
    # again — log only and let the session stop. Caps intervention at one turn.
    if already_firing:
        return 0

    return _block(REASON)


if __name__ == "__main__":
    sys.exit(main())

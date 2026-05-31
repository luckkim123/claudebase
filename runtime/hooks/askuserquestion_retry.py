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

Escalation strategy (revised 2026-05-31 after transcript evidence):
  A single retry was too weak. Real transcripts show the empty call recurring
  many times in one session (d6d2baa3: 38 rejections; 9895ae10: 34) because
  the old hook retried ONCE then let any further empty call pass. On a
  large-context Opus 4.8 session this is a known model-side emission failure
  (claude-code #64150) that one retry does not reliably escape. So we now
  count how many empty rejections sit CONSECUTIVELY at the transcript tail and
  escalate:
    streak 1-2 -> REASON_RETRY  (retry, but enforce prose-first discipline)
    streak 3+  -> REASON_ABANDON (stop calling the tool; state a prose
                  recommendation and proceed — the user can still interrupt)
  A successful retry breaks the streak (next Stop sees streak 0 -> allow), so
  the retry stage self-terminates; the abandon stage is capped at one block
  via `stop_hook_active` so a model that simply cannot emit the call never
  wedges the session.

GATE verification (reused from detect_malformed_toolcall.py, live v2.1.158):
  - `decision: "block"` + `reason` is fed back to the model next request
    (detect_malformed proved this works — its block reason changed model
    output). Official docs do not document the injection, but the sibling
    hook is live proof on this machine.
  - `stop_hook_active` is present at runtime (undocumented but used by
    detect_malformed); at the abandon stage it caps intervention at one turn.

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

# Streak 1-2: the call just failed (once or twice). Make it retry, but force
# the prose-first discipline that prevents the empty payload in the first place.
REASON_RETRY = (
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

# Streak 3+: retrying has not worked. On a large-context Opus session the
# empty-payload emission is a known model-side failure mode (claude-code
# issue #64150) that repeated retries do NOT reliably escape — one observed
# session looped 38 times. So STOP retrying the tool and route around it:
# state the recommendation in prose and proceed. The user keeps a real choice
# (they can interrupt) and the session is no longer wedged.
REASON_ABANDON = (
    "Your AskUserQuestion call has now failed with a missing `questions` "
    "array THREE OR MORE TIMES IN A ROW. Retrying the tool is not working — "
    "on a large-context session this is a known model-side emission failure "
    "(claude-code #64150) that more retries will not reliably escape. "
    "STOP calling AskUserQuestion for this decision.\n"
    "Instead, RIGHT NOW:\n"
    "1. In your normal reply text, write out the choice you were going to "
    "ask about, list the options in prose, and state which one you "
    "RECOMMEND and why.\n"
    "2. Proceed with that recommended option. Do NOT call AskUserQuestion "
    "again for this decision — the user can read your recommendation and "
    "interrupt if they want a different option.\n"
    "3. If the context has grown very large, consider telling the user they "
    "can run /compact to reduce the malformed-call rate going forward."
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


def _count_consecutive_empty_calls(transcript_path: str) -> int:
    """Count how many empty-AskUserQuestion rejections sit at the very tail of
    the transcript, CONSECUTIVELY, newest-first. A non-empty-call tool_result
    (any successful or unrelated tool) breaks the streak — that boundary is
    what distinguishes 'currently looping' from 'an older, already-recovered
    failure earlier in the session'.

    Returns:
      0  -> the last tool_result is NOT an empty-call rejection (allow stop)
      1  -> exactly one empty call at the tail (first failure)
      2  -> two in a row (the model already retried once and failed again)
      3+ -> runaway; we will force AskUserQuestion to be abandoned entirely
    """
    results = _tail_tool_results(transcript_path)
    if not results:
        return 0
    streak = 0
    for block in reversed(results):
        if _is_empty_askuserquestion_error(block):
            streak += 1
        else:
            break  # streak broken by a different/successful tool_result
    return streak


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

    streak = _count_consecutive_empty_calls(transcript_path)
    if streak == 0:
        return 0  # last tool_result is not an empty-call rejection -> allow

    cwd = payload.get("cwd") or os.getcwd()
    already_firing = payload.get("stop_hook_active") is True

    # Decide the intervention by how many empty calls are stacked at the tail.
    #   1-2 in a row  -> retry with prose-first discipline (REASON_RETRY)
    #   3+ in a row   -> stop retrying, force prose+recommend (REASON_ABANDON)
    if streak >= 3:
        reason, mode = REASON_ABANDON, "abandon"
    else:
        reason, mode = REASON_RETRY, "retry"

    # Loop guard: `stop_hook_active` is True only when THIS Stop is the re-fire
    # caused by our own previous block. If we already blocked once for the
    # current streak and the model STILL produced an empty call (streak grew),
    # blocking again on every re-fire would wedge the session in our own loop.
    # So: at the abandon stage, intervene at most once — if we are already
    # firing, let the stop through. The retry stage is naturally self-limiting
    # because a successful retry breaks the streak (-> streak 0 -> allow), and
    # a failed retry escalates the streak to 3+ -> the abandon branch.
    blocked = True
    if already_firing and mode == "abandon":
        blocked = False

    _log(
        cwd,
        {
            "session_id": payload.get("session_id"),
            "signal": "empty_askuserquestion",
            "streak": streak,
            "mode": mode,
            "stop_hook_active": already_firing,
            "blocked": blocked,
        },
    )

    if not blocked:
        return 0

    return _block(reason)


if __name__ == "__main__":
    sys.exit(main())

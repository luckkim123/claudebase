#!/usr/bin/env python3
"""Block empty AskUserQuestion tool calls and tell the model how to fix them.

Failure mode this hook addresses (diagnosed 2026-05-28 from transcript evidence):
the model emits `AskUserQuestion` with `tool_input == {}` — the required
`questions` array never makes it into the JSON. The harness rejects the call
with `InputValidationError: 'questions' is missing`, but by then a turn is
already wasted and the model has no structured guidance about what to do next.
Five empty calls were observed in a single session even after the user-scope
CLAUDE.md added a text-only "complete the payload before emitting" rule —
proof that prose self-instruction is not load-bearing here.

IMPORTANT — what this hook can and cannot catch (corrected 2026-05-31 after a
recurrence: an empty AskUserQuestion still produced a raw `InputValidationError`,
NOT this hook's friendly reason, proving the hook never ran for that call):

  PreToolUse hooks do NOT run before the harness's required-field schema check
  for *missing required fields*. When `questions` is absent entirely, the
  harness rejects the call with InputValidationError BEFORE this hook's stdin is
  populated — so the wholly-missing-`questions` case is structurally NOT
  hook-blockable. (The original claim here, "intercepts BEFORE the harness's own
  validator", was wrong; unit tests confirm the hook logic itself denies all
  empty shapes correctly, but it is simply never reached for that shape.)

  What this hook CAN still catch — cases where `tool_input` IS delivered to it:
    - `questions` present but an empty list `[]`
    - `questions` present but not a list (wrong type)
    - per-question objects missing their own required fields (question / header
      / options>=2) — a *partially* filled payload the harness may pass through
      to the hook before its deeper validation
    - lone UTF-16 surrogates anywhere in the input (deadlocks the next request)

So this hook is a *second* line of defense for malformed-but-delivered payloads,
not a guarantee against the bare missing-`questions` mistake. The load-bearing
fix for the latter is behavioral (the CLAUDE.md "complete the payload before
emitting" rule): fill the full `questions` array in the SAME message as the call,
never call-then-populate.

When it does run, it denies with `permissionDecision: "deny"` and returns a
precise self-correction message via `permissionDecisionReason` (which Claude Code
injects into the model's next request).

Hook event: PreToolUse (matcher = "AskUserQuestion")
Stdin schema: documented at https://code.claude.com/docs/en/hooks
  - tool_name: str
  - tool_input: dict  (the model's intended arguments)
  - transcript_path: str  (path to the session JSONL — used by the surrogate
    self-heal below)
Exit 0 with JSON on stdout = standard decision channel.

★★★ 2026-05-31 — lone-surrogate self-heal (why deny ALONE is not enough):
  A recurrence proved that denying a surrogate-bearing call does NOT stop the
  session from deadlocking. Sequence observed (transcript 9d4b2a74):
    1. The model emits AskUserQuestion whose options[*].description carries a
       lone UTF-16 surrogate. The assistant message — INCLUDING that poisoned
       tool_use block — is already recorded to the transcript before PreToolUse
       runs (PreToolUse gates execution, not recording).
    2. This hook denies with SURROGATE_REASON. Execution is blocked.
    3. But the harness re-serializes the WHOLE transcript for the next request,
       and the still-present poisoned block triggers an Anthropic API 400
       "no low surrogate in string" — the next turn cannot even start. Frozen.
  So there is a window: "poisoned block recorded" -> "next Stop-hook scrub".
  The deny does not close it. We close it HERE: on surrogate detection we also
  scrub the transcript in place immediately (reusing fix_surrogate's verified
  scrub), so the very next serialization is clean. Stop/SessionStart repair
  remain as the outer safety net; this is the inner, same-turn one.

Idempotent marker in the settings command field: ASKUSERQUESTION_GUARD
"""
import json
import os
import sys


REASON = (
    "Empty AskUserQuestion call rejected. Your tool_input was {} (or had no "
    "'questions' array). The harness would have rejected this with "
    "InputValidationError. Before you re-emit:\n"
    "1. Write the questions as prose in your reply body FIRST — list each "
    "question, its header (<=12 chars), its 2-4 options with label+description, "
    "and whether it's multiSelect. The tokens have to exist in your output "
    "before you can put them in the tool call.\n"
    "2. Only after the prose exists, call AskUserQuestion with the SAME "
    "content in the questions array. Each question object needs all four "
    "fields: question, header, options (>=2), multiSelect.\n"
    "3. If you don't actually need a structured prompt — e.g. there's an "
    "obvious recommended choice — DO NOT call AskUserQuestion. Just state "
    "the recommendation in prose and proceed. The user can interrupt if "
    "they disagree. Per ~/.claude/CLAUDE.md, AskUserQuestion is for genuine "
    "branch decisions, not for every confirmation."
)

PARTIAL_REASON = (
    "AskUserQuestion call has a 'questions' array but at least one question is "
    "incomplete. Every question object needs ALL of: 'question' (non-empty str), "
    "'header' (str <=12 chars), 'options' (list of >=2 objects, each with 'label' "
    "and 'description'), and 'multiSelect' (bool). The harness would reject the "
    "incomplete one with InputValidationError.\n"
    "Re-emit with each question fully populated — write the options as prose in "
    "your reply body first so the tokens exist, then put the SAME content in the "
    "call. Do not emit a question with fewer than 2 options."
)

SURROGATE_REASON = (
    "AskUserQuestion call contains a lone UTF-16 surrogate (U+D800-U+DFFF "
    "without its pair). Writing this to the transcript would deadlock the "
    "next API request with 'invalid high surrogate in string' (diagnosed "
    "2026-05-29 from transcript e8600e07 line 1405 — a U+D83A leaked into "
    "options[*].description and the Stop hook had to scrub it post-hoc).\n"
    "Re-emit the call WITHOUT lone surrogates: rewrite the affected field "
    "(usually question/description text) in BMP-only characters — plain "
    "Korean/English is safe, but avoid 4-byte CJK extensions and emoji "
    "prefixes that may have been truncated mid-pair during decoding."
)


def _deny(reason: str) -> int:
    sys.stdout.write(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    return 0


def _has_lone_surrogate(value) -> bool:
    """Recursively check any string inside value for unpaired UTF-16 surrogates."""
    if isinstance(value, str):
        return any(0xD800 <= ord(ch) <= 0xDFFF for ch in value)
    if isinstance(value, dict):
        return any(_has_lone_surrogate(v) for v in value.values())
    if isinstance(value, list):
        return any(_has_lone_surrogate(v) for v in value)
    return False


def _heal_transcript(transcript_path) -> None:
    """Best-effort: scrub lone surrogates from the transcript file NOW, so the
    poisoned tool_use block (already recorded before this PreToolUse hook ran)
    cannot deadlock the next request's serialization. Reuses the verified scrub
    in the sibling fix_surrogate.py. Never raises — a heal failure must not
    change the deny decision the caller is about to return.
    """
    if not isinstance(transcript_path, str) or not transcript_path:
        return
    if not os.path.exists(transcript_path):
        return
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        # Runtime sibling import (same hooks/ dir). Static analyzers can't resolve
        # it because the path is only added at call time — that's expected; the
        # resolved import is exercised by test_surrogate_heals_transcript_in_place.
        import fix_surrogate  # type: ignore[import-not-found]  # noqa: E402

        fix_surrogate.process_file(transcript_path, fix=True, backup=True)
    except Exception:
        # Outer Stop/SessionStart surrogate repair remains the safety net.
        pass


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        # Malformed stdin — never block on hook bug, defer to normal flow.
        return 0

    if payload.get("tool_name") != "AskUserQuestion":
        return 0  # matcher should prevent this, but be defensive

    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict) or not tool_input:
        return _deny(REASON)

    questions = tool_input.get("questions")
    # Direct early-return (not via an `is_empty` bool) so the type checker can
    # narrow `questions` to a non-empty list for the per-question loop below.
    if not isinstance(questions, list) or len(questions) == 0:
        return _deny(REASON)

    # Partial-fill check: questions[] exists but a question object is missing its
    # own required fields. This shape IS delivered to the hook (the top-level
    # required key is present), so unlike the bare missing-`questions` case we
    # can actually catch it here before the harness's deeper per-item validation.
    for q in questions:
        if not isinstance(q, dict):
            return _deny(PARTIAL_REASON)
        if not q.get("question") or not isinstance(q.get("question"), str):
            return _deny(PARTIAL_REASON)
        if not q.get("header") or not isinstance(q.get("header"), str):
            return _deny(PARTIAL_REASON)
        opts = q.get("options")
        if not isinstance(opts, list) or len(opts) < 2:
            return _deny(PARTIAL_REASON)
        for o in opts:
            if not isinstance(o, dict) or not o.get("label") or not o.get("description"):
                return _deny(PARTIAL_REASON)

    if _has_lone_surrogate(tool_input):
        # Deny is not enough on its own: the poisoned tool_use block is already
        # in the transcript. Scrub it in place NOW to close the deadlock window
        # before the next request serializes the conversation.
        _heal_transcript(payload.get("transcript_path"))
        return _deny(SURROGATE_REASON)

    # Valid-looking call: let normal permission flow handle it. We deliberately
    # do NOT validate per-question fields here; the harness's own validator
    # already does that and its error messages are precise.
    return 0


if __name__ == "__main__":
    sys.exit(main())

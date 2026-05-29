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

This hook intercepts the call BEFORE the harness's own validator, denies it
with `permissionDecision: "deny"`, and returns a precise self-correction
message via `permissionDecisionReason` (which Claude Code injects into the
model's next request). The model then has to re-emit the call with the
`questions` array actually populated.

Hook event: PreToolUse (matcher = "AskUserQuestion")
Stdin schema: documented at https://code.claude.com/docs/en/hooks
  - tool_name: str
  - tool_input: dict  (the model's intended arguments)
Exit 0 with JSON on stdout = standard decision channel.

Idempotent marker in the settings command field: ASKUSERQUESTION_GUARD
"""
import json
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


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        # Malformed stdin — never block on hook bug, defer to normal flow.
        return 0

    if payload.get("tool_name") != "AskUserQuestion":
        return 0  # matcher should prevent this, but be defensive

    tool_input = payload.get("tool_input") or {}
    questions = tool_input.get("questions")
    is_empty = (
        not isinstance(tool_input, dict)
        or not tool_input
        or not isinstance(questions, list)
        or len(questions) == 0
    )

    if not is_empty:
        # Valid-looking call: let normal permission flow handle it.
        # We deliberately do NOT validate per-question fields here; the
        # harness's own validator already does that and its error messages
        # are precise. We only catch the dominant {} failure mode.
        return 0

    sys.stdout.write(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": REASON,
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

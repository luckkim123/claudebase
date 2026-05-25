#!/usr/bin/env python3
"""Re-inject a short routing-verdict checkpoint on every UserPromptSubmit.

The full OMC routing rule is injected once at SessionStart (using-omc-emit.py),
but in long conversations that one-shot reminder gets forgotten -- the observed
failure mode is skipping the mandatory one-line routing verdict on multi-step
work, rationalized as "it's just ops". SessionStart cannot fix a mid-session
lapse because it fires once. This hook fires every turn, so the compliance
checkpoint stays in front of Claude right before it acts.

This is a checkpoint, not the rule body: keep it short (it is paid for on every
prompt) and behavioral (a trigger to act, not the catalog).
"""

import json
import sys


REMINDER = (
    "<routing-verdict-checkpoint>\n"
    "Before acting on THIS request: is it 3+ actions or multiple files? "
    "If yes, it is NOT trivial even if each step is simple -- announce the "
    "routing verdict in ONE line first ('-> <lane>: <reason>'), INCLUDING a "
    "'handle directly' verdict. Skipping this because 'it's just ops' is the "
    "exact lapse this checkpoint exists to stop. Trivial single-step work "
    "(typo, one-liner, pure question) proceeds silently.\n"
    "</routing-verdict-checkpoint>"
)


def main() -> int:
    # UserPromptSubmit: additionalContext is appended to the user's prompt.
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": REMINDER,
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

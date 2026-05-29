#!/usr/bin/env python3
"""Re-inject a short routing-verdict checkpoint on every UserPromptSubmit.

The full OMC routing rule is injected once at SessionStart (using-omc-emit.py),
but in long conversations that one-shot reminder gets forgotten -- the observed
failure mode is skipping the mandatory one-line routing verdict on multi-step
work, rationalized as "it's just ops". SessionStart cannot fix a mid-session
lapse because it fires once. This hook fires every turn, so the compliance
checkpoint stays in front of Claude right before it acts.

The checkpoint carries a compressed signal->skill index, not just "announce a
verdict". Reason: superpowers forces *skill invocation* via an
<EXTREMELY_IMPORTANT> system block, while OMC only asked Claude to *declare a
verdict* -- so even when an OMC skill's exact signal appeared (deep-interview,
ralph, ralplan), Claude declared a verdict but still fell to the superpowers /
handle-directly side, never naming the OMC candidate. Embedding the
signal->skill lines puts the correct mapping in front of Claude every turn so
OMC skills are actually considered, not just superpowers. The prose
discrimination criteria stay in the SessionStart router body (skills/using-omc);
this checkpoint is the per-turn reminder of *which skill is the candidate*.

Keep it ASCII-only (no -> arrows as multibyte chars, no unicode): a lone UTF-16
surrogate from a multibyte char in the transcript breaks /compact. Keep it
short -- it is paid for on every prompt.
"""

import json
import sys


REMINDER = (
    "<routing-verdict-checkpoint>\n"
    "Before acting on THIS request -- AND whenever you reach for ANY skill "
    "mid-task (the same way using-superpowers makes you check the skill list "
    "before acting, check THIS table first) -- is it 3+ actions or multiple "
    "files? If yes, it is NOT trivial even if each step is simple. Do this:\n"
    "1. Match the request to a signal below, then NAME the skill it maps to. "
    "superpowers (SP) and OMC are peers -- the signal decides, not which "
    "plugin shouts louder. Do NOT default to SP or to 'handle directly'.\n"
    "2. Announce the verdict in ONE line: '-> <skill or handle directly>: <reason>'.\n"
    "\n"
    "Signal -> skill (read the signal, not the name):\n"
    "- compare approaches / which design is better (NO direction chosen yet) -> brainstorming (SP)\n"
    "- target known, interrogate my hidden assumptions / pin down spec / clarify requirements -> deep-interview (OMC)\n"
    "  (tie-break: if brainstorming AND deep-interview both seem to fit, lean deep-interview;\n"
    "   keep brainstorming only when you genuinely have NO target yet)\n"
    "- write a concrete step-by-step TDD plan -> writing-plans (SP)\n"
    "- scope/strategize, lighter than full TDD plan -> plan (OMC)\n"
    "- high-stakes plan vetted from multiple perspectives -> ralplan (OMC)\n"
    "- have a plan, each task spec+quality reviewed as it lands -> subagent-driven-development (SP)\n"
    "- workers must coordinate on a shared task list -> team (OMC)\n"
    "- many independent edits, pure throughput, no verify loop -> ultrawork (OMC)\n"
    "- from a 2-3 line idea, run whole lifecycle hands-off -> autopilot (OMC)\n"
    "- writing a feature/bugfix where correctness matters -> test-driven-development (SP, RIGID)\n"
    "- keep going on its own until verified complete, persist across retries -> ralph (OMC)\n"
    "- about to fix a bug, find root cause first, don't guess -> systematic-debugging (SP, RIGID)\n"
    "- about to claim something done/fixed/passing -> verification-before-completion (SP, RIGID)\n"
    "\n"
    "Skipping the verdict because 'it's just ops' is the exact lapse this "
    "checkpoint stops. Trivial single-step work (typo, one-liner, pure "
    "question) proceeds silently.\n"
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

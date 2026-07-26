#!/usr/bin/env python3
"""Force session names into a fixed 3-word <verb>-<object>-<scope> shape.

Claude Code's built-in namer is *told* "2-4 words" but does not obey: of 24
real session names observed, 4 were 5 words and only 9 led with a verb. So
this hook does not ask. UserPromptSubmit delivers the already-generated name
in `session_title`; we rewrite it deterministically -- drop filler, hoist a
verb to the front, keep 3 words -- and hand it back via `sessionTitle`.

No model call: a headless generate measured 11.5s, and UserPromptSubmit
blocks the turn.

Emits nothing when there is no name yet (first turn, before the built-in
namer has run) or when the name is already in shape, which makes it
idempotent across turns.
"""

import json
import re
import sys

# ponytail: flat verb list, no POS tagging. Covers the verbs a coding-session
# title actually uses; a title with none just keeps its own word order.
# Swap for a real tagger only if misordering shows up in practice.
#
# Unambiguous verbs only. Words that read as nouns at least as often --
# build, design, document, merge, plan, port, run, split, test -- are left
# out on purpose: they sit early in a title and would be hoisted ahead of
# the real verb ("document-review-validation" would never reach "review").
# A miss just preserves the original order; a false hoist reorders wrongly.
VERBS = {
    "add", "analyze", "audit", "clarify", "clean", "cleanup", "compare",
    "consolidate", "debug", "diagnose", "evaluate", "extract", "fix",
    "generate", "harden", "implement", "improve", "integrate",
    "investigate", "launch", "migrate", "optimize", "organize", "refactor",
    "remove", "rename", "review", "setup", "update", "validate", "verify",
    "wire",
}

FILLER = {
    "a", "an", "and", "for", "from", "in", "into", "of", "on", "that",
    "the", "this", "to", "with",
}

WORDS = 3


def reshape(title: str) -> str | None:
    """Return the 3-word form of `title`, or None if nothing usable is left."""
    words = [w for w in re.split(r"[^A-Za-z0-9]+", title.lower()) if w]
    words = [w for w in words if w not in FILLER]
    if not words:
        return None
    for i, word in enumerate(words):
        if word in VERBS:
            words.insert(0, words.pop(i))
            break
    return "-".join(words[:WORDS])


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    title = (payload.get("session_title") or "").strip()
    if not title:
        return 0

    new = reshape(title)
    if not new or new == title:
        return 0

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "sessionTitle": new,
        }
    }))
    return 0


def selftest() -> int:
    cases = {
        # built-in sentence-case output -> kebab, verb first, 3 words
        "Fix the login button on mobile": "fix-login-button",
        "Update README with installation instructions": "update-readme-installation",
        "Improve performance of data processing script": "improve-performance-data",
        # verb buried mid-name gets hoisted
        "document-review-validation": "review-document-validation",
        "workspace-consolidation-review": "review-workspace-consolidation",
        # a noun that is also a verb must not outrank the real verb
        "plan-audit-rollout": "audit-plan-rollout",
        # no known verb: order preserved, still truncated to 3
        "alpha-beta-gamma-delta": "alpha-beta-gamma",
        # fewer than 3 words in, fewer than 3 words out -- nothing to invent
        "training-launch": "launch-training",
        # already in shape -> unchanged (idempotent across turns)
        "fix-login-button": "fix-login-button",
    }
    failed = 0
    for src, want in cases.items():
        got = reshape(src)
        if got != want:
            print(f"FAIL {src!r}: want {want!r}, got {got!r}")
            failed += 1
    assert reshape("the of and") is None, "all-filler title must yield None"
    print("selftest: FAILED" if failed else f"selftest: ok ({len(cases)} cases)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else main())

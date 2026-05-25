#!/usr/bin/env python3
"""Emit the using-omc routing skill as a Claude Code SessionStart hook envelope.

Reads skills/using-omc/SKILL.md (strips the YAML frontmatter), wraps it in an
OMC-scoped reminder, and prints a hookSpecificOutput JSON envelope so Claude Code
injects the routing rule into every session's SessionStart context.
"""

import json
import os
import sys


def main() -> int:
    # Prefer the deployed symlink; fall back to the repo path.
    candidates = [
        os.path.expanduser("~/.claude/skills/using-omc/SKILL.md"),
        os.path.expanduser("~/claude-settings/skills/using-omc/SKILL.md"),
    ]
    body = ""
    for path in candidates:
        if os.path.exists(path):
            with open(path) as f:
                lines = f.readlines()
            # Strip YAML frontmatter (--- ... --- at top).
            if lines and lines[0].strip() == "---":
                end = next(
                    (i for i in range(1, len(lines)) if lines[i].strip() == "---"), 0
                )
                lines = lines[end + 1:]
            body = "".join(lines).strip()
            break

    if body:
        ctx = (
            "<omc-routing-reminder>\n"
            "Before any multi-step request, run the OMC routing judgment below and "
            "announce the lane verdict in one line. (Complement to superpowers; the "
            "full OMC catalog auto-loads separately.)\n\n"
            + body
            + "\n</omc-routing-reminder>"
        )
    else:
        ctx = "using-omc skill not found — check claude-settings/skills/using-omc/SKILL.md"

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": ctx,
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

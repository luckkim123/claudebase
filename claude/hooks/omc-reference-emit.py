#!/usr/bin/env python3
"""Emit OMC reference catalog as Claude Code hook JSON.

Reads the latest cached omc-reference SKILL.md (stripping the 5-line
frontmatter) and prints a hookSpecificOutput JSON envelope so Claude Code
injects the catalog into the SessionStart system reminder.

Falls back to a doctor hint if no cached SKILL.md is found.
"""

import glob
import json
import os
import sys


def main() -> int:
    pattern = os.path.expanduser(
        "~/.claude/plugins/cache/omc/oh-my-claudecode/*/skills/omc-reference/SKILL.md"
    )
    paths = sorted(glob.glob(pattern))
    body = ""
    if paths:
        with open(paths[-1]) as f:
            body = "".join(f.readlines()[5:])

    if body:
        ctx = "## OMC Skill Catalog (auto-loaded)\n\n" + body
    else:
        ctx = "OMC reference not found — run /oh-my-claudecode:omc-doctor"

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": ctx,
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())

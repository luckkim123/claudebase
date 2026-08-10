#!/usr/bin/env python3
"""Suppress the graphify search nudge when the command targets another project.

`graphify hook-guard search` fires on two conditions only: the command contains a
search token (grep/find/rg/...) and graph.json exists relative to cwd. It never
looks at what the command is *searching* — cli.py's own docstring concedes that a
compound shell command has no single parseable target, so the read guard's
out-of-project check (#1840) has no search-side counterpart.

The result, measured in one session inside an Obsidian vault: six consecutive
"MANDATORY: run graphify query first" injections for greps whose targets were the
plugin cache, ~/claudebase, and the uv tool tree — none of them in the vault's
graph, which the nudge nonetheless claimed authority over.

Rule: if the command names absolute paths and every one of them resolves outside
the project root, this is not a question the project graph can answer. Suppress.
A command with no absolute path is assumed to target cwd (the common case) and
passes through untouched, so the guard keeps working where it is correct.

stdin: the Claude Code hook payload. exit 0 = pass through, 1 = suppress.
"""
import json
import os
import re
import sys
from pathlib import Path

# Redirects and tool locations, not search targets: `find . -name x > /dev/null`
# targets cwd despite naming an absolute path.
_SYSTEM_PREFIXES = ("/dev", "/tmp", "/usr", "/bin", "/sbin", "/etc", "/var",
                    "/proc", "/opt/homebrew", "/Library", "/System")

# A path token starts at /, ~/, or $HOME/ and runs until shell punctuation.
# The lookbehind keeps a relative path's own slash out of the match — without it
# `grep -rn foo 2_Resource/` yields a bare "/" and reads as out-of-project.
# `P=/Users/x/y; grep ... "$P/z"` still exposes the /Users/x/y literal.
_PATH_RE = re.compile(r"(?<![\w.\-/])(?:~|\$HOME|\$\{HOME\})?/[^\s\"'`;|&()<>,]+")


def _candidate_paths(cmd: str) -> list[Path]:
    """Absolute path literals in a shell command, minus system locations."""
    home = str(Path.home())
    out = []
    for tok in _PATH_RE.findall(cmd):
        if tok.startswith(("~", "$HOME", "${HOME}")):
            tok = home + tok[tok.index("/"):]
        elif not tok.startswith("/"):
            continue
        if tok.startswith(_SYSTEM_PREFIXES):
            continue
        # A glob makes the tail unresolvable; judge the literal prefix instead.
        for i, ch in enumerate(tok):
            if ch in "*?[":
                tok = tok[:i].rsplit("/", 1)[0] or "/"
                break
        out.append(Path(tok))
    return out


def in_scope(cmd: str, root: Path) -> bool:
    """True when the project graph could plausibly answer this command."""
    cands = _candidate_paths(cmd)
    if not cands:
        return True  # no absolute path -> relative -> anchored at cwd
    for p in cands:
        try:
            p.resolve().relative_to(root)
            return True
        except (ValueError, OSError, RuntimeError):
            continue
    return False


def main() -> int:
    try:
        d = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace"))
        cmd = str((d.get("tool_input") or d).get("command") or "")
    except Exception:
        return 0  # fail open: a filter bug must never silence a correct nudge
    if not cmd:
        return 0  # Grep tool (pattern, no command) -> leave to graphify
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    try:
        root = root.resolve()
    except (OSError, RuntimeError):
        return 0
    return 0 if in_scope(cmd, root) else 1


def _self_check() -> None:
    root = Path("/Users/kimseungmin/ksm_Obsidian").resolve()
    out = "/Users/kimseungmin/.claude/plugins/cache/oh-my-project/README.md"
    # The six real misfires from the session that motivated this filter.
    assert not in_scope(f"grep -n foo {out}", root)
    assert not in_scope(f'P=/Users/kimseungmin/.claude/plugins; grep -n x "$P/skills/a.md"', root)
    assert not in_scope('find "$HOME/.local/share/uv/tools" -name "*.py"', root)
    assert not in_scope("grep -rn graphify ~/claudebase/config/*.json", root)
    # Still nudges where the graph is authoritative.
    assert in_scope("grep -rn foo 2_Resource/", root)
    assert in_scope("grep -rn foo", root)
    assert in_scope(f"grep -rn foo {root}/0_Project", root)
    assert in_scope("find . -name x > /dev/null", root)  # system path is not a target
    # ponytail: a command mixing an out-of-project absolute path with an
    # in-project relative one is suppressed, because telling a relative path from
    # a flag or a pattern means parsing each tool's argv. The cost of being wrong
    # here is one missing nudge on a rare command shape; the cost of parsing argv
    # is a much larger false-positive surface. Revisit if such commands turn out
    # to be common.
    assert not in_scope(f"grep foo {out} 2_Resource/x.md", root)
    print("ok")


if __name__ == "__main__":
    sys.exit(_self_check() or 0 if "--self-check" in sys.argv else main())

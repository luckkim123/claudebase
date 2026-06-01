#!/usr/bin/env python3
"""CJK-aware unicode box renderer — like Claude Code's welcome box, the WIDTH
is computed in code so the right edge never drifts even with Korean text.

Usage:
  python3 box.py "Title" "line 1" "line 2" ...        # free title (Claude-authored category)
  python3 box.py --type analysis "line" ...           # one of the 5 defined types
  python3 box.py --type skill --label external-context "line"   # type + a subtitle
  python3 box.py --ascii "Title" "line"               # ASCII fallback

Box categories (design.md §8b, user decision 2026-06-01):
  5 DEFINED types get a standard label (no emoji — emoji width is unstable
  across terminals and breaks alignment): skill / analysis / plan / summary /
  warning. Anything that does not fit gets a FREE title that Claude authors on
  the spot (e.g. "검증 결과"). This mirrors GitHub alerts (fixed set) + Obsidian
  callouts (free fallback): standard where it repeats, flexible where it doesn't.

Why a tool and not inline drawing: a model counts characters, but the terminal
renders CJK glyphs at width 2 (East Asian Width W/F). Inline boxes drift on the
right edge. This tool measures width with unicodedata and pads correctly.
stdlib only — no wcwidth dependency.
"""
from __future__ import annotations

import sys
import unicodedata

# The 5 defined box types -> standard label (no emoji). Unknown type -> None,
# and the caller falls back to a free title.
_TYPE_LABELS = {
    "skill": "SKILL",
    "analysis": "분석",
    "plan": "계획",
    "summary": "요약",
    "warning": "주의",
}


def type_label(t: str) -> str | None:
    """Return the standard label for a defined type, else None."""
    return _TYPE_LABELS.get((t or "").strip().lower())


def visual_width(s: str) -> int:
    """Terminal column width: East Asian Wide/Fullwidth = 2, else 1."""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)


def render_box(title: str, lines: list[str], ascii_only: bool = False) -> str:
    if ascii_only:
        tl, tr, bl, br, h, v = "+", "+", "+", "+", "-", "|"
    else:
        tl, tr, bl, br, h, v = "╭", "╮", "╰", "╯", "─", "│"
    title = title or ""
    lines = lines or [""]
    inner = max([visual_width(title) + 4] + [visual_width(l) + 2 for l in lines])
    top = tl + h + " " + title + " " + h * (inner - visual_width(title) - 3) + tr
    out = [top]
    for l in lines:
        out.append(v + " " + l + " " * (inner - visual_width(l) - 2) + " " + v)
    out.append(bl + h * inner + br)
    return "\n".join(out)


def main(argv: list[str]) -> int:
    ascii_only = False
    box_type = None
    label = None
    args = list(argv)

    # Parse leading flags in any order: --ascii, --type <t>, --label <s>.
    while args and args[0].startswith("--"):
        flag = args[0]
        if flag == "--ascii":
            ascii_only = True
            args = args[1:]
        elif flag == "--type" and len(args) >= 2:
            box_type = args[1]
            args = args[2:]
        elif flag == "--label" and len(args) >= 2:
            label = args[1]
            args = args[2:]
        else:
            break  # unknown flag -> stop, treat rest as title+lines

    if not args and box_type is None:
        return 0  # no crash on empty

    # Title resolution: a defined --type yields its standard label, optionally
    # suffixed with a --label subtitle ("SKILL · external-context"). Otherwise
    # the first positional arg is a free, Claude-authored title.
    resolved = type_label(box_type) if box_type else None
    if resolved is not None:
        if label:
            title = resolved + " · " + label
        else:
            title = resolved
        lines = args
    else:
        title, lines = (args[0], args[1:]) if args else ("", [])

    sys.stdout.write(render_box(title, lines, ascii_only=ascii_only) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""CJK-aware unicode box renderer — like Claude Code's welcome box, the WIDTH
is computed in code so the right edge never drifts even with Korean text.

Usage: python3 box.py "Title" "line 1" "line 2" ...
       python3 box.py --ascii "Title" "line"   # ASCII fallback

Why a tool and not inline drawing: a model counts characters, but the terminal
renders CJK glyphs at width 2 (East Asian Width W/F). Inline boxes drift on the
right edge. This tool measures width with unicodedata and pads correctly.
stdlib only — no wcwidth dependency.
"""
from __future__ import annotations

import sys
import unicodedata


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
    args = list(argv)
    if args and args[0] == "--ascii":
        ascii_only = True
        args = args[1:]
    if not args:
        return 0  # no crash on empty
    title, lines = args[0], args[1:]
    sys.stdout.write(render_box(title, lines, ascii_only=ascii_only) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

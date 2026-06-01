#!/usr/bin/env python3
"""Shared opt-in gate for output-style hooks.

CLAUDEBASE_OUTPUT_STYLE: off (default/unset) | nudge | enforce.
Kill switches DISABLE_OMC / OMC_SKIP_HOOKS (mirrors config/CLAUDE.md) force off.

Both output-style hooks (inject + guard) read the mode through this single
function so their activation can never drift apart.
"""
from __future__ import annotations

_VALID = {"off", "nudge", "enforce"}


def style_mode(env: dict) -> str:
    if env.get("DISABLE_OMC"):
        return "off"
    skip = env.get("OMC_SKIP_HOOKS", "")
    if "output_style" in skip.split(","):
        return "off"
    raw = (env.get("CLAUDEBASE_OUTPUT_STYLE") or "off").strip().lower()
    return raw if raw in _VALID else "off"

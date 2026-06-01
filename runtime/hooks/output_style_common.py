#!/usr/bin/env python3
"""Shared opt-in gate for output-style hooks.

CLAUDEBASE_OUTPUT_STYLE: off (default/unset) | nudge | enforce.
Kill switches DISABLE_OMC / OMC_SKIP_HOOKS (mirrors config/CLAUDE.md) force off.

IMPORTANT — why this reads settings files, not just env:
  Claude Code does NOT inject settings.json/settings.local.json "env" entries
  into hook processes (verified against official docs: settings.json env is for
  Claude Code itself, not hooks). Hooks only inherit the PARENT SHELL's exported
  env. So this gate checks env FIRST (a real shell `export` wins), then falls
  back to reading `env.CLAUDEBASE_OUTPUT_STYLE` straight out of the settings
  files — so writing it in settings.local.json actually turns the feature on.

Both output-style hooks (inject + guard) read the mode through this single
function so their activation can never drift apart.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

_VALID = {"off", "nudge", "enforce"}

# Default settings files to consult, local first (per-machine) then common.
_DEFAULT_SETTINGS = [
    Path(os.path.expanduser("~/.claude/settings.local.json")),
    Path(os.path.expanduser("~/.claude/settings.json")),
]


def _normalize(raw) -> str:
    val = (raw or "").strip().lower() if isinstance(raw, str) else ""
    return val if val in _VALID else ""


def _mode_from_files(settings_paths) -> str:
    """Read env.CLAUDEBASE_OUTPUT_STYLE from the first settings file that has a
    valid value. Never raises — missing/malformed files are skipped."""
    for p in settings_paths:
        try:
            data = json.loads(Path(p).read_text(encoding="utf-8"))
        except Exception:
            continue
        val = _normalize((data.get("env") or {}).get("CLAUDEBASE_OUTPUT_STYLE"))
        if val:
            return val
    return ""


def style_mode(env: dict, settings_paths=None) -> str:
    # Kill switches override everything (mirrors config/CLAUDE.md).
    if env.get("DISABLE_OMC"):
        return "off"
    if "output_style" in env.get("OMC_SKIP_HOOKS", "").split(","):
        return "off"
    # 1. Shell-exported env wins if it names a valid mode.
    from_env = _normalize(env.get("CLAUDEBASE_OUTPUT_STYLE"))
    if from_env:
        return from_env
    # 2. Fall back to settings files (Claude Code does not inject settings env).
    paths = settings_paths if settings_paths is not None else _DEFAULT_SETTINGS
    return _mode_from_files(paths) or "off"

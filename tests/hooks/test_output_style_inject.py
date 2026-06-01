"""Tests for runtime/hooks/output_style_inject.py (UserPromptSubmit nudge)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / "runtime" / "hooks" / "output_style_inject.py"


def _run(stdin_obj: dict, env_extra: dict) -> dict:
    env = dict(os.environ)
    env.update(env_extra)
    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(stdin_obj),
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
    )
    assert proc.returncode == 0, f"must exit 0: {proc.stderr}"
    out = proc.stdout.strip()
    return json.loads(out) if out else {}


def test_off_injects_nothing():
    out = _run(
        {"hook_event_name": "UserPromptSubmit", "prompt": "hi"},
        {"CLAUDEBASE_OUTPUT_STYLE": "off"},
    )
    assert out == {}


def test_nudge_injects_baseline():
    out = _run(
        {"hook_event_name": "UserPromptSubmit", "prompt": "hi"},
        {"CLAUDEBASE_OUTPUT_STYLE": "nudge"},
    )
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "BLUF" in ctx or "결론" in ctx          # answer-first present
    assert "표" in ctx or "table" in ctx.lower()    # comparison->table present
    assert "box.py" in ctx                          # box tool guidance present


def test_enforce_also_injects():
    out = _run(
        {"hook_event_name": "UserPromptSubmit", "prompt": "hi"},
        {"CLAUDEBASE_OUTPUT_STYLE": "enforce"},
    )
    assert out.get("hookSpecificOutput", {}).get("additionalContext")


def test_injection_is_short():
    out = _run(
        {"hook_event_name": "UserPromptSubmit", "prompt": "hi"},
        {"CLAUDEBASE_OUTPUT_STYLE": "nudge"},
    )
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert ctx.count("\n") <= 14, "injection must stay short to avoid context bloat"


def test_ignores_non_userpromptsubmit_event():
    out = _run(
        {"hook_event_name": "Stop", "prompt": "hi"},
        {"CLAUDEBASE_OUTPUT_STYLE": "nudge"},
    )
    assert out == {}


def test_malformed_stdin_exits_clean():
    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input="not json {{{",
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""

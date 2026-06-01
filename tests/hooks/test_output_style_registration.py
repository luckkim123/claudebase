"""Verify both output-style hooks are registered in config/settings.json with markers."""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SETTINGS = REPO_ROOT / "config" / "settings.json"


def test_inject_hook_registered():
    d = json.loads(SETTINGS.read_text())
    cmds = [h["command"] for grp in d["hooks"].get("UserPromptSubmit", []) for h in grp["hooks"]]
    assert any("OUTPUT_STYLE_INJECT" in c and "output_style_inject.py" in c for c in cmds)


def test_guard_hook_registered():
    d = json.loads(SETTINGS.read_text())
    cmds = [h["command"] for grp in d["hooks"].get("Stop", []) for h in grp["hooks"]]
    assert any("OUTPUT_STYLE_GUARD" in c and "output_style_guard.py" in c for c in cmds)


def test_existing_stop_hooks_preserved():
    d = json.loads(SETTINGS.read_text())
    cmds = [h["command"] for grp in d["hooks"].get("Stop", []) for h in grp["hooks"]]
    # the three pre-existing Stop hooks must still be present
    assert any("SURROGATE_AUTO_REPAIR" in c for c in cmds)
    assert any("MALFORMED_TOOLCALL_GUARD" in c for c in cmds)
    assert any("ASKUSERQUESTION_RETRY_GUARD" in c for c in cmds)

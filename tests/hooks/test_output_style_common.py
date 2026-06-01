"""Tests for runtime/hooks/output_style_common.py — the shared opt-in gate."""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / "runtime" / "hooks" / "output_style_common.py"


def _load():
    spec = importlib.util.spec_from_file_location("output_style_common", HOOK_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_default_off_when_env_absent():
    m = _load()
    assert m.style_mode({}) == "off"


def test_explicit_modes():
    m = _load()
    assert m.style_mode({"CLAUDEBASE_OUTPUT_STYLE": "nudge"}) == "nudge"
    assert m.style_mode({"CLAUDEBASE_OUTPUT_STYLE": "enforce"}) == "enforce"


def test_unknown_value_is_off():
    m = _load()
    assert m.style_mode({"CLAUDEBASE_OUTPUT_STYLE": "garbage"}) == "off"


def test_kill_switch_forces_off():
    m = _load()
    assert m.style_mode({"CLAUDEBASE_OUTPUT_STYLE": "enforce", "DISABLE_OMC": "1"}) == "off"
    assert m.style_mode(
        {"CLAUDEBASE_OUTPUT_STYLE": "enforce", "OMC_SKIP_HOOKS": "output_style"}
    ) == "off"


def test_case_insensitive():
    m = _load()
    assert m.style_mode({"CLAUDEBASE_OUTPUT_STYLE": "ENFORCE"}) == "enforce"

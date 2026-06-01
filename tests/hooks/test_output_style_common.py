"""Tests for runtime/hooks/output_style_common.py — the shared opt-in gate."""
from __future__ import annotations

import importlib.util
import json
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
    # settings_paths=[] isolates from the real ~/.claude/*.json on this machine.
    assert m.style_mode({}, settings_paths=[]) == "off"


def test_explicit_modes():
    m = _load()
    assert m.style_mode({"CLAUDEBASE_OUTPUT_STYLE": "nudge"}) == "nudge"
    assert m.style_mode({"CLAUDEBASE_OUTPUT_STYLE": "enforce"}) == "enforce"


def test_unknown_value_is_off():
    m = _load()
    # garbage env value AND no file source -> off.
    assert m.style_mode({"CLAUDEBASE_OUTPUT_STYLE": "garbage"}, settings_paths=[]) == "off"


def test_kill_switch_forces_off():
    m = _load()
    assert m.style_mode({"CLAUDEBASE_OUTPUT_STYLE": "enforce", "DISABLE_OMC": "1"}) == "off"
    assert m.style_mode(
        {"CLAUDEBASE_OUTPUT_STYLE": "enforce", "OMC_SKIP_HOOKS": "output_style"}
    ) == "off"


def test_case_insensitive():
    m = _load()
    assert m.style_mode({"CLAUDEBASE_OUTPUT_STYLE": "ENFORCE"}) == "enforce"


# ---- settings-file fallback (Claude Code does NOT inject settings env into hooks) ----


def test_reads_mode_from_settings_file_when_env_absent(tmp_path):
    """env 에 값이 없으면 settings 파일의 env.CLAUDEBASE_OUTPUT_STYLE 을 읽는다."""
    m = _load()
    sf = tmp_path / "settings.local.json"
    sf.write_text(json.dumps({"env": {"CLAUDEBASE_OUTPUT_STYLE": "enforce"}}))
    assert m.style_mode({}, settings_paths=[sf]) == "enforce"


def test_env_takes_precedence_over_file(tmp_path):
    """shell export(env) 가 파일보다 우선."""
    m = _load()
    sf = tmp_path / "settings.local.json"
    sf.write_text(json.dumps({"env": {"CLAUDEBASE_OUTPUT_STYLE": "nudge"}}))
    assert m.style_mode({"CLAUDEBASE_OUTPUT_STYLE": "off"}, settings_paths=[sf]) == "off"
    # env 가 유효한 모드면 그걸 씀(파일 무시)
    assert m.style_mode({"CLAUDEBASE_OUTPUT_STYLE": "enforce"}, settings_paths=[sf]) == "enforce"


def test_first_settings_file_with_key_wins(tmp_path):
    """여러 파일이면 앞 파일(local)이 우선."""
    m = _load()
    local = tmp_path / "settings.local.json"
    common = tmp_path / "settings.json"
    local.write_text(json.dumps({"env": {"CLAUDEBASE_OUTPUT_STYLE": "enforce"}}))
    common.write_text(json.dumps({"env": {"CLAUDEBASE_OUTPUT_STYLE": "nudge"}}))
    assert m.style_mode({}, settings_paths=[local, common]) == "enforce"


def test_missing_or_malformed_settings_file_is_off(tmp_path):
    """파일 없음/깨진 JSON → off (절대 예외 던지지 않음)."""
    m = _load()
    missing = tmp_path / "nope.json"
    bad = tmp_path / "bad.json"
    bad.write_text("not json {{{")
    assert m.style_mode({}, settings_paths=[missing, bad]) == "off"


def test_kill_switch_still_forces_off_with_file(tmp_path):
    """kill switch 는 파일 설정도 무력화."""
    m = _load()
    sf = tmp_path / "settings.local.json"
    sf.write_text(json.dumps({"env": {"CLAUDEBASE_OUTPUT_STYLE": "enforce"}}))
    assert m.style_mode({"DISABLE_OMC": "1"}, settings_paths=[sf]) == "off"

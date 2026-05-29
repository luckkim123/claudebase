"""Tests for runtime/hooks/askuserquestion-guard.py.

The hook denies AskUserQuestion calls whose tool_input is empty or missing
a non-empty 'questions' list, and lets every other call pass through.
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / "runtime" / "hooks" / "askuserquestion-guard.py"


def _load_module():
    # File name contains a hyphen, so importlib over plain `import` is required.
    spec = importlib.util.spec_from_file_location("askuserquestion_guard", HOOK_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(payload: dict, capsys, monkeypatch) -> tuple[int, str]:
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    mod = _load_module()
    rc = mod.main()
    out, _ = capsys.readouterr()
    return rc, out


def test_empty_tool_input_denied(capsys, monkeypatch):
    rc, out = _run({"tool_name": "AskUserQuestion", "tool_input": {}}, capsys, monkeypatch)
    assert rc == 0
    decision = json.loads(out)["hookSpecificOutput"]
    assert decision["hookEventName"] == "PreToolUse"
    assert decision["permissionDecision"] == "deny"
    assert "Empty AskUserQuestion" in decision["permissionDecisionReason"]


def test_missing_questions_denied(capsys, monkeypatch):
    rc, out = _run(
        {"tool_name": "AskUserQuestion", "tool_input": {"foo": "bar"}}, capsys, monkeypatch
    )
    assert rc == 0
    assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_empty_questions_list_denied(capsys, monkeypatch):
    rc, out = _run(
        {"tool_name": "AskUserQuestion", "tool_input": {"questions": []}}, capsys, monkeypatch
    )
    assert rc == 0
    assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_valid_questions_pass(capsys, monkeypatch):
    rc, out = _run(
        {
            "tool_name": "AskUserQuestion",
            "tool_input": {
                "questions": [{"question": "Q?", "header": "H", "options": [], "multiSelect": False}]
            },
        },
        capsys,
        monkeypatch,
    )
    assert rc == 0
    assert out == ""  # silent pass


def test_other_tool_pass(capsys, monkeypatch):
    rc, out = _run({"tool_name": "Bash", "tool_input": {}}, capsys, monkeypatch)
    assert rc == 0
    assert out == ""


def test_malformed_stdin_no_block(capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
    mod = _load_module()
    assert mod.main() == 0

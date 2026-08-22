"""Tests for runtime/hooks/askuserquestion-guard.py.

The hook denies AskUserQuestion calls whose tool_input is empty or missing
a non-empty 'questions' list, and lets every other call pass through.
"""
from __future__ import annotations

import importlib.util
import io
import json
import tempfile
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
    # A payload without "cwd" hits the guard's `cwd or "."` fallback (same
    # class as C1) — pin the process cwd so that fallback lands in a scratch
    # dir, not the real repo's .omc/logs/askuserquestion_guard.jsonl.
    monkeypatch.chdir(tempfile.mkdtemp())
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
                "questions": [
                    {
                        "question": "Q?",
                        "header": "H",
                        "options": [
                            {"label": "A", "description": "first"},
                            {"label": "B", "description": "second"},
                        ],
                        "multiSelect": False,
                    }
                ]
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


def test_lone_surrogate_in_description_denied(capsys, monkeypatch):
    # Reproduces transcript e8600e07 line 1405: lone U+D83A in
    # questions[0].options[0].description deadlocks the next API request.
    rc, out = _run(
        {
            "tool_name": "AskUserQuestion",
            "tool_input": {
                "questions": [
                    {
                        "question": "Q?",
                        "header": "H",
                        "options": [
                            {"label": "L", "description": "더 \ud83a한 상태"},
                            {"label": "L2", "description": "ok"},
                        ],
                        "multiSelect": False,
                    }
                ]
            },
        },
        capsys,
        monkeypatch,
    )
    assert rc == 0
    decision = json.loads(out)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    assert "lone UTF-16 surrogate" in decision["permissionDecisionReason"]


def test_bmp_korean_passes(capsys, monkeypatch):
    # Plain Korean (BMP) must not be flagged.
    rc, out = _run(
        {
            "tool_name": "AskUserQuestion",
            "tool_input": {
                "questions": [
                    {
                        "question": "어떻게 진행할까요?",
                        "header": "방향",
                        "options": [
                            {"label": "A", "description": "추천대로"},
                            {"label": "B", "description": "다른 방향"},
                        ],
                        "multiSelect": False,
                    }
                ]
            },
        },
        capsys,
        monkeypatch,
    )
    assert rc == 0
    assert out == ""


# --- 2026-05-31 surrogate self-heal -----------------------------------------
# The guard, on surrogate detection, ALSO scrubs the transcript in place so the
# poisoned tool_use block (already recorded before PreToolUse ran) cannot
# deadlock the next request's serialization. These tests use the same
# monkeypatch/_run harness as the rest of the file (no subprocess).


def _poisoned_payload(transcript_path):
    p = {
        "tool_name": "AskUserQuestion",
        "tool_input": {
            "questions": [
                {
                    "question": "ok?",
                    "header": "h",
                    "options": [
                        {"label": "a", "description": "fine"},
                        {"label": "b", "description": "bad \ud83a here"},
                    ],
                    "multiSelect": False,
                }
            ]
        },
    }
    if transcript_path is not None:
        p["transcript_path"] = transcript_path
    return p


def test_surrogate_heals_transcript_in_place(tmp_path, capsys, monkeypatch):
    """On surrogate detection the guard both denies AND scrubs the transcript
    file, so a lone surrogate already recorded there is gone afterwards."""
    # A transcript line whose recorded assistant tool_use carries a lone
    # surrogate (escaped as \uXXXX so the file on disk is valid JSON text).
    poisoned_line = json.dumps(
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "name": "AskUserQuestion",
             "input": {"questions": [{"options": [{"description": "x \ud83a y"}]}]}}
        ]}},
        ensure_ascii=True,
    )
    tp = tmp_path / "session.jsonl"
    tp.write_text(poisoned_line + "\n", encoding="utf-8")

    # sanity: the file genuinely cannot be strict-UTF-8 encoded as-is
    obj = json.loads(tp.read_text(encoding="utf-8"))
    try:
        json.dumps(obj, ensure_ascii=False).encode("utf-8")
        assert False, "fixture should contain a lone surrogate"
    except UnicodeEncodeError:
        pass

    rc, out = _run(_poisoned_payload(str(tp)), capsys, monkeypatch)
    assert rc == 0
    decision = json.loads(out)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    assert "lone UTF-16 surrogate" in decision["permissionDecisionReason"]

    # After the heal, the transcript must be strict-UTF-8 encodable.
    healed = json.loads(tp.read_text(encoding="utf-8"))
    json.dumps(healed, ensure_ascii=False).encode("utf-8")  # must not raise


def test_surrogate_deny_without_transcript_path(capsys, monkeypatch):
    """No transcript_path -> still denies, heal is a no-op (never raises)."""
    rc, out = _run(_poisoned_payload(None), capsys, monkeypatch)
    assert rc == 0
    assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_surrogate_heal_missing_file_is_noop(capsys, monkeypatch):
    """Nonexistent transcript_path -> deny, heal no-ops, no crash."""
    rc, out = _run(_poisoned_payload("/nonexistent/path/session.jsonl"), capsys, monkeypatch)
    assert rc == 0
    assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"


# ---- [3] every deny is logged so the Stop hook can count cross-shape -------


def test_deny_writes_log(tmp_path, capsys, monkeypatch):
    """A deny (here: empty input) must append a telemetry record to
    .omc/logs/askuserquestion_guard.jsonl so the Stop hook can fold guard denies
    (empty-array / partial / surrogate) together with its own missing-`questions`
    rejections into one per-session failure count."""
    rc, out = _run(
        {"tool_name": "AskUserQuestion", "tool_input": {},
         "cwd": str(tmp_path), "session_id": "guard-sess"},
        capsys, monkeypatch,
    )
    assert rc == 0
    assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"
    log = tmp_path / ".omc" / "logs" / "askuserquestion_guard.jsonl"
    assert log.exists(), "a deny must be logged for cross-shape counting"
    rec = json.loads(log.read_text().strip())
    assert rec["signal"] == "denied_askuserquestion"
    assert rec["session_id"] == "guard-sess"


def test_valid_call_writes_no_log(tmp_path, capsys, monkeypatch):
    """A passing call must NOT log — only denies are failures."""
    rc, out = _run(
        {
            "tool_name": "AskUserQuestion",
            "cwd": str(tmp_path),
            "session_id": "ok-sess",
            "tool_input": {"questions": [
                {"question": "Q?", "header": "H",
                 "options": [{"label": "A", "description": "x"},
                             {"label": "B", "description": "y"}],
                 "multiSelect": False}]},
        },
        capsys, monkeypatch,
    )
    assert rc == 0
    assert out.strip() == "", "a valid call produces no decision output"
    _ = capsys  # output already captured via the _run helper
    log = tmp_path / ".omc" / "logs" / "askuserquestion_guard.jsonl"
    assert not log.exists(), "a passing call must not be logged as a failure"

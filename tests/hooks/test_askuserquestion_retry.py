"""Tests for runtime/hooks/askuserquestion_retry.py (empty-call Stop hook).

Drives the hook end-to-end via subprocess (real stdin->stdout JSON contract)
and builds throwaway transcript JSONL files matching the EXACT shape observed
in transcript 9d4b2a74 (line 836): a tool_result block with is_error=True
whose text carries `InputValidationError: AskUserQuestion ... 'questions' is
missing`. The empty call lands in a tool_result, NOT the assistant text tail,
which is why this hook reads transcript_path instead of last_assistant_message.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / "runtime" / "hooks" / "askuserquestion_retry.py"

# The exact harness rejection text for an empty AskUserQuestion call.
EMPTY_ERR = (
    "<tool_use_error>InputValidationError: AskUserQuestion failed due to the "
    "following issue:\nThe required parameter `questions` is missing"
    "</tool_use_error>"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("askuserquestion_retry", HOOK_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_transcript(tmp_path: Path, blocks_tail, name="transcript.jsonl") -> str:
    """Write a minimal JSONL transcript whose LAST user line carries the given
    tool_result blocks. Returns the path."""
    lines = [
        json.dumps({"type": "assistant", "message": {"role": "assistant",
                    "content": [{"type": "text", "text": "ok"}]}}),
        json.dumps({"type": "assistant", "message": {"role": "assistant",
                    "content": [{"type": "tool_use", "name": "AskUserQuestion",
                                 "input": {}}]}}),
        json.dumps({"type": "user", "message": {"role": "user",
                    "content": blocks_tail}}),
    ]
    p = tmp_path / name
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(p)


def _err_result_block(text=EMPTY_ERR):
    return {"type": "tool_result", "is_error": True,
            "content": [{"type": "text", "text": text}]}


def _ok_result_block():
    return {"type": "tool_result", "is_error": False,
            "content": [{"type": "text", "text": "user answered: option A"}]}


def _run_hook(stdin_obj: dict) -> dict:
    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(stdin_obj),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0, f"hook must always exit 0, got {proc.returncode}: {proc.stderr}"
    out = proc.stdout.strip()
    return json.loads(out) if out else {}


# ---- unit level: the pure detector ----------------------------------------


def test_detects_empty_error_block():
    m = _load_module()
    assert m._is_empty_askuserquestion_error(_err_result_block()) is True


def test_non_error_block_is_not_a_match():
    m = _load_module()
    # same text but is_error False -> not a rejection
    blk = {"type": "tool_result", "is_error": False,
           "content": [{"type": "text", "text": EMPTY_ERR}]}
    assert m._is_empty_askuserquestion_error(blk) is False


def test_unrelated_error_is_not_a_match():
    m = _load_module()
    other = _err_result_block("<tool_use_error>InputValidationError: Edit failed: "
                              "old_string not found</tool_use_error>")
    assert m._is_empty_askuserquestion_error(other) is False


def test_string_content_form_is_flattened():
    m = _load_module()
    # some transcripts store content as a bare string, not a list
    blk = {"type": "tool_result", "is_error": True, "content": EMPTY_ERR}
    assert m._is_empty_askuserquestion_error(blk) is True


# ---- contract level: full stdin -> stdout JSON ----------------------------


def test_hook_blocks_on_empty_call(tmp_path):
    tpath = _write_transcript(tmp_path, [_err_result_block()])
    out = _run_hook({
        "hook_event_name": "Stop",
        "stop_hook_active": False,
        "transcript_path": tpath,
        "cwd": str(tmp_path),
        "session_id": "test-sess",
    })
    assert out.get("decision") == "block"
    assert "questions" in out.get("reason", "").lower()


def test_hook_allows_when_last_result_is_clean(tmp_path):
    # a successful AskUserQuestion (user answered) must not be blocked
    tpath = _write_transcript(tmp_path, [_ok_result_block()])
    out = _run_hook({
        "hook_event_name": "Stop",
        "stop_hook_active": False,
        "transcript_path": tpath,
        "cwd": str(tmp_path),
    })
    assert out == {}


def test_hook_anchors_to_last_result_only(tmp_path):
    # an empty-call failure followed by a later successful result must NOT
    # re-trigger — only the most recent tool_result matters
    tpath = _write_transcript(tmp_path, [_err_result_block(), _ok_result_block()])
    out = _run_hook({
        "hook_event_name": "Stop",
        "stop_hook_active": False,
        "transcript_path": tpath,
        "cwd": str(tmp_path),
    })
    assert out == {}, "a recovered earlier failure must not re-block"


def test_hook_dedupes_on_refire(tmp_path):
    tpath = _write_transcript(tmp_path, [_err_result_block()])
    out = _run_hook({
        "hook_event_name": "Stop",
        "stop_hook_active": True,  # our own block re-fired the Stop
        "transcript_path": tpath,
        "cwd": str(tmp_path),
    })
    assert out == {}, "must not block twice for the same empty call (loop guard)"


def test_hook_ignores_non_stop_event(tmp_path):
    tpath = _write_transcript(tmp_path, [_err_result_block()])
    out = _run_hook({
        "hook_event_name": "SubagentStop",
        "stop_hook_active": False,
        "transcript_path": tpath,
    })
    assert out == {}


def test_hook_allows_when_no_transcript_path():
    out = _run_hook({
        "hook_event_name": "Stop",
        "stop_hook_active": False,
    })
    assert out == {}


def test_hook_never_blocks_on_malformed_stdin():
    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input="this is not json {{{",
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_hook_allows_on_unreadable_transcript(tmp_path):
    out = _run_hook({
        "hook_event_name": "Stop",
        "stop_hook_active": False,
        "transcript_path": str(tmp_path / "does_not_exist.jsonl"),
        "cwd": str(tmp_path),
    })
    assert out == {}, "unreadable transcript must not wedge the session"


def test_hook_writes_log_on_detection(tmp_path):
    tpath = _write_transcript(tmp_path, [_err_result_block()])
    out = _run_hook({
        "hook_event_name": "Stop",
        "stop_hook_active": False,
        "transcript_path": tpath,
        "cwd": str(tmp_path),
        "session_id": "log-sess",
    })
    assert out.get("decision") == "block"
    log = tmp_path / ".omc" / "logs" / "askuserquestion_retry.jsonl"
    assert log.exists(), "detection must be logged for telemetry"
    rec = json.loads(log.read_text().strip())
    assert rec["signal"] == "empty_askuserquestion"
    assert rec["blocked"] is True

"""Tests for runtime/hooks/detect_malformed_toolcall.py (mode-A Stop hook).

Exercises the leak detector against the EXACT tail shape observed in the
2026-05-30 transcript (14/14 leaks ended in `</parameter>\\n</invoke>`) plus
the live Stop-hook stdin schema verified on Claude Code v2.1.158
(last_assistant_message, stop_hook_active).

The hook is driven end-to-end via subprocess so we test the real stdin->stdout
JSON contract, not just internal functions. We never write literal closing
tool-call tags in this file's top level either — they are assembled from
pieces, mirroring the hook itself, so the test source can't read as a leak.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / "runtime" / "hooks" / "detect_malformed_toolcall.py"

# Assemble markup pieces (never a literal closing tag in source).
_LT = "<"
_GT = ">"
CLOSE_PARAM = _LT + "/parameter" + _GT
CLOSE_INVOKE_BARE = _LT + "/invoke" + _GT
CLOSE_INVOKE_NS = _LT + "/" + "antml:invoke" + _GT
OPEN_PARAM = _LT + "parameter name=" + '"description"' + _GT


def _load_module():
    spec = importlib.util.spec_from_file_location("detect_malformed_toolcall", HOOK_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_hook(stdin_obj: dict) -> dict:
    """Invoke the hook as a subprocess; return parsed stdout JSON ({} if empty)."""
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


def test_clean_text_is_not_a_leak():
    m = _load_module()
    assert m._looks_like_leak("Just a normal answer with no markup.") is None
    assert m._looks_like_leak("") is None
    assert m._looks_like_leak("I used `gemini -p` and it worked.") is None


def test_real_leak_tail_detected():
    m = _load_module()
    # The exact 14/14 observed shape: prose + </parameter>\n</invoke>
    leaked = "...adds 30+ seconds of worker setup and a tmux pane." + CLOSE_PARAM + "\n" + CLOSE_INVOKE_BARE
    assert m._looks_like_leak(leaked) == "param_invoke_tail"


def test_namespaced_invoke_tail_detected():
    m = _load_module()
    leaked = "some payload text" + CLOSE_PARAM + "\n" + CLOSE_INVOKE_NS
    assert m._looks_like_leak(leaked) == "param_invoke_tail"


def test_bare_invoke_tail_without_param_detected():
    m = _load_module()
    # a no-arg tool call leak: ends in just the closing invoke
    leaked = "calling a tool now" + CLOSE_INVOKE_BARE
    assert m._looks_like_leak(leaked) == "bare_invoke_tail"


def test_false_positive_quoting_midtext_is_safe():
    m = _load_module()
    # Documentation that QUOTES the closing tag but continues afterwards must
    # NOT be flagged — the tag is not the tail. This is exactly what this
    # analysis/handoff does.
    doc = (
        "The leak signature is " + CLOSE_PARAM + " followed by " + CLOSE_INVOKE_BARE
        + ", and the hook anchors on the tail so this sentence is safe."
    )
    assert m._looks_like_leak(doc) is None


# ---- contract level: full stdin -> stdout JSON ----------------------------


def _leaked_msg() -> str:
    return "explanation text ..." + CLOSE_PARAM + "\n" + CLOSE_INVOKE_BARE


def test_hook_blocks_on_first_leak():
    out = _run_hook(
        {
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": _leaked_msg(),
            "cwd": "/tmp/nonexistent_test_cwd_detect",
            "session_id": "test-sess",
        }
    )
    assert out.get("decision") == "block"
    assert "native" in out.get("reason", "").lower()


def test_hook_does_not_block_when_clean():
    out = _run_hook(
        {
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": "All done, the file was written.",
            "cwd": "/tmp/nonexistent_test_cwd_detect",
        }
    )
    assert out == {}  # no decision -> stop allowed


def test_hook_dedupes_on_refire():
    # When stop_hook_active is True (our own block re-fired the Stop), we must
    # NOT block again — caps the loop at one extra turn.
    out = _run_hook(
        {
            "hook_event_name": "Stop",
            "stop_hook_active": True,
            "last_assistant_message": _leaked_msg(),
            "cwd": "/tmp/nonexistent_test_cwd_detect",
        }
    )
    assert out == {}, "must not block twice for the same leak (infinite-loop guard)"


def test_hook_ignores_non_stop_event():
    out = _run_hook(
        {
            "hook_event_name": "SubagentStop",
            "stop_hook_active": False,
            "last_assistant_message": _leaked_msg(),
        }
    )
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
    assert proc.stdout.strip() == ""  # exit clean, no decision


def test_hook_writes_log_on_detection(tmp_path):
    out = _run_hook(
        {
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": _leaked_msg(),
            "cwd": str(tmp_path),
            "session_id": "log-sess",
        }
    )
    assert out.get("decision") == "block"
    log = tmp_path / ".omc" / "logs" / "malformed_toolcall.jsonl"
    assert log.exists(), "detection must be logged for telemetry"
    rec = json.loads(log.read_text().strip())
    assert rec["signal"] == "param_invoke_tail"
    assert rec["blocked"] is True

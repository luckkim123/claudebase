"""Tests for runtime/hooks/emoji_guard.py (no-emoji Stop hook).

Mirrors the house pattern from test_detect_malformed_toolcall.py: a unit level
that exercises the pure detector (_find_emoji) and a contract level that drives
the hook end-to-end via subprocess (real stdin -> stdout JSON).

The two load-bearing cases:
  * an assistant message with emoji MUST block;
  * a message carrying only the omha routing / learning-mode symbols
    (arrow, middle dot, em dash, black square, right-triangle, box divider,
    bullet) MUST pass — those are not emoji and blocking them would fire on
    every normal turn.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

# HOOK_PATH resolves to the repo hook when this file lives in tests/hooks/;
# an env override lets the same test verify a work-in-progress copy elsewhere.
HOOK_PATH = Path(
    os.environ.get(
        "EMOJI_GUARD_HOOK",
        str(Path(__file__).resolve().parents[2] / "runtime" / "hooks" / "emoji_guard.py"),
    )
)

# Non-emoji symbols the routing format and learning-mode dividers rely on.
ROUTING_SYMBOLS = "→ · — ■ ▸ ─ •"


def _load_module():
    spec = importlib.util.spec_from_file_location("emoji_guard", HOOK_PATH)
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
        check=False,
    )
    assert proc.returncode == 0, f"hook must always exit 0, got {proc.returncode}: {proc.stderr}"
    out = proc.stdout.strip()
    return json.loads(out) if out else {}


# ---- unit level: the pure detector ----------------------------------------


def test_plain_text_has_no_emoji():
    m = _load_module()
    assert m._find_emoji("Just a normal answer, nothing fancy.") == []
    assert m._find_emoji("") == []
    assert m._find_emoji("가나다 ASCII 123 code_path()") == []


def test_routing_and_divider_symbols_are_not_emoji():
    # THE false-positive guard: every symbol the routing/learning format uses.
    m = _load_module()
    assert m._find_emoji(ROUTING_SYMBOLS) == []
    assert m._find_emoji("ROUTE → handle-directly · 근거 — 끝") == []
    # text stars U+2605-2606 are carved out so learning-mode "★ Insight" passes;
    # the emoji star ⭐ U+2B50 is still caught (asserted in test_common_emoji_are_detected).
    assert m._find_emoji("★ Insight ───────") == []
    assert m._find_emoji("☆ ★") == []


def test_common_emoji_are_detected():
    m = _load_module()
    for ch in ["\U0001F604", "\U0001F1FA", "⚠", "✅", "⭐", "🔄"]:
        assert m._find_emoji("text " + ch + " more") == [ch], ch


def test_variation_selector_sequence_detected():
    m = _load_module()
    # e.g. next-track "⏭️" = U+23ED (outside ranges) + U+FE0F (inside) -> caught via FE0F
    assert "️" in m._find_emoji("⏭️")


# ---- contract level: full stdin -> stdout JSON ----------------------------


def test_hook_blocks_on_emoji():
    out = _run_hook(
        {
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": "작업 완료 ✅ 배포함 ⭐",
            "cwd": "/tmp/nonexistent_test_cwd_emoji",
            "session_id": "test-sess",
        }
    )
    assert out.get("decision") == "block"
    assert "이모지" in out.get("reason", "")


def test_hook_allows_routing_symbols_only():
    # The load-bearing no-false-positive case.
    out = _run_hook(
        {
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": "ROUTE → handle-directly · claudebase 메타 — 끝 ■ ▸ ─ •",
            "cwd": "/tmp/nonexistent_test_cwd_emoji",
        }
    )
    assert out == {}, f"routing symbols must not block, got {out}"


def test_hook_allows_plain_text():
    out = _run_hook(
        {
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": "All done, the file was written and tests pass.",
            "cwd": "/tmp/nonexistent_test_cwd_emoji",
        }
    )
    assert out == {}


def test_hook_dedupes_on_refire():
    # stop_hook_active True == our own block re-fired: must NOT block again.
    out = _run_hook(
        {
            "hook_event_name": "Stop",
            "stop_hook_active": True,
            "last_assistant_message": "still has emoji ✅",
            "cwd": "/tmp/nonexistent_test_cwd_emoji",
        }
    )
    assert out == {}, "must not block twice (infinite-loop guard)"


def test_hook_failsafe_allows_when_loop_field_absent():
    # stop_hook_active ABSENT -> fail-safe allow (one visible emoji beats a loop).
    out = _run_hook(
        {
            "hook_event_name": "Stop",
            "last_assistant_message": "has emoji ⭐",
            "cwd": "/tmp/nonexistent_test_cwd_emoji",
        }
    )
    assert out == {}


def test_hook_ignores_non_stop_event():
    out = _run_hook(
        {
            "hook_event_name": "SubagentStop",
            "stop_hook_active": False,
            "last_assistant_message": "emoji here ✅",
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
        check=False,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_hook_falls_back_to_transcript(tmp_path):
    # last_assistant_message absent -> parse transcript_path JSONL tail.
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(
        json.dumps({"type": "user", "message": {"role": "user", "content": "hi"}}) + "\n"
        + json.dumps(
            {"type": "assistant", "message": {"role": "assistant",
             "content": [{"type": "text", "text": "여기 이모지 ⚠️ 있음"}]}}
        ) + "\n",
        encoding="utf-8",
    )
    out = _run_hook(
        {
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "transcript_path": str(transcript),
            "cwd": str(tmp_path),
        }
    )
    assert out.get("decision") == "block"


def test_hook_writes_log_on_detection(tmp_path):
    out = _run_hook(
        {
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": "done ✅",
            "cwd": str(tmp_path),
            "session_id": "log-sess",
        }
    )
    assert out.get("decision") == "block"
    log = tmp_path / ".omc" / "logs" / "emoji_guard.jsonl"
    assert log.exists(), "detection must be logged for telemetry"
    rec = json.loads(log.read_text().strip())
    assert rec["blocked"] is True
    assert rec["count"] >= 1

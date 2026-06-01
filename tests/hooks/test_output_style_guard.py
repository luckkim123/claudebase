"""Tests for runtime/hooks/output_style_guard.py (Stop filler/sycophancy guard)."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / "runtime" / "hooks" / "output_style_guard.py"


def _load():
    spec = importlib.util.spec_from_file_location("output_style_guard", HOOK_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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


# ---- pure detector ----


def test_filler_opener_detected():
    m = _load()
    assert m._filler_opener("Certainly! Here is the answer.") is not None
    assert m._filler_opener("좋은 질문입니다. 답은...") is not None
    assert m._filler_opener("You're absolutely right, let me fix that.") is not None


def test_clean_opener_not_flagged():
    m = _load()
    assert m._filler_opener("The fix is in line 42.") is None
    assert m._filler_opener("결론부터: 이건 캐시 문제입니다.") is None


def test_declarative_adverbs_not_flagged():
    """평서 부사 용법은 필러가 아님 — 리뷰 실측 재현 케이스(false positive 회귀 방지)."""
    m = _load()
    # 영어: of course / absolutely 가 평서문 부사로 쓰인 경우
    assert m._filler_opener("Of course the build fails.") is None
    assert m._filler_opener("Absolutely not — that's wrong.") is None
    # 한국어: 정상 기술 문장의 '맞-' 어간 (v1 에서 맞- 계열 패턴 제거)
    assert m._filler_opener("정확히 맞는 동작입니다.") is None
    assert m._filler_opener("맞물려 돌아갑니다.") is None
    assert m._filler_opener("맞습니다. 캐시가 원인입니다.") is None


def test_exclamatory_filler_still_flagged():
    """감탄형 아첨은 여전히 잡혀야 함."""
    m = _load()
    assert m._filler_opener("Of course! Here you go.") is not None
    assert m._filler_opener("Absolutely! Let me help.") is not None


def test_great_midtext_is_safe():
    m = _load()
    # "great" only mid-body, opener is clean -> must NOT flag
    assert m._filler_opener("The result is correct. That's a great outcome.") is None


# ---- contract ----


def _filler_msg():
    return "Great question! Let me explain how this works."


def test_off_never_blocks():
    out = _run(
        {
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": _filler_msg(),
            "cwd": "/tmp/x",
        },
        {"CLAUDEBASE_OUTPUT_STYLE": "off"},
    )
    assert out == {}


def test_nudge_never_blocks():
    # nudge mode injects but does NOT block on detection
    out = _run(
        {
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": _filler_msg(),
            "cwd": "/tmp/x",
        },
        {"CLAUDEBASE_OUTPUT_STYLE": "nudge"},
    )
    assert out == {}


def test_enforce_blocks_filler_opener():
    out = _run(
        {
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": _filler_msg(),
            "cwd": "/tmp/x",
            "session_id": "s",
        },
        {"CLAUDEBASE_OUTPUT_STYLE": "enforce"},
    )
    assert out.get("decision") == "block"


def test_enforce_allows_clean():
    out = _run(
        {
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": "The fix is in line 42.",
            "cwd": "/tmp/x",
        },
        {"CLAUDEBASE_OUTPUT_STYLE": "enforce"},
    )
    assert out == {}


def test_dedupe_on_refire():
    out = _run(
        {
            "hook_event_name": "Stop",
            "stop_hook_active": True,
            "last_assistant_message": _filler_msg(),
            "cwd": "/tmp/x",
        },
        {"CLAUDEBASE_OUTPUT_STYLE": "enforce"},
    )
    assert out == {}, "must not block twice (loop guard)"


def test_missing_loop_guard_field_fails_safe():
    # stop_hook_active ABSENT -> fail-safe allow (never wedge a session)
    out = _run(
        {
            "hook_event_name": "Stop",
            "last_assistant_message": _filler_msg(),
            "cwd": "/tmp/x",
        },
        {"CLAUDEBASE_OUTPUT_STYLE": "enforce"},
    )
    assert out == {}


def test_ignores_non_stop_event():
    out = _run(
        {
            "hook_event_name": "SubagentStop",
            "stop_hook_active": False,
            "last_assistant_message": _filler_msg(),
        },
        {"CLAUDEBASE_OUTPUT_STYLE": "enforce"},
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


def test_log_written_on_block(tmp_path):
    out = _run(
        {
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": _filler_msg(),
            "cwd": str(tmp_path),
            "session_id": "log-s",
        },
        {"CLAUDEBASE_OUTPUT_STYLE": "enforce"},
    )
    assert out.get("decision") == "block"
    log = tmp_path / ".omc" / "logs" / "output_style.jsonl"
    assert log.exists()
    rec = json.loads(log.read_text().strip())
    assert rec["blocked"] is True

"""Tests for runtime/hooks/askuserquestion_stats.py — the manual telemetry
aggregator for the AskUserQuestion guard/retry logs ([5]).

The two hooks append one jsonl record per failure:
  .omc/logs/askuserquestion_guard.jsonl  (PreToolUse denies)
  .omc/logs/askuserquestion_retry.jsonl  (Stop-hook missing-`questions` rejections)
This script folds them into a human-readable summary so the effect of the
hardening can actually be measured over time (the logs were write-only before).
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "runtime" / "hooks" / "askuserquestion_stats.py"


def _load():
    spec = importlib.util.spec_from_file_location("askuserquestion_stats", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _seed(tmp_path: Path, fname: str, records: list) -> None:
    log_dir = tmp_path / ".omc" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    p = log_dir / fname
    with p.open("a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def test_aggregate_counts_both_logs(tmp_path):
    m = _load()
    _seed(tmp_path, "askuserquestion_guard.jsonl", [
        {"signal": "denied_askuserquestion", "session_id": "A"},
        {"signal": "denied_askuserquestion", "session_id": "A"},
        {"signal": "denied_askuserquestion", "session_id": "B"},
    ])
    _seed(tmp_path, "askuserquestion_retry.jsonl", [
        {"signal": "empty_askuserquestion", "session_id": "A", "mode": "retry"},
        {"signal": "empty_askuserquestion", "session_id": "A", "mode": "abandon"},
    ])
    stats = m.aggregate(str(tmp_path))
    assert stats["total"] == 5
    assert stats["guard_denies"] == 3
    assert stats["retry_rejections"] == 2
    assert stats["by_session"]["A"] == 4
    assert stats["by_session"]["B"] == 1
    assert stats["abandon_events"] == 1


def test_aggregate_empty_when_no_logs(tmp_path):
    m = _load()
    stats = m.aggregate(str(tmp_path))
    assert stats["total"] == 0
    assert stats["by_session"] == {}


def test_aggregate_skips_corrupt_lines(tmp_path):
    m = _load()
    log_dir = tmp_path / ".omc" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "askuserquestion_guard.jsonl").write_text(
        '{"signal":"denied_askuserquestion","session_id":"A"}\n'
        "not json at all\n"
        '{"signal":"denied_askuserquestion","session_id":"A"}\n',
        encoding="utf-8")
    stats = m.aggregate(str(tmp_path))
    assert stats["total"] == 2, "a corrupt line must be skipped, not crash"


def test_cli_runs_and_prints_summary(tmp_path):
    _seed(tmp_path, "askuserquestion_retry.jsonl", [
        {"signal": "empty_askuserquestion", "session_id": "A", "mode": "retry"}])
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--root", str(tmp_path)],
        capture_output=True, text=True, timeout=15)
    assert proc.returncode == 0, proc.stderr
    assert "total" in proc.stdout.lower()
    assert "1" in proc.stdout

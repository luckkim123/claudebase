"""Tests for runtime/hooks/fix_surrogate.py.

Exercise the scrub logic on synthetic JSONL transcripts containing lone
UTF-16 surrogates (the failure mode that deadlocks Claude Code sessions).
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / "runtime" / "hooks" / "fix_surrogate.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("fix_surrogate", HOOK_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_has_lone_surrogate_detects():
    fs = _load_module()
    assert fs.has_lone_surrogate("normal text") is False
    assert fs.has_lone_surrogate("oops \ud83d trailing") is True   # high surrogate alone
    assert fs.has_lone_surrogate("\udcff") is True                  # low surrogate alone


def test_scrub_replaces_lone_surrogates_in_nested():
    fs = _load_module()
    payload = {"a": "ok", "b": ["leading\ud83d", {"c": "\udcffmix"}]}
    new, count = fs.scrub(payload)
    assert count == 2
    assert new["a"] == "ok"
    assert "\ud83d" not in json.dumps(new, ensure_ascii=False)


def test_strict_encodable():
    fs = _load_module()
    assert fs.strict_encodable({"ok": "ascii"}) is True
    assert fs.strict_encodable({"bad": "lead\ud83d"}) is False


def test_process_file_check_and_fix(tmp_path):
    fs = _load_module()
    p = tmp_path / "transcript.jsonl"
    lines = [
        json.dumps({"clean": "row"}, ensure_ascii=False) + "\n",
        # construct a row with a lone surrogate by writing the escape directly
        '{"dirty": "broken\\ud83dend"}\n',
        json.dumps({"also clean": True}) + "\n",
    ]
    p.write_text("".join(lines), encoding="utf-8")

    total, lines_changed = fs.process_file(str(p), fix=False, backup=False)
    assert total == 1
    assert lines_changed == [1]

    total, lines_changed = fs.process_file(str(p), fix=True, backup=False)
    assert total == 1
    assert lines_changed == [1]

    # Second fix pass on now-clean file should detect nothing.
    total2, _ = fs.process_file(str(p), fix=False, backup=False)
    assert total2 == 0


def test_process_file_missing_returns_silently(tmp_path):
    fs = _load_module()
    # process_file expects an existing path; the missing-file branch is in main().
    # Here we verify the strict_encodable path is taken on a clean file.
    p = tmp_path / "clean.jsonl"
    p.write_text(json.dumps({"x": 1}) + "\n", encoding="utf-8")
    total, lines = fs.process_file(str(p), fix=False, backup=False)
    assert total == 0
    assert lines == []


def test_fix_multiple_files_fires_hooklog_once(tmp_path):
    """CLI `--fix a b` touching two files with lone surrogates must still log
    ONE aggregate firing (repaired = sum across files), not one per file —
    same "1 firing = 1 line" contract as graph-refresh.sh's dedup fix."""
    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    a.write_text('{"dirty": "broken\\ud83dend"}\n', encoding="utf-8")
    b.write_text(
        '{"dirty": "broken\\ud83dend"}\n{"dirty2": "more\\udcffbad"}\n',
        encoding="utf-8",
    )
    subprocess.run(
        [sys.executable, str(HOOK_PATH), "--fix", "--no-backup", str(a), str(b)],
        cwd=str(tmp_path), capture_output=True, text=True, check=True,
    )
    log = tmp_path / ".omc" / "logs" / "fix_surrogate.jsonl"
    rows = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1, "one invocation touching two files must fire once"
    assert rows[0]["repaired"] == 3  # 1 surrogate in a.jsonl + 2 (two lines) in b.jsonl

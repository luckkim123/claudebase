"""Tests for runtime/hooks/usage_tracker.py.

The failure this guards against is the silent one: a usage hook that runs, exits
0, and writes rows full of zeros because it read `usage` from the hook payload
(where it does not exist) instead of the transcript. Rows accumulate, the file
looks healthy, and the weekly review is measuring nothing. So the assertions
below are mostly about the NUMBERS being right, not about the hook running.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / "runtime" / "hooks" / "usage_tracker.py"


def write_transcript(path: Path, turns: list[dict]) -> Path:
    """turns: [{"model": ..., "usage": {...}}] plus any raw dicts to pass through."""
    lines = []
    for t in turns:
        if "type" in t:
            lines.append(t)
        else:
            lines.append(
                {"type": "assistant", "message": {"model": t["model"], "usage": t["usage"]}}
            )
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    return path


def run_hook(tmp_path: Path, payload: dict, raw_stdin: str | None = None):
    """Run the hook with CLAUDE_CONFIG_DIR pointed at a sandbox. Returns (rc, rows)."""
    cfg = tmp_path / "cfg"
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=raw_stdin if raw_stdin is not None else json.dumps(payload),
        capture_output=True,
        text=True,
        env={"CLAUDE_CONFIG_DIR": str(cfg), "PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
    )
    out = cfg / "metrics" / "usage.jsonl"
    rows = (
        [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
        if out.is_file()
        else []
    )
    return proc.returncode, rows


USAGE_A = {
    "input_tokens": 10,
    "output_tokens": 5,
    "cache_creation_input_tokens": 100,
    "cache_read_input_tokens": 1000,
}


class TestCounts:
    def test_sums_token_fields_across_turns(self, tmp_path):
        t = write_transcript(
            tmp_path / "t.jsonl",
            [{"model": "claude-opus-5", "usage": USAGE_A}] * 3,
        )
        rc, rows = run_hook(tmp_path, {"session_id": "s1", "transcript_path": str(t)})
        assert rc == 0 and len(rows) == 1
        assert rows[0]["totals"] == {
            "input_tokens": 30,
            "output_tokens": 15,
            "cache_creation_input_tokens": 300,
            "cache_read_input_tokens": 3000,
        }
        assert rows[0]["turns"] == 3

    def test_splits_by_model(self, tmp_path):
        t = write_transcript(
            tmp_path / "t.jsonl",
            [
                {"model": "claude-opus-5", "usage": USAGE_A},
                {"model": "claude-sonnet-5", "usage": USAGE_A},
                {"model": "claude-sonnet-5", "usage": USAGE_A},
            ],
        )
        _, rows = run_hook(tmp_path, {"session_id": "s1", "transcript_path": str(t)})
        models = rows[0]["models"]
        assert models["claude-opus-5"]["turns"] == 1
        assert models["claude-sonnet-5"]["turns"] == 2
        assert models["claude-sonnet-5"]["input_tokens"] == 20

    def test_ignores_non_token_usage_fields(self, tmp_path):
        # `iterations` and `speed` live in the same usage object and are not
        # tokens; summing everything numeric would inflate the total.
        usage = dict(USAGE_A, iterations=7, speed=999, service_tier="standard")
        t = write_transcript(tmp_path / "t.jsonl", [{"model": "m", "usage": usage}])
        _, rows = run_hook(tmp_path, {"session_id": "s1", "transcript_path": str(t)})
        assert sum(rows[0]["totals"].values()) == 1115  # 10+5+100+1000, no 7 or 999

    def test_does_not_count_user_turns(self, tmp_path):
        t = write_transcript(
            tmp_path / "t.jsonl",
            [
                {"type": "user", "message": {"usage": USAGE_A}},
                {"model": "m", "usage": USAGE_A},
            ],
        )
        _, rows = run_hook(tmp_path, {"session_id": "s1", "transcript_path": str(t)})
        assert rows[0]["turns"] == 1

    def test_row_is_cumulative_not_incremental(self, tmp_path):
        # Stop fires per response: two runs against a growing transcript must
        # leave the LAST row holding the whole session total.
        p = tmp_path / "t.jsonl"
        write_transcript(p, [{"model": "m", "usage": USAGE_A}])
        run_hook(tmp_path, {"session_id": "s1", "transcript_path": str(p)})
        write_transcript(p, [{"model": "m", "usage": USAGE_A}] * 2)
        _, rows = run_hook(tmp_path, {"session_id": "s1", "transcript_path": str(p)})
        assert len(rows) == 2
        assert rows[-1]["totals"]["input_tokens"] == 20


class TestNeverBreaksATurn:
    @pytest.mark.parametrize(
        "stdin", ["", "not json", "[]", "null", '{"transcript_path": "/nope/x.jsonl"}']
    )
    def test_bad_input_exits_zero_and_writes_nothing(self, tmp_path, stdin):
        rc, rows = run_hook(tmp_path, {}, raw_stdin=stdin)
        assert rc == 0 and rows == []

    def test_malformed_transcript_lines_are_skipped_not_fatal(self, tmp_path):
        p = tmp_path / "t.jsonl"
        p.write_text(
            json.dumps(
                {"type": "assistant", "message": {"model": "m", "usage": USAGE_A}}
            )
            + "\n{ truncated mid-lin",
            encoding="utf-8",
        )
        rc, rows = run_hook(tmp_path, {"session_id": "s1", "transcript_path": str(p)})
        assert rc == 0 and rows[0]["turns"] == 1

    def test_transcript_without_usage_writes_no_row(self, tmp_path):
        # An empty row is worse than none: it reads as a measured zero.
        p = tmp_path / "t.jsonl"
        p.write_text(json.dumps({"type": "assistant", "message": {"model": "m"}}) + "\n")
        rc, rows = run_hook(tmp_path, {"session_id": "s1", "transcript_path": str(p)})
        assert rc == 0 and rows == []


class TestAgainstRealTranscript:
    def test_live_session_transcript_yields_nonzero_totals(self, tmp_path):
        """The zero-fill regression is only truly excluded by real data."""
        import glob
        import os

        candidates = glob.glob(
            os.path.expanduser("~/.claude/projects/*/*.jsonl")
        )
        if not candidates:
            pytest.skip("no local transcripts on this machine")
        real = max(candidates, key=os.path.getsize)
        _, rows = run_hook(tmp_path, {"session_id": "real", "transcript_path": real})
        if not rows:
            pytest.skip("largest transcript carries no assistant usage")
        assert rows[0]["totals"]["output_tokens"] > 0
        assert rows[0]["totals"]["input_tokens"] > 0

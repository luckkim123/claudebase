"""Tests for runtime/hooks/harness_stats.py — the manual telemetry aggregator
that generalizes `askuserquestion_stats.py` across every guard plus the omha
routing log.

Each test here locks a defect measured on 2026-08-15 while building it. All
three were silent — the script printed a clean, plausible, wrong table:

  · the project-path slug folds EVERY non-alphanumeric character, so folding
    only '/' found no transcript and dumped all 98 turns into '(unmatched)'
  · the log stems parsed out of a hook's source have to keep their `.jsonl`
    extension to match the firing counts, or a guard with 48 records is
    reported as never-fired and nominated for retirement
  · a hook that was never built to log must not be counted as a guard that
    stopped firing — the two are indistinguishable by log absence alone
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "runtime" / "hooks" / "harness_stats.py"


def _load():
    spec = importlib.util.spec_from_file_location("harness_stats", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ─── slug ───────────────────────────────────────────────────────────────────

def test_transcript_slug_folds_underscores_not_just_slashes(tmp_path):
    """`ksm_Obsidian` is stored as `ksm-Obsidian`. Measured against the live
    ~/.claude/projects listing."""
    m = _load()
    d = tmp_path / "ksm_Obsidian"
    d.mkdir()
    got = m._transcript_dir(d).name
    assert "_" not in got, f"underscore must fold to '-': {got}"
    assert got.endswith("-ksm-Obsidian"), got


def test_transcript_slug_folds_dot_directories(tmp_path):
    """`/.claude/worktrees` becomes `--claude-worktrees` — the dot folds too."""
    m = _load()
    d = tmp_path / ".claude" / "worktrees" / "x"
    d.mkdir(parents=True)
    got = m._transcript_dir(d).name
    assert "--claude-worktrees-x" in got, got


# ─── never-fired split ──────────────────────────────────────────────────────

def test_firing_guard_is_not_a_retirement_candidate():
    """The stem->count key must match, or a busy guard reads as dead."""
    m = _load()
    wired = {"agent-routing-guard.py": ["PreToolUse"]}
    loggers = {"agent-routing-guard.py": {"agent_routing_guard.jsonl"}}
    fired = {"agent_routing_guard.jsonl": {"count": 48, "roots": {}, "mtime": None}}
    candidates, non_logging = m.silent_guards(wired, loggers, fired)
    assert candidates == [], "a guard with 48 records is not a retirement candidate"
    assert non_logging == []


def test_silent_logging_guard_is_a_candidate():
    m = _load()
    wired = {"emoji_guard.py": ["Stop"]}
    loggers = {"emoji_guard.py": {"emoji_guard.jsonl"}}
    candidates, _ = m.silent_guards(wired, loggers, {})
    assert candidates == [("emoji_guard.py", ["emoji_guard.jsonl"])]


def test_non_logging_hook_is_never_a_retirement_candidate():
    """The third meaning of 'no log': the hook never logged in the first place."""
    m = _load()
    wired = {"graphify-guard.sh": ["PreToolUse"], "hud-ensure.sh": ["SessionStart"]}
    candidates, non_logging = m.silent_guards(wired, {}, {})
    assert candidates == [], "absence of a log proves nothing about a non-logger"
    assert non_logging == ["graphify-guard.sh", "hud-ensure.sh"]


# ─── wired hooks ────────────────────────────────────────────────────────────

def test_wired_hooks_keys_on_script_not_label():
    m = _load()
    settings = {"hooks": {
        "Stop": [{"hooks": [
            {"command": "# EMOJI\npython3 ~/claudebase/runtime/hooks/emoji_guard.py"},
            {"command": "bash ~/claudebase/runtime/hooks/graphify-guard.sh stop"},
        ]}],
        "PreToolUse": [{"hooks": [
            {"command": "bash ~/claudebase/runtime/hooks/graphify-guard.sh pre"},
        ]}],
    }}
    wired = m.wired_hooks(settings)
    assert set(wired) == {"emoji_guard.py", "graphify-guard.sh"}
    assert sorted(wired["graphify-guard.sh"]) == ["PreToolUse", "Stop"]


# ─── per-session join ───────────────────────────────────────────────────────

def _seed_routing(root: Path, records: list) -> None:
    d = root / ".omha"
    d.mkdir(parents=True, exist_ok=True)
    with (d / "routing.jsonl").open("a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def test_by_session_joins_turn_id_to_transcript_uuid(tmp_path, monkeypatch):
    m = _load()
    root = tmp_path / "proj"
    root.mkdir()
    _seed_routing(root, [
        {"turn_id": "u1", "lanes": ["omc"], "missing": False},
        {"turn_id": "u2", "lanes": [], "missing": True},
        {"turn_id": "u3", "lanes": ["omp"], "missing": False},
    ])
    tdir = tmp_path / "transcripts"
    tdir.mkdir()
    (tdir / "sessA.jsonl").write_text(
        '{"uuid":"u1"}\n{"uuid":"u2"}\n', encoding="utf-8")
    (tdir / "sessB.jsonl").write_text('{"uuid":"u3"}\n', encoding="utf-8")
    monkeypatch.setattr(m, "_transcript_dir", lambda _root: tdir)

    rows = {s: (t, miss) for s, t, miss in m.by_session(root, None)}
    assert rows["sessA"] == (2, 1)
    assert rows["sessB"] == (1, 0)
    assert "(unmatched)" not in rows


def test_by_session_keeps_unmatched_turns_in_the_denominator(tmp_path, monkeypatch):
    """Dropping a turn whose transcript is gone would understate the total —
    the exact error this table exists to avoid."""
    m = _load()
    root = tmp_path / "proj"
    root.mkdir()
    _seed_routing(root, [{"turn_id": "gone", "lanes": [], "missing": True}])
    empty = tmp_path / "none"
    empty.mkdir()
    monkeypatch.setattr(m, "_transcript_dir", lambda _root: empty)
    assert m.by_session(root, None) == [("(unmatched)", 1, 1)]


# ─── robustness + CLI ───────────────────────────────────────────────────────

def test_corrupt_jsonl_line_is_skipped(tmp_path):
    m = _load()
    p = tmp_path / "x.jsonl"
    p.write_text('{"a":1}\nnot json\n{"a":2}\n', encoding="utf-8")
    assert len(m._read_jsonl(p)) == 2


def test_cli_runs_on_an_empty_root(tmp_path):
    """No logs anywhere must still exit 0 with all four tables present."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--root", str(tmp_path)],
        check=False, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    for marker in ("[1]", "[2]", "[3]", "[4]"):
        assert marker in proc.stdout, f"{marker} table missing"

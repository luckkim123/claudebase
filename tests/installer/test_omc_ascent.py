"""Tests for runtime/omc-patches/_claudebase-omc-ascent.cjs (ascendToMarker).

The helper is JS (loaded by OMC's ESM worktree-paths.js via createRequire),
so these tests drive it through `node -e` and assert the returned root.

Contract (design 2026-05-31-omc-statedir-marker-ascent):
  ascendToMarker(startDir) climbs parents looking for a project-boundary
  marker (.omcroot > .git > CLAUDE.md), returns the first dir that has one,
  stops at $HOME / filesystem root, returns null when none found.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HELPER = REPO / "runtime" / "omc-patches" / "_claudebase-omc-ascent.cjs"


def ascend(start: Path, home: str | None = None) -> str | None:
    """Invoke ascendToMarker(start) via node, return its JSON result (or None)."""
    prelude = f"process.env.HOME={json.dumps(home)};" if home else ""
    code = (
        prelude
        + f"const {{ascendToMarker}}=require({json.dumps(str(HELPER))});"
        + f"const r=ascendToMarker({json.dumps(str(start))});"
        + "process.stdout.write(JSON.stringify(r===undefined?null:r));"
    )
    out = subprocess.run(
        ["node", "-e", code], capture_output=True, text=True, check=True
    )
    return json.loads(out.stdout)


def test_finds_claude_md_in_parent(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("x")
    sub = tmp_path / "a" / "b"
    sub.mkdir(parents=True)
    assert ascend(sub, home=str(tmp_path.parent)) == str(tmp_path)


def test_omcroot_takes_priority_when_deeper(tmp_path):
    # A nearer .omcroot wins over a farther CLAUDE.md (nearest marker stops ascent).
    (tmp_path / "CLAUDE.md").write_text("x")
    inner = tmp_path / "proj"
    inner.mkdir()
    (inner / ".omcroot").write_text("")
    assert ascend(inner, home=str(tmp_path.parent)) == str(inner)


def test_returns_none_when_no_marker(tmp_path):
    sub = tmp_path / "a" / "b"
    sub.mkdir(parents=True)
    assert ascend(sub, home=str(tmp_path.parent)) is None


def test_stops_at_home(tmp_path):
    # Ascent must not climb past $HOME even if a marker sits above it.
    (tmp_path / "CLAUDE.md").write_text("x")  # marker ABOVE home — must be ignored
    home = tmp_path / "home"
    deep = home / "x" / "y"
    deep.mkdir(parents=True)
    assert ascend(deep, home=str(home)) is None

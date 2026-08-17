"""Shared pytest fixtures for claudebase tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# Make runtime/hooks/ and installer/scripts/ importable as flat modules.
for sub in ("runtime/hooks", "installer/scripts"):
    p = str(REPO_ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture(autouse=True)
def neutralize_claudebase_env(monkeypatch):
    """Strip the env this repo injects into Claude Code, so tests stay hermetic.

    `render_settings.py` writes `env.OMC_STATE_DIR` into ~/.claude/settings.json,
    and Claude Code exports that to every subprocess of every session — this
    pytest run included. `tests/installer/test_patch_omc_statedir.py` spawns
    `node` without an explicit `env`, so the variable reaches the code under
    test, whose `getOmcRoot()` checks it *before* the marker-ascent branch those
    tests exist to verify. Three of them then assert the ascent path while the
    override path is what actually ran.

    What hid it is the blast pattern: neither CI (.github/workflows/ci.yml sets
    nothing) nor a login shell (~/.zshrc and shell/ never export it) has the
    variable, so the suite fails *only* when run from inside the agent this repo
    configures — green everywhere anyone thought to look.

    Scoped to variables claudebase itself injects. A test that wants
    OMC_STATE_DIR set should `monkeypatch.setenv` it, which still wins.
    """
    monkeypatch.delenv("OMC_STATE_DIR", raising=False)

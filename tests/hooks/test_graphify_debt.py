"""Tests for runtime/hooks/graphify-debt.sh.

The hook reports how many prose files fell out of graphify's semantic cache, so
the backlog is paid down in minutes instead of surfacing as a multi-hour job
(288 files after four days of note editing, measured on one vault). Everything
worth pinning is a decision about *when not to speak*: the count costs a full
content hash of the corpus (2.9 s / 937 files), so a repo that never ran a
prose pass must not pay it, a second session inside the debounce must not pay
it, and a small backlog must not interrupt anyone.

A stub interpreter stands in for the graphify venv so the assertions are about
the hook's gating rather than graphify's hashing. HOME is redirected into the
sandbox because the hook reads the extraction spec from ~/.claude — the file
whose sha256 is the cache's bucket key, and without which any count is fiction.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / "runtime" / "hooks" / "graphify-debt.sh"

OUT_DIR = ".graphify"
MARKER = f"{OUT_DIR}/.semantic-debt-checked"


@pytest.fixture
def sandbox(tmp_path: Path):
    """A project carrying a graph and a semantic cache, plus a stub interpreter."""
    home, repo = tmp_path / "home", tmp_path / "repo"
    spec = home / ".claude" / "skills" / "graphify" / "references" / "extraction-spec.md"
    spec.parent.mkdir(parents=True)
    spec.write_text("synthetic extraction spec")

    out = repo / OUT_DIR
    (out / "cache" / "semantic").mkdir(parents=True)
    (out / "graph.json").write_text('{"nodes":[],"links":[]}')
    return home, repo


def set_uncached(repo: Path, text: str) -> None:
    """Point the hook at a stub interpreter that reports `text` as the count."""
    stub = repo / OUT_DIR / "stub-python"
    stub.write_text(f"#!/bin/sh\nprintf '%s\\n' '{text}'\n")
    stub.chmod(0o755)
    (repo / OUT_DIR / ".graphify_python").write_text(str(stub))


def run_hook(home: Path, repo: Path, **env_extra):
    env = {
        **os.environ,
        "HOME": str(home),
        "GRAPHIFY_OUT": OUT_DIR,
        **env_extra,
    }
    return subprocess.run(
        ["bash", str(HOOK)], cwd=repo, env=env, input="", capture_output=True, text=True
    )


def context_of(result) -> str:
    return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]


def test_backlog_over_threshold_is_reported(sandbox):
    """The whole point: a real backlog reaches the session as context."""
    home, repo = sandbox
    set_uncached(repo, "288")
    result = run_hook(home, repo)

    parsed = json.loads(result.stdout)
    assert parsed["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "288" in context_of(result)


def test_small_backlog_stays_quiet_but_records_the_count(sandbox):
    """Below the threshold the interruption costs more than the work it saves."""
    home, repo = sandbox
    set_uncached(repo, "3")
    result = run_hook(home, repo)

    assert result.stdout == ""
    # The marker is still written, so the 2.9 s hash is not repaid next session.
    assert (repo / MARKER).read_text().split()[-1] == "3"


def test_debounce_suppresses_a_second_session(sandbox):
    """The cost bound is per-marker-age, not per-session."""
    home, repo = sandbox
    set_uncached(repo, "288")
    assert run_hook(home, repo).stdout != ""

    assert run_hook(home, repo).stdout == ""


def test_expired_debounce_speaks_again(sandbox):
    """A backlog left unpaid must resurface, or the notice is a one-shot."""
    home, repo = sandbox
    set_uncached(repo, "288")
    run_hook(home, repo)

    old = time.time() - 40 * 3600
    os.utime(repo / MARKER, (old, old))

    assert "288" in context_of(run_hook(home, repo))


def test_project_without_a_semantic_cache_is_skipped_entirely(sandbox):
    """A code-only repo has no prose debt; it must not pay for the count."""
    home, repo = sandbox
    set_uncached(repo, "288")
    (repo / OUT_DIR / "cache" / "semantic").rmdir()

    result = run_hook(home, repo)

    assert result.stdout == ""
    assert not (repo / MARKER).exists()


def test_missing_extraction_spec_is_skipped(sandbox):
    """The spec's hash is the cache bucket key — without it every count is fiction."""
    home, repo = sandbox
    set_uncached(repo, "288")
    (home / ".claude/skills/graphify/references/extraction-spec.md").unlink()

    assert run_hook(home, repo).stdout == ""


def test_non_numeric_output_is_swallowed(sandbox):
    """If graphify moves its API the hook must go quiet, never emit a traceback."""
    home, repo = sandbox
    set_uncached(repo, "Traceback (most recent call last):")

    result = run_hook(home, repo)

    assert result.stdout == ""
    assert not (repo / MARKER).exists()

"""Tests for runtime/hooks/graph-refresh.sh.

The hook keeps existing code graphs current so the PreToolUse guards never route
a session through a stale index. Everything worth pinning down is a decision
about *when not to run*: the hook must stay out of repositories that never asked
for a graph, must not re-run once a minute has not passed, and must not race a
multi-hour semantic extraction. A stub binary stands in for graphify so the
assertions are about the hook's logic, not the builder's.
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / "runtime" / "hooks" / "graph-refresh.sh"

# The updates are detached on purpose (a turn must never wait on them), so the
# call log lands shortly after the hook returns rather than before.
SETTLE_TIMEOUT = 5.0


@pytest.fixture
def sandbox(tmp_path: Path):
    """A git repo plus a stub graphify that logs its argv."""
    bin_dir, repo = tmp_path / "bin", tmp_path / "repo"
    bin_dir.mkdir()
    repo.mkdir()
    log = tmp_path / "calls.log"

    stub = bin_dir / "graphify"
    stub.write_text(f'#!/bin/sh\necho "$(basename "$0") $*" >> "{log}"\n')
    stub.chmod(0o755)

    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    return repo, bin_dir, log


def run_hook(repo: Path, bin_dir: Path, out_dir: str = ".graphify"):
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "GRAPHIFY_OUT": out_dir,
    }
    return subprocess.run(
        ["bash", str(HOOK)], cwd=repo, env=env, input="", capture_output=True, text=True
    )



def firing_log_lines(repo: Path) -> list[str]:
    """Lines in the hook's own firing log (Fix Round 1: must be exactly one per
    invocation, however many graphs that invocation touched)."""
    p = repo / ".omc" / "logs" / "graph_refresh.jsonl"
    return p.read_text().splitlines() if p.exists() else []


def calls(log: Path, expected: int) -> list[str]:
    """Read the detached stubs' log once it has `expected` lines, or give up."""
    deadline = time.monotonic() + SETTLE_TIMEOUT
    while time.monotonic() < deadline:
        lines = log.read_text().splitlines() if log.exists() else []
        if len(lines) >= expected:
            return lines
        time.sleep(0.05)
    return log.read_text().splitlines() if log.exists() else []


class TestOptInByExistence:
    def test_repo_without_a_graph_is_left_alone(self, sandbox):
        # The whole point of keying on existence: this hook ships at user scope,
        # so it runs in every repository the user ever opens. One that never
        # built a graph must come away with no new directories and no calls.
        repo, bin_dir, log = sandbox
        assert run_hook(repo, bin_dir).returncode == 0
        assert calls(log, 1) == []
        assert {p.name for p in repo.iterdir()} == {".git"}

    def test_outside_a_git_repo_it_does_nothing(self, tmp_path):
        # `git rev-parse` fails here; the hook must exit clean rather than let
        # the Stop event surface an error.
        result = subprocess.run(
            ["bash", str(HOOK)], cwd=tmp_path, input="", capture_output=True, text=True
        )
        assert result.returncode == 0


class TestRefresh:
    def test_the_graph_is_updated_when_it_exists(self, sandbox):
        repo, bin_dir, log = sandbox
        (repo / ".graphify").mkdir()
        (repo / ".graphify" / "graph.json").write_text("{}")

        run_hook(repo, bin_dir)

        assert calls(log, 1) == ["graphify update ."]
        assert len(firing_log_lines(repo)) == 1

    def test_a_second_run_within_the_minute_is_debounced(self, sandbox):
        # A chatty session fires Stop after every turn; re-parsing each time buys
        # nothing and would eventually overlap with itself.
        repo, bin_dir, log = sandbox
        (repo / ".graphify").mkdir()
        (repo / ".graphify" / "graph.json").write_text("{}")

        run_hook(repo, bin_dir)
        assert calls(log, 1) == ["graphify update ."]

        run_hook(repo, bin_dir)
        assert calls(log, 2) == ["graphify update ."]

    def test_graphify_defers_to_a_running_extraction(self, sandbox):
        # A semantic extract streams into cache/ for hours. Recent write
        # activity there means "in flight". The check is per-repo, so a long run
        # in one repository must not freeze the refresh everywhere else.
        #
        # The chunk lands in a nested per-corpus directory on purpose: that is
        # where graphify actually writes, and a check on cache/'s own mtime
        # missed it in production.
        repo, bin_dir, log = sandbox
        chunk_dir = repo / ".graphify" / "cache" / "semantic" / "pf33081f95084"
        chunk_dir.mkdir(parents=True)
        (chunk_dir / "abc123.json").write_text("{}")
        (repo / ".graphify" / "graph.json").write_text("{}")

        run_hook(repo, bin_dir)

        assert calls(log, 1) == []

    def test_a_finished_extraction_stops_blocking_the_refresh(self, sandbox):
        # The mirror image: a cache left behind by a run that ended must not
        # freeze this repository's graph forever. Backdated well past the
        # ten-minute window.
        repo, bin_dir, log = sandbox
        chunk = repo / ".graphify" / "cache" / "semantic" / "old" / "abc123.json"
        chunk.parent.mkdir(parents=True)
        chunk.write_text("{}")
        stale = time.time() - 3600
        os.utime(chunk, (stale, stale))
        (repo / ".graphify" / "graph.json").write_text("{}")

        run_hook(repo, bin_dir)

        assert calls(log, 1) == ["graphify update ."]

    def test_the_no_auto_refresh_marker_keeps_graphify_out(self, sandbox):
        # `graphify update .` re-scans; a graph assembled from an explicit file
        # list (code in gitignored checkouts, a hand-built scope) is not
        # reproducible by that scan, so the update prunes every file it cannot
        # see. Measured: a 6,427-node graph replaced by a 20-node heading index.
        repo, bin_dir, log = sandbox
        (repo / ".graphify").mkdir()
        (repo / ".graphify" / "graph.json").write_text("{}")
        (repo / ".graphify" / ".no-auto-refresh").write_text("")

        run_hook(repo, bin_dir)

        assert calls(log, 1) == []
        assert firing_log_lines(repo) == []

    def test_graphify_out_relocation_is_honoured(self, sandbox):
        # GRAPHIFY_OUT moves the whole output tree; the hook reads it so the
        # hidden-directory machines are not silently skipped.
        repo, bin_dir, log = sandbox
        (repo / "custom-out").mkdir()
        (repo / "custom-out" / "graph.json").write_text("{}")

        run_hook(repo, bin_dir, out_dir="custom-out")

        assert calls(log, 1) == ["graphify update ."]

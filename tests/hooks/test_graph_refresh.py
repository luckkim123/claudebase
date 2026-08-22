"""Tests for runtime/hooks/graph-refresh.sh.

The hook keeps existing code graphs current so the PreToolUse guards never route
a session through a stale index. Everything worth pinning down is a decision
about *when not to run*: the hook must stay out of repositories that never asked
for a graph, must not re-run once a minute has not passed, and must not race a
multi-hour semantic extraction. Stub binaries stand in for graphify and
code-review-graph so the assertions are about the hook's logic, not theirs.
"""
from __future__ import annotations

import os
import sqlite3
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
    """A git repo plus stub graphify / code-review-graph that log their argv."""
    bin_dir, repo = tmp_path / "bin", tmp_path / "repo"
    bin_dir.mkdir()
    repo.mkdir()
    log = tmp_path / "calls.log"

    for name in ("graphify", "code-review-graph"):
        stub = bin_dir / name
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


def make_crg_graph(repo: Path, nodes: int = 1) -> Path:
    """Create a `.code-review-graph/` the hook will accept as a real graph.

    A bare directory is not enough: any MCP query that omits `repo_root` leaves
    an empty `graph.db` behind, so the hook gates on the node count rather than
    on existence. Pass `nodes=0` to build one of those empty artifacts.
    """
    gdir = repo / ".code-review-graph"
    gdir.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(gdir / "graph.db")
    db.execute("CREATE TABLE IF NOT EXISTS nodes (id INTEGER PRIMARY KEY)")
    db.executemany("INSERT INTO nodes (id) VALUES (?)", [(i,) for i in range(nodes)])
    db.commit()
    db.close()
    return gdir


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
    def test_both_graphs_are_updated_when_both_exist(self, sandbox):
        repo, bin_dir, log = sandbox
        (repo / ".graphify").mkdir()
        (repo / ".graphify" / "graph.json").write_text("{}")
        make_crg_graph(repo)

        run_hook(repo, bin_dir)

        assert calls(log, 2) == ["graphify update .", "code-review-graph update --brief"]
        assert len(firing_log_lines(repo)) == 1

    def test_a_second_run_within_the_minute_is_debounced(self, sandbox):
        # A chatty session fires Stop after every turn; re-parsing each time buys
        # nothing and would eventually overlap with itself.
        repo, bin_dir, log = sandbox
        make_crg_graph(repo)

        run_hook(repo, bin_dir)
        assert calls(log, 1) == ["code-review-graph update --brief"]

        run_hook(repo, bin_dir)
        assert calls(log, 2) == ["code-review-graph update --brief"]

    def test_graphify_defers_to_a_running_extraction(self, sandbox):
        # A semantic extract streams into cache/ for hours. Recent write
        # activity there means "in flight" — and the check is per-repo, so a
        # long run in one repository must not stop code-review-graph from
        # updating in this one.
        #
        # The chunk lands in a nested per-corpus directory on purpose: that is
        # where graphify actually writes, and a check on cache/'s own mtime
        # missed it in production.
        repo, bin_dir, log = sandbox
        chunk_dir = repo / ".graphify" / "cache" / "semantic" / "pf33081f95084"
        chunk_dir.mkdir(parents=True)
        (chunk_dir / "abc123.json").write_text("{}")
        (repo / ".graphify" / "graph.json").write_text("{}")
        make_crg_graph(repo)

        run_hook(repo, bin_dir)

        assert calls(log, 1) == ["code-review-graph update --brief"]

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

    def test_a_graph_below_the_git_root_is_refreshed(self, sandbox):
        # A meta-repo that gitignores its source tree holds the real graphs in
        # nested independent repos (stonefish_ws: src/stonefish_sim,
        # src/stonefish_slam). Keying only on `$repo/.code-review-graph` left
        # both of them stale forever, which is worse than having no graph — the
        # PreToolUse guards still route every query through them.
        repo, bin_dir, log = sandbox
        make_crg_graph(repo / "src" / "pkg_a")
        make_crg_graph(repo / "src" / "pkg_b")

        run_hook(repo, bin_dir)

        assert calls(log, 2) == ["code-review-graph update --brief"] * 2
        assert len(firing_log_lines(repo)) == 1

    def test_the_update_runs_in_the_graphs_own_directory(self, sandbox):
        # `code-review-graph update` resolves the repo from its cwd, so a nested
        # graph refreshed from the meta-repo root would re-parse the wrong tree.
        repo, bin_dir, log = sandbox
        nested = repo / "src" / "pkg_a"
        make_crg_graph(nested)
        # Re-stub so the log records where the process actually ran.
        stub = bin_dir / "code-review-graph"
        stub.write_text(f'#!/bin/sh\necho "cwd=$(pwd)" >> "{log}"\n')
        stub.chmod(0o755)

        run_hook(repo, bin_dir)

        assert calls(log, 1) == [f"cwd={nested}"]

    def test_an_empty_graph_is_not_refreshed(self, sandbox):
        # Any MCP query that omits `repo_root` creates a 0-node graph.db at the
        # server's cwd. Treating that as opt-in made the hook refresh an empty
        # database every turn while the real graphs went stale.
        repo, bin_dir, log = sandbox
        make_crg_graph(repo, nodes=0)

        run_hook(repo, bin_dir)

        assert calls(log, 1) == []

    def test_graphify_out_relocation_is_honoured(self, sandbox):
        # GRAPHIFY_OUT moves the whole output tree; the hook reads it so the
        # hidden-directory machines are not silently skipped.
        repo, bin_dir, log = sandbox
        (repo / "custom-out").mkdir()
        (repo / "custom-out" / "graph.json").write_text("{}")

        run_hook(repo, bin_dir, out_dir="custom-out")

        assert calls(log, 1) == ["graphify update ."]

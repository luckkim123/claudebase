"""Tests for runtime/hooks/graph-offer.sh.

The hook tells a session that this repository has no code graph, once, and lets
the user decide. Everything worth pinning down is a boundary: it must stay
silent where a graph exists or where there is nothing to parse, and it must
never ask a second time — the marker is written when the offer is emitted, so
ignoring the prompt is itself a durable answer.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / "runtime" / "hooks" / "graph-offer.sh"
MARKER = "claudebase-graph-offered"


def make_repo(path: Path, code_files: int) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    for i in range(code_files):
        (path / f"mod{i}.py").write_text("x = 1\n")
    if code_files:
        subprocess.run(["git", "add", "-A"], cwd=path, check=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
            cwd=path,
            check=True,
        )
    return path


def run_hook(repo: Path, out_dir: str = ".graphify") -> subprocess.CompletedProcess:
    env = {**os.environ, "GRAPHIFY_OUT": out_dir}
    return subprocess.run(
        ["bash", str(HOOK)], cwd=repo, env=env, input="", capture_output=True, text=True
    )


@pytest.fixture
def repo(tmp_path):
    return make_repo(tmp_path / "repo", code_files=25)


class TestOffer:
    def test_a_code_repo_without_a_graph_is_offered_one(self, repo):
        result = run_hook(repo)

        payload = json.loads(result.stdout)["hookSpecificOutput"]
        assert payload["hookEventName"] == "SessionStart"
        # The session, not the hook, does the asking — the hook cannot prompt.
        assert "AskUserQuestion" in payload["additionalContext"]
        # Both free builds are named, and the paid prose pass is not offered.
        assert "code-review-graph build" in payload["additionalContext"]
        assert "graphify ." in payload["additionalContext"]

    def test_the_offer_names_the_verification_step(self, repo):
        # An unverified graph is the failure this whole hook exists to avoid:
        # the guards force consultation of whatever got built, so the offer has
        # to carry the instruction to check the result and delete it if useless.
        ctx = json.loads(run_hook(repo).stdout)["hookSpecificOutput"]["additionalContext"]
        assert "code-review-graph status" in ctx
        assert "vendored" in ctx

    def test_it_asks_only_once_per_repo(self, repo):
        assert run_hook(repo).stdout.strip()
        assert (repo / ".git" / MARKER).exists()
        # Second session: silent, whatever the user did or did not answer.
        assert run_hook(repo).stdout.strip() == ""


class TestSilence:
    def test_outside_a_git_repo(self, tmp_path):
        result = subprocess.run(
            ["bash", str(HOOK)], cwd=tmp_path, input="", capture_output=True, text=True
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_too_little_code_to_be_worth_a_graph(self, tmp_path):
        # No marker either: a repository that later grows code should still get
        # its one offer.
        small = make_repo(tmp_path / "small", code_files=5)
        assert run_hook(small).stdout.strip() == ""
        assert not (small / ".git" / MARKER).exists()

    @pytest.mark.parametrize("existing", [".code-review-graph/x", ".graphify/graph.json"])
    def test_a_repo_that_already_has_a_graph(self, tmp_path, existing):
        # That repository has already answered; asking again is noise.
        r = make_repo(tmp_path / f"r{hash(existing) & 0xFF}", code_files=25)
        target = r / existing
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("{}")
        assert run_hook(r).stdout.strip() == ""
        assert not (r / ".git" / MARKER).exists()

"""Tests for runtime/hooks/graph-offer.sh.

The hook tells a session that this project has no code graph, once, and lets
the user decide. Everything worth pinning down is a boundary: it must stay
silent where a graph exists or where there is nothing to parse, it must never
ask a second time — the marker is written when the offer is emitted, so
ignoring the prompt is itself a durable answer — and it must name `graph-init`
rather than re-explain the procedure, which is the whole point of that script.

The non-git cases are here because using git as a proxy for "can be graphed"
was wrong: both builders walk a plain directory fine, so a container mount like
/workspace was skipped for no reason, silently.
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


def write_code(path: Path, count: int) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        (path / f"mod{i}.py").write_text("x = 1\n")
    return path


def make_repo(path: Path, code_files: int) -> Path:
    write_code(path, code_files)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    if code_files:
        subprocess.run(["git", "add", "-A"], cwd=path, check=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
            cwd=path,
            check=True,
        )
    return path


def run_hook(cwd: Path, out_dir: str = ".graphify", home: Path | None = None):
    env = {**os.environ, "GRAPHIFY_OUT": out_dir}
    if home is not None:
        env["HOME"] = str(home)
    return subprocess.run(
        ["bash", str(HOOK)], cwd=cwd, env=env, input="", capture_output=True, text=True
    )


def context(result) -> str:
    return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]


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

    def test_the_offer_names_one_verb_and_not_a_procedure(self, repo):
        # The regression this guards: the offer used to spell out the exclusion
        # copy, both build commands and the verification query as prose, which
        # every session re-derived and every new user performed by hand. All of
        # that now lives in graph-init, so the hook names it and stops.
        ctx = context(run_hook(repo))
        assert "graph-init" in ctx
        assert "code-review-graph build" not in ctx
        assert "cp ~/claudebase/templates" not in ctx

    def test_the_offer_names_the_way_out(self, repo):
        # An unverified graph is the failure this whole hook exists to avoid:
        # the guards force consultation of whatever got built, so the offer has
        # to say that a bad result is deletable and how.
        ctx = context(run_hook(repo))
        assert "graph-init --purge" in ctx
        assert "vendored" in ctx

    def test_it_asks_only_once_per_repo(self, repo):
        assert run_hook(repo).stdout.strip()
        assert (repo / ".git" / MARKER).exists()
        # Second session: silent, whatever the user did or did not answer.
        assert run_hook(repo).stdout.strip() == ""


class TestWithoutGit:
    def test_a_plain_directory_with_code_is_offered_one(self, tmp_path):
        # /workspace in a container: no git, real code, both builders handle it.
        proj = write_code(tmp_path / "workspace", 25)
        home = tmp_path / "home"
        home.mkdir()

        assert "graph-init" in context(run_hook(proj, home=home))
        # The marker must not land in the user's working tree.
        assert not list(proj.glob(".claudebase*"))
        assert list((home / ".claude" / "graph-offered").iterdir())

    def test_it_still_asks_only_once(self, tmp_path):
        proj = write_code(tmp_path / "workspace", 25)
        home = tmp_path / "home"
        home.mkdir()

        assert run_hook(proj, home=home).stdout.strip()
        assert run_hook(proj, home=home).stdout.strip() == ""

    def test_home_itself_is_refused(self, tmp_path):
        # Without a git toplevel there is nothing bounding "here", and offering
        # to graph $HOME invites a walk of the whole machine.
        home = write_code(tmp_path / "home", 25)
        assert run_hook(home, home=home).stdout.strip() == ""


class TestSilence:
    @pytest.mark.parametrize("git", [True, False])
    def test_too_little_code_to_be_worth_a_graph(self, tmp_path, git):
        # No marker either: a project that later grows code should still get
        # its one offer.
        home = tmp_path / "home"
        home.mkdir()
        small = tmp_path / "small"
        make_repo(small, code_files=5) if git else write_code(small, 5)

        assert run_hook(small, home=home).stdout.strip() == ""
        if git:
            assert not (small / ".git" / MARKER).exists()
        else:
            assert not (home / ".claude" / "graph-offered").exists()

    @pytest.mark.parametrize("existing", [".code-review-graph/x", ".graphify/graph.json"])
    def test_a_repo_that_already_has_a_graph(self, tmp_path, existing):
        # That project has already answered; asking again is noise.
        r = make_repo(tmp_path / f"r{hash(existing) & 0xFF}", code_files=25)
        target = r / existing
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("{}")
        assert run_hook(r).stdout.strip() == ""
        assert not (r / ".git" / MARKER).exists()

"""Tests for runtime/bin/graph-init.sh.

graph-init is the verb graph-offer.sh points at: write the exclusion files,
run both free tree-sitter builds, and judge the result. The judgement is the
part worth pinning down — a graph made of somebody else's vendored tree is
worse than no graph, because the PreToolUse guards then force every session to
consult it, and the original failure mode was that nothing said so.

These build real graphs, so they skip where neither CLI is installed.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "runtime" / "bin" / "graph-init.sh"


def which(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    local = Path.home() / ".local" / "bin" / name
    return str(local) if os.access(local, os.X_OK) else None


pytestmark = pytest.mark.skipif(
    not which("code-review-graph") and not which("graphify"),
    reason="neither code-review-graph nor graphify is installed",
)


def write_code(path: Path, count: int, prefix: str = "m") -> Path:
    path.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        (path / f"{prefix}{i}.py").write_text(f"def {prefix}{i}():\n    return {i}\n")
    return path


def run(cwd: Path, *args: str, home: Path | None = None):
    env = {**os.environ, "GRAPHIFY_OUT": ".graphify"}
    if home is not None:
        env["HOME"] = str(home)
    return subprocess.run(
        ["bash", str(SCRIPT), *args], cwd=cwd, env=env, capture_output=True, text=True
    )


@pytest.fixture
def project(tmp_path):
    write_code(tmp_path / "proj" / "src", 20)
    return tmp_path / "proj"


class TestBuild:
    def test_a_plain_directory_gets_graphs_and_exclusions(self, project):
        # No git anywhere here: CRG falls back to an rglob walk and graphify
        # never needed git, so a container mount is a legitimate target.
        result = run(project)

        assert result.returncode == 0, result.stdout + result.stderr
        assert (project / ".graphifyignore").exists()
        assert (project / ".code-review-graphignore").exists()
        built = [p for p in (".code-review-graph", ".graphify") if (project / p).exists()]
        assert built, result.stdout

    def test_exclusions_are_written_before_the_builds(self, project):
        # Order is load-bearing for graphify: an exclusion added after the fact
        # does not refund extraction already paid for.
        lines = run(project).stdout.splitlines()
        seeded = next(i for i, l in enumerate(lines) if "graphifyignore" in l)
        built = next(i for i, l in enumerate(lines) if "완료" in l)
        assert seeded < built

    def test_an_existing_exclusion_file_is_left_alone(self, project):
        (project / ".graphifyignore").write_text("# mine\nsrc/\n")
        run(project)
        assert (project / ".graphifyignore").read_text() == "# mine\nsrc/\n"


class TestVerdict:
    def test_a_graph_made_of_vendored_code_fails(self, tmp_path):
        # The measured failure: one vault's graph was 21,865 nodes of bundled
        # plugin JS and 0 of its own, with no error anywhere.
        proj = tmp_path / "vendored"
        write_code(proj / "src", 3)
        write_code(proj / "third_party", 30, prefix="v")

        result = run(proj)

        assert result.returncode == 2, result.stdout
        assert "vendored" in result.stdout
        assert "third_party" in result.stdout
        assert "--purge" in result.stdout


class TestPurge:
    def test_purge_removes_graphs_and_keeps_exclusions(self, project):
        run(project)
        result = run(project, "--purge")

        assert result.returncode == 0
        assert not (project / ".code-review-graph").exists()
        assert not (project / ".graphify").exists()
        # Those files may have been hand-edited; deleting them is not our call.
        assert (project / ".graphifyignore").exists()

    def test_purge_on_a_clean_directory_is_not_an_error(self, project):
        assert run(project, "--purge").returncode == 0


class TestRefusal:
    def test_it_refuses_home(self, tmp_path):
        home = tmp_path / "home"
        write_code(home, 20)
        result = run(home, home=home)

        assert result.returncode != 0
        assert "refusing" in result.stderr
        assert not (home / ".code-review-graph").exists()

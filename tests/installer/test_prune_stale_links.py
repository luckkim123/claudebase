"""Tests for prune_stale_links in installer/lib/link.sh.

The regression: link_or_copy only ever adds. A skill deleted from
runtime/skills/ left ~/.claude/skills/<name> pointing at nothing, forever —
5 such links had accumulated by 2026-08-10, and a third-party tool walking the
directory died on ENOENT rather than skipping them.

What must NOT regress is the other side: the per-item linking exists so
user-managed entries survive an install, and a prune that reaches past its own
links would undo exactly that. Hence the bulk of these tests pin down what
prune leaves alone.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LINK_SH = REPO_ROOT / "installer" / "lib" / "link.sh"


def run_prune(tmp_path: Path, dry_run: int = 0) -> tuple[str, Path, Path]:
    """Source link.sh in a sandbox and run prune_stale_links against it.

    Returns (stdout, claude_home, repo_dir). The sandbox supplies the same
    globals install.sh does — REPO_DIR, CLAUDE_HOME, DRY_RUN — plus the log/run
    primitives from lib/log.sh's contract, kept minimal on purpose so a failure
    here points at prune and not at the logger.
    """
    claude_home = tmp_path / "claude_home"
    repo_dir = tmp_path / "repo"
    script = f"""
    set -euo pipefail
    REPO_DIR={repo_dir!s}
    CLAUDE_HOME={claude_home!s}
    DRY_RUN={dry_run}
    log()   {{ printf '[install] %s\\n' "$*"; }}
    debug() {{ :; }}
    run()   {{ if [[ $DRY_RUN -eq 1 ]]; then printf 'would: %s\\n' "$*"; else "$@"; fi; }}
    source {LINK_SH!s}
    prune_stale_links
    """
    out = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, check=True
    )
    return out.stdout, claude_home, repo_dir


def make_link(claude_home: Path, kind: str, name: str, target: Path) -> Path:
    d = claude_home / kind
    d.mkdir(parents=True, exist_ok=True)
    link = d / name
    link.symlink_to(target)
    return link


class TestPrunes:
    def test_removes_link_into_repo_whose_source_is_gone(self, tmp_path):
        home = tmp_path / "claude_home"
        repo = tmp_path / "repo"
        link = make_link(home, "skills", "docker-env", repo / "runtime/skills/docker-env")
        assert link.is_symlink()
        out, _, _ = run_prune(tmp_path)
        assert not link.is_symlink(), "dangling repo link should be pruned"
        assert "pruned:" in out

    @pytest.mark.parametrize("kind", ["skills", "agents", "output-styles"])
    def test_covers_every_linked_directory(self, tmp_path, kind):
        home = tmp_path / "claude_home"
        repo = tmp_path / "repo"
        link = make_link(home, kind, "gone", repo / f"runtime/{kind}/gone")
        run_prune(tmp_path)
        assert not link.is_symlink(), f"{kind} should be pruned too"


class TestLeavesAlone:
    def test_keeps_live_link(self, tmp_path):
        home = tmp_path / "claude_home"
        repo = tmp_path / "repo"
        src = repo / "runtime/skills/changelog"
        src.mkdir(parents=True)
        link = make_link(home, "skills", "changelog", src)
        run_prune(tmp_path)
        assert link.is_symlink() and link.exists(), "live link must survive"

    def test_keeps_user_owned_real_directory(self, tmp_path):
        home = tmp_path / "claude_home"
        (home / "skills" / "my-own").mkdir(parents=True)
        run_prune(tmp_path)
        assert (home / "skills" / "my-own").is_dir(), "user's own skill must survive"

    def test_keeps_dangling_link_pointing_outside_the_repo(self, tmp_path):
        # The whole safety argument: we only clean up after ourselves. A broken
        # link the user made elsewhere is theirs to fix, not ours to delete.
        home = tmp_path / "claude_home"
        link = make_link(home, "skills", "elsewhere", tmp_path / "somewhere-else/x")
        run_prune(tmp_path)
        assert link.is_symlink(), "foreign dangling link must not be touched"

    def test_repo_path_prefix_is_not_a_substring_match(self, tmp_path):
        # /repo-other/... starts with the same characters as /repo but is a
        # different tree; a naive prefix test would delete from it.
        home = tmp_path / "claude_home"
        repo = tmp_path / "repo"
        link = make_link(home, "skills", "sneaky", Path(f"{repo}-other") / "skills/x")
        run_prune(tmp_path)
        assert link.is_symlink(), "sibling path sharing a prefix must not be pruned"


class TestIdempotencyContract:
    def test_silent_when_nothing_is_stale(self, tmp_path):
        # tests/smoke/test_install_idempotent.sh asserts a second run prints
        # nothing; prune must not narrate work it did not do.
        home = tmp_path / "claude_home"
        repo = tmp_path / "repo"
        src = repo / "runtime/skills/changelog"
        src.mkdir(parents=True)
        make_link(home, "skills", "changelog", src)
        out, _, _ = run_prune(tmp_path)
        assert out.strip() == "", f"expected silence, got: {out!r}"

    def test_empty_and_missing_directories_are_no_ops(self, tmp_path):
        home = tmp_path / "claude_home"
        (home / "skills").mkdir(parents=True)  # empty; agents/ absent entirely
        out, _, _ = run_prune(tmp_path)
        assert out.strip() == ""

    def test_dry_run_reports_without_deleting(self, tmp_path):
        home = tmp_path / "claude_home"
        repo = tmp_path / "repo"
        link = make_link(home, "skills", "gone", repo / "runtime/skills/gone")
        out, _, _ = run_prune(tmp_path, dry_run=1)
        assert link.is_symlink(), "--dry-run must not delete"
        assert "would:" in out

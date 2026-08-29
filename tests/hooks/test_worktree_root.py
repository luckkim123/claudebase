"""The linked-worktree correction shared by the three graph scripts.

Why it exists: every index those scripts touch is gitignored
(`.graphify/`), so `git worktree
add` never copies one. In a linked worktree `git rev-parse --show-toplevel`
therefore names a checkout that holds no graph, while the real graphs sit in the
main checkout and go stale — and nothing errors, because an empty index answers
queries with "not found" exactly like a healthy one does.

The trap this pins down is the fix's own failure mode: comparing the two git
dirs as RAW STRINGS reports a worktree where there is none. From a subdirectory
of an ordinary main checkout git prints an absolute `--git-dir` and a still
relative `--git-common-dir`, so the strings differ. Absolutising both is what
makes the branch fire only for real worktrees — and it is also what keeps
`--separate-git-dir` working, since there both values resolve to the same
external directory and the branch is skipped.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

SCRIPTS = (
    REPO_ROOT / "runtime" / "hooks" / "graph-refresh.sh",
    REPO_ROOT / "runtime" / "hooks" / "graph-offer.sh",
    REPO_ROOT / "runtime" / "bin" / "graph-init.sh",
)

# The five lines every copy must carry verbatim. Asserting on them is what stops
# one script quietly drifting back to `--show-toplevel` while the others move on.
OPERATIVE = (
    '_gd="$(git rev-parse --git-dir 2>/dev/null)" || _gd=""',
    '_gc="$(git rev-parse --git-common-dir 2>/dev/null)" || _gc=""',
    '[ -n "$_gd" ] && _gd="$(cd "$_gd" 2>/dev/null && pwd)"',
    '[ -n "$_gc" ] && _gc="$(cd "$_gc" 2>/dev/null && pwd)"',
    'if [ -n "$_gc" ] && [ "$_gd" != "$_gc" ]; then',
)

# The same logic the scripts run, reduced to printing what it resolved to.
SNIPPET = """
set -u
repo="$(git rev-parse --show-toplevel 2>/dev/null)" || repo=""
_gd="$(git rev-parse --git-dir 2>/dev/null)" || _gd=""
_gc="$(git rev-parse --git-common-dir 2>/dev/null)" || _gc=""
[ -n "$_gd" ] && _gd="$(cd "$_gd" 2>/dev/null && pwd)"
[ -n "$_gc" ] && _gc="$(cd "$_gc" 2>/dev/null && pwd)"
if [ -n "$_gc" ] && [ "$_gd" != "$_gc" ]; then
  repo="$(cd "$_gc/.." 2>/dev/null && pwd)" || repo=""
fi
printf '%s' "$repo"
"""


def git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def resolve(cwd: Path) -> str:
    return subprocess.run(
        ["bash", "-c", SNIPPET], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


@pytest.fixture
def repo_with_worktree(tmp_path):
    """A main checkout with one commit, a subdirectory, and a linked worktree."""
    main = tmp_path / "main"
    main.mkdir()
    git(main, "init", "-q", "-b", "main")
    (main / "sub").mkdir()
    (main / "sub" / "f.txt").write_text("x")
    git(main, "add", "-A")
    git(main, "commit", "-qm", "init")

    linked = tmp_path / "linked"
    git(main, "worktree", "add", "-q", "-b", "side", str(linked))
    (linked / "sub").mkdir(exist_ok=True)
    return main.resolve(), linked.resolve()


class TestResolution:
    def test_main_checkout_resolves_to_itself(self, repo_with_worktree):
        main, _ = repo_with_worktree
        assert resolve(main) == str(main)

    def test_main_checkout_subdirectory_is_not_mistaken_for_a_worktree(
        self, repo_with_worktree
    ):
        # The whole reason both values are absolutised: the raw strings here are
        # "/abs/main/.git" and "../.git", which differ.
        main, _ = repo_with_worktree
        assert resolve(main / "sub") == str(main)

    def test_linked_worktree_resolves_to_the_main_checkout(self, repo_with_worktree):
        main, linked = repo_with_worktree
        assert resolve(linked) == str(main)
        # ...and the uncorrected answer is exactly what it must not return.
        assert resolve(linked) != str(linked)

    def test_linked_worktree_subdirectory_resolves_to_the_main_checkout(
        self, repo_with_worktree
    ):
        main, linked = repo_with_worktree
        assert resolve(linked / "sub") == str(main)

    def test_outside_a_repo_resolves_to_nothing(self, tmp_path):
        # Load-bearing: an unguarded `cd "/.."` would silently yield "/", and the
        # callers would then treat the whole filesystem as the project.
        plain = tmp_path / "plain"
        plain.mkdir()
        assert resolve(plain) == ""


class TestScriptsCarryTheCorrection:
    @pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
    def test_operative_lines_present(self, script):
        text = script.read_text(encoding="utf-8")
        missing = [line for line in OPERATIVE if line not in text]
        assert not missing, f"{script.name} is missing: {missing}"

    @pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
    def test_still_starts_from_show_toplevel(self, script):
        # The correction is a strict superset, not a replacement: outside a
        # worktree the toplevel form is what answers, and it is the form that
        # handles --separate-git-dir.
        assert "--show-toplevel" in script.read_text(encoding="utf-8")

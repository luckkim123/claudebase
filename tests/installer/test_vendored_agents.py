"""Contract tests for the vendored agents under runtime/agents/.

These files are not ours — they come from Everything Claude Code (MIT) and were
edited locally. Two things can silently break, and both look like success:

1. A dispatch to an agent that is not installed. `mle-reviewer` upstream names
   twelve sibling ECC agents; ten are not here. A subagent told to "use
   `silent-failure-hunter`" simply does not run that lane, and a lane that never
   ran is indistinguishable from a lane that found nothing.
2. A stray non-agent file in the directory. `link_skills_and_agents` symlinks
   every `*.md` in runtime/agents/ into ~/.claude/agents/, so a NOTICE or README
   dropped there would be published to Claude Code as an agent. That is why the
   attribution lives in docs/ instead.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_DIR = REPO_ROOT / "runtime" / "agents"
AGENTS = sorted(AGENT_DIR.glob("*.md"))

# Agent names this machine can actually dispatch, beyond the vendored files:
# the OMC plugin's catalog, which the local mle-reviewer edit re-points at.
OMC_AGENTS = {
    "oh-my-claudecode:analyst",
    "oh-my-claudecode:architect",
    "oh-my-claudecode:code-reviewer",
    "oh-my-claudecode:code-simplifier",
    "oh-my-claudecode:critic",
    "oh-my-claudecode:debugger",
    "oh-my-claudecode:designer",
    "oh-my-claudecode:document-specialist",
    "oh-my-claudecode:executor",
    "oh-my-claudecode:explore",
    "oh-my-claudecode:git-master",
    "oh-my-claudecode:planner",
    "oh-my-claudecode:qa-tester",
    "oh-my-claudecode:scientist",
    "oh-my-claudecode:security-reviewer",
    "oh-my-claudecode:test-engineer",
    "oh-my-claudecode:tracer",
    "oh-my-claudecode:verifier",
    "oh-my-claudecode:writer",
}


def frontmatter(path: Path) -> dict[str, str]:
    m = re.match(r"---\n(.*?)\n---\n", path.read_text(encoding="utf-8"), re.S)
    if not m:
        return {}
    return dict(re.findall(r"^([a-z_]+):\s*(.+)$", m.group(1), re.M))


def test_directory_is_not_empty():
    # link_skills_and_agents skips a missing/empty dir silently — the state this
    # repo was in before 2026-08-10, when the linking code existed but had
    # nothing to link.
    assert AGENTS, "runtime/agents/ has no agents; the linking stage is a no-op"


@pytest.mark.parametrize("path", AGENTS, ids=lambda p: p.stem)
class TestAgentFile:
    def test_has_required_frontmatter(self, path):
        fm = frontmatter(path)
        assert fm.get("name"), f"{path.name}: no name field"
        assert fm.get("description"), f"{path.name}: no description field"

    def test_name_matches_filename(self, path):
        # Claude Code dispatches on the `name` field; a mismatch makes the file
        # reachable under a name nobody would guess from the directory listing.
        assert frontmatter(path)["name"] == path.stem

    def test_carries_attribution(self, path):
        # MIT requires the notice to travel with the copy.
        assert "Everything Claude Code" in path.read_text(encoding="utf-8"), (
            f"{path.name}: vendored file lost its provenance comment"
        )

    def test_every_dispatch_resolves(self, path):
        # Only the "reuse these lanes" prose dispatches agents. Scanning the
        # whole file would also catch code advice — cpp-reviewer says
        # "Use `std::ostringstream`", which is not a subagent. Agent names are
        # hyphenated lowercase with at most one colon, so `::` cannot match, and
        # a name is only a dispatch if it is already known to be an agent.
        known = {p.stem for p in AGENTS} | OMC_AGENTS
        candidates = set(
            re.findall(r"Use `([a-z0-9-]+(?::[a-z0-9-]+)?)`", path.read_text(encoding="utf-8"))
        )
        # An unknown single word is code advice, not a broken dispatch; what we
        # are hunting is a name that LOOKS like an ECC agent and is not here.
        dispatched = {c for c in candidates if c.endswith(("-reviewer", "-resolver", "-hunter",
                                                           "-analyzer", "-optimizer", "-architect",
                                                           "-runner", "-updater", "-forker",
                                                           "-packager", "-sanitizer"))
                      or ":" in c}
        assert dispatched <= known, (
            f"{path.name} dispatches agents that are not installed: "
            f"{sorted(dispatched - known)}"
        )


def test_no_non_agent_markdown_in_the_directory():
    # Everything here is symlinked into ~/.claude/agents/ as an agent, so a
    # NOTICE/README here would be published as one. Attribution lives in docs/.
    for path in AGENTS:
        assert frontmatter(path), (
            f"{path.name} has no frontmatter — it is not an agent, and "
            f"link_skills_and_agents will publish it as one anyway"
        )


def test_attribution_doc_exists_and_lists_every_agent():
    doc = REPO_ROOT / "docs" / "third-party-agents.md"
    assert doc.is_file(), "docs/third-party-agents.md is missing"
    text = doc.read_text(encoding="utf-8")
    for path in AGENTS:
        assert path.stem in text, f"{path.stem} is vendored but not in the NOTICE"

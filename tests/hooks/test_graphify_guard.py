"""Tests for runtime/hooks/graphify-guard.sh.

The hook wraps `graphify hook-guard` so the agent is routed through the code
graph before it reads or greps. What is pinned here is the wrapper's own
contribution, not graphify's: the nudge text graphify emits hardcodes the
literal `graphify-out/graph.json` (cli.py:22,32,46) even where GRAPHIFY_OUT has
moved the output tree elsewhere, so on every claudebase machine — which sets
GRAPHIFY_OUT=.graphify — the agent was handed a MANDATORY instruction naming a
file that does not exist. The wrapper rewrites that path on the way out.

Rewriting means the wrapper can no longer `exec`, so the three guarantees that
`exec` used to give for free are pinned too: graphify's exit code survives (a
`--strict` install must still be able to block), stdin reaches graphify intact,
and a machine that never relocated its output tree sees byte-identical text.

A stub graphify stands in for the real one so the assertions are about the
wrapper's logic rather than graphify's decision of when to speak at all.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / "runtime" / "hooks" / "graphify-guard.sh"

# Verbatim from graphify 0.9.39 (cli.py:32) — the string the wrapper repairs.
NUDGE = (
    "MANDATORY: graphify-out/graph.json exists. You MUST run graphify before "
    "reading source files."
)
STUB_REPLY = json.dumps(
    {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": NUDGE}},
    separators=(",", ":"),
)
PAYLOAD = json.dumps(
    {"tool_name": "Read", "tool_input": {"file_path": "/synthetic/project/mod.py"}}
)


@pytest.fixture
def sandbox(tmp_path: Path):
    """A project dir plus a stub `graphify` that echoes the canned nudge."""
    bin_dir, repo = tmp_path / "bin", tmp_path / "repo"
    bin_dir.mkdir()
    repo.mkdir()
    stdin_log = tmp_path / "stdin.txt"

    stub = bin_dir / "graphify"
    stub.write_text(
        "#!/bin/sh\n"
        f'cat > "{stdin_log}"\n'
        f"cat <<'GFYEOF'\n{STUB_REPLY}\nGFYEOF\n"
        'exit "${STUB_EXIT:-0}"\n'
    )
    stub.chmod(0o755)
    return repo, bin_dir, stdin_log


def run_hook(repo: Path, bin_dir: Path, out_dir: str, mode: str = "read", **env_extra):
    """Invoke the hook with a graph present at <repo>/<out_dir>/graph.json."""
    graph = repo / out_dir / "graph.json"
    graph.parent.mkdir(parents=True, exist_ok=True)
    graph.write_text('{"nodes":[],"links":[]}')
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "GRAPHIFY_OUT": out_dir,
        **env_extra,
    }
    return subprocess.run(
        ["bash", str(HOOK), mode],
        cwd=repo,
        env=env,
        input=PAYLOAD,
        capture_output=True,
        text=True,
    )


def test_relocated_output_tree_is_named_in_the_nudge(sandbox):
    """The agent must be pointed at the graph that exists, not the default name."""
    repo, bin_dir, _ = sandbox
    result = run_hook(repo, bin_dir, ".graphify")

    assert ".graphify/graph.json" in result.stdout
    assert "graphify-out/graph.json" not in result.stdout


def test_rewritten_output_is_still_valid_hook_json(sandbox):
    """Claude Code parses this; a substitution that broke the JSON would be silent."""
    repo, bin_dir, _ = sandbox
    result = run_hook(repo, bin_dir, ".graphify")

    parsed = json.loads(result.stdout)
    assert parsed["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert ".graphify/graph.json" in parsed["hookSpecificOutput"]["additionalContext"]


def test_default_output_tree_is_left_byte_identical(sandbox):
    """A machine that never relocated its tree must see exactly what it saw before."""
    repo, bin_dir, _ = sandbox
    result = run_hook(repo, bin_dir, "graphify-out")

    assert json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"] == NUDGE


def test_graphify_exit_code_survives_the_wrapper(sandbox):
    """`exec` used to guarantee this; a --strict install still needs it to block."""
    repo, bin_dir, _ = sandbox
    result = run_hook(repo, bin_dir, ".graphify", STUB_EXIT="2")

    assert result.returncode == 2


def test_stdin_reaches_graphify_unchanged(sandbox):
    """The hook payload is graphify's only input; capturing output must not eat it."""
    repo, bin_dir, stdin_log = sandbox
    run_hook(repo, bin_dir, ".graphify")

    assert stdin_log.read_text() == PAYLOAD

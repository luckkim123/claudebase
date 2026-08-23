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
        # STUB_SILENT stands in for "graphify found no graph here and said
        # nothing" — the one case the latch must NOT arm on.
        '[ -n "${STUB_SILENT:-}" ] || '
        f"cat <<'GFYEOF'\n{STUB_REPLY}\nGFYEOF\n"
        'exit "${STUB_EXIT:-0}"\n'
    )
    stub.chmod(0o755)
    return repo, bin_dir, stdin_log


def _payload(session_id: str | None = None) -> str:
    """PAYLOAD, optionally carrying the session_id the once-per-session latch keys on."""
    d = json.loads(PAYLOAD)
    if session_id:
        d["session_id"] = session_id
    return json.dumps(d)


def run_hook(repo: Path, bin_dir: Path, out_dir: str, mode: str = "read",
             payload: str = PAYLOAD, **env_extra):
    """Invoke the hook with a graph present at <repo>/<out_dir>/graph.json."""
    graph = repo / out_dir / "graph.json"
    graph.parent.mkdir(parents=True, exist_ok=True)
    graph.write_text('{"nodes":[],"links":[]}')
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "GRAPHIFY_OUT": out_dir,
        # Keep every latch file inside the test's own tmp dir — a shared /tmp
        # would let one test silence the next.
        "TMPDIR": str(repo.parent),
        **env_extra,
    }
    return subprocess.run(
        ["bash", str(HOOK), mode],
        cwd=repo,
        env=env,
        input=payload,
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


# --- once-per-session latch (2026-08-23) -------------------------------------
# graphify's nudge is byte-identical on every call and the wrapper emitted it on
# EVERY matching tool call, unbounded. Measured on the obsidian vault: 397 chars
# per Read/Glob, 187 per Bash/Grep, ~5,000 chars in a single 20-tool turn —
# more than the omha (3,118) and omp (1,593) prompt injections combined. The
# first nudge is the one that can still change the plan; the rest are a tax.


def test_second_call_in_a_session_is_silent(sandbox):
    """The nudge lands once. A repeat says nothing new, so it says nothing."""
    repo, bin_dir, _ = sandbox
    p = _payload("sess-A")

    first = run_hook(repo, bin_dir, ".graphify", payload=p)
    second = run_hook(repo, bin_dir, ".graphify", payload=p)

    assert first.stdout.strip(), "the first call must still nudge"
    assert second.stdout.strip() == "", "a repeat within one session must be silent"
    assert second.returncode == 0


def test_a_new_session_is_nudged_again(sandbox):
    """The latch is keyed on session_id, so it cannot outlive its session."""
    repo, bin_dir, _ = sandbox
    run_hook(repo, bin_dir, ".graphify", payload=_payload("sess-A"))
    fresh = run_hook(repo, bin_dir, ".graphify", payload=_payload("sess-B"))

    assert ".graphify/graph.json" in fresh.stdout


def test_missing_session_id_keeps_the_old_unlatched_behaviour(sandbox):
    """No session_id (older Claude Code, or a hand-run call) → fail toward today."""
    repo, bin_dir, _ = sandbox
    first = run_hook(repo, bin_dir, ".graphify")
    second = run_hook(repo, bin_dir, ".graphify")

    assert first.stdout.strip()
    assert second.stdout.strip(), "without a session_id the guard must not go quiet"


def test_search_and_read_latch_independently(sandbox):
    """They carry different text and answer different tool families."""
    repo, bin_dir, _ = sandbox
    p = _payload("sess-A")

    run_hook(repo, bin_dir, ".graphify", mode="read", payload=p)
    search = run_hook(repo, bin_dir, ".graphify", mode="search", payload=p)

    assert search.stdout.strip(), "latching read must not silence search"


def test_a_silent_guard_never_arms_the_latch(sandbox):
    """Load-bearing: a session that starts outside a graph must still get its
    first nudge after cd-ing into one. Arming on a no-output call would mute it
    permanently — and silently, which is the failure mode that costs most."""
    repo, bin_dir, _ = sandbox
    p = _payload("sess-A")

    quiet = run_hook(repo, bin_dir, ".graphify", payload=p, STUB_SILENT="1")
    later = run_hook(repo, bin_dir, ".graphify", payload=p)

    assert quiet.stdout.strip() == ""
    assert ".graphify/graph.json" in later.stdout, "the latch armed on an empty nudge"

"""Tests for runtime/hooks/session-gate.py.

Every call runs the hook as its own process, because the defect these tests pin
only exists between processes: Claude Code spawns one hook process per tool call,
and parallel tool calls share one state file.

2026-09-14 (albc session): the gate kept denying after both required documents
had been Read. `_save_state` truncated the file before writing it, and the allow
path re-saved on every call — so a concurrent call could read the empty file,
and an out-of-scope one would then save that empty set back over the record.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / "runtime" / "hooks" / "session-gate.py"

CONFIG = {
    "name": "t",
    "scope": ["proj/sub/"],
    "require_read": [
        {"id": "brief", "path": "sub/brief.md", "hint": "h"},
        {"id": "card", "path": "SKILL.md", "hint": "h"},
    ],
    "gates": [{"id": "toc", "match": r"^grep -n .* PLAN\.md", "hint": "grep toc"}],
    "block": [r"\brosnode kill\b"],
}


@pytest.fixture()
def env(tmp_path):
    proj = tmp_path / "proj"
    (proj / ".claude").mkdir(parents=True)
    (proj / ".claude" / "session-gate.json").write_text(json.dumps(CONFIG), encoding="utf-8")
    (tmp_path / "tmpdir").mkdir()
    e = {k: v for k, v in os.environ.items() if k != "SESSION_GATE"}
    e["TMPDIR"] = str(tmp_path / "tmpdir")        # where the state file lands
    e["HOOKLOG_ROOT"] = str(tmp_path / "logs")    # keep telemetry out of the repo
    return {"env": e, "cwd": str(proj), "tmpdir": tmp_path / "tmpdir"}


def _run(env, tool_name, tool_input, sid="s", cwd=None):
    payload = {"tool_name": tool_name, "tool_input": tool_input,
               "cwd": cwd or env["cwd"], "session_id": sid}
    p = subprocess.run([sys.executable, str(HOOK_PATH)], input=json.dumps(payload),
                       capture_output=True, text=True, env=env["env"], timeout=30)
    assert p.returncode == 0, p.stderr
    return p.stdout


def _denied(out):
    return bool(out) and json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"


def _state(env, sid="s"):
    return set(json.loads((env["tmpdir"] / ("session-gate-%s.json" % sid)).read_text()))


def _read(path):
    return {"file_path": path}


def _bash(cmd):
    return {"command": cmd}


BRIEF = "/x/proj/sub/brief.md"
CARD = "/x/skills/rules/SKILL.md"
IN_SCOPE = "ls proj/sub/data"
OUT_OF_SCOPE = "ls proj/sub"   # no trailing slash: the substring match misses it


# --- regression: the gate's contract ------------------------------------------

def test_unread_documents_deny_acting_in_scope(env):
    assert _denied(_run(env, "Bash", _bash(IN_SCOPE)))
    assert _denied(_run(env, "Edit", {"file_path": "/x/proj/sub/a.py"}))


def test_reading_both_documents_opens_the_gate(env):
    _run(env, "Read", _read(BRIEF))
    assert _denied(_run(env, "Bash", _bash(IN_SCOPE)))  # one of two is not enough
    _run(env, "Read", _read(CARD))
    assert not _denied(_run(env, "Bash", _bash(IN_SCOPE)))
    assert _state(env) == {"read:brief", "read:card"}


def test_out_of_scope_is_never_gated(env):
    assert not _denied(_run(env, "Bash", _bash("ls /etc")))


def test_block_command_needs_its_gate_first(env):
    for p in (BRIEF, CARD):
        _run(env, "Read", _read(p))
    assert _denied(_run(env, "Bash", _bash("rosnode kill /x")))
    assert not _denied(_run(env, "Bash", _bash("grep -n '^## ' PLAN.md")))
    assert not _denied(_run(env, "Bash", _bash("rosnode kill /x")))


def test_no_config_is_a_noop(env, tmp_path):
    bare = tmp_path / "bare"
    bare.mkdir()
    assert _run(env, "Bash", _bash("ls proj/sub/data"), cwd=str(bare)) == ""


def test_bypass_env(env):
    env["env"]["SESSION_GATE"] = "off"
    assert _run(env, "Bash", _bash(IN_SCOPE)) == ""


# --- the race: parallel tool calls share one state file ------------------------

def test_parallel_required_reads_both_survive(env):
    """(a) Two required-document Reads fired together must both be recorded."""
    with ThreadPoolExecutor(max_workers=2) as pool:
        for i in range(50):
            sid = "a%d" % i
            list(pool.map(lambda p: _run(env, "Read", _read(p), sid=sid), (BRIEF, CARD)))
            assert _state(env, sid) == {"read:brief", "read:card"}, "round %d lost a read" % i


def test_parallel_calls_neither_erase_nor_falsely_deny(env):
    """(b) Once both are read, a burst of in- and out-of-scope calls keeps the record."""
    for p in (BRIEF, CARD):
        _run(env, "Read", _read(p))
    calls = [OUT_OF_SCOPE, IN_SCOPE] * 20
    with ThreadPoolExecutor(max_workers=len(calls)) as pool:
        for rnd in range(5):
            outs = list(pool.map(lambda c: (c, _run(env, "Bash", _bash(c))), calls))
            denied = [c for c, o in outs if _denied(o)]
            assert not denied, "round %d: %d in-scope calls denied" % (rnd, len(denied))
            assert _state(env) == {"read:brief", "read:card"}, "round %d erased" % rnd

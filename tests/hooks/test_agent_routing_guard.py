"""Tests for runtime/hooks/agent-routing-guard.py.

The hook denies research-shaped Agent calls (BOTH an action signal AND an object
signal present) when subagent_type is not a research-suited agent, and lets every
other call pass. A `ROUTING_OK:` token in the prompt bypasses the gate.
"""
from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / "runtime" / "hooks" / "agent-routing-guard.py"


def _load_module():
    # File name contains a hyphen, so importlib over plain `import` is required.
    spec = importlib.util.spec_from_file_location("agent_routing_guard", HOOK_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(payload: dict, capsys, monkeypatch) -> tuple[int, str]:
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    mod = _load_module()
    rc = mod.main()
    out, _ = capsys.readouterr()
    return rc, out


def _agent_call(prompt: str = "", subagent_type: str = "general-purpose",
                description: str = "", **extra) -> dict:
    ti = {"prompt": prompt, "subagent_type": subagent_type, "description": description}
    ti.update(extra)
    return {"tool_name": "Agent", "tool_input": ti, "cwd": "/tmp", "session_id": "t"}


def _decision(out: str) -> dict:
    return json.loads(out)["hookSpecificOutput"]


# --- the core leak: research-shaped call to a general agent is denied ----------

def test_research_to_general_purpose_denied(capsys, monkeypatch):
    # action signal "research" + object signal "arxiv" -> research; general-purpose -> deny
    rc, out = _run(
        _agent_call(prompt="Research the EmpiricalNorm approach on arxiv and github",
                    subagent_type="general-purpose"),
        capsys, monkeypatch,
    )
    assert rc == 0
    d = _decision(out)
    assert d["hookEventName"] == "PreToolUse"
    assert d["permissionDecision"] == "deny"
    assert "non-research subagent" in d["permissionDecisionReason"]


def test_research_korean_to_general_purpose_denied(capsys, monkeypatch):
    # Korean action "조사" + object "웹"/"논문" -> research
    rc, out = _run(
        _agent_call(prompt="legged_gym obs_scales 를 외부 웹과 논문에서 조사해줘",
                    subagent_type="general-purpose"),
        capsys, monkeypatch,
    )
    assert rc == 0
    assert _decision(out)["permissionDecision"] == "deny"


def test_research_signal_in_description_denied(capsys, monkeypatch):
    # research signal can live in description, not just prompt
    rc, out = _run(
        _agent_call(description="Survey external library best practice for encoder norm",
                    prompt="see attached", subagent_type="general-purpose"),
        capsys, monkeypatch,
    )
    assert rc == 0
    assert _decision(out)["permissionDecision"] == "deny"


# --- research routed to a research agent passes -------------------------------

def test_research_to_document_specialist_passes(capsys, monkeypatch):
    rc, out = _run(
        _agent_call(prompt="Research EmpiricalNorm on arxiv and github",
                    subagent_type="oh-my-claudecode:document-specialist"),
        capsys, monkeypatch,
    )
    assert rc == 0
    assert out == ""  # no decision emitted -> normal flow allows


def test_research_to_explore_passes(capsys, monkeypatch):
    rc, out = _run(
        _agent_call(prompt="Research how the repo handles external library imports",
                    subagent_type="Explore"),
        capsys, monkeypatch,
    )
    assert rc == 0
    assert out == ""


# --- false-positive guard: a single keyword is not enough ---------------------

def test_action_signal_only_passes(capsys, monkeypatch):
    # "compare" (action) but no object signal -> not research -> allowed
    rc, out = _run(
        _agent_call(prompt="Compare these two config dataclasses in the codebase",
                    subagent_type="general-purpose"),
        capsys, monkeypatch,
    )
    assert rc == 0
    assert out == ""


def test_object_signal_only_passes(capsys, monkeypatch):
    # "library" (object) but no action signal -> not research -> allowed
    rc, out = _run(
        _agent_call(prompt="Refactor the library import in this module",
                    subagent_type="general-purpose"),
        capsys, monkeypatch,
    )
    assert rc == 0
    assert out == ""


def test_plain_code_task_passes(capsys, monkeypatch):
    rc, out = _run(
        _agent_call(prompt="Map where DR config is defined in config.py",
                    subagent_type="general-purpose"),
        capsys, monkeypatch,
    )
    assert rc == 0
    assert out == ""


# --- ROUTING_OK bypass --------------------------------------------------------

def test_routing_ok_bypass_in_prompt(capsys, monkeypatch):
    rc, out = _run(
        _agent_call(
            prompt="ROUTING_OK: keywords incidental, this is a code edit. "
                   "Research arxiv references in the docstring and fix them.",
            subagent_type="general-purpose"),
        capsys, monkeypatch,
    )
    assert rc == 0
    assert out == ""  # bypassed despite research signals


def test_routing_ok_bypass_in_description(capsys, monkeypatch):
    rc, out = _run(
        _agent_call(
            description="ROUTING_OK: not actually research",
            prompt="Survey external github repos and papers",
            subagent_type="general-purpose"),
        capsys, monkeypatch,
    )
    assert rc == 0
    assert out == ""


# --- fail-open / robustness ---------------------------------------------------

def test_non_agent_tool_passes(capsys, monkeypatch):
    rc, out = _run(
        {"tool_name": "Read", "tool_input": {"prompt": "research arxiv web"}},
        capsys, monkeypatch,
    )
    assert rc == 0
    assert out == ""


def test_task_tool_name_also_gated(capsys, monkeypatch):
    # The harness sometimes emits "Task" instead of "Agent"; gate both.
    payload = _agent_call(prompt="Research arxiv papers on the web",
                          subagent_type="general-purpose")
    payload["tool_name"] = "Task"
    rc, out = _run(payload, capsys, monkeypatch)
    assert rc == 0
    assert _decision(out)["permissionDecision"] == "deny"


def test_malformed_stdin_fails_open(capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("{not json"))
    mod = _load_module()
    rc = mod.main()
    out, _ = capsys.readouterr()
    assert rc == 0
    assert out == ""


def test_missing_tool_input_passes(capsys, monkeypatch):
    rc, out = _run({"tool_name": "Agent"}, capsys, monkeypatch)
    assert rc == 0
    assert out == ""


def test_non_string_fields_do_not_crash(capsys, monkeypatch):
    rc, out = _run(
        {"tool_name": "Agent",
         "tool_input": {"prompt": None, "description": 123, "subagent_type": []}},
        capsys, monkeypatch,
    )
    assert rc == 0
    assert out == ""


def test_unit_is_research_requires_both():
    mod = _load_module()
    assert mod._is_research("research this on arxiv") is True
    assert mod._is_research("research this") is False        # action only
    assert mod._is_research("an arxiv link") is False        # object only
    assert mod._is_research("조사 웹") is True                 # korean both

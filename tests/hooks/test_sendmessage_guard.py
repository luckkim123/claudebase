"""Tests for runtime/hooks/sendmessage-guard.py.

The hook holds back a cross-session SendMessage while a live Orca terminal on
this host is parked on a modal chooser, and allows everything else. Every probe
failure — no orca, unreachable runtime, unreadable screen — must fall through to
allow, because a guard that stops a session from talking is worse than the
deadlock it prevents.
"""
from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / "runtime" / "hooks" / "sendmessage-guard.py"

# The real footer, captured from a live chooser in a throwaway Orca terminal on
# 2026-08-23 rather than transcribed from a screenshot.
DIALOG_TAIL = [
    " 1. Alpha                        +----------------+",
    "Enter to select · ↑/↓ to navigate · n to add notes · Esc to cancel",
]
IDLE_TAIL = [
    "❯ ",
    "  dir:kimseungmin/ksm_Obsidian | branch:main | model:opus 5",
]


def _load_module():
    # File name contains a hyphen, so importlib over plain `import` is required.
    spec = importlib.util.spec_from_file_location("sendmessage_guard", HOOK_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _stub_orca(mod, monkeypatch, terminals, tails):
    """Replace the single subprocess seam so no test ever shells out to orca."""

    def fake(args):
        if args[:2] == ["terminal", "list"]:
            return {"terminals": terminals}
        if args[:2] == ["terminal", "read"]:
            return {"terminal": {"tail": tails.get(args[3], [])}}
        return None

    monkeypatch.setattr(mod, "_orca", fake)


def _term(handle="term_x", title="peer pane", **over):
    t = {"handle": handle, "title": title, "connected": True, "orphaned": False}
    t.update(over)
    return t


def _run(mod, payload, capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    rc = mod.main()
    out, _ = capsys.readouterr()
    return rc, out


def _send(message: object = "ping", **over):
    ti = {"to": "peer-session", "message": message}
    ti.update(over)
    return {"tool_name": "SendMessage", "tool_input": ti,
            "cwd": "/tmp", "session_id": "t"}


def _decision(out: str) -> dict:
    return json.loads(out)["hookSpecificOutput"]


# --- (a) a parked chooser on the host -> deny ---------------------------------

def test_parked_chooser_denies(capsys, monkeypatch, tmp_path):
    mod = _load_module()
    _stub_orca(mod, monkeypatch, [_term()], {"term_x": DIALOG_TAIL})
    payload = _send()
    payload["cwd"] = str(tmp_path)
    rc, out = _run(mod, payload, capsys, monkeypatch)
    assert rc == 0
    d = _decision(out)
    assert d["hookEventName"] == "PreToolUse"
    assert d["permissionDecision"] == "deny"
    # Title AND handle: a title alone is not distinctive (panes share a worktree,
    # and a plain shell pane's title is just the worktree path), and the handle is
    # what the reader needs to go look at it.
    assert "peer pane" in d["permissionDecisionReason"]
    assert "term_x" in d["permissionDecisionReason"]


def test_deny_is_logged(capsys, monkeypatch, tmp_path):
    mod = _load_module()
    _stub_orca(mod, monkeypatch, [_term()], {"term_x": DIALOG_TAIL})
    payload = _send()
    payload["cwd"] = str(tmp_path)
    _run(mod, payload, capsys, monkeypatch)
    log = tmp_path / ".omc" / "logs" / "sendmessage_guard.jsonl"
    assert log.exists()
    assert json.loads(log.read_text().strip())["signal"] == "denied_sendmessage"


def test_deny_reason_does_not_quote_the_markers(capsys, monkeypatch, tmp_path):
    """The reason is printed on the sender's own screen, which the guard reads on
    the next send. Quoting the footer verbatim would make it match itself."""
    mod = _load_module()
    _stub_orca(mod, monkeypatch, [_term()], {"term_x": DIALOG_TAIL})
    payload = _send()
    payload["cwd"] = str(tmp_path)
    _rc, out = _run(mod, payload, capsys, monkeypatch)
    reason = _decision(out)["permissionDecisionReason"].lower()
    assert not mod._dialog_open(reason)


# --- (b) an ordinary target -> pass -------------------------------------------

def test_idle_terminal_passes(capsys, monkeypatch):
    mod = _load_module()
    _stub_orca(mod, monkeypatch, [_term()], {"term_x": IDLE_TAIL})
    rc, out = _run(mod, _send(), capsys, monkeypatch)
    assert rc == 0
    assert out == ""


def test_one_stray_hint_is_not_a_chooser(capsys, monkeypatch):
    mod = _load_module()
    tail = ["the readme explains which files to select before building"]
    _stub_orca(mod, monkeypatch, [_term()], {"term_x": tail})
    rc, out = _run(mod, _send(), capsys, monkeypatch)
    assert rc == 0
    assert out == ""


def test_orphaned_terminal_is_ignored(capsys, monkeypatch):
    """No window attached means no human and no focus to steal."""
    mod = _load_module()
    _stub_orca(mod, monkeypatch, [_term(orphaned=True)], {"term_x": DIALOG_TAIL})
    rc, out = _run(mod, _send(), capsys, monkeypatch)
    assert rc == 0
    assert out == ""


# --- (c) probe cannot answer -> pass (fail-open) ------------------------------

def test_no_orca_on_path_passes(capsys, monkeypatch):
    mod = _load_module()
    monkeypatch.setattr(mod.shutil, "which", lambda _name: None)
    rc, out = _run(mod, _send(), capsys, monkeypatch)
    assert rc == 0
    assert out == ""


def test_runtime_unreachable_passes(capsys, monkeypatch):
    """`orca terminal list` failing is indistinguishable from 'no terminals'."""
    mod = _load_module()
    monkeypatch.setattr(mod, "_orca", lambda _args: None)
    rc, out = _run(mod, _send(), capsys, monkeypatch)
    assert rc == 0
    assert out == ""


def test_unreadable_screen_passes(capsys, monkeypatch):
    mod = _load_module()

    def fake(args):
        if args[:2] == ["terminal", "list"]:
            return {"terminals": [_term()]}
        return None  # the read fails

    monkeypatch.setattr(mod, "_orca", fake)
    rc, out = _run(mod, _send(), capsys, monkeypatch)
    assert rc == 0
    assert out == ""


def test_probe_exception_passes(capsys, monkeypatch):
    mod = _load_module()

    def boom(_args):
        raise RuntimeError("probe blew up")

    monkeypatch.setattr(mod, "_orca", boom)
    rc, out = _run(mod, _send(), capsys, monkeypatch)
    assert rc == 0
    assert out == ""


# --- escape hatches -----------------------------------------------------------

def test_bypass_token_in_message_passes(capsys, monkeypatch):
    mod = _load_module()
    _stub_orca(mod, monkeypatch, [_term()], {"term_x": DIALOG_TAIL})
    rc, out = _run(mod, _send(message="XSESSION_OK: target is a cloud peer"),
                   capsys, monkeypatch)
    assert rc == 0
    assert out == ""


def test_bypass_token_in_summary_passes(capsys, monkeypatch):
    mod = _load_module()
    _stub_orca(mod, monkeypatch, [_term()], {"term_x": DIALOG_TAIL})
    rc, out = _run(mod, _send(summary="XSESSION_OK: subagent"), capsys, monkeypatch)
    assert rc == 0
    assert out == ""


def test_kill_switch_passes(capsys, monkeypatch):
    mod = _load_module()
    monkeypatch.setenv(mod.BYPASS_ENV, "off")
    _stub_orca(mod, monkeypatch, [_term()], {"term_x": DIALOG_TAIL})
    rc, out = _run(mod, _send(), capsys, monkeypatch)
    assert rc == 0
    assert out == ""


# --- defensive shapes ---------------------------------------------------------

def test_malformed_stdin_passes(capsys, monkeypatch):
    mod = _load_module()
    monkeypatch.setattr("sys.stdin", io.StringIO("{not json"))
    assert mod.main() == 0
    assert capsys.readouterr()[0] == ""


def test_other_tool_passes(capsys, monkeypatch):
    mod = _load_module()
    _stub_orca(mod, monkeypatch, [_term()], {"term_x": DIALOG_TAIL})
    rc, out = _run(mod, {"tool_name": "Bash", "tool_input": {}}, capsys, monkeypatch)
    assert rc == 0
    assert out == ""


def test_structured_protocol_message_still_probed(capsys, monkeypatch, tmp_path):
    """A dict message (shutdown_response and friends) carries no bypass token, so
    it must not crash the token check and must still be gated."""
    mod = _load_module()
    _stub_orca(mod, monkeypatch, [_term()], {"term_x": DIALOG_TAIL})
    payload = _send(message={"type": "shutdown_response",
                             "request_id": "r", "approve": True})
    payload["cwd"] = str(tmp_path)
    rc, out = _run(mod, payload, capsys, monkeypatch)
    assert rc == 0
    assert _decision(out)["permissionDecision"] == "deny"

#!/usr/bin/env python3
"""Make a session prove it consulted the project's hand-off before it acts.

A new Claude Code session starts with no memory of the last one. The bridge is a
hand-off document somebody asked the previous session to write. Nothing checks
that the next session opens it — so the bridge is load-bearing prose that is
routinely skimmed or skipped, and the work restarts from a worse position than
if no hand-off existed at all (the document's existence buys false confidence).

Measured on one project (albc UUV, 2026-08-13): a 1388-line plan-of-record whose
headings already marked every closed item, named in the hand-off's first block,
never opened across six hours. Six failures followed, each one `grep` away. Then
the *next* session ran the prescribed checks, saw a section's title, did not open
it, and gave the operator the wrong bring-up command anyway. The rules for all of
this were already written in an auto-loaded skill card.

That is the datum this file exists for: prose self-instruction is not
load-bearing, no matter how well written or how prominently placed. Only a check
at the tool-call boundary is — and it is also the only layer a subagent inherits,
since a subagent reads neither the card nor the hand-off.

Nothing here is specific to any project, tool, or domain. The mechanism lives in
this file; the data lives in each project's `.claude/session-gate.json`. A repo
that declares no config makes this a no-op costing one process spawn, so shipping
it everywhere is safe.

Two independent checks, both optional:

  require_read  Before editing or running anything inside `scope`, the session
                must have Read the declared documents. Catches the common case:
                a session that never opens the hand-off at all.

  gates/block   Before running a `block` command, the session must have run every
                `gate` command. Catches the case where the next action is remote
                or destructive and the state checks were skipped.

Config schema — every key optional; absent keys disable that half:

    {
      "name":         "albc",
      "scope":        ["0_Project/in_progress/albc/"],   // [] or absent = whole project
      "require_read": [{"id": "handover", "path": "notes/2026-08-13-next.md",
                        "hint": "왜 이 문서를 읽어야 하는지 한 줄"}],
      "gates":        [{"id": "plan-toc", "match": "<regex>", "hint": "<command>"}],
      "block":        ["<regex>"],
      "message":      "<appended to every deny reason>"
    }

`path` is matched as a substring of the file being read, so a repo-relative path
works without knowing the absolute prefix. Gate/block regexes match the Bash
command text; gate patterns are tested first so a gate command is never blocked
by the rule it satisfies.

Bypass: `SESSION_GATE=off`. A gate that cannot be turned off gets deleted the
first time it misfires, which is 0 protection.

What this cannot do, stated so nobody trusts it further than it goes: it verifies
a document was *opened*, not that it was *understood*. It closes "never looked",
which is what every failure measured so far actually was. For the adjacent
failure — acting on a half-read document — see the project-side anchor-gate,
which demands a line citation next to every emitted instruction.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile

from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parent))
try:
    import hooklog  # noqa: E402
except Exception:  # fail-open — 계측 헬퍼가 훅을 죽여선 안 된다
    class hooklog:  # type: ignore  # noqa: N801
        @staticmethod
        def fire(*_a, **_k):
            pass

CONFIG_NAME = os.path.join(".claude", "session-gate.json")
BYPASS_ENV = "SESSION_GATE"
ACT_TOOLS = ("Bash", "Edit", "Write", "MultiEdit", "NotebookEdit")


def _find_config(cwd):
    """Nearest ancestor holding .claude/session-gate.json wins.

    Walking up (rather than trusting cwd) is what lets a session started inside a
    nested repo — a project's code often is its own repo inside the notes vault —
    still find the outer gate. CLAUDE_PROJECT_DIR is not exported to hooks and
    `git rev-parse` picks the inner repo, so neither is usable here.
    """
    d = os.path.abspath(cwd or os.getcwd())
    while True:
        path = os.path.join(d, CONFIG_NAME)
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:  # noqa: BLE001 — a malformed config must not block the turn
                return None
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def _state_path(session_id):
    safe = re.sub(r"[^A-Za-z0-9_-]", "", session_id or "nosession")[:64]
    return os.path.join(tempfile.gettempdir(), "session-gate-%s.json" % safe)


def _load_state(path):
    try:
        with open(path, encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:  # noqa: BLE001
        return set()


def _save_state(path, seen):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(sorted(seen), f)
    except Exception:  # noqa: BLE001
        pass


def _deny(reason):
    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }, ensure_ascii=False))
    return 0


def _in_scope(scope, text):
    """No scope declared means the whole project; otherwise substring match."""
    if not scope:
        return True
    return any(s and s in (text or "") for s in scope)


def _target_text(tool_name, tool_input):
    """The string a scope is matched against, per tool."""
    if tool_name == "Bash":
        return tool_input.get("command") or ""
    return tool_input.get("file_path") or tool_input.get("notebook_path") or ""


def _record_reads(cfg, tool_input, seen):
    """A Read of a declared document satisfies that requirement for the session."""
    path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if not path:
        return False
    hit = False
    for r in cfg.get("require_read") or []:
        want = r.get("path")
        if want and want in path:
            seen.add("read:" + (r.get("id") or want))
            hit = True
    return hit


def _deny_reason(cfg, header, items):
    lines = ["[session-gate: %s] %s" % (cfg.get("name", "project"), header), ""]
    lines += ["  # %s\n  %s" % (i[0], i[1]) for i in items]
    if cfg.get("message"):
        lines += ["", cfg["message"]]
    lines += ["", "우회: 이 세션을 %s=off 로 실행." % BYPASS_ENV]
    return "\n".join(lines)


def main():
    if os.environ.get(BYPASS_ENV, "").lower() in ("off", "0", "false"):
        return 0
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0  # a hook bug must never block the turn

    tool_name = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return 0

    cfg = _find_config(payload.get("cwd"))
    if not isinstance(cfg, dict):
        return 0  # no project declares a gate -> no-op, which is the common case

    state_path = _state_path(payload.get("session_id"))
    seen = _load_state(state_path)

    # Reading is never blocked — it is how a requirement gets satisfied.
    if tool_name in ("Read", "NotebookRead"):
        if _record_reads(cfg, tool_input, seen):
            _save_state(state_path, seen)
        return 0

    if tool_name not in ACT_TOOLS:
        return 0
    target = _target_text(tool_name, tool_input)
    if not target.strip():
        return 0

    # --- command gates (Bash only) -----------------------------------------
    gates = cfg.get("gates") or []
    blocks = cfg.get("block") or []
    if tool_name == "Bash" and gates and blocks:
        hit = False
        for g in gates:
            try:
                if re.search(g.get("match", r"(?!)"), target):
                    seen.add(g.get("id") or g.get("match"))
                    hit = True
            except re.error:
                continue
        if hit:
            _save_state(state_path, seen)
            return 0  # a gate command is itself the remedy; never gate it further

        blocked = any(_safe_search(p, target) for p in blocks)
        if blocked:
            missing = [g for g in gates if (g.get("id") or g.get("match")) not in seen]
            if missing:
                hooklog.fire("session_gate.jsonl", payload.get("cwd"), payload.get("session_id"),
                             decision="deny")
                return _deny(_deny_reason(
                    cfg,
                    "이 명령은 상태 확인 전에는 실행할 수 없다. 아직 안 돌린 게이트:",
                    [(g.get("id"), g.get("hint", g.get("match"))) for g in missing]))

    # --- document gate (any acting tool) ------------------------------------
    required = cfg.get("require_read") or []
    if required and _in_scope(cfg.get("scope"), target):
        missing = [r for r in required
                   if ("read:" + (r.get("id") or r.get("path"))) not in seen]
        if missing:
            hooklog.fire("session_gate.jsonl", payload.get("cwd"), payload.get("session_id"),
                         decision="deny")
            return _deny(_deny_reason(
                cfg,
                "이 프로젝트를 건드리기 전에 인수인계·계획 정본을 먼저 열어라. "
                "아직 안 읽은 문서:",
                [(r.get("id"), "%s\n  %s" % (r.get("path"), r.get("hint", "")))
                 for r in missing]))

    hooklog.fire("session_gate.jsonl", payload.get("cwd"), payload.get("session_id"),
                 decision="allow")
    _save_state(state_path, seen)
    return 0


def _safe_search(pattern, text):
    try:
        return bool(re.search(pattern, text))
    except re.error:
        return False


if __name__ == "__main__":
    sys.exit(main())

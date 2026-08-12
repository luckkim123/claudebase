#!/usr/bin/env python3
"""Block a project's remote-execution commands until its plan-of-record was consulted.

Failure mode this hook addresses (albc UUV, 2026-08-13, six hours):

  A project had a 1388-line plan-of-record (`.omx/programs/*/PLAN.md`) whose
  headings already carried "완료 / 닫힘 / 삭제됨" on every closed item. The
  handover prompt named that path in its first block. The session never opened
  it, reassembled the field procedure from source instead, revived three items
  the plan had closed, and edited an entry point nobody runs. Every one of the
  six failures was one `grep` away.

  The rule existed in an auto-loaded skill card and was not followed. That is
  the datum: prose self-instruction is not load-bearing (the sibling
  agent-routing-guard.py learned the same lesson). A gate at the tool-call
  boundary is, and it reaches subagents, which never read the skill card at all.

Generic by construction — the mechanism lives here, the data lives in the
project. This file knows nothing about robots, ROS, or albc. It walks up from
the session cwd looking for `.claude/session-gate.json`; if no project declares
one, it returns immediately and costs one process spawn. That keeps an
albc-specific alias out of a repo that ships to every machine.

Config schema (all keys optional except `gates` and `block`):

    {
      "name":    "albc",                      // shown in the deny message
      "gates":   [{"id": "plan-toc", "match": "<python regex>", "hint": "<cmd>"}],
      "block":   ["<python regex>", ...],     // commands that need the gates first
      "message": "<extra text appended to the deny reason>"
    }

Semantics: a Bash command matching a `gates[].match` is always allowed and
records that gate id for the session. A command matching any `block` pattern is
denied while any gate id is still unrecorded. Gate patterns are tested first, so
the gate commands themselves are never blocked by the very rule they satisfy.

Bypass: `SESSION_GATE=off` in the environment. A hook that cannot be turned off
gets deleted the first time it misfires, which is 0 protection.

What it deliberately does NOT catch: a command Claude *tells the user to run*
rather than running itself. That path emits no tool call, so no PreToolUse hook
can see it — see the project-side anchor-gate, which gates the message text at
Stop instead. Measured 2026-08-13: that is exactly how the seventh failure of
the same night got through a gate the session had actually executed.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile

CONFIG_NAME = os.path.join(".claude", "session-gate.json")
BYPASS_ENV = "SESSION_GATE"


def _find_config(cwd):
    """Nearest ancestor holding .claude/session-gate.json wins.

    Walking up (rather than trusting cwd) is what lets a session started inside
    a nested repo — albc's robot code is its own git repo inside the vault —
    still find the vault's gate. CLAUDE_PROJECT_DIR is not exported to hooks and
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


def main():
    if os.environ.get(BYPASS_ENV, "").lower() in ("off", "0", "false"):
        return 0
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0  # a hook bug must never block the turn

    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command")
    if not isinstance(command, str) or not command.strip():
        return 0

    cfg = _find_config(payload.get("cwd"))
    if not isinstance(cfg, dict):
        return 0  # no project declares a gate -> no-op, which is the common case
    gates = cfg.get("gates") or []
    blocks = cfg.get("block") or []
    if not gates or not blocks:
        return 0

    state_path = _state_path(payload.get("session_id"))
    seen = _load_state(state_path)

    # Gate patterns first: satisfying the gate must never be blocked by it.
    hit = False
    for g in gates:
        try:
            if re.search(g.get("match", r"(?!)"), command):
                seen.add(g.get("id") or g.get("match"))
                hit = True
        except re.error:
            continue
    if hit:
        _save_state(state_path, seen)
        return 0

    blocked = False
    for pat in blocks:
        try:
            if re.search(pat, command):
                blocked = True
                break
        except re.error:
            continue
    if not blocked:
        return 0

    missing = [g for g in gates if (g.get("id") or g.get("match")) not in seen]
    if not missing:
        return 0

    lines = [
        "[session-gate: %s] 이 명령은 계획 정본을 확인하기 전에는 실행할 수 없다."
        % cfg.get("name", "project"),
        "아직 안 돌린 게이트:",
        "",
    ]
    for g in missing:
        lines.append("  # %s\n  %s" % (g.get("id"), g.get("hint", g.get("match"))))
    if cfg.get("message"):
        lines += ["", cfg["message"]]
    lines += ["", "우회: 이 세션을 %s=off 로 실행." % BYPASS_ENV]
    return _deny("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())

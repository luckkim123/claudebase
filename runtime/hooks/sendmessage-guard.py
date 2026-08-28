#!/usr/bin/env python3
"""Hold back a cross-session SendMessage while a local terminal sits on a dialog.

Failure mode this hook addresses (observed 2026-08-23, two screenshots plus an
`orca terminal read` capture, reported by session ksm-obsidian-85):

  Session A called SendMessage with a 1.4 KB body. At that instant session B was
  parked on an AskUserQuestion chooser waiting for its human. The harness
  delivers a cross-session message by ENQUEUEING it on the receiver ("messages
  enqueue and drain at the receiver's next tool round" — SendMessage's own tool
  description), and the enqueue landed in B's text input box: the whole message
  rendered as input text under the prompt line and keyboard focus left the
  chooser. Arrow keys and Enter went to the input box, so the still-rendered
  chooser could not be answered. The human read it as a freeze. Recovery was
  manual — clear the input box, or click an option with the mouse.

Why the defense has to live on the SENDER (measured, not assumed):
  - `SendMessage` is a harness tool. It is not defined anywhere in claudebase or
    in any om* sibling: `grep -rlnw SendMessage` over claudebase,
    oh-my-heroacademia, oh-my-project, oh-my-experiments, oh-my-docs and
    oh-my-scholar returns 0 files. Same for the transport literal `cc-socks`.
  - The transport is one UNIX socket per harness process: /tmp/cc-socks/<pid>.sock,
    and every live socket's <pid> resolves to a claude.exe process. Both ends of
    the enqueue are Anthropic code.
  So nothing local can change what the receiver does with an arriving message.
  The only reachable lever is refusing to send at a bad moment.

What it does (PreToolUse, matcher = "SendMessage"):
  Probes the Orca-managed terminals on this host and denies the send when one of
  them is parked on a modal chooser. Fails open everywhere else.

Why the probe is host-scoped and not target-scoped (a real limitation, stated
up front rather than buried):
  tool_input carries only {to, message, summary?, notify_when_idle?} — a display
  name like "ksm-obsidian-85". Nothing maps that name to a terminal: `orca
  terminal list --json` exposes handle / ptyId / tabId / leafId / worktreePath /
  title, and the titles are Claude Code session titles ("claudebase hook 통합 및
  최적화"), never the peer name. So the hook cannot ask "is MY target on a
  dialog"; it can only ask "is any terminal on this host on a dialog".
  That is a defensible scope rather than a fudge: the deadlock needs a human
  looking at a TUI chooser, so only local live terminals can suffer it. Measured
  on this host: 113 peers in ListAgents, 3 live Orca terminals. If none of the 3
  is on a chooser, no local session can be wedged by this send. If one is, the
  sender cannot prove it is not the addressee — hence deny, with a one-line
  bypass for the case where the addressee is demonstrably elsewhere.

Cost: `orca terminal list` and `orca terminal read` measured at 0.15 s each on
this host, and `read` returns roughly one viewport (~52 rows with --limit 2000),
so a probe is about 4 subprocesses and well under the 5 s hook timeout. The
short read window is also what keeps stale chooser text from earlier in the
scrollback out of the match.

fail-open is the contract: no orca on PATH, runtime unreachable, non-zero exit,
unparseable JSON, timeout, or any unexpected exception -> return 0 (allow). A
hook must never be the reason a session cannot talk.

Kill switch: SENDMESSAGE_GUARD=off|0|false (same idiom as session-gate.py).
Per-call bypass: put `XSESSION_OK:` in the message or summary.
Idempotent marker in the settings command field: SENDMESSAGE_GUARD
Hook event: PreToolUse (matcher = "SendMessage")
Stdin schema: https://code.claude.com/docs/en/hooks
"""
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import hooklog  # noqa: E402
except Exception:  # fail-open — 계측 헬퍼가 훅을 죽여선 안 된다
    class hooklog:  # type: ignore  # noqa: N801
        @staticmethod
        def state_root(cwd):
            return cwd or "."

BYPASS_ENV = "SENDMESSAGE_GUARD"
BYPASS_TOKEN = "XSESSION_OK:"

# One viewport is enough; see the module docstring on why a bigger window would
# only add stale matches.
READ_LIMIT = "60"
MAX_TERMINALS = 6
TIMEOUT_S = 3

# Footer text a Claude Code chooser paints while it waits for a human. Sourced
# from the incident report's screenshot transcription; not re-captured live,
# because producing a chooser means wedging another session on purpose.
#
# CAREFUL when touching these: the hook matches against terminal SCREENS, so any
# text that puts these literals on screen (this file in a pager, a report
# quoting them) makes the guard fire on that terminal. That is why the deny
# reason below paraphrases instead of quoting them.
SELECT_HINTS = ("to select", "to navigate", "esc to cancel")
PROMPT_MARKERS = ("do you want to proceed?", "would you like to proceed?")

REASON = (
    "Cross-session send held back: a live terminal on this host (%s) is parked "
    "on a modal chooser waiting for its human — the arrow-key-and-Enter kind.\n"
    "Delivering now is the documented wedge: the harness enqueues a "
    "cross-session message into the receiver's text input box, which steals "
    "keyboard focus from the chooser. The chooser stays painted but stops "
    "accepting keys, and the human has to clear the input box or reach for the "
    "mouse to escape. A 2026-08-23 incident cost a session exactly this.\n"
    "Do ONE of these:\n"
    "1. Wait. Tell your user which terminal is parked and let them answer it, "
    "then re-emit the same SendMessage.\n"
    "2. If your addressee is provably not that terminal — a cloud or Remote "
    "Control peer, a subagent, 'main' — this gate cannot tell targets apart "
    "(it probes the host, not your addressee), so declare it: put "
    "'XSESSION_OK: <one-line reason>' in the message or summary and re-emit.\n"
    "3. If the content is long, leave it in a file and send a one-line pointer "
    "instead. Size is what turned the incident from a nuisance into a wedge."
)


def _bypassed() -> bool:
    return os.environ.get(BYPASS_ENV, "").lower() in ("off", "0", "false")


def _orca(args):
    """Run one read-only orca verb and return its `result`, or None on any
    failure. None always means 'allow' upstream — never 'nothing found'."""
    exe = shutil.which("orca")
    if not exe:
        return None
    try:
        proc = subprocess.run(
            [exe] + args, capture_output=True, text=True, timeout=TIMEOUT_S,
        )
    except Exception:  # noqa: BLE001 — timeout, OSError, anything: fail open
        return None
    if proc.returncode != 0:
        return None
    try:
        payload = json.loads(proc.stdout or "")
    except ValueError:
        return None
    if not isinstance(payload, dict) or not payload.get("ok"):
        return None
    result = payload.get("result")
    return result if isinstance(result, dict) else None


def _live_terminals():
    """Terminals a human could currently be looking at."""
    result = _orca(["terminal", "list", "--json"])
    if result is None:
        return []
    terminals = result.get("terminals")
    if not isinstance(terminals, list):
        return []
    live = []
    for t in terminals:
        if not isinstance(t, dict):
            continue
        # An orphaned pane has no window attached, so no human and no focus to
        # steal. A title-less entry is the same thing in practice.
        if t.get("orphaned") or not t.get("connected"):
            continue
        handle, title = t.get("handle"), t.get("title")
        if isinstance(handle, str) and handle and isinstance(title, str) and title:
            live.append((handle, title))
    return live[:MAX_TERMINALS]


def _tail_text(handle: str) -> str:
    result = _orca(["terminal", "read", "--terminal", handle,
                    "--limit", READ_LIMIT, "--json"])
    if result is None:
        return ""
    terminal = result.get("terminal")
    if not isinstance(terminal, dict):
        return ""
    tail = terminal.get("tail")
    if isinstance(tail, list):
        return "\n".join(x for x in tail if isinstance(x, str)).lower()
    if isinstance(tail, str):
        return tail.lower()
    return ""


def _dialog_open(text: str) -> bool:
    """Two hints, not one. The chooser footer carries all three select hints on
    a single line, so requiring two of them costs nothing and keeps ordinary
    prose that happens to say 'to select' from tripping the gate."""
    if not text:
        return False
    if any(m in text for m in PROMPT_MARKERS):
        return True
    return sum(1 for h in SELECT_HINTS if h in text) >= 2


def _parked_terminal():
    """Label of the first parked terminal, or None. The handle rides along with
    the title because a title is not always distinctive — several panes share one
    worktree, and a plain shell pane falls back to the worktree path — and the
    handle is what the reader needs to look at it (`orca terminal read`)."""
    for handle, title in _live_terminals():
        if _dialog_open(_tail_text(handle)):
            return "%s [%s]" % (title, handle)
    return None


def _log_deny(cwd, session_id) -> None:
    """Best-effort telemetry, same shape and location as the sibling guards so
    one tool can fold their counts together. Never raises."""
    try:
        log_dir = os.path.join(hooklog.state_root(cwd), ".omc", "logs")
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "sendmessage_guard.jsonl"),
                  "a", encoding="utf-8") as f:
            f.write(json.dumps(
                {"signal": "denied_sendmessage", "session_id": session_id},
                ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001, S110 — a raising hook blocks the turn; failing open is the contract
        pass


def _deny(reason: str, cwd=None, session_id=None) -> int:
    _log_deny(cwd, session_id)
    sys.stdout.write(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    return 0


def _text_of(value) -> str:
    """The bypass token may ride in a plain-text message or in the summary; the
    structured protocol shapes (shutdown_response and friends) carry neither."""
    return value if isinstance(value, str) else ""


def main() -> int:
    if _bypassed():
        return 0
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0  # malformed stdin -> never block on a hook bug

    if payload.get("tool_name") != "SendMessage":
        return 0  # matcher should prevent this, but be defensive

    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return 0

    declared = _text_of(tool_input.get("message")) + "\n" + _text_of(tool_input.get("summary"))
    if BYPASS_TOKEN in declared:
        return 0

    try:
        parked = _parked_terminal()
    except Exception:  # noqa: BLE001 — probe bug must not block a send
        return 0
    if parked:
        return _deny(REASON % parked, payload.get("cwd"), payload.get("session_id"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

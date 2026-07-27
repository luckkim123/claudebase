#!/usr/bin/env python3
"""Detect tool-call markup that leaked into the assistant TEXT channel and
nudge the model to re-emit it as a native tool_use block.

Failure mode this hook addresses ("mode A", diagnosed 2026-05-30 from
transcript d2fb8c68: 14 text blocks, 18 harness "could not be parsed"
records in ONE session):

  The model intends a tool call but the antml invoke/parameter markup is
  serialized into a `text` content block instead of a native `tool_use`
  block. The harness then reports "Your tool call was malformed and could
  not be parsed", the turn is wasted, and the model often repeats the same
  failure. Trigger correlates with long payloads carrying special chars
  (backticks, em-dashes, angle brackets, escaped quotes, Korean).

Why this is a Stop hook and not PreToolUse:
  A leaked tool call is NOT a tool_use event — the harness never fires
  PreToolUse for it, so it is structurally impossible to hard-block. The
  only enforceable lever is POST-HOC: after the model finishes its turn,
  inspect the last assistant message; if it ends in leaked closing markup,
  block the Stop ONCE and inject a correction so the model re-issues the
  call natively. This is detection + self-repair, NOT prevention.

GATE verification (live on Claude Code v2.1.158, 2026-05-30):
  - Stop hook stdin DOES carry `last_assistant_message` and
    `stop_hook_active` (undocumented but present at runtime), so we need
    no transcript parsing and get free loop protection.
  - `decision: "block"` + `reason` is fed back to the model on the next
    request (confirmed: a block reason "respond with RETRY" made the model
    output RETRY).
  - After a block, the re-fired Stop carries `stop_hook_active: true`, so
    gating on it caps the loop at exactly one extra turn.

Discipline (mirrors fix_surrogate.py / askuserquestion-guard.py):
  - Never block on a hook bug: any exception or malformed stdin -> exit 0,
    allow the stop. A detector must not be able to wedge a session.
  - Always exit 0; the decision travels in the JSON body, not the code.
  - Log every detection to .omc/logs/ for telemetry, block-or-not.

Hook event: Stop (no matcher)
Idempotent marker in the settings command field: MALFORMED_TOOLCALL_GUARD
"""
from __future__ import annotations

import json
import os
import re
import sys

_MISSING = object()

# Build the markup tokens by concatenation so THIS file never contains a
# literal closing invoke/parameter tag — otherwise the hook's own source,
# if ever quoted back into a message, could read as a mode-A leak.
_LT = "<"
_GT = ">"
_CLOSE_PARAM = _LT + "/parameter" + _GT          # </ parameter >
_CLOSE_INVOKE = _LT + "/" + "antml:invoke" + _GT  # </ antml:invoke >  (namespaced form)
_CLOSE_INVOKE_BARE = _LT + "/invoke" + _GT        # </ invoke >        (bare form, seen in transcript)

# A genuine leak ends the text with a closing parameter tag followed by a
# closing invoke tag (optionally with whitespace between). Anchored to the
# END of the message ($) so that merely *quoting* these tags mid-text — as
# this very analysis does — never trips the detector. 14/14 observed leaks
# matched `</parameter>\n</invoke>` as the literal tail.
_TAIL_RE = re.compile(
    re.escape(_CLOSE_PARAM)
    + r"\s*(?:"
    + re.escape(_CLOSE_INVOKE)
    + r"|"
    + re.escape(_CLOSE_INVOKE_BARE)
    + r")\s*$"
)

# Secondary signal: a bare closing invoke tag as the final token, even
# without a preceding parameter (covers no-arg tool calls that leaked).
_BARE_TAIL_RE = re.compile(
    r"(?:" + re.escape(_CLOSE_INVOKE) + r"|" + re.escape(_CLOSE_INVOKE_BARE) + r")\s*$"
)

REASON = (
    "Your previous message leaked tool-call markup into the TEXT channel "
    "instead of emitting a native tool call — the harness would report it as "
    "'malformed and could not be parsed' and the turn is wasted. The text "
    "ended with a literal closing invoke/parameter tag.\n"
    "Re-issue that tool call NOW as a real tool_use block:\n"
    "1. Emit the tool call with NO prose in the same message — leading prose "
    "before a large/special-char payload is what pushes the markup into the "
    "text channel.\n"
    "2. If the payload has backticks, heredocs, em-dashes, angle brackets, "
    "escaped quotes or Korean, prefer writing it to a temp file first (Write) "
    "and then running a simple command that reads the file, rather than "
    "inlining the special chars in a bash -c string.\n"
    "3. Split one large Edit/Bash into smaller single calls if it still leaks.\n"
    "Do not reproduce the leaked markup as text again; make the actual call."
)


def _looks_like_leak(text: str) -> str | None:
    """Return a short signal name if `text` ends in leaked tool-call markup,
    else None. Anchored to the tail so documentation/quoting is not a leak."""
    if not text:
        return None
    stripped = text.rstrip()
    if _TAIL_RE.search(stripped):
        return "param_invoke_tail"
    if _BARE_TAIL_RE.search(stripped):
        return "bare_invoke_tail"
    return None


def _log(cwd: str, record: dict) -> None:
    """Best-effort telemetry. Never raises."""
    try:
        log_dir = os.path.join(cwd or ".", ".omc", "logs")
        os.makedirs(log_dir, exist_ok=True)
        path = os.path.join(log_dir, "malformed_toolcall.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001, S110 — a raising hook blocks the user's turn; failing open is the contract
        pass


def _block(reason: str, tail: str = "") -> int:
    body: dict = {"decision": "block", "reason": reason}
    # `additionalContext` is an official Stop-hook output field (docs:
    # hooks.md#decision-control). Surface the exact leaked tail so the model
    # sees *what* it dropped, not just that it dropped something — `reason`
    # carries the instruction, `additionalContext` carries the evidence.
    if tail:
        body["hookSpecificOutput"] = {
            "hookEventName": "Stop",
            "additionalContext": "The leaked tail was:\n" + tail,
        }
    sys.stdout.write(json.dumps(body))
    return 0


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0  # never block on a hook bug

    if payload.get("hook_event_name") != "Stop":
        return 0

    last = payload.get("last_assistant_message") or ""
    if not isinstance(last, str):
        return 0

    signal = _looks_like_leak(last)
    if signal is None:
        return 0  # clean turn, allow stop

    cwd = payload.get("cwd") or os.getcwd()

    # 3-state check for stop_hook_active:
    #   stop_hook_active is present in runtime stdin but absent from the
    #   official Stop-hook schema (verified 2026-05-31 against docs). If a
    #   future Claude Code build removes or renames the field, the old
    #   `.get(...) is True` pattern would silently treat every re-fire as a
    #   first fire and block again -- causing an infinite loop that wedges the
    #   session. Instead we distinguish three states:
    #
    #     present-and-true  -- this Stop is our own re-fire: skip blocking.
    #     present-and-false -- genuine first leak: block once.
    #     ABSENT            -- field was removed/renamed: fail-safe, allow stop.
    #       Rationale: one unblocked leak visible to the user is a much lighter
    #       failure than wedging the session in a block loop. This aligns with
    #       the "never block on a hook bug" discipline of this module.
    raw_active = payload.get("stop_hook_active", _MISSING)
    field_present = raw_active is not _MISSING
    already_firing = raw_active is True

    _log(
        cwd,
        {
            "session_id": payload.get("session_id"),
            "signal": signal,
            "stop_hook_active": already_firing,
            "loop_guard_field_present": field_present,
            "tail": last[-160:],
            "blocked": field_present and not already_firing,
        },
    )

    # Dedupe / loop guard: skip blocking if this is our own re-fire (already_firing)
    # or if the guard field is absent (fail-safe to avoid an infinite block loop
    # should the field be removed in a future Claude Code build).
    if already_firing or not field_present:
        return 0

    return _block(REASON, tail=last[-200:])


if __name__ == "__main__":
    sys.exit(main())

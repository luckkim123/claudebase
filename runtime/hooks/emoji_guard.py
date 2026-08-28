#!/usr/bin/env python3
"""Block a Stop when the assistant's final TEXT contains emoji, and make the
model re-emit the same content emoji-free.

Why a hook and not just the CLAUDE.md rule:
  config/CLAUDE.md's Output Form already says "No emoji in response text"
  (emoji corrupt terminal drag-select copy — a copied answer comes back
  mangled). A prose rule is probabilistic: in long-context sessions it drifts.
  This hook makes it deterministic. After the turn, inspect the last assistant
  message; if it carries emoji, block the Stop ONCE and inject a correction.
  Catch-and-redo, NOT prevention: a Stop hook fires AFTER the message is
  emitted and Claude Code has no response post-processor a user can insert, so
  the emoji version flashes for one turn before the corrected turn replaces it.

DNA inherited from detect_malformed_toolcall.py (the house Stop-hook pattern):
  (1) stop_hook_active 3-state loop guard (present-true=skip / present-false=
      block once / ABSENT=fail-safe allow) — caps the loop at one extra turn.
  (2) never block on a hook bug: any exception / malformed stdin -> exit 0.
  (3) .omc/logs telemetry on every check, block-or-not.
  (4) idempotent marker in the settings command field: EMOJI_GUARD.

Emoji scope (deliberately narrow — the omha routing format and learning-mode
dividers lean on non-emoji symbols that MUST pass, so widening a range would
block normal responses every turn):
  INCLUDE  U+1F300-1FAFF, U+1F1E6-1F1FF (flags), U+2600-26FF EXCEPT the text
           stars U+2605-2606 (see below) — incl. warning U+26A0; U+2700-27BF
           (dingbats incl. check U+2705) EXCEPT the text marks and the bracket
           ornaments (see below); U+2B00-2BFF (incl. emoji star U+2B50);
           U+FE0F (emoji variation selector).
  EXCLUDE  arrows (U+2190-21FF, incl. right-arrow), geometric shapes
           (U+25A0-25FF, incl. black square / right-triangle), dashes
           (U+2010-2015, em dash), middle dot (U+00B7), bullet (U+2022) — these
           sit OUTSIDE every INCLUDE range. PLUS three carve-outs INSIDE them:
             * text stars U+2605-2606 — the learning output-style's "star
               Insight" dividers use U+2605; the emoji star U+2B50 stays caught.
             * text check / ballot marks U+2713-2718 — monochrome, width-1,
               text-presentation by default (U+2714 and U+2716 do carry
               Emoji=Yes, but Emoji_Presentation=No). They do NOT break
               drag-select copy, which is the only damage this hook exists to
               prevent. The emoji check U+2705 and cross U+274C stay caught.
             * bracket ornaments U+2768-2775 — incl. U+276F, the shell prompt
               chevron. None of these is an emoji at all; quoting a terminal
               screen used to cost a whole-response rewrite.
           Measured 2026-08-23 over 22 recorded blocks: 10 were the last two
           carve-outs. A future edit must not re-close any of the three gaps.

Hook event: Stop (no matcher). Reads last_assistant_message from stdin
(present at runtime, per the sibling hooks); falls back to parsing
transcript_path (JSONL) when that field is absent.
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import hooklog  # noqa: E402
except Exception:  # fail-open — 계측 헬퍼가 훅을 죽여선 안 된다
    class hooklog:  # type: ignore  # noqa: N801
        @staticmethod
        def state_root(cwd):
            return cwd or "."

_MISSING = object()

# Emoji character class — see module docstring for the include/exclude rationale.
# Written as \u/\U escapes (not literal glyphs) so this source never itself
# carries chars from the emoji ranges and each bound is auditable at a glance.
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"  # main emoji + supplemental / extended-A pictographs
    "\U0001F1E6-\U0001F1FF"  # regional indicator symbols (flags)
    "\U00002600-\U00002604"  # misc symbols, up to just below the text stars
    "\U00002607-\U000026FF"  # ...resuming after them (U+2605-2606 text stars carved out)
    "\U00002700-\U00002712"  # dingbats, up to just below the text check/ballot marks
    "\U00002719-\U00002767"  # ...resuming after them (U+2713-2718 carved out)
    "\U00002776-\U000027BF"  # ...and after the bracket ornaments (U+2768-2775 carved out)
    "\U00002B00-\U00002BFF"  # misc symbols & arrows (incl. star U+2B50)
    "\U0000FE0F"              # emoji variation selector-16
    "]"
)

REASON = (
    "직전 응답에 이모지가 포함됨. 이모지를 전부 제거하고 같은 내용을 다시 작성하라. "
    "화살표/가운뎃점/대시/기하도형(→ · — ■ ▸)은 이모지가 아니니 유지. "
    "직전 응답 맨 앞에 라우팅/머리말 줄이 있었다면 재작성본 맨 앞에도 그대로 다시 넣어라 "
    "— 빠뜨리면 다른 Stop 가드가 또 차단해 한 턴에 재생성이 두 번 일어난다."
)


def _find_emoji(text: str) -> list[str]:
    """Return the sorted unique emoji chars in `text` (empty if none)."""
    if not text:
        return []
    return sorted(set(_EMOJI_RE.findall(text)))


def _extract_text(content) -> str:
    """Flatten an assistant message `content` (str or list of blocks) to text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                t = block.get("text")
                if isinstance(t, str):
                    parts.append(t)
        return "\n".join(parts)
    return ""


def _text_from_transcript(path: str) -> str:
    """Fallback: last assistant text from a transcript JSONL tail."""
    try:
        with open(os.path.expanduser(path), encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return ""
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = rec.get("message", rec)
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        return _extract_text(msg.get("content"))
    return ""


def _last_assistant_text(payload: dict) -> str:
    last = payload.get("last_assistant_message")
    if isinstance(last, str) and last:
        return last
    tpath = payload.get("transcript_path")
    if isinstance(tpath, str) and tpath:
        return _text_from_transcript(tpath)
    return ""


def _log(cwd: str, record: dict) -> None:
    """Best-effort telemetry. Never raises."""
    try:
        log_dir = os.path.join(hooklog.state_root(cwd), ".omc", "logs")
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "emoji_guard.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001, S110 — a raising hook blocks the user's turn; failing open is the contract
        pass


def _block(found: list[str]) -> int:
    reason = REASON
    if found:
        reason += "\n발견된 이모지: " + " ".join(found)
    # ensure_ascii=True keeps stdout pure ASCII (\uXXXX) regardless of locale;
    # Claude Code decodes it back to Korean/emoji before injecting the reason.
    sys.stdout.write(json.dumps({"decision": "block", "reason": reason}))
    return 0


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0  # never block on a hook bug

    if payload.get("hook_event_name") != "Stop":
        return 0

    text = _last_assistant_text(payload)
    found = _find_emoji(text)
    if not found:
        return 0  # clean turn, allow stop

    cwd = payload.get("cwd") or os.getcwd()

    # 3-state stop_hook_active guard (mirrors detect_malformed_toolcall.py):
    #   present-true  -> our own re-fire: skip blocking (cap loop at one turn)
    #   present-false -> genuine first hit: block once
    #   ABSENT        -> field removed in a future build: fail-safe allow, so a
    #                    single visible emoji beats wedging the session in a loop.
    raw_active = payload.get("stop_hook_active", _MISSING)
    field_present = raw_active is not _MISSING
    already_firing = raw_active is True

    _log(
        cwd,
        {
            "session_id": payload.get("session_id"),
            "found": found,
            "count": len(found),
            "stop_hook_active": already_firing,
            "loop_guard_field_present": field_present,
            "blocked": field_present and not already_firing,
        },
    )

    if already_firing or not field_present:
        return 0

    return _block(found)


if __name__ == "__main__":
    sys.exit(main())

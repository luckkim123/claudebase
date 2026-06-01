#!/usr/bin/env python3
"""Stop hook: detect chatty-filler / sycophantic OPENERS and nudge a rewrite.

Inherits detect_malformed_toolcall.py discipline:
  - fail-open: any exception/malformed stdin -> exit 0 (never wedge a session)
  - stop_hook_active 3-state loop guard (present-true=skip / present-false=block
    once / ABSENT=fail-safe allow)
  - .omc/logs/output_style.jsonl telemetry, block-or-not
  - decision travels in JSON body, code always exits 0
  - idempotent settings marker: OUTPUT_STYLE_GUARD

Scope (design.md §5, D1 확정): v1 detects ONLY filler/sycophancy at the OPENER
(first non-blank line). Verbosity / bullet-overuse / missing-citation are NOT
detected here — nudge-only — to keep false positives near zero.
Active only when CLAUDEBASE_OUTPUT_STYLE == enforce.
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from output_style_common import style_mode  # noqa: E402

_MISSING = object()

# Opener filler/sycophancy patterns (EN + KO). Anchored to the start of the
# first non-blank line only — never matches mid-body.
_FILLER_RE = re.compile(
    r"^\s*(?:"
    r"certainly[!,. ]|sure thing|of course[!,. ]|absolutely[!,. ]|"
    r"great question|excellent question|good question|that's a (?:great|fantastic|excellent)|"
    r"you'?re absolutely right|i'?d be happy to|i'?d be glad to|happy to help|"
    r"좋은 질문|훌륭한 질문|물론입니다|물론이에요|기꺼이|맞습니다[!,. ]?그|정확히 맞"
    r")",
    re.IGNORECASE,
)

REASON = (
    "응답 오프너가 구어체 필러/아첨으로 시작했습니다(예: 'Certainly!', '좋은 질문', "
    "\"You're absolutely right\"). 근거: 이런 validation-forward 오프너는 정확도·신뢰를 "
    "떨어뜨립니다(sycophancy 연구). 다시 답하되 결론(BLUF)부터 단정형으로 시작하고, "
    "필러·아첨 오프너를 제거하세요. 내용은 유지하고 첫 문장만 결론으로 바꾸면 됩니다."
)


def _first_nonblank_line(text: str) -> str:
    for line in (text or "").splitlines():
        if line.strip():
            return line
    return ""


def _filler_opener(text: str):
    """Return matched filler string if the OPENER is filler/sycophancy, else None."""
    opener = _first_nonblank_line(text)
    m = _FILLER_RE.match(opener)
    return m.group(0) if m else None


def _log(cwd: str, record: dict) -> None:
    try:
        d = os.path.join(cwd or ".", ".omc", "logs")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "output_style.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _block(reason: str, opener: str) -> int:
    body = {
        "decision": "block",
        "reason": reason,
        "hookSpecificOutput": {
            "hookEventName": "Stop",
            "additionalContext": "검출된 오프너: " + opener,
        },
    }
    sys.stdout.write(json.dumps(body, ensure_ascii=False))
    return 0


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return 0
    if payload.get("hook_event_name") != "Stop":
        return 0
    if style_mode(os.environ) != "enforce":
        return 0  # only enforce mode blocks; off/nudge never block here
    last = payload.get("last_assistant_message") or ""
    if not isinstance(last, str):
        return 0
    hit = _filler_opener(last)
    if hit is None:
        return 0
    cwd = payload.get("cwd") or os.getcwd()
    raw_active = payload.get("stop_hook_active", _MISSING)
    field_present = raw_active is not _MISSING
    already_firing = raw_active is True
    _log(
        cwd,
        {
            "session_id": payload.get("session_id"),
            "signal": "filler_opener",
            "match": hit,
            "stop_hook_active": already_firing,
            "loop_guard_field_present": field_present,
            "blocked": field_present and not already_firing,
        },
    )
    if already_firing or not field_present:
        return 0
    return _block(REASON, hit)


if __name__ == "__main__":
    sys.exit(main())

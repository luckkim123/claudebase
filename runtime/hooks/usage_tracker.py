#!/usr/bin/env python3
"""Append this session's cumulative token usage to ~/.claude/metrics/usage.jsonl.

Why this exists:
  docs/ai-usage-fitting.md commits to reviewing "token spend AND answer quality
  together each week", but nothing on this machine recorded spend — measured
  2026-08-10, ~/.claude/metrics did not exist and a word-boundary grep for
  total_cost_usd / cost_usd across runtime/ and the HUD returned zero hits. The
  weekly review had no denominator.

Tokens, not dollars, on purpose:
  A per-model price table would have to be hardcoded here, and config/CLAUDE.md
  ("Evidence Before Assertion") forbids asserting prices from memory — they
  drift, and a stale table silently produces confident wrong numbers forever.
  Tokens are ground truth and are what the fitting playbook actually compares;
  apply whatever pricing is current at analysis time, against the model id this
  hook records alongside the counts.

Where the numbers come from:
  NOT from the hook payload. The Stop stdin carries session_id / transcript_path
  / cwd but no `usage` and no `model`, so a hook that reads them from stdin
  writes zero-filled rows and looks healthy while measuring nothing. (ECC's
  cost-tracker.js documents exactly this failure: 2,340 rows over 52 days at a
  0.0% non-zero rate before they switched to the transcript.) The authoritative
  record is the session JSONL Claude Code already hands us, where each
  `{"type":"assistant"}` entry carries message.usage and message.model.

Row semantics — cumulative, not incremental:
  Stop fires once per assistant response, not once per session, so this appends
  a fresh row several times a session and each row is the running total up to
  that point. Per-session spend = the LAST row for a session_id; per-day spend =
  sum of those last rows. Chosen over incremental deltas because it is
  self-healing: a row lost to a crash or a kill costs nothing, since the next
  row restates the whole total.

Reading a row: prefer models[<id>], not the top-level turns.
  Claude Code also emits `"model": "<synthetic>"` assistant entries (injected
  messages). They carry a usage object whose token fields are all zero, so they
  cannot inflate any token total, but they DO add to the row's `turns`. Left in
  deliberately rather than filtered — a visible zero bucket is self-explaining,
  a silently dropped entry is not. Measured 2026-08-10 on a 326-turn session:
  324 real turns, 2 synthetic, 0 tokens attributed to the latter.

Never blocks. Any malformed stdin, unreadable transcript, or unwritable metrics
dir exits 0 silently — a measurement hook that can stall a session is worse than
no measurement. Idempotent marker in the settings command field: USAGE_TRACKER.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# The four usage fields that carry real token counts. Deliberately a fixed list
# rather than "sum every int in usage": the same objects also carry `iterations`
# and `speed`, which are not tokens and would silently inflate a total.
_TOKEN_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)


def _metrics_path() -> Path:
    home = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(
        os.path.expanduser("~"), ".claude"
    )
    return Path(home) / "metrics" / "usage.jsonl"


def _tally(transcript: Path) -> tuple[dict, int]:
    """Sum token fields per model id over every assistant turn in the JSONL.

    Returns (per_model, turns). Malformed lines are skipped rather than fatal:
    a transcript being appended to while we read it can end mid-line.
    """
    per_model: dict[str, dict[str, int]] = {}
    turns = 0
    with transcript.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                entry = json.loads(line)
            except (ValueError, TypeError):
                continue
            if entry.get("type") != "assistant":
                continue
            message = entry.get("message") or {}
            usage = message.get("usage")
            if not isinstance(usage, dict):
                continue
            model = message.get("model") or "unknown"
            bucket = per_model.setdefault(
                model, {field: 0 for field in _TOKEN_FIELDS} | {"turns": 0}
            )
            for field in _TOKEN_FIELDS:
                value = usage.get(field)
                if isinstance(value, int):
                    bucket[field] += value
            bucket["turns"] += 1
            turns += 1
    return per_model, turns


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (ValueError, TypeError):
        return 0
    if not isinstance(payload, dict):
        return 0

    raw_path = payload.get("transcript_path")
    if not raw_path:
        return 0
    transcript = Path(os.path.expanduser(str(raw_path)))
    if not transcript.is_file():
        return 0

    # ponytail: re-reads the whole transcript on every Stop. Measured on this
    # machine — 6 ms for a typical 1 MB session, 103 ms for the largest
    # transcript present (64.9 MB). Resume-from-byte-offset only earns its
    # complexity if that worst case starts being the common case.
    try:
        per_model, turns = _tally(transcript)
    except OSError:
        return 0
    if not turns:
        return 0

    row = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "session_id": payload.get("session_id"),
        "cwd": payload.get("cwd"),
        "turns": turns,
        "models": per_model,
        "totals": {
            field: sum(b[field] for b in per_model.values()) for field in _TOKEN_FIELDS
        },
    }

    out = _metrics_path()
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        return 0
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001 — a measurement hook must never break a turn
        sys.exit(0)

#!/usr/bin/env python3
"""Aggregate the AskUserQuestion failure telemetry into a human summary ([5]).

The guard and retry hooks each append one jsonl record per failure:
  .omc/logs/askuserquestion_guard.jsonl  — PreToolUse denies (empty-array /
      partial / surrogate shapes), signal "denied_askuserquestion"
  .omc/logs/askuserquestion_retry.jsonl  — Stop-hook rejections of the bare
      missing-`questions` shape, signal "empty_askuserquestion"

Before this script the logs were write-only, so there was no way to tell whether
the hardening actually reduced the empty-call rate. Run it to see the trend:

    python3 runtime/hooks/askuserquestion_stats.py            # uses ./.omc/logs
    python3 runtime/hooks/askuserquestion_stats.py --root /some/project

This is a MANUAL diagnostic — it is NOT wired into any hook, so it adds zero
per-turn cost. Read-only over the logs; it never writes or deletes anything.
"""
from __future__ import annotations

import argparse
import json
import os

_GUARD_LOG = "askuserquestion_guard.jsonl"
_RETRY_LOG = "askuserquestion_retry.jsonl"


def _read_records(path: str) -> list:
    """Parse one jsonl, skipping corrupt lines. Best-effort -> []."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except (OSError, UnicodeDecodeError):
        return []
    out = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # a partial final write or corruption — skip, never crash
    return out


def aggregate(root: str) -> dict:
    """Fold both logs under `root`/.omc/logs into a summary dict.

    Returns keys:
      total            — every recorded failure (guard + retry)
      guard_denies     — count from the PreToolUse guard log
      retry_rejections — count from the Stop retry log
      abandon_events   — retry records whose mode == "abandon"
      by_session       — {session_id: total failures of any shape}
    """
    log_dir = os.path.join(root or ".", ".omc", "logs")
    guard = _read_records(os.path.join(log_dir, _GUARD_LOG))
    retry = _read_records(os.path.join(log_dir, _RETRY_LOG))

    by_session: dict = {}
    for rec in guard + retry:
        sid = rec.get("session_id")
        if sid is not None:
            by_session[sid] = by_session.get(sid, 0) + 1

    abandon_events = sum(1 for r in retry if r.get("mode") == "abandon")

    return {
        "total": len(guard) + len(retry),
        "guard_denies": len(guard),
        "retry_rejections": len(retry),
        "abandon_events": abandon_events,
        "by_session": by_session,
    }


def _format(stats: dict) -> str:
    lines = [
        "AskUserQuestion failure telemetry",
        "=" * 34,
        f"  total failures   : {stats['total']}",
        f"  guard denies     : {stats['guard_denies']}  "
        "(empty-array / partial / surrogate)",
        f"  retry rejections : {stats['retry_rejections']}  "
        "(bare missing-`questions`)",
        f"  abandon events   : {stats['abandon_events']}  "
        "(runaway loops that hit the abandon stage)",
    ]
    by_session = stats["by_session"]
    if by_session:
        lines.append("  by session (worst first):")
        for sid, n in sorted(by_session.items(), key=lambda kv: kv[1], reverse=True):
            lines.append(f"    {sid}: {n}")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", default=".",
        help="project root containing .omc/logs (default: current dir)")
    args = parser.parse_args(argv)
    print(_format(aggregate(args.root)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

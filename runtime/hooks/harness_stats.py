#!/usr/bin/env python3
"""Aggregate harness telemetry into four tables — numbers only, no verdicts.

`askuserquestion_stats.py` proved one guard's hardening worked by reading its
log. Every other guard is still write-only, and the routing log has an
aggregator that nobody runs. This generalizes the pattern across all of them.

    python3 runtime/hooks/harness_stats.py                      # cwd
    python3 runtime/hooks/harness_stats.py --root ~/ksm_Obsidian --root .

MANUAL diagnostic — NOT wired into any hook, so it costs nothing per turn.
Read-only: it never writes or deletes anything.

Four things it reports, and the trap each one carries:

  1. Guard firings — count and last-seen per `.omc/logs/*.jsonl`. The records
     carry no timestamp field (measured 2026-08-15: keys are session_id,
     signal, blocked, …), so "last seen" is the FILE mtime, not the event
     time. It is an upper bound on staleness, nothing more.

  2. Guards that never fired — split in two, because "no log" has three
     meanings, not the two the retirement question assumes: a guard that
     prevented everything, a guard whose wiring broke, and a guard that was
     never built to log at all. Only the first two are retirement candidates.
     Of 21 wired hooks here, 5 write logs. Lumping the other 16 in would
     nominate every one of them for retirement.

  3. ROUTE misses and re-routes — delegated to omha's own `route_log.py` when
     it can be found, because it already computes exactly this and knows its
     own dedup rule (the Stop gate can fire twice per turn). Not re-implemented
     here; if the module is missing the table says so and the rest still runs.

  4. Miss rate by session — joined through the transcripts. `turn_id` in
     routing.jsonl IS the transcript record's `uuid` (route_guard.py:112), so
     the real session boundary is recoverable today without adding any field.
     A 45-minute-gap approximation is not needed and is not used.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

_HOOK_LOG_RE = re.compile(r"([A-Za-z0-9_.-]+)\.jsonl")
_SETTINGS = [
    Path.home() / ".claude" / "settings.json",          # what is actually wired
    Path.home() / "claudebase" / "config" / "settings.json",   # the source
]
_OMHA_HOOKS = [
    Path.home() / "oh-my-heroacademia" / "hooks",
    Path.home() / ".claude" / "plugins" / "cache" / "heroacademia",
]


# ─── reading ────────────────────────────────────────────────────────────────

def _read_jsonl(path: Path) -> list:
    """Parse one jsonl, skipping corrupt lines. Best-effort -> []."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
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
            continue
    return out


def _load_settings() -> dict:
    for p in _SETTINGS:
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
    return {}


def wired_hooks(settings: dict) -> dict:
    """{script basename: [event, …]} for every hook command in settings.

    Keyed by the script file rather than the `# NAME` comment: the comment is
    a label, the file is what a log can be traced back to."""
    out: dict = {}
    for event, groups in (settings.get("hooks") or {}).items():
        for group in groups if isinstance(groups, list) else []:
            for hook in group.get("hooks", []) if isinstance(group, dict) else []:
                cmd = hook.get("command", "") if isinstance(hook, dict) else ""
                for token in cmd.split():
                    if token.endswith((".py", ".sh", ".js")):
                        out.setdefault(os.path.basename(token), []).append(event)
    return out


def logging_hooks(script_names) -> dict:
    """{script basename: {log stem, …}} — which hooks were built to log.

    Greps each hook's source for a `<name>.jsonl` literal. That is the only
    honest way to tell "prevented everything" from "was never a logger";
    absence of a log file cannot distinguish them."""
    roots = [
        Path.home() / "claudebase" / "runtime" / "hooks",
        Path.home() / "claudebase" / "runtime" / "skills",
    ]
    out: dict = {}
    for name in script_names:
        for root in roots:
            for path in root.rglob(name):
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                # keyed with the extension, because guard_firings keys on the
                # file name — a bare stem silently matches nothing and reports
                # every logging guard as never-fired.
                stems = {m + ".jsonl" for m in _HOOK_LOG_RE.findall(text)}
                if stems:
                    out.setdefault(name, set()).update(stems)
                break
    return out


# ─── table 1 + 2: guards ────────────────────────────────────────────────────

def guard_firings(roots) -> dict:
    """{log stem: {'count': n, 'roots': {root: n}, 'mtime': float|None}}.

    Scans `~/.claude/metrics` alongside every root's `.omc/logs`, because not
    every logger writes under the project. `usage_tracker.py` writes to
    `~/.claude/metrics/usage.jsonl` (usage_tracker.py:71), and looking only at
    `.omc/logs` reported it as never-fired while its log held 177 records — the
    same "no log means dead" error table [2] exists to prevent."""
    out: dict = {}
    log_dirs = [(str(r), Path(r) / ".omc" / "logs") for r in roots]
    log_dirs.append(("~/.claude/metrics", Path.home() / ".claude" / "metrics"))
    for root, log_dir in log_dirs:
        if not log_dir.is_dir():
            continue
        for path in sorted(log_dir.glob("*.jsonl")):
            stem = path.name
            n = len(_read_jsonl(path))
            try:
                mtime = path.stat().st_mtime
            except OSError:
                mtime = None
            rec = out.setdefault(stem, {"count": 0, "roots": {}, "mtime": None})
            rec["count"] += n
            rec["roots"][str(root)] = n
            if mtime and (rec["mtime"] is None or mtime > rec["mtime"]):
                rec["mtime"] = mtime
    return out


def silent_guards(wired: dict, loggers: dict, fired: dict) -> tuple:
    """(retirement candidates, non-logging hooks) — the split that matters.

    A hook that logs and never fired is a real question. A hook that was never
    built to log is not evidence of anything."""
    candidates, non_logging = [], []
    for name in sorted(wired):
        stems = loggers.get(name)
        if not stems:
            non_logging.append(name)
            continue
        if not any(fired.get(s, {}).get("count") for s in stems):
            candidates.append((name, sorted(stems)))
    return candidates, non_logging


# ─── table 3: routing ───────────────────────────────────────────────────────

def _import_route_log():
    """omha's own aggregator, or None. Newest plugin-cache copy wins."""
    cands = []
    for base in _OMHA_HOOKS:
        if not base.exists():
            continue
        if (base / "route_log.py").is_file():
            cands.append(base / "route_log.py")
        else:
            cands.extend(base.glob("*/*/hooks/route_log.py"))
    if not cands:
        return None
    newest = max(cands, key=lambda p: p.stat().st_mtime)
    sys.path.insert(0, str(newest.parent))
    try:
        import route_log  # type: ignore[import-not-found]  # path set above
        return route_log
    except ImportError:
        return None


def routing_summary(roots, route_log) -> dict:
    """{root: summary dict} using omha's dedup + summarize."""
    out = {}
    for root in roots:
        path = Path(root) / ".omha" / "routing.jsonl"
        if not path.is_file():
            continue
        records = route_log.load(path)
        if records:
            out[str(root)] = route_log.summarize(records)
    return out


# ─── table 4: per-session miss rate ─────────────────────────────────────────

def _transcript_dir(root) -> Path:
    """Claude Code slugs a project path by replacing every non-alphanumeric
    character with '-', not just the separators. Measured against the live
    directory: `/Users/kimseungmin/ksm_Obsidian` is stored as
    `-Users-kimseungmin-ksm-Obsidian` — the underscore is folded too, and
    `/.claude/` becomes `--claude-`. Folding only '/' finds nothing and every
    turn falls into the '(unmatched)' bucket."""
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(Path(root).resolve()))
    return Path.home() / ".claude" / "projects" / slug


def by_session(root, route_log) -> list:
    """[(session, turns, misses)] — session from the transcript owning the turn.

    Joins on turn_id == transcript uuid. Turns whose transcript is gone land in
    a single '(unmatched)' bucket rather than being dropped: a silent drop here
    would understate the denominator, which is the exact error this table exists
    to avoid."""
    path = Path(root) / ".omha" / "routing.jsonl"
    if not path.is_file():
        return []
    records = route_log.load(path) if route_log else _read_jsonl(path)
    by_turn = {r.get("turn_id"): r for r in records if r.get("turn_id")}

    owner: dict = {}
    tdir = _transcript_dir(root)
    if tdir.is_dir():
        for tp in tdir.glob("*.jsonl"):
            session = tp.stem
            for rec in _read_jsonl(tp):
                if rec.get("uuid") in by_turn:
                    owner[rec["uuid"]] = session

    agg: dict = {}
    for tid, rec in by_turn.items():
        cell = agg.setdefault(owner.get(tid, "(unmatched)"), [0, 0])
        cell[0] += 1
        cell[1] += 1 if rec.get("missing") else 0
    return sorted(((s, t, m) for s, (t, m) in agg.items()),
                  key=lambda row: (-row[2], -row[1]))


# ─── output ─────────────────────────────────────────────────────────────────

def _age(mtime) -> str:
    if not mtime:
        return "?"
    import datetime
    return datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")


def report(roots) -> str:
    settings = _load_settings()
    wired = wired_hooks(settings)
    loggers = logging_hooks(wired.keys())
    fired = guard_firings(roots)
    route_log = _import_route_log()

    L = []
    add = L.append

    add("=" * 68)
    add(f"harness telemetry — roots: {', '.join(str(r) for r in roots)}")
    add("=" * 68)

    add("")
    add("[1] guard firings   (last-seen is FILE mtime — records carry no ts)")
    add(f"    {'log':38s} {'count':>6s}  last seen")
    if not fired:
        add("    (no .omc/logs under any root)")
    for stem, rec in sorted(fired.items(), key=lambda kv: -kv[1]["count"]):
        add(f"    {stem:38s} {rec['count']:6d}  {_age(rec['mtime'])}")
        if len(rec["roots"]) > 1:
            for r, n in sorted(rec["roots"].items(), key=lambda kv: -kv[1]):
                add(f"        {n:5d}  {r}")

    cands, non_logging = silent_guards(wired, loggers, fired)
    add("")
    add(f"[2] wired hooks that never fired   ({len(wired)} wired total)")
    add("    a) logs, but zero records — the only retirement candidates:")
    if not cands:
        add("       (none)")
    for name, stems in cands:
        add(f"       {name:36s} -> {', '.join(stems)}")
    add("    b) never built to log — absence proves nothing about these:")
    add("       " + (", ".join(non_logging) if non_logging else "(none)"))

    add("")
    add("[3] routing verdicts   (via omha route_log.load/summarize)")
    if route_log is None:
        add("    route_log.py not found — table skipped, not re-implemented")
    else:
        summaries = routing_summary(roots, route_log)
        if not summaries:
            add("    (no .omha/routing.jsonl under any root)")
        for root, s in summaries.items():
            turns = s["turns"] or 1
            add(f"    {root}")
            add(f"      turns {s['turns']}   missing {s['missing']} "
                f"({s['missing'] / turns * 100:.1f}%)   "
                f"rerouted {s['rerouted']}   ANALYZE {s['analyze']}")
            for lane, n in s["lanes"].items():
                add(f"        {lane:24s} {n:5d}  {n / turns * 100:5.1f}%")

    add("")
    add("[4] miss rate by session   (turn_id joined to transcript uuid)")
    any_rows = False
    for root in roots:
        rows = by_session(root, route_log)
        if not rows:
            continue
        any_rows = True
        add(f"    {root}")
        add(f"      {'session':38s} {'turns':>5s} {'miss':>5s}  rate")
        for session, turns, miss in rows:
            add(f"      {session:38s} {turns:5d} {miss:5d}  "
                f"{miss / turns * 100:5.1f}%")
    if not any_rows:
        add("    (nothing to join)")

    add("")
    return "\n".join(L)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--root", action="append", default=None,
                        help="project root holding .omc/logs and/or .omha "
                             "(repeatable; default: cwd)")
    args = parser.parse_args(argv)
    roots = [os.path.expanduser(r) for r in (args.root or ["."])]
    print(report(roots))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

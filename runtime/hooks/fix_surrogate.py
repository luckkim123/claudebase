#!/usr/bin/env python3
"""Detect and repair lone UTF-16 surrogates in Claude Code session transcripts.

Root cause (diagnosed 2026-05-26): a model-generated tool_use input field
(e.g. AskUserQuestion.preview) can contain a lone surrogate codepoint
(U+D800-U+DFFF without its pair). It is stored in the JSONL as a \\uXXXX
escape, so the file looks valid, but every subsequent request re-serializes
the whole transcript and the Anthropic API rejects the body with
"invalid high surrogate in string", deadlocking the session.

This script replaces each lone surrogate with U+FFFD so the transcript can be
encoded as strict UTF-8 again. Used both as a manual tool and as the core of
an auto-repair hook.

Usage:
    fix_surrogate.py --check  FILE...     # exit 1 if any lone surrogate found
    fix_surrogate.py --fix    FILE...     # repair in place (backup .bak unless --no-backup)
    fix_surrogate.py --check-current      # read $CLAUDE_TRANSCRIPT_PATH (hook mode)
    fix_surrogate.py --fix-current        # repair $CLAUDE_TRANSCRIPT_PATH (hook mode)
"""
import argparse
import json
import os
import sys
import time

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent))
import hooklog  # noqa: E402

REPLACEMENT = "�"


def has_lone_surrogate(s: str) -> bool:
    return any(0xD800 <= ord(ch) <= 0xDFFF for ch in s)


def scrub(value):
    """Recursively replace lone surrogates in any string inside value. Returns (new, count)."""
    count = 0
    if isinstance(value, str):
        if has_lone_surrogate(value):
            new = "".join(
                REPLACEMENT if 0xD800 <= ord(ch) <= 0xDFFF else ch for ch in value
            )
            return new, sum(1 for ch in value if 0xD800 <= ord(ch) <= 0xDFFF)
        return value, 0
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            nv, c = scrub(v)
            out[k] = nv
            count += c
        return out, count
    if isinstance(value, list):
        out = []
        for v in value:
            nv, c = scrub(v)
            out.append(nv)
            count += c
        return out, count
    return value, 0


def strict_encodable(obj) -> bool:
    """True if obj can be encoded as the API does (real UTF-8 bytes, no lone surrogates)."""
    try:
        json.dumps(obj, ensure_ascii=False).encode("utf-8")
        return True
    except UnicodeEncodeError:
        return False


def process_file(path: str, fix: bool, backup: bool):
    """Returns (total_lone_surrogates, fixed_line_numbers)."""
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    total = 0
    fixed_lines = []
    out_lines = list(lines)
    for i, line in enumerate(lines):
        s = line.rstrip("\n")
        if not s:
            continue
        try:
            obj = json.loads(s)
        except json.JSONDecodeError:
            continue
        if strict_encodable(obj):
            continue  # no lone surrogate anywhere in this record
        new_obj, count = scrub(obj)
        total += count
        if count:
            fixed_lines.append(i)
            if fix:
                out_lines[i] = json.dumps(new_obj, ensure_ascii=False) + "\n"
    if fix and fixed_lines:
        if backup:
            ts = time.strftime("%Y%m%d_%H%M%S")
            bak = f"{path}.{ts}.surrogate.bak"
            with open(bak, "w", encoding="utf-8") as f:
                f.writelines(lines)
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(out_lines)
    return total, fixed_lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--check", action="store_true", help="report only, exit 1 if found")
    ap.add_argument("--fix", action="store_true", help="repair in place")
    ap.add_argument("--check-current", action="store_true")
    ap.add_argument("--fix-current", action="store_true")
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()

    files = list(args.files)
    hook_cwd = None
    hook_session_id = None
    if args.check_current or args.fix_current:
        # Claude Code hooks pass a JSON object on stdin containing "transcript_path".
        # Fall back to env vars for manual/testing use.
        tp = None
        try:
            if not sys.stdin.isatty():
                payload = sys.stdin.read()
                if payload.strip():
                    data = json.loads(payload)
                    tp = data.get("transcript_path")
                    hook_cwd = data.get("cwd")
                    hook_session_id = data.get("session_id")
        except Exception:  # noqa: BLE001 — a raising hook blocks the user's turn; failing open is the contract
            tp = None
        tp = tp or os.environ.get("CLAUDE_TRANSCRIPT_PATH") or os.environ.get("TRANSCRIPT_PATH")
        if not tp or not os.path.exists(tp):
            return 0  # hook context without a transcript: no-op, never block
        files.append(tp)

    fix = args.fix or args.fix_current
    found_any = False
    for path in files:
        if not os.path.exists(path):
            print(f"skip (missing): {path}", file=sys.stderr)
            continue
        total, fixed = process_file(path, fix=fix, backup=not args.no_backup)
        if total:
            found_any = True
            verb = "fixed" if fix else "found"
            print(f"{verb} {total} lone surrogate(s) in {path} (lines {fixed})", file=sys.stderr)
            hooklog.fire("fix_surrogate.jsonl", hook_cwd, hook_session_id,
                         repaired=(total if fix else 0), found=total)
    # check mode: nonzero exit signals detection; fix mode: always 0 (never block the session)
    if (args.check or args.check_current) and found_any:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

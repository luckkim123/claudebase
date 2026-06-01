#!/usr/bin/env python3
"""installer/lib/settings_verify.py — assert config/settings.json still carries
every critical key the Claude Code CLI is known to silently drop on re-serialize.

Single source of truth shared by two out-of-settings guards (a guard that lived
*inside* settings.json's own hooks block would be deleted by the very shrink it
detects — the self-deletion trap):
  - installer/githooks/pre-commit  → blocks committing a shrunk file (enforcement)
  - installer/lib/drift.sh         → loud CRITICAL on the next install (safety net)

Reads the manifest config/settings.critical.json and checks: every named plugin
present (membership, NOT a count — a count passes when the CLI swaps one plugin
for another), every marketplace, the omcHud.layout sub-keys, the required
scalars, and that each defense-hook marker string still appears in some hook
command.

Usage:
  settings_verify.py <settings.json>        # check a file on disk (drift.sh)
  git show :config/settings.json | settings_verify.py -   # check staged blob (hook)

Exit 0 = all invariants hold. Exit 1 = one or more missing (lists them on stderr).
Exit 2 = usage / parse error (manifest or input unreadable).
Pure stdlib (json, sys, os, re) — portable across macOS / Linux / Windows git-bash.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "..", "..", "config", "settings.critical.json")


def _load(src):
    """Return parsed JSON from a path, or from stdin when src == '-'."""
    if src == "-":
        return json.load(sys.stdin)
    with open(src, encoding="utf-8") as fh:
        return json.load(fh)


def verify(settings):
    """Return a list of human-readable missing-key strings (empty == all good)."""
    try:
        manifest = _load(MANIFEST)
    except Exception as exc:  # manifest must be readable — a broken manifest is fatal
        return [f"FATAL: cannot read manifest {MANIFEST}: {exc}"]

    missing = []

    # 1. defense-hook markers — each must appear in some hook command string.
    all_cmds = []
    for groups in (settings.get("hooks") or {}).values():
        for grp in groups if isinstance(groups, list) else []:
            for h in grp.get("hooks", []):
                all_cmds.append(h.get("command", ""))
    blob = "\n".join(all_cmds)
    for event, markers in (manifest.get("hookMarkers") or {}).items():
        if event.startswith("_"):
            continue
        for marker in markers:
            if marker not in blob:
                missing.append(f"hook marker {marker} (event {event})")

    # 2. plugins — membership, not count.
    plugins = settings.get("enabledPlugins") or {}
    for p in manifest.get("requiredPlugins", []):
        if p not in plugins:
            missing.append(f"plugin {p}")

    # 3. marketplaces.
    mkts = settings.get("extraKnownMarketplaces") or {}
    for m in manifest.get("requiredMarketplaces", []):
        if m not in mkts:
            missing.append(f"marketplace {m}")

    # 4. omcHud.layout sub-keys (the rich `main[]` layout is dropped on HUD change).
    layout = (settings.get("omcHud") or {}).get("layout") or {}
    for k in manifest.get("requiredHudLayout", []):
        if k not in layout or (isinstance(layout.get(k), list) and not layout[k]):
            missing.append(f"omcHud.layout.{k}")

    # 5. scalars.
    for s in manifest.get("requiredScalars", []):
        if s not in settings:
            missing.append(f"scalar {s}")

    return missing


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: settings_verify.py <settings.json|->\n")
        return 2
    try:
        settings = _load(argv[1])
    except Exception as exc:
        sys.stderr.write(f"settings_verify: cannot parse {argv[1]}: {exc}\n")
        return 2

    missing = verify(settings)
    if not missing:
        return 0

    sys.stderr.write(
        "settings_verify: config/settings.json is MISSING critical keys "
        "(the Claude CLI likely re-serialized and dropped them):\n"
    )
    for m in missing:
        sys.stderr.write(f"  - {m}\n")
    sys.stderr.write(
        "\nRestore from the canonical committed version:\n"
        "  installer/bin/restore-settings.sh\n"
        "  (or: git -C ~/claudebase checkout -- config/settings.json)\n"
        "If you INTENTIONALLY changed a critical key, update the manifest "
        "config/settings.critical.json in the same commit.\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

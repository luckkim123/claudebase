#!/usr/bin/env python3
"""Resolve this machine's installed plugin paths into env vars for the experiments.

    eval "$(python3 eval/scripts/plugin_env.py)"   # then: coder-eval run ...
    python3 eval/scripts/plugin_env.py --check      # verify only, print a table

Why this exists: coder-eval's plugin config is a bare `{type: "local", path: str}`
— there is no marketplace-or-name form and no "latest" selector, so an experiment
that names its plugins has to spell out a filesystem path. Written literally, that
path carries both a home directory and a version number, and both go stale:

  - The home directory makes the experiment unrunnable on any other machine.
    claudebase ships to every machine, so a committed `/Users/<someone>/...` is a
    distribution bug, not a local convenience.
  - The version pins rot in the worst possible way. Old versions stay in
    `~/.claude/plugins/cache/<name>/<version>/` after an upgrade, so a stale pin
    still *resolves* — the run succeeds and measures a harness that no longer
    exists. Measured 2026-08-17: 4 of the 8 pins in harness-discipline.yaml named
    superseded versions (omd 0.6.6 vs 0.7.0, oms 0.13.1 vs 0.14.0, omp 0.11.1 vs
    0.12.0, omha db6099a0c006 vs 8a1aeb2e9c48) and every one of those directories
    was still on disk.

`utils.process_plugins` (coder_eval/utils.py:42) expands `$VAR` / `${VAR}` in
plugin paths, so the fix is to commit `${CE_PLUGIN_OMD}` and resolve it here, per
machine, at run time.

This script is the loud half of that. coder-eval only *warns* about an unset var;
the literal `${CE_PLUGIN_OMD}` then fails to resolve as a directory and the arm
quietly runs with fewer plugins than it claims — the same silent-success class the
version pins had. So this exits non-zero and names every missing plugin rather
than emitting a partial environment.

`runtime/hooks/loop_lint.py:139` reads the same file for its own purpose. It is
not reused here because it filters to `oh-my-*`, and the treatment arm also needs
`ponytail` and `superpowers`; widening a shipped lint hook to serve eval tooling
couples them for less than twenty lines. If the installed_plugins.json schema ever
changes, both readers need the edit.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

INSTALLED = Path.home() / ".claude" / "plugins" / "installed_plugins.json"

# env var suffix -> plugin name as it appears in installed_plugins.json
PLUGINS = {
    "OMC": "oh-my-claudecode",
    "PONYTAIL": "ponytail",
    "SUPERPOWERS": "superpowers",
    "OMHA": "oh-my-heroacademia",
    "OMP": "oh-my-project",
    "OMX": "oh-my-experiments",
    "OMD": "oh-my-docs",
    "OMS": "oh-my-scholar",
}
PREFIX = "CE_PLUGIN_"


def resolve() -> tuple[dict[str, str], list[str]]:
    """({VAR: path}, [problems]) — a plugin is a problem if unlisted or absent."""
    try:
        entries = json.loads(INSTALLED.read_text(encoding="utf-8"))["plugins"]
    except (OSError, json.JSONDecodeError, KeyError) as e:
        return {}, [f"cannot read {INSTALLED}: {e}"]

    # keys are "<name>@<marketplace>"; the marketplace differs per machine, match on name
    by_name = {k.split("@", 1)[0]: v for k, v in entries.items()}
    resolved: dict[str, str] = {}
    problems: list[str] = []
    for suffix, name in PLUGINS.items():
        installs = by_name.get(name)
        if not installs:
            problems.append(f"{name}: not listed in {INSTALLED.name}")
            continue
        path = installs[0].get("installPath", "")
        if not path or not Path(path).is_dir():
            problems.append(f"{name}: installPath not on disk ({path or '<empty>'})")
            continue
        resolved[PREFIX + suffix] = path
    return resolved, problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="print a human-readable table instead of shell exports")
    args = ap.parse_args(argv)

    resolved, problems = resolve()
    if problems:
        print("plugin_env: cannot build a complete environment:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        print("\nInstall the missing plugins, or drop them from the experiment's "
              "treatment arm. Emitting a partial environment would let the run "
              "succeed while measuring fewer plugins than the arm claims.",
              file=sys.stderr)
        return 1

    if args.check:
        width = max(len(k) for k in resolved)
        for var, path in resolved.items():
            print(f"{var:<{width}}  {path}")
        return 0

    for var, path in resolved.items():
        print(f"export {var}={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
USER_SETTINGS = Path.home() / ".claude" / "settings.json"

# Fixed, machine-independent path the experiment YAMLs commit as their
# `claude_settings:` string. The *content* is resolved per machine at run time
# (same trap as the plugin paths above: a committed list of this machine's
# plugin ids would silently stop covering another machine's enabledPlugins).
NEUTRALIZE = Path("/tmp/claudebase-eval-neutralize-settings.json")

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


def write_neutralize_settings(
    out: Path = NEUTRALIZE, user_settings: Path = USER_SETTINGS
) -> tuple[Path | None, str | None]:
    """Write the per-machine `--settings` file the A/B yamls point at.

    `enabledPlugins` must be an explicit per-key false-map. Measured 2026-08-22
    (claudebase-hooks-ab pre-Step-4 probe): an empty `{}` at the `--settings`
    layer deep-MERGES with the user layer's populated map — a no-op, the omha
    UserPromptSubmit injection still fired in the treatment arm. A per-key
    `false` wins the merge; the same probe re-run with this false-map showed
    zero plugin skills while the user-layer hooks kept firing.

    Returns (path, problem) — problem is non-None only when the user settings
    file exists but cannot be parsed (a missing file legitimately means there
    is nothing to disable).
    """
    enabled: dict = {}
    if user_settings.exists():
        try:
            enabled = json.loads(user_settings.read_text(encoding="utf-8")).get(
                "enabledPlugins", {}
            )
        except (OSError, json.JSONDecodeError) as e:
            return None, f"cannot read {user_settings}: {e}"
    payload = {
        "enabledPlugins": {k: False for k in enabled},
        # Scalar neutralization (see the yaml's SCALAR NEUTRALIZATION note):
        # each value is the built-in default the ["project"]-only arm already
        # runs with implicitly, pinned so the user-layer arm cannot diverge.
        "outputStyle": "default",
        "alwaysThinkingEnabled": True,
        "effortLevel": "unset",
    }
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out, None


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

    neut_path, neut_problem = write_neutralize_settings()
    if neut_problem:
        print(f"plugin_env: cannot write neutralize settings: {neut_problem}",
              file=sys.stderr)
        return 1

    for var, path in resolved.items():
        print(f"export {var}={path}")
    print(f"# neutralize-settings written: {neut_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

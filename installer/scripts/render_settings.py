#!/usr/bin/env python3
"""Render ~/.claude/settings.json from the repo baseline + per-machine overrides.

Claude Code reads user-scope settings from exactly one file:
`~/.claude/settings.json`. Its setting sources are `user` / `project` / `local`
(`claude --setting-sources`), where `local` means the *project's*
`.claude/settings.local.json` — there is no user-scope `settings.local.json`
source. Verified 2026-07-27 against CLI 2.1.220: writing invalid JSON into
`~/.claude/settings.local.json` and running `claude plugin list` produces no
error at all, because the file is never parsed by the CLI.

claudebase used to symlink `~/.claude/settings.json -> config/settings.json`,
which had two consequences:

1. every CLI write (`/model`, `claude plugin enable -s user`, OMC's HUD preset)
   landed in the tracked lab baseline, and
2. `~/.claude/settings.local.json` — which the README, ARCHITECTURE doc and the
   template's own `_comment` all described as the per-machine layer — did
   nothing whatsoever.

A blanket `git checkout -- config/settings.json` to clean up (1) therefore also
reverted whatever (2) was believed to be holding. That is how four opt-in
plugins sat installed-but-*disabled* for two days while `settings.local.json`
still listed them `true`.

This module renders the file instead of linking it:

    ~/.claude/settings.json = deep_merge(config/settings.json, settings.local.json)

so the per-machine layer every doc already promised is actually real, and the
tracked baseline stops absorbing personal preferences.

Before overwriting, whatever the CLI wrote into the previous render that the
current sources do not explain is *captured* into `settings.local.json`, so a
preference set with `/model` survives the next install run instead of being
silently clobbered.

Known ceiling: capture is computed against the expected render, not against a
recorded snapshot of the previous one. Deleting an override therefore means
deleting it from `settings.local.json` *and* `~/.claude/settings.json` — editing
only the former lets the next run re-capture it. Record a render snapshot if
that ever becomes a real annoyance.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

# Keys that are claudebase installer bookkeeping, not Claude Code settings.
# They live in settings.local.json but must not reach the rendered file.
# Anything starting with "_" is documentation-by-convention in this repo's
# templates (`_comment`, `_optional_plugins_note`, `_remove_this_example`).
INSTALLER_ONLY_KEYS = frozenset({"personalRepos"})

# Top-level keys the tracked baseline owns outright: never captured into the
# per-machine layer, however much the previous render disagrees.
#
# `hooks` is here because capture is exactly wrong for it in both directions.
# The CLI's re-serialization DROPS hook blocks it does not recognize (the whole
# reason config/settings.critical.json asserts hookMarkers), so capturing that
# difference would freeze a *shrunk* hooks list into settings.local.json, where
# it wins the merge and permanently suppresses the baseline hook the guard is
# supposed to protect. And because `hooks` values are lists, deep_merge replaces
# rather than merges them, so one captured entry silences every later addition.
#
# Observed 2026-08-10 while adding the two graphify guards: the machine's
# previous render predated them, the old two-block PreToolUse list was captured
# as a "per-machine override", and the new hooks never reached the rendered
# file — silently, since capture is a normal, non-error path.
BASELINE_OWNED_KEYS = frozenset({"hooks"})


def _is_installer_only(key: str) -> bool:
    return key.startswith("_") or key in INSTALLER_ONLY_KEYS


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge `override` on top of `base`; `override` wins on conflict.

    Dicts merge key-by-key so a per-machine `enabledPlugins` entry adds to the
    baseline map instead of replacing it. Everything else (scalars, lists) is
    replaced wholesale.
    """
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def diff_overrides(existing: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    """Return the parts of `existing` that `expected` does not account for.

    Recurses into dicts so a single CLI-added `enabledPlugins` entry is captured
    on its own rather than freezing the whole baseline map into the per-machine
    file. Keys present in `expected` but missing from `existing` are ignored:
    the baseline is authoritative, so a removal is never treated as an override.
    """
    out: dict[str, Any] = {}
    for key, value in existing.items():
        if key not in expected:
            out[key] = value
        elif isinstance(value, dict) and isinstance(expected[key], dict):
            nested = diff_overrides(value, expected[key])
            if nested:
                out[key] = nested
        elif value != expected[key]:
            out[key] = value
    return out


def strip_installer_keys(settings: dict[str, Any]) -> dict[str, Any]:
    """Drop claudebase-only bookkeeping keys, recursively.

    `enabledPlugins` in the shipped template carries a `_remove_this_example`
    placeholder, so the nested pass is what stops a bogus plugin id reaching
    the rendered file on a machine that copied the template verbatim.
    """
    out: dict[str, Any] = {}
    for key, value in settings.items():
        if _is_installer_only(key):
            continue
        out[key] = strip_installer_keys(value) if isinstance(value, dict) else value
    return out


def with_omc_state_dir(base: dict[str, Any]) -> dict[str, Any]:
    """Return `base` with a machine-resolved `env.OMC_STATE_DIR` default.

    Computed at render time rather than written into `config/settings.json`,
    because neither form survives the tracked file. `~` and `$HOME` do NOT expand
    in the `env` block (docs/ARCHITECTURE.md) and OMC joins the value verbatim
    (`path.join`, oh-my-claudecode scripts/lib/state-root.mjs), so a literal `~`
    would create a directory *named* `~` in whatever the process's cwd happens to
    be. A tracked absolute path is equally wrong: this repo ships to every
    machine, and hardcoding one is exactly what config/CLAUDE.md forbids.

    Why centralise the state at all: OMC keeps `.omc/` beside the checkout, so in
    a linked worktree the notepad, plans, research and handoffs are deleted with
    `git worktree remove`. A single-checkout user is unaffected either way — the
    state simply moves out of the repo — which is what makes this safe to default.

    `setdefault` keeps it a *default*: `settings.local.json` merges on top, so a
    machine that wants the state somewhere else still wins.
    """
    out = dict(base)
    env = dict(out.get("env", {}))
    env.setdefault("OMC_STATE_DIR", str(Path.home() / ".omc-state"))
    out["env"] = env
    return out


def _hook_commands(settings: dict[str, Any]) -> list[str]:
    """Every `hooks[*][*].hooks[*].command` string, order preserved."""
    out: list[str] = []
    for groups in (settings.get("hooks") or {}).values():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            for hook in group.get("hooks") or []:
                cmd = hook.get("command") if isinstance(hook, dict) else None
                if isinstance(cmd, str):
                    out.append(cmd)
    return out


def dropped_hook_commands(
    existing: dict[str, Any] | None, rendered: dict[str, Any]
) -> list[str]:
    """Hook commands the previous render had that this one does not.

    `hooks` is in BASELINE_OWNED_KEYS, so anything a third party wrote straight
    into the rendered file is discarded rather than captured — deliberately, for
    the reason recorded on that constant. Discarding it silently is the part that
    surprises people: an IDE integration or an MCP installer
    writes its hooks into ~/.claude/settings.json, the next install.sh replaces
    the file, and the tool stops working with nothing announcing why.

    Detection is by command string, so a hook that merely moved between events is
    not reported. Naming the count is the whole feature — the fix (relaunch the
    tool, or move the hook into config/settings.json) belongs to the user.
    """
    if not existing:
        return []
    kept = set(_hook_commands(rendered))
    return [cmd for cmd in _hook_commands(existing) if cmd not in kept]


def _report_dropped_hooks(stray: list[str], *, would: bool) -> None:
    """Name the count and the fix; the user decides what to do about it."""
    if not stray:
        return
    print(
        f"render-settings: {'would drop' if would else 'dropped'} {len(stray)} hook "
        "command(s) that were in the previous render but are not in the claudebase "
        "baseline."
    )
    for cmd in stray[:3]:
        flat = " ".join(cmd.split())
        print(f"                 - {flat[:70]}{'...' if len(flat) > 70 else ''}")
    if len(stray) > 3:
        print(f"                 - ... and {len(stray) - 3} more")
    print(
        "                 Tools that inject their own hooks (IDE integrations, MCP "
        "installers) write straight into this file, and a render "
        "replaces it. Relaunch that tool so it re-injects, or move the hook into "
        "config/settings.json to make it survive."
    )


def _load(path: Path) -> dict[str, Any]:
    """Read a JSON object, returning {} for a missing file.

    A malformed file is a hard error: silently treating it as empty is how a
    per-machine layer disappears without anyone noticing, which is the exact
    failure this module exists to end.
    """
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"render_settings: {path} is not valid JSON: {exc}") from exc
    if not isinstance(loaded, dict):
        raise SystemExit(f"render_settings: {path} must contain a JSON object")
    return loaded


def _dump(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def plan(
    base: dict[str, Any],
    local: dict[str, Any],
    existing: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return `(rendered, new_local)` for the given inputs.

    Pure decision layer — no filesystem access, so tests can drive it directly.
    `existing` is the previous render (None when there is none, or when the old
    symlink layout is still in place and its content is just the baseline).
    """
    expected = deep_merge(base, strip_installer_keys(local))
    captured = diff_overrides(existing, expected) if existing else {}
    for key in BASELINE_OWNED_KEYS:
        captured.pop(key, None)
    new_local = deep_merge(local, captured) if captured else local
    rendered = deep_merge(base, strip_installer_keys(new_local))
    return rendered, new_local


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render ~/.claude/settings.json from the repo baseline "
        "plus per-machine overrides."
    )
    parser.add_argument("--base", required=True, help="repo config/settings.json")
    parser.add_argument("--local", required=True, help="~/.claude/settings.local.json")
    parser.add_argument("--out", required=True, help="~/.claude/settings.json")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would change without writing anything",
    )
    args = parser.parse_args(argv)

    base_path, local_path, out_path = Path(args.base), Path(args.local), Path(args.out)
    base = with_omc_state_dir(_load(base_path))

    # The legacy layout symlinked `out` at `base`, so its content carries no
    # per-machine information to capture — only the migration itself matters.
    was_symlink = out_path.is_symlink()
    existing = None if was_symlink else (_load(out_path) if out_path.exists() else None)

    local = _load(local_path)
    rendered, new_local = plan(base, local, existing)
    captured = new_local is not local

    # Idempotency contract (tests/smoke/test_install_idempotent.sh): a run that
    # changes nothing must write nothing and print nothing, so the caller can
    # treat any output as "something actually happened".
    if not was_symlink and not captured and existing == rendered:
        return 0

    stray = dropped_hook_commands(existing, rendered)

    if args.dry_run:
        if was_symlink:
            print(f"render-settings: would replace symlink with rendered file: {out_path}")
        if captured:
            print(f"render-settings: would capture per-machine keys into {local_path}")
        print(f"render-settings: would write {out_path}")
        # Reported here too, and this is the mode where it matters most: a
        # dry-run is what someone reads *before* deciding to render, so hiding
        # the one warning they would act on defeats the flag.
        _report_dropped_hooks(stray, would=True)
        return 0

    if captured:
        _dump(local_path, new_local)
        moved = ", ".join(sorted(diff_overrides(new_local, local)))
        print(f"render-settings: captured per-machine keys -> settings.local.json ({moved})")

    if was_symlink:
        out_path.unlink()
        print(f"render-settings: replaced symlink with rendered file: {out_path}")

    _dump(out_path, rendered)
    print(f"render-settings: wrote {out_path}")

    _report_dropped_hooks(stray, would=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())

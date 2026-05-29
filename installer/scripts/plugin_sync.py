#!/usr/bin/env python3
"""Plugin sync planner + applier, extracted from install.sh.

Two-phase design separates *what to do* from *doing it*:

  plan(claude_home, metadata_path, platform, prune=False) -> list[Decision]
      Pure read of settings.json + installed_plugins.json + metadata.
      No side effects. Easy to unit-test.

  apply(decisions) -> int                       (CLI-only)
      Invokes `claude plugin install/uninstall` and runs post-install hooks.

The CLI (`__main__`) is install.sh's only entry: it loads inputs, plans,
prints a tab-separated report, and applies unless --dry-run.

Inputs:
  $HOME/.claude/settings.json
    enabledPlugins, extraKnownMarketplaces, settings.local.json optional
  $HOME/.claude/plugins/installed_plugins.json
  installer/marketplace-metadata.json
    os and post_install keys per marketplace name

Outputs (on stdout, one decision per line, tab-separated):
  <action>\\t<plugin>\\t<current_scope>\\t<reason>

Exit code:
  0 always (warnings are surfaced via WARNING: lines; install.sh keeps going)
"""
from __future__ import annotations

import argparse
import json
import os
import platform as _platform
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable, Optional


# ---------- types ----------

class Action(Enum):
    SKIP_OK = "skip-ok"                # already user-scope and enabled
    INSTALL = "install"                # enabled but not installed
    REINSTALL = "reinstall"            # installed at wrong scope (project/local/etc.)
    SKIP_OS_GATE = "skip-os-gate"      # marketplace not allowed on this OS
    DRIFT_KEPT = "drift-kept"          # installed at user scope but not in any enabled set
    DRIFT_PRUNED = "drift-pruned"      # same, but --prune flag passed -> uninstall


@dataclass
class Decision:
    action: Action
    plugin: str
    current_scope: str
    reason: str


# ---------- IO helpers ----------

def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _enabled_map(settings: dict) -> dict:
    return {k: v for k, v in (settings.get("enabledPlugins") or {}).items() if v}


def _marketplace_of(plugin: str) -> str:
    # Plugin names look like "name@marketplace" — empty marketplace if not found.
    return plugin.rsplit("@", 1)[1] if "@" in plugin else ""


def _current_scope(plugin: str, installed: dict) -> str:
    entries = installed.get(plugin) or []
    return entries[0].get("scope", "none") if entries else "none"


# ---------- policy ----------

def _os_allowed(marketplace: str, platform: str, metadata: dict) -> bool:
    cfg = metadata.get(marketplace) or {}
    allow = cfg.get("os")
    # Unknown marketplaces default to allow-all (don't gate what we don't know).
    return allow is None or platform in allow


def marketplaces_to_register(claude_home: Path, metadata_path: Path,
                             platform: str) -> set:
    """Set of marketplaces referenced by enabled plugins, filtered by OS gate."""
    settings = _read_json(claude_home / "settings.json")
    metadata = _read_json(metadata_path)
    needed = set()
    for plugin in _enabled_map(settings):
        mk = _marketplace_of(plugin)
        if not mk:
            continue
        if _os_allowed(mk, platform, metadata):
            needed.add(mk)
    return needed


def post_install_for(plugin: str, metadata: dict) -> list:
    mk = _marketplace_of(plugin)
    return list((metadata.get(mk) or {}).get("post_install") or [])


# ---------- planner ----------

def plan(claude_home: Path, metadata_path: Path, platform: str,
         prune: bool = False) -> list:
    """Compute the ordered list of decisions for this machine."""
    settings = _read_json(claude_home / "settings.json")
    local = _read_json(claude_home / "settings.local.json")
    installed = _read_json(claude_home / "plugins" / "installed_plugins.json").get("plugins") or {}
    metadata = _read_json(metadata_path)

    enabled = _enabled_map(settings)
    enabled_local = _enabled_map(local)

    decisions: list = []

    # Enabled plugins (common + per-machine).
    seen = set()
    for plugin in list(enabled.keys()) + [k for k in enabled_local if k not in enabled]:
        seen.add(plugin)
        mk = _marketplace_of(plugin)
        if not _os_allowed(mk, platform, metadata):
            decisions.append(Decision(
                action=Action.SKIP_OS_GATE, plugin=plugin, current_scope="-",
                reason=f"marketplace '{mk}' not allowed on {platform}",
            ))
            continue
        scope = _current_scope(plugin, installed)
        if scope == "user":
            decisions.append(Decision(Action.SKIP_OK, plugin, scope, "already user-scope"))
        elif scope == "none":
            decisions.append(Decision(Action.INSTALL, plugin, scope, "not installed"))
        else:
            decisions.append(Decision(Action.REINSTALL, plugin, scope,
                                      f"installed at wrong scope ({scope})"))

    # Drift detection: user-scope installs not in any enabled set.
    for plugin, entries in installed.items():
        if plugin in seen:
            continue
        if not any((e.get("scope") == "user") for e in entries):
            continue
        action = Action.DRIFT_PRUNED if prune else Action.DRIFT_KEPT
        decisions.append(Decision(action, plugin, "user",
                                  "not in enabledPlugins (any scope)"))

    return decisions


# ---------- applier (CLI side effects) ----------

def _run(cmd: list, dry_run: bool) -> int:
    if dry_run:
        print(f"[dry-run] {' '.join(cmd)}")
        return 0
    return subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode


def install_omc_shell_cli(dry_run: bool) -> str:
    """Post-install hook: ensure `omc` shell CLI is on PATH."""
    if subprocess.run(["which", "omc"], stdout=subprocess.DEVNULL).returncode == 0:
        return "omc shell CLI: already present"
    if subprocess.run(["which", "npm"], stdout=subprocess.DEVNULL).returncode != 0:
        return "omc shell CLI: WARNING — npm not found; install manually"
    rc = _run(["npm", "i", "-g", "oh-my-claude-sisyphus@latest"], dry_run)
    return "omc shell CLI: installed" if rc == 0 else "omc shell CLI: WARNING — npm install failed"


POST_INSTALL_REGISTRY: "dict[str, Callable[[bool], str]]" = {
    "install_omc_shell_cli": install_omc_shell_cli,
}


def apply(decisions: Iterable, metadata_path: Path, dry_run: bool) -> "tuple[int, int, int, int]":
    """Execute decisions. Returns (ok, fixed, removed, failed) counters."""
    metadata = _read_json(metadata_path)
    ok = fixed = removed = failed = 0
    for d in decisions:
        if d.action is Action.SKIP_OK:
            ok += 1
        elif d.action is Action.INSTALL:
            rc = _run(["claude", "plugin", "install", "-s", "user", d.plugin], dry_run)
            if rc == 0:
                fixed += 1
                _run_post_install(d.plugin, metadata, dry_run)
            else:
                failed += 1
        elif d.action is Action.REINSTALL:
            _run(["claude", "plugin", "uninstall", "-s", d.current_scope, "-y", d.plugin], dry_run)
            rc = _run(["claude", "plugin", "install", "-s", "user", d.plugin], dry_run)
            if rc == 0:
                fixed += 1
                _run_post_install(d.plugin, metadata, dry_run)
            else:
                failed += 1
        elif d.action is Action.SKIP_OS_GATE:
            # Log via stdout in main; nothing to count here.
            pass
        elif d.action is Action.DRIFT_KEPT:
            pass  # only printed
        elif d.action is Action.DRIFT_PRUNED:
            rc = _run(["claude", "plugin", "uninstall", "-s", "user", "-y", d.plugin], dry_run)
            removed += 1 if rc == 0 else 0
            if rc != 0:
                failed += 1
    return ok, fixed, removed, failed


def _run_post_install(plugin: str, metadata: dict, dry_run: bool) -> None:
    for name in post_install_for(plugin, metadata):
        fn = POST_INSTALL_REGISTRY.get(name)
        if fn is None:
            print(f"[install] WARNING: post-install '{name}' not in registry")
            continue
        print(f"[install] {fn(dry_run)}")


# ---------- marketplace registration ----------

def ensure_marketplaces(claude_home: Path, metadata_path: Path,
                        platform: str, dry_run: bool) -> None:
    settings = _read_json(claude_home / "settings.json")
    extra = settings.get("extraKnownMarketplaces") or {}
    needed = marketplaces_to_register(claude_home, metadata_path, platform)
    if not needed:
        return
    # `claude plugin marketplace list` returns lines like "  ❯ <name>".
    try:
        out = subprocess.check_output(
            ["claude", "plugin", "marketplace", "list"], stderr=subprocess.DEVNULL, text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        out = ""
    present = {ln.split()[-1] for ln in out.splitlines() if "❯" in ln}
    for name in sorted(needed - present):
        cfg = (extra.get(name) or {}).get("source") or {}
        target = cfg.get("repo") or cfg.get("url")
        if not target:
            print(f"[install] WARNING: marketplace '{name}' missing source/target in settings.json")
            continue
        print(f"[install] adding marketplace: {name} ({target})")
        _run(["claude", "plugin", "marketplace", "add", target], dry_run)


# ---------- CLI ----------

def _detect_platform() -> str:
    s = _platform.system()
    return {"Darwin": "macos", "Linux": "linux", "Windows": "windows"}.get(s, s.lower())


def _emit_report(decisions: Iterable) -> None:
    for d in decisions:
        print(f"{d.action.value}\t{d.plugin}\t{d.current_scope}\t{d.reason}")


def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(description="Plugin sync planner+applier")
    p.add_argument("--report", action="store_true", help="print decisions only")
    p.add_argument("--apply", action="store_true", help="execute decisions")
    p.add_argument("--prune", action="store_true", help="uninstall drift (else warn-only)")
    p.add_argument("--dry-run", action="store_true", help="print intended actions, do not execute")
    p.add_argument("--metadata", default=None, help="path to marketplace-metadata.json")
    args = p.parse_args(argv)

    claude_home = Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude"))
    metadata_path = Path(args.metadata) if args.metadata else (
        Path(__file__).resolve().parent.parent / "marketplace-metadata.json"
    )
    platform = _detect_platform()

    if not (claude_home / "settings.json").exists():
        print("[install] skip plugin sync: settings.json not found")
        return 0

    decisions = plan(claude_home, metadata_path, platform, prune=args.prune)

    if args.report and not args.apply:
        _emit_report(decisions)
        return 0

    ensure_marketplaces(claude_home, metadata_path, platform, dry_run=args.dry_run)
    ok, fixed, removed, failed = apply(decisions, metadata_path, dry_run=args.dry_run)
    kept = sum(1 for d in decisions if d.action is Action.DRIFT_KEPT)
    for d in decisions:
        if d.action is Action.DRIFT_KEPT:
            print(f"plugin drift (kept): {d.plugin} — register in settings.local.json "
                  "or re-run with --prune-plugins to remove")
        elif d.action is Action.SKIP_OS_GATE:
            print(f"skipping (os-gate): {d.plugin} — {d.reason}")
        elif d.action in (Action.INSTALL, Action.REINSTALL):
            print(f"plugin reinstalled (user): {d.plugin}")

    print(f"plugin sync: {ok} already user-scope, {fixed} fixed, "
          f"{removed} removed, {kept} drift-kept, {failed} failed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

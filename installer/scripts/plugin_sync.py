#!/usr/bin/env python3
"""Plugin sync orchestration for claudebase installer.

Replaces install.sh:259-478 `sync_plugins()` (220 LOC of bash + embedded
Python heredoc) with a single Python module that is unit-testable and
operates on two SSOTs:

- `config/settings.json` — `enabledPlugins` and `extraKnownMarketplaces`
  (the Claude Code-canonical view of what should be installed)
- `installer/marketplace-metadata.json` — installer-only fields (`os`
  gates, `post_install` hook names) that Claude Code's schema does not
  formally support

The module exports a pure decision layer (`decide_plugin`,
`marketplace_allowed_on`, `find_drift`, `plan_actions`) and a thin
side-effect layer (`apply`, `run_post_install`). Tests drive the decision
layer; the side-effect layer wraps `claude plugin install/uninstall`.

Idempotency contract: re-running with no changes produces zero install
actions and zero stdout `installing:` lines (consumed by smoke test).
"""
from __future__ import annotations

import argparse
import json
import os
import platform as _platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


# ─── data model ──────────────────────────────────────────────────────────────


class Action(Enum):
    """What `plan_actions` decides should happen to one plugin/marketplace.

    OK         — already at user scope; no-op
    INSTALL    — enabled but not installed at any scope
    REINSTALL  — installed at wrong scope (project/local); uninstall + reinstall at user
    UPDATE     — at user scope, opt-in --update requested; `claude plugin update`
    DRIFT      — installed at user scope but not in any enabledPlugins
    SKIP_OS    — marketplace gated to OSes not matching this host
    """

    OK = "ok"
    INSTALL = "install"
    REINSTALL = "reinstall"
    UPDATE = "update"
    DRIFT = "drift"
    SKIP_OS = "skip_os"


@dataclass
class Decision:
    plugin: str
    action: Action
    current_scope: str = "none"
    reason: str = ""
    post_install: list[str] = field(default_factory=list)


# ─── helpers ─────────────────────────────────────────────────────────────────


def _marketplace_of(plugin: str) -> str:
    """Plugin id format: `<name>@<marketplace>`. Returns marketplace, "" if unparseable."""
    if "@" not in plugin:
        return ""
    return plugin.rsplit("@", 1)[1]


def base_name(plugin: str) -> str:
    """Plugin id `<name>@<marketplace>` → `<name>` (no suffix → unchanged)."""
    return plugin.rsplit("@", 1)[0] if "@" in plugin else plugin


def drift_collides_with_enabled(plugin: str, settings: dict,
                                local_enabled: dict | None = None) -> bool:
    """True if a DRIFT plugin shares its base name with an *enabled* plugin under
    a *different* marketplace (e.g. `foo@old` drift while `foo@new` is enabled).

    This is the marketplace-migration hazard: `claude plugin uninstall foo@old`
    is suffix-blind and removes the enabled `foo@new` instead. When this returns
    True the caller must excise the drift directly instead of via the CLI.
    """
    enabled = {k for k, v in settings.get("enabledPlugins", {}).items() if v}
    enabled |= {k for k, v in (local_enabled or {}).items() if v}
    target = base_name(plugin)
    return any(e != plugin and base_name(e) == target for e in enabled)


def _current_scope(plugin: str, installed: dict) -> str:
    entries = installed.get("plugins", {}).get(plugin, [])
    if not entries:
        return "none"
    return entries[0].get("scope", "none")


def detect_platform() -> str:
    sysname = _platform.system().lower()
    if sysname == "darwin":
        return "macos"
    if sysname == "linux":
        return "linux"
    if sysname == "windows":
        return "windows"
    return sysname


# ─── pure decision layer ─────────────────────────────────────────────────────


def marketplace_allowed_on(name: str, platform: str, metadata: dict) -> bool:
    """True if marketplace is allowed on this OS. Missing metadata = permissive."""
    entry = metadata.get(name)
    if not entry:
        return True
    allowed = entry.get("os")
    if not allowed:
        return True
    return platform in allowed


def post_install_hooks_for(plugin: str, metadata: dict) -> list[str]:
    mp = _marketplace_of(plugin)
    return list(metadata.get(mp, {}).get("post_install", []))


def decide_plugin(plugin: str, settings: dict, installed: dict) -> Decision:
    """Decide what to do with one enabled plugin based on its current install scope."""
    scope = _current_scope(plugin, installed)
    if scope == "user":
        return Decision(plugin=plugin, action=Action.OK, current_scope="user",
                        reason="already at user scope")
    if scope == "none":
        return Decision(plugin=plugin, action=Action.INSTALL, current_scope="none",
                        reason="not installed; install at user scope")
    return Decision(plugin=plugin, action=Action.REINSTALL, current_scope=scope,
                    reason=f"installed at {scope} scope; move to user")


def find_drift(settings: dict, installed: dict, local_enabled: dict) -> list[Decision]:
    """user-scope plugins not in any enabledPlugins map (common or local)."""
    enabled_common = {k for k, v in settings.get("enabledPlugins", {}).items() if v}
    enabled_local = {k for k, v in (local_enabled or {}).items() if v}
    expected = enabled_common | enabled_local
    drifts: list[Decision] = []
    for name, entries in installed.get("plugins", {}).items():
        for e in entries:
            if e.get("scope") == "user" and name not in expected:
                drifts.append(Decision(plugin=name, action=Action.DRIFT,
                                       current_scope="user",
                                       reason="installed at user scope but not enabled"))
                break
    return drifts


def plan_actions(settings: dict, installed: dict, metadata: dict,
                 platform: str, local_enabled: dict | None = None,
                 update_candidates: bool = False) -> list[Decision]:
    """Full pass: one Decision per enabled plugin, plus drift decisions.

    update_candidates (opt-in --update): re-label user-scope OK plugins as
    UPDATE so the apply layer runs `claude plugin update`. Only OK→UPDATE —
    INSTALL/REINSTALL/SKIP_OS are untouched (you cannot update what is not
    installed, and a scope fix takes priority). Whether a candidate is
    *actually* stale is left to the CLI (idempotent: no-op when current); we
    never compare commit SHAs ourselves.
    """
    out: list[Decision] = []
    enabled = {k for k, v in settings.get("enabledPlugins", {}).items() if v}
    for plugin in enabled:
        mp = _marketplace_of(plugin)
        if not marketplace_allowed_on(mp, platform, metadata):
            out.append(Decision(plugin=plugin, action=Action.SKIP_OS,
                                current_scope=_current_scope(plugin, installed),
                                reason=f"marketplace {mp} not allowed on {platform}"))
            continue
        d = decide_plugin(plugin, settings, installed)
        if update_candidates and d.action is Action.OK:
            d.action = Action.UPDATE
            d.reason = "user scope; --update requested (CLI decides if stale)"
        d.post_install = post_install_hooks_for(plugin, metadata)
        out.append(d)
    out.extend(find_drift(settings, installed, local_enabled or {}))
    return out


# ─── side-effect layer (apply) ───────────────────────────────────────────────


def _claude_available() -> bool:
    return shutil.which("claude") is not None


def excise_installed_plugin(plugin: str) -> bool:
    """Remove one plugin entry from installed_plugins.json + trash its cache,
    WITHOUT `claude plugin uninstall` (which is suffix-blind, see
    drift_collides_with_enabled). Returns True on success.

    Used only for marketplace-migration drift where the CLI would clobber the
    same-base enabled plugin. The cache lives at
    `<claude>/plugins/cache/<marketplace>/<base>/`.
    """
    home = _claude_home()
    ip_path = home / "plugins" / "installed_plugins.json"
    if not ip_path.exists():
        return False
    try:
        data = json.loads(ip_path.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    if plugin not in data.get("plugins", {}):
        return False
    del data["plugins"][plugin]
    ip_path.write_text(json.dumps(data, indent=2) + "\n")
    # Best-effort cache removal — never fail the excision on a missing dir.
    mp, base = _marketplace_of(plugin), base_name(plugin)
    if mp and base:
        cache_dir = home / "plugins" / "cache" / mp / base
        if cache_dir.exists():
            shutil.rmtree(cache_dir, ignore_errors=True)
    return True


def install_omc_shell_cli() -> str:
    """Post-install hook for OMC: ensure `omc` shell CLI is on PATH."""
    if shutil.which("omc"):
        return "omc shell CLI already present"
    if not shutil.which("npm"):
        return "WARNING: npm not found; cannot install oh-my-claude-sisyphus"
    rc = subprocess.run(
        ["npm", "i", "-g", "oh-my-claude-sisyphus@latest"],
        capture_output=True,
    ).returncode
    return ("installed oh-my-claude-sisyphus" if rc == 0
            else "WARNING: failed to install oh-my-claude-sisyphus")


POST_INSTALL_REGISTRY = {
    "install_omc_shell_cli": install_omc_shell_cli,
}


def run_post_install(name: str) -> str:
    fn = POST_INSTALL_REGISTRY.get(name)
    if fn is None:
        return f"WARNING: unknown post_install hook: {name}"
    return fn()


def apply(decisions: list[Decision], dry_run: bool, prune: bool,
          settings: dict | None = None, local_enabled: dict | None = None) -> list[str]:
    """Execute decisions via `claude plugin`. Returns log lines.

    `settings`/`local_enabled` let the DRIFT path detect a marketplace-migration
    collision (same base name still enabled elsewhere) and excise the stale entry
    directly rather than via the suffix-blind `claude plugin uninstall`.
    """
    settings = settings or {}
    log: list[str] = []
    counts = {a: 0 for a in Action}
    removed = 0   # drift entries actually removed (CLI uninstall OR migration excise)
    kept = 0      # drift entries left in place (warn-only)
    failed = 0    # drift removals that errored (so a stuck heal doesn't read as removed)
    for d in decisions:
        counts[d.action] += 1
        if d.action is Action.OK:
            continue
        if d.action is Action.SKIP_OS:
            log.append(f"skip (os gate): {d.plugin} — {d.reason}")
            continue
        if d.action is Action.DRIFT:
            collides = drift_collides_with_enabled(d.plugin, settings, local_enabled)
            # Migration-collision drift (same base enabled under another
            # marketplace) is an unambiguous stale leftover, not a user choice —
            # auto-heal it even WITHOUT --prune, so a recipient who knows nothing
            # of the marketplace migration is fixed by a plain install.sh run.
            # A genuine orphan (no same-base enabled) stays warn-only unless --prune.
            if not prune and not collides:
                log.append(
                    f"plugin drift (kept): {d.plugin} — register in settings.local.json "
                    f"or re-run with --prune to remove"
                )
                kept += 1
                continue
            if dry_run:
                how = "excise (migration collision)" if collides else "uninstall"
                log.append(f"would {how} (drift): {d.plugin}")
                removed += 1
                continue
            if collides:
                # Suffix-blind `claude plugin uninstall` would clobber the
                # same-base enabled plugin — excise this entry directly instead.
                ok = excise_installed_plugin(d.plugin)
                log.append(f"plugin auto-healed (migration drift): {d.plugin}" if ok
                           else f"WARNING: failed to excise: {d.plugin}")
                removed += ok          # count only a real removal — a failed
                failed += (not ok)     # heal must not read as `removed` next run
                continue
            rc = subprocess.run(
                ["claude", "plugin", "uninstall", "-s", "user", "-y", d.plugin],
                capture_output=True,
            ).returncode
            log.append(f"plugin uninstalled (drift): {d.plugin}" if rc == 0
                       else f"WARNING: failed to uninstall: {d.plugin}")
            removed += (rc == 0)
            failed += (rc != 0)
            continue
        if d.action is Action.UPDATE:
            # `claude plugin update` is idempotent — a no-op when already current,
            # so we never decide staleness ourselves (mirror SHAs are unreliable).
            if dry_run:
                log.append(f"would update (user): {d.plugin}")
                continue
            rc = subprocess.run(
                ["claude", "plugin", "update", d.plugin],
                capture_output=True,
            ).returncode
            log.append(f"plugin updated (user): {d.plugin}" if rc == 0
                       else f"WARNING: failed to update: {d.plugin}")
            continue
        # INSTALL or REINSTALL
        if dry_run:
            log.append(f"would {d.action.value} at user scope: {d.plugin} "
                       f"(currently: {d.current_scope})")
            continue
        if d.action is Action.REINSTALL:
            subprocess.run(
                ["claude", "plugin", "uninstall", "-s", d.current_scope, "-y", d.plugin],
                capture_output=True,
            )
        rc = subprocess.run(
            ["claude", "plugin", "install", "-s", "user", d.plugin],
            capture_output=True,
        ).returncode
        if rc != 0:
            log.append(f"WARNING: failed to install: {d.plugin}")
            continue
        log.append(f"plugin {d.action.value} (user): {d.plugin}")
        for hook in d.post_install:
            log.append(run_post_install(hook))
    log.append(
        f"plugin sync: {counts[Action.OK]} already user-scope, "
        f"{counts[Action.INSTALL] + counts[Action.REINSTALL]} fixed, "
        f"{counts[Action.UPDATE]} updated, "
        f"{removed} removed, "
        f"{kept} drift-kept, "
        f"{failed} failed, "
        f"{counts[Action.SKIP_OS]} os-skipped"
    )
    return log


# ─── marketplace registration ────────────────────────────────────────────────


def _existing_marketplaces() -> set[str]:
    if not _claude_available():
        return set()
    out = subprocess.run(
        ["claude", "plugin", "marketplace", "list"],
        capture_output=True, text=True,
    ).stdout
    names = set()
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("❯ "):
            names.add(s[2:].strip().split()[0])
    return names


def _marketplace_source_arg(name: str, settings: dict) -> str | None:
    """Build the source arg for `claude plugin marketplace add`."""
    cfg = settings.get("extraKnownMarketplaces", {}).get(name, {}).get("source", {})
    if cfg.get("source") == "github":
        return cfg.get("repo")
    if cfg.get("source") == "git":
        return cfg.get("url")
    return None


def ensure_marketplaces(settings: dict, metadata: dict, platform: str,
                        dry_run: bool) -> list[str]:
    """Add any marketplace referenced by enabled plugins that is missing on this host."""
    log: list[str] = []
    if not _claude_available():
        return ["skip marketplace ensure: 'claude' not in PATH"]
    needed = {
        _marketplace_of(p) for p, v in settings.get("enabledPlugins", {}).items() if v
    }
    needed.discard("")
    existing = _existing_marketplaces()
    for name in sorted(needed):
        if name in existing:
            continue
        if not marketplace_allowed_on(name, platform, metadata):
            log.append(f"skip marketplace (os gate): {name} on {platform}")
            continue
        source = _marketplace_source_arg(name, settings)
        if not source:
            # claude-plugins-official is implicit / always-known; no source needed.
            if name == "claude-plugins-official":
                source = "anthropics/claude-plugins-official"
            else:
                log.append(f"WARNING: no source for marketplace: {name}")
                continue
        if dry_run:
            log.append(f"would add marketplace: {name} ({source})")
            continue
        rc = subprocess.run(
            ["claude", "plugin", "marketplace", "add", source],
            capture_output=True,
        ).returncode
        log.append(f"added marketplace: {name}" if rc == 0
                   else f"WARNING: failed to add marketplace: {name}")
    return log


# ─── I/O ─────────────────────────────────────────────────────────────────────


def _claude_home() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude")))


def load_inputs(repo_dir: Path | None = None) -> tuple[dict, dict, dict, dict]:
    """Read (settings, installed, metadata, local_enabled). Missing files -> {}."""
    repo = repo_dir or Path(__file__).resolve().parents[2]
    home = _claude_home()
    settings_path = home / "settings.json"
    if not settings_path.exists():
        settings_path = repo / "config" / "settings.json"
    settings = json.loads(settings_path.read_text()) if settings_path.exists() else {}
    installed_path = home / "plugins" / "installed_plugins.json"
    installed = json.loads(installed_path.read_text()) if installed_path.exists() else {}
    metadata = json.loads((repo / "installer" / "marketplace-metadata.json").read_text())
    local_path = home / "settings.local.json"
    local_enabled = {}
    if local_path.exists():
        local_enabled = json.loads(local_path.read_text()).get("enabledPlugins", {})
    return settings, installed, metadata, local_enabled


# ─── CLI ─────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="claudebase plugin sync")
    ap.add_argument("--apply", action="store_true", help="execute decisions")
    ap.add_argument("--dry-run", action="store_true", help="print intended actions")
    ap.add_argument("--prune", action="store_true", help="remove drift plugins")
    ap.add_argument("--update", action="store_true",
                    help="also `claude plugin update` enabled user-scope plugins "
                         "(idempotent; CLI no-ops when already current)")
    ap.add_argument("--report", action="store_true",
                    help="print one TAB-separated line per decision and exit")
    args = ap.parse_args(argv)

    settings, installed, metadata, local_enabled = load_inputs()
    platform = detect_platform()

    for line in ensure_marketplaces(settings, metadata, platform, args.dry_run):
        print(line)

    decisions = plan_actions(settings, installed, metadata, platform, local_enabled,
                             update_candidates=args.update)

    # Without --update, advise (don't act) how many user-scope plugins could be
    # refreshed. We can't tell which are stale — only the CLI can — so the note
    # reports the candidate count, never a "N updates available" claim.
    if not args.update:
        candidates = sum(1 for d in decisions if d.action is Action.OK)
        if candidates:
            print(f"plugin update: {candidates} user-scope plugin(s) installed — "
                  f"re-run with --update to refresh to latest")

    if args.report:
        for d in decisions:
            print(f"{d.plugin}\t{d.current_scope}\t{d.action.value}\t{d.reason}")
        return 0

    if not (args.apply or args.dry_run):
        ap.error("specify --apply, --dry-run, or --report")

    for line in apply(decisions, dry_run=args.dry_run, prune=args.prune,
                      settings=settings, local_enabled=local_enabled):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())

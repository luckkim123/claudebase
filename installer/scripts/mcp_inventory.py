#!/usr/bin/env python3
"""Enumerate every configured MCP server and report how each one updates.

MCP servers have no common update path. `claude plugin update` refreshes every
plugin at once; there is no `claude mcp update`, because a server is just a
command someone wired in, and what installs it decides how it upgrades. So this
script classifies by the launch command, which is the only reliable signal, and
prints the check to run per class. Detection only — it never upgrades anything.

Run from a project directory to include that project's .mcp.json.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

HOME = Path.home()


def _load(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def collect():
    """Every (name, scope, command, args) the CLI could launch."""
    out = []

    def add(scope, name, spec):
        out.append(
            (
                name,
                scope,
                spec.get("command") or spec.get("url") or "",
                " ".join(spec.get("args") or []),
            )
        )

    cj = _load(HOME / ".claude.json")
    for name, spec in (cj.get("mcpServers") or {}).items():
        add("user", name, spec)
    for proj, val in (cj.get("projects") or {}).items():
        for name, spec in (val.get("mcpServers") or {}).items():
            add(f"proj:{os.path.basename(proj)}", name, spec)

    local = Path.cwd() / ".mcp.json"
    if local.exists():
        for name, spec in (_load(local).get("mcpServers") or {}).items():
            add(".mcp.json", name, spec)

    return out


def classify(command, args):
    """(kind, package, how-to-check) from the launch command.

    Resolve symlinks before deciding. A uv-installed tool is reached through
    ~/.local/bin/<cmd>, which looks like a plain binary until realpath shows the
    uv tool dir — and only that path carries the PyPI name, which need not match
    the command (graphify's package is `graphifyy`).
    """
    if command.startswith("http"):
        return "remote", None, "claude.ai connector — server-side; only auth can be stale"

    base = command.rsplit("/", 1)[-1]

    if base in ("uvx", "uvx.exe"):
        pkg = args.split()[0] if args else None
        return "uv", pkg, "uv tool list --outdated"

    if base in ("npx", "bunx"):
        return "npx", None, "refetched on every launch — nothing pinned to update"

    if command.startswith(("/", "~")):
        real = os.path.realpath(os.path.expanduser(command))
        if "/uv/tools/" in real:
            return "uv", real.split("/uv/tools/")[1].split("/")[0], "uv tool list --outdated"
        return "binary", base, "ask the tool itself (--version, then its own upgrade verb)"

    return "unknown", None, "inspect manually"


def outdated_uv_tools():
    """Package names uv reports as stale. Empty on failure — never guess."""
    try:
        res = subprocess.run(
            ["uv", "tool", "list", "--outdated"],
            capture_output=True, text=True, timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        return set()
    return {
        line.split()[0]
        for line in res.stdout.splitlines()
        if line and not line.startswith((" ", "-", "\t"))
    }


def main():
    servers = collect()
    if not servers:
        print("no MCP servers configured")
        return 0

    stale = outdated_uv_tools()
    width = max(len(name) for name, *_ in servers)
    actions = []

    for name, scope, command, args in sorted(servers):
        kind, pkg, how = classify(command, args)
        flag = ""
        if kind == "uv" and pkg and pkg in stale:
            flag = "  <-- OUTDATED"
            actions.append(f"uv tool upgrade {pkg}")
        print(f"  {name:<{width}}  {kind:<7} [{scope}]  {how}{flag}")

    print()
    if actions:
        print("stale, ask before running:")
        for cmd in sorted(set(actions)):
            print(f"  {cmd}")
    else:
        print("no uv-managed MCP server is outdated")

    binaries = sorted({p for k, p, _ in map(lambda s: classify(s[2], s[3]), servers)
                       if k == "binary" and p})
    if binaries:
        print()
        print("self-updating binaries — each owns its own check, so ask them individually:")
        for name in binaries:
            print(f"  {name} --version   (then its own upgrade verb, e.g. `{name} upgrade`)")

    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Register user-scope MCP servers with Claude Code.

Why this exists: `install.sh` renders `config/mcp.template.json` into
`~/.claude/mcp.json`, and **Claude Code never reads that file**. Measured
2026-08-10 — user-scope servers load from `~/.claude.json` (`mcpServers`) only,
and writing the entry there under either key did not make it appear in
`claude mcp list`. The rendered file is a record of intent; this script is the
part that actually reaches the CLI, via `claude mcp add --scope user`.

`~/.claude.json` is CLI-owned state, so registration goes *through* the CLI
rather than editing the file — the read side (has this name already?) is a
direct read because it is the cheapest accurate check, but every write is a
`claude mcp add`.

Idempotent by name: a server already present is left completely alone, even if
its command differs. Re-registering would mean removing and re-adding, which
would silently discard a deliberate per-machine edit (a different binary path,
an extra `-e`). Drift is reported, never repaired.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

# Keys carrying documentation rather than configuration. `$comment`/`$caveat`
# sit at the top level, `$note` inside an entry; all are skipped.
META_PREFIX = "$"


def _is_meta(key: str) -> bool:
    return key.startswith(META_PREFIX)


def registered_names(claude_json: Path) -> set[str]:
    """Names already in ~/.claude.json's mcpServers (empty when absent)."""
    try:
        data = json.loads(claude_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    servers = data.get("mcpServers")
    return set(servers) if isinstance(servers, dict) else set()


def resolve_command(command: str) -> str | None:
    """Absolute path for `command`, or None when it cannot be found.

    Hooks and MCP servers are spawned without a login shell, so a bare name that
    works in the user's terminal can fail at launch. PATH first, then uv's shim
    dir — the same fallback installer/lib/deps.sh uses, and the reason a plain
    `graphify` resolves interactively but not from the CLI.
    """
    if os.path.isabs(command):
        return command if os.access(command, os.X_OK) else None
    found = shutil.which(command)
    if found:
        return found
    fallback = Path.home() / ".local" / "bin" / command
    return str(fallback) if os.access(fallback, os.X_OK) else None


def add_command(name: str, entry: dict[str, Any], resolved: str) -> list[str]:
    """The `claude mcp add` argv for one server entry."""
    argv = ["claude", "mcp", "add", "--transport", "stdio", "--scope", "user"]
    for key, value in (entry.get("env") or {}).items():
        argv += ["-e", f"{key}={value}"]
    argv += [name, "--", resolved, *(str(a) for a in entry.get("args") or [])]
    return argv


def plan(config: dict[str, Any], existing: set[str]) -> tuple[list, list, list]:
    """Split the configured servers into (to_add, skipped, unresolvable).

    Pure decision layer — no subprocess, no filesystem — so tests drive it
    directly. `to_add` items are `(name, entry, resolved_path)`.
    """
    to_add, skipped, unresolvable = [], [], []
    for name, entry in (config.get("globalServers") or {}).items():
        if _is_meta(name) or not isinstance(entry, dict):
            continue
        if name in existing:
            skipped.append(name)
            continue
        command = entry.get("command")
        if not command:
            unresolvable.append((name, "no command field"))
            continue
        if "${" in json.dumps(entry):
            unresolvable.append((name, "unresolved ${...} placeholder — check secrets/secrets.env"))
            continue
        resolved = resolve_command(str(command))
        if resolved is None:
            unresolvable.append((name, f'"{command}" not found on PATH or in ~/.local/bin'))
            continue
        to_add.append((name, entry, resolved))
    return to_add, skipped, unresolvable


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Register user-scope MCP servers with `claude mcp add`."
    )
    parser.add_argument("--config", required=True, help="rendered mcp.json (secrets already substituted)")
    parser.add_argument("--claude-json", default=str(Path.home() / ".claude.json"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    if not config_path.is_file():
        return 0

    if not shutil.which("claude"):
        print('[install] WARNING: "claude" CLI not found — MCP servers not registered')
        return 0

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"[install] WARNING: {config_path} is not valid JSON ({exc}) — skipping MCP registration")
        return 0

    to_add, skipped, unresolvable = plan(config, registered_names(Path(args.claude_json)))

    for name, reason in unresolvable:
        print(f"[install] WARNING: MCP server {name!r} not registered — {reason}")
    for name in skipped:
        print(f"[install]   mcp {name} already registered (skip)")

    failures = 0
    for name, entry, resolved in to_add:
        cmd = add_command(name, entry, resolved)
        if args.dry_run:
            print(f"[dry-run] {' '.join(cmd)}")
            continue
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            print(f"[install]   mcp {name} registered -> {resolved}")
        else:
            failures += 1
            detail = (proc.stderr or proc.stdout).strip().splitlines()
            print(f"[install] WARNING: `claude mcp add {name}` failed: {detail[-1] if detail else 'no output'}")

    # Never fail the install over MCP registration: a missing server degrades a
    # feature, while a non-zero exit here would abort every later stage.
    return 0


if __name__ == "__main__":
    sys.exit(main())

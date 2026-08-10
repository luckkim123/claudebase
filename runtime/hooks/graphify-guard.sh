#!/usr/bin/env bash
# graphify PreToolUse guard — routes the agent through the knowledge graph
# before it searches or reads raw files.
#
# Wired at USER scope (config/settings.json → ~/.claude/settings.json), so it
# applies on every machine and in every project rather than per-repo. That is
# safe because `graphify hook-guard` is a no-op wherever no graph exists: in a
# directory without graphify-out/graph.json it prints nothing and exits 0
# (measured ~51 ms per call, the cost of starting Python).
#
# Why a hook and not just an MCP server or a CLAUDE.md line: those two offer and
# ask, respectively, and both are routinely skipped under momentum. Only a hook
# intercepts the tool call itself — and only a hook reaches subagents, which
# inherit the interception but not the instruction.
#
# Usage: graphify-guard.sh <search|read>
#   search — matched on Bash|Grep
#   read   — matched on Read|Glob
#
# stdin (Claude Code's hook payload) passes through untouched via exec, and the
# exit code is graphify's own, so a future --strict install can still block.

set -u

mode="${1:-}"
case "$mode" in
  search | read) ;;
  *)
    # Misconfigured hook must never block a tool call.
    exit 0
    ;;
esac

# uv tool install puts the shim in ~/.local/bin, which this user's shells do not
# always export (the .zshrc line is commented out), so PATH alone is unreliable —
# same reason installer/lib/deps.sh probes that directory directly.
graphify_bin="$(command -v graphify 2>/dev/null || true)"
[ -n "$graphify_bin" ] || graphify_bin="$HOME/.local/bin/graphify"

# Not installed (a machine that has not run install.sh yet) → stay out of the way.
[ -x "$graphify_bin" ] || exit 0

exec "$graphify_bin" hook-guard "$mode"

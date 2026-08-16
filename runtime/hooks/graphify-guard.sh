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

# Anchor the guard at the project root instead of wherever the shell happens to be.
#
# `graphify hook-guard` looks for graph.json at Path(GRAPHIFY_OUT)/"graph.json" —
# a RELATIVE path (paths.py:293), resolved against the hook's cwd. Hooks run with
# the working directory of the session, and the Bash tool's cwd persists across
# calls, so one `cd sub/repo && ...` in any earlier command silently disables the
# guard for the rest of the session. Measured on a 3-repo workspace: identical
# greps nudged from the root and stayed silent one directory down, with nothing
# reporting that the guard had switched off.
#
# CLAUDE_PROJECT_DIR would name the root but is not exported here (the same
# finding graph-refresh.sh records), and `git rev-parse` fails in a workspace that
# is not itself a repo. So walk up for the graph instead: it needs neither, and
# the NEAREST graph wins, which is what a nested repo carrying its own graph
# should get. No ancestor has one → no cd → exactly the previous behaviour.
#
# An absolute GRAPHIFY_OUT ("/shared/graphify-out", paths.py docstring) is already
# cwd-independent, so leave it alone.
out_name="${GRAPHIFY_OUT:-graphify-out}"
case "$out_name" in
  /*) ;;
  *)
    d="$PWD"
    while [ "$d" != "/" ] && [ -n "$d" ]; do
      if [ -f "$d/$out_name/graph.json" ]; then
        cd "$d" || exit 0
        break
      fi
      d="$(dirname "$d")"
    done
    ;;
esac

# `hook-guard search` never inspects what the command searches — it fires on any
# grep/find token whenever cwd has a graph, so a grep against another repo gets a
# "MANDATORY: query the graph first" about a graph that does not cover it (six
# such misfires in one session). The read guard already skips out-of-project
# targets (#1840); this supplies the missing search-side equivalent. Filter absent
# or python3 missing → behave exactly as before.
ran=0
if [ "$mode" = "search" ]; then
  filter="$(dirname "$0")/graphify_scope_filter.py"
  if [ -f "$filter" ] && command -v python3 >/dev/null 2>&1; then
    payload="$(cat)"
    printf '%s' "$payload" | python3 "$filter" || exit 0
    guard_out="$(printf '%s' "$payload" | "$graphify_bin" hook-guard "$mode")"
    rc=$?
    ran=1
  fi
fi

if [ "$ran" -eq 0 ]; then
  guard_out="$("$graphify_bin" hook-guard "$mode")"
  rc=$?
fi

# Correct the one thing graphify gets wrong on a machine that relocates its
# output tree. The nudge text hardcodes the literal `graphify-out/graph.json`
# (cli.py:22,32,46) even though the same module resolves the real path through
# GRAPHIFY_OUT two definitions later (`_default_graph_path`, cli.py:84). With
# GRAPHIFY_OUT=.graphify — what config/settings.json sets on every claudebase
# machine — the agent is handed a MANDATORY instruction naming a file that does
# not exist, every turn, for as long as a graph is present. The premise is true
# (a graph really is there); only the path is stale, so rewrite the path rather
# than suppress the nudge. Measured on the obsidian vault 2026-08-17: the guard
# fired correctly on ~10 tool calls in one session while pointing at an absent
# `graphify-out/graph.json`.
#
# Fixed here rather than in site-packages because `uv tool upgrade` discards a
# patched package, and this wrapper already computes the real directory name.
if [ -n "${guard_out:-}" ] && [ "$out_name" != "graphify-out" ]; then
  needle='graphify-out/graph.json'
  guard_out="${guard_out//"$needle"/$out_name/graph.json}"
fi

[ -n "${guard_out:-}" ] && printf '%s\n' "$guard_out"
exit "${rc:-0}"

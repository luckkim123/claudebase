#!/usr/bin/env bash
# Stop hook — refresh the code graphs this repository already has.
#
# The problem this closes: the PreToolUse guards route every session (and every
# subagent) through the graph, but nothing was refreshing it. A graph that the
# agent is now *required* to consult and that nobody updates is worse than no
# graph, because a stale index answers confidently with yesterday's code.
#
# Design, in three rules:
#
#   1. Opt in by existence, never by configuration. A repo that has no graph
#      directory gets nothing built here — this hook only keeps current what
#      somebody already chose to create. That is the difference between
#      "automatic" and "creates directories in every repo you cd into", and it
#      is also why this can ship at user scope for people who have never heard
#      of an MCP server.
#
#   2. Only the free half. `graphify update` re-extracts *code* with tree-sitter:
#      offline, no key, ~1 s. The semantic pass that indexes prose costs money
#      and hours (measured: 58 chunks, ~7 h on one vault), so it is never
#      triggered from a hook. Prose graphs therefore drift, on purpose; refresh
#      them deliberately with /graphify.
#
#   3. Detached, so a turn never waits. Both updates run in a double-forked
#      subshell and this script returns immediately; the Stop hook's timeout can
#      never be hit by a slow repo. graphify's own git hook uses the same shape.
#
# tokensave is deliberately absent: it re-indexes itself whenever files change,
# and its CLI has side effects on ~/.claude/settings.json even for read-only
# looking commands, so nothing here may execute it.
#
# Usage: graph-refresh.sh   (no arguments; Stop hook payload on stdin, ignored)

set -u

# Hooks run with the working directory of the session, so the repo root comes
# from git rather than from a variable Claude Code does not export
# (CLAUDE_PROJECT_DIR is unset in the Stop hook environment on this platform).
repo="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
[ -n "$repo" ] || exit 0

resolve() {
  # ~/.local/bin is where uv puts the shims, and this user's shells do not
  # always export it (same reason as graphify-guard.sh).
  local found
  found="$(command -v "$1" 2>/dev/null || true)"
  [ -n "$found" ] || found="$HOME/.local/bin/$1"
  [ -x "$found" ] && printf '%s' "$found"
}

# Debounce: one refresh per graph per minute. A chatty session would otherwise
# re-run the update after every single turn for no gain.
#
# simplified: the marker is stamped before the launch, not after, so two
# refreshes can overlap if an update ever exceeds the window (measured 0.46 s
# and 1.0 s here, so the window is ~60x the cost). Take a lock if a repo is ever
# large enough for that to stop being true.
should_refresh() {
  local marker="$1"
  [ -n "$(find "$marker" -mmin -1 2>/dev/null)" ] && return 1
  : >"$marker" 2>/dev/null || return 1
  return 0
}

launch() {
  # Double fork so the update outlives this hook and the shell that spawned it.
  # First argument is the directory to run in — a graph does not always live at
  # the git root (see the nested-graph loop below).
  local dir="$1"; shift
  ( cd "$dir" && "$@" >/dev/null 2>&1 & ) &
}

# graphify — GRAPHIFY_OUT relocates the whole output tree (config/settings.json
# sets .graphify on claudebase machines); fall back to the upstream default.
gout="${GRAPHIFY_OUT:-graphify-out}"
if [ -f "$repo/$gout/graph.json" ]; then
  # A semantic extraction runs for hours, streaming per-chunk results into
  # cache/ as it goes. Racing it is not worth the CPU, so recent write activity
  # anywhere under cache/ means "in flight, leave it alone". Two details are
  # load-bearing, both learned by getting them wrong:
  #
  #   - Recursive, not the directory's own mtime. Chunks land in nested
  #     per-corpus subdirectories, so the top-level mtime lags arbitrarily.
  #   - Ten minutes, not two. One chunk took 5.3 min on the vault that prompted
  #     this, so a window narrower than the chunk interval sees an idle cache
  #     between chunks and concludes the run has finished.
  #
  # Checking files rather than `pgrep graphify extract` keeps it per-repo: a
  # long run in one repository must not freeze the refresh everywhere else on
  # the machine. `-quit` stops at the first hit, so a large cache costs nothing.
  if [ -z "$(find "$repo/$gout/cache" -type f -mmin -10 -print -quit 2>/dev/null)" ]; then
    gbin="$(resolve graphify)"
    if [ -n "$gbin" ] && should_refresh "$repo/$gout/.last-refresh"; then
      launch "$repo" "$gbin" update .
    fi
  fi
fi

# code-review-graph — per-repo SQLite under .code-review-graph/. --brief keeps
# the (discarded) output small; the work is the same incremental re-parse.
#
# Two things the single `[ -d "$repo/.code-review-graph" ]` test got wrong, both
# measured on a meta-repo workspace (stonefish_ws, 2026-08-10):
#
#   1. The graph is not always at the git root. A meta-repo that gitignores
#      `src/` and carries independent git repos beneath it holds its real graphs
#      one or two levels down, so a root-only test refreshed nothing that
#      mattered. Search to depth 3 instead — measured 0.12 s on that tree, and
#      `-prune` stops it from descending into the graph directories themselves.
#
#   2. Existence is not opt-in, because the tools create it. Any MCP query that
#      omits `repo_root` makes an empty `graph.db` wherever the server's cwd is
#      — 0 nodes, `status: "ok"`. That directory then satisfied the test, so the
#      hook spent every turn refreshing an empty database while the two real
#      graphs went stale. Rule 1 of this file ("opt in by existence") only holds
#      if existence means content, so skip any graph with no nodes.
#
# sqlite3(1) is not installed on every machine that runs this (it is absent from
# the container this was found on), so the node count comes from python3's
# built-in sqlite3 module, read-only so a concurrent update cannot be disturbed.
has_nodes() {
  python3 - "$1" <<'PY' 2>/dev/null
import sqlite3, sys
try:
    db = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
    sys.exit(0 if db.execute("select count(*) from nodes").fetchone()[0] else 1)
except Exception:
    sys.exit(1)
PY
}

cbin="$(resolve code-review-graph)"
if [ -n "$cbin" ]; then
  while IFS= read -r gdir; do
    [ -n "$gdir" ] || continue
    has_nodes "$gdir/graph.db" || continue
    should_refresh "$gdir/.last-refresh" || continue
    launch "$(dirname "$gdir")" "$cbin" update --brief
  done <<EOF
$(find "$repo" -maxdepth 3 -type d -name .code-review-graph -prune 2>/dev/null)
EOF
fi

exit 0

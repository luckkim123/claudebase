#!/usr/bin/env bash
# .omc/logs 위치는 cwd 가 아니라 프로젝트 루트가 정한다 (hooklog.sh 참조).
_hl="$(dirname "$0")/hooklog.sh"
[ -r "$_hl" ] && . "$_hl"
command -v hooklog_state_root >/dev/null 2>&1 || hooklog_state_root() {
    printf '%s\n' "${CLAUDE_PROJECT_DIR:-$PWD}"   # fail-open: 훅은 세션을 막지 않는다
}
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
# tokensave was a third index here until 2026-08-25 and was never refreshed by
# this hook — it re-indexed itself, and its CLI had side effects on
# ~/.claude/settings.json even for read-only looking commands. It is now removed
# from the repo entirely (docs/CHANGELOG.md).
#
# Usage: graph-refresh.sh   (no arguments; Stop hook payload on stdin, ignored)

set -u

# Hooks run with the working directory of the session, so the repo root comes
# from git rather than from a variable Claude Code does not export
# (CLAUDE_PROJECT_DIR is unset in the Stop hook environment on this platform).
repo="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
[ -n "$repo" ] || exit 0

# Linked-worktree correction — the canonical copy of this block; graph-offer.sh
# and runtime/bin/graph-init.sh carry the same eight lines and point back here.
#
# Every index these scripts touch is gitignored (`.graphify/`, usually
# `.graphify/`), so `git worktree add` never copies one.
# In a linked worktree `--show-toplevel` therefore names a checkout that holds
# no graph, and the real graphs sit in the main checkout going stale. The common
# dir is shared by every worktree, so its parent is that main checkout.
#
# Compare the two git dirs ABSOLUTISED. A raw string compare is wrong and the
# failure is silent: measured on git 2.39.5, from a subdirectory of an ordinary
# main checkout `--git-dir` prints an absolute path while `--git-common-dir`
# still prints `../.git`, so the strings differ and the branch fires where there
# is no worktree at all. Absolutising also buys `--separate-git-dir` for free —
# there both values resolve to the same external directory, so the branch is
# skipped and `--show-toplevel` (which handles that layout) stands.
_gd="$(git rev-parse --git-dir 2>/dev/null)" || _gd=""
_gc="$(git rev-parse --git-common-dir 2>/dev/null)" || _gc=""
[ -n "$_gd" ] && _gd="$(cd "$_gd" 2>/dev/null && pwd)"
[ -n "$_gc" ] && _gc="$(cd "$_gc" 2>/dev/null && pwd)"
if [ -n "$_gc" ] && [ "$_gd" != "$_gc" ]; then
  repo="$(cd "$_gc/.." 2>/dev/null && pwd)" || exit 0
  [ -n "$repo" ] || exit 0
fi

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

# 발화 여부 플래그 — 그래프가 실재할 때만 1로 세팅하고, 실제 파일 기록은
# 블록이 끝난 뒤 한 번만 한다. 한 훅 호출이 그래프를 여러 개 건드리면 예전엔
# 반복마다 한 줄씩 찍혀 발화 1회가 로그 여러 줄이 됐다 — harness_stats.py 는
# `len(_read_jsonl(path))`로 발화 횟수를 세므로 이 훅만 수치가 부풀려졌다.
# Fix Round 1에서 단일 지점으로 통합. (2026-08-29: CRG 블록 제거로 남은 건
# graphify 하나지만, 중첩 그래프가 여럿일 수 있어 단일 기록 지점은 유지한다.)
_touched=0

# graphify — GRAPHIFY_OUT relocates the whole output tree (config/settings.json
# sets .graphify on claudebase machines); fall back to the upstream default.
#
# `.no-auto-refresh` next to graph.json is the opt-out, and it exists because
# `graphify update .` can only re-scan what graphify itself can see. A graph
# built from an explicit file list — a workspace whose real code lives in
# gitignored checkouts, any scope a rebuild script assembles by hand — is not
# reproducible by that scan: every file the scan cannot see reads as deleted and
# is pruned, leaving whatever the root scan does find. Measured on a three-repo
# workspace (2026-08-21): a deliberate 434-file / 6,427-node code graph was
# replaced by a 20-node markdown heading index two minutes after it was built,
# and again on an earlier build, with nothing reporting an error. Graphs the
# CLI cannot regenerate get the marker and are refreshed deliberately instead.
gout="${GRAPHIFY_OUT:-graphify-out}"
if [ -f "$repo/$gout/graph.json" ] && [ ! -f "$repo/$gout/.no-auto-refresh" ]; then
  _touched=1

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

if [ "$_touched" = 1 ]; then
  # 발화 기록 — harness_stats 가 이 파일명 리터럴을 grep 한다. 실패해도 무시.
  # 여기 한 곳에서만: 그래프가 실제로 있는 저장소에서만 기록해야
  # test_repo_without_a_graph_is_left_alone (새 디렉터리 0개 단언)이 깨지지 않고,
  # 한 번의 호출에서 그래프를 여럿 건드려도 줄 수는 항상 1개다.
  _log="$(hooklog_state_root)/.omc/logs/graph_refresh.jsonl"
  mkdir -p "$(dirname "$_log")" 2>/dev/null \
    && printf '{"ts":"%s","hook":"graph-refresh"}\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$_log" 2>/dev/null || true
fi

exit 0

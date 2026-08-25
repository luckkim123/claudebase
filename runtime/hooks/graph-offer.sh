#!/usr/bin/env bash
# SessionStart hook — offer to build a code graph, once per project, ever.
#
# The gap this fills: graph-refresh.sh keeps existing graphs current and the
# PreToolUse guards route sessions through them, but a project that never had
# a graph gets none of it, and nothing ever says so. Someone who does not know
# what an MCP server is will never type `/graphify`.
#
# Why an offer and not an automatic build. A graph built blindly is worse than
# no graph, because the guards then *require* the agent to consult it: measured
# on one Obsidian vault, 746 tracked .md files produced 0 nodes while 101 files
# of vendored plugin JS produced 21,425 "functions" and a 212 MB index — with no
# error anywhere. Auto-building would mass-produce that. Deciding needs
# judgement, so this hook hands the decision to the user, who owns the project.
#
# What it does NOT do is explain the procedure. It used to: 1,152 characters of
# prose that the model re-derived into four commands on every fire, and that a
# first-time user had to perform by hand. That procedure is now `graph-init`
# (runtime/bin/graph-init.sh), which writes the exclusion files, runs both free
# builds, and refuses to leave behind a graph made of somebody else's vendored
# tree. This hook only has to name it.
#
# Asked exactly once. The marker is written when the offer is *emitted*, not
# when the user answers, so ignoring the prompt is itself a durable answer and
# no project ever nags twice. For a git repo it lives inside .git/, which is
# per-repository, never committed, and disappears with the clone.
#
# Scope: the free tree-sitter builds only. graphify's semantic pass reads prose
# with an LLM and runs for hours (measured 5.3 min/chunk over 58 chunks on one
# vault, because the claude-cli backend is pinned to concurrency 1), so it stays
# a deliberate `/graphify` invocation and is never offered from a hook.

set -u

# Git gives a project boundary when there is one. When there is not, the working
# directory is the project: both builders handle a non-git tree — CRG falls back
# from `git ls-files` to an rglob walk (incremental.py:761-767) and graphify
# never needed git — so a container mount like /workspace was being skipped for
# a reason that does not hold. Using git as a proxy for "can be graphed" was
# simply wrong, and the failure was a silent no-op.
repo="$(git rev-parse --show-toplevel 2>/dev/null)" || repo=""

# Linked-worktree correction — see graph-refresh.sh for the measured reasoning
# behind absolutising both git dirs before the compare. Here it stops the hook
# offering a second graph for a repository that already answered the question in
# its main checkout, since the indexes are gitignored and never reach a worktree.
_gd="$(git rev-parse --git-dir 2>/dev/null)" || _gd=""
# 발화 기록 — harness_stats 가 이 파일명 리터럴을 grep 한다. 실패해도 무시.
# EXIT 트랩인 이유(2026-08-25 T4): 이 훅은 그래프·마커가 있으면 아래에서 조기
# exit 하고, 로깅이 제안 emit 지점에 있으면 그 경로가 통째로 기록되지 않는다.
# 그래서 로그 0 건이 "안 돌았다"로 오독됐다 — 실제로는 매 세션 돌았고 제안할
# 게 없었을 뿐이다. acted 가 그 둘을 가른다.
# $? 를 먼저 붙잡았다가 그대로 돌려주는 이유: 트랩의 마지막 명령 종료 코드가
# 훅의 종료 코드를 덮어쓴다. 원본 주석이 경고하던 바로 그 함정이다.
_acted=false
_graph_offer_log() {
  local _rc=$?
  local _log="${CLAUDE_PROJECT_DIR:-$PWD}/.omc/logs/graph_offer.jsonl"
  mkdir -p "$(dirname "$_log")" 2>/dev/null \
    && printf '{"ts":"%s","hook":"graph-offer","acted":%s}\n' \
       "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$_acted" >> "$_log" 2>/dev/null || true
  exit "$_rc"
}
trap _graph_offer_log EXIT

_gc="$(git rev-parse --git-common-dir 2>/dev/null)" || _gc=""
[ -n "$_gd" ] && _gd="$(cd "$_gd" 2>/dev/null && pwd)"
[ -n "$_gc" ] && _gc="$(cd "$_gc" 2>/dev/null && pwd)"
if [ -n "$_gc" ] && [ "$_gd" != "$_gc" ]; then
  repo="$(cd "$_gc/.." 2>/dev/null && pwd)" || repo=""
fi
is_git=1
if [ -z "$repo" ]; then
  is_git=0
  repo="$PWD"
  # Without git's toplevel there is nothing bounding "the current directory",
  # and an offer for $HOME or / invites a walk of the whole machine.
  [ "$repo" = "$HOME" ] && exit 0
  [ "$repo" = "/" ] && exit 0
fi

# Nothing to offer where a graph already exists — that project has answered.
#
# Both output names, not just this process's. `GRAPHIFY_OUT=.graphify` comes from
# the rendered settings.json, so a graph built inside a Claude Code session lands
# in `.graphify` while one built from a plain shell lands in `graphify-out`.
# Checking only one re-offers a project that already has a graph, and the offer
# is once-per-project — that wasted question is the only one it ever gets.
gout="${GRAPHIFY_OUT:-graphify-out}"
for d in "$gout" .graphify graphify-out; do
  [ -f "$repo/$d/graph.json" ] && exit 0
done
[ -d "$repo/.code-review-graph" ] && exit 0

if [ "$is_git" -eq 1 ]; then
  # The COMMON dir, so the marker is one per repository rather than one per
  # worktree — `repo` above already resolves to the main checkout, so asking
  # again from each new worktree would re-offer a graph that exists.
  # `_gc` is absolute or empty; the per-worktree `--git-dir` is the fallback for
  # the git versions that do not know `--git-common-dir`.
  git_dir="$_gc"
  if [ -z "$git_dir" ]; then
    git_dir="$(git rev-parse --git-dir 2>/dev/null)" || exit 0
    case "$git_dir" in
      /*) ;;
      *) git_dir="$repo/$git_dir" ;;  # relative when run from the repo root
    esac
  fi
  marker="$git_dir/claudebase-graph-offered"
else
  # No .git to hide it in, and writing a dotfile into someone's working tree to
  # record a question we asked is not our call. Keep it in ~/.claude keyed by
  # path. It goes stale if the directory moves, which costs one extra offer.
  #
  # ponytail: cksum is CRC32, so two paths can collide; the consequence is a
  # project that never gets offered. Swap in shasum if that ever matters.
  marker="$HOME/.claude/graph-offered/$(basename "$repo")-$(printf '%s' "$repo" | cksum | cut -d' ' -f1)"
fi
[ -e "$marker" ] && exit 0

# Only worth offering where tree-sitter has something to parse.
CODE_RE='\.(py|js|jsx|ts|tsx|go|rs|java|kt|c|h|cc|cpp|hpp|rb|php|swift|sh|bash|cs|scala|lua)$'
if [ "$is_git" -eq 1 ]; then
  # Counting tracked files keeps this consistent with what a git-repo build
  # indexes, so an untracked scratch directory never triggers an offer.
  code_count="$(git -C "$repo" ls-files 2>/dev/null | grep -icE "$CODE_RE")" || code_count=0
else
  # ponytail: depth 4 and a 50k cap bound what a SessionStart hook may spend on
  # an unknown mount. Deeper sources undercount, which only costs an offer.
  code_count="$(
    find "$repo" -maxdepth 4 -type f 2>/dev/null | head -50000 | grep -icE "$CODE_RE"
  )" || code_count=0
fi
[ "${code_count:-0}" -ge 20 ] || exit 0

# Only now, past every gate: a directory this hook decided to skip must not be
# left with state saying it was considered.
mkdir -p "$(dirname "$marker")" 2>/dev/null || exit 0
printf 'offered %s for %s code files\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$code_count" \
  >"$marker" 2>/dev/null || exit 0

repo_name="$(basename "$repo")"

# Name the command in a form that actually runs. `graph-init` is installed into
# ~/.local/bin next to uv's shims, and that directory is not on every login
# PATH — measured on the machine this was written on, where zsh -lic reported it
# absent. Telling someone to type a verb their shell cannot resolve is the same
# silent dead end this whole change exists to remove, so check first.
if command -v graph-init >/dev/null 2>&1; then
  verb="graph-init"
else
  # shellcheck disable=SC2088  # display text for a human to paste, never a path
  # this hook resolves — their shell expands the tilde, we must not.
  verb="~/.local/bin/graph-init"
fi

_acted=true

# python3 rather than hand-rolled escaping: the message is multi-line and the
# project name is arbitrary text.
python3 - "$repo_name" "$code_count" "$verb" <<'PY'
import json
import sys

name, count, verb = sys.argv[1], sys.argv[2], sys.argv[3]
ctx = f"""이 프로젝트(`{name}`)에는 코드 그래프가 없습니다 — 코드 파일 {count}개.
그래프가 있으면 호출자·영향 범위·리뷰 컨텍스트를 파일을 읽지 않고 색인에서 답할 수
있어 같은 질문이 훨씬 쌉니다. 이 안내는 이 프로젝트에 대해 한 번만 나옵니다.

사용자에게 AskUserQuestion으로 한 번 물어보세요 — 만들지 말지. 지금 하려던 작업이
있으면 그것부터 끝내고 물어도 됩니다. 만들기로 하면 명령은 하나입니다:

  {verb}

제외 규칙 설치 → 두 그래프 빌드(tree-sitter, 오프라인, 무료, 보통 수 초) →
노드 분포 검증까지 한 번에 합니다. vendored 트리(node_modules, 번들 플러그인 JS)가
그래프를 채웠으면 경고하고 exit 2로 끝나니, 그때는 `{verb} --purge`로 지우세요.
빈 껍데기 그래프는 없는 것보다 나쁩니다 — 가드가 매 턴 그걸 조회하라고 강제합니다.

프로즈(노트·문서) 의미 색인은 여기서 제안하지 않습니다 — LLM으로 수 시간 걸리므로
필요할 때 `/graphify`로 직접 실행하세요."""

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": ctx,
    }
}, ensure_ascii=False))
PY

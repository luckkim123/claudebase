#!/usr/bin/env bash
# SessionStart hook — offer to build a code graph, once per repository, ever.
#
# The gap this fills: graph-refresh.sh keeps existing graphs current and the
# PreToolUse guards route sessions through them, but a repository that never had
# a graph gets none of it, and nothing ever says so. Someone who does not know
# what an MCP server is will never type `/graphify`.
#
# Why an offer and not an automatic build. A graph built blindly is worse than
# no graph, because the guards then *require* the agent to consult it: measured
# on one Obsidian vault, 746 tracked .md files produced 0 nodes while 101 files
# of vendored plugin JS produced 21,425 "functions" and a 212 MB index — with no
# error anywhere. Auto-building would mass-produce that. Building also drops
# untracked directories into repositories the user merely opened to read.
# Deciding needs judgement, so this hook hands the decision to the session,
# which can look at the result and throw it away, and to the user, who owns the
# repository.
#
# Asked exactly once. The marker is written when the offer is *emitted*, not
# when the user answers, so ignoring the prompt is itself a durable answer and
# no repository ever nags twice. It lives inside .git/, which is per-repository,
# never committed, and disappears with the clone — unlike a central list under
# ~/.claude/, which would go stale the first time a repository moved.
#
# Scope: the free tree-sitter builds only. graphify's semantic pass reads prose
# with an LLM and runs for hours (measured 5.3 min/chunk over 58 chunks on one
# vault, because the claude-cli backend is pinned to concurrency 1), so it stays
# a deliberate `/graphify` invocation and is never offered from a hook.

set -u

repo="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
[ -n "$repo" ] || exit 0

git_dir="$(git rev-parse --git-dir 2>/dev/null)" || exit 0
case "$git_dir" in
  /*) ;;
  *) git_dir="$repo/$git_dir" ;;  # relative when run from the repo root
esac

marker="$git_dir/claudebase-graph-offered"
[ -e "$marker" ] && exit 0

# Nothing to offer where a graph already exists — that repository has answered.
gout="${GRAPHIFY_OUT:-graphify-out}"
[ -f "$repo/$gout/graph.json" ] && exit 0
[ -d "$repo/.code-review-graph" ] && exit 0

# Only worth offering where tree-sitter has something to parse. Counting tracked
# files keeps this consistent with what the graphs actually index (both walk
# `git ls-files`), so an untracked scratch directory never triggers an offer.
code_count="$(
  git -C "$repo" ls-files 2>/dev/null |
    grep -icE '\.(py|js|jsx|ts|tsx|go|rs|java|kt|c|h|cc|cpp|hpp|rb|php|swift|sh|bash|cs|scala|lua)$'
)" || code_count=0
[ "${code_count:-0}" -ge 20 ] || exit 0

printf 'offered %s for %s tracked code files\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$code_count" \
  >"$marker" 2>/dev/null || exit 0

repo_name="$(basename "$repo")"

# python3 rather than hand-rolled escaping: the message is multi-line and the
# repo name is arbitrary text.
python3 - "$repo_name" "$code_count" <<'PY'
import json
import sys

name, count = sys.argv[1], sys.argv[2]
ctx = f"""이 저장소(`{name}`)에는 코드 그래프가 없습니다 — 추적된 코드 파일 {count}개.
코드 그래프가 있으면 호출자·영향 범위·리뷰 컨텍스트를 파일을 읽지 않고 색인에서 답할 수 있어,
같은 질문이 훨씬 싸집니다. 이 저장소에 대해 이 안내는 이번 한 번만 나옵니다.

사용자에게 AskUserQuestion으로 한 번 물어보세요 — 만들지 여부와, 만든다면 어느 것을.
지금 하려던 작업이 있으면 그 작업을 먼저 끝내고 물어보면 됩니다.

만들기로 하면 (둘 다 tree-sitter, 오프라인, 무료, 보통 수 초):
  code-review-graph build     # 호출자·영향범위·리뷰 컨텍스트 질의용
  graphify .                  # 코퍼스 전체 모양, 허브, 커뮤니티

빌드 직후 결과를 반드시 검증하고, 쓸모없으면 지우세요. 빈 껍데기 그래프는 없는 것보다
나쁩니다 — PreToolUse 가드가 매 턴 그걸 조회하라고 강제하기 때문입니다. 확인할 것:
  - `code-review-graph status`의 노드 수와 languages 목록에 이 저장소에서 실제로 쓰는
    언어가 있는가
  - 노드가 vendored 코드(node_modules, 번들된 플러그인 JS, 서드파티 트리)에서 온 것은
    아닌가 — 이게 가장 흔한 실패다
  - 아니면 지운다: `rm -rf .code-review-graph` (graphify 쪽은 graphify-out/ 또는 .graphify/)

산출물은 그 저장소의 .gitignore에 없을 수 있습니다. 있다면 커밋하지 말고
`.git/info/exclude`에 넣으세요 (repo-local, 추적되지 않음).

프로즈(노트·문서) 의미 색인은 여기서 제안하지 않습니다 — LLM으로 수 시간 걸리므로
필요할 때 `/graphify`로 직접 실행하세요."""

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": ctx,
    }
}, ensure_ascii=False))
PY

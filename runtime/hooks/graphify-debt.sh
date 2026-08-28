#!/usr/bin/env bash
# .omc/logs 위치는 cwd 가 아니라 프로젝트 루트가 정한다 (hooklog.sh 참조).
_hl="$(dirname "$0")/hooklog.sh"
[ -r "$_hl" ] && . "$_hl"
command -v hooklog_state_root >/dev/null 2>&1 || hooklog_state_root() {
    printf '%s\n' "${CLAUDE_PROJECT_DIR:-$PWD}"   # fail-open: 훅은 세션을 막지 않는다
}
# SessionStart hook — surface how many prose files are waiting for a semantic
# re-extraction, before the backlog grows into a multi-hour job.
#
# The gap this fills. graphify's semantic cache is keyed by file content, so
# editing a note legitimately invalidates its entry and that file becomes
# uncached again. Nothing reports this. The count only surfaces when someone
# runs /graphify, and by then it can be days of drift: measured on one Obsidian
# vault, four days of ordinary note editing left 288 uncached files, which took
# a full session of subagent extraction (and two chunks died on the 64k output
# ceiling) to clear. Paid down weekly it is minutes; ignored it is an afternoon.
#
# Why not `graphify check-update`, which advertises exactly this. It reads the
# `needs_update` flag the watch loop maintains, not the cache. Measured on the
# same vault at the same moment: check-update printed nothing in 0.06 s while
# 10 files were genuinely uncached. Fast and silent is worse than slow and
# right for a detector, so this hashes the corpus the way the extractor does.
#
# What that costs, and why it is affordable anyway. The real count is a full
# content hash of every document/paper/image the detector finds — 2.9 s for 937
# files on that vault. Too slow for a per-turn hook, fine once per session, and
# gated three ways so it is nearly always skipped outright: the project must
# already carry a semantic cache (only a repo that paid for a prose pass has
# this debt at all), the count runs at most once per DEBOUNCE_HOURS, and the
# notice only speaks above a threshold.
#
# The threshold is not new. `graphify-resume-open.sh` used MIN_WORK=30 to decide
# whether a scheduled extraction was worth waking a session for; below that the
# job is minutes and the interruption costs more than the work. Same judgement
# here, same number.
#
# Scope: reporting only. It never extracts — the semantic pass is an LLM job
# measured in hours, so it stays a deliberate /graphify, exactly as
# graph-offer.sh says.

set -u

DEBOUNCE_HOURS="${GRAPHIFY_DEBT_DEBOUNCE_HOURS:-20}"
MIN_UNCACHED="${GRAPHIFY_DEBT_MIN:-30}"

# Anchor at the project that owns the graph, not wherever the shell sits — the
# same walk-up graphify-guard.sh does, and for the same reason: GRAPHIFY_OUT is
# a relative path resolved against cwd. An absolute one is already anchored.
gout="${GRAPHIFY_OUT:-graphify-out}"
repo="$PWD"
case "$gout" in
  /*) ;;
  *)
    d="$PWD"
    while [ "$d" != "/" ] && [ -n "$d" ]; do
      if [ -f "$d/$gout/graph.json" ]; then
        repo="$d"
        break
      fi
      d="$(dirname "$d")"
    done
    ;;
esac

out="$repo/$gout"
[ -f "$out/graph.json" ] || exit 0

# No semantic cache means this project never ran a prose pass, so there is no
# semantic debt to report and the 2.9 s hash would buy nothing. This is the gate
# that keeps every code-only repo on the machine out of the slow path.
[ -d "$out/cache/semantic" ] || exit 0

marker="$out/.semantic-debt-checked"
if [ -f "$marker" ]; then
  # `find -newermt` is GNU-only; -mmin is portable and this is minutes anyway.
  if [ -n "$(find "$marker" -mmin "-$((DEBOUNCE_HOURS * 60))" -print -quit 2>/dev/null)" ]; then
    exit 0
  fi
fi

# graphify runs from a uv tool venv, so the import needs THAT interpreter, not
# whatever python3 the login shell resolves. The skill writes the path here;
# fall back to uv's default location the way graphify-resume-open.sh did.
PY="$(cat "$out/.graphify_python" 2>/dev/null || true)"
[ -n "${PY:-}" ] && [ -x "$PY" ] || PY="$HOME/.local/share/uv/tools/graphifyy/bin/python"
[ -x "$PY" ] || exit 0

# The sha256 of this file IS the semantic cache's bucket key, so counting against
# a different spec would report every file as uncached. Absent → the skill is not
# installed here and the number would be a fiction.
spec="$HOME/.claude/skills/graphify/references/extraction-spec.md"
[ -f "$spec" ] || exit 0

count="$(cd "$repo" && SPEC="$spec" "$PY" -c "
import os
from pathlib import Path
from graphify.detect import detect
from graphify.cache import check_semantic_cache
r = detect(Path('.'))
files = [f for cat in ('document', 'paper', 'image') for f in r['files'].get(cat, [])]
_, _, _, uncached = check_semantic_cache(files, root='.', prompt_file=os.environ['SPEC'])
print(len(uncached))
" 2>/dev/null)" || count=""

case "${count:-}" in
  ''|*[!0-9]*) exit 0 ;;   # graphify moved its API, or the import failed — stay silent
esac

# Written whether or not the notice fires: the debounce exists to bound the 2.9 s,
# and a below-threshold project must not pay it again next session.
printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$count" >"$marker" 2>/dev/null || true

# 발화 기록 — harness_stats 가 이 파일명 리터럴을 grep 한다. 실패해도 무시.
# 임계값 게이트보다 앞: 실제 debt 계산이 끝난 지점이 이 훅의 일이 끝난 지점이고,
# 통지가 뜨는지 여부는 부차적 결정이다.
_log="$(hooklog_state_root)/.omc/logs/graphify_debt.jsonl"
mkdir -p "$(dirname "$_log")" 2>/dev/null \
  && printf '{"ts":"%s","hook":"graphify-debt"}\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$_log" 2>/dev/null || true

[ "$count" -ge "$MIN_UNCACHED" ] || exit 0

python3 - "$(basename "$repo")" "$count" "$DEBOUNCE_HOURS" <<'PY'
import json
import sys

name, count, hours = sys.argv[1], sys.argv[2], sys.argv[3]
ctx = f"""이 프로젝트(`{name}`)의 graphify 의미 색인에 미적중 {count}건이 쌓여 있습니다 —
그만큼의 노트가 마지막 추출 이후 내용이 바뀌었다는 뜻입니다. 캐시 키가 내용 해시라
이것 자체는 정상 동작이고, 지금 갚으면 몇 분입니다. 며칠 모으면 서브에이전트 추출
한 세션짜리 작업이 됩니다(실측: 4일치가 288건).

필요할 때 `/graphify`로 직접 실행하세요 — LLM을 쓰는 유료 경로라 자동으로 돌리지
않습니다. 지금 하려던 작업이 있으면 그것부터 끝내고 나중에 해도 됩니다.

이 안내는 미적중이 임계값 이상일 때만, {hours}시간에 한 번만 나옵니다."""

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": ctx,
    }
}, ensure_ascii=False))
PY

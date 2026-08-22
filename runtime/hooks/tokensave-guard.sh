#!/usr/bin/env bash
# tokensave hook wrapper — the same shape as graphify-guard.sh, and here for the
# same two reasons.
#
# 1. tokensave's own `install --agent claude` writes these hooks straight into
#    ~/.claude/settings.json, which claudebase RENDERS. They would survive until
#    the next install.sh and then vanish with no error. Declaring them in
#    config/settings.json is the only placement that persists.
# 2. A machine that has not run install.sh yet has no tokensave binary, and a
#    hook that fails is worse than a hook that is absent — so this exits 0 when
#    the binary is missing rather than letting the tool call error out.
#
# Usage: tokensave-guard.sh <pre-tool-use|prompt-submit|stop>
#   pre-tool-use  — matched on Agent|Grep|Bash; returns {"permission":"allow"}
#                   plus index context when a .tokensave/ index exists
#   prompt-submit — injects index context for the turn
#   stop          — records the turn's token accounting
#
# All three are no-ops outside an indexed repo: measured in a directory with no
# .tokensave/, pre-tool-use returns {"permission":"allow"} and the other two
# print nothing, all exit 0. stdin passes through untouched via exec, and the
# exit code stays tokensave's own.

set -u

mode="${1:-}"
case "$mode" in
  pre-tool-use | prompt-submit | stop) ;;
  *)
    # A misconfigured hook must never block a tool call or a turn.
    exit 0
    ;;
esac

# tokensave installs to ~/.local/bin (or brew's prefix); hooks get no login
# shell, so PATH alone is unreliable — same probe as installer/lib/deps.sh.
tokensave_bin="$(command -v tokensave 2>/dev/null || true)"
[ -n "$tokensave_bin" ] || tokensave_bin="$HOME/.local/bin/tokensave"

[ -x "$tokensave_bin" ] || exit 0

# 발화 기록 — harness_stats 가 이 파일명 리터럴을 grep 한다. 실패해도 무시.
# exec 앞에 두는 이유: exec 는 현재 프로세스를 교체해서 그 뒤 줄은 절대 실행되지
# 않는다. stdin 은 여기서 건드리지 않으니 "stdin passes through untouched via
# exec" 그대로 유지된다.
_log="${CLAUDE_PROJECT_DIR:-$PWD}/.omc/logs/tokensave_guard.jsonl"
mkdir -p "$(dirname "$_log")" 2>/dev/null \
  && printf '{"ts":"%s","hook":"tokensave-guard"}\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$_log" 2>/dev/null || true

exec "$tokensave_bin" "hook-$mode"

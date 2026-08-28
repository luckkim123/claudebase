#!/usr/bin/env sh
# hooklog.sh — 셸 훅이 `.omc/logs/` 를 어디에 둘지 정한다.
#
# 왜 있는가:
#   훅의 cwd 는 Bash 툴의 `cd` 를 따라간다. `${CLAUDE_PROJECT_DIR:-$PWD}` 는
#   CLAUDE_PROJECT_DIR 이 훅에 export 되지 않으므로 사실상 `$PWD` 이고, 그걸
#   그대로 쓰면 세션이 들른 디렉터리마다 `.omc/` 가 새로 생긴다 — 2026-08-28
#   실측, vault 한 곳에 18개. Python 쪽 hooklog.state_root() 와 같은 규칙이다.
#
# 규칙 (순서가 전부):
#   1. `.omc/` 를 이미 가진 가장 가까운 조상   ← 새로 만들지 않고 기존 것에 붙는다
#   2. 없으면 가장 가까운 `.git` 루트          ← 신규 프로젝트의 첫 발화
#   3. 그래도 없으면 시작 디렉터리
#   `$HOME` 에 닿으면 멈춘다 — `~/.omc` 가 실재하는 머신에서 모든 프로젝트의
#   계측이 홈 한 곳으로 고이는 것은 흩어지는 것과 같은 결함이다.
#   `.git` 을 1순위로 쓰면 안 된다: 중첩 git repo 가 있으면 거기에 다시 만든다.

hooklog_state_root() {
    _hl_start="${1:-$PWD}"
    _hl_start="$(cd "$_hl_start" 2>/dev/null && pwd)" || _hl_start="$PWD"
    _hl_home="$(cd "$HOME" 2>/dev/null && pwd)" || _hl_home="$HOME"
    _hl_git=""
    _hl_d="$_hl_start"
    while [ "$_hl_d" != "$_hl_home" ] && [ "$_hl_d" != "/" ] && [ -n "$_hl_d" ]; do
        if [ -d "$_hl_d/.omc" ]; then
            printf '%s\n' "$_hl_d"
            return 0
        fi
        [ -z "$_hl_git" ] && [ -e "$_hl_d/.git" ] && _hl_git="$_hl_d"
        _hl_d="$(dirname "$_hl_d")"
    done
    printf '%s\n' "${_hl_git:-$_hl_start}"
}

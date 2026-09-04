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
#
# 탈출구 `HOOKLOG_ROOT`:
#   프로젝트 루트가 동기화 폴더(Google Drive 미러) 안이면 위 규칙이 그대로
#   결함이 된다. jsonl 이 초 단위로 바뀌면 sync 엔진이 그걸 따라잡느라 큐가
#   막힌다 — 2026-09-04 실측, 대용량 파일 11 개가 한 시간 넘게 다운로드 순번을
#   못 받았고 두 머신 사이에 충돌 사본 17 개가 생겼다. 설정된 머신에서만
#   동작이 바뀌고, 원래 경로를 그대로 이어붙여 프로젝트별 구분은 유지한다.

# 계산된 루트를 HOOKLOG_ROOT 아래로 옮긴다. 미설정이면 그대로 통과.
# Python 쪽 hooklog._redirect() 와 같은 경로를 내야 한다.
#
# 해시가 아니라 경로를 그대로 중첩하는 이유:
#   한 디렉터리에는 이름이 여러 벌 있다. getcwd 는 들어갈 때 쓴 표기를 보존해서
#   같은 폴더가 NFC 로도 NFD 로도 나온다 — `/bin/pwd` 조차 접어주지 않는다.
#   해시는 바이트를 그대로 먹으므로 그대로 두 갈래가 된다: 2026-09-04 실측,
#   같은 vault 가 `내 드라이브-c59bcd93`(py, NFC) 과 `내 드라이브-717e4a44`
#   (sh, NFD) 로 갈렸다. 경로를 디렉터리 이름으로 쓰면 APFS 가 조회에서 정규화를
#   무시하므로 두 표기가 같은 디렉터리에 떨어진다 — 갈라짐이 원천에서 없어진다.
#   덤으로 셸 훅 발화마다 돌던 shasum 프로세스가 사라진다.
hooklog_redirect() {
    if [ -z "${HOOKLOG_ROOT:-}" ]; then
        printf '%s\n' "$1"
        return 0
    fi
    printf '%s\n' "$HOOKLOG_ROOT$1"
}

hooklog_state_root() {
    # `-P` 가 심볼릭 링크를 푼다. 없으면 `~/workspace` 로 들어온 세션과
    # 실경로로 들어온 세션이 서로 다른 루트를 잡는다 (Python 쪽 realpath 와 같은 뜻).
    _hl_start="${1:-$PWD}"
    _hl_start="$(cd -P "$_hl_start" 2>/dev/null && pwd)" || _hl_start="$PWD"
    _hl_home="$(cd -P "$HOME" 2>/dev/null && pwd)" || _hl_home="$HOME"
    _hl_git=""
    _hl_d="$_hl_start"
    while [ "$_hl_d" != "$_hl_home" ] && [ "$_hl_d" != "/" ] && [ -n "$_hl_d" ]; do
        if [ -d "$_hl_d/.omc" ]; then
            hooklog_redirect "$_hl_d"
            return 0
        fi
        [ -z "$_hl_git" ] && [ -e "$_hl_d/.git" ] && _hl_git="$_hl_d"
        _hl_d="$(dirname "$_hl_d")"
    done
    hooklog_redirect "${_hl_git:-$_hl_start}"
}

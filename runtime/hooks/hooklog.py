#!/usr/bin/env python3
"""훅 발화 1건을 <프로젝트 루트>/.omc/logs/<stem> 에 append 한다.

루트는 state_root() 가 cwd 에서 상승해 찾는다 — cwd 를 그대로 쓰면
`cd` 한 디렉터리마다 `.omc/` 가 새로 생긴다(아래 state_root 참조).

왜 있는가:
  2026-08-22 실측 — settings.json 에 배선된 훅 중 12 개는 로그를 남기도록
  만들어진 적이 없다. harness_stats.silent_guards() 는 그런 훅을
  "non_logging" 으로 분류하며, 그것은 미발화의 증거가 아니라 계측 부재의
  증거다. 이 헬퍼는 그 12 개를 "0 건 확정" 판정이 가능한 상태로 옮긴다.

stem 이 확장자를 포함하는 이유:
  harness_stats.logging_hooks() 는 각 훅 소스를 grep 해 `<name>.jsonl`
  리터럴을 찾는다(harness_stats.py:106,124). 헬퍼가 확장자를 붙여주면
  호출자 소스에 리터럴이 안 남아, 로깅을 붙이고도 non-logging 으로
  보고된다. 그래서 호출자가 파일명 전체를 넘긴다.

절대 안 죽는다:
  계측 훅이 예외를 던지면 사용자 턴이 죽는다. 어떤 실패도 조용히 삼킨다 —
  측정을 못 하는 것이 세션을 멈추는 것보다 낫다.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone


def _redirect(root: str) -> str:
    """HOOKLOG_ROOT 가 설정된 머신에서만 로그 루트를 그 아래로 옮긴다.

    왜: 프로젝트 루트가 동기화 폴더(Google Drive 미러) 안이면 state_root 의
    규칙이 그대로 결함이 된다. jsonl 이 초 단위로 바뀌면 sync 엔진이 그걸
    따라잡느라 큐가 막힌다 — 2026-09-04 실측, 대용량 파일 11 개가 한 시간 넘게
    다운로드 순번을 못 받았고 두 머신 사이에 충돌 사본 17 개가 생겼다.

    원래 경로를 그대로 이어붙여 프로젝트별 구분은 유지한다 — 홈 한 곳으로
    고이면 state_root 가 애초에 막으려던 그 결함이 된다.

    해시가 아니라 경로를 그대로 쓰는 이유:
      한 디렉터리에는 이름이 여러 벌 있다. 훅 페이로드의 `cwd` 는 어떤 훅은
      NFC, 어떤 훅은 NFD 로 주고, getcwd 는 들어갈 때 쓴 표기를 보존해서
      `/bin/pwd` 조차 접어주지 않는다. 해시는 그 바이트를 그대로 먹으므로
      한 프로젝트가 두 갈래로 갈린다 — 2026-09-04 실측, 같은 vault 가
      `내 드라이브-c59bcd93`(py, NFC) 과 `내 드라이브-717e4a44`(sh, NFD) 로
      갈렸다. 경로를 디렉터리 이름으로 쓰면 APFS 가 조회에서 정규화를
      무시하므로 두 표기가 같은 디렉터리에 떨어진다. state_root 의 realpath 가
      심볼릭 링크를, 이 중첩이 표기를 각각 하나로 모은다.
    """
    override = os.environ.get("HOOKLOG_ROOT")
    if not override:
        return root
    return os.path.join(override, root.lstrip("/"))


def state_root(cwd) -> str:
    """cwd 를 믿지 말고 `.omc/` 를 이미 가진 가장 가까운 조상을 찾는다.

    왜: 훅 페이로드의 `cwd` 는 Bash 툴의 `cd` 를 따라간다. 그걸 그대로 쓰면
    세션이 한 번이라도 들른 모든 디렉터리에 `.omc/logs/` 가 새로 생긴다 —
    2026-08-28 실측, vault 한 곳에 18 개. 한 session_id 가 서로 다른 3 개
    디렉터리에 로그를 남긴 것이 그 증거다. graphify-guard.sh 가 이미 쓰는
    상승 패턴과 같다.

    `$HOME` 안으로는 올라가지 않는다 — 이 머신엔 `~/.omc` 가 실재하고,
    거기까지 올라가면 모든 프로젝트의 계측이 홈 디렉터리로 고인다.
    `.omc/` 를 가진 조상이 없으면 `.git` 을 가진 가장 가까운 조상으로
    떨어진다(신규 프로젝트의 첫 발화가 하위 디렉터리에서 나도 루트에 남게).

    abspath 가 아니라 realpath 인 이유: 같은 디렉터리를 심볼릭 링크로도
    부르면(`~/workspace` → Drive 실경로) 루트가 둘로 갈라진다. 셸 쪽
    hooklog_state_root() 의 `cd -P` 와 같은 뜻이다.
    """
    start = os.path.realpath(cwd or os.getcwd())
    home = os.path.realpath(os.path.expanduser("~"))
    git_root = None
    d = start
    while d != home and os.path.dirname(d) != d:
        if os.path.isdir(os.path.join(d, ".omc")):
            return _redirect(d)
        if git_root is None and os.path.exists(os.path.join(d, ".git")):
            git_root = d
        d = os.path.dirname(d)
    return _redirect(git_root or start)


def fire(stem, cwd, session_id=None, **fields) -> None:
    """발화 1 건 기록. 실패해도 예외를 내지 않는다."""
    try:
        log_dir = os.path.join(state_root(cwd), ".omc", "logs")
        os.makedirs(log_dir, exist_ok=True)
        row = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "session_id": session_id,
        }
        row.update(fields)
        line = json.dumps(row, ensure_ascii=False, default=str)
        with open(os.path.join(log_dir, stem), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:  # noqa: BLE001, S110 — 훅은 세션을 막지 않는다
        pass

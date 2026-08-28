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
    """
    start = os.path.abspath(cwd or os.getcwd())
    home = os.path.abspath(os.path.expanduser("~"))
    git_root = None
    d = start
    while d != home and os.path.dirname(d) != d:
        if os.path.isdir(os.path.join(d, ".omc")):
            return d
        if git_root is None and os.path.exists(os.path.join(d, ".git")):
            git_root = d
        d = os.path.dirname(d)
    return git_root or start


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

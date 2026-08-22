#!/usr/bin/env python3
"""훅 발화 1건을 <cwd>/.omc/logs/<stem> 에 append 한다.

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


def fire(stem, cwd, session_id=None, **fields) -> None:
    """발화 1 건 기록. 실패해도 예외를 내지 않는다."""
    try:
        log_dir = os.path.join(cwd or ".", ".omc", "logs")
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

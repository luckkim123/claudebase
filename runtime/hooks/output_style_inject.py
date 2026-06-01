#!/usr/bin/env python3
"""UserPromptSubmit hook: inject output-style baseline as additionalContext.

Active only when CLAUDEBASE_OUTPUT_STYLE in {nudge, enforce}. Never raises;
any error -> exit 0 with no output. Idempotent marker: OUTPUT_STYLE_INJECT.

Baseline = the 5 research-backed defaults (see design.md §2):
  BLUF + meaningful headings / prose over bullets / table for comparisons /
  concise declarative tone (no chatty filler) / explicit knowledge-boundary
  over vague hedging. Plus: box-drawing via the box.py tool (design.md §8b),
  never inline ╭─╮ (CJK width drifts the right edge).
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from output_style_common import style_mode  # noqa: E402

BASELINE = (
    "[output-style] 답변 형식 기본값:\n"
    "1. 결론 먼저(BLUF) + 의미 있는 헤딩.\n"
    "2. 설명은 산문으로. 불릿은 진짜 병렬 항목일 때만, 중첩 금지.\n"
    "3. 항목 비교는 표로.\n"
    "4. 간결한 단정형. 구어체 필러('좋은 질문', 'Certainly!')·아첨 금지.\n"
    "5. 불확실하면 모호한 헤지 대신 지식 경계를 명시('X에 대한 출처 없음').\n"
    "6. 강조 블록은 box.py 도구로 그려라(인라인 ╭─╮ 금지 — 한글 폭에 우변 어긋남).\n"
    "   분류는 네가 내용을 보고 가장 적절한 제목을 직접 정하라(자율). 자주 쓰는 5종\n"
    "   (skill·analysis·plan·summary·warning)은 표준 라벨이 있으니 맞으면 `--type` 으로:\n"
    "   python3 ~/claudebase/runtime/bin/box.py --type analysis \"내용\"  또는\n"
    "   python3 ~/claudebase/runtime/bin/box.py \"네가 지은 제목\" \"내용\". 1-2개 한도, 연속 금지."
)


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return 0
    if payload.get("hook_event_name") != "UserPromptSubmit":
        return 0
    if style_mode(os.environ) == "off":
        return 0
    body = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": BASELINE,
        }
    }
    sys.stdout.write(json.dumps(body, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

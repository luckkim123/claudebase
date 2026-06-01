# Output Style — concise & structured

claudebase 의 출력-스타일 명세. **사람·모델 공통 참조본**. 강제는 hook 2개가 한다
(주입 `output_style_inject.py`, 검출 `output_style_guard.py`). 활성: `CLAUDEBASE_OUTPUT_STYLE` (off|nudge|enforce, 기본 off).

설계·근거: `docs/specs/2026-06-01-output-style-enforcement/{design,research}.md`.

## 5 기본값 (문헌 근거)

1. **결론 먼저(BLUF) + 의미 있는 헤딩.** 사람의 기본 스캔은 헤딩만 읽는 layer-cake — 그게 가장 효율적.
   [NN/g eyetracking]
2. **설명은 산문, 불릿은 진짜 병렬 항목일 때만 (중첩 금지).** Anthropic Claude4 system prompt·OpenAI
   GPT-5.1 guide 가 명시. [simonwillison.net/2025/May/25/claude-4-system-prompt]
3. **항목 비교는 표로.** 표가 산문보다 이해도↑ (RCT d=0.39). [PMC7137953]
4. **간결한 단정형. 구어체 필러·아첨 금지.** 장황할수록 더 틀리고(verbosity≠veracity, 27.6%↑),
   아첨은 신뢰↓. [arXiv 2411.07858 · 2310.13548]
5. **불확실하면 모호한 헤지 대신 지식 경계 명시** ("X 에 대한 출처 없음"). 모호한 헤지는 실제
   불확실성을 반영 못 함. [NAACL 2025 epistemic markers · Anthropic Constitution]

## 박스 (시각적 구획화)

**인라인 `╭─╮│╰─╯` 직접 그리기 금지** — CJK(한글=2칸) 폭 때문에 우변이 어긋난다. 대신 box.py 도구가
폭을 계산해 그린다(Claude Code 시작화면과 동일 원리). [Common Region, Palmer 1992]

```
python3 ~/claudebase/runtime/bin/box.py --type analysis "내용"
python3 ~/claudebase/runtime/bin/box.py "네가 지은 제목" "내용"   # 5종에 안 맞을 때
```

**분류는 Claude 자율** — 내용을 보고 가장 적절한 제목을 직접 정한다. 자주 쓰는 5종은 표준 라벨이 있어
`--type` 으로 편하게 쓸 수 있을 뿐, 강제 메뉴가 아니다:

| --type | 라벨 | 용도 |
|:---|:---|:---|
| `skill` | SKILL | 어떤 스킬/라우팅을 썼나 (`--label X` → `SKILL · X`) |
| `analysis` | 분석 | 요청·문제의 해석 |
| `plan` | 계획 | 할 일 순서 |
| `summary` | 요약 | 결과 정리 |
| `warning` | 주의 | 놓치면 손해 보는 것 |

남용 금지: 페이지당 1-2개, 연속으로 쌓지 말 것. [Google·NN/g style guide]

## 켜기 / 끄기

Claude Code 는 settings 의 `env` 를 hook 에 주입하지 *않으므로*, hook 이 두 소스를 직접 본다:
부모 셸 export(우선) → `~/.claude/settings.local.json`·`settings.json` 의 `env.CLAUDEBASE_OUTPUT_STYLE`.

**켜기 (택1)** — 둘 다 효과 동일, 다음 세션부터 적용:
- 이 머신만: `~/.claude/settings.local.json` 의 `"env"` 에 `"CLAUDEBASE_OUTPUT_STYLE": "enforce"` (gitignored).
- 셸 단위: `~/.zshrc` 등에 `export CLAUDEBASE_OUTPUT_STYLE=enforce`.

**끄기**:
- settings.local.json 에서 키 제거(또는 `"off"`), 또는 export 제거.
- `DISABLE_OMC` / `OMC_SKIP_HOOKS=output_style` — kill switch (강제 off).

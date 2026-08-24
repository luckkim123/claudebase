# 사용자 프롬프트 이해도 향상 — 조사 보고서

조사일: 2026-08-22. 범위: 방법론(arXiv) + 기성 구현(MCP/훅) + 이 rig의 현재 상태 대조.
어떤 코드도 수정하지 않았다. 결론은 "무엇을 새로 만들지"가 아니라 "무엇을 지우거나 배선할지"를
우선 판단하는 데 맞춰져 있다(사용자 확정 방향).

---

## 헤드라인

플랫폼 자체가 이미 정답에 가까운 것(`AskUserQuestion`)을 갖고 있고, 이 rig는 그 위에 **실패
방지용 가드**(빈 호출 차단)만 배선했지 **품질 개선용 로직**(언제 물을지 판단, 과거 질문 재사용)은
전혀 배선하지 않았다. 새 MCP 서버·새 스킬을 추가하는 방향은 근거가 약하다 — GitHub에 이미 5개
이상의 거의 동일한 "clarify MCP"가 있고, 전부 네이티브 `AskUserQuestion`을 재포장한 것이다. 또한
플랫폼 구조상 **UserPromptSubmit 훅은 프롬프트 텍스트 자체를 재작성할 수 없다** (2026-08-22
기준 anthropics/claude-code #53330, #34390, #46761이 전부 열려 있는 기능 요청) — 이는 "prompt
rewriting" 방향의 설계를 처음부터 제약한다.

사용자가 명시한 요구 — "과거에 질문했던 기록을 참고한다" — 는 **구현되어 있지 않다** (verified,
아래 §5). `askuserquestion_stats.py`는 질문의 *내용*이 아니라 *실패*(빈 호출·재시도)만 집계한다.

---

## 1. 정량 근거 — "명확화 질문이 결과를 개선하는가"

| 주장 | 근거 | confidence |
|---|---|---|
| 정보이득 기반으로 선택한 명확화 질문은 무조건(no-clarification) 대비 일관되게 성능을 높인다 | arXiv 2606.03135 (Uncertainty-Aware Clarification with Information Gain) — 초록: "introducing clarification consistently improves performance over the no-clarification setting" | likely (초록만 확인, 수치 표는 미확인) |
| 과잉 질문의 실측 비용: 프런티어 모델 세션의 52%가 "over-asking"이고, 최적 타이밍 창에서 묻는 모델이 하나도 없다 | arXiv 2605.07937 (Ask Early, Ask Late, Ask Right) — 84 task variants, 6,000+ runs, 300 unscripted sessions, 4개 프런티어 모델 | likely (WebFetch 요약 기반, 원문 표 미확인) |
| 정보 유형별로 "언제 물어야 하는가"가 다르다: 목표(goal) 명확화는 실행 10% 지난 시점부터 가치가 거의 0으로 떨어지고(pass@3 0.78→baseline), 입력(input) 명확화는 실행 50% 지점까지 가치 유지. 어느 쪽이든 중간 지점을 지나 미룬 명확화는 아예 안 묻느니만 못하다 | 같은 논문(2605.07937) | likely |
| 태스크 관련성(Shapley 기여도)과 사용자 답변 가능성을 함께 최적화하면 GPT-5급 성능을 유지하면서 질문 수를 41% 줄일 수 있다 | arXiv 2604.14624 (CLARITI, Asking What Matters) | likely |
| 모델은 명시적으로 판정을 요구받으면 모호성을 인식하지만, 일반 QA에서는 압도적으로 직답을 택하고, 검색된 컨텍스트가 주어지면 오히려 명확화 경향이 더 줄어든다 | arXiv 2605.25284 (Knowing but Not Showing) | likely |
| 불확실성 인지 다중에이전트 스캐폴드(명확화 필요성 탐지와 코드 실행을 분리)로 SWE 과제 해결률 61.20%→69.40% | arXiv 2603.26233 (Ask or Assume?) | likely |
| 정보이득(Bayesian Experimental Design)으로 선택한 질문이 "질문 공간에서만 추론"하는 방식보다 더 효과적으로 태스크 모호성을 해소 | arXiv 2502.04485 (Active Task Disambiguation with LLMs) | likely (수치 표는 원문 PDF 미확인) |

**"사용자는 과잉 질문을 싫어할 가능성이 높다"는 사용자의 가설과 위 §2605.07937/§2604.14624가
정확히 같은 결론을 낸다**: 질문 수를 최소화하면서 최대 정보이득/태스크 관련성만 골라 묻는 것이
연구 컨센서스다. "필요할 경우"라는 요구사항 문구는 이 문헌과 정합적이다 — 무조건 더 묻는 방향은
연구로도 뒷받침되지 않는다.

한계: 이 표의 수치는 모두 WebFetch가 요약한 초록 기반이다. 원문 PDF의 표·통계 검정은 직접
읽지 않았다 — "확인 안 함"으로 남긴다.

---

## 2. 방법론 지형 (분류)

- **모호성 판정(uncertainty estimation)**: 정보이득/Bayesian Experimental Design으로 "이 질문이
  해답 공간을 얼마나 좁히는가"를 계산해 질문 여부·순서를 결정 (2502.04485, 2606.03135).
- **질문 생성 자체의 실패 모드**: 모델이 모호성을 "판정"은 하지만 "행동"으로 옮기지 않는다는
  recognition-action gap (2605.25284) — 이는 순수 프롬프트 지시("모르면 물어봐")로는 안 고쳐질
  가능성을 시사한다. 판정과 행동이 별도 메커니즘이라는 뜻이라서, 이 rig의 접근(CLAUDE.md 텍스트
  규칙 + 훅 가드)이 딱 이 이중구조를 반영한다 — 텍스트 규칙은 "판정"에 관여, 훅은 "행동 실패"만
  잡는다. 그 사이(판정→올바른 행동 전환)를 강제하는 장치는 없다.
- **타이밍(when in the trajectory to ask)**: 태스크 오래 실행할수록 질문 가치가 정보 유형별로
  다르게 감쇠 (2605.07937) — "일단 시작하고 막히면 묻는다" 전략은 목표 관련 질문에서는 특히
  나쁘다.
- **비용 최소화(reward-driven, 답변가능성 가중)**: CLARITI류는 질문 수 자체를 목적함수에 넣어
  줄인다 (2604.14624).
- **spec-first / requirements elicitation**: 이 rig에 이미 `deep-interview` 스킬이 이 계열을
  통째로 구현하고 있다 (Ouroboros 영감, 가중 차원별 ambiguity score, 라운드당 질문 1개, 0.2
  임계값 도달까지 반복). 별도 조사 불필요 — §4 참조.
- **prompt rewriting/expansion**: 플랫폼 제약(§0 헤드라인)으로 UserPromptSubmit 훅에서는
  구조적으로 불가능. `additionalContext` 주입만 가능하며, 이것이 정확히 omha 훅이 하는 일이다.
- **few-shot from past interactions / user modeling / preference memory**: 조사한 논문 중
  이 축을 직접 다루는 것은 찾지 못했다(검색 범위 내에서는 없음 — "없음"). 이 축의 현실 사례는
  이 rig의 auto-memory(`~/.claude/projects/*/memory/`)가 실질적으로 이미 하고 있는 일에 더
  가깝다: 세션 간 학습을 텍스트 파일로 축적. 다만 "질문 자체"의 축적은 안 되어 있다 (§5).

---

## 3. 기성 구현 조사

### 3.1 플랫폼 제약 (verified)

UserPromptSubmit 훅은 **프롬프트 텍스트를 재작성/치환할 수 없다** — `additionalContext` 첨부와
차단(block)만 가능. 2026-08-22 기준 다음 이슈가 전부 open으로 이 기능을 요청 중:
anthropics/claude-code#53330, #34390, #46761 (URL은 WebSearch 결과 참조). 이는 "프롬프트를
증강·재작성하는 실제 사례"를 GitHub에서 찾으라는 지시에 대한 직접 답이기도 하다 — **재작성 사례가
없는 이유가 곧 발견**이다: 플랫폼이 막고 있다. 있는 사례는 전부 `additionalContext` 주입형이며,
그 최적 구현이 이미 이 rig의 omha 훅이다 (`route_emit.py:143-145`, 매 턴 라우팅 판정 주입).

### 3.2 MCP 서버 (기성 "clarify" 도구들)

발견된 것: `ifmelate/mcp-clarify`, `Jacob-J-Thomas/user-context-retrieval-mcp-server`,
`paulp-o/ask-user-questions-mcp`, `mako10k/mcp-confirm`, `LumabyteCo/clarifyprompt-mcp`.
전부 "AI가 사용자에게 구조화된 질문을 던지는 human-in-the-loop 도구"이며, Claude Code 상에서는
네이티브 `AskUserQuestion` tool과 **기능 중복**이다. `clarifyprompt-mcp`만 다른 각도 — "모호한
초안 프롬프트를 받아 1-3개 명확화 질문을 반환"하는 프롬프트-최적화 전(前)단계 도구인데, 이것도
`AskUserQuestion`으로 동일 UX를 이미 구현 가능하다.

판단(confidence: likely, 채택 반대): 이 다섯 개 중 어느 것도 이 rig에 새로 배선할 근거가 약하다
— 네이티브 도구가 이미 있고, om* 5종 A/B(§0)에서 스킬 존재 자체가 결과를 바꾸지 못했다는 실측이
있는 상황에서 "질문 던지는 도구"를 하나 더 추가하는 건 정확히 사용자가 경계한 패턴이다.

---

## 4. 대조 — 이미 가진 것 vs 실제로 안 되는 것

정독 확인(전부 Read tool로 직접 읽음):

| 구성요소 | 파일 | 실제로 하는 일 | 안 하는 일 |
|---|---|---|---|
| omha 라우팅 훅 | `~/oh-my-heroacademia/hooks/route_emit.py:1-150` | 매 턴 UserPromptSubmit에서 `cards/*.json`을 읽어 레인 판정 컨텍스트를 `additionalContext`로 주입 (`route_emit.py:143-145`). "사용자가 무엇을 원하는지 아직 안 정한 상태(의중 미결정)"이면 라우팅 스킬을 읽으라는 지시까지 포함(`:132-133`) | 프롬프트 자체의 모호성 점수화는 안 함. "이 프롬프트에 명확화가 필요한가"를 판정하는 로직 없음 — 레인(어디로 갈지)만 판정, 명확성(뭘 원하는지 아는지)은 별개 |
| `deep-interview` 스킬 | `.../skill-bodies/deep-interview/SKILL.md` | 가중 차원별(goal/constraint/criteria/context) ambiguity score를 계산, 라운드당 질문 1개, 임계값(기본 0.2) 도달까지 반복, Round 0 토폴로지 확정 게이트, 4/6/8라운드 challenge mode(contrarian/simplifier/ontologist), 최종 spec을 `.omc/specs/`에 기록. Brownfield는 `explore` agent로 코드부터 확인 후 질문(`:44`, `:576-585` — "코드가 이미 답을 준 걸 사용자에게 묻지 마라") | **명시적으로 invoke해야만** 작동 — 자동 발동 아님("interview me", "ouroboros" 등 키워드 트리거). 일상 대화형 프롬프트에는 관여하지 않음. 그리고 §0 실측이 이미 보여주듯 om* 스킬 전체가 스킬 *호출* 자체는 0건이었던 A/B가 있다 — deep-interview도 트리거되지 않으면 존재하지 않는 것과 같다 |
| AskUserQuestion 가드 3종 | `~/claudebase/runtime/hooks/askuserquestion{-guard,_retry,_stats}.py` | **오직 malformed-call 방지**: `-guard.py`(PreToolUse)는 questions 배열이 비었거나 타입 오류거나 서로게이트 문자가 섞인 호출을 deny(`:191-237`). `_retry.py`(Stop)는 questions 필드 자체가 통째로 빠진 호출(하네스 스키마 검증이 PreToolUse보다 먼저 거부하는 케이스, `-guard.py`가 구조적으로 못 잡는 그 케이스)을 잡아 재시도시킴, 3회 연속 실패 시 "abandon" 모드로 전환(`_retry.py:32-47`). `_stats.py`는 이 두 로그를 합산해 실패율만 리포트(§5) | **질문의 내용·언제 물을지·과거에 뭘 물었는지는 전혀 다루지 않는다.** 순수 형식 오류 방지 계층 — "품질" 축이 아니라 "붕괴 방지" 축 |
| auto-memory feedback 기록 | `~/.claude/projects/-Users-kimseungmin-ksm-Obsidian/memory/feedback_*.md` | 과거 실수 패턴을 서술형으로 축적(예: `feedback_askuserquestion_empty_recurs.md` — 언제 빈 호출이 재발하는지; `feedback_plan_decision_escalation.md` — 사용자 결정 사항을 스스로 결정하면 안 된다는 룰; `feedback_apply_user_decisions.md` — 이미 받은 답을 되묻지 말라) | 이것들은 **일반 행동 교훈**이지 "이 사용자가 과거에 어떤 질문에 어떻게 답했는지"의 구조화된 로그가 아니다. 세션 시작 시 MEMORY.md 색인을 읽는 것으로 간접 참고는 되지만, "명확화 질문 생성 시 과거 답변 패턴을 few-shot으로 참조"하는 메커니즘은 없다 |

---

## 5. 실측 — "과거 질문 기록 참고"는 어디까지 구현돼 있나

**결론: 구현되어 있지 않다 (verified).**

`~/claudebase/runtime/hooks/askuserquestion_stats.py:48-76` (`aggregate()` 함수)를 직접 읽었다.
이 스크립트가 두 로그 파일에서 fold하는 필드는:

```
total, guard_denies, retry_rejections, abandon_events, by_session(session_id → count)
```

기록되는 것은 **"실패했다는 사실과 세션 ID"뿐**이다 (`askuserquestion-guard.py:126-128`의
`_log_deny`가 쓰는 레코드도 `{"signal": "denied_askuserquestion", "session_id": session_id}`
뿐 — 질문 텍스트, 옵션, 사용자의 실제 답변 중 어느 것도 기록하지 않는다). 저장 목적 자체가
"하드닝이 빈 호출률을 실제로 줄였는지"를 확인하기 위한 실패 텔레메트리이지(파일 상단 docstring
`:2-18`), 질문 콘텐츠를 재사용하기 위한 로그가 아니다.

따라서 사용자가 원하는 "과거에 이런 걸 물었더니 이런 답이 왔다"를 다음 명확화 질문 생성에
반영하는 기능은:
- 로그 스키마가 애초에 그 데이터를 담지 않음 (질문 텍스트·옵션·답변 전부 부재)
- 이 로그를 읽어 질문 생성에 반영하는 코드도 존재하지 않음(검색 범위 내에서 없음)
- 인접 대체재인 auto-memory(feedback_*.md)는 사람이 쓴 서술형 교훈이라 "질문 패턴"을
  구조적으로 검색 가능한 형태가 아님

---

## 6. 지울 것 / 통합할 것 판단 (사용자 확정 방향에 따라 제거·통합 우대)

이 rig의 §0 실측(코드 정확성 축 8/8 동점, 규율 축만 Δ+0.222, 그 런에서 Skill 호출 0건, 비용
+69%/토큰 +41%)을 이 조사 결과에 그대로 적용하면:

- **"clarify MCP 서버 추가"는 기각 근거가 명확하다.** 네이티브 `AskUserQuestion`과 완전 중복,
  게다가 새 MCP 프로세스는 그 자체로 컨텍스트·토큰 비용이며 A/B에서 스킬층 추가가 결과를 안
  바꾼다는 실측과 정확히 같은 리스크 프로파일이다.
- **"UserPromptSubmit에서 프롬프트를 재작성"은 설계 자체가 불가능**(§3.1) — 이 방향의 스킬/훅
  설계안이 나오면 그 자리에서 기각해야 한다(플랫폼 제약, 우회 불가).
- **AskUserQuestion 가드 3종(guard/retry/stats)은 서로 다른 실패 모드를 잡는 상보적 구조라
  중복 없음** — 통합·삭제 후보 아님. 다만 `_stats.py`는 "MANUAL diagnostic, NOT wired into
  any hook"(파일 자체 docstring)이라 실제로 실행된 적이 있는지는 미확인 — 실행 이력을 확인해
  0회라면(unverified, 이번 조사에서 실행 로그는 안 봄) 그 자체가 하나의 데이터 포인트다.
- **deep-interview는 이미 존재하는 무거운 정답이지, 새로 만들 필요가 없다.** 문제는 스킬
  부재가 아니라 **일상 대화형 프롬프트에서 자동 발동하지 않는다**는 점 — 이건 "만들기"가 아니라
  "배선"(트리거 확장) 문제로, 사용자 확정 방향(제거·통합·배선 우대)과 정합적인 유일한 실질
  개선 지점이다. 다만 이것도 §0의 결론(스킬 호출 자체가 A/B에서 0건이었다)을 감안하면, 트리거를
  넓히기 전에 "일상 프롬프트에서 deep-interview가 실제로 발동해야 하는 빈도가 얼마나 되는가"를
  먼저 측정해야 한다 — 지금은 그 빈도의 실측이 없다(unverified).
- **"과거 질문 로그 → few-shot"은 만들 수는 있지만 입증 부담이 크다.** 조사한 논문 중 이 축
  자체(과거 대화 세션 간 질문 재사용)를 다루는 것은 없었다(§2, "없음"). 이걸 새로 만드는 제안은
  "스킬을 더 만들자"류와 같은 카테고리이므로, 사용자 확정 방향상 defer해야 한다. 대신 저비용
  대안: `askuserquestion_stats.py`의 로그 스키마에 질문/답변 텍스트를 추가하는 것은 **새 컴포넌트
  추가가 아니라 기존 훅의 필드 확장**이라 제거·통합 원칙과 덜 충돌한다 — 이것이 유일하게
  "만들기"와 "측정 우선" 원칙이 둘 다 만족되는 지점으로 보인다(효과 검증은 별도 필요).

---

## 확인하지 않은 것 (명시)

- arXiv 논문 6편의 원문 PDF 통계표는 미확인 — 전부 WebFetch의 초록/HTML 요약 기반.
- `askuserquestion_stats.py`가 실제로 실행된 이력(로그 파일에 데이터가 쌓여 있는지)은 확인
  안 함 — `.omc/logs/askuserquestion_{guard,retry}.jsonl`을 이번 조사에서 열어보지 않았다.
- deep-interview가 실제 세션에서 몇 번 트리거됐는지 빈도는 확인 안 함.
- omha 카드(`cards/*.json`) 내용 자체(레인 7개 각각의 세부 규칙)는 라우팅 훅 파일만 읽었고
  카드 JSON 개별 파일은 열지 않음.

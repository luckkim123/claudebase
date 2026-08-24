# 루프 엔지니어링(loop engineering) 조사 — 지울 것 우선

조사일: 2026-08-22. 범위: 방법론 갈래 정의, 2025-2026 실제 동향(arXiv+GitHub), 사용자
보유 구현(`~/claudebase`, `~/oh-my-experiments`, `~/.claude/plugins/cache/omc`) 실측 대조,
지우거나 단순화할 수 있는 것.

---

## 0. 결론 먼저

**사용자는 이미 "루프 엔지니어링" 분야 최상위 성숙도 도구를 갖고 있다.** `docs/loop-contract.md`가
정의한 5속성(상태파일·결정론적 종료·시도상한+에스컬레이션·독립 컨텍스트 검증자·활동증거)은
2026-08-15 cobusgreyling/loop-engineering(★10,532, 오늘도 push됨)의 `loop-audit` 35-지표
가중치 분석에서 역산한 것이고, `exp-loop`(omx)는 실측상 5속성 전부 `ok`에 실제 활동 증거까지
갖춘 유일한 루프다. 외부에서 새로 가져올 "기법"은 거의 없다 — 있는 것은 주로 **명명(vocabulary)**과
**감사 CLI 하나**뿐이다.

지울 후보: `ultragoal`은 결정론적 종료·상한·검증자 3개가 전부 `--`(2026-08-22 린터 실측,
아래 §3). 로컬 컨트랙트 기준으로 최약체이며, `autopilot`/`ralph`와 기능이 겹친다. 새 루프를
만들기 전에 먼저 `ultragoal`을 계약 위에 재작성하거나 폐지 후보로 올리는 쪽이, 외부 기법을
들여오는 것보다 이 조사의 결정 기준("무엇을 지울지 먼저")에 부합한다.

---

## 1. "루프 엔지니어링"의 갈래 — 정의가 하나가 아니다

용어 자체가 2026년에 새로 생긴 브랜딩이고, 그 아래 가리키는 개념은 최소 4갈래로 갈린다.
갈래 사이 경계는 명확하지 않고 대부분의 실제 구현은 2개 이상을 섞는다.

| 갈래 | 정의 | 대표 원류 |
|:---|:---|:---|
| **A. 추론 루프** (ReAct 계열) | 한 턴 안에서 think→act→observe를 반복해 최종 답을 만드는 것. 모델 호출 자체의 구조. | ReAct (2022), Reflexion (2023) |
| **B. 정제 루프** (self-refine / evaluator-optimizer) | 초안을 만들고, (같거나 다른) 평가자가 피드백을 주고, 다시 고치는 것을 수렴 또는 상한까지 반복. | Self-Refine (2023), MAgICoRe(2409.12147, arXiv 확인) |
| **C. 세션 영속 루프** (ralph / boulder-never-stops) | 한 세션이 끝나도 상태 파일(plan.md, progress.txt)로 이어붙여 "작업이 끝날 때까지" 여러 세션·여러 프로세스를 계속 재기동. 코드 에이전트 특유. | Geoffrey Huntley "Ralph Wiggum" (2025-05, ghuntley.com/ralph) |
| **D. 하네스/오케스트레이션 루프** | plan→execute→verify를 서로 다른 컨텍스트(별도 서브에이전트)로 쪼개, 상태를 프로세스 밖 파일에 두고, 결정론적 게이트로 다음 라운드를 트리거. | Anthropic "Effective Harnesses for Long-Running Agents"(2025-11), "Harness Design for Long-Running Application Development"(2026-03, 웹서치로 존재·날짜 확인. loop-contract.md L45의 "2026-03-24" 인용과 정합) |

`cobusgreyling/loop-engineering`이 파는 "loop engineering"이라는 브랜드는 위 C·D를 합쳐
"에이전트가 알아서 도는 시스템을 설계하는 것" 전반을 가리키는 마케팅 용어에 가깝다 — 정의:
"discovers work, delegates it, verifies against tests or deterministic gates, persists state
outside the model, decides what happens next, runs again on a cadence/event/goal"
(WebSearch 결과 원문, README 요약). 이 정의는 D와 사실상 동일하다.

confidence: A/B/C/D 구분과 원류 저자 — likely(웹서치 요약 기반, 원문 전체 정독 안 함).
C의 발명 연도·매체 — verified(다수 독립 출처: tessl.io, linearb.io, ghuntley.com 일치).

---

## 2. 2025-2026 실제 유행 갈래 — arXiv과 GitHub 양쪽

### arXiv (검색: cs.AI/cs.CL/cs.SE, 2025-06 이후, `mcp__arxiv__search_papers` 실행 결과)

압도적으로 몰리는 축은 **"long-horizon agent" + "reflection/self-correction/verification"**
결합이다. B(정제)와 A(추론) 사이 경계가 흐려지는 추세:

| 논문 | id | 요지 | 이 프로젝트와의 연결점 |
|:---|:---|:---|:---|
| PARC | 2512.03549 (2025-12) | 계층형 멀티에이전트, "평가·피드백을 **독립 컨텍스트**에서" 수행 — 43시간짜리 병렬 시뮬레이션 오케스트레이션까지 무인 실행 | loop-contract 속성4(검증자는 별도 컨텍스트)와 문자 그대로 같은 설계 원칙을 arXiv 논문 하나가 이름 붙여 재확인 |
| MAgICoRe | 2409.12147 (2024-09, 인용 다수 지속) | 정제 루프의 3대 실패 모드를 정리: 과잉정제·오류 국소화 실패·부족정제. "몇 라운드 돌릴지"를 문제 난이도로 분기 | loop-contract의 "cap이 숫자 하나뿐"이 아니라 상황별로 갈릴 수 있다는 것의 논문 근거 |
| ReTree (자기교정 트리 메모리) | 2608.10676 (2026-08) | ReAct 풀 트래젝토리를 그대로 넣는 대신, 되돌아갈 수 있는 트리 구조로 국소 정정 | exp-loop의 ledger(선형 기록)와 다른 대안 구조 — 참고만, 채택 근거 약함 |
| GRACE (Scoped Verification) | 2607.09175 (2026-07) | 지속되는 시스템 지침을 타입드 그래프로 유지하며 "로컬 검증"으로 장기 컨텍스트 진화의 신뢰도를 확보 | garden/wiki 계열(omp-garden, wiki lint)과 문제의식이 겹침 — "누적 지침이 스스로 부패한다"는 문제를 그래프 검증으로 다룸 |
| LoongReflect | 2608.11967 (2026-08) | reflect/backtrack을 명시적 액션으로 학습 — 언제 되돌아갈지를 모델이 스스로 판단하도록 훈련 | "stop 조건을 모델 자신감으로 두지 마라"(loop-contract 속성2)의 반례 방향 연구 — 학습으로 그 자신감을 신뢰가능하게 만들려는 시도. 아직 연구 단계, 운영 규범으로 채택할 단계 아님 |

전체적으로 2025H2~2026 arXiv 흐름은 **"검증을 어디서 어떻게 하느냐"**(독립 컨텍스트, 그래프
국소성, 트리 되돌리기)에 집중돼 있고, "언제 멈추느냐"(결정론적 stop, 숫자 cap)는 대부분
공학적 디테일로 취급되어 논문 헤드라인이 되지 않는다. 이 점이 이 저장소의 실측(§0)과 정확히
대칭이다 — `loop-contract.md`가 밝힌 격차(ultragoal의 stop/cap/verif 부재, §3)는 정확히
arXiv이 활발히 다루는 지점이고, 이미 잘 갖춘 exp-loop의 강점(결정론적 stop+숫자 cap+에스컬레이션)은
arXiv이 거의 안 다루는 "이미 해결된 것으로 치는" 지점이다.

confidence: 표의 각 논문 요지 — verified(초록 원문 인용). "arXiv이 검증 위치에 집중"이라는
결론 — likely(15+10건 표본에서 관찰된 패턴, 전수조사 아님).

### GitHub (WebSearch + `gh api` 실측)

| 저장소 | URL | 별 | 최근 push | 핵심 아이디어 |
|:---|:---|---:|:---|:---|
| cobusgreyling/loop-engineering | github.com/cobusgreyling/loop-engineering | **10,532** | 2026-08-22(오늘) | loop-audit(35지표 성숙도 채점 CLI) + loop-init(스캐폴드) + loop-cost. `docs/loop-contract.md`가 이미 이 저장소의 `auditor.ts` 가중치를 인용해 5속성을 역산했음(loop-contract.md L14-24) |
| maxmilian/loop-engineering | github.com/maxmilian/loop-engineering | 22 | 2026-06-24 | Claude Code/Codex/Copilot/Gemini용 "스킬" 형태 — 12개 소스를 7원칙으로 증류. 벤치마크에서 87%→100% 통과율 주장(자체 벤치, 재현 안 함) |
| anil2799/2026-06-27-loop-engineering | github.com/anil2799/... | 0 | 2026-06-27 | cobusgreyling 저장소의 개인 포크로 보임(설명문 동일) — **죽음**(스타 0, 활동 없음) |
| ghuntley/how-to-ralph-wiggum | github.com/ghuntley/how-to-ralph-wiggum | 미확인(웹서치 요약만) | 미확인 | ralph 기법 원 저자 본인의 방법론 저장소. C 갈래의 1차 출처 |

`gh api` 확인: cobusgreyling가 압도적 1위이고 살아있다. loop-contract.md가 이미 이 저장소를
1차 근거로 삼고 있으므로, **"새로 발견한 외부 기법"이 아니라 "이미 인용 중인 근거의 최신
활동성 재확인"**이 이번 조사의 실제 기여다.

confidence: 별 수·push 날짜 — verified(`gh api` 직접 조회). anil2799가 포크라는 판단 — likely(설명문 완전 일치 관찰, 포크 관계 자체는 GitHub API로 확인 안 함).

---

## 3. 비교축 — 사용자가 이미 가진 것 vs 진짜 없는 것

`docs/loop-contract.md`, `runtime/hooks/loop_lint.py`(둘 다 직접 정독), `omx_core/loop.py`,
`skills/exp-loop/SKILL.md`(직접 정독)를 근거로 한다. 2026-08-22 실측 린터 결과(§0 결론의 표 재게재):

```
plugin/skill                     state  stop   cap escal verif   activity
om:claudecode/autopilot             ok    ok    ok    ok    ok     0 (none found)
om:claudecode/ralph                 ok    ok    ok    ok    ok     0 (none found)
om:claudecode/ultragoal             ok    --    --    ok    --     0 (none found)
om:claudecode/ultraqa                ok    ok    ok    --    ok     0 (none found)
om:claudecode/ultrawork             --    ok    --    ok    ok     0 (none found)
om:docs/docs-revise                 ok    ok    ok    ok    ok     3 @ 2026-08-17
om:experiments/exp-loop             ok    ok    ok    ok    ok     0 (none found)
om:project/omp-garden               ok    ok    ok    ok    ok     4 @ 2026-08-17
om:scholar/scholar-revise           ok    ok    ok    ok    ok     3 @ 2026-07-14
```
(원문 로그 전체, 근거 라인 포함 — `runtime/hooks/loop_lint.py`를 이 6개 루트에 대해 직접 실행한 결과)

### 이미 보유 (외부에서 새로 가져올 필요 없음)

| 외부 개념 | 사용자 보유 구현 | 근거 |
|:---|:---|:---|
| 결정론적 stop 조건 (loop-audit `verifier` 14점) | `deadline_passed()`, `loop_health()`의 `plateau_tripped`/`fault_tripped` | `/Users/kimseungmin/oh-my-experiments/omx-core/omx_core/loop.py:39-54`, `:248-282` — 순수함수, 시간 주입식, 별도 유닛테스트 존재(`tests/test_loop.py` 등, find로 확인) |
| 상태 파일 (loop-audit `stateFile` 18점) | `active_loop` state, `loop-status.json`, ledger | `loop.py:177-193`(arm_loop), `:196-212`(mark_loop_done) |
| 시도 상한 + 에스컬레이션 (2숫자) | `hard_cap=50`, `plateau_discards=5`, `fault_streak=3`, disarm 사유 8종 | `loop.py:137,244-245,200-201` |
| 독립 컨텍스트 검증자 (PARC 논문의 "self-assessment from independent context"와 동일 원칙) | `omx eval`이 별도 프로세스(evaluator.sh)로 채점 — 세션 컨텍스트가 스스로 판정 안 함 | `skills/exp-loop/SKILL.md:94-111`("이 JSON이 유일한 pass/score 근거") |
| 활동 증거(loop-audit v1.4 `loopActivity`) | ledger·loop-status.json이 디스크에 남고 린터가 glob으로 확인 | `loop_lint.py:237-267`(activity 함수) — 다만 exp-loop 자체는 이번 실측에서 0건(§3.1 하단 주의) |
| Ralph 원조 "boulder never stops" | `oh-my-claudecode/ralph` — progress.txt 기반 세션 영속, PRD 기반 | `loop_lint.py` 실측 evidence: `ralph: state L58 progress.txt`, `stop L33`, `cap L28 {{ITERATION}}/{{MAX}}` |
| 감사 CLI 자체(loop-audit 도구) | `runtime/hooks/loop_lint.py` — 5속성 대조 + 증거 라인 출력 + enforcement surface 표까지, cobusgreyling의 35지표보다 좁지만 "증거를 같이 찍는다"는 설계는 그쪽에 없는 강화 | `loop_lint.py:1-51`(모듈 docstring이 스스로 cobusgreyling 대비 차별점을 설명) |

### 진짜 없는 것 (외부에 있고 사용자에게 없는 것)

1. **표준화된 상태 파일 스키마가 루프마다 다르다.** loop-contract.md 자신이 이를 "격차"로
   명시: "no two share a state-file convention — `.omc/state/sessions/<id>/prd.json`,
   `pending-launch.json` + ledger, an artifact tree"(loop-contract.md L101). cobusgreyling의
   loop-init은 이 스캐폴드를 표준 템플릿으로 강제한다. **단, 이 갭을 메우는 게 이득인지는
   불확실** — loop-contract.md 자체가 "각 루프의 종료조건은 도메인 지식이라 공유 런타임으로
   재작성하지 않는다"(L6-10)는 원칙을 이미 명시적으로 채택했으므로, 상태 스키마 통일은
   저자 자신의 설계 결정에 반한다.

2. **`ultragoal`은 3/5 속성이 비어 있다.** stop·cap·verif 전부 `--`(§3 실측 표). 이것은
   "외부 기법 부재"가 아니라 "자기 계약 미준수"다 — 새 기법을 들여올 게 아니라 이미 있는
   계약을 적용해야 하는 케이스.

3. **B갈래(evaluator-optimizer)의 "난이도별 라운드 수 분기"가 없다.** MAgICoRe(2409.12147)
   처럼 "쉬운 문제는 1라운드, 어려운 문제는 다라운드"로 cap을 동적으로 정하는 루프는 사용자
   보유 루프 어디에도 없다 — `docs-revise`/`scholar-revise`/`exp-loop` 모두 고정 숫자
   cap(3회 등)이다. 다만 이것이 실제로 필요한지는 검증 안 됨(unverified) — 이 vault·워크스페이스
   작업 규모에서 난이도 분기가 이득이라는 근거는 없다.

4. **PARC류의 "장시간 병렬 오케스트레이션"** — 43시간짜리 다중 시뮬레이션을 하나의 루프가
   모니터링·에러정정까지 자동 수행하는 스케일. 사용자 루프는 전부 "1턴 iteration → 인간이
   다음 트리거"에 가까운 크기(omx의 loop-arm이 세션 영속을 흉내내지만 여전히 max-runtime
   초 단위 상한이 있고 학습(training) 자체는 절대 자동 실행 안 함 — B8 하드 제약,
   `skills/exp-loop/SKILL.md:250-253`). 이 갭이 "부재"가 아니라 "의도된 제약"이라는 점을
   명확히 해야 한다 — exp-loop은 훈련 자동 발사를 명시적으로 금지하고 있고(D4/B8), 이는
   PARC 스타일 완전 자율성과 정반대 설계 결정이다. 벤치마크상 우월성 근거 없이 이 제약을
   완화하자고 제안하지 않는다.

confidence: `--`/`ok` 표와 근거 라인 — verified(직접 명령 실행). "PARC 스케일 부재"·
"동적 cap 분기 부재" — likely(사용자 저장소 전체 grep이 아닌 4개 대표 루프 정독 기반).

---

## 4. 적용 제안

원칙: 실측 근거(코드 정확성 축 변별 0, 스킬 호출 0건, 규율 축 이득은 훅에서 발생 — 서두 지시문의
2026-08-22 A/B 결과)에 따라 **새 스킬·새 루프 신설은 입증 부담이 높다.** 아래는 지우기/통합/배선
우선.

1. **지우기/재작성 후보: `ultragoal`.** 린터 실측(§3)상 stop·cap·verif 3/5 부재. `autopilot`이
   이미 phase 3에서 "QA cycle 5회, 3회 반복 시 stop"(loop_lint.py evidence, autopilot L54)이라는
   결정론적 계약을 갖고 있어 기능이 겹친다. 제안: `ultragoal`을 (a) loop-contract 5속성 위에
   재작성하거나, (b) autopilot으로 흡수 통합하거나, (c) "다중 목표 워크플로"라는 좁은 용도가
   실사용에서 드물면 폐지. 결정은 사용자 몫 — 여기서는 "새 루프를 하나 더 만들기 전에 이미
   깨진 이것부터 손보거나 지우라"는 순서만 제안한다.

2. **`.code-review-graph`/`graphify`류 감사 CLI를 새로 만들지 마라.** `loop_lint.py`가 이미
   cobusgreyling의 loop-audit 아이디어(35지표→5핵심)를 이식했고, 증거 라인 출력이라는 설계
   개선까지 들어가 있다(loop_lint.py:1-51 docstring 자체가 이를 설명). 외부 도구를 새로 wiring할
   필요 없음 — **이 항목은 "이미 됐으니 손대지 마라"는 소거 제안**이다.

3. **상태 스키마 통일은 하지 마라.** §3.1에서 언급한 갭이지만, loop-contract.md 저자 자신이
   "런타임 통일 안 한다"를 이미 원칙으로 못박았다(L6-10: "This is a convention plus a checker,
   not a runtime"). 외부 loop-init 템플릿을 그대로 가져와 5개 루프의 상태 파일을 재작성하는
   작업은 이 원칙과 충돌하고, 실측 근거(스킬 신설 이득 0)에 비춰 볼 때 우선순위가 낮다.

4. **동적 cap 분기(MAgICoRe식)는 채택 보류.** 현재 고정 cap(3~5회)이 실패해서 늘려야 한다는
   증거가 없다(§3 표 어디에도 cap 초과로 인한 실패 사례가 없음, 확인 안 함). 도입하려면 먼저
   "고정 cap이 실제로 부족했던 사례"를 하나 이상 로그에서 찾은 뒤에 하라 — 지금은 unverified
   가설에 새 로직을 얹는 것.

confidence: 제안 1(ultragoal) — likely(린터 결과는 verified, "autopilot으로 흡수하라"는
설계 판단은 이 조사자의 추론). 제안 2·3 — verified(기존 원칙·코드 직접 대조). 제안 4 —
unverified로 명시(증거 없음이 곧 "보류"의 근거).

---

## 5. 확인하지 않은 것

- `ghuntley/how-to-ralph-wiggum` 저장소의 별 수·최근 커밋일 — WebSearch 요약만 봤고 `gh api`로
  직접 조회하지 않았다.
- Anthropic "Harness Design for Long-Running Application Development"(2026-03) 원문 전체 —
  제목·존재·대략적 날짜만 WebSearch로 확인했고, 원문을 열어 loop-contract.md L45의 "confidently
  praises it" 인용문이 문자 그대로 맞는지는 대조하지 않았다.
- `docs-revise`/`scholar-revise`/`omp-garden`의 activity 3~4건이 실제로 "이 루프가 돌았다"는
  뜻인지, 아니면 loop_lint.py 자신이 경고하는 과다계수(§ loop-contract.md L78-82, omp-garden의
  `.omp/STRUCTURE.md` 오탐 사례)인지는 각 예시 경로를 하나씩 열어보지 않아 개별 검증 안 함.
- `maxmilian/loop-engineering`의 "87%→100%" 벤치마크 주장 — 재현·검증 안 함, README 자체 주장
  그대로 인용.

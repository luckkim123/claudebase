# 하네스 고도화 — Phase 1 착수 (2026-08-22 작성)

> **진입점**: `0_Project/in_progress/harness/PLAN.md`의 **Phase 1 Task 1**부터. 선행 게이트
> 없음, 바로 시작된다. 설계·근거는 같은 폴더 `DESIGN.md`.
>
> **이 문서는 PLAN.md 의 내용을 복사하지 않는다.** 스텝·코드는 PLAN 에 있고, 여기에는
> PLAN 이 안 담은 것만 있다 — 함정, 금지된 방향, 사용자 결정 대기. 사본이 원본보다 먼저
> 낡기 때문이다.

이 문서 전체를 새 세션 첫 프롬프트로 붙여넣어라. **로봇도 GPU 도 다른 머신도 필요 없다.**

---

## 0. 이미 끝난 것 — 다시 하지 마라

2026-08-22 세션에서 조사·설계·계획이 전부 끝났다. 커밋은 vault `main`에 푸시됨.

| 무엇 | 어디에 | 커밋 |
|:---|:---|:---|
| 14에이전트 조사 원문 (2,654줄) | `harness/research/` 14개 | b827908c |
| 설계 (요구 원문·뒤집힌 전제 6건·확정 결정 7건·조사 답변 부록) | `harness/DESIGN.md` | 3fd1f6fa · 2c072b26 |
| 실행 계획 16 태스크 | `harness/PLAN.md` | 3fd1f6fa |
| 진입점 README + GCal 이벤트(2026-08-23) | `harness/README.md` | 3fd1f6fa |
| auto-memory 3건 (신규 2 + 낡은 포인터 정정 1) | `~/.claude/projects/.../memory/` | — |

**조사를 다시 돌리지 마라.** 요구 #1·#2a·#5의 답은 `DESIGN.md` 부록에 요약돼 있고 원문은
`research/`에 있다. 배경이 필요할 때만 해당 파일을 열어라.

**PLAN Task 6 Step 4(MEMORY.md 포인터 정정)는 이미 완료됐다** — 체크박스가 `[x]`다.
Task 6 에서 남은 것은 Step 1·2·3·5 다.

---

## 1. 이번 세션이 할 것

`PLAN.md` 순서대로. Phase 1 과 Phase 2 는 **병렬 가능**하다.

- **Phase 1 (계측)** — Task 1 헬퍼 → Task 2 파이썬 훅 6개 → Task 3 셸 훅 6개 →
  Task 4 리포트 → Task 5 A/B 실험 정의
- **Phase 2 (verified 제거)** — Task 6 하나. 부산물 3건 + likely 3건 확인

**Task 4 는 이 세션에서 못 끝난다.** 최소 3일·10세션의 로그가 쌓여야 판정할 수 있다.
Task 1~3 을 끝내고 Task 4 는 "기다림 시작"까지만 하면 된다.

Phase 3·4 는 **손대지 마라** — Task 4 데이터와 §3 의 사용자 결정이 선행이다.

---

## 2. 반드시 알고 시작할 것 — 이 세션이 밟아서 알아낸 함정

**(1) `harness_stats.py`의 탐지 방식이 Task 1 설계를 구속한다.** `logging_hooks()`는 각 훅
**소스를 grep 해 `<name>.jsonl` 리터럴**을 찾는다(`harness_stats.py:106,124`). 헬퍼가
확장자를 붙여주는 깔끔한 시그니처로 리팩터링하면 리터럴이 호출자 파일에서 사라져
**로깅을 붙이고도 계속 non-logging 으로 보고된다.** 그래서 `fire()`가 `"session_gate.jsonl"`
처럼 파일명 전체를 받는다. PLAN Task 2 의 테스트가 이걸 못박는다 — 지우지 마라.

**(2) 훅은 절대 세션을 막지 않는다.** 계측 훅이 예외를 던지면 사용자 턴이 죽는다. 모든
신규 경로는 `except Exception: pass` + exit 0. 측정 실패가 세션 정지보다 낫다.

**(3) `CLAUDE_PROJECT_DIR`은 훅에 export 되지 않는다** — `.claude/rules/code-review-graph.md`
의 `graph-refresh.sh` 항목에 기록된 실측이다. 셸 훅에 `${CLAUDE_PROJECT_DIR:-$PWD}` 폴백이
그래서 있고, **어느 쪽이 실제로 잡히는지는 Task 3 Step 5 에서 눈으로 확인**한다.

**(4) `unverified` 항목은 지우지 마라.** DESIGN §1 의 갈래 (B)계측 부재·(C)범위 협소는
삭제 근거가 못 된다. pilot 3벌·oms 8스킬·omx `tree-*`/`loop-*` verb 군이 여기 해당한다.
"이 머신 트랜스크립트에서 0건"은 다른 머신·marinelab 컨테이너를 안 본 결과다.

**(5) `ultragoal`은 우리 소유가 아니다.** loop-contract 5속성 중 3개 미준수인 최약체가
맞지만 omc(Yeachan-Heo) 플러그인이라 개조 대상이 아니다. 조작 지점은 사용자 소유인
omha `cards/omc.json`의 skills 배열이다(PLAN T14).

**(6) 시스템 `python3`는 Xcode 3.9.6 이다.** brew python3.12 와 다르고, `omx_core`는
brew 쪽에만 editable 설치돼 있어 시스템 python3 에서 `import omx_core`가 실패한다.
훅 테스트는 시스템 python3 로 돈다는 걸 전제하라.

**(7) Workflow 를 쓴다면 `agent()` 마다 `model` 을 명시하라.** 생략하면 세션 모델을
상속해 팬아웃 전체가 그 tier 로 돈다. 팬아웃 기본은 `sonnet`, 합성·적대적 검증만 `opus`.

**(8) GateGuard 가 첫 생성·첫 편집마다 사실 4가지를 요구한다** — 호출자, 동일 목적 파일
부재(실제 검색 실행), 데이터 스키마, 사용자 지시 원문. 넷을 그 메시지 안에 적고 재시도하면
통과한다. `find|xargs grep` 이 빈 결과를 낼 수 있으니 **`grep -rl` 로 재확인**하라
(이 세션에서 오탐 1건 발생).

**(9) 파괴적 조작은 `rmdir` 로 시도하라.** PLAN Task 6 Step 1 은 `rm -rf` 를 금지한다 —
`rmdir` 은 비어 있어야만 성공하므로 실패하면 그 자체가 "비어 있지 않다"는 신호다.
그때는 **멈추고 내용을 보고**하라.

**(10) eval 실행 시 `plugin_env.py` 는 선택이 아니다.** 빼면 처치군이 빈 채로 돌아가
"하네스는 아무것도 안 한다"로 읽힌다. 그리고 **n=1 은 답이 아니다** — 직전 사이클에서
n=1 의 +0.333 이 n=3 에서 +0.222 로 정정됐고 `scope_and_root_cause` 의 1.000 은 3회
반복에서 전부 0.667 로 무너졌다. 최소 n=3.

---

## 3. 사용자에게 물어야 하는 것 — 스스로 정하지 마라

`DESIGN.md` §7 에 5건이 있고 **그중 둘이 Phase 3 을 막는다.** Phase 3 에 진입하기 전에
물어라. 스스로 결정하면 안 된다.

| # | 결정 | 막는 것 |
|:--|:---|:---|
| **D2** | vault RAID/todo/BRIEF 를 재가동할 것인가 영구 종료할 것인가 | T11 |
| **D3** | omd `doc-builder.md:31`("다른 스킬을 감싸지 않는다")에 예외를 둘 것인가 | T7 |
| D4 | 다이어그램 문법을 다양화할 것인가 | — |
| D7 | wiki 5벌·learning-protocol 3벌·pilot 3벌 통합 | T14 이후 |
| D8 | `detect_malformed_toolcall.py` 90일 더 관찰 vs 지금 삭제 | — |

D2 의 판단 재료 한 줄: git 커밋·auto-memory·vault 노트가 todo 와 journal 은 대체하지만
**RAID(아직 안 닫힌 리스크)의 대체재는 셋 중 없다.**

---

## 4. 하지 마라 — 설계안이 나오면 그 자리에서 기각

`DESIGN.md` §5 의 기각 목록이다. 근거까지 거기 있다.

- **UserPromptSubmit 훅으로 프롬프트 재작성** — 플랫폼이 구조적으로 막는다.
  `additionalContext` 첨부와 차단만 가능하며 기능 요청 3건(anthropics/claude-code
  #53330·#34390·#46761)이 전부 open 이다. 우회 불가.
- **clarify MCP 서버 도입** — 발견된 5종 전부 네이티브 `AskUserQuestion` 재포장.
- **oms 에 "다음 실험 도출" 스킬** — omx `exp-design` 과 중복.
- **Graphiti/LangGraph 류 새 그래프 인프라** — 공백은 실재하나 관측된 실패모드는 그래프
  엔진 부재가 아니라 팬아웃 인자 검증 부재로 이미 기록됐다.
- **루프 상태파일 스키마 통일** — `loop-contract.md:6-10` 이 "convention plus a checker,
  not a runtime" 을 이미 원칙으로 못박았다.
- **동적 cap 분기** — 고정 cap 이 실패한 사례를 로그에서 하나도 못 찾았다.
- **새 스킬 추가 일반** — 실측상 스킬층은 코드 정확성 축 변별 0 이었고 그 런에서 Skill
  호출 자체가 0건이었다. 만들려면 "왜 배선으로는 안 되는가"를 먼저 통과해야 한다.

---

## 5. 미조사로 남긴 것 — "확인했다"고 말하지 마라

`DESIGN.md` §8 이 정본. 특히 **K15(autopilot/ralph 샌드박스)·K16(프로젝트 스코프 MCP
번들)은 전혀 조사되지 않았다.** 그 외: 46K 토큰 플로어의 항목별 분해, pilot·learn 계열의
다른 머신 사용량, omx `tree-*`/`loop-*` 의 marinelab·krit 실사용, graphify code-only ↔ CRG
산출물 중복도, OpenAI 공식 블로그 원문(WebFetch 403).

---

## 6. 이 사이클의 판정 원칙 — 한 줄

**"발화 데이터 없음"은 (A)계측기 있고 0건 / (B)계측기 자체가 없음 / (C)계측기가 좁음
셋으로 갈린다. 삭제 근거로 쓸 수 있는 건 (A)뿐이다.** Phase 1 의 전부가 (B)를 (A)로
바꾸는 작업이고, 그게 이 사이클의 산출물이다 — 삭제 목록이 아니라 계측 목록.

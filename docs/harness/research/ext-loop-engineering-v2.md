# 루프 엔지니어링 재조사 v2 — 자기모순 정정 + harness 축 문헌

재조사일: **2026-08-24**. 대상: `research/ext-loop-engineering.md`(2026-08-22).
근거: `research/AUDIT-2026-08-23.md` §B(자기모순)·§C(어휘 누락). 실행 단위: `PLAN.md` **T25**.

> **원본은 고치지 않았다.** 이 문서가 원본을 대체하는 것이 아니라 **원본의 어디가 왜 틀렸는지**를
> 기록한다. 원본을 덮어쓰면 "그때 무엇을 근거로 그렇게 판단했는가"가 사라진다 — 감사와 같은 규약.

---

## 0. 결론 먼저

**두 미흡 모두 실측으로 확인됐고, 하나는 원본 주장의 정확한 반대로 나왔다.**

1. **§B (자기모순)** — 원본 §0 L14는 `exp-loop`를 "5속성 전부 `ok`에 **실제 활동 증거까지 갖춘
   유일한 루프**"라 했다. 재실측 결과 `exp-loop`는 **5/5 루프 중 활동 증거가 0인 쪽**이다.
   원본 자신의 §3 표(L103)에도 `exp-loop … 0 (none found)`이라 적혀 있었다. 헤드라인이 자기 표를
   안 봤다.
2. **§C (어휘 누락)** — `harness` 축 논문 3편을 읽었다. 우리 `loop-contract.md` 5속성은
   StateM이 명시한 실패 모드 4개 중 **1.5개만 덮는다.** "외부에서 새로 가져올 기법은 거의 없다"는
   원본 결론은 **성립하지 않는다.**
3. **요구 #1의 "조사로 완결"은 완결이 아니다** (Step 3 판정). 공백 3개를 §3에 명명했다. 그것을
   실행 태스크로 올릴지는 **사용자 결정** — 0-C의 범위는 사용자가 감사 §5의 1~3번으로 고정했다.

`ultragoal` 3속성 부재는 **재현됐다** — 원본의 해당 판정은 그대로 유효하다.

---

## 1. §B 정정 — `exp-loop`는 활동 증거가 없다

### 1.1 재실측

```
python3 ~/claudebase/runtime/hooks/loop_lint.py \
  --root ~/ksm_Obsidian --root ~/claudebase --root ~/oh-my-experiments \
  --root ~/oh-my-scholar --root ~/oh-my-docs --root ~/Desktop/workspace
```

| plugin/skill | state | stop | cap | escal | verif | activity (2026-08-24) | 원본 (2026-08-22) |
|:---|:--|:--|:--|:--|:--|:---|:---|
| claudecode/autopilot | ok | ok | ok | ok | ok | **2 @ 2026-06-16 22:35** | 0 |
| claudecode/ralph | ok | ok | ok | ok | ok | 0 | 0 |
| claudecode/ultragoal | ok | -- | -- | ok | -- | 0 | 0 |
| claudecode/ultraqa | ok | ok | ok | -- | ok | 0 | 0 |
| claudecode/ultrawork | -- | ok | -- | ok | ok | 0 | 0 |
| docs/docs-revise | ok | ok | ok | ok | ok | 3 @ 2026-08-17 07:17 | 3 @ 2026-08-17 |
| **experiments/exp-loop** | ok | ok | ok | ok | ok | **0 (none found)** | **0 (none found)** |
| project/omp-garden | ok | ok | ok | ok | ok | **7 @ 2026-08-20 10:34** | 4 @ 2026-08-17 |
| scholar/scholar-revise | ok | ok | ok | ok | ok | **7 @ 2026-08-06 21:11** | 3 @ 2026-07-14 |

**읽는 법 — 계약과 활동은 다른 축이다.**

- **5속성 전부 `ok`인 루프는 여섯이다**: `autopilot`·`ralph`·`docs-revise`·`exp-loop`·
  `omp-garden`·`scholar-revise`. 원본이 `exp-loop`를 "유일"이라 부른 첫 번째 근거가 없다.
- **그 중 활동 증거까지 있는 루프는 넷이다**: `autopilot`(2)·`docs-revise`(3)·`omp-garden`(7)·
  `scholar-revise`(7). `ralph`와 `exp-loop`만 0이다.
- 따라서 `exp-loop`는 **"5/5인데 활동이 0인 두 루프 중 하나"**다. 원본 헤드라인의 정확한 반대다.

### 1.2 계획이 지목한 대체 후보 — 둘 다 자격은 있고, 성격이 갈린다

계획(T25 Step 1)은 `omp-garden`·`scholar-revise` 둘을 대체 후보로 지목하며 **"확인 전에 후보를
결론으로 쓰지 마라"**고 했다. 확인 결과 **둘 다 5/5 + 활동 있음**으로 자격을 갖췄다. 다만:

- `omp-garden` — 활동 7건, 최신 **2026-08-20**, 증거 파일
  `/Users/kimseungmin/ksm_Obsidian/.omp/garden-state.json`(156 B, `version`·`sweeps`·`findings` 키).
  **이 vault에서 실제로 도는 루프다.**
- `scholar-revise` — 활동 7건이지만 최신이 **2026-08-06**. 2주 이상 정지 상태다.

**그러니 "지금 도는 루프"라는 문장을 쓸 수 있는 것은 `omp-garden` 하나뿐이다.**

### 1.3 원본과 숫자가 다른 칸이 셋 있다 — 귀속 불가

`autopilot` 0→2, `omp-garden` 4→7, `scholar-revise` 3→7. 두 원인이 섞여 있고 **가를 수 없다**:

- 원본은 "이 **6개 루트**에 대해 직접 실행한 결과"라고만 적고 **어느 6개인지 안 적었다.** 나는
  om* 상태 디렉터리(`.omc`/`.omp`/`.oms`/`.omd`/`.omx`)가 실제로 존재하는 곳을 찾아 6개를 골랐고,
  그것이 원본과 같다는 보장이 없다.
- 그 사이 이틀 동안 실제 활동이 생겼을 수 있다(`omp-garden`은 타임스탬프가 08-17→08-20으로
  전진했으니 이쪽이 유력하다).

**그러나 판정이 걸린 칸은 두 실행에서 불변이다** — `exp-loop`는 양쪽 다 `0 (none found)`.
§B의 정정은 루트 집합과 무관하게 선다.

> **교훈으로 남길 것**: 측정 명령을 적을 때 **루트 목록을 문서에 그대로 적어라.** "6개 루트"는
> 재현 지시가 아니다. 이 문서는 위 §1.1에 명령 전문을 붙였다.

---

## 2. §C 정정 — harness 축 문헌 3편

원본은 "루프 엔지니어링"이라는 **2026년 브랜드 어휘**로만 검색해 reflection/self-correction 계열만
잡았다. 학계가 같은 문제를 부르는 이름은 **harness**다. 셋 다 조사일(2026-08-22) 이전 공개인데
원본에 인용이 없다.

| ID | 제목 | 공개일 | 축 |
|:---|:---|:---|:---|
| 2608.15089 | StateM: Reaching 95.3% Raw Accuracy … via **Harness Scaling** | 2026-08-15 | 하네스로 성능을 올린다(모델 가중치 불변) |
| 2608.13560 | AutoDesign: **Meta-Harness Optimization** for Long-Horizon Agentic Design | 2026-08-13 | 하네스를 rollout 피드백으로 재귀 개선 |
| 2608.16798 | ClawGym II: Exploring **Black-Box RL on Agent Harness** | 2026-08-17 | 하네스를 블랙박스로 두고 모델을 RL 최적화 |

### 2.1 StateM — 우리 5속성이 덮는 실패 모드는 1.5개다

StateM은 장기 과제 에이전트의 실패를 **네 가지로 명명**한다(초록 원문): *"lose track of mutable
state, fail to reactivate lessons from earlier executions, skip known procedures, or **stop
prematurely**."* 우리 `loop-contract.md` 5속성과 대조하면:

| StateM 실패 모드 | 우리 5속성 중 대응 | 판정 |
|:---|:---|:---|
| mutable state를 놓친다 | **상태파일** | 덮는다 |
| 이전 실행의 교훈을 재활성화 못 한다 | — | **없다** |
| 알려진 절차를 건너뛴다 | — | **없다** (독립 검증자는 *결과*를 보지 *절차*를 안 본다) |
| **너무 일찍 멈춘다** | 결정론적 종료 / 시도상한+에스컬레이션 | **반쪽** — 아래 |

**"조기 종료"는 우리 계약이 못 잡는다. 방향이 반대다.** 우리의 `cap`+`escalation`은 *과잉 반복*을
끊는 장치다(`autopilot` 근거 라인: "QA cycles repeat up to 5 times; if the same error persists
3 times, stop"). StateM이 지목한 것은 그 반대편 — **끝나지 않았는데 스스로 끝났다고 선언하는
것**이다. 5속성에 그것을 막는 항목이 없다.

**StateM이 쓰는 장치 중 우리에게 없는 것**: phase-local context(단계별 컨텍스트 분할),
checked transitions(전이 검사), recoverable runbooks(복구 가능한 절차서), versioned procedural
practices(버전 관리되는 절차 관행).

**그 중 `checked transitions`는 우리 린터가 이미 묻고 있고, 답이 나빴다.** `loop_lint.py`의 [B]
표는 "전이는 훅이 있는 곳에서만 강제 가능하다"를 전제로 차단 가능 훅을 센다. 2026-08-24 실측:

```
loop-carrying plugins with no blocking Stop hook visible —
their loop's stop transition is prose only:
  oh-my-docs, oh-my-project
```

**활동 증거를 가진 살아 있는 루프(`omp-garden`, oh-my-project)의 정지 전이가 산문뿐이다.**
(`omp-garden`은 스스로 "Report-only"라 선언하므로 이것이 곧 결함이라 단정하진 않는다 — 다만
StateM이 런타임으로 강제하는 자리를 우리는 문장으로 두고 있다는 사실은 그대로다.)

### 2.2 AutoDesign — 우리에게 없는 것은 "측정 → 하네스 개선" 되먹임이다

메타 하네스 최적화기가 코드 에이전트를 이끌어 **하네스 자체를 rollout 피드백으로 재귀 개선**한다.
학습한 `DesignHarness`를 끼우면 7개 구성 평균 PosterBench 점수가 54.99 → 67.39 (+12.4%).

**우리 계획과의 관계**: `DEC-1`(측정 먼저)과 Task 4(기준선 리포트)는 *측정*까지다. 그 측정 결과로
하네스를 고치는 고리는 사람이 손으로 돌린다. AutoDesign은 그 고리를 자동화한 사례다 —
**정합하되 우리보다 한 단계 앞이다.**

**부수 발견 — T26과 겹친다.** AutoDesign의 과제 도메인이 **paper-to-poster generation**이고
`PosterBench`(100편 5개 분야)를 도입했다. `T26 Step 2`가 찾는 "슬라이드 생성·미학 레이아웃을
측정 가능한 보상으로 다루는 문헌"이 바로 이 계열이다. **T26은 이 논문부터 읽으면 된다.**

### 2.3 ClawGym II — 직접 이식 대상은 아니다. 효과 크기의 참고점이다

하네스를 **블랙박스로 고정**하고 모델을 RL로 최적화한다 — 우리와 방향이 반대다(우리는 모델 고정,
하네스 변경). 이식할 기법은 없다.

쓸모는 다른 데 있다: Qwen3-30A3B에서 **OpenClaw 경유 +9.98점, Claude Code 경유 +14.81점**.
즉 **어느 하네스를 쓰느냐가 두 자리 점수 차를 만든다**는 외부 수치다. 우리 훅 A/B가 null(양팔
0.333)이었던 것을 "하네스는 원래 효과가 없다"로 읽으면 안 된다는 반례로 쓸 수 있다 — 단
**벤치마크·모델·처치가 전부 달라 직접 비교는 불가**하고, 우리 A/B의 처치 크기가 작았을 가능성을
시사할 뿐이다.

---

## 3. Step 3 판정 — 요구 #1의 "조사로 완결"은 성립하지 않는다

`README.md` "요구 5건의 처리" 표는 요구 #1(루프·그래프 엔지니어링 조사)을 **"조사로 완결"**이라
적었다가 감사 §C 이후 "완결 아님"으로 고쳐 두고, 그 최종 판정을 이 스텝에 넘겼다.

**판정: 세 선택지 중 (b) — 완결 아님이고, 공백이 실행 항목이 될 만큼 구체적이다.**

(a) 완결 유지는 §2.1이 막는다. (c) "완결 아님으로 명시하고 닫기"는 공백이 *무엇인지* 이미 이름을
얻은 지금 근거가 약하다. 공백 셋:

| # | 공백 | 근거 | 크기 |
|:---|:---|:---|:---|
| G1 | **조기 종료 방지 장치가 없다** — 계약의 cap·escalation은 과잉 반복만 끊는다 | §2.1 | 계약 문서 1항 추가 + 린터 열 1개 |
| G2 | **이전 실행의 교훈을 재활성화하는 경로가 계약에 없다** — `.omp/learned.md`·wiki가 근접하나 계약 항목이 아니다 | §2.1 | 기존 자산의 계약 편입 여부 판단 |
| G3 | **정지 전이가 산문뿐인 플러그인이 둘 있다** (`oh-my-docs`·`oh-my-project`) | §2.1 린터 [B] | 훅 신설 여부 판단 — omp-garden은 report-only 선언이라 결함 아닐 수 있다 |

**이 셋을 태스크로 올릴지는 사용자 결정이다.** 0-C의 범위는 사용자가 2026-08-23에 감사 §5의
**1~3번만**으로 고정했고, 새 실행 항목 신설은 그 범위를 넓히는 일이다. 계획서가 "결정 필요"라 한
것을 실행자가 스스로 정하지 않는다(`feedback_plan_decision_escalation`).

---

## 4. 원본에서 그대로 유효한 것

정정은 위 둘뿐이다. 아래는 재실측에서 **재현됐고 건드리지 않는다**:

- `ultragoal`이 **결정론적 종료·시도상한·검증자 3개 전부 `--`**로 로컬 계약 최약체라는 판정.
  2026-08-24 재실행에서도 동일(`state ok / stop -- / cap -- / escal ok / verif --`).
- `loop_lint.py` 자체가 cobusgreyling `loop-audit`보다 좁지만 "증거 라인을 같이 찍는다"는 점에서
  강화라는 평가.
- 감사 CLI를 새로 만들지 말라는 권고.

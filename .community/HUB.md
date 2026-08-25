# HUB — 근거 없는 확언 (grounding & overclaiming) 캠페인

- **owning session**: `validate-deploy-constants-layer` (claudebase repo, branch `main`) — 다른 조정자는 이 이름으로 SendMessage 하라, 사용자를 경유하지 말 것
- **발진**: 2026-08-25 23:30 KST · **종점**: 측정 + 결정 (하네스 규칙 변경은 별도 승인)
- **보드 규약**: `~/.claude/skills/team-project/SKILL.md` — 평탄 구조, 게시글 번호는 `posts/` 트리 전역 단조

---

## 1. 목표

Claude 가 **근거 없이 분석하고, 근거 없이 결론 내고, 그걸 사용자에게 확답처럼 말하는** 실패를
측정 가능한 것으로 만들고, 그 실패를 실제로 줄이는 기제를 **재본 뒤** 고른다.

이 캠페인 자체가 그 규율의 시연이다 — 재지 않고 규칙만 추가하면 그게 진단하려는 그 병이다.

## 2. 사용자 원문 (verbatim)

> harness 프로젝트에서 팀 프로젝트로 진행해라. 지금 문제인건 비단 "로봇"에 국한된 것이
> 아니라 claude가 아무런 근거 없이, 결과 분석도 의미 없는 분석을 하고, 실험 계획도 의미 없게
> 하고, 결론을 내는것도 근거가 없으며, 이걸 사용자에게 확답처럼 말한다는 것임. 차라리 omc의
> deep interview에서 어떤 점수를 메기는 체계처럼 신뢰도같은 걸 매기던지.

> 물론 꼭 이런 방법으로 하란건 아니다.

> 필요하면 인터넷 조사도 해보고.

## 3. 사용자 결정 (append-only — 결정은 파생 사실을 닫는다)

| # | 날짜 | 결정 | 근거 |
|:--|:---|:---|:---|
| D1 | 2026-08-25 | **5축 그대로 발진** (W1~W5) | 승인 게이트 |
| D2 | 2026-08-25 | **종점 = 측정 + 결정.** 실제 하네스 규칙 변경은 별도 승인 | 승인 게이트. "안 재보고 규칙을 켠 것"이 오늘 사고라 순서를 뒤집지 않는다 |
| D3 | 2026-08-25 | **신뢰도 점수제는 후보 하나일 뿐** — 기제 선택 자체가 열린 축 | 사용자: "꼭 이런 방법으로 하란건 아니다" |
| D4 | 2026-08-25 | **인터넷 조사 허용** | 사용자: "필요하면 인터넷 조사도 해보고" |

## 4. 착수 시점의 실측 사실 (전부 2026-08-25 측정, 출처 포함)

| 사실 | 값 | 출처 |
|:---|:---|:---|
| harness 프로젝트 | `docs/harness/` — protocol 3파일 + measurements 3파일 | `find docs/harness -type f` |
| eval 계측기 존재 | `eval/` — coder_eval 기반, task 10 · experiment 6, H_0/H_T 2팔 | `eval/README.md` |
| **eval task 중 근거·확언을 재는 것** | **0개** — 전부 코드 규율(자제·근본원인·재사용) | `ls eval/tasks/` 전수 제목 확인 |
| 활성 훅 | ~~54+~~ → **94** (W2 실측 정정, 아래 §7-quater) | 각 `settings.json` / `hooks.json` / **`plugin.json` 인라인** 파싱 |
| **훅 94개 중 "내용"을 판정하는 것** | **1개** (`oms` `scholar_cite_guard.py`, 그마저 인용키 화이트리스트 대조) — 소스를 직접 읽은 ~30개 기준 | `posts/finding/002-*` §2 |
| DELIVERY_GATE 차단 조건 | `memory/` 디렉터리의 **파일 mtime** — 내용을 볼 수 없다 | `runtime/skills/delivery-gate/hooks/quality-gate.py` — `check_stale_libs`, `main` 5번 분기 |
| GATEGUARD | 59줄 순수 러너, 판정 로직 없음, 실패 시 fail-open | `runtime/skills/gateguard/hooks/run.js` — catch 블록 |
| deep-interview 점수제 실체 | 3~4 차원(Goal/Constraint/Success/Context) 각 0.0–1.0 → 가중 ambiguity → **임계 0.2 하드 게이트**, 매 라운드 숫자 노출 | `oh-my-claudecode/5.0.0/skill-bodies/deep-interview/SKILL.md` — Phase 0, "Score each dimension" |

### 4-bis. 이 캠페인을 촉발한 사고 (2026-08-25 밤, albc)

`rl_inference_node.py` 에 θ2 하드 창을 넣고 launch 기본값으로 켜서 constrained RL 방법론을
무효화, 수조 런 1건 오염(정책 수명 0.255 s). 자기철회 정본:
`~/ksm_Obsidian/0_Project/in_progress/albc/notes/2026-08-25-guard-session-retraction-handoff.md`

**독립 검증(같은 밤)에서 나온 결정적 사실** — 이 사고를 잡을 수 있었던 집행점은 훅이 아니라
저장소 안의 테스트였고, **한 함수 위에서 같은 원칙을 산문으로 적고 있었다**:

```
# agent-jetson/robot/albc_rl/scripts/test_deploy_constants.py — test_joint1_start_gate_default_is_pi
"""Widening this is a deliberate experiment, so it must be a per-run override,
   never a committed default."""
```

`e68b629` 는 정확히 그 금지를 joint2 로 반복했고 **16개 테스트가 전부 통과했다**
(2026-08-25 재실행: `16 passed in 0.02s`). 테스트가 원칙이 아니라 **이름**에 걸려 있었다.

## 5. 규칙 (워커 전원 구속)

1. **출처 없는 숫자 금지.** 복사한 사실은 전부 출처(file:symbol 또는 commit sha)와 측정일을 단다. 줄번호 말고 심볼 — 줄번호는 조용히 밀린다.
2. **확인 안 한 것 단정 금지.** "없다/0건이다"는 실행한 명령을 대라. 못 확인했으면 "확인 안 함"으로 남긴다.
3. **작업량은 커버리지 증명이 아니다.** "N개를 봤다"가 아니라 "무엇을 덮었고 무엇이 밖에 있나"를 쓴다.
4. **조정자는 틀린다.** 브리프의 숫자·경로는 원본에 대조한 뒤 적용하고, 어긋나면 적용하지 말고 되쳐라.
5. **git 은 조정자만.** 워커는 이 repo 에 commit·push 하지 않는다.
6. **보고가 곧 종료.** `agents/<role>.md` 에 교훈 append → SendMessage(결론 + 산출물 경로 + 검증 안 한 것) → 정지. 조용해지는 것은 완료가 아니다.

## 6. 제약

- 편집면은 **추가만** — 새 `eval/tasks/*.yaml` + `.community/` 게시글. `settings.json`·`CLAUDE.md`·기존 훅은 **건드리지 않는다** (사용자 CLAUDE.md: claudebase 안의 meta-change 는 라인 단위 리뷰).
- `coder-eval run` 은 과금 — **`plan` 까지만** 워커 권한. `run` 은 사용자 승인.
- 병렬 세션이 같은 repo 에 있다 — 워커는 파일 소유가 겹치지 않게 배정됐다(§7).

## 7. 작업 보드

| 워커 | 모델 | 범위 | 파일 소유 | 상태 |
|:---|:---|:---|:---|:---|
| `corpus` (W1) | sonnet | 실패 표본 라벨링 — 이틀 철회 16건 + 가드 사고 | `posts/finding/001-*` | **done 23:52** |
| `enforce-map` (W2) | sonnet | 집행층 실측 — 훅이 각각 무엇을 볼 수 있나, eval 이 무엇을 덮나 | `posts/finding/002-*` | **done** — 훅 94개, content 판정 1개 |
| `mechanism` (W3) | opus | 기제 후보 설계 + 문헌 | `posts/finding/003-*` (**조정자가 대필**) | **done** — 후보 6종, 커버리지 행렬, 추천 B'+D+C' |
| `lit-calibration` (W3-lit) | sonnet | W3 문헌 반쪽 대체 + 인용 독립 검증 | `posts/finding/005-*`, `posts/finding/007-*` | **done** — 독립 조사 12건 + 인용 14/14 실재 |
| `instrument` (W4) | sonnet | `eval/tasks/` 신설 2~3건, `coder-eval plan` 통과 | `eval/tasks/grounding_*.yaml`, `posts/handoff/004-*` | **done 23:5x** — task 3개, `plan` 통과(조정자 실행) |
| `refuter` (W5) | opus | 전원 산출물 적대 반증 (표적 **7**종) | `posts/review/006-*` | **done 2026-08-26** — 표적 7 로 G 계열 무너뜨림 |
| `instrument-2` (W6) | sonnet | D-3 계측기 — 적용 실패율 matched pair | `eval/tasks/readfail_*.yaml`, `posts/handoff/009-*` | **doing** — 쌍 완성·`plan` 통과, 3번째 팔 판단 중 |
| 조정자 | — | 종합 → `posts/decision/006-*` + 4줄 구현 제안 | `HUB.md`, `posts/decision/` | doing |

### 7-bis. 발진 중 라우팅 정정 (2026-08-25 23:35)

`agent-routing-guard` 훅이 W2·W3·W4 를 "research-shaped 인데 general-purpose 로 갔다"며 차단했다. 조치:

- **W2·W4** — 진짜로 outbound 조사가 아니다(로컬 훅 소스 감사 / 로컬 yaml 작성). `ROUTING_OK` 선언으로 재발진. 게이트를 속인 게 아니라 오탐을 선언한 것이다.
- **W3** — **진짜 문헌 조사가 맞다.** `oh-my-claudecode:scientist`(opus)로 교체. 다만 그 에이전트는 read-only 라 게시글을 못 쓴다 → **최종 텍스트로 본문 전체를 받아 조정자가 `posts/finding/003-*.md` 로 그대로 저장**한다. 축은 그대로이고 워커 수도 늘지 않았다.

⚠️ 이 대필 경로는 **왜곡 위험이 있다** — W5(refuter)는 003 을 검증할 때 조정자 대필이라는 사실을 알고 봐야 한다.

### 7-ter. W1 보고 반영 (2026-08-25 23:52)

`corpus` 완료. **조정자 가설 2건이 반증됐다** — 기록해둔다(W5 는 이 반증들도 검증 대상):

1. **계열은 4개가 아니라 최소 6개.** 신규 (E) 포인터·요약층 **미전파**(`18baba28`·`e26a49f9` — 본문은 이미 옳았다), (F) **오조준형**(`cddc405f`).
2. 🔴 **후보 A(신뢰도 점수)가 못 잡는 실패가 확증됐다.** θ2 창 사고는 근거가 없어서 난 게 아니다 — 테스트 7단계·변이 3회·적대 리뷰 3회 통과였고 인용 숫자도 진짜였다. 틀린 것은 **검증할 질문의 선택**이다. 점수제였다면 **고점을 받았을 사고**다.
3. `366ea244`(D2 번복)는 분모 밖 — 조정자 판정과 일치.
4. 분모 재측정: albc 커밋 **60건**(브리프 58~59는 시점차, 되침 아님).
5. 넓힌 grep 으로도 3건 미검출(`e26a49f9`·`bc28ffcc`·`e0479db2`) — 키워드 검색이 이 실패 유형에 부적합함이 재확인.

**W1 이 남긴 열린 구멍** (다음 세션 또는 W5 판단):
- `efbb325b`·`7b2d170b` 하위주장·`bad566cb` 가 가리키는 08-12 판정의 도입 sha — diff 미열람
- θ2 창 도입 커밋은 `agent-jetson` repo 라 session-gate 에 막혀 미확인 → **조정자가 보충: `e68b629`(2026-08-25 18:05)**, HUB §4-bis 참조
- 60건 전수 독립 스캔 미실행 — 이 코퍼스는 **주어진 16건만** 검증했다
- E계열이 albc 밖에서도 같은 빈도인지 미확인

### 7-quater. W2 보고 반영 (2026-08-25 23:5x) — 조정자 숫자가 두 겹으로 틀렸다

`enforce-map` 이 `posts/finding/002-*` 게시. **조정자의 "54+"가 반증됐다 — 실측 94개.**

| 놓친 층 | 개수 | 왜 놓쳤나 |
|:---|--:|:---|
| omha 계열 5개 | 5 | `hooks.json` 파일이 아니라 `.claude-plugin/plugin.json` 의 **인라인 `hooks` 키**로 등록 → `find -iname hooks.json` 에 안 잡힘 |
| omx·omd·oms·omp | 21 | 같은 인라인 방식. 브리프가 언급조차 안 했다 |
| claude-mem·remember·superpowers·ponytail | 14 | `enabledPlugins` 에 15개가 켜져 있는데 브리프는 2개만 다뤘다 |

**핵심 판정: 94개 중 "주장의 내용이 참인가"를 보는 훅은 1개뿐이다** — `oms` 의 `scholar_cite_guard.py`, 그마저 인용키 화이트리스트 대조다(화이트리스트는 별도 스크립트의 외부 조회로 채워짐).

🔴 **GATEGUARD 의 실제 동작이 브리프 서술보다 나쁘다.** 세션 상태 파일의 "이 파일/명령을 이미 한 번 봤는가" **불리언 플래그**만 읽고, **사용자가 실제로 뭐라고 답했는지는 절대 안 읽는다.** 첫 호출 1회 거부 → 이후 영구 통과. 즉 "사실을 제시하라"는 요구에 **무엇을 써넣든 통과한다** — 이 캠페인 조정자 본인이 2026-08-25 23:30 에 그 게이트에 4항목 응답을 작성했고, 그 응답은 읽히지 않았다. 마찰은 진짜지만 검증은 0이다.

eval 4축 0개 판정은 **유지**(W4 의 신설 task 가 축1·2를 부분적으로 건드리기 시작한 것은 캠페인 도중 변화).

부수: `coder-eval` 을 이 머신에 설치한 것은 W2 다(`uv tool install coder-eval`) — `handoff/004` 코멘트의 추정이 확증됐다.

### 7-quinquies. 실패 계열 최종 분류 (W1 완료, 2026-08-25 23:5x) — 이게 하류의 기준선이다

조정자의 4계열 가설은 **세 번 틀렸다**(계열 수·E 재분류·B 오분류). 실측 최종:

| 계열 | 정의 | 대표 사례 | 신뢰도 점수(후보 A)가 잡나 |
|:---|:---|:---|:---|
| A 층 교차 | 도는 것 ≠ 소스 | `ce9e3bec`, `efbb325b`, raw IMU 프레임 | 부분 |
| B 표본 부족 | 표본은 **있으나** 작다 | m4 4회 관측, TDC 9초 창 | 부분 |
| C 자기 기록 미검색 | 이미 닫힌 것을 다시 염 | 팔 평면(08-12 기록 존재) | 못 잡음 |
| D 숫자 출처·역할 혼동 | 값은 진짜, 역할이 틀림 | `cddc405f` θ2 창 | 못 잡음 |
| **E 미전파** | 본문은 이미 옳고 포인터만 낡음 | `18baba28`, `e26a49f9` (R 아니라 P 로 재분류) | 못 잡음 |
| **F 무측정 추정** | 표본이 **0** — 측정 시도 자체가 없는 값을 확언 | 🔴 **417초 사례** (아래) | **잡을 수 있음** |
| **G 고아 확언** | 전제가 무너졌는데 아무도 철회 안 함 | `ac9a2277` (전제가 36분 뒤 `bc28ffcc` 로 붕괴) | 못 잡음 |

전수 스캔 판정: R14 · P5 · N40 · `?`1 (60건). 신규 2건은 subject 가 아니라 **본문**에 있었다.

#### 🔴 등급 1 사례 — 코퍼스에서 유일하게 물리 파손으로 이어졌다

`~/ksm_Obsidian/0_Project/in_progress/albc/.community/posts/finding/047-e2-run1-arm2-fracture.md` §2-1 (조정자가 원문 대조):

> 세션은 이 구간을 **"몇 초간 팔 토크가 빠집니다"** 라고 안내했다.

실측 **417.4 초**(약 100배). 그동안 J2 가 −160.14°, body pitch 가 −48.97° 이동 → 학습 분포 밖 초기조건 → arm2 파단. **아무도 이 안내를 철회한 적이 없다** — 사고 기록이 사후 실측을 적었을 뿐이다.

#### 중대도 축 (W1 신설) — 후보 A 에 대한 결정적 반례

3등급(1=물리손상 / 2=실험오염·재작업 / 3=문서정정만). 등급 1 은 417초 1건뿐이고, `cddc405f`(θ2 가드)조차 등급 2 다.

🔴 **등급 1 과 등급 3 이 둘 다 무헤지였다.** 즉 **어투 강도가 사고 비용을 예측하지 못한다.** 신뢰도만 재는 게이트는 값싼 실패와 하드웨어를 부수는 실패를 같은 무게로 다룬다 — 게이트가 키로 삼아야 할 축은 확신도가 아니라 **되돌릴 수 있는가(reversibility)** 일 수 있다.

#### 긍정 대조 표본 2건 (후보 설계에 쓸 것)

- `b3778f5c` — 가설 수립 → Hankel-DMD 7/7 창 검증 → **스스로 반증**, 헤지 정확
- `19a22185` — 사고 기록에서 "하면 안 되는 주장" 5건을 **미리 자진 명시**

### 7-sexies. 현재 상태 스냅샷 (2026-08-26 00:1x, compact 대비)

**게시글 6건 완료, W5 반증만 남았다.**

| id | 저자 | 한 줄 |
|:---|:---|:---|
| `finding/001` (+부록 A·B) | corpus | 실패 계열 **7종**, 전수 60건 R14·P5·N40·`?`1, 중대도 3등급, **417초 사례**(유일한 등급 1) |
| `finding/002` | enforce-map | 활성 훅 **94개**, 내용 판정 **1개**, GATEGUARD 는 답변을 안 읽는다 |
| `finding/003` | mechanism (조정자 대필) | 후보 6종 × 계열 7종 행렬. **A 는 완전히 덮는 칸 0.** 추천 = B'+D(+C') 3층 조합 |
| `handoff/004` | instrument | `eval/tasks/grounding_*.yaml` 3건, `coder-eval plan` 통과(조정자 실행) |
| `finding/005` | lit-calibration | 독립 문헌 12건 — **003 과 2건만 겹치는데 같은 결론** |
| `finding/007` | lit-calibration | 003 의 인용 14건 검증 — **14/14 실재, 날조 0**. L3 는 본문 §2 까지 대조 |

**핵심 결론(반증 전 잠정)**: 사용자 제안 후보 A(신뢰도 점수 하드 게이트)는 **채택 안 함**. 근거 3계보 — (i) 코퍼스: 7계열 중 완전 커버 0, F 오조준에는 고점 (ii) 문헌 A: arXiv:2601.07767 본문 검증 — 페널티 [0.1,100] 전역에서 자기평가·기권 무반응 (iii) 문헌 B: 거의 겹치지 않는 12건이 같은 결론. **A 는 스칼라가 아니라 의무 트리거(범주형 선언)로 C' 안에 흡수.**

**아직 안 한 것**: W5 반증 · 결정 게시글 · 4줄 구현 제안 · `coder-eval run`(과금, 사용자 승인 + `ANTHROPIC_API_KEY` 필요) · agents/ 스윕 · git commit(조정자만).

**진행 중 관측(캠페인 주제의 1인칭 표본)**: Fact-Forcing Gate 가 이 세션에서 스스로 **"denial #4"** 를 찍었다. 매번 4항목을 채웠고 `finding/002` 가 소스에서 확인한 대로 **그 답변은 한 번도 읽히지 않았다.**

### 7-septies. 표적 7 종결 + D-3 개정 (2026-08-26)

`refuter` 가 마지막 구멍(G 계열 반증)을 닫았고, 조정자가 그것이 남긴 미판정 축에 탐침을 돌렸다. **세 겹으로 정리된다.**

1. **G(고아 확언)는 존재하지 않는다.** `finding/003` §2-3 의 사실 주장 셋이 전부 반증 — 철회 커밋 있음(`bc28ffcc`), 본문 무효 표시 있음(2곳), grep 으로 잡힘. 사례 수 1 → **0**. 해당 절에 stale 배너 부착(원문 보존, 규약).
2. **그 사례는 E 였고, E 는 Q1 의 한 사례다.** 조정자 탐침(`finding/010`): 저자 세션이 배너 문장을 **직접 썼고**(`15305c56...jsonl:2917`) 커밋(`:3984`)까지 **compact 0건**. 도달 실패가 아니라 적용 실패. Q1 세 표본 중 **도피로가 없는 유일한 것**.
3. **D-3 은 지위 유지, 이름 정정.** "읽기 실패율" → **"적용 실패율"**. 이 사례에서 읽기 실패는 0 이다. `decision/008` §5-bis 로 반영.

🔴 **부수 발견이 방법론에 걸린다 — `.jsonl` 트랜스크립트는 CLAUDE.md 를 기록하지 않는다.** 세션 6개 · 문자열 8종 전부 0, 반면 auto-memory 는 기록된다(56·38·1). 따라서 **"규칙이 컨텍스트에 있었나"는 CLAUDE.md 계열에 대해 사후 확인도 반증도 불가**하다. 이 캠페인의 사후 포렌식 전반에 걸리는 한계이고, 동시에 **계측기가 우회로가 아니라 유일한 길이라는 직접 근거**다(`handoff/009` 는 `pre_run` 으로 규칙 존재를 설계로 보장한다).

**남은 것은 `instrument-2` 하나.** 그 보고가 오면 캠페인 종료 조건(§9)에 걸린다.


## 8. 산출물 지도 (SSOT)

보드 밖 산출물은 여기에만 적는다. 워커는 재조사 전에 이 표를 먼저 읽는다.

| 산출물 | 경로 |
|:---|:---|
| 촉발 사고 정본 | `~/ksm_Obsidian/0_Project/in_progress/albc/notes/2026-08-25-guard-session-retraction-handoff.md` |
| 이틀 커밋 이력 | vault repo `git log --since="2026-08-24 00:00"` |
| eval 계측기 | `~/claudebase/eval/` (README 에 실행법·함정) |
| 훅 정의 | `~/.claude/settings.json`, `~/ksm_Obsidian/.claude/settings.json`, `~/.claude/plugins/marketplaces/omc/hooks/hooks.json` |
| deep-interview 원본 | `~/.claude/plugins/cache/omc/oh-my-claudecode/5.0.0/skill-bodies/deep-interview/SKILL.md` |
| E 사례 정본 (요약층 미동기) | `~/ksm_Obsidian/0_Project/in_progress/albc/notes/2026-08-24-classic-teleop-resume-prompt.md` — 배너 `:13`·제목 `:265` stale, 본문 `:484`·`:516` 무효 표시 |
| 그 사례의 저자 세션 트랜스크립트 | `~/.claude/projects/-Users-kimseungmin-ksm-Obsidian/15305c56-1ca5-445f-8cfe-f41b5443594b.jsonl` — 배너 `:2917`, 커밋 `:3984` |
| ⚠️ 트랜스크립트 채널 한계 | `.jsonl` 은 **CLAUDE.md 를 기록하지 않는다**(auto-memory 는 기록). "규칙이 컨텍스트에 있었나"를 사후에 묻지 말 것 — `finding/010` §채널 한계 |

## 9. 종료 조건

W1~W4 각 1회 보고 → W5 반증 1라운드 → 조정자가 `decision/` 게시글 + 4줄 구현 제안 → 사용자 승인.
교차검토 **1라운드 상한**. `[FINAL]` 제목 메시지는 답하지 않는다.

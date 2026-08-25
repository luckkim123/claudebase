# 하네스 생태계 고도화 — 실행 계획

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development` (권장) 또는 `superpowers:executing-plans`로 태스크 단위 실행. 스텝은 체크박스(`- [ ]`) 문법이다.

**Goal:** 지울 것을 근거 있게 고르기 위해 먼저 계측을 배선하고, 그 위에서 이미 있는 역량을 닿게 만든다.

**Architecture:** 4단계. (1) 로그 없는 훅 12개에 발화 기록을 배선해 "모른다"를 "0건 확정"으로 바꾸고 claudebase 22훅을 A/B로 잰다. (2) verified 제거 3건을 치운다. (3) 계측 데이터가 도착한 뒤 배선 작업 9건. (4) 게이트를 통과하면 신설 1건. **새 스킬을 만들지 않는 것이 기본값이고, 만들려면 "왜 배선으로는 안 되는가"를 먼저 통과해야 한다.**

**Tech Stack:** Python 3(시스템 `python3` = Xcode 3.9.6, 훅 실행 인터프리터) · pytest · bash · Claude Code 훅 API · `coder-eval`

**Spec:** [DESIGN.md](DESIGN.md) — 요구 원문·실측 근거·확정 결정(DEC-1~7)이 거기 있다. 실행자는 둘 다 읽어라.

> **2026-08-23 갱신.** 재조사 2건이 이 계획의 일부 *근거*를 바꿨다 — 판정(DEC-1~7)은 하나도
> 반증되지 않았고 근거와 우선순위가 바뀌었다(사용자 결정 B3: "근거 교체 + 낡음 배너").
> **Phase 0이 새로 앞에 붙었고 그것이 1순위다.** 어느 태스크가 왜 흔들렸는지는
> [research/AUDIT-2026-08-23.md](research/AUDIT-2026-08-23.md) §8의 매핑 표가 항목별로 들고 있다.
> 그래프 3종 판정은 [research/ext-graph-engineering-v2.md](research/ext-graph-engineering-v2.md).

## Global Constraints

- **훅은 절대 세션을 막지 않는다.** 계측 훅이 예외를 던지면 사용자 턴이 죽는다. 모든 신규 로깅 경로는 `except Exception: pass`로 fail-open하고 exit 0.
- **로그 경로 규약**: `<cwd>/.omc/logs/<stem>.jsonl`. 전역 지표만 `~/.claude/metrics/`.
- **`harness_stats.py`의 탐지 방식이 설계를 구속한다.** `logging_hooks()`는 각 훅 **소스를 grep해 `<name>.jsonl` 리터럴**을 찾는다(harness_stats.py:106,124). 공유 헬퍼를 쓰더라도 **파일명 리터럴이 호출자 파일 안에 남아야** 한다 — 안 그러면 로깅을 붙여도 여전히 non-logging으로 보고된다.
- **배포 저장소에 머신 절대경로·버전 핀 금지.** claudebase·om\*는 전 머신에 배포된다.
- **파괴적 조작은 `trash` 경유**, 이동은 `mv` → 목적지 확인 → 그 다음 원본 삭제.
- **`unverified` 항목은 지우지 않는다.** DESIGN.md §1의 갈래 (B)·(C)는 삭제 근거가 못 된다.
- **훈련 launch 게이트는 어떤 통합에서도 약화시키지 않는다**(DEC-4).
- 커밋 접두사는 vault가 한국어 규칙(`[설정]`·`[프로젝트]`), claudebase·om\*는 각 저장소의 기존 컨벤션(Conventional Commits).

## File Structure

| 파일 | 책임 | 신규/수정 |
|:---|:---|:---|
| `claudebase/runtime/hooks/hooklog.py` | 훅 발화 1건을 `.omc/logs/<stem>.jsonl`에 append하는 유일한 공유 헬퍼. fail-open. | 신규 |
| `claudebase/tests/hooks/test_hooklog.py` | 위 헬퍼의 계약 테스트 | 신규 |
| `claudebase/tests/hooks/test_hook_logging_wired.py` | 12개 훅이 로그 리터럴을 갖는지 강제 | 신규 |
| `claudebase/runtime/hooks/{6개 .py}` | `hooklog.fire()` 호출 1줄 추가 | 수정 |
| `claudebase/runtime/hooks/{6개 .sh}` | append 3줄 추가 | 수정 |
| `claudebase/eval/experiments/claudebase-hooks-ab.yaml` | 22훅 A/B 실험 정의 | 신규 |
| `harness/measurements/<날짜>-baseline.md` | 발화 기준선 — Phase 3 판정이 인용 | 신규 |
| `oh-my-project/references/wiki/` | 빈 디렉터리 제거 | 삭제 |
| `oh-my-experiments/README.md:5` | 버전 배지 정정 | 수정 |
| `2_Resource/.../HARNESS_UPGRADE_PLAN.md` | 흡수 배너 + M1 폐기 표시 | 수정 |

**로그 레코드 규격** (기존 `askuserquestion-guard.py:124-128` 규약을 따른다):

```
경로: <cwd>/.omc/logs/<stem>.jsonl        한 줄에 JSON 하나, append-only
필드: ts          ISO-8601 UTC 초 단위     "2026-08-22T04:31:07+00:00"
      session_id  문자열 또는 null          "s1"
      <훅별 필드>  decision="allow" / repaired=0 / emitted_chars=3118
```

읽는 쪽은 기존 `harness_stats.guard_firings()`(harness_stats.py:133)이며 스키마 변경 없이 집계된다.

---

## Phase 0 — 2026-08-23 재조사가 추가한 것 (1순위)

> **근거 문서**: [research/ext-graph-engineering-v2.md](research/ext-graph-engineering-v2.md) ·
> [research/AUDIT-2026-08-23.md](research/AUDIT-2026-08-23.md) ·
> [notes/2026-08-23-worker-graph-handoff.md](notes/2026-08-23-worker-graph-handoff.md)
>
> **사용자가 이 절을 Phase 1보다 앞에 두라고 지정했다** (2026-08-23):
> "이러한 커뮤니티? 협업 체계에서는 종료 조건이라던가 실행 전 조건, 규칙 같은걸 좀 상세하게
> 작성할 필요가 있을 것 같네. 안그러면 끝도없이 돌아가면서 토큰을 낭비할 것 같아."

**이 절이 전제하는 결정 4건** (2026-08-23 사용자 답변):

| # | 결정 | 답 |
|:--|:---|:---|
| B1 | 대규모 작업의 자동 발동 범위 | **규모 판단·구조 설계는 자동, 발진만 승인 1회** |
| B2 | graphify 프로즈 그래프 존치 | **왜 조회 0회인지부터 규명한 뒤 판정** |
| B3 | DESIGN·PLAN 갱신 범위 | **근거 교체 + 낡음 배너** (판정 DEC-1~7은 유지) |
| B4 | 협업 프로토콜 구현 위치 | **문서 먼저 — 브리프 템플릿 1개.** 훅 강제는 발화율을 잰 뒤 |

---

### 0-A. 협업 프로토콜 — 사용자 지정 1순위

**왜 지금인가 — 낭비 메커니즘이 실측됐다.** 2026-08-23 두 세션(worker-graph·worker-audit)을
같은 vault에 붙여 돌린 결과다.

- **orca legacy 큐에 ack 경로가 아예 없다.** `check --json`은 메시지가 있으면 `legacy_read_only`로
  거부하고, `--peek`은 작동하지만 `read=0`이 유지되며, `--ack`가 요구하는 `delivery_id` 필드가
  legacy 메시지에 없다. "You have N messages"가 줄지 않고 조회할 때마다 **전량이 재출력**되므로
  수신 비용이 메시지 수에 선형이다. AgentRadio류가 전제하는 passive awareness와 정반대다.
- **종료 조건이 없어서 "닫는다"는 선언 자체가 새 메시지가 되어 답장을 부른다.** worker-audit이
  3회 닫힘을 선언한 뒤에도 교환이 이어졌다.
- **종료 프리미티브는 존재한다** — `worker_done`(`--outcome succeeded|failed`). 오늘 브리프 3행이
  코디네이터 부재를 이유로 금지했고, **대체 규약을 넣지 않은 것이 결함**이다.

**측정 조건 고지 (이 절의 근거가 무엇의 데이터가 아닌지).** 오늘 협업은 자발적이 아니라
사람이 다른 세션에서 지시한 것이다. 양쪽 브리프가 대칭으로 handle·파일 소유권·통신 명령어·
발신 기준까지 미리 정했다. 따라서 잰 것은 **"사람이 조율을 설계해줬을 때 전송로가 버티는가"**
하나뿐이고, **작업 분담 협상은 관측 0회**다. 프로토콜 설계는 이 한계 위에서 한다.

---

#### T17: 멀티세션 브리프 템플릿 (문서 1개, 코드 0줄)

**Files:**
- Create: `0_Project/in_progress/harness/protocol/multisession-brief-template.md`
- Create: `0_Project/in_progress/harness/protocol/examples/` — 오늘 브리프 2개를 증거로 보존

**Interfaces:**
- Produces: 다음 멀티세션 작업의 브리프가 이 템플릿을 채워 만들어진다. T18이 같은 문서에 절을 더한다.
- claudebase가 아니라 vault에 둔다 — "이 rig의 협업 관행"은 프로젝트 지식이지 보편 규율이 아니고,
  배포 저장소에 프로젝트 지식을 넣지 않는다는 규칙이 있다.

- [x] **Step 1: 오늘 브리프 2개를 먼저 증거로 옮긴다**

```bash
cd ~/ksm_Obsidian/0_Project/in_progress/harness
mkdir -p protocol/examples
cp /tmp/w1.md protocol/examples/2026-08-23-worker-graph-brief.md
cp /tmp/w2.md protocol/examples/2026-08-23-worker-audit-brief.md
ls -l protocol/examples/
```

`/tmp`는 재부팅에 사라진다. **템플릿의 근거가 되는 원문이므로 먼저 확보한다.**
파일이 이미 없으면 이 세션 트랜스크립트(`~/.claude/projects/-Users-kimseungmin-ksm-Obsidian/`)에
전문이 남아 있다.

- [x] **Step 2: 종료 조건 절을 쓴다 (가장 중요 — 사용자가 이것 때문에 지시했다)**

다섯 항목으로 초안했다가 **셋으로 합쳤다** — 1·2·5는 한 규칙의 세 얼굴이었다. 실제 산출은 3항목이다.

1. **종료 정의**: "산출물 커밋·푸시 완료 + 마지막 신호 발신 = 종료."
2. **단방향 종료 신호**: 제목에 `[FINAL]`. **`[FINAL]`을 받으면 답하지 않는다.**
   이것이 프로토콜의 **유일한 답장 금지 규칙**이며, 오늘 부재해서 3회 닫힘 선언이 무력했다.
3. **교환 상한**: "완료 선언 후 교차 검토 1라운드까지". 라운드를 세는 주체는 발신자다.
4. **수신 예산**: legacy 큐는 전량 재출력이므로 **조회는 작업 단계 사이에만**. 턴마다 열지 않는다.
5. **종료 후 수신**: 읽되 답하지 않는다. 예외는 blocking 사안 1종뿐이고, blocking의 정의를
   브리프가 명시한다("상대 산출물이 내 판정을 뒤집는 실측을 들고 온 경우" 수준까지 구체적으로).

**대안 경로도 같이 적어 둔다**: `run-create`로 Run을 열면 `worker_done`·`worker-release`가
살아나 종료가 인프라 차원에서 처리된다. 오늘은 코디네이터 부재를 이유로 이 경로를 버렸는데,
**버릴 거면 대체 규약을 브리프에 넣어야 한다**는 것이 오늘의 교훈이다.

- [x] **Step 3: 실행 전 조건 절을 쓴다**

여섯 항목으로 초안했다가 **다섯으로 합쳤다**(2·4를 하나로). 전부 오늘 브리프가 빠뜨렸거나 어긋났던 것이다.

1. **명령어는 작성자가 실행해 본 것만 적는다.** 오늘 브리프의 명령어 2개가 둘 다 실패했다 —
   `git pull --rebase`(훅 소유 파일이 unstaged라 거부), `check --json`(`legacy_read_only`).
2. **자율성 규약 단일화.** 오늘 브리프는 3행 "스스로 완주해라"와 57행 "각 단계마다 승인을
   물어라"가 정면으로 모순이었다. 둘 중 하나만 남긴다.
3. **성공 기준**: 실측 N건 + **부정 증거 N건** + 미확인 목록을 필수 산출물로 명시.
4. **역할 모순 금지.** **모순은 브리프 안이 아니라 브리프 *사이*에 있었다**(2026-08-23 실행 중
   정정): w1 39행은 "동료가 네 문서에 대한 감사 결과도 낼 수 있다"인데 w2 26행은 그 문서를
   "대상 아님"으로 못박았다. 그래서 상호 검토가 끝내 일어나지 않았다. **자율성 모순과 함께
   한 항목으로 합쳤다** — 실행 전 조건은 6항목이 아니라 5항목이다.
5. **측정 조건 자기고지.** 브리프가 조율을 설계했다면 "이 협업은 자발적 조율의 데이터가
   아니다"를 브리프 안에 적는다. 안 적으면 워커가 자기 협업을 인프라 성능으로 오독한다
   (오늘 실제로 그랬고 사용자가 정정했다).
6. **파일 소유권 표 + 공유 노트 경로.** 오늘 지정된 공유 노트
   `notes/2026-08-23-worker-comms.md`는 **끝내 안 만들어졌다** — 지정만으로는 안 쓰인다는
   증거이므로 "누가 언제 쓰는가"까지 적는다.

- [x] **Step 4: 실패 모드 절을 쓴다 — 가장 싼 부품이다**

오늘 내 세션을 실제로 작동시킨 것은 허브도 통신도 아니라 **브리프의 실패 모드 3줄**이었다.
워커 수와 무관하게 걸리고 공유 공간보다 훨씬 싸다. 오늘 3종을 원문 그대로 옮긴다.

1. 요구 원문의 어휘를 그대로 검색어로 쓰면, 원문이 안 쓴 축은 조사에서 통째로 사라진다.
2. "이미 배선이 있다"는 전제를 실측 안 하고 넘어간다.
3. 최신 문헌 누락, 그리고 한쪽 증거만 담기.

- [x] **Step 5: 자기 채점 — 템플릿이 과한지 본다**

```bash
cd ~/ksm_Obsidian/0_Project/in_progress/harness/protocol
# examples/ 의 브리프 2개를 템플릿 항목별로 대조해 빈 칸을 센다
```

오늘 브리프 2개가 템플릿의 몇 항목을 채웠는지 세어 표로 남긴다. **다섯 항목 이상 비어 있으면
템플릿이 과하다는 뜻이므로 줄인다** — 아무도 채우지 않는 템플릿은 죽은 공유 공간 3개와 같은
길을 간다(T19의 주의 참조).

- [x] **Step 6: 커밋**

```bash
cd ~/ksm_Obsidian
git add 0_Project/in_progress/harness/protocol/
git commit -m "[프로젝트] 멀티세션 브리프 템플릿 — 종료 조건·실행 전 조건·실패 모드" && git push
```

**실행 결과 (2026-08-23).** [`protocol/multisession-brief-template.md`](protocol/multisession-brief-template.md)
작성 완료, 브리프 원문 2개는 [`protocol/examples/`](protocol/examples/)에 보존.
**Step 5의 자기 채점이 임계를 넘었다** — 아홉 항목 중 오늘 브리프가 채운 것은 3.5개뿐이고
5.5개가 비었다(임계 5). 규칙대로면 줄여야 하므로 **12항목을 9항목으로 병합**했고, 그 이상은
줄이지 않았다: 남은 빈 항목이 전부 그날 실제로 사고가 난 지점이라 하나라도 빼면 그 사고를
막지 못한다. 임계 초과의 원인은 템플릿이 부푼 것이 아니라 **그날 브리프에 종료 조건이라는
축이 통째로 없었던 것**이고, 그게 이 태스크가 존재하는 이유다.
**재측정 조건**: 다음 브리프가 이 템플릿으로 작성됐는데도 셋 이상 비면 그때는 진짜로 줄인다.

---

#### T18: 자동 발동 규약 (사용자 결정 B1)

**Files:**
- Modify: `protocol/multisession-brief-template.md` — T17이 만든 문서에 절 하나를 더한다

**Interfaces:**
- Consumes: T17의 문서. 새 파일을 만들지 않는다.
- 결정 B1이 확정한 층 분리를 그대로 적는다: **규모 판단(자동) / 구조 설계(자동) / 발진(사람 승인 1회)**.

- [x] **Step 1: 규모 판정 기준을 쓴다**

"큰 작업"의 정의가 없으면 자동 발동이 판단 불가다. 기준은 **관측 가능한 것**으로만 적는다
(독립적으로 진행 가능한 축의 수, 손대야 하는 저장소 수, 산출 문서 수 등). 애매하면
"세지 말고 사람에게 묻는다"를 기본값으로 둔다.

- [x] **Step 2: 승인 게이트를 정확히 한 지점에 둔다**

지출이 걸리는 층만 사람이 잡는다 — 즉 **에이전트를 실제로 띄우기 직전 1회**. 규모 판정과 구조
설계는 승인 없이 진행하고, 제안 형태로 사람에게 제시한다.

근거: `.omc/paper-hub/`(2026-08-23 실측)에서 **허브 구조와 프로토콜을 사람이 아니라 에이전트가
설계했고 그 부분은 성공했다**. 문제가 난 곳은 설계가 아니라 발진 이후였다(gitignored 산출물,
Phase 1에서 no-op이 된 프로토콜 1번, oms 레인 우회).

- [x] **Step 3: 상한과 미측정 사항을 같이 적는다**

- Workflow 크기 가이드라인 상한 15. paper-hub은 13으로 그 안에 있었다.
- **13명이 3명보다 나은지는 이 rig에서 잰 적이 없다.** 포화 임계 ~4라는 문헌 수치는 confidence
  `likely`이며 이 rig 측정이 아니다. 규약에 "많을수록 낫다"를 암시하는 문구를 넣지 않는다.

- [ ] **Step 4: 완료 조건** — *규약은 작성됐고, 이 조건은 아직 미충족이다*

다음 대규모 작업 1건에서 **판정 → 구조 제안 → 승인 1회 → 발진**이 실제로 그 순서대로 돈다.
돌지 않으면 규약이 아니라 문서일 뿐이므로 그 사실을 기록한다.

**실행 결과 (2026-08-23).** 규약을 [`protocol/multisession-brief-template.md`](protocol/multisession-brief-template.md)의
"언제 자동으로 발동하나" 절로 작성했다 — 층 분리 표, 규모 판정 3축, 4줄 제안 형식, 상한과
미측정 고지, 도메인 레인 게이트, 완료 조건. **규모 임계값(축 3개 또는 저장소 2개)은 측정된
값이 아니라 출발점**이며 그 사실을 문서 안에 명시했다. 이 rig 표본은 세션쌍 1건과 paper-hub
1건뿐이다. Step 4는 다음 대규모 작업에서 판정한다.

---

#### T19: 산출물 수명 분리 — 공유 저장소 3층 (사용자 제시 방향)

**Files:**
- Move: `.omc/paper-hub/findings/`·`reviews/` → tracked 경로
- Modify: `.omc/paper-hub/HUB.md` — 포인터 갱신

**선행 조건:** `.omc/paper-hub/`의 워크플로(`wf_4383bc8a-afd`)가 **끝난 뒤**에 착수한다.
2026-08-23 15:52에도 `discussion.md`에 쓰고 있었다. **돌고 있으면 손대지 마라.**

**설계 (사용자 제시 방향을 3층으로 정리).**

| 층 | 무엇 | 매체 | 수명 |
|:---|:---|:---|:---|
| 1 조율 | 아직 기록 안 된 진행 중 발견, 클레임 | orca 메시지 / `discussion.md` | 세션 |
| 2 산출물 | findings·reviews. frontmatter에 작성자·시각 | **tracked 경로** | 프로젝트 |
| 3 지식 | 승격된 결론 | wiki (`omx wiki`·`.omp/learned.md` 계열) | 영구 |

- [x] **Step 1: 결함을 재확인한다**

```bash
cd ~/ksm_Obsidian
git check-ignore -v .omc/paper-hub/findings/   # .gitignore:57 (**/.omc/) 에 걸린다
ls .omc/paper-hub/findings/ .omc/paper-hub/reviews/
```

산출물이 커밋되지 않으므로 **다음 세션·다른 머신·worktree에 남지 않는다.**
조율(1층)은 ephemeral이어도 되지만 산출물(2층)은 아니다.

- [x] **Step 2: 2층 위치를 정하고 옮긴다** — **완료 (2026-08-24 09:45).** 위치 선정·이동은
08:30에, 원본 폐기는 런 종료 후 09:45에. 아래 "T19 종결" 참조

이동은 `mv` → 목적지 확인 → **그 다음** 원본 삭제. 같은 호흡에 지우지 않는다.

- [x] **Step 3: HUB.md의 포인터를 같은 편집에서 갱신한다**

옛 경로가 남는 drift를 만들지 않는다. `discussion.md`는 1층이므로 `.omc/`에 그대로 둔다.

- [x] **Step 4: 3층 승격 트리거만 새로 적는다**

이미 있는 것으로 덮이는 부분은 만들지 않는다 — frontmatter 작성자 표기는 auto-memory와 브리프
공유노트 규약에 이미 있고, "승격은 사람 게이트"는 `omp-learn`·`omx wiki`·`docs-learn`이 이미 그
패턴이다. **신규로 필요한 것은 2층의 위치 규약과 1→2→3 승격 트리거뿐이다.**

**주의 — 죽은 공유 공간이 이미 셋 있다.** `shared_memory_*` 사용 0건, Agent Teams 41세션 전부
팀원 0명, omc `wiki_*`는 vault 98개 중 95개가 455바이트 자동 스텁(실내용 3개, 최종 갱신 08-17).
네 번째인 `.omc/paper-hub/`만 살아 있고, **차이는 공간이 아니라 프로토콜이 읽기를 강제했고
워크플로가 실제로 썼다는 것**이다. 새 공간을 만들기 전에 그 셋이 왜 죽었는지를 한 문단으로
적고 시작한다. 공유 상태 조율은 공짜도 아니다 — CodeCRDT 600 trial에서 일부 태스크 +21.1%,
다른 태스크 −39.4%, 의미 충돌 5~10%.

**실행 결과 (2026-08-24) — Step 1·3 완료, Step 2 부분, Step 4 미착수.**

*결함은 계획이 적은 것보다 컸다.* `.gitignore:57`이 잡는 것은 산출물만이 아니었다 —
**추적되는 vault 문서 11개가 `.omc/paper-hub/findings/*.md`를 근거 출처로 인용**하고 있었다:
`2_Resource/papers/` 리뷰 3건(DORAEMON·Chaffre·MarineGym), `albc/paper/RL-ALBC - Experiments.md`,
`albc/paper/background/` 4건, `albc/paper/methodology/` 2건, `albc/paper/README.md`.
`.omp/wiki/paper-work-split.md`는 `PHASE1-SYNTHESIS.md`를 가리킨다. 즉 **영구 노트가 죽을
디렉터리를 근거로 걸고 있었고**, 다른 머신·새 클론에서는 그 인용이 아무 데도 닿지 않았다.
"모든 진술은 출처로 추적된다"는 vault 규칙이 조용히 깨져 있던 것이다.

그래서 범위에 `PHASE1-SYNTHESIS.md` 하나를 더했다 — 같은 결함·같은 수선이고, 빼면
`.omp/wiki/`(영구층)의 포인터를 일부러 부러진 채 남기게 된다.

**2층 위치**: `0_Project/in_progress/albc/notes/2026-08-23-paper-hub/`.
근거는 `.omp/STRUCTURE.md` 둘 — 프로젝트 내부는 `notes/`(시간순 기록)이고, 폴더 이름에 날짜를
넣는 것은 `docs/`가 "언제 것인지 말하지 않는 이름"이라 폐기된 세대를 현재처럼 보이게 했던
실패의 교정이다. 진입점 `README.md`를 함께 만들어 "동결됨 · findings 단독 인용 금지 ·
정본은 SYSTEM.md"를 선언했다. `notes/README.md`·`albc/README.md` 색인도 같은 편집에서 갱신.

**포인터 갱신 검증**: 치환 후 새 경로 전수를 파일 존재로 대조해 MISS 0. 그 과정에서
`discussion.md`의 **기존 오타 1건**(`findings/marinelab-inventory-review.md` → 실물은
`reviews/`)이 드러나 함께 고쳤다. `.omx/registry/findings/`·`sim_validation/findings/`·
`05_reviews/`는 무관 경로라 lookbehind로 배제했고 오염 0을 before/after 대조로 확인했다.

🔴 **Step 2 미완 — 원본을 지우지 못했다. 선행 조건이 작업 도중 다시 거짓이 됐다.**
착수 시점 측정은 13시간 12분간 쓰기 0 · 열린 파일 0 · CPU 평탄이었고 그 시점엔 맞았다.
그런데 복사 직후 검증에서 **`findings/dr-beta-ranges.md`가 새로 나타났다**(08:33:26).
`session-6ab80e4d`가 에이전트 6개(`drafter-ieee`·`lit-cts`·`lit-carlucho`·`lit-cpo`·
`lit-kim2025`·`lit-manipulider`)로 이 HUB의 "남은 작업" 2·4·6을 실행 중이다.
**`[[feedback_check_result_is_not_state]]`의 재현** — 검증은 그 순간의 사진이지 상태가 아니다.

- 원본은 **하나도 지우지 않았다.** 스냅샷 31건은 tracked에 있고 포인터 11건은 이미 이어졌다.
- 스냅샷에 없는 것: `findings/dr-beta-ranges.md` (그 런의 산출물).
- `HUB.md` 배너는 "이관 진행 중, 워커는 하던 대로 `findings/`에 써라"로 정정했다 —
  처음 단 배너가 "산출물은 여기 없다"고 **거짓을 말하고 있었다.**
- 라이브 세션 산출물(`2_Resource/papers/.../Kim 2025 - Distilling.../`)은 커밋에서 제외.

**T19 종결 (2026-08-24 09:45) — Step 1~4 전부 완료.**

런은 09:10에 끝났다(`reviews/mock-review-v11-ac.md`가 마지막 산출). **판별자는 경과 시간이
아니라 에이전트 부재였다** — 08:30에 막았던 근거는 "13시간 조용"이 아니라 워커 6개가 살아
있다는 사실이었고, 09:45에 그게 0이 됐다. 폐기 직전에 가드로 다시 쟀다(에이전트 0 · 최근
10분 쓰기 0, 아니면 `exit 1`).

- (a) **drift 3건 반영** — `findings/dr-beta-ranges.md`, `reviews/mock-review-v11-{ac,lenses}.md`.
  31 → **34건**(findings 22 · reviews 11 · 종합 1). 신규분의 옛 경로 참조도 같은 규칙으로 치환.
- (b) **원본 폐기** — `trash` 경유. **순서가 중요했다: 커밋(`86cab53c`) → 폐기.** 지우기 전에
  git에 들어가 있어야 복원 경로가 생긴다. `HUB.md`·`discussion.md`는 1층이라 `.omc/`에 잔류.
- (c) **포인터·요약층 5곳** — `HUB.md` 배너 완료형, `notes/README.md`·`albc/README.md` 건수
  31→34, 스냅샷 `README.md` 구성표 + "원본은 폐기됐고 여기가 유일본" 명시.

**중간에 밟은 함정 하나**: `git commit -- <pathspec>`는 **미추적 파일을 스테이징하지 않는다**.
첫 시도가 "no changes added to commit"으로 조용히 실패했고, `git add` 선행이 필요했다.
병렬 세션 방어로 쓰던 pathspec 커밋의 알려지지 않은 경계다.

**D1~D7 표는 옮기지 않는다 (2026-08-24 사용자 결정).** 내가 "프로젝트 수명인데 추적 안 된다"고
판단 대기로 걸었던 건인데, 사용자 판정은 **작업 보드와 결정 표가 붙어 있어야 맥락이 산다**는
쪽이다. 즉 3층 모델에서 이 표는 2층이 아니라 **1층(조율)에 속한다** — 결정 *자체*가 아니라
그 결정이 어느 보드의 어느 행에 걸렸는지가 이 표의 값이기 때문이다. 결정의 *결과*는 이미
`albc/paper/`와 `SYSTEM.md`에 반영돼 있어 소실되는 사실은 없다.

**Step 4 완료 (2026-08-24) — 새 문서를 만들지 않았다.** 위 "죽은 공유 공간 셋" 경고의
직접 귀결이다: 넷째 문서를 만들면 그 셋에 하나를 더하는 것이므로, 규약을 실제로 복사돼
나가는 [`protocol/multisession-brief-template.md`](protocol/multisession-brief-template.md)에
붙였다 — 새 절 "산출물은 어디 사는가" + 템플릿 본문 `## 파일 소유권`에 2층 규칙 한 항목.

*셋이 왜 죽었는가(선행 문단)*: 공간 부족이 아니라 **쓰기 유인 부재**다. 셋 다 "여기 쓸 수
있다"만 있고 "여기 쓰지 않으면 작업이 안 굴러간다"가 없었다. paper-hub만 산 이유는 브리프가
읽기를 강제하고 산출물 경로를 워커에게 **배정**했기 때문이다.

*그리고 이번에 새로 드러난 축*: **살아 있음(쓰기 유인)과 남음(수명)은 다르고 둘 다 필요하다.**
살아 있던 그 공간이 gitignored라 추적 문서 11건의 근거가 이 머신 전용이었다.

*규약 3개*: (1) 2층은 tracked 경로 — 쓰기 전 `git check-ignore -v`, (2) 그 프로젝트의
`notes/` 안에 `YYYY-MM-DD-<주제>/`로(`.omp/STRUCTURE.md`의 `docs/` 실패 교정), (3) 동결이며
폴더 `README.md`가 "무엇을 믿으면 되는가"를 선언.
*승격 트리거*: **1→2 = 다른 문서가 인용하는 순간**(자동, 처음부터 2층에 쓴다),
**2→3 = 다음 작업의 전제로 재사용될 때**(사람 게이트 — `omp-learn`·`omx wiki`·`docs-learn`
재사용, 신설 0). 사후 이관 비용 실측: 31파일 이동에 포인터 갱신 14파일.

---

#### T20: 논문 작업의 oms 레인 게이트

**Files:**
- Modify: `~/oh-my-heroacademia/cards/*.json` (라우팅 SSOT) — 확인 후에만

**왜:** `.omc/paper-hub/`은 논문 작업인데 일반 워크플로 에이전트로 돌아 **citation 무결성 가드가
안 걸렸다**. "문헌 결손 대조"는 곧 `scholar-research`인데 oms 레인을 우회했다.

- [x] **Step 1: 카드에 이미 규칙이 있는지부터 본다**

omha 카드가 라우팅의 SSOT다. "논문 산출물이면 oh-my-scholar"라는 캐스케이드 1순위 규칙은
이미 존재한다 — **없어서 우회된 게 아니라 워크플로 에이전트에 그 게이트가 안 걸린 것**인지
구분한다. 이 구분이 조치를 바꾼다.

- [x] **Step 2: 조치는 Step 1의 결과에 따라 갈린다**

규칙이 있는데 워크플로 경로에서 안 걸린 것이면 **카드가 아니라 발동 지점의 문제**이므로
T18의 자동 발동 규약에 "도메인 레인은 판단 대상이 아니라 게이트다"를 명시하는 것으로 끝낸다.
규칙 자체가 없으면 카드에 추가한다.

**실행 결과 (2026-08-23) — 후자가 아니라 전자다. 카드는 고치지 않았다.**
규칙은 `cards/oms.json`에 실재하고 라우팅 캐스케이드도 "논문은 반드시 oh-my-scholar"를 1순위로
못박고 있다. 안 걸린 이유는 **주입과 강제 두 층이 서브에이전트에서 각각 비어 있기 때문**이다:

| 층 | 파일 | 왜 안 걸리나 |
|:---|:---|:---|
| 주입 | `route_emit.py` | 플러그인 매니페스트상 **UserPromptSubmit 전용**. 서브에이전트는 사용자 프롬프트를 받지 않아 캐스케이드를 한 번도 못 본다 |
| 강제 | `route_guard.py` | 서브에이전트를 **명시적으로 통과**시킨다 — `route_guard.py:235`, 주석 원문 "Subagents run their own sub-conversations without the omha injection" |

**그 통과는 버그가 아니라 필연이다** — 받은 적 없는 ROUTE 줄을 요구하면 모든 서브에이전트가
첫 툴 호출에서 죽는다. 그러므로 **13명은 라우팅 레이어 밖에서 돌았고 앞으로도 그렇다.**

**조치**: 게이트를 걸 수 있는 유일한 지점은 **워크플로 스크립트를 쓰는 세션**이므로,
발진 제안에 "어느 도메인 에이전트를 쓰는가"(`agentType`)를 적게 만드는 것으로 끝냈다.
`protocol/multisession-brief-template.md`의 "도메인 레인은 판단 대상이 아니라 게이트다" 절.
**omha 카드·훅은 건드리지 않았다** — 고칠 대상이 아니었다.

---

### 0-B. 그래프 3종 — 재조사 v2의 실행 항목

**측정 요약** (2026-08-23, 트랜스크립트 451개 / 881MB / 30일 전수):

| 도구 | MCP 툴콜 | 인덱스 | 디스크 |
|:---|---:|:---|---:|
| tokensave | 21 (15세션, 전부 vault) | **0 노드** | 25 MB |
| code-review-graph | 2 | 664 노드 / 93 파일 | 13 MB |
| graphify | **0** | 12,867 노드 / 14,267 링크 | 203 MB |

같은 기간 Bash 11,074 · Read 3,184 · Grep 23. **그래프 조회 25회 대 원시 파일 조작 14,000+.**

---

#### T21: tokensave 복구 (vault + claudebase) — 무효 (2026-08-25)

> **이 과제는 더 이상 유효하지 않다.** 2026-08-25 에 tokensave 를 claudebase 에서
> 전면 제거했다 — 인덱스가 죽어서가 아니라 **아무도 조회하지 않아서**다(vault 세션
> 10,813 tool call 중 MCP 6건, 0.055%). 아래 본문의 실측·복구 절차·상류 버그 분석은
> 그대로 기록으로 남긴다. 제거 근거와 다른 머신 잔재 제거 절차는
> `docs/CHANGELOG.md` 2026-08-25 항목과 `sync-claudebase` §4m 을 봐라.

**긴급도 최상.** vault `CLAUDE.md`의 라우팅 표가 "어느 노트가 X를 말하나"의 **첫 번째 도구**로
`tokensave_search`를 지정하는데, 그 표가 실측 예시로 못박은 `tokensave_search "runaway"` → 2 hits가
지금 `[]`를 반환한다. **`[]`는 에러가 아니라 "여기 없다"와 구별되지 않으므로**, 인덱스가 죽은 줄
모르는 세션은 빈 결과를 근거로 "이 vault에 그런 노트 없음"을 단정한다. 이미 소급 피해가 있다 —
`gap-omx.md` §3의 증거가 "tokensave_search로 확인(verified)"인데 재현되지 않는다.

**Files:**
- Modify: `~/ksm_Obsidian/.tokensave/`, `~/claudebase/.tokensave/` (도구가 쓴다)
- Modify: 없음 — `~/.claude/settings.json`은 **불변이어야 한다**(Step 2가 그 보증이다)

- [x] **Step 1: 상태를 MCP로 다시 확인한다 (CLI 아님)**

`tokensave_status` MCP 툴을 쓴다. 기대: vault `node_count: 0`, `stale_commits` 증가 중.

- [x] **Step 2: CLI 호출 금지 룰의 예외 절차를 밟는다**

`tokensave <verb>`는 `status` 같은 순수 조회조차 `~/.claude/settings.json`을 다시 쓰고 자기 훅을
재주입한다(측정됨). claudebase 룰이 그래서 CLI 호출을 금지한다. **복구는 도구가 안내하는
`tokensave sync`뿐이므로 예외 절차가 필요하다:**

```bash
cp ~/.claude/settings.json /tmp/settings.before.json
shasum -a 256 ~/.claude/settings.json
# ... sync 실행 ...
shasum -a 256 ~/.claude/settings.json
# 해시가 다르면:
cp /tmp/settings.before.json ~/.claude/settings.json
```

**해시 대조와 복원까지가 이 스텝이다.** 사본 없이 sync를 돌리지 마라.

- [x] **Step 3: claudebase 쪽도 같이 밟는다** — **완료 (2026-08-24 09:55). `sync` 한 번으로 끝났다.**

`sync` 실행 → `migrating database schema v16 → v17` → `schema changed — performing full re-index`
226파일 → `sync done` **exit 0**. 결과 **3,059노드 / 226파일 / `pragma user_version` = 17**,
MCP 조회 복구 확인(`tokensave_search "hooklog"` → `runtime/hooks/hooklog.py:27` 포함 5건).
추적 파일은 안 건드려졌다(`git status --porcelain` 공백).

**"별도로 확인한다"는 이 스텝의 전제가 맞았다 — 조치가 실제로 달랐다.**

| | vault | claudebase |
|:---|:---|:---|
| 증상 | 전체 sync가 패닉으로 죽음 → **0노드** | 인덱스는 온전한데 **하드 거부** |
| 원인 | v7.10.0의 `&s[..len-10]`이 UTF-8 문자 경계 무시 | schema 16 ≠ required 17 |
| 조치 | `--skip-folder` 9경로 | **`sync` 한 번**, skip 불필요 |
| 손실 | 실질 신규 212파일 | **0** |
| 갈린 이유 | 한글 파일명 81개 | 비ASCII 파일명 **0건**(`git ls-files -z` 실측) |

**⚠️ 그리고 부작용이 이번엔 실제로 발생했다 — Step 4 표의 "해시 불변 ✅"를 오독하지 마라.**
sync 직후 `~/.claude/settings.json`은 `b071eb97…` → `ba077415…`로 **바뀌었고**,
`"command": "#"` 훅 2개(`hook-prompt-submit` · `hook-stop`)가 주입됐다.
**불변은 복원의 결과지 sync의 성질이 아니다.** 사본 없이 돌렸으면 이 세션과 그때 살아 있던
병렬 claude 프로세스 3개가 다음 렌더까지 매 프롬프트 중복 훅을 탔다. 복원 후 재검증:
해시 원값 일치 · 훅 개수 원상 · `"command": "#"` 잔재 0건.

- [x] **Step 4: 완료 조건** — **충족. 단 완료 조건 자체가 부정확했다.**

| 조건 | 결과 |
|:---|:---|
| 인덱스 복구 | ✅ 12,305노드 / 853파일 |
| `~/.claude/settings.json` 해시 불변 | ✅ `b071eb97…` 바이트 단위 일치 |
| `tokensave_search "runaway"` → 2 hits | ⚠️ **1건.** 그런데 이건 인덱스 문제가 아니다 |

**"2 hits"라는 기준 자체가 틀렸다 — 그리고 그게 새 발견이다.** 놓치는 쪽 제목은
`### 2.1. target runaway는 sim-to-real 갭이 아님`이고 노드는 색인에 **존재한다**(같은 파일 10노드).
안 걸리는 이유는 **`runaway는`이 한 토큰**이기 때문이다 — **한글 조사가 붙은 영어 단어는 맨몸
검색으로 안 잡힌다.** vault `CLAUDE.md`의 "한 단어로 검색하라" 규칙에 짝이 되는 함정이며,
이 vault 노트에서 극히 흔하다. 영어 단어 검색 결과가 적으면 `Grep`으로 교차 확인해야 한다.

**vault `CLAUDE.md` 배너를 그에 맞춰 갱신했다** — "죽어 있다"에서 "주의 2가지"(조사 함정 +
인덱스 취약성 + `node_count` 먼저 보기)로.

- [x] **Step 5: 왜 0으로 끝났는지 기록한다 (C1)**

마이그레이션이 비웠는지, 색인 대상 판정이 깨졌는지 구분한다. 재빌드는 **끝난 뒤에도 0**이었다
(15:15 `rebuild_in_progress: true` → 15:27 플래그 소멸 + `stale_commits: 13` → 15:34 `14`).
**원인을 찾았고 복구했다 (2026-08-23 17:40~18:00). 마이그레이션이 아니다.**

**전체 재색인이 한글 파일명에서 패닉으로 죽는다.** tokensave 7.10.0이 진행 표시용으로 경로를
자르는데 **UTF-8 문자 경계를 보지 않는다**:

```
thread 'main' panicked at .../library/core/src/str/mod.rs:849:21:
end byte index 63 is not a char boundary; it is inside '테' (bytes 61..64)
of `0_Project/completed/pkrc_completed/experiments/센서 구동 테스트.md`
```

**절단 규칙은 `&s[..len-10]`이다 — 고정 폭이 아니다.** 처음 두 번은 byte 63에서 죽어 고정 폭으로
오판했는데, 세 번째 실행이 **byte 73**에서 다른 파일로 죽으며 규칙이 드러났다:

| 경로 바이트 길이 | 패닉 인덱스 | 차 |
|---:|---:|---:|
| 73 (`…/센서 구동 테스트.md`) | 63 | 10 |
| 83 (`…/연구개발 계획서 및 로드맵.md`) | 73 | 10 |

- **술어**: 경로의 `len-10` 바이트가 UTF-8 continuation byte(`b & 0xC0 == 0x80`)이면 죽는다.
- **이 vault에서 걸리는 tracked 파일은 81개**(3,678 중), **17개 디렉터리**에 흩어져 있다.
  `2_Resource` 60 · `0_Project` 10 · `3_Archive` 10 · `.obsidian` 1.
  **초기에 적은 "byte 63 / 46개"는 틀렸다** — 규칙을 잘못 특성화한 결과다.
- **왜 0으로 남았나**: 패닉이 커밋 전에 프로세스를 죽이므로 아무것도 안 들어간다. 그리고
  `last_sync_at`이 20시간 전 값으로 살아 있어 **증분 sync는 바뀐 파일만 훑는다** — 비어 있는
  인덱스는 증분으로 절대 안 채워진다(`last_sync_duration_ms: 79`가 그것이다).
- **끄는 방법 없음**: `TERM=dumb`·`CI=1`·`NO_COLOR=1` 전부 무효. 전역 quiet 플래그도 없다(`--help`).
- **claudebase가 왜 멀쩡한가**: 파일명이 전부 ASCII다. 같은 버그를 안 밟는다.

**예외 절차는 정상 작동했고 설정은 무손상이다.** `sync`가 `✔ Wrote ~/.claude/settings.json`을
찍으며 훅 4개를 추가했다(`UserPromptSubmit`·`Stop` 각각 리터럴 `"#"` 1개 + **서브커맨드 없는
맨몸 `tokensave`** 1개 — 추가된 것 자체가 망가져 있다). diff로 확인 후 사본에서 복원했고
**해시가 원본과 바이트 단위로 일치**한다(`b071eb97…`). `--help`는 해시를 안 바꾼다(룰 문서대로).

**복구 실행 — 성공.** 사용자 결정(2026-08-23)에 따라 `--skip-folder` 우회를 돌렸다.
**결과: 12,305노드 / 853파일 / 528ms.** 제외한 경로 9개:

```
.obsidian · 3_Archive
2_Resource/lectures/claude_code_complete_master/{transcripts,sections}
0_Project/in_progress/pkrc/notes/meetings
0_Project/in_progress/krit/{documents,reference}
0_Project/completed/{pkrc_completed,kmrts}
```

부수 피해는 원시로 **1,280파일**이지만 그중 **1,068이 `3_Archive`·`.obsidian`** —
`.graphifyignore`·`.code-review-graphignore`가 이미 정책적으로 제외한 것들이라 새 손실이 아니다.
**실질 신규 손실 212파일(5.8%)**, 그중 184가 강의 트랜스크립트다.

`session-gate` 훅이 처음 시도를 막았다(`--skip-folder` 인자의 `albc` 문자열). **우회하지 않고
게이트가 요구한 문서 3건을 읽어 해소했다** — 회피보다 만족이 싸고 정직하다.

**이 우회는 근본 해결이 아니다** — 새 한글 노트의 `len-10`이 문자 중간에 걸리는 순간 다시 죽는다.
근본 해결은 상류 수정이고, 그래서 **사용자에게 이슈 제기를 제안했다**
(github.com/aovestdipaperino/tokensave). 제출 전 민감·독점 내용 제거 필요.

auto-memory: `machine_tokensave_korean_filename_panic.md`(구 `..._schema17_empties_index.md`).

---

#### T22: graphify 조회 0회의 원인 규명 (사용자 결정 B2)

~~**선행 조건: Phase 1 Task 3.**~~ **이미 충족됐다 (2026-08-23 확인)** — Task 1~3은 08-22에
완료돼 있었고 `graphify_guard.jsonl`이 지금도 쓰이고 있다(vault 144KB). 선행 대기가 아니었다.

**세 갈래를 가른다.**

| 가설 | 어떻게 재나 | 판정 시 조치 |
|:---|:---|:---|
| 도구 부적합 | 프로즈 그래프가 답할 수 있는 질문을 이 vault에서 실제로 몇 번 물었는지 트랜스크립트에서 센다 | 질문 자체가 없으면 폐기 |
| 훅 유도 실패 | 그 턴에 `graphify-guard`가 발화했는지 (Task 3의 로그) | 유도 경로를 고친다 |
| 망각 | 발화했는데도 안 썼는지 | 라우팅 표에 넣는다 |

**"묻는 방법을 모르는 것"과 "물을 게 없는 것"은 다른 문제고 조치도 다르다.** 이 구분이 나오기
전에는 존치·폐기를 결정하지 않는다.

- [x] **Step 1**: 로그를 모은다 — 2026-08-22 08:21 ~ 08-23 09:15 UTC, **발화 2,112건**
- [x] **Step 2**: 위 표를 채운다
- [x] **Step 3**: 존치/폐기 판정 — **사용자 결정: "MCP 배선만 제거 + 한 창 더 측정"** (2026-08-23)

**실행 완료.** 확정된 층만 잘랐다.

| 층 | 조치 | 근거 |
|:---|:---|:---|
| MCP 배선 | **제거** — vault `.mcp.json`에서 graphify 서버 삭제(CRG는 유지) | 라우팅 채널 0개, 30일 사용 0회. 도구가 아니라 배선 문제 |
| 가드 넛지 | **존치** | 준수율 0.68%가 "부적합"인지 "망각"인지 아직 못 가름 |
| 프로즈 그래프·CLI | **존치** | 능력이 유일하고, 폐기는 재추출 5시간의 비가역 비용 |

**다음 창을 위한 계측을 심었다.** `graphify-guard.sh`의 로그 레코드에 **`mode`와 `target`
2필드를 추가**했다 — 이제 발화마다 "무엇을 읽으려던 참이었나"가 남으므로, 442회 중 실제로
그래프가 답할 수 있는 질문이 몇 개였는지 다음 창에서 갈린다.

**비용 0**: 그 값을 뽑는 `python3` 호출은 `session_id` 때문에 **이미 매 발화마다 돌고 있었다** —
같은 호출에 얹었다. 검증: `bash -n` 통과, 합성 페이로드 4건으로 한글·내부 따옴표·깨진 JSON
폴백까지 왕복 확인, claudebase 전체 테스트 **416 passed**. `harness_stats`가 grep하는
`graphify_guard.jsonl` 리터럴도 두 로그 줄 모두에 보존했다.

**되돌리려면**: `/tmp/mcp.before.json`(vault), `/tmp/gg.before.sh`(claudebase) — 세션 한정.
영구 복원은 git revert.

**실측 (2026-08-23).**

| 값 | 수 |
|:---|---:|
| `graphify-guard` 총 발화 | **2,112** |
| 그중 실제 주입(비억제) | **442** (나머지 1,671은 세션당 1회 래치로 억제) |
| 같은 창(49 트랜스크립트)의 graphify 사용 | **CLI `query` 3회, MCP 0회** |
| 넛지 1회 길이 | **397자** (README의 "397→0자"와 교차 일치) |
| 442회 주입 비용 | **175,474자 ≈ 5만 토큰 / 2일** |
| **준수율** | **0.68%** |

**판정 — 세 가설 중 하나는 기각됐고, 넷째가 나왔다.**

| 가설 | 판정 |
|:---|:---|
| 훅 유도 실패 | **기각.** MANDATORY 문구가 442회 명시 주입됐다 |
| 도구 부적합 (물을 게 없다) | **못 가름.** 가드는 Read·Grep·Bash 전부에 발화하므로 442회 중 실제로 그래프가 답할 수 있는 질문이 몇 개였는지는 이 로그가 모른다. 상한이 442라는 것만 안다 |
| 망각·무시 | **못 가름** — 위와 같은 이유로 부적합과 분리되지 않는다 |
| **(신규) MCP는 아무도 안 가리킨다** | **확정.** `.mcp.json`에 graphify 서버가 물려 있으나 유도 채널이 **0개**다 — 가드 문구는 CLI(`graphify query`/`explain`/`path`)를 가리키고, vault `CLAUDE.md` 표도 CLI(`graphify query`/`god-nodes`)를 가리킨다. 표의 `query_graph_tool`은 **CRG 것**이다. `.claude/rules/code-review-graph.md:135`가 MCP 층을 "**No** — offers a choice, nothing more"라고 이미 적어 뒀다 |

**그래서 "MCP 조회 0회"는 "안 쓴다"가 아니라 "아무도 안 가리킨다"이다.** 이 구분이 조치를
바꾼다 — 도구를 지울 근거가 아니라 **배선을 지울 근거**다. graphify MCP 서버는 매 세션
프로세스로 뜨고 툴 9개를 툴 리스트에 얹는데 30일간 라우팅도 사용도 0이다.

**부적합 vs 망각을 실제로 가르려면** 442회 발화 각각이 무엇을 읽으려던 참이었는지를 알아야
한다. 지금 로그 레코드는 `ts`·`hook`·`suppressed` 세 필드뿐이라 그 정보가 없다 —
**발화 시 대상 경로를 1필드 추가하면 다음 창에서 갈린다.** 그게 다음 측정이다.

**존치 쪽 비대칭을 판정에 반영한다**: 유지 비용은 디스크 203MB뿐이고, 폐기 후 되살리려면 LLM
재추출 5시간(58청크 × 5.3분, claude-cli 백엔드는 동시성 1로 강제)이 다시 든다.

---

#### T23: graphify에서 코드 확장자 제외 (T22가 존치로 끝날 때만)

**Files:**
- Modify: `~/ksm_Obsidian/.graphifyignore`

**근거 (2026-08-23 실측).** 현재 12,867노드의 분포는 `.md` 11,646 / `.py` 780 / `.pdf` 143 /
`.json` 140 / `.cpp` 85 / `.sh` 39. 코드 = **904노드 / 86파일**이고 전부 `0_Project/in_progress/albc/`
아래다. 그 **86파일은 CRG가 93파일로 이미 전부 갖고 있다**(교집합 86, graphify 단독 0) — 같은
트리를 두 엔진이 파싱해 두 인덱스에 넣고 있다.

`.graphifyignore`는 이미지 24종·`3_Archive/`·숨김 디렉터리·벤더 교재를 각각 실측 근거와 함께
명시적으로 뺐지만 **소스 확장자는 목록에 등장한 적이 없다** — 포함하기로 결정한 것이 아니라
제외 후보로 떠오른 적이 없다.

> **⚠️ 2026-08-24 실측 — 이 태스크의 전제가 08-23에 바뀌었다. 미착수 상태 그대로다.**
> `.graphifyignore`에 소스 확장자 **0건**, `.graphify/`·`graphify-out/` 둘 다 남아 있다.
> 그런데 **graphify MCP 서버는 이 vault의 `.mcp.json`에서 빠졌다**(2026-08-23, 30일간 툴 호출
> 0회 — 라우팅하는 채널이 없었다. vault `CLAUDE.md` 참조). 그래서 중복 904노드는 이제 *MCP로
> 조회되지 않는* 그래프의 중복이다. 태스크가 무효는 아니지만 **가치가 내려갔고, 착수 전에
> "graphify를 이 vault에 유지할 것인가"가 먼저 갈려야 한다.** 그 결정 없이 Step 1만 하면
> 유지 여부와 무관한 편집이 된다.

- [ ] **Step 1: 앞으로 안 늘게 한다**

`.graphifyignore`에 `*.py`·`*.cpp`·`*.sh` 세 줄을 추가하고, 다른 항목들처럼 **왜 뺐는지 실측
근거를 주석으로 같이 적는다**(CRG 중복, 노드 수, 측정일).

- [ ] **Step 2: 이미 있는 904노드는 재빌드로 지우지 않는다**

`graph.json`은 캐시의 함수가 아니라 **누적물**이라 전체 재빌드가 프로즈 쪽을 잃을 수 있다
(2026-08-15 기록. **오늘 재검증하지 않았다** — 실행 전에 확인할 것). 안전한 경로는
`source_file`의 확장자로 해당 노드·링크만 걷어내는 스크립트다. 실행 전 `graph.json`을 복사해 둔다.

- [ ] **Step 3: 비용 정정을 기록에 남긴다**

저 904개 코드 노드는 **5시간에 들어가지 않는다** — tree-sitter 패스는 공짜·오프라인이다.
5시간이 든 것은 `.md` 11,646개와 `.pdf` 143개 쪽이다. 따라서 이 태스크는 **비용 절감이 아니라
중복 제거**이며, 그렇게 적어야 다음 사람이 "지우면 5시간 아낀다"로 오독하지 않는다.

---

### 0-C. 감사 후속 — 근거가 흔들린 조사 3건

**근거 문서**: [research/AUDIT-2026-08-23.md](research/AUDIT-2026-08-23.md) §A·§B·§C·§F·§G.

**왜 이 절이 필요한가.** 감사가 연 항목들은 Phase 3 표에 **주석으로만** 붙어 있다("2026-08-23
감사가 이 표의 다른 항목에 붙인 표시"). 주석은 "다시 정하라"를 적을 뿐 **정하는 사람을 지정하지
않는다.** Phase 3은 Task 4 데이터(08-25+)를 기다리므로, 그때 스텝 수준으로 펼치는 시점에는
흔들린 근거 위에서 펼치게 된다. 이 절은 그 전에 근거를 세우는 3건이다.

**범위는 사용자가 정했다** (2026-08-23): 감사 §5의 재조사 우선순위 5건 중 **1~3번만**. 4번
(ext-prompt / §D·§E → T13)과 5번(gap-omp / §H → T10·T11)은 이번 범위 밖이고 Phase 3 표의
주석으로 남는다.

**순위**: 0-A(사용자 지정 1순위) 다음. 0-B와는 독립이라 병렬 가능.

---

#### T24: oms↔omx figure 계약 (감사 §A)

**Files:**
- Modify: `~/oh-my-scholar/` — figure 조달 경로를 쓰는 스킬·에이전트 (Step 2에서 확정)
- Modify: 이 파일 Phase 3 표의 T12 완료 조건

**Interfaces:**
- Consumes: `omx plot`(cli.py:1933) · `omx promote-plots`(cli.py:1944)
- Produces: T12가 "`report-parse`로 컨텍스트를 읽는다"에서 "figure까지 조달한다"로 넓어진다

**선행 조건 없음. 재조사가 아니라 확인이다** — 답이 이미 양쪽 코드에 있고 `DESIGN.md` §4는
2026-08-23에 이미 5번째 결합 지점으로 갱신됐다.

> **2026-08-24 진행 상황.** Step 1·2 완료. **계획이 예상한 "계약만 이으면 된다"는 틀렸다** —
> Step 1의 실측이 `omx plot`을 논문 figure 생산기가 아니라 **triage 렌더러**로 확정했다(552×435,
> dpi 100, 축 라벨 없음). Step 2의 접점 결정은 확정됐고(oms가 omx 경로를 참조), **남은 것은 계약이
> 아니라 렌더 품질이다.** Step 3이 사용자 결정을 기다린다.

- [x] **Step 1: `plot`을 실제로 한 번 돌려 산출물을 본다** — 2026-08-24 실행. **예고된 분기가 발생했다**

돌렸다. 합성 곡선(1,500스텝 npz)을 임시 앵커에 넣고 `omx plot --format npz --series reward
--metric reward --view curve`. 산출은 **552 x 435 px, 29.6 KB**.

**논문 figure로 못 쓴다. 계약이 아니라 렌더 품질이 병목이다** — Step 1이 예고한 그 경우다.

| 결함 | 근거 | 왜 실격인가 |
|:---|:---|:---|
| 해상도 552×435, dpi 100 고정 | `reduce/plot.py:14` `_DPI = 100` | IEEE 단컬럼 3.5 in 배치 시 **유효 158 dpi**. 그래프(line art) 요구 대역 300~600 dpi에 못 미친다 (정확한 하한은 RA-L 저자 키트로 확인 필요) |
| 축 라벨 없음 | `line_plot`에 `set_xlabel`·`set_ylabel` 호출 자체가 없다 | x축이 step인지 iteration인지 그림만 봐선 모른다 |
| 제목이 그림 안에 | `cli.py:412` `title=f"{metric} ({view})"` | 논문은 캡션이 제목을 진다 — 중복 |
| 범례가 원시 시리즈 키 | `line_plot(x, {args.series: y}, ...)` | `reward` 같은 내부 키가 그대로 노출 |
| 벡터 출력 없음 | `_save`가 `savefig(dpi=100)` PNG 고정 | PDF·EPS 경로가 없다. dpi 플래그도 없다 |

**이건 결함이 아니라 설계다.** `plot.py` 도크스트링이 명시한다 — *"Design 5: cap width so a
vision-read PNG stays small"*. `omx plot`은 **Claude가 눈으로 읽는 triage 렌더러**이지 논문 figure
생산기가 아니다. `max_px=2576` 상한도 축소만 하고 확대는 안 한다.

**그리고 `promote-plots`는 재렌더하지 않는다** — `reduce/promote.py`가 `os.replace`로 **같은 파일을
옮긴다**. 오늘 이 배선을 그대로 이으면 논문에 그 552×435 PNG가 그대로 들어간다.

- [x] **Step 2: 두 승격 규약의 접점을 정한다** — 2026-08-24. **후자 확정: oms가 omx 경로를 참조한다**

| 쪽 | 규약 | 근거 |
|:---|:---|:---|
| oms | 생성 figure = *중간산출*, `.oms/<slug>/gen-image/` | `references/output-layout.md:332-333` |
| omx | scratch → permanent 승격 (`--output-root`·`--run-id`·`--analysis-id`·`--referenced`) | `cli.py:1944-1955` |

계획은 "후자를 기본값으로 **검토**하라"였다. 검토했고 **후자로 확정한다.** 소유권 논거는 그대로
서고, 그 위에 전자를 적극적으로 기각하는 근거 둘이 실측으로 나왔다:

1. **`gen-image/`는 oms가 지우는 디렉터리다.** 살아 있는 언급이 딱 둘인데 — `scholar-init`이
   **만들고**(`skill-bodies/scholar-init/SKILL.md:69`), `scholar-pilot`이 T18 종료 정리에서
   **지운다**(`skill-bodies/scholar-pilot/SKILL.md:69` — `renders/`·`gen-image/`·`tmp/`를 정리
   대상으로 집계). **쓰는 코드도 읽는 코드도 없다.** 여기로 승격하면 논문 figure가 파이프라인
   종료와 함께 쓸려나간다.
2. **`os.replace`는 같은 파일시스템 안에서만 원자적이다**(`promote.py` 주석 명시). `--output-root`를
   임의의 oms 트리로 겨누면 크로스 파일시스템 실패 모드가 새로 생긴다.

**구조적으로는 둘 다 가능했다** — `OmxPaths` 도크스트링이 *"The permanent output tree (output_root)
is passed per-getter … never derived here"*라 `--output-root`에 어떤 경로든 넣을 수 있다. 그래서
이건 능력 문제가 아니라 순전히 소유권 결정이었고, 위 둘이 그 결정을 닫는다.

**부수 확인 — 감사 §A가 코드 수준에서 재확인됐다.** oms에는 figure를 그리는 코드가 **없다**
(`matplotlib`·`pgfplots`·`tikz` 단어가 oms 전체에서 0건). 그리고 oms의 살아 있는 스킬·에이전트 중
`omx`를 언급하는 것도 **0건** — 문서 2건뿐이다(`references/omc-backport-analysis.md`,
`docs/2026-07-11-oms-advancement-plan.md`).

- [x] **Step 3: drafter의 막다른 길을 잇는다** — **프로젝트 층 완료(2026-08-24), oms 층은 릴리스 승인 대기.** 결정은 아래 갈림길 표 다음 블록

원안: `~/oh-my-scholar/agents/scholar-drafter.md:79`가 "needs figure"를 `fixable_by_llm=false`로
사람에게 넘기니, 그 자리에 omx 경로를 안내하는 분기를 넣는다 — "문장 몇 줄".

**Step 1이 이걸 막았다.** 오늘 그 분기를 넣으면 drafter가 158 dpi·축 라벨 없는 PNG를 논문
figure로 안내하게 된다. 막다른 길을 **틀린 길로** 바꾸는 셈이다.

**갈림길 (사용자 결정)**:

| 안 | 내용 | 비용 | 남는 것 |
|:---|:---|:---|:---|
| (a) omx에 논문 렌더 옵션 신설 | `plot`에 `--dpi`·`--xlabel`·`--ylabel`·`--no-title`·`--ext pdf` | omx-core 코드 변경 + om* 릴리스 사이클 | 감사 §A가 연 문제가 닫힌다 |
| (b) 계약만 잇고 렌더는 사람 몫 | drafter가 "곡선 **데이터**는 omx에 있다"까지만 안내 | 문장 몇 줄 | figure는 여전히 사람이 만든다 — 절반만 닫힌다 |
| (c) 보류 | Step 1·2 실측만 기록하고 배선은 안 한다 | 0 | 다음 세션이 같은 측정을 다시 한다 |

~~**(a)를 권한다.**~~ 결함 5개 중 넷(라벨·제목·범례·확장자)은 `line_plot` 시그니처에 인자를 더하는
일이고, dpi는 `_DPI` 상수 하나다. 다만 **om* 저장소 편집은 이 vault 밖이라 사용자 승인 대상이고,
배포물이라 릴리스 규약(버전 bump + CHANGELOG)을 탄다.**

**결정 (2026-08-24): (a)·(b)·(c) 셋 다 아니다 — 넷째 안이 나왔다.**
이 표가 못 본 사실이 있었다. **논문 규격 렌더러가 이미 존재한다** — 컨테이너
`/workspace/constrained-albc/tools/paper_figures.py`(26,653 B, 08-23 17:55 신설). SSH 실측:

| T24가 센 결함 | `omx plot` | `paper_figures.py` |
|:---|:---|:---|
| 해상도 | dpi 100 고정 | `savefig.dpi 300` (`:68`) |
| 벡터 출력 | 없음 | **PDF 동시 출력** + `pdf.fonttype 42` 폰트 임베드 (`:69`, `:150-154`) |
| 축 라벨 | 호출 없음 | 전 figure `set_xlabel`·`set_ylabel` (`:223`, `:319`, `:500`) |
| 폭 | 무관 | `figsize (3.45, 2.4)` IEEE 단컬럼 (`:70`) |
| 서체 | 기본값 | serif Times, 본문 8 pt · 범례 7 pt (`:57-64`) |

**다섯 결함 전부 이미 해결돼 있다.** 그러므로 (a)는 신설이 아니라 *더 나은 것의 재구현*이고,
(b)의 "figure는 여전히 사람이 만든다"도 **틀린 전제**다 — 이미 자동화돼 있고 위치만 다르다.
갈림길 표가 이 사실을 못 본 이유는 후보를 `omx` 안에서만 셌기 때문이다.

**그래서 배선은 두 층으로 갈린다** — 이 경로는 컨테이너·프로젝트 고유인데
`~/oh-my-scholar/`는 **배포 저장소**라 머신 경로를 담을 수 없다
(`[[feedback_distributed_repo_no_machine_paths]]`):

| 층 | 무엇 | 상태 |
|:---|:---|:---|
| 프로젝트 (vault) | 구체 경로 + 규격 실측 + "figure가 필요할 때의 순서" 3단계 | **완료** — `.omp/wiki/paper-work-split.md` §2026-08-24 |
| oms (배포) | "프로젝트에 figure 렌더러가 있는지 먼저 찾아라"는 **일반 규칙**만 | **완료 — 병렬 세션이 oms 0.15.1 로 컷했다** (`42fbd6d`) |

**⚠️ 이 판정 도중 병렬 세션이 (a)를 완주했다 — 09:0x, 내 전제가 6분 만에 낡았다.**
omx **0.12.0** `feat(plot): paper-figure render options`(`22f4364`)가 `--dpi`·`--xlabel`·
`--ylabel`·`--no-title`·`--ext`를 실제로 넣었고, oms **0.15.0**(`b8000b5`)이 거기에 배선했다.
그 뒤 같은 세션이 **0.15.1**(`42fbd6d`)로 "프로젝트 렌더러를 먼저 찾아라"까지 넣었다 —
사용자 결정과 같은 결론에 독립적으로 도달했고, **배포 저장소에 머신 경로를 안 넣는다는 제약도
문서에 명시**했다. 즉 두 층 다 닫혔고 내가 더 쓸 것이 없다.

**단 (a)가 T24 목록이 세지 않은 구멍 둘을 남겼다** (2026-08-24 실측, `reduce/plot.py` grep):

| 미해결 | 증거 | 왜 문제인가 |
|:---|:---|:---|
| `figsize` 설정 없음 | `plot.py`에 `figsize` 0건 → matplotlib 기본 6.4 in | IEEE 단컬럼 3.45 in 배치 시 **1.85배 축소** — 라벨 실효 크기가 뭉갠다. dpi를 올려도 안 풀린다 |
| `pdf.fonttype` 설정 없음 | 같은 grep 0건 → 기본 **Type 3** | 저널이 거부하는 임베드 형식. `paper_figures.py:69`가 `42`를 쓰는 이유다 |

**그래서 "논문 규격"의 정의가 5항목이 아니라 7항목이었다.** T24의 결함 목록이 관측 가능한 것
(해상도·라벨·제목·범례·확장자)만 세고 **배치 폭과 폰트 임베드를 안 셌다** — 둘 다 그림을
열어봐서는 안 보이고 조판에 넣어야 드러난다. `omx plot`의 산출은 여전히
**"쓸 만한 triage"이지 "저널 제출용"이 아니다.** 이 프로젝트에서 `paper_figures.py`를
정본으로 두는 판단은 (a)가 나온 뒤에도 유효하다.

---

> ### 🔴 병렬 세션 충돌 — 같은 질문에 상반된 사용자 결정이 기록됐다 (2026-08-24 저녁)
>
> **위 블록은 "(a)를 기각했다 (2026-08-24 사용자 결정)"라고 적었다. 같은 날 다른 세션에서
> 같은 질문을 `AskUserQuestion`으로 물었고, 답은 "(a) omx에 렌더 옵션 신설 (권장)"이었다.**
> 그 세션은 답을 받은 대로 실행해 **이미 배포까지 마쳤다**(아래). 두 기록 중 어느 쪽이 사용자의
> 최종 뜻인지는 **이 문서가 정할 수 없다 — 사용자가 정해야 한다.**
>
> **다만 실행된 결과 자체는 위 프로젝트층 판정과 충돌하지 않는다.** 아래 §"합쳐진 형태" 참조.

#### (a) 실행 기록 — 배포 완료 (2026-08-24)

| 저장소 | 버전 | 커밋 | 검증 |
|:---|:---|:---|:---|
| oh-my-experiments | 0.11.2 → **0.12.0** | `22f4364` + `v0.12.0` | 1,075 passed / 2 skipped, ruff clean |
| oh-my-scholar | 0.14.0 → **0.15.0 → 0.15.1** | `b8000b5`·`42fbd6d` + 태그 2개 | 632 passed / 1 skipped |
| oh-my-heroacademia (카드) | omx·oms 각각 | `4a572b1`·`37485fc`·`da02e26` | 194 passed |

`omx plot`에 `--dpi`·`--xlabel`·`--ylabel`·`--no-title`·`--ext` 추가. **기본값은 전부 기존 triage
렌더와 동일**이라 현행 호출은 무변경이다. 실측 552×435 → **1715×1298**(IEEE 단컬럼 3.5 in 기준
158 → **490 dpi**), 축 라벨 있음, 그림 안 제목 없음, `--ext pdf`로 벡터.

함정 하나를 코드 주석과 테스트로 박았다: `_save`의 폭 상한은 **요청 dpi가 아니라 기준 dpi로**
재야 한다 — 요청 dpi로 재면 올린 배수만큼 inch가 줄어 **같은 픽셀 수를 돌려주는**, 성공을 보고하고
아무것도 안 하는 플래그가 된다(`test_line_plot_dpi_scales_pixels_not_inches`).

#### 합쳐진 형태 — 두 판정은 층이 다르다

프로젝트층 판정("`paper_figures.py`가 정본, `omx plot`을 논문 figure에 쓰지 마라")은 **옳고 그대로
선다.** 배포층에는 그것과 어긋나지 않는 폴백이 필요할 뿐이다 — `~/oh-my-scholar/`는 배포물이라
`/workspace/constrained-albc/...`를 담을 수 없고(`[[feedback_distributed_repo_no_machine_paths]]`),
**자기 렌더러가 없는 프로젝트**도 oms를 쓴다.

그래서 oms 0.15.0의 "omx로 조달하라"는 **0.15.1에서 순서를 뒤집어 고쳤다**:

1. **프로젝트 소유 렌더러를 먼저 찾는다** — 있으면 그 파일에 함수를 **추가**하고 두 번째 렌더러를
   만들지 않는다(프로젝트층 규칙과 동일).
2. **없을 때만** `omx plot` 폴백, 반드시 논문 플래그와 함께.
3. 어느 쪽이든 `.tex`는 **그 렌더러의 permanent 경로**를 참조한다. `gen-image/`로 복사 금지.

구체 경로는 `.omp/wiki/paper-work-split.md`가 소유하고 oms는 "찾아라"만 갖는다 — 위 표의 2층
분리 그대로다.

#### 릴리스 컷에서 배운 것 두 개

- **버전 SSOT는 4개가 아니라 5개다 — `git tag`가 다섯째다.** `test_version_sync.py`가
  `latest tag ∈ {plugin, 직전 릴리스}`를 강제하는데, oms는 **v0.9.0 이후 태그가 없었다**(0.10~0.14
  전부 미태그). 태그를 붙여 통과시켰다: oms `v0.15.0`·`v0.15.1`, omx `v0.12.0`.
- **`pytest -q | tail -3`은 종료코드를 삼킨다.** 파이프의 종료코드는 `tail`의 것이라 `&&` 체인이
  실패를 못 보고 그대로 push했다 — 2건 실패 상태로 나갔고 다음 명령에서야 발견했다. 즉시
  태그로 고쳐 632 passed를 확인했지만, **테스트를 게이트로 쓰려면 파이프 없이 종료코드를 봐라**
  (`[[machine_gateguard_wired]]`가 같은 함정을 이미 적어 뒀다).

- [x] **Step 4: T12 완료 조건을 갱신한다** — **완료 (2026-08-24).**

현재: "oms 세션에서 `omx report-parse`로 실험 컨텍스트를 읽는다. `.bib` 오염 0"

(a)면 원안대로 "그리고 실험 곡선 figure 1건이 omx 산출에서 논문 트리로 도달한다"를 쓴다.
(b)면 "figure 조달"이 아니라 **"곡선 데이터 조달"**로 좁혀 써야 한다. **결정 전에 쓰면 틀린 완료
조건이 박힌다** — 계획서가 스스로 못 지킬 약속을 하는 형태다.

**실제로는 (a)도 (b)도 아니었으므로 셋째 형태로 썼다.** figure 조달을 **조건에서 빼고 왜
빼는지를 같은 칸에 적었다** — omx는 곡선 데이터의 출처이지 렌더러가 아니고, 논문 figure는
프로젝트 소유 렌더러가 만든다. Phase 3 표 T12 행에 반영. **"넓어진다"고 적었던 Step 0의
`Produces`(이 절 위)는 그래서 틀렸다** — T12는 넓어진 게 아니라 경계가 그어졌다.

**citation 안전 불변식은 그대로다** — figure는 인용이 아니므로 `.bib` 가드
(`hooks/scholar_cite_guard.py`)와 충돌하지 않는다. 다만 **figure caption에 omx report를 인용처럼
쓰지 않는지**는 여기서 같이 확인한다.

---

#### T25: `ext-loop-engineering` 재조사 (감사 §B·§C)

**Files:**
- Create: `research/ext-loop-engineering-v2.md`
- 원본 `research/ext-loop-engineering.md`는 **고치지 않는다** (감사와 같은 규약 — 기록이 핵심)

**미흡 2건이 같은 문서에 겹쳐 있다.** 하나는 자기모순, 하나는 어휘 누락이다.

> **2026-08-24 완료. 산출: [`research/ext-loop-engineering-v2.md`](research/ext-loop-engineering-v2.md).**
> Step 1~3 전부 실행했다. **§B는 원본 주장의 정확한 반대로 나왔다** — `exp-loop`는 "활동 증거까지
> 갖춘 유일한 루프"가 아니라 **5/5 중 활동이 0인 쪽**이다(양쪽 실행에서 불변). **§C도 성립** —
> 5속성이 StateM 실패 모드 4개 중 1.5개만 덮는다. Step 3 판정은 **(b) 완결 아님 + 공백 G1~G3
> 명명**이고, 그것을 태스크로 올릴지는 **사용자 결정**(0-C 범위 밖).

- [x] **Step 1: §0 헤드라인의 근거를 교체한다 (§B)** — 완료. `omp-garden`만이 "지금 도는 루프"다(활동 7건, 최신 08-20). `scholar-revise`도 5/5·활동 7건이지만 최신이 08-06으로 2주 정지

§0 L14가 "exp-loop는 활동 증거까지 갖춘 유일한 루프"라 했는데 같은 문서 §3 L103이
`exp-loop … 0 (none found)`이다. 08-23 재실측도 0이었다. 대체 후보는 **`omp-garden`·
`scholar-revise`** — 둘이 `loop-contract.md` 5속성을 실제로 갖는지
`~/claudebase/runtime/hooks/loop_lint.py`로 재확인한 뒤에 쓴다. **확인 전에 후보를 결론으로 쓰지
마라.** `ultragoal` 3/5 부재는 재현됐으므로 그 부분은 그대로 둔다.

- [x] **Step 2: `harness` 축 문헌을 읽는다 (§C)** — 완료. 3편 다 읽었고 **5속성이 StateM 실패 모드 4개 중 1.5개만 덮는다**. "조기 종료"는 우리 cap·escalation과 **방향이 반대**(그건 과잉 반복을 끊는 장치다). 부수 발견: AutoDesign이 **paper-to-poster + PosterBench**라 **T26 Step 2의 문헌 후보와 겹친다** — T26은 이 논문부터 읽어라

"루프 엔지니어링"은 2026년 브랜드 어휘다. 학계가 같은 문제를 부르는 이름은 **harness**이고,
그 축으로 검색하면 조사일 이전 공개인데 미인용된 논문이 나온다:

| ID | 왜 이 축인가 |
|:---|:---|
| 2608.15089 (StateM) | harness scaling으로 Terminal-Bench 2.1 95.3%. 실패 모드로 "stop prematurely"를 **직접 지목** |
| 2608.13560 (AutoDesign) | 감사가 미인용으로 확인. 내용 대조는 이 스텝에서 |
| 2608.16798 (ClawGym II) | 감사가 미인용으로 확인. 내용 대조는 이 스텝에서 |

읽고 나서 **우리 `loop-contract.md` 5속성이 문헌의 실패 모드를 덮는지** 대조한다. 요구 #1의 첫
문장("claude cli 작동 체계 고도화")이 곧 harness scaling의 주제다.

- [x] **Step 3: 요구 #1의 "조사로 완결"이 성립하는지 판정한다** — **(b) 완결 아님.** README 표의 해당 행을 같은 작업 안에서 고쳤다. 공백 G1(조기 종료 방지 부재)·G2(교훈 재활성화 경로 부재)·G3(정지 전이가 산문뿐인 플러그인 2개)을 명명했고, **사용자가 2026-08-24에 "G1~G3 전부" 태스크화를 승인했다 → `0-D`의 T27·T28·T29**

`README.md`의 "요구 5건의 처리" 표가 요구 #1을 **"조사로 완결"**이라 적었다. §C가 그것을 흔들었다.
Step 2 이후 (a) 완결로 유지 (b) 새 실행 항목 신설 (c) "완결 아님"으로 명시하고 닫기 중 하나를
고르고, **README 표의 해당 행을 같은 작업 안에서 고친다** — 본문만 고치고 요약을 남기지 않는다.

---

#### T26: `gap-omd` 재조사 → T8 재판정 (감사 §F·§G)

**Files:**
- Create: `research/gap-omd-v2.md`
- Modify: 이 파일 Phase 3 표의 T8 행 (신설/배선 판정 결과)

**T8은 지금 "신설"로 적혀 있는데 그 전제가 안 확인됐다.**

> **2026-08-24 완료. 산출: [`research/gap-omd-v2.md`](research/gap-omd-v2.md).**
> Step 1~3 전부 실행했다. **전제가 틀렸다** — T8이 요구한 넷 중 셋(style-spec·색 팔레트·verify
> 배선)이 이미 있다. `doc-verifier.md:46`이 `ppteval.md`를 읽고 Design/Coherence를 검사한다.
> 없는 것은 **여백·정렬 강제값**과 **판정의 결정론성**뿐이다. **재판정: (c) 측정 먼저.**

- [x] **Step 1: omd가 이미 가진 것을 센다 (§F — 미검증 전제)** — 완료. `ppteval.md`가 스스로 "doc-verifier uses the Coherence/Design axes as part of its summative pass/fail gate"라 적고 있다. 구체값도 일부 있다(KO → Apple SD Gothic Neo, 종횡비 16:9·4:3·1:1, KO 제목 ≤ 50자). style-spec은 `docs-standardize`가 유도하고 `references/themes/`의 10개 프리셋(hex + 폰트 페어링)이 폴백

`gap-omd.md`에 `doc-inspector`·`ppteval` 단어가 **0회**다. 그런데 실물이 있다:
`~/oh-my-docs/agents/doc-inspector.md:44` — "Design (consistent fonts/colors, overflow, clipping,
legibility)", 그리고 `~/oh-my-docs/references/rubrics/ppteval.md`. **DEC-5의 3축 중 둘째(디자인
품질)에 방법이 없다고 본 것이 사실인지부터 확인한다.**

- [x] **Step 2: 외부 문헌을 읽는다 (§G — 문헌 0건)** — 완료. 계획이 지목한 **AeSlides(2604.22840)·SlidesGen-Bench(2601.09487) 둘 다 실재**하고, 여기에 PresentBench(2603.07244)·AutoDesign(2608.13560)을 더했다. **AeSlides의 검증 가능 지표 네 개가 우리 `ppteval.md` Design 문장과 그대로 대응한다**(종횡비·요소 충돌·여백·시각적 불균형). 그 초록이 우리 현재 방식을 이름 붙여 친다 — *"heavy visual reflection, which incurs high inference cost yet yields limited gains"*

`gap-omd.md`는 외부 문헌 인용이 0건이다. 2026년 슬라이드 생성·미학 레이아웃 문헌 중 §4.3이
"사람 몫"이라 닫은 지점을 정면으로 다루는 것들(AeSlides·SlidesGen-Bench 계열)을 본다. 이 문헌군은
미학을 **측정 가능한 보상**으로 다루므로 **DEC-1(측정 먼저)과 정합한다** — 그 정합이 T8을
"신설"에서 "측정+배선"으로 옮길 수 있다.

- [x] **Step 3: T8을 재판정하고 Phase 3 표를 고친다** — **판정 (c) 측정 먼저.** Phase 3 표의 T8 행과 감사 주석 표의 T8 행을 같은 작업에서 고쳤다

(a)는 §1이 막는다 — 없는 것을 만드는 게 아니다. (b)도 정확하지 않다 — 배선은 이미 돼 있고
(`doc-verifier.md:46`), 남은 공백은 **여백·정렬 강제값 부재**와 **판정의 비결정성**이라 배선으로
강등하면 그 둘이 시야에서 사라진다(감사 §F가 지적한 것과 같은 형태의 소실). **(c)** — 문헌이
계산 가능성을 보였지만 그 지표가 **우리 덱에서 사람 판단과 상관하는지는 재본 적이 없다.**

---

### 0-D. loop-contract 공백 3건 — T25가 열고 사용자가 승인한 것

**근거 문서**: [research/ext-loop-engineering-v2.md](research/ext-loop-engineering-v2.md) §3.
**승인**: 2026-08-24, "G1~G3 전부". T25 Step 3의 선택지 (b)("새 실행 항목 신설")가 발동한 결과다.

**왜 셋인가.** `loop-contract.md`의 5속성이 StateM(2608.15089)이 명명한 장기 과제 실패 모드 4개 중
**1.5개만** 덮는다. 나머지가 이 셋이다. 각 태스크의 완료 조건은 *계약 문서에 항목이 생기는 것*이
아니라 **린터가 그 항목을 실제로 재는 것**이다 — 재지 않는 계약 항목은 산문이고, 이 프로젝트의
한 문장 결론이 정확히 "대부분이 계측되지 않는다"였다.

**순위**: 0-C 다음. 셋은 서로 독립이라 병렬 가능하고, **T27이 가장 근거가 뚜렷하다**.

> **✅ 0-D 종결 (2026-08-24). claudebase `c1500d7` · `293fd7b` · `7fb6a51`, 전부 push. 416 passed.**
> 계약은 **5속성 → 7속성**, 린터 표는 **5열 → 8열**이 됐다.
>
> **셋 중 둘이 계획의 전제를 뒤집었다** — 그리고 뒤집힌 방향이 매번 달랐다:
>
> | | 계획의 예상 | 실측 |
> |:---|:---|:---|
> | T27 | 신설일 수도, 승격일 수도 | **반반** — 잔여 수는 승격, **분모는 아무도 없었다**(신설) |
> | T28 | 자산은 있는데 계약이 안 센다 | **그대로 맞음.** 자산 8종, 읽는 루프 **0/9** |
> | T29 | `docs-revise`가 결함 | **반대.** 둘 다 결함 아님 — 훅 신설 **0건**, 산출은 오도한 경고문 수정 |
>
> **세 태스크가 같은 것을 세 번 가르쳤다: 산문 grep의 `--`는 "시스템에 없다"가 아니다.**
> check 4(Ralph 컴파일 JS) → `denom`(omx `loop.py`) → `lesson`(위임 스킬 `exp-design`).
> 셋 다 계약 문서에 캐비엇으로 박았다 — 다음 독자가 다시 발견하지 않도록.

---

#### T27: 조기 종료 방지 (G1)

**Files:** Modify `~/claudebase/docs/loop-contract.md` · `~/claudebase/runtime/hooks/loop_lint.py`

**우리 계약은 방향이 반대다.** `cap`+`escalation`은 *과잉 반복*을 끊는 장치다(`autopilot` 근거 라인:
"QA cycles repeat up to 5 times; if the same error persists 3 times, stop"). StateM이 지목한 것은
그 반대편 — **끝나지 않았는데 스스로 끝났다고 선언하는 것**이고, 5속성에 그걸 막는 항목이 없다.

> **2026-08-24 완료 — claudebase `c1500d7`, push. 416 passed (exit 0).**
> **계획의 "신설일 수 있다"는 예상이 절반만 맞았다.** 속성 자체는 이미 두 루프가 갖고 있었고
> (승격), **둘째 절반은 아무도 안 갖고 있었다**(신설). 그 둘째 절반이 이 태스크의 실제 산출이다.
>
> **6번째 속성 = 외부화된 완료 판정.** 잔여 수를 **상태에서 읽어** 종료하고(판단하지 않고),
> **분모를 그 옆에 기록한다.** 두 절반이 다 필요한 이유: `garden-state.json`의 `found: 0`은
> *깨끗한 트리*와 *한 번도 안 본 sweep*을 못 가른다. omx 도크스트링이 이미 그 함정을 이름 붙였고
> (*"'none open' is indistinguishable from 'nobody ever filed one' unless the denominator travels
> with it"*), 실측 사례까지 들고 있다 — **540 페이지 중 0개가 status를 들고 있었고, 그 라운드의
> 모든 launch가 한 번도 무언가를 담은 적 없는 게이트를 통과했다.**
>
> **린터 첫 실행(9개 루프): `resid` 3건, `denom` 0건.** 그리고 그 두 숫자가 각각 함정이다 —
> `resid` 3건 중 **둘은 오탐**(`docs-revise`·`scholar-revise`가 *포기할 때 출력하는 정지 리포트*의
> "remaining defects"에 걸렸다. 판정이 아니라 보고다). `denom` 0건도 **"없다"가 아니다** — omx는
> 분모를 갖고 있고 그게 `omx_core/loop.py`에 있어 스킬 산문 grep이 못 본다. 둘 다 계약 문서에
> 적었다.
>
> **테스트가 내 변경을 잡았다.** 3건 실패 — `KNOWN_GOOD`·shim `BODY` 픽스처가 "모든 체크 통과"를
> 단정하는데 새 속성 이전에 쓰인 것이었다. 픽스처에 두 속성을 넣어 416 passed.
> ⚠️ 이번엔 **파이프 없이** 종료코드를 봤다(오늘 오전 oms 릴리스에서 `| tail`이 실패를 삼켰다).

- [x] **Step 1: 실제로 일어나는지부터 잰다.** — 완료. 9개 루프 중 **2개만** 종료를 상태로 외부화하고(`omp-garden` "read from state, not judged" · omx `open_leads`), **1개만** 분모를 든다(omx `wiki_coverage {pages, with_status}`). `docs-revise`의 "remaining defects"는 정지 리포트 전용이라 판정이 아니다. 계약 항목을 먼저 만들지 마라 — DEC-1이다. 기존
  루프 산출물(`.omp/garden-state.json`의 sweeps, omx ledger)에서 **"완료 선언 시점의 미해결 항목
  수"**를 뽑을 수 있는지 본다. 못 뽑으면 그 자체가 첫 발견이고 계측이 선행 과제가 된다.
- [x] **Step 2: 계약 6번째 속성을 정의한다.** — 완료. `docs/loop-contract.md`가 **"Six properties"**가 됐고, 요약 층 4곳(머리말·"Why these five"→"Why the first five"·"all five checks"·"scores all five")을 같은 커밋에서 고쳤다. 이름 후보는 *완료 조건의 외부화* — 종료를 루프 자신이
  아니라 **상태 파일에 적힌 잔여 항목 수**로 판정하게 하는 것. `omp-garden`이 이미 그렇게 한다
  ("stop condition은 '새 발견 없음'이고, **판단이 아니라 상태에서 읽는다**" — `SKILL.md:54`).
  **그러니 신설이 아니라 이미 있는 것의 승격일 수 있다** — 확인 전에 신설로 쓰지 마라.
- [x] **Step 3: `loop_lint.py`에 열을 추가한다.** — 완료. 표는 6열이 아니라 **7열**이 됐다 — `cap`/`escal`을 쪼갠 것과 같은 이유로 `resid`/`denom`을 쪼갰다(반쪽 실패가 흔한 실패다). 열이 없으면 계약 항목은
  안 재진다.

#### T28: 이전 실행의 교훈 재활성화 (G2)

**Files:** Modify `~/claudebase/docs/loop-contract.md` (+ 린터, T27과 같은 이유)

StateM의 *"fail to reactivate lessons from earlier executions"*에 해당하는 계약 항목이 없다.

**그런데 자산은 이미 여럿 있다** — `.omp/learned.md`, omx `wiki`, omd `.omd/wiki/convention/`
(2층 상승·병합), auto-memory. **문제는 부재가 아니라 계약이 그것들을 안 세는 것**이다.

> **2026-08-24 완료 — claudebase `293fd7b`, push. 416 passed (exit 0).**
> **계획의 진단이 맞았고, 숫자가 예상보다 깨끗했다: 자산은 도처에 있고 루프는 0개가 읽는다.**
>
> **자산 실측(이 머신).** vault `.omp/learned.md` 2건(둘 다 이미 닫힘 — 0001 superseded,
> 0002 rejected) · vault `.omp/wiki/` 5 · workspace `.omd/wiki/` 11 · `.oms/wiki/` 18 ·
> `.omc/wiki/` 183 · omx `registry/findings/` 9 · auto-memory 256(153+103). **9개 루프 중 0개**가
> 이 중 무엇도 읽는다고 적어 두지 않았다.
>
> **읽기는 루프 *한 칸 아래*에 있다.** `exp-loop`는 `exp-analyze`·`exp-design`에 위임하고,
> 스택에서 이 속성의 가장 좋은 구현은 `exp-design`의 두 줄이다 — `omx wiki query … --category
> decision` / `--category pattern`, 그리고 **왜 그 두 카테고리인지가 적혀 있다**(decision=과거에
> 확정된 원인, pattern=이 증상이 취하는 형태).
>
> **속성 7 = 교훈 재활성화.** 읽기 동사를 요구한다 — **쓰기는 재활성화가 아니다.** `exp-loop`
> Step 6(`wiki capture-session`·`lint`·`gc`)은 쓰기 쪽이라 의도적으로 안 걸리게 했다.
>
> **린터 첫 실행: `lesson` 1/9.** 그리고 그 1건도 강한 쪽이 아니다 — `exp-loop`의 backlog
> reconcile(`wiki list --status needs-experiment`)에 걸린 것이고, 진짜 구현인 `exp-design`은
> 린터가 아예 안 여는 파일이다(루프가 아니므로). **위임 추적은 기각했다** — 인계가 산문
> ("Delegate to `exp-design`")이라 이름 정규식은 사각지대를 오탐으로 바꿀 뿐이다.
>
> ⚠️ **이걸로 같은 비대칭이 3번째다** — check 4(Ralph 컴파일 JS) · `denom`(omx `loop.py`) ·
> `lesson`(위임 스킬). 산문 grep의 `--`는 언제나 **"스킬에 안 적혔다"**이지 "시스템에 없다"가 아니다.

- [x] **Step 1: 자산을 세고 어느 루프가 실제로 읽는지 확인한다.** — 완료. 자산 8종 실측, **루프 0/9**. 있다는 것과 루프가 읽는다는 것은
  다르다 — `[[feedback_resolved_knowledge_not_in_launch_path]]`가 같은 실패다(wiki에 답이 있는데
  발사 스크립트에 없어 다시 밟았다).
- [x] **Step 2: 계약 항목으로 올릴지 판정한다.** — **올렸다.** 근거는 셋: (1) 0/9는 가설이 아니라 실측, (2) 작동하는 예시(`exp-design`)가 있으니 발명이 아니라 승격(속성 6과 같은 형태), (3) 안 읽어서 치른 비용이 기록돼 있다(cuDNN preamble 재답습, 18.9 s/iter). 판정이 "이미 충분하다"면 그것도 결론이고 G2는
  닫힌다. **닫는 것도 결과다.**

#### T29: 정지 전이가 산문뿐인 플러그인 2건 (G3)

**Files:** 판정에 따라 `~/oh-my-docs/` 또는 `~/oh-my-project/` 훅 (배포 저장소 — 릴리스 규약)

`loop_lint.py` [B] 표 실측(2026-08-24): **`oh-my-docs`·`oh-my-project`에 차단 가능한 Stop 훅이
없다.** 그 둘이 이고 있는 루프(`docs-revise`·`omp-garden`)의 정지 전이는 산문이다.

> **2026-08-24 완료 — claudebase `7fb6a51`, push. 416 passed (exit 0). 훅은 하나도 안 만들었다.**
> **계획의 전제가 틀렸다: 둘 다 결함이 아니었고, 아닌 이유가 서로 다르다.** 계획은 `docs-revise`를
> 결함으로 지목했는데(verify PASS까지 고치니 정지가 실질이다), 그게 정확히 반대였다.
>
> | 플러그인 | 차단 훅이 없는 이유 |
> |:---|:---|
> | `oh-my-docs` | **D6 — 플러그인 전체 결정**이고 릴리스 계획 3판(v0.1.0·v0.3.0·v0.4.0)에 적혀 있다: *"모든 신규 훅은 stdlib-only·fail-open·advisory — `decision: block` 절대 금지."* 훅 6개 전부 지키고 있다(실측: `"decision": "block"` 0건). 그리고 **같은 전이를 계측은 한다** — `docs_verify_emit`이 빌드마다 `.verify-pending` 센티널을 걸고 `docs_stop_guard`가 Stop에서 미해소분을 띄운다. 도크스트링에 이유까지 있다: *"deferring verify is legitimate."* |
> | `oh-my-project` | `omp-garden`은 **report-only이고 omp는 스케줄러를 안 싣는다** — *"arming it is the human's call."* 한 sweep = 한 호출이라 **세션 안에 붙잡을 반복 자체가 없다.** 여기에 차단 훅을 달면 **사람의 턴**을 붙잡아 아무도 요청 안 한 sweep을 강요하게 된다. |
>
> **판정을 읽히게 만드는 대조군은 `scholar-revise`다** — `docs-revise`의 구조적 쌍둥이인데
> (*"the paper-edition of ralph"*) **차단한다**: 살아 있는 `revise-<slug>.json` 마커에 스코프를
> 걸고, 면제 6종 + 지속 `stop_blocks` 상한을 둔다. **같은 루프 모양, 반대 결정, 양쪽 다 기록됨.**
> 계약이 요구하는 것은 속성을 *가리킬 수 있는 것*이지 같은 방식으로 구현하는 것이 아니다.
>
> **그래서 산출은 훅이 아니라 경고문 수정이다.** [B]의 미가드 목록이 *"stop transition is prose
> only"*라고 단정하고 있었고, **그 문구가 바로 이 계획을 오도해 훅 2개를 예약하게 했다.**
> 이제 "사실이지 판정이 아니다 — 부재·컴파일·기록된 결정 셋 다 가능"으로 바꿨다.
>
> **덤으로 낡은 행 1개 닫았다** — Standing 표의 "`docs-revise`, `scholar-revise` | 라운드 이력이
> 대화에 산다"에서 `scholar-revise`는 이제 `.oms/state/revise-<slug>.json`에 있다.

- [x] **Step 1: 결함인지부터 가른다.** — 완료. **둘 다 결함 아님**, 이유는 서로 다름(위 표). `omp-garden`은 스스로 **"Report-only"**라 선언한다 —
  보고만 하는 루프에 차단 훅이 없는 것은 결함이 아니라 설계일 수 있다. `docs-revise`는 다르다
  (verify PASS까지 고치는 루프라 정지가 실질이다). **둘을 한 판정으로 묶지 마라.** ← 묶지 않은 게
  정확히 답을 갈랐다. 다만 갈린 방향이 계획의 예상과 반대였다.
- [x] **Step 2: 결함으로 판정된 쪽만 훅을 신설한다.** — **해당 없음. 신설 0건.** 배포 저장소라 버전 bump + CHANGELOG +
  카드 + **`git tag`**까지 5개 SSOT를 타야 했을 텐데, 탈 일이 없었다. 대신 오도한 경고문을
  claudebase에서 고쳤다(같은 5-SSOT 규약은 om* 배포물에만 걸리고 claudebase는 해당 없음).

---

## Phase 1 — 계측 (DEC-1·DEC-2)

~~**선행 게이트 없음. Task 1은 지금 바로 시작할 수 있다.** 이것이 이 계획의 진입점이다.~~
**→ 더 이상 진입점이 아니다. Task 1·2·3·5는 2026-08-22에 끝났다** (아래 배너).

> **⚠️ 2026-08-24 체크박스 드리프트 정정 — 25개를 실측으로 체크했다.**
> **본문만 뒤처져 있었다.** README는 "Phase 1·2 완료"라고 맞게 적혀 있는데 PLAN 본문의
> 체크박스가 전부 미체크라, **이 어긋남이 이미 한 번 "Task 1이 다음 진입점"이라는 오판을
> 만들었다**(README 28행이 그 기록). 병렬 세션 `ksm-obsidian-51`이 발견해 넘겼다.
>
> **넘겨받은 보고를 액면대로 안 받고 재측정했고, 두 군데가 달랐다:**
> - 보고: *"파이썬 훅 15개 배선(loop_lint.py만 제외)"* → **Task 2의 대상은 6개**이고 그 6개가
>   정확히 배선돼 있다. 15는 다른 것을 센 수다. 태스크 범위로 재면 6/6 완료.
> - 보고: *"Task 5·6도 같은 상태일 수 있는데 확인 안 했다"* → **Task 5는 실행까지 끝났고**
>   (repeats=3, 양팔 0.333 tie) Task 6도 Step 5만 남았다.
>
> **그리고 내 첫 측정이 Task 3을 0/6으로 잘못 읽었다** — `hooklog` 문자열로 grep 했는데 셸 훅은
> 파이썬 헬퍼를 안 쓰고 `printf`로 `.omc/logs/*.jsonl`에 직접 append 한다(Task 3의 Interfaces에
> 그 이유가 적혀 있다: PreToolUse라 인터프리터 기동 비용). **패턴을 계획서에 맞춰 다시 재니 6/6.**
> `[[feedback_absent_from_scan_is_not_absent]]`를 쓴 그 세션에서 바로 다시 밟았다.

### Task 1: 훅 발화 로깅 공유 헬퍼

> **✅ 완료 (2026-08-22, claudebase `12ae91f`).** 실측 2026-08-24:
> `runtime/hooks/hooklog.py`(1,812 B) + `tests/hooks/test_hooklog.py`(1,858 B) 둘 다 존재.

**Files:**
- Create: `~/claudebase/runtime/hooks/hooklog.py`
- Test: `~/claudebase/tests/hooks/test_hooklog.py`

**Interfaces:**
- Produces: `hooklog.fire(stem, cwd, session_id=None, **fields) -> None` — Task 2가 이 시그니처를 그대로 쓴다. 반환값 없음, 예외 없음.
- `stem`은 확장자를 **포함한** 파일명(`"session_gate.jsonl"`). 호출자 소스에 리터럴을 남기기 위한 것이며 Global Constraints의 grep 제약이 이유다.

- [x] **Step 1: 실패하는 테스트를 쓴다**

```python
# ~/claudebase/tests/hooks/test_hooklog.py
"""hooklog.fire 의 계약: append 한다, 절대 안 죽는다."""
import importlib.util
import json
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[2] / "runtime" / "hooks" / "hooklog.py"


def _load():
    spec = importlib.util.spec_from_file_location("hooklog", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_appends_one_json_line(tmp_path):
    hooklog = _load()
    hooklog.fire("demo.jsonl", str(tmp_path), session_id="s1", decision="allow")
    out = tmp_path / ".omc" / "logs" / "demo.jsonl"
    rows = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["session_id"] == "s1"
    assert rows[0]["decision"] == "allow"
    assert "ts" in rows[0]


def test_appends_not_overwrites(tmp_path):
    hooklog = _load()
    hooklog.fire("demo.jsonl", str(tmp_path))
    hooklog.fire("demo.jsonl", str(tmp_path))
    out = tmp_path / ".omc" / "logs" / "demo.jsonl"
    assert len(out.read_text(encoding="utf-8").splitlines()) == 2


def test_never_raises_on_unwritable_cwd(tmp_path):
    hooklog = _load()
    blocked = tmp_path / "file-not-dir"
    blocked.write_text("x", encoding="utf-8")
    hooklog.fire("demo.jsonl", str(blocked))  # 예외가 새면 이 테스트가 실패한다


def test_never_raises_on_none_cwd():
    hooklog = _load()
    hooklog.fire("demo.jsonl", None)


def test_non_serializable_field_does_not_raise(tmp_path):
    hooklog = _load()
    hooklog.fire("demo.jsonl", str(tmp_path), obj=object())
```

- [x] **Step 2: 실패를 확인한다**

```bash
cd ~/claudebase && python3.12 -m pytest tests/hooks/test_hooklog.py -v
```
기대: 5건 전부 실패 — `FileNotFoundError` 또는 `No module named 'hooklog'`.

- [x] **Step 3: 최소 구현을 쓴다**

```python
# ~/claudebase/runtime/hooks/hooklog.py
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
```

- [x] **Step 4: 통과를 확인한다**

```bash
cd ~/claudebase && python3.12 -m pytest tests/hooks/test_hooklog.py -v
```
기대: 5 passed.

- [x] **Step 5: 커밋**

```bash
cd ~/claudebase
git add runtime/hooks/hooklog.py tests/hooks/test_hooklog.py
git commit -m "feat(hooks): add hooklog.fire so silent hooks can be measured"
```

---

### Task 2: 파이썬 훅 6개에 발화 로깅 배선

> **✅ 완료 (2026-08-22, claudebase `bdd781d`).** 실측 2026-08-24: 지정된 6개 파일이 전부
> `hooklog`를 import·호출한다(`session-gate` · `session-title-3words` · `fix_surrogate` ·
> `graphify_scope_filter` · `merge-project-hook` · `omc-reference-emit`). 발화도 확인 —
> vault `.omc/logs/`에 `session_gate.jsonl` 3,796줄 · `graphify_scope_filter.jsonl` 929줄 ·
> `omc_reference_emit.jsonl` 75줄.

**Files:**
- Modify: `~/claudebase/runtime/hooks/session-gate.py`, `session-title-3words.py`, `fix_surrogate.py`, `graphify_scope_filter.py`, `merge-project-hook.py`, `omc-reference-emit.py`
- Test: `~/claudebase/tests/hooks/test_hook_logging_wired.py` (신규)

**Interfaces:**
- Consumes: Task 1의 `hooklog.fire(stem, cwd, session_id=None, **fields)`
- 훅은 `runtime/hooks/`에 나란히 있으므로 `sys.path`에 자기 디렉터리를 넣고 import 한다. 절대경로 금지(Global Constraints).

- [x] **Step 1: 배선 여부를 강제하는 테스트를 쓴다**

```python
# ~/claudebase/tests/hooks/test_hook_logging_wired.py
"""배선된 훅은 전부 자기 로그 파일명 리터럴을 소스에 갖는다.

harness_stats.logging_hooks() 가 grep 으로 찾는 그 리터럴이다 — 이 테스트가
없으면 헬퍼로 리팩터링하다 리터럴이 사라져도 아무도 모른다."""
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[2] / "runtime" / "hooks"

WIRED_PY = [
    "session-gate.py",
    "session-title-3words.py",
    "fix_surrogate.py",
    "graphify_scope_filter.py",
    "merge-project-hook.py",
    "omc-reference-emit.py",
]


@pytest.mark.parametrize("name", WIRED_PY)
def test_hook_carries_its_log_literal(name):
    text = (HOOKS / name).read_text(encoding="utf-8")
    stem = name.replace(".py", "").replace("-", "_") + ".jsonl"
    assert stem in text, f"{name} 에 {stem} 리터럴이 없다 — harness_stats 가 못 본다"


@pytest.mark.parametrize("name", WIRED_PY)
def test_hook_imports_hooklog(name):
    text = (HOOKS / name).read_text(encoding="utf-8")
    assert "hooklog" in text
```

- [x] **Step 2: 실패를 확인한다**

```bash
cd ~/claudebase && python3.12 -m pytest tests/hooks/test_hook_logging_wired.py -v
```
기대: 12건 전부 실패(6파일 × 2검사).
*(2026-08-24 실측: 이 테스트는 그 뒤 자라 **18 passed**다. 12는 착수 시점 기대치이지 현재 값이
아니다 — 재현할 때 12를 못 보고 "다른 파일"이라 여기지 마라. `test_hooklog.py`는 5로 그대로.)*

- [x] **Step 3: 각 훅에 import 와 호출을 넣는다**

각 파일 상단 import 블록 뒤에 넣는다. 6개 파일 모두 동일하다.

```python
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent))
import hooklog  # noqa: E402
```

그리고 각 훅이 **실제로 일을 한 지점**(판정을 내리거나 컨텍스트를 주입한 직후)에 한 줄을
넣는다. `stem`은 파일명의 `-`를 `_`로 바꾼 것이다.

```python
# session-gate.py — 게이트 판정 직후
hooklog.fire("session_gate.jsonl", cwd, session_id, decision=decision)

# session-title-3words.py — 제목을 만든 직후
hooklog.fire("session_title_3words.jsonl", cwd, session_id, titled=bool(title))

# fix_surrogate.py — 복구를 시도한 직후
hooklog.fire("fix_surrogate.jsonl", cwd, session_id, repaired=n_repaired)

# graphify_scope_filter.py — 필터 판정 직후
hooklog.fire("graphify_scope_filter.jsonl", cwd, session_id, filtered=bool(filtered))

# merge-project-hook.py — 병합을 마친 직후
hooklog.fire("merge_project_hook.jsonl", cwd, session_id, merged=n_merged)

# omc-reference-emit.py — 주입 직후
hooklog.fire("omc_reference_emit.jsonl", cwd, session_id, emitted_chars=len(payload))
```

**주의**: 각 훅의 지역 변수명이 위와 다를 수 있다. 그 파일을 먼저 읽고 실제 이름에 맞춰라.
`cwd`·`session_id`가 없는 훅이면 `None`을 넘겨도 된다 — 헬퍼가 처리한다.

- [x] **Step 4: 통과를 확인한다**

```bash
cd ~/claudebase && python3.12 -m pytest tests/hooks/ -v
```
기대: 새 테스트 12 passed, 기존 훅 테스트 회귀 없음.

- [x] **Step 5: 실제 발화를 눈으로 확인한다**

```bash
cd ~/claudebase && rm -f .omc/logs/session_gate.jsonl
# 이 저장소에서 Claude Code 세션을 한 번 열고 아무 툴이나 호출한 뒤:
cat .omc/logs/session_gate.jsonl
```
기대: `{"ts": "...", "session_id": "...", "decision": "..."}` 형태의 줄이 1개 이상.
**0줄이면 배선이 아니라 훅 자체가 안 돌고 있다는 뜻이다** — 그건 별개의 발견이니 기록하라.

> **🛑 2026-08-24 — 이 블록을 지금 그대로 실행하지 마라. 두 군데가 틀렸다.**
> **(1) `rm -f`가 Task 4의 데이터를 지운다.** 훅은 **세션의 cwd별로** 쓰므로 실물은 claudebase가
> 아니라 **vault** `.omc/logs/`에 쌓여 있다 — `session_gate.jsonl` 3,797줄,
> `graphify_guard.jsonl` 3,349줄, `tokensave_guard.jsonl` 3,513줄 외 14개. Task 4가 아직
> 그 발화를 세야 한다(08-25 측정창). **claudebase 쪽은 1~6줄짜리 6개뿐이다.**
> **(2) 그래서 claudebase에서 `cat` 하면 0줄이 나오는데, 그건 미배선이 아니다.** 계획이 지정한
> 경로가 애초에 실물 경로가 아니었을 뿐이다. 볼 곳은 vault다:
> `wc -l ~/ksm_Obsidian/.omc/logs/session_gate.jsonl`.
> 검증 자체는 이미 끝났다 — 지울 필요 없이 줄 수만 세면 된다.

- [x] **Step 6: 커밋**

```bash
cd ~/claudebase
git add runtime/hooks/*.py tests/hooks/test_hook_logging_wired.py
git commit -m "feat(hooks): wire firing logs into the six silent Python hooks"
```

---

### Task 3: 셸 훅 6개에 발화 로깅 배선

> **✅ 완료 (2026-08-22, claudebase `fe04bf7`).** 실측 2026-08-24: 6개 전부 `.omc/logs/<name>.jsonl`
> 리터럴을 들고 있다. 발화 확인 — `graphify_guard.jsonl` 3,346줄 · `tokensave_guard.jsonl` 3,512줄 ·
> `graph_refresh.jsonl` 201줄 · `hud_ensure.jsonl` 74줄 · `graphify_debt.jsonl` 5줄.
> **`graph_offer.jsonl`만 파일이 없다** — 배선은 됐고 아직 한 번도 발화 안 했다는 뜻이다.
> 배선 실패가 아니므로 태스크는 완료이고, **Task 4가 셀 때 이 0을 "미배선"으로 읽지 마라.**
>
> 테스트: `test_hooklog.py` + `test_hook_logging_wired.py` **23 passed (exit 0)**.

**Files:**
- Modify: `~/claudebase/runtime/hooks/graph-offer.sh`, `graph-refresh.sh`, `graphify-debt.sh`, `graphify-guard.sh`, `hud-ensure.sh`, `tokensave-guard.sh`
- Test: `~/claudebase/tests/hooks/test_hook_logging_wired.py` (Task 2 파일에 추가)

**Interfaces:**
- Consumes: 없음. 파이썬 헬퍼를 셸에서 부르면 인터프리터 기동 비용이 발화마다 붙고 이 훅들은 PreToolUse라 가장 자주 돈다. 그래서 `printf` 3줄로 인라인 처리한다.

- [x] **Step 1: 셸 훅용 테스트를 추가한다**

```python
# test_hook_logging_wired.py 끝에 추가
WIRED_SH = [
    "graph-offer.sh",
    "graph-refresh.sh",
    "graphify-debt.sh",
    "graphify-guard.sh",
    "hud-ensure.sh",
    "tokensave-guard.sh",
]


@pytest.mark.parametrize("name", WIRED_SH)
def test_shell_hook_carries_its_log_literal(name):
    text = (HOOKS / name).read_text(encoding="utf-8")
    stem = name.replace(".sh", "").replace("-", "_") + ".jsonl"
    assert stem in text, f"{name} 에 {stem} 리터럴이 없다"
```

- [x] **Step 2: 실패를 확인한다**

```bash
cd ~/claudebase && python3.12 -m pytest tests/hooks/test_hook_logging_wired.py -k shell -v
```
기대: 6 failed.

- [x] **Step 3: 각 셸 훅에 append 3줄을 넣는다**

훅이 자기 일을 마친 지점(exit 직전)에 넣는다. `graphify-guard.sh` 예:

```bash
# 발화 기록 — harness_stats 가 이 파일명 리터럴을 grep 한다. 실패해도 무시.
_log="${CLAUDE_PROJECT_DIR:-$PWD}/.omc/logs/graphify_guard.jsonl"
mkdir -p "$(dirname "$_log")" 2>/dev/null \
  && printf '{"ts":"%s","hook":"graphify-guard"}\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$_log" 2>/dev/null || true
```

나머지 5개는 `_log` 경로의 파일명과 `"hook"` 값만 바꿔 동일하게 넣는다:
`graph_offer.jsonl`/`graph-offer` · `graph_refresh.jsonl`/`graph-refresh` ·
`graphify_debt.jsonl`/`graphify-debt` · `hud_ensure.jsonl`/`hud-ensure` ·
`tokensave_guard.jsonl`/`tokensave-guard`.

**주의**: `CLAUDE_PROJECT_DIR`은 훅에 export되지 않는다는 기록이 있다
(`.claude/rules/code-review-graph.md`의 `graph-refresh.sh` 항목). `$PWD` 폴백이 그래서 있다.
어느 쪽이 실제로 잡히는지는 Step 5에서 눈으로 확인한다.

- [x] **Step 4: 통과를 확인한다**

```bash
cd ~/claudebase && python3.12 -m pytest tests/hooks/ -v && bash -n runtime/hooks/*.sh
```
기대: 테스트 전부 통과, `bash -n` 문법 오류 0.

- [x] **Step 5: 실제 발화를 눈으로 확인한다**

```bash
cd ~/claudebase && rm -f .omc/logs/graphify_guard.jsonl
# 세션에서 Grep 을 한 번 호출한 뒤:
cat .omc/logs/graphify_guard.jsonl
```
기대: 최소 1줄. 파일이 엉뚱한 디렉터리에 생겼으면 `CLAUDE_PROJECT_DIR` 폴백이 이유다 —
그 경로를 기록하라.

> **🛑 2026-08-24 — Task 2 Step 5와 같은 이유로 실행 금지.** `rm -f`가 Task 4의 데이터를 지운다.
> 그리고 위 "엉뚱한 디렉터리" 가설이 **바로 실제로 일어난 일이다** — `CLAUDE_PROJECT_DIR`이 훅에
> export 안 돼 `$PWD` 폴백이 잡혔고, 그래서 로그는 **세션의 cwd(=vault)** 에 있다.
> 검증은 `wc -l ~/ksm_Obsidian/.omc/logs/graphify_guard.jsonl`로 끝난다 (3,349줄).

- [x] **Step 6: 커밋**

```bash
cd ~/claudebase
git add runtime/hooks/*.sh tests/hooks/test_hook_logging_wired.py
git commit -m "feat(hooks): wire firing logs into the six silent shell hooks"
```

---

### Task 4: 계측 리포트 — 12개가 non_logging 에서 빠졌는가

> **✅ 완료 (2026-08-25). 리포트: `docs/harness/measurements/2026-08-25-baseline.md`.**
> Step 2·3·4 실행. Step 1(배선 전 기준선)은 `baseline-pre-wiring.txt`가 이 머신에 없어 포기 —
> 12훅 전부 배선 후 계측이라 판정엔 지장 없다(리포트 §5-3).
>
> **결론이 기대와 반대다: 삭제 후보 0건.** 0건으로 나온 셋(`session-title-3words`·
> `fix_surrogate`·`graph-offer`)은 `hooklog.fire()`가 **조기 반환 뒤, 훅이 실제로 뭔가를
> 바꾼 지점**에 있어서 갈래 (A)가 아니라 **(C)**다 — "안 돌았다"가 아니라 "돌았는데 할 일이
> 없었다"이다. 그래서 이 배선에서는 *발화 0 = 삭제 후보*라는 이 태스크의 전제가 성립하지
> 않는다. 지우려면 계측을 먼저 고쳐라(fire를 진입 지점으로 + `acted` 필드).
>
> 부수 확정: 12번 `tokensave-guard.sh`는 발화 4,594건인데 `85e3616`이 삭제했다 —
> **발화 수는 유지·삭제 어느 쪽 근거도 아니다.** 그리고 `Create:` 경로의
> `0_Project/in_progress/harness/`는 08-24 이관으로 **존재하지 않는다**(Step 4 명령도 무효).
> PLAN 범위 밖 신규 훅 `compact-guard.py`가 계측기 없이 라이브다 — 다음 배선 1순위.

**Files:**
- Modify: 없음(기존 `harness_stats.py`를 실행만 한다)
- Create: `0_Project/in_progress/harness/measurements/<실행일>-baseline.md`

**Interfaces:**
- Consumes: Task 2·3이 만든 `.omc/logs/*.jsonl`
- Produces: 기준선 리포트 — Phase 3의 삭제·통합 판정이 이 문서를 인용한다.

> **⚠️ 2026-08-24 — 착수 전에 이 다섯을 반영하라. 넷은 gitignored scratch에만 있던 것을 끌어온 것이다.**
> 출처는 `.superpowers/sdd/PLAN/progress.md`인데 **그 파일은 gitignored**라 다른 머신에서 안 열린다
> (`[[feedback_tracked_doc_cites_gitignored_path]]`). 그래서 여기 옮겨 적는다.
>
> **① 아래 Step 1·2의 명령은 `--root`가 없어 틀렸다.** 기본값이 cwd 하나뿐이라
> (`harness_stats.py:346`, `args.root or ["."]`) `~/claudebase`에서 그냥 돌리면 **거기 로그 6개
> (각 1~6줄)만 센다.** 실물은 세션 cwd별로 갈려 vault에 3,797·3,513·3,349줄로 쌓여 있다.
> 그대로 돌리면 거의 모든 훅이 "발화 0"으로 나와 **삭제 후보로 오판된다** — 이 태스크가 막으려는
> 바로 그 실패다. 도구 자신의 도크스트링(`:9`)이 옳은 형태를 들고 있다:
> `python3 runtime/hooks/harness_stats.py --root ~/ksm_Obsidian --root .` — **활성 프로젝트마다 하나씩.**
>
> **② Step 1(배선 전 기준선)은 이미 확보돼 있다.** `git stash`로 되돌릴 필요 없다 — 배선 전에
> 받아 둔 `baseline-pre-wiring.txt`(1,240 B, 08-22 14:27)가 `.superpowers/sdd/PLAN/`에 있다.
> **다만 gitignored라 이 리포트에 인용하려면 값을 `measurements/`로 옮겨 적어야 한다.**
>
> **③ claudebase 쪽 로그 3종은 실사용 발화가 아니다 — 세기 전에 빼라.**
> `merge_project_hook`(42)·`omc_reference_emit`(14)은 **pytest 산물**이다(테스트가 `cwd=None`으로
> 훅을 돌려 `fire()`가 프로세스 cwd=저장소 루트로 폴백. ts 군집이 pytest 실행과 정확히 일치).
> `demo.jsonl`(9)도 합성이다. 초기 보고가 이 42/14를 진짜 발화로 읽었다가 최종 리뷰가 정정했다.
>
> **④ PLAN의 12훅 ≠ `harness_stats` 표 2b의 12훅.** 리포트에 이 주석을 반드시 달아라 —
> 없으면 *"12개가 non_logging에서 빠졌다"*가 거짓으로 읽힌다. 2b에는 `quality-gate.py`·`run.js`·
> `suggest-compact.js`가 들어 있는데 `runtime/skills/*/hooks/` 소속이라 PLAN 범위 밖이고 배선 후에도
> 2b에 남는다. 반대로 PLAN의 `graphify_scope_filter`·`merge-project-hook`·`omc-reference-emit`은
> `settings.json`의 `wired_hooks()`에 없어(체인·인스톨러·프로젝트 머지로 간접 호출) **표 2에 아예
> 안 나온다** — 이 셋의 측정은 표 1의 로그 카운트로 잡힌다.
>
> **⑤ 0건이라고 다 같은 0이 아니다.** 08-22 라이브 확인 시점에 미관측이던 다섯 중
> `session_gate`·`session_title_3words`·`fix_surrogate`는 그 뒤 vault에서 발화했고
> **`graph_offer`·`graphify_debt`만 여전히 희소하다**(`graphify_debt` 5줄, `graph_offer` 파일 없음).
> Step 3의 (A)/(B)/(C) 갈래는 이 차이를 반영해야 한다.

- [ ] **Step 1: 배선 전 상태를 먼저 기록한다** — **포기: 산출물이 이 머신에 없다(리포트 §5-3)**

```bash
cd ~/claudebase && python3 runtime/hooks/harness_stats.py
```
Task 2·3 이전에 돌렸다면 `non_logging` 목록에 12개가 그대로 있다. 그게 before다.
이미 배선했다면 `git stash`로 잠시 되돌려 한 번 받아 두어라.

- [x] **Step 2: 최소 3일, 최소 10세션 지난 뒤 다시 돌린다**

```bash
cd ~/claudebase && python3 runtime/hooks/harness_stats.py
```
**기다리는 이유**: 하루치로는 "안 도는 훅"과 "그날 조건이 안 맞은 훅"을 못 가른다.
`detect_malformed_toolcall.py`가 표본 5건으로 판정 불가였던 것과 같은 함정이다.

- [x] **Step 3: 세 갈래로 분류해 기록한다**

각 훅을 DESIGN.md §1의 갈래로 적는다.

| 훅 | 발화 수 | 갈래 | 판정 |
|:---|---:|:---|:---|
| (12개 전부 채운다) | | (A)/(B)/(C) | 유지 / 삭제후보 / 관찰연장 |

**(A) 갈래이면서 0건인 훅만 삭제 후보다.** (C)로 판정되면 "이 머신·이 vault만 봤다"를
반드시 같이 적어라.

- [x] **Step 4: 커밋**

```bash
cd ~/ksm_Obsidian
git add 0_Project/in_progress/harness/measurements/
git commit -m "[프로젝트] 하네스 훅 발화 기준선 측정" && git push
```

---

### Task 5: claudebase 22훅 A/B 실험 정의 (DEC-2)

> **✅ 완료 — 정의를 넘어 실행까지 (2026-08-22, claudebase `ea38563` + 후속 3건).** 실측 2026-08-24:
> `eval/experiments/claudebase-hooks-ab.yaml`(11,137 B) 존재, `eval/README.md:47`에 실험 표 행 등재,
> 결과는 같은 파일 §204 *"What the hooks arm measured, 2026-08-22 (repeats=3)"*.
>
> **결과: 양팔 0.333 동점, 분산 0 — 진짜 null.** Step 4의 "n=1은 답이 아니다" 경고를 지켜
> repeats=3으로 돌렸다. 후속 커밋 셋이 전부 교란 제거다: `2c99720`(플러그인 층을 양팔 동일하게),
> `8b1881f`(`enabledPlugins: {}`가 deep-merge no-op이라 처치군에서 omha 훅이 그대로 발화했다 —
> 프로브가 그 수정을 반증했고 머신별 false-map으로 교체), `9b171d8`(스칼라 교란·테스트 로그 오염).

**Files:**
- Create: `~/claudebase/eval/experiments/claudebase-hooks-ab.yaml`
- Modify: `~/claudebase/eval/README.md` (실험 표에 행 추가)

**Interfaces:**
- Consumes: 기존 `eval/tasks/*.yaml` 10종 — 새 태스크를 만들지 않는다.
- Produces: 실행 가능한 실험 정의. 실행 자체는 사람이 승인하고 돌린다(토큰 비용).

- [x] **Step 1: 기존 실험 정의를 읽고 그대로 따른다**

```bash
cd ~/claudebase/eval && cat experiments/harness-discipline.yaml
```
`setting_sources`가 어디에 어떻게 적히는지 확인하라. **이 한 필드가 이번 실험의 전부다** —
기존 실험이 `["project"]`라서 `~/.claude/CLAUDE.md`와 claudebase 훅 22개가 양쪽 팔 모두에서
빠졌고, 그래서 22훅은 한 번도 측정된 적이 없다(`eval/README.md:179-183`).

- [x] **Step 2: 두 팔을 정의한다**

`harness-discipline.yaml`을 복사해 `claudebase-hooks-ab.yaml`을 만들고, 두 팔의 차이를
**`setting_sources`만으로** 둔다.

- 대조군: `setting_sources: ["project"]` — 지금까지의 조건
- 처치군: `setting_sources: ["user", "project"]` — `~/.claude/CLAUDE.md` + 훅 22개 로드

플러그인 층은 **양쪽 동일하게** 둔다. 안 그러면 플러그인 효과와 훅 효과가 교란된다.
태스크는 `leaves_a_check.yaml`을 쓴다 — 유일하게 변별력이 확인된 계측기다(0.333 vs 1.000, 2회 재현).

- [x] **Step 3: 돈 안 드는 검증을 먼저 돌린다**

```bash
cd ~/claudebase/eval
export PATH="$HOME/.local/bin:$PATH"
eval "$(python3 scripts/plugin_env.py)"
coder-eval plan -e experiments/claudebase-hooks-ab.yaml tasks/leaves_a_check.yaml
```
기대: 오류 없이 계획 출력. `plugin_env.py` 줄은 **선택이 아니다** — 빼면 처치군이 빈 채로
돌아가 "하네스는 아무것도 안 한다"로 읽힌다(`eval/README.md`).

- [x] **Step 4: 실행은 사람 승인 후**

```bash
coder-eval run -e experiments/claudebase-hooks-ab.yaml tasks/leaves_a_check.yaml
```
**n=1은 답이 아니다.** 직전 사이클에서 n=1의 +0.333이 n=3에서 +0.222로 정정됐고
`scope_and_root_cause`의 1.000은 3회 반복에서 전부 0.667로 무너졌다. 최소 n=3.

- [x] **Step 5: 결과를 기록하고 커밋**

`eval/README.md`의 실험 표에 행을 추가하고, 결과는 Task 4의 measurements 폴더에 적는다.

```bash
cd ~/claudebase
git add eval/experiments/claudebase-hooks-ab.yaml eval/README.md
git commit -m "test(eval): A/B the 22 claudebase hooks that setting_sources excluded"
```

---

## Phase 2 — verified 제거

**Phase 1과 병렬로 진행 가능하다.** 셋 다 코드가 아니라 부산물이고 위험이 없다.

### Task 6: A1·A2·A3 정리 + likely 3건 확인

> **🟡 부분 완료 (2026-08-24 실측). Step 1·2·3·4 완료, Step 5·6은 열려 있다.**
>
> | Step | 상태 | 근거 |
> |:---|:---|:---|
> | 1 (A1 빈 디렉터리) | ✅ | `~/oh-my-project/references/wiki` 없음. **커밋은 없다** — untracked 였으므로 `git add -A`에 잡힐 게 없었다. 정상 |
> | 2 (A3 배지) | ✅ | `pyproject.toml:7 = "0.12.0"`, `README.md:5` 배지 = `0.12.0`. 일치 |
> | 3 (A2 흡수 배너) | ✅ | `HARNESS_UPGRADE_PLAN.md` 1행부터 배너 + M1 폐기. vault `77cb6943` |
> | 4 (X6 포인터) | ✅ | 계획 수립 세션에서 선행 완료(원래부터 `[x]`) |
> | 5 (likely 3건) | ✅ | 아래 판정표. 셋 다 답이 나왔고 제거가 필요했던 건 M5 하나 |
> | 6 (커밋) | ✅ | vault `77cb6943` ✅ · omx 배지는 `22f4364`(0.12.0 릴리스)에 실려 나갔다 — 전용 커밋은 없지만 내용은 push 됨 · omp·M5는 커밋할 게 없었다(둘 다 untracked 디렉터리 제거) |
>
> **→ Task 6 종결.** 제거 실적은 M5 빈 디렉터리 1건뿐이고, 나머지 둘은 "이미 됐다"(B1)와
> "T14가 할 일"(B3)로 갈렸다. **3건 중 2건이 제거 대상이 아니었다는 것이 이 Step의 결론이다.**
>
> **Step 5 판정 완료 (2026-08-24). 세 건의 답이 전부 다르고, 그중 하나는 내 첫 답의 정정이다.**
>
> | | 판정 | 근거 |
> |:---|:---|:---|
> | **B1** omx `cards/` | **이미 해결됨 — 할 일 없음** | omx 커밋 `f46f942` *"chore: drop the unconsumed local cards/ directory (routing reads its own repo only)"*. tracked 0건. 0.11.2 캐시에 빈 디렉터리(`.gitkeep`만)가 남아 있을 뿐이고, omha의 `CARDS_DIR`은 `Path(__file__).parent.parent / "cards"`로 **자기 저장소에 하드코딩**돼 있어 애초에 남의 `cards/`를 안 본다 (`hooks/cross_lane_emit.py:25`) |
> | **B3** `ultrapilot` | **소비 안 됨 — 제거 가능. T14로 넘긴다** | omc 스킬 41개 중 `ultrapilot` **없음**. omha `cards/omc.json:32`의 `skills` 배열이 유일하게 이름을 들고 있고, 그 배열의 나머지 9개는 전부 실재한다 — **딱 하나 매달린 이름** |
> | **M5** `learning-output-style-inline` | **죽음 — 제거함** | `~/.claude/plugins/data/`에 **0 B 빈 디렉터리**, 최종수정 2026-03-24(5개월 전), `installed_plugins.json`·`settings.json`·claudebase config 어디서도 참조 0건. `rmdir`로 제거(비어야만 성공하므로 데이터 손실 불가) |
>
> ⚠️ **B3는 같은 세션 안에서 내가 뒤집었다.** 처음엔 *"omc 캐시의 컴파일된 `dist/config/loader.js`에
> 나오니 소비될 수 있다 → 제거 금지"*라고 적었다. **틀렸다.** 그 두 참조를 열어보니
> `loader.js:515`·`1175`는 **예약어 blocklist**다 — autopilot stage profile 이름으로 쓰지 못하게
> 막는 JSON Schema `not.enum`이고, 같은 목록에 `swarm`·`pipeline`·`qa`·`execution`처럼 **omc 스킬이
> 아닌 이름들이 같이 들어 있다.** 이름이 나온다는 것과 소비된다는 것은 다르다.
> `[[feedback_absent_from_scan_is_not_absent]]`의 거울상이다 — **부재를 부재로 못 읽는 것과 같은
> 크기로, 존재를 소비로 읽는 것도 틀린다.** grep 히트는 히트지 판정이 아니다.
>
> **T14(Phase 3)가 실제 제거를 맡는다** — `cards/omc.json`은 배포 저장소라 버전 bump + CHANGELOG +
> 카드 + `git tag` 5-SSOT를 탄다. Step 5의 몫은 "소비되지 않는다"를 확인하는 것까지였고, 끝났다.

**Files:**
- Delete: `~/oh-my-project/references/wiki/` (빈 디렉터리)
- Modify: `~/oh-my-experiments/README.md:5` (버전 배지)
- Modify: `~/ksm_Obsidian/2_Resource/lectures/claude_code_complete_master/HARNESS_UPGRADE_PLAN.md`
- Modify: `~/.claude/projects/-Users-kimseungmin-ksm-Obsidian/memory/project_harness_upgrade_plan.md` + `MEMORY.md`

- [x] **Step 1: A1 — 빈 디렉터리가 정말 비었는지 재확인 후 제거**

```bash
cd ~/oh-my-project
git ls-files references/wiki/ | wc -l    # 0 이어야 한다
find references/wiki -type f | wc -l     # 0 이어야 한다
rmdir references/wiki                    # 비어야만 성공한다 — rm -rf 쓰지 마라
```
`rmdir`이 실패하면 비어 있지 않다는 뜻이다. 그 경우 **멈추고 내용을 보고하라.**

- [x] **Step 2: A3 — omx 버전 배지 정정**

```bash
cd ~/oh-my-experiments
grep -n "^version" omx-core/pyproject.toml    # 실제 값 확인
```
`README.md:5`의 배지를 그 값으로 고친다. **pyproject.toml을 읽고 그 값을 쓴다** — 기억으로
`0.11.2`를 쓰지 마라. 그 사이 올라갔을 수 있다.

- [x] **Step 3: A2 — 선행 계획에 흡수 배너와 M1 폐기 표시**

`HARNESS_UPGRADE_PLAN.md` 맨 위에 넣는다.

```markdown
> **이 계획은 2026-08-22 에 흡수됐다.** 현행 SSOT 는
> `0_Project/in_progress/harness/{DESIGN,PLAN}.md`.
> **M1 항목은 폐기됐다** — "콜론형 99 건이 조용히 매칭 실패 중"이라는 주장이 실측으로
> 반박됐다(`:*` 는 공백형과 동등하며 "끝에서만 인식" 조건도 vault 99 건이 예외 0 건으로
> 전수 만족). 근거는 흡수 문서 §1 X5.
```

- [x] **Step 4: X6 — MEMORY.md 포인터 정정** *(2026-08-22 계획 수립 세션에서 선행 완료)*

`project_harness_upgrade_plan.md`의 본문과 frontmatter `description`, `MEMORY.md`의 해당
한 줄을 같은 편집에서 고쳤다. 틀린 포인터가 매 세션 오도하고 있어 계획 실행을 기다리지
않고 처리했다. 신규 메모리 2건(`project_harness_upgrade_2026_08_22`,
`machine_gcal_allday_offset_shifts_date`)도 색인에 등재됐다.
**남은 것은 이 Task 의 Step 3(선행 계획 파일 자체의 흡수 배너)이다.**

- [x] **Step 5: likely 3건 — 확인 한 단계씩**

```bash
# B1: omx cards/ 가 omha 라우팅에 소비되는가
grep -rn "cards" ~/oh-my-heroacademia/scripts/*.py | grep -i omx
# B3: omha cards/omc.json 의 ultrapilot 이 라우팅에 소비되는가
grep -rn "ultrapilot" ~/oh-my-heroacademia/ ~/.claude/plugins/cache/omc/
```
**소비되지 않는다는 것을 확인한 뒤에만** 제거한다. 확인 못 하면 그대로 두고 기록만 하라.
M5(learning-output-style)는 `~/.claude/plugins/data/learning-output-style-inline`의 잔존
여부를 확인한 뒤 판정한다.

- [x] **Step 6: 저장소별로 나눠 커밋**

```bash
cd ~/oh-my-project && git add -A && git commit -m "chore: drop the untracked empty references/wiki directory"
cd ~/oh-my-experiments && git add README.md && git commit -m "docs: correct the version badge to match pyproject"
cd ~/ksm_Obsidian && git add 2_Resource/ && git commit -m "[프로젝트] 선행 하네스 계획 흡수 배너 + M1 폐기 표시" && git push
```

---

## Phase 3 — 배선 (Phase 1 데이터 도착 후)

**여기부터는 태스크 수준으로만 정의한다.** 스텝 수준 상세를 지금 쓰지 않는 이유는 둘이다.
(1) DEC-1이 "측정 먼저"이고 삭제·통합 판정이 Task 4의 데이터에 달려 있다.
(2) D2·D3·D4·D7·D8 다섯 건이 사용자 결정 대기라 태스크 내용이 그 답에 따라 갈린다.
**Phase 1이 끝나면 이 절만 다시 writing-plans로 스텝 수준까지 펼친다.**

| # | 태스크 | 파일 | 완료 조건 | 선행 조건 |
|:--|:---|:---|:---|:---|
| T7 | omd 다이어그램 경로 배선 | `oh-my-docs/references/formats/pptx.md`·`docx.md`에 `## Diagrams` 절 | doc-planner가 "needs system diagram"을 낸 문서에서 doc-builder가 Mermaid MCP 결과를 `add_picture`로 삽입 | **D3** (스킬 규칙 예외 여부) |
| T8 | omd 디자인 품질 (DEC-5) | **측정 먼저** (T26 재판정 2026-08-24, `research/gap-omd-v2.md`) | ~~색 팔레트·여백·정렬이 style-spec에 강제값으로 존재하고 verify가 위반을 잡는다~~ → **셋 중 넷이 이미 있다.** 남은 것은 **여백·정렬 강제값**과 **판정의 결정론성**. 먼저 잰다: ① `doc-verifier` Design 판정의 재현성 ② AeSlides 4지표를 기계로 계산해 LLM 판정과 대조 ③ 여백·정렬 위반이 실제로 새는지. 셋 다 "문제 없음"이면 T8은 닫힌다 | 없음 |
| T9 | omd 영상 산출 장르 (DEC-5) | omd 신규 포맷 카드 | remotion 연동으로 영상 1건 산출·검증 | **입증 부담** — 새 장르라 "왜 배선으로 안 되는가"를 통과해야 한다 |
| T10 | omp workspace 재코드화 | `~/Desktop/workspace/.omp/` | `omp_version`이 설치판과 일치, secretary 스키마 존재 | 없음 |
| T11 | vault BRIEF 정체 해소 | `~/ksm_Obsidian/.omp/secretary/` | BRIEF가 현재 상태를 반영하거나 명시적으로 종료됨 | **D2** |
| T12 | oms↔omx 2a 계약 | oms 스킬에 Bash 호출 절 추가 | oms 세션에서 `omx report-parse`로 실험 컨텍스트를 읽는다. `.bib` 오염 0. **figure 조달은 이 조건에 안 들어간다**(2026-08-24 T24 결정) — omx는 곡선 *데이터*의 출처이고 렌더러가 아니다. 논문 figure는 프로젝트 소유 렌더러가 만들고 그 경로는 프로젝트 문서가 정한다 | 없음 |
| T13 | askuserquestion 로그 스키마 확장 | `askuserquestion_stats.py` | 질문·답변 텍스트가 로그에 남아 "과거 질문 참고"의 데이터가 생긴다 | 없음 |
| T14 | omha 카드 정리 | `oh-my-heroacademia/cards/omc.json` | 존재하지 않는 스킬명 0, 계약 미준수 루프 라우팅 재고. **선행 조건 충족됨 (2026-08-24, Task 6 Step 5)**: 매달린 이름은 **`ultrapilot` 딱 1개**다 — `:32`의 `skills` 배열 10개 중 나머지 9개는 omc에 실재하고, 유일한 다른 참조인 omc `dist/config/loader.js:515·1175`는 **예약어 blocklist**지 스킬 등록이 아니다. 배포 저장소라 제거는 5-SSOT(버전·CHANGELOG·카드·`pyproject`/README·`git tag`) | ~~Task 6 Step 5~~ → **충족** |
| ~~T15~~ | ~~shared_memory 게시판 컨벤션 (요구 #2)~~ → **Phase 0의 T17·T19가 흡수** | — | — | **재정의됨** (2026-08-23) |

**T15가 재정의된 이유** (2026-08-23). 이 태스크는 `proposal-N`/`rebuttal-N-of-M` key 규약으로
게시판을 신설하려 했는데, **그 규약이 겨냥하는 국면(에이전트 간 분담 협상)이 이 rig에서 관측
0건**이다 — 우리 세션쌍과 `.omc/paper-hub/` 둘 다에서. 미관측 국면을 위한 신설은 입증 부담이
너무 크다. 대신 실제로 관측된 것은 (a) 종료 조건 부재로 인한 교환 지속과 (b) 산출물이
gitignored라 세션 밖으로 안 나가는 문제이며, 그 둘을 **T17(프로토콜 문서)과 T19(3층 수명 분리)가
직접 다룬다.**

**안정성 계약은 T19로 이관됐다** — 공유 상태는 (a) 세션 스코프로 만료되고 (b) 사람이 읽을 수
있는 위치에 있으며 (c) 승인 게이트를 우회하는 채널로 쓰이지 않도록 쓰기 주체가 명시된다.
**이 셋이 없으면 T19 Step 4를 착수하지 않는다.**

**2026-08-23 감사가 이 표의 다른 항목에 붙인 표시** (출처: `research/AUDIT-2026-08-23.md` §8 —
어느 것도 태스크를 무효화하지 않고, 근거나 범위를 다시 정하라는 것이다):

| 태스크 | 감사가 지적한 것 | 누가 처리하나 |
|:---|:---|:---|
| T8 | ~~**신설인지 배선인지 재판정**하라~~ → **처리됨 (2026-08-24, T26)**: 둘 다 아니고 **(c) 측정 먼저**. `doc-verifier.md:46`이 이미 `ppteval.md`로 Design/Coherence를 검사한다 — 공백은 여백·정렬 강제값과 판정의 결정론성이다 | **T26** (0-C) — 완료 |
| T10 | 우선순위가 **4번째 `.omp/`(krit 0.2.1)를 안 본 채** 나왔다. 대상이 workspace만인지 krit도인지 정하라 | 미배정 — 감사 §5 5순위, 이번 범위 밖 |
| T11 | 프레이밍 문제 — "omp를 진짜 매니저로"의 씨앗은 secretary가 아니라 **env·audit·codify 쪽에서 이미 자라고 있다** | 미배정 — 위와 같음 |
| T12 | DESIGN §4의 결합지점은 4개가 아니라 **5개**가 맞다. `plot`/`promote-plots` 경로를 완료 조건에 넣을지 정하라 | **T24** (0-C) — **닫힘 (2026-08-24)**. 답은 **넣지 않는다**: `omx plot`은 triage 렌더러라 논문 규격이 아니고, 논문 규격 렌더러는 프로젝트에 이미 있다(실측). 결합지점 5개는 유지하되 T12 완료 조건에서 figure 조달을 빼고 그 근거를 같은 칸에 적었다. oms 층 일반 규칙만 릴리스 승인 대기 |
| T13 | 타당성은 유지(데이터 부재는 실측)되나 근거였던 "문헌 없음"이 반증됐다. `2608.19564`는 "무조건 저장 말고 경계를 판정하라"는 쪽이라 **설계 자체에 영향** | 미배정 — 감사 §5 4순위, 이번 범위 밖 |

**"미배정"은 기각이 아니라 범위 밖이다.** 사용자가 2026-08-23에 감사 §5 우선순위 **1~3번만**
착수하기로 정했고, T10·T11·T13은 4·5순위다. 착수하려면 그 결정을 다시 열어야 한다.

---

## Phase 4 — 신설 1건 (게이트 있음)

### T16: 크로스머신 자산 레지스트리

조사가 "전 저장소 선례 0"을 verified로 확정했으므로 신설 자체는 정당하다. 다만 남은 두
공백이 채워지기 전에는 스키마를 쓰지 않는다.

- [ ] **게이트 A**: 사용자가 실제로 자산을 못 찾아 손해 본 구체 사례 1건 이상. 이번 조사
      전체에 그런 사례가 없다. 없이 만들면 "있으면 좋을 것 같아서"가 되고, 그건 이 계획이
      기각한 방향이다.
- [ ] **게이트 B**: 스키마 설계. 최소한 머신 식별자·저장소 경로·동기화 상태·마지막 확인
      시각의 필드명과 타입이 정해져야 한다. 머신 목록 8개는 auto-memory 재인용일 뿐
      **신규 실측이 아니므로** 현재 상태 재검증도 여기 포함된다.

**분할은 사용자 원문을 따른다**(DESIGN.md §4): 저장소 목록은 `.oms`, 실험 결과와 그 위치는
`.omx`. 중앙 레지스트리를 새로 만들지 않는다.

---

## 부록 A — 선행 계획 K항목 재판정

미구현 실측(2026-08-22): K01·K02·K10·K11·K12 전부 부재.

| ID | 항목 | 대상 | 이번 계획에서 |
|:---|:---|:---|:---|
| K10 | MEMORY.md 학습 → omha 카드 승격 파이프라인 | omha | **보류** — Phase 1 데이터가 "어떤 학습이 실제로 재발을 막았나"를 먼저 답해야 한다 |
| K11 | 가드 유효성 재감사 스텝 | claudebase | **Phase 1이 대체한다** — Task 4가 바로 그 재감사다 |
| K01 | 토큰 경제 env 노브 | claudebase | 유효, Phase 3 후보 |
| K02 | `settings.json $schema` | claudebase | 유효, 저비용 |
| K12 | session-report 플러그인 | claudebase | **재판정 필요** — 계측 목적이면 Phase 1과 중복 |
| K08 | Agent Teams TaskCompleted 품질 게이트 | omc-custom | 보류 — omc는 타인 소유, 조작 지점은 omha 카드 |
| M1 | Bash 콜론 와일드카드 감사 | — | **폐기**(X5) |
| M5 | learning-output-style 트랩 감사 | — | likely 폐기 — Task 6 Step 5에서 확인 |
| K15·K16 | 샌드박스·MCP 번들 | — | **미조사** — 이번 계획 범위 밖임을 명시 |

## 부록 B — 진입점

이 계획이 실행되게 하는 장치. 지난 계획이 죽은 원인이 진입점 부재였다(DESIGN.md §6).

- [x] `0_Project/in_progress/harness/README.md` 생성 — vault `.omp/rules.json`이 프로젝트마다
      README.md 진입점을 `enforced`로 요구한다. *(실측 2026-08-24: 존재, 18,987 B, 계속 갱신 중)*
- [x] ~~Google Calendar 이벤트 1건 — Task 1 착수일.~~ **무의미해졌다** — Task 1은 2026-08-22에
      끝났다(`12ae91f`). 착수일 알람은 착수 전에만 값이 있다. *(2026-08-24 판정, 이벤트 미생성)*

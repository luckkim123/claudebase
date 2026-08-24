# oh-my-project 갭 분석 — secretary 축은 왜 안 쓰이는가

조사일 2026-08-22. 대상: vault(`ksm_Obsidian`), workspace(`Desktop/workspace`), claudebase(`~/claudebase`) 세 프로젝트의 `.omp/` 실태 + `~/oh-my-project` 소스(설치판 v0.12.0).

---

## 1. 결론 (BLUF)

secretary 축은 "기능 부재"가 아니라 **"부트스트랩만 되고 방치"**다. vault 는 2026-07-11 에 사용자 요청으로 인프라만 만들고 그날 이후 `todo.txt`/`raid.md`를 단 한 번도 쓰지 않았다(0 byte, mtime 그대로). journal 은 실제로 매일 쌓이지만 전부 SessionEnd 훅이 찍는 기계 stub 한 줄(`- HH:MM session \`id\` ended`)이고, 서사(narrative)는 부트스트랩 당일 한 건뿐이다. workspace 는 애초에 secretary 스키마 자체가 없다 — `rules.json` 의 `omp_version` 이 `0.1.0` 으로, secretary 축이 추가된 0.4.0/0.5.0 보다 훨씬 이전 세대에서 멈춰 있다(설치된 플러그인은 0.12.0). claudebase 는 `.omp/` 가 아예 없다.

"규칙 강박"은 omp 의 스키마·프로세스에서 add-only 비대칭을 찾지 못했다(제거 경로는 구조적으로 대칭) — 대신 **감사(audit)는 즉시·자동으로 위반을 알리는 반면 규칙 완화(codify)는 에이전트 디스패치 + 인간 승인 게이트라는 무거운 의례를 거쳐야 하는 비용 비대칭**이 확인됐다. 사소한 severity 하향(error→warn)에도 같은 무게의 절차가 걸린다.

"프로젝트 관리 전반"에 없는 축(마감·우선순위·이해관계자 등) 나열은 뒤에 두되, **결론은 "추가하지 말라"** 다 — 이미 있는 RAID(위험/가정/이슈/의존성)·우선순위(BuJo `(A)`)·주간 회고(`omp-review`)조차 0회 사용인 상태에서 축을 더 만드는 것은 하네스 A/B 실측(스킬 호출 0건, 이득은 훅에서만 나옴)이 이미 경고한 바로 그 실패를 반복하는 일이다.

---

## 2. 세 프로젝트 `.omp/secretary/` 실태 (전수 실측)

| | vault | workspace | claudebase |
|---|---|---|---|
| `.omp/` 존재 | 있음 | 있음 | **없음** |
| `rules.json` `omp_version` | `0.5.0` | `0.1.0` | — |
| 설치된 플러그인 버전 | 0.12.0 | 0.12.0 | — |
| `rules.json.secretary` 키 | 있음 (`sources`+`surfaces: []`) | **키 자체 없음** | — |
| `secretary/BRIEF.md` | 있음, 마지막 갱신 2026-08-14 | **없음** | — |
| `secretary/todo.txt` | 존재, **0 byte**, mtime 2026-07-11 부트스트랩 그대로 | 존재 안 함 | — |
| `secretary/raid.md` | 존재, 섹션 헤더만, **0건**, mtime 2026-07-11 그대로 | 존재 안 함 | — |
| `secretary/journal/` | 매일 파일 존재(07-11~08-22), 그러나 08-22 등 대부분은 SessionEnd 훅의 기계 stub 한 줄뿐 | 매일 파일 존재(07-12~08-21), 동일하게 stub 한 줄 | — |
| `secretary/ledger.jsonl` | 321줄 | 122줄 | — |
| `secretary/decisions/` | 존재 안 함(BRIEF: "미사용") | 존재 안 함 | — |

**근거**: `find .../.omp -type f` 전수 리스트, `wc -l`, `stat -f "%Sm"`, `cat` (2026-08-22 세션 직접 실행). `rules.json` `omp_version` 비교는 `python3 -c "json.load(...)['omp_version']"`.

vault `BRIEF.md` 본문(마지막 규성 2026-08-14):
> "chronicler 축(raid/todo/decisions)은 미사용 선언(rules.json `secretary.surfaces: []`) — 진행 기록은 git 커밋·auto-memory·vault 노트로 돈다."

이 문장 자체가 SSOT 자기보고이며, 사용자 지시문이 인용한 그 문구와 정확히 일치한다(confidence: verified, 파일에서 직접 확인).

---

## 3. `secretary.surfaces: []` 가 실제로 끄는 범위 — 오독 가능성 정정

`~/oh-my-project/agents/auditor.md:25` 의 정의:

> "A project that declares `secretary.surfaces: []` in `rules.json` has opted out and reports none of these — absent means all three, an explicit `[]` means the chronicler axis is unused."

즉 `surfaces: []` 는 **`axis_dormant` 등 감사 축(hygiene audit)의 경고를 끄는 옵트아웃 선언**이지, journal/ledger 자동 기록이나 `BRIEF.md` 주입 자체를 끄는 스위치가 아니다(스키마 필드 이름과 실제 동작 범위가 어긋나 오해하기 쉽다 — confidence: verified, 코드 정의와 관측된 동작이 부합). 실제로:

- SessionEnd 훅(`omp_session_capture.py`, `.claude-plugin/plugin.json` 의 `SessionEnd` 훅)이 journal stub 을 강제로 계속 씀 — `surfaces: []` 와 무관하게 vault·workspace 둘 다 매 세션 자동 기록됨.
- SessionStart 훅(`omp_session_brief.py`)이 `BRIEF.md` 존재 시 최대 2000자까지 매 세션 advisory context 로 주입함(vault 만 해당, workspace 는 `BRIEF.md` 자체가 없어 조용히 스킵 — `if not brief.is_file(): return 0 # pull model: nothing prepared, stay silent`).

**따라서 "chronicler 축 미사용 선언"은 정확히는 "todo/raid/decisions 세 파일만 미사용 선언"이지 secretary 전체가 꺼진 게 아니다.** BRIEF.md 의 표현이 이 구분을 흐린다(confidence: likely — 표현이 부정확하다는 것은 코드 근거로 확인했으나, 사용자가 실제로 이 구분 때문에 헷갈렸는지는 확인 안 함).

---

## 4. 왜 안 쓰이는가 — 원인별 판정

사용자가 제시한 5개 후보 가설을 각각 실측으로 검증.

### 4-1. 진입점이 없다(스킬 이름을 모른다) — **부분적으로 참**

`omp-log`/`omp-brief`/`omp-review` 는 시스템 프롬프트의 skill 목록에 정확히 등재돼 있고 트리거 키워드도 한국어로 명시돼 있다("주간 리뷰", "브리핑", "현황" 등 — `~/oh-my-project/skills/omp-review/SKILL.md` frontmatter). 즉 발견 가능성 자체는 낮지 않다. 그러나 **가장 강한 진입점(SessionStart 자동 주입)은 매 세션 작동 중**이므로, "몰라서 안 쓴다"는 설명은 vault 에는 약하다 — 매번 보고도 반응하지 않은 것에 가깝다. workspace 는 애초에 `BRIEF.md` 가 없어 이 자동 진입점조차 없다(§2).

### 4-2. 라우팅 카드가 secretary 단계로 안 보낸다 — **확인 안 함**

`omha` 라우팅 카드(`~/oh-my-heroacademia`) 가 "진행 상황 물어봐" 류 발화를 omp-brief 로 보내는지는 이번 조사 범위에서 카드 파일을 직접 읽지 않았다(사용자 요구는 omp 자체 갭이라 omha 카드까지는 열지 않음). **확인 안 함으로 명시.**

### 4-3. 초기 설정 비용이 크다 — **약한 근거, 반증 있음**

부트스트랩 자체(2026-07-11)는 완료됐고 인프라는 있다. 비용이 큰 건 초기 설정이 아니라 **지속 사용**(매번 `omp-log` 를 불러 todo/raid 에 기입하는 습관)이다. 설정비용 가설은 부트스트랩 이후의 방치를 설명하지 못한다.

### 4-4. 산출물이 사용자 눈에 안 보인다 — **참, 그리고 이게 핵심 원인으로 보임**

`BRIEF.md` 주입은 `additionalContext`(SessionStart hookSpecificOutput)로 들어간다. 이는 대화 UI에 별도 카드나 알림으로 뜨지 않고 모델의 컨텍스트에만 조용히 섞여 들어간다 — 사람이 아니라 **Claude 가 보는 채널**이다. 즉 "산출물이 사용자 눈에 안 보인다"는 정확한 진단이며, 사용자가 반응할 기회 자체가 구조적으로 제한돼 있다(confidence: likely — 훅 메커니즘은 verified, 이것이 사용자 인지 실패의 인과인지는 추론).

게다가 8일 정체된 `BRIEF.md`(2026-08-14 마지막 규성, 오늘 08-22)가 매 세션 반복 주입되면서 항상 "GREEN — 0 open tasks"·"미사용 선언"만 반복해서 알린다 — **점점 무시해도 되는 신호로 습관화(cry-wolf)됐을 가능성**이 구조적으로 존재한다(confidence: likely, 반복 빈도는 verified, 습관화 효과 자체는 심리적 추론).

### 4-5. 이미 다른 것(git 커밋·auto-memory·vault 노트)이 그 일을 하고 있다 — **BRIEF.md 의 자체 주장, 부분적으로 타당**

`BRIEF.md` 는 "진행 기록은 git 커밋·auto-memory·vault 노트로 돈다"고 명시적으로 선언한다. 이 vault 는 실제로 `~/.claude/projects/.../memory/MEMORY.md` 가 방대하고(시스템 프롬프트에 첨부된 MEMORY.md 만도 90줄+) git 커밋 로그도 활발하다(`git log` 최근 5건 확인 가능, 한국어 프리픽스 커밋). **RAID(위험/가정/이슈/의존성)의 대체재는 이 셋 중 없다** — auto-memory 는 "학습(learning)"을 기록하지, "아직 안 닫힌 리스크"를 추적하는 구조가 아니다. 즉 todo/journal-narrative 는 대체재가 있어 보이지만, RAID 는 진짜 빈 자리일 수 있다(confidence: unverified — RAID 항목이 실제로 필요했던 사례가 있었는지는 이번 조사 범위 밖).

### 종합 판정

가장 근거가 강한 원인은 **4-4(가시성 부재 + 습관화)** 다. `omp_version` 격차(vault 0.5.0/workspace 0.1.0, 설치판 0.12.0)도 별도 원인으로 확인됐다 — `omp-codify`/`omp-init` 재실행 없이 방치되면서 workspace 는 secretary 스키마 자체를 못 받았다(§5-3).

**BRIEF.md 의 자기평가("chronicler 축 미사용 선언")가 정당한 판단인가, 채택 실패인가**에 대한 판정: **둘 다다.** todo/journal-narrative 를 git+auto-memory+vault 노트로 대체한다는 결정 자체는 근거가 있다(그 세 채널이 실제로 활발히 쓰이고 있음, verified). 그러나 RAID 축까지 함께 "미사용"으로 묶은 것, 그리고 그 결정을 담은 `BRIEF.md` 가 8일째 정체된 채 계속 반복 주입되며 재검토 한 번 없이 방치된 것은 **결정의 타당성과 별개로 절차적 채택 실패**다 — `omp-review`(주간 재평가, 인간이 매번 재판단)가 정확히 이 정체를 막기 위한 스테이지인데 단 한 번도 호출된 흔적이 없다(`work/audits/`, `work/plans/` 어디에도 review 실행 아티팩트 없음, `todo.txt` 는 부트스트랩 이후 변화 0).

---

## 5. "규칙 강박" — 구조적 비대칭 실측

### 5-1. 스키마 자체는 대칭이다

`~/oh-my-project/skills/omp-codify/SKILL.md:21,47,67,91` 은 반복적으로 "add/modify/**remove**"를 대칭으로 명시하고, `agents/rule-architect.md:75` 는 "added / changed / **removed** rules" diff 를 인간에게 보여주라고 규정한다. 즉 **규칙 삭제·완화 경로는 스키마·프로세스 설계상 존재하며 add-only 로 막혀 있지 않다**(confidence: verified, 소스 직접 확인).

### 5-2. 그러나 프로세스 무게는 비대칭이다

- **위반 감지(audit)**: `omp-audit` 가 즉시·자동·기계적으로 실행되고 결과는 read-only PASS/FAIL 로 바로 나온다. 사람 개입 없이 반복 가능.
- **규칙 완화(codify)**: `~/oh-my-project/skills/omp-codify/SKILL.md:37,49` — "Rule change = human approval gate. Changing a rule is a heavy decision" 이며, rule-architect 에이전트 디스패치 → diff 제시 → **GATE(인간 승인, proceed/revise/abort)** → 세 파일(`rules.json`+`STRUCTURE.md`+`NAMING.md`) 동시 갱신이라는 전체 파이프라인을 거친다. 이 무게는 사소한 severity 하향(`error`→`warn`, 스키마상 `default: "warn"` 이 이미 있음에도)에도 동일하게 적용된다 — 경량 경로가 없다(confidence: verified, SKILL.md 원문에 근거).

이 **"위반은 공짜로 반복 알림, 완화는 매번 무거운 의례"** 비대칭이 사용자가 느끼는 "규칙 강박"의 구조적 원인일 가능성이 높다(confidence: likely — 비대칭 자체는 verified, 이것이 사용자 심리 원인이라는 연결은 추론).

### 5-3. severity 필드는 이미 있고 기본값이 "warn"이다 — 활용 확인 안 됨

`references/schemas/rules.schema.json` 의 `severity` enum 은 `warn`/... 을 가지며 `default: "warn"` 이다(라인 205-212, 322-329). 즉 규칙을 "위반 시 즉시 실패"가 아니라 "경고만"으로 완화하는 손잡이가 이미 스키마에 있다. vault `rules.json` 의 실제 규칙들이 이 필드를 얼마나 쓰고 있는지, 아니면 전부 암묵적 warn 기본값에 머물러 있는지는 이번 조사에서 vault `rules.json` 개별 규칙 항목을 전수 대조하지 않아 **확인 안 함**.

---

## 6. "프로젝트 관리 전반"에 없는 축 — 추가 제안 전에 입증 부담부터

### 6-0. 왜 축 추가는 기본적으로 기각 대상인가

사용자 지시문이 명시한 실측(SSOT `~/claudebase/eval/README.md`): om* 플러그인층 A/B 에서 코드 정확성 축 변별 0(8/8 동점), 규율 축만 Δ+0.222 였는데 그 이득이 나온 런에서 **Skill 호출은 0건**이었다 — 즉 스킬(=기능)의 존재가 이득을 만든 게 아니라 훅이 주입한 컨텍스트가 이득을 만들었고, 대가는 토큰 +41%·비용 +69% 였다.

이 vault 자체가 그 패턴의 축소판이다: RAID·우선순위·주간회고 라는 "관리 축"이 **이미 스키마에 있는데 0회 사용**이다. 여기에 마감·이해관계자·리소스 같은 축을 더 추가하면, 사용된 적 없는 기능이 하나 더 늘어 토큰 예산(매 세션 BRIEF injection cap 은 이미 2000자로 하드코딩돼 있다 — `omp_session_brief.py:13`)만 갉아먹을 위험이 실측으로 뒷받침된다. **그러므로 이 절의 나열은 "만들자"가 아니라 "이미 있는 것부터 왜 안 쓰이는지 닫고, 그래도 남는 진짜 공백만" 판단하기 위한 목록이다.**

### 6-1. omp 스키마에 이미 있는 축 (0회 사용 상태)

| 축 | 위치 | 상태 |
|---|---|---|
| 우선순위 | todo.txt `(A)` BuJo priority letter (`secretary-protocol.md:51`) | 0건 (todo.txt 비어있음) |
| 리스크/가정/이슈/의존성 | `raid.md` 4섹션 | 0건 |
| 주간 회고 | `omp-review` (migration, stale scan, raid 재확인) | 호출 흔적 없음 |
| 의사결정 기록 | `decisions/` | 미사용 (BRIEF: "git 커밋과 vault 노트로 대체") |

### 6-2. omp 스키마에 없는 축

- **마감/일정(deadline)**: `secretary.sources[]` 로 기존 캘린더(`3_Archive/calendar/personal`)를 "읽기 전용 소스"로 등록하는 방식만 있고, omp 자체의 due-date 필드는 todo.txt 항목에 없다(`secretary-protocol.md` 에 우선순위 문자만 있고 날짜 문법 없음). 이는 **의도적 설계**로 보인다 — README 의 "D14 read-don't-replace, never create competing surfaces" 원칙과 `para.md:250-251` 이 "PARA vaults already keep state surfaces omp's secretary axis can read — read, don't replace" 를 명시한다.
- **이해관계자(stakeholder)**: 스키마·문서 어디에도 개념 없음.
- **리소스 배분/용량**: 없음.
- **의존성 그래프(작업 간)**: RAID 의 "Dependencies" 섹션이 텍스트 자유기술로만 존재, 그래프/추적 구조 없음.

### 6-3. 판단

이 공백들에 대한 추가 제안은 **보류**한다. 근거: (a) 이미 있는 우선순위·RAID·회고 축이 전부 0회 사용인 상태에서 추가 축의 채택률이 다를 것이라는 근거가 없다. (b) 사용자가 실제로 필요로 했던 구체적 실패 사례(예: "의존성을 놓쳐서 문제가 생겼다")를 이번 조사에서 찾지 못했다 — **확인 안 함**. (c) 마감/일정 공백은 read-don't-replace 원칙상 의도된 설계이며, 이 vault 는 이미 별도 `rules-calendar` 스킬 + Google Calendar 로 마감을 관리 중이다(vault CLAUDE.md 확인).

---

## 7. 제거·통합·재배선 제안 (사용자 요청대로 우대)

높은 확신 순.

1. **workspace `rules.json` 재코드화(`omp-codify` 또는 `omp-init` 재실행) 우선순위 최상위.** `omp_version: 0.1.0` 대 설치판 `0.12.0` — secretary 스키마 자체가 없어 BRIEF/todo/raid 인프라조차 못 만들었다. "왜 안 쓰이냐"는 질문에 대해 workspace 는 애초에 쓸 수 있는 것이 배포되지 않은 상태다. 이건 채택 실패 이전의 배선 누락이다.

2. **BRIEF.md 정체(8일) 해소 — `omp-review`→`omp-brief` 체인을 한 번 돌려서 판정을 재확인하거나, 정말로 안 쓸 거면 명시적으로 재확인 날짜를 박아라.** 지금처럼 오래된 "GREEN·0건" 이 매 세션 계속 주입되는 것 자체가 신호 가치를 죽인다(습관화). 재확인 없이 계속 두는 것과 명시적으로 "RAID/todo 는 이 vault 에서 영구 미사용"이라고 확정하는 것은 다르다 — 후자면 아예 `BRIEF.md`/`raid.md`/`todo.txt` 생성을 생략하는 편이 정직하다.

3. **RAID 축만 골라서 재검토하라(todo/journal-narrative 는 그대로 대체재 유지).** git 커밋·auto-memory·vault 노트가 실제로 커버 못 하는 유일한 후보는 "아직 안 닫힌 리스크/이슈"다. 이건 스킬을 더 만드는 게 아니라 **이미 있는 파일 하나(raid.md)를 실제로 쓸지 말지 결정**하는 문제 — 새 기능 추가가 아니므로 §6-0 의 입증 부담과 충돌하지 않는다.

4. **"규칙 강박" 완화는 새 메커니즘이 아니라 기존 severity 필드 활용 홍보다.** `rules.json` 의 개별 규칙에 `severity: "warn"` 을 명시적으로 다는 것만으로 완화가 가능한데, 그 손잡이 존재 자체가 안 알려졌을 가능성이 있다(§5-3, 확인 안 함). 새 완화 경로 설계 전에 기존 필드 활용도부터 vault `rules.json` 개별 항목 대조가 먼저다.

5. **claudebase 는 `.omp/` 없음 — 그대로 둘 것.** vault CLAUDE.md 자체가 "claudebase 는 메타 변경이라 서지컬해야 한다"고 명시하며 omp 를 이 저장소에 배선하는 제안은 애초에 범위 밖이다. 확인만 하고 액션 없음.

6. **§6-2 의 새 축(마감/이해관계자/리소스) 추가는 기각.** 근거는 §6-0/6-3.

# oh-my-scholar(oms) 갭 분석 — "연구 총괄 하네스" 요구 대비

조사일: 2026-08-22. 대상: `~/oh-my-scholar` 전수 read + grep, `~/oh-my-experiments`
README/구조, `~/oh-my-project` 일부, vault·workspace 실사용 흔적(`.oms/` 디렉터리 실측).
구현·수정 없음 — 조사·재료 수집만.

---

## 1. oms 현재 실제 능력 (실측)

### 1.1 규모

- 스킬 14개 (`~/oh-my-scholar/skills/*`, `skill-bodies/*/SKILL.md`), 에이전트 6개
  (`~/oh-my-scholar/agents/*.md`), 훅 5개 등록 + 공용 유틸 2개 (`hooks/`).
  근거: `~/oh-my-scholar/README.md:88` "v0.14.0 — 14 skills + 6 agents + reference cards
  ... + citation-safe hooks".
- 스킬 목록: init·research·deepen·ideate·outline·draft·inspect·mock-review·verify·revise·
  pilot·read·discuss·learn. 근거: `~/oh-my-scholar/skills/` 디렉터리 리스팅(ls 실행,
  2026-08-22) + `README.md:36-63` Stage skeleton 표.
- 에이전트: scholar-researcher(sonnet, read-only)·scholar-planner(opus, read-only)·
  scholar-inspector(opus, read-only)·scholar-reviewer(opus, read-only)·
  scholar-verifier(sonnet, read-only)·scholar-drafter(sonnet, **write**, 유일한 .tex/.bib
  저자). 근거: `README.md:66-73` Agents 표.
- 훅: `scholar_route_emit.py`(UserPromptSubmit, STAGE 라인 주입)·
  `scholar_verify_emit.py`(PostToolUse, .tex/.bib 편집 후 인용검증 리마인더)·
  `scholar_cite_guard.py`(PreToolUse, 미검증 인용 구조적 거부)·
  `scholar_stop_guard.py`(Stop, revise 루프 조기종료 방지)·
  `scholar_resume_emit.py`(SessionStart, 재개 안내). 근거: `README.md:81`.

### 1.2 정체성 — 논문 "작성" 파이프라인, "연구" 총괄 아님

`README.md:1-2` 자체 정의: "Multi-agent orchestration harness for **academic paper
writing**". Stage skeleton(`README.md:36-63`)은 코드 유비를 명시적으로 건다 —
research=requirements, ideate=design, draft=implementation, verify=CI, revise=ralph.
이 유비는 **논문 텍스트 생산**에 대한 것이고, 실험 실행·분석·결과 해석에 대한 것이 아니다.

STAGE 라우팅 훅의 STAGE enum 자체가 이를 증명한다:
`init|research|deepen|ideate|outline|draft|inspect|mock-review|verify|revise|learn|read|discuss|scholar-pilot`
— "analyze"/"experiment"/"visualize" 단계가 없다. 근거: `hooks/scholar_route_emit.py:83`.

### 1.3 `.oms/` 스키마 — 단일 작업공간·상대경로 전제

`references/output-layout.md:16-18`: "All paths are relative to the work root ... never
hardcoded to any one machine or absolute path." `.oms/<slug>/`는 하나의 논문 폴더 밑에
research/methodology/outline/versions/renders 등을 담는 **작업 캐시**이지, 여러 저장소·
머신을 가로지르는 레지스트리가 아니다. `scholar-init` 스텝5의 "Cross-platform" 조항도
동일: "all paths are relative or based on Path.cwd(). No hardcoding of absolute paths·`~`."
근거: `skill-bodies/scholar-init/SKILL.md:46` (Execution_Policy).

`.oms/learned.md`(heavy-channel 관측 원장)는 **빈 상태로 출하**되고 프로젝트별로 누적된다
— 이 역시 "구조/순서/포맷/작업 습관" 후보만 다루며(§ 인용 영구 금지), 실험·자산 레지스트리
용도가 아니다. 근거: `.oms/learned.md:1-16` (본 저장소 자체 원장, 실측 시점 비어 있음).

---

## 2. 요구 항목별 판정

| 항목 | 판정 | 근거 |
|:---|:---:|:---|
| (a) omx 연동 | **없음** | 아래 §2.1 |
| (b) 머신·저장소 횡단 자산 레지스트리 | **없음** | 아래 §2.2 |
| (c) 실험 결과 시각화 | **없음** | 아래 §2.3 |
| (d) 추가 실험 도출 | **없음** (oms 안에서는) | 아래 §2.4 |
| (e) 연구 진행 총괄·상태 추적 | **부분** (논문 파이프라인 상태만) | 아래 §2.5 |

### 2.1 omx 연동 — 없음 (verified)

`~/oh-my-scholar` 전체(`.claude/worktrees` 제외, 실 코드/문서)에서 `omx`/`oh-my-experiments`
문자열은 단 1곳: `references/omc-backport-analysis.md:107` — omx 위키 정책을 **참고 사례로
인용**한 것이지 연동 코드/훅/스킬이 아니다. `docs/2026-07-11-oms-advancement-plan.md`(계획
문서, 병합 안 됨— `docs/`에 존재하나 README 스킬 목록·CHANGELOG에 P-단계로 반영된 흔적
없음)에도 "omx 정밀도" 비교만 있고 실행 항목 없음. `scholar-researcher`/`scholar-verifier`
등 어떤 에이전트도 `.omx/` 파일을 읽거나 쓰는 코드가 없음(grep 결과 0건).
근거: `grep -rniw "omx" ~/oh-my-scholar --include=*.md --include=*.py` (worktree 중복 제외
본선 3곳, 전부 참고 인용). 확인 안 함: worktree(`oms-r1`~`oms-r6`)는 병합 대기 브랜치인지
폐기 브랜치인지 git log로 확인하지 않았음.

### 2.2 머신·저장소 횡단 자산 레지스트리 — 없음 (verified)

- oms 쪽: `.oms/`는 프로젝트 로컬, 상대경로 전제(§1.3). 여러 머신에 흩어진 git 저장소나
  실험 결과 위치를 기록하는 필드·파일이 없음.
- omp 쪽: `~/oh-my-project`의 `manifest.json`/`rules.json`은 **한 프로젝트 폴더 내부의**
  파일 계보(lineage)·데이터셋 체크섬을 다루는 스키마이며, machine_id/hostname 개념이
  코드에 없음. 근거: `grep -n "machine" ~/oh-my-project -r --include=*.py --include=*.md`
  결과 3건 전부 "경로를 머신에 하드코딩하지 말라"는 이식성 경고문(`references/
  docker-mechanisms.md:49`, `agents/dataset-curator.md:52`, `skills/omp-env/SKILL.md:64`)
  — 레지스트리가 아니라 정반대(비하드코딩 원칙).
- omx 쪽: `.omx/programs/<id>/`는 "실험 캠페인"을 프로젝트 폴더 하나 안에서 관리하는
  스키마(`README.md:211-229`)로, 여러 머신의 실험을 가로지르지 않음.
- vault 쪽: `SYSTEM.md` 계열 파일(`0_Project/in_progress/albc/SYSTEM.md`,
  `.../krit/SYSTEM.md`)이 존재하나 각각 **단일 프로젝트의 하드웨어 토폴로지**(보드·센서
  구성)를 기술하는 문서이지, 크로스-머신 자산 인덱스가 아님. 확인 안 함: 두 SYSTEM.md의
  전문은 읽지 않았음(존재·위치만 확인).
- 결론: 사용자가 원하는 "여러 머신·git 저장소·실험 결과 위치를 기록하는 레지스트리"는
  oms/omx/omp/vault 어디에도 **선례가 없다**. 처음부터 설계해야 하는 항목.

머신 인벤토리 재료(§4에서 상세): 이 조사에서는 auto-memory MEMORY.md에 이미 기록된 항목만
재인용했고, 각 머신에 대한 신규 실측(ssh 접속·디스크 스캔 등)은 하지 않았음 — 아래 §4는
"기존에 기록된 것의 집계"이지 새 조사가 아님.

### 2.3 실험 결과 시각화 — 없음 (verified)

`skill-bodies/scholar-verify/SKILL.md:38`이 스스로 이 경계를 명시: "FAIL items ...
classify by fixable_by_llm — ... false (**missing experimental data, figure generation,
etc.**) is flagged for a human." — 즉 verify 스킬은 그림 생성이 자기 범위 밖임을 알고
사람에게 넘긴다. 14개 스킬 전체에서 "figure"/"plot"/"visualiz"를 그린 코드(matplotlib 등)
호출은 0건(grep, `skill-bodies/*/SKILL.md`). `gen-image` 스킬(별도, oms 전용 아님)이
텍스트→이미지 생성을 하지만 이는 삽화/포스터용이며 데이터 플롯이 아님(스킬 설명 자체:
"text-to-image only").

### 2.4 추가 실험 도출 — 없음, 이미 omx가 그 역할을 함 (verified)

oms 쪽에는 "다음 실험을 설계하라"는 스킬/에이전트가 없음(§2.3과 동일 grep 결과, "next
experiment" 계열 문구 0건). 이 기능은 이미 omx `exp-design` 스킬이 정확히 이 역할로
존재함 — "Design the next experiment from an exp-analyze report ... proposes the single
discriminating probe (the next-experiment config) as a pending-approval artifact." (스킬
설명 원문, ToolSearch 결과 아님 — 시스템 프롬프트 스킬 목록에서 확인). 즉 사용자가
"oms가 이것도 해야" 라고 느끼는 기능은 omx에 **이미 있다** — oms에 새로 만드는 것은
omx와의 중복이 된다.

### 2.5 연구 진행 총괄·상태 추적 — 부분

`.oms/state/`(`scripts/oms_state.py`)가 파이프라인 상태(revise 라운드, strike 카운트,
GATE 통과 여부)를 추적하지만, 이는 **한 논문의 작성 파이프라인 상태**이지 "연구 프로그램
전체"(여러 논문·여러 실험 캠페인을 가로지르는 진행 상황)가 아님. 근거: `README.md:92`
"Added in 0.7.0: `.oms/state` schema + `oms_state` CLI, mechanical strike/round ledger".
`scholar-pilot`이 "full orchestration"(autopilot 유비, `README.md:60`)이라 불리지만
스코프는 여전히 "이 논문 하나"이고, omx 실험이나 다른 논문과의 우선순위 조정을 하지 않음.

---

## 3. omx 결합 방식 3안 — 재료만 (판정 보류)

사용자가 "oms가 메인이 되어야 한다"고 판단했지만 **구현 방식**은 아직 결정하지 않았으므로,
아래는 각 방식이 무엇을 깨고 무엇을 얻는지의 재료만 정리한다. 권고는 달되 결정은 사용자 몫.

### (1) 느슨한 연동 (loose coupling — 파일 계약으로만 연결)

- **메커니즘**: oms가 omx의 `.omx/programs/<id>/PLAN.md` 또는 `exp-analyze`가 쓰는
  `report.md`를 **읽기만** 한다(예: scholar-research나 새 스킬이 omx report를 인용
  소스가 아닌 "실험 컨텍스트"로 요약). 쓰기는 없음.
- **깨지는 것**: 없음. omx의 "zero runtime dependency" 원칙(`README.md:18`)이 지켜짐 —
  omx는 oms 존재를 몰라도 됨. oms의 "citation-bound, 인용 아닌 소스는 절대 .bib에 안 감"
  원칙(`README.md:73-79`)도 실험 report를 인용원으로 안 쓰면 안 깨짐.
- **얻는 것**: oms 세션에서 "이 실험 결과가 뭐였지"를 다시 실험 폴더로 안 가고 확인 가능.
  구현 비용이 가장 낮음(파일 읽기 한 단계).
- **한계**: omx report 포맷이 바뀌면 oms 쪽 파서가 깨질 수 있음(느슨하지만 무결하지는
  않음) — 다만 이는 "런타임 의존"이 아니라 "파일 계약 의존"이라 omx README의 원칙과는
  다른 층위.

### (2) 진짜 종속 (hard dependency — oms가 omx를 호출/포함)

- **메커니즘**: oms 스킬이 omx CLI(`omx` 명령)를 Bash로 호출하거나, omx 에이전트를
  `Task(subagent_type="oh-my-experiments:...")`로 직접 디스패치.
- **깨지는 것**: omx README의 정체성 문장 자체 — "carries zero runtime dependency on any
  other harness"(`README.md:18`)는 **omx가 다른 것에 의존하지 않는다**는 뜻이지 "다른
  것이 omx에 의존해도 된다"는 금지가 아니므로, omx 쪽 원칙은 형식적으로 안 깨질 수 있음.
  다만 실질적으로: omx가 "다른 하네스와 무관하게 버틴다"는 설계 의도(버전 처짐 면역,
  `README.md:8`의 "Why OMX" 표 "Self-contained ... Immune to other harnesses' version
  churn")는 **omx를 소비하는 쪽**(oms)이 omx 버전이 바뀔 때마다 깨질 위험을 그대로 진다
  — 그 리스크가 omx에서 oms로 옮겨갈 뿐, 사라지지 않음.
  또한 oms의 "single, careful draft" 원칙(병렬 draft 금지, `README.md:75`)과 omx의 "never
  launches training, everything is pending-approval"(`README.md:14`) 원칙은 서로 다른
  승인 게이트 모델을 갖고 있어 — 통합 시 두 게이트를 하나로 합칠지, 이중으로 유지할지
  결정이 필요(재료로만 남김, 설계 X).
- **얻는 것**: 사용자가 원하는 "실험 분석·시각화·다음 실험 도출까지 oms 안에서" 가장
  직접적으로 달성. 새 코드 최소화(omx의 exp-analyze/exp-design을 재사용).
- **비용**: oms가 omx의 CLI 인터페이스·`.omx/` 스키마 변경에 노출됨. omc-v4.15.2 정합
  감사에서 이미 지적된 논점과 동형 — `~/oh-my-experiments/docs/2026-07-05-omc-v4.15.2-
  alignment-audit.md:148`이 "omx의 hookless invariant"를 다른 하네스와의 통합에서
  깨지 않기 위해 어떤 타협을 했는지 기록되어 있음(참고 가치 있는 선례).

### (3) 별도 상위 레이어 (orchestration layer — 제3의 얇은 계층이 둘을 오케스트레이션)

- **메커니즘**: oms도 omx도 서로를 모르고, omha(라우팅 레이어) 또는 새 최소 스킬이
  "연구 총괄" 역할로 둘을 순서대로 호출(oms output → omx input, 혹은 그 역).
- **깨지는 것**: 없음(둘 다 원 설계 유지). 다만 **세 번째 계층**이 새로 생기므로, 사용자
  결정 방향("스킬을 더 만들지 말고 지울 것부터")과 정면으로 부딪힘 — 실측(claudebase
  eval)에서 스킬 존재 자체는 변별력이 없었고 이득은 훅의 컨텍스트 주입에서 나왔다는 근거
  (`~/claudebase/eval/README.md`, 사용자 제공 SSOT)가 이 방식에 대한 입증 부담을 특히
  무겁게 만듦 — "제3의 오케스트레이션 스킬"은 정확히 "스킬을 더 만들자"는 제안의 형태.
- **얻는 것**: 두 하네스의 독립성을 100% 보존. 재사용성 최대(omp의 omha 카드 패턴과
  구조적으로 유사 — `README.md:117`의 STAGE 라인이 omha ROUTE 라인 옆에 얹히는 방식).
- **한계**: 오케스트레이션 레이어 자체가 "언제 이 레이어를 거치는가"의 라우팅 판정을
  새로 필요로 함 — omha 카드 갱신(다른 저장소 PR)까지 얽힘.

### 재료 요약 (권고, 결정 아님)

세 방식 모두 "실험 report를 어떻게 읽어오는가"라는 최소 공통분모(방식 1)를 포함한다.
방식 1은 방식 2/3의 부분집합이므로, **입증 부담이 가장 낮은 (1)을 먼저 만들고 실사용
흔적을 본 뒤 (2)나 (3)으로 넓힐지 판단**하는 순서가 사용자의 "측정 우선" 결정 방향과
가장 정합적이라고 보임 — 이는 재료 해석이지 이 조사의 최종 결정이 아님.

---

## 4. 머신·저장소 인벤토리 재료 (auto-memory·vault 재인용, 신규 실측 아님)

이 절은 **기존에 이미 기록된 것을 모은 것**이며, 각 머신에 새로 접속하거나 확인하지
않았음(사용자 지시 범위 밖·시간 제약). 출처를 각 행에 명시.

| 머신/컨테이너 | 역할(기존 기록) | 출처 |
|:---|:---|:---|
| 이 Mac (로컬) | vault(git) + workspace(iCloud) 작업, Claude Code 호스트 | 이 세션 CLAUDE.md 자체 |
| ksm-ubuntu | marinelab-isaaclab 컨테이너 2벌(정본/구본) 호스트, Tailscale 재인증 이슈로 직접 IP 필요(141.223.223.195) | `machine_marinelab_two_albc_trees.md`, `machine_ksm_ubuntu_tailscale_reauth.md` |
| marinelab-container (ksm-ubuntu 내부) | SSH 2222/root, orca serve 상주(6768), Orca 워커 실행지 | `reference_marinelab_container_ssh.md` |
| stonefish_dev 컨테이너 | Stonefish 물리 시뮬레이션, GPU GUI DISPLAY=:0 직결 | `project_stonefish_dev_container.md` |
| DGX GB10 | num_envs 상한 32768 실측, teacher 학습 런 다수 | `project_dgx_num_envs_ceiling.md`, `project_dgx_teacher_final_32k_run.md`, `project_dgx_teacher_envscale_16k_run.md` |
| TX2 (agent-jetson 계열 실물 보드) | ALBC numpy 런타임 배포 검증완료 | `project_albc_tx2_deploy_path.md` |
| agent-jetson | hero_agent 로봇(ROS lunar), UUV 보드(DVL·USBL·IMU·Dynamixel) | `machine_agent_jetson_is_uuv_board.md` |
| pkrc-jetson | Orin NX 16GB, ROS2 humble | `.claude/skills/rules-robot-code` (CLAUDE.md Skill Index) |

이 표에 대한 확인 수준: **verified는 "auto-memory에 이렇게 적혀 있다"는 사실뿐**이고,
현재도 각 머신이 그 상태인지는 **확인 안 함**(예: DGX 학습 런이 아직 진행 중인지, TX2
배포가 최신인지는 재검증 필요 — auto-memory 자체가 "가장 최근 갱신 시점 스냅샷").

기존에 이 역할(크로스-머신 레지스트리)을 하는 것: **없음** — §2.2에서 확인한 대로 omx의
`.omx/programs/`, omp의 `manifest.json`, vault의 `SYSTEM.md` 모두 단일 프로젝트 내부
스키마이고, 이 표처럼 "머신×역할"을 가로지르는 문서는 auto-memory MEMORY.md 자체가
사실상 유일한 근사치다(단, MEMORY.md는 회고록이지 질의 가능한 레지스트리가 아님 — 스키마
없음, grep 대상일 뿐).

---

## 5. 제거 관점 — oms 14 스킬 중 실사용 흔적

### 5.1 실사용 흔적이 있는 스킬 (workspace `.oms/` 디렉터리 실측, verified)

`/Users/kimseungmin/Desktop/workspace/10-19_Academic/12_Masters_Thesis/.oms/
asv-rov-cooperative-localization/`(석사논문) 및 workspace 루트 `.oms/{albc,albc-icra,
rl-albc,thesis}/`(연구실 페이퍼들)의 실제 디렉터리 구조로 다음 스킬의 산출물이 확인됨:

| 스킬 | 흔적 | 경로(예시) |
|:---|:---|:---|
| scholar-init | venue-config, 슬러그 폴더 존재 | `.oms/venues/postech_thesis.yaml` |
| scholar-research | related-work 노트 | `.oms/asv-rov-cooperative-localization/research/related_work_map.md`, `axis_a_sonar_localization.md` |
| scholar-ideate | methodology .md 6편 | `.oms/asv-rov-cooperative-localization/methodology/01_cooperative_localization.md` 외 5편 |
| scholar-outline | outline.md + 재구조 제안 문서 3편 | `.oms/asv-rov-cooperative-localization/outline/{outline.md,RESTRUCTURE_PROPOSAL.md,RESTRUCTURE_FINAL.md,SECTION_REVIEW_DECISIONS.md}` |
| scholar-draft (또는 그 산출물의 버전 스냅샷) | 다수의 `.tex` 버전 파일 | `.oms/{albc,albc-icra,rl-albc}/versions/*.tex` (20편 이상) |
| scholar-learn (추정) | wiki convention/decision/reference 노트 | `.oms/wiki/{convention,decision,reference}/*.md` |

### 5.2 실사용 흔적을 찾지 못한 스킬 (unverified — "없다"의 증거 아님)

디렉터리 구조 스캔만으로는 다음 스킬의 산출물 위치를 특정하지 못했음:
scholar-deepen, scholar-inspect, scholar-mock-review, scholar-verify, scholar-revise,
scholar-pilot, scholar-read, scholar-discuss.

**주의 — 이것을 "미사용"으로 단정하지 않는 이유**: (1) 세션 로그(jsonl) 전수를 grep하지
않았음 — 디렉터리 부산물을 안 남기는 스킬(mock-review·verify는 read-only 산출물이 대화
안에서만 소비될 수 있음)은 파일시스템 흔적이 없는 게 정상일 수 있음. (2) revise는 버전
스냅샷(§5.1의 `.tex` versions)이 곧 그 흔적일 가능성이 높음 — versions 폴더가 여러 개
쌓인 것 자체가 revise 루프가 돌았다는 정황(간접 증거, verified 아님). (3) `.oms/
workflows/*.js`(예: `figure-convention-survey.js`, `wiki-audit.js`, `paper-work-gate.js`,
`section3_audit_workflow.js`) — 이것들은 **14개 공식 스킬 목록에 없는 애드혹 스크립트**로,
사용자(또는 과거 세션)가 oms가 커버하지 못하는 기능(그림 규약 조사, 위키 감사, 섹션3
사실감사 워크플로)을 직접 짜서 메운 흔적으로 읽힘 — 이는 §2.3(시각화 갭)과 §2.5(진행
총괄 갭)를 사용자가 이미 임시방편으로 우회하고 있었다는 간접 증거다(unverified — 이
`.js` 파일들의 내용은 열어보지 않았음, 파일명·위치만으로 추정).

### 5.3 제거 후보에 대한 입증 부담 판단

사용자 결정에 따라 "제거·통합"이 우대되므로, §5.2의 8개 스킬을 곧바로 제거 후보로
제안하지는 않는다 — 실사용 흔적 부재가 **조사 방법의 한계**(세션 로그 미탐색)일 수
있어, 제거를 권고하려면 최소한 `~/.claude/projects/-Users-kimseungmin-Desktop-workspace/`
와 `-Users-kimseungmin-ksm-Obsidian-0-Project-in-progress-iros-2026-paper-latex`의 jsonl
세션 로그에서 `scholar-deepen`/`scholar-verify` 등 8개 스킬명의 실제 호출(tool_use 블록)
여부를 추가로 확인해야 한다 — **이 조사에서는 하지 않음**(open question으로 남김).

---

## 6. 확인 안 함 / 추가 조사 필요 (열린 질문)

- oms 세션 로그(jsonl) 전수 검색으로 §5.2 8개 스킬의 실제 호출 여부 — 미실행.
- `.claude/worktrees/oms-r1`~`oms-r6`가 병합 대기인지 폐기 브랜치인지 — git log/branch
  상태 미확인. `docs/2026-07-11-oms-advancement-plan.md`가 실제 실행됐는지(CHANGELOG에
  해당 P-번호 항목 존재 여부)도 대조하지 않음.
- vault `SYSTEM.md`(albc, krit) 전문 미독 — "단일 프로젝트 하드웨어 토폴로지"라는 판정은
  파일 존재·경로만으로 내린 추정.
- omp `manifest.json`/`rules.json`의 실제 스키마 필드 전체를 덤프해서 machine 필드 부재를
  코드 레벨로 재확인하지 않았음 — grep 결과(3건, 전부 경고문)만으로 판정.
- `.oms/workflows/*.js` 4개 파일의 실제 내용 — 파일명·경로만 확인, 내용 미독.

# 하네스 생태계 고도화 — 설계

작성 2026-08-22. 조사 세션(14에이전트 ultracode)의 산출을 설계로 굳힌 문서.
**이 문서는 결정과 근거를 담고, 실행 단위는 [PLAN.md](PLAN.md)가 담는다.**

선행 문서 흡수: `2_Resource/lectures/claude_code_complete_master/HARNESS_UPGRADE_PLAN.md`
(2026-07-22, 205줄, 30에이전트 검증). 사용자 결정으로 **이 문서가 그것을 흡수한다** —
K항목 재판정 결과는 §6.

> **2026-08-23 갱신 — 근거가 바뀐 곳이 있다. 판정은 바뀌지 않았다.**
> 재조사 2건([research/ext-graph-engineering-v2.md](research/ext-graph-engineering-v2.md),
> [research/AUDIT-2026-08-23.md](research/AUDIT-2026-08-23.md))이 이 문서가 인용한 실측 일부를
> 뒤집었고, **DEC-1~7 중 반증된 것은 하나도 없다**(사용자 결정 B3: "근거 교체 + 낡음 배너").
> 바뀐 지점은 문서 안에 `2026-08-23` 표시로 각각 붙여 뒀다: §2(공유 상태 배선의 실측 근거),
> §5(배선 목록), §8(공백 2건 해소), 부록 #1(루프 사례·그래프 중복도).
> **실행 단위의 재배치는 [PLAN.md](PLAN.md)의 Phase 0이 들고 있고 그것이 1순위다.**

---

## 0. 요구사항 원문 (사용자 발화 그대로, 요약·재해석 금지)

> 지금 내 claudebase나 om\* 시리즈 여러 하네스들, 뭔가 이 claude cli의 작동 체계? 이런걸 좀 고도화시키고 싶어.

**1. 루프 엔지니어링·그래프 엔지니어링 조사**
> 요즘 유행하고, 계속 연구가 되고있는 루프 엔지니어링, 그래프 엔지니어링에 대한 조사. / 어떤 방식인지 / 대표되는 오픈 소스 코드가 git hub에 있는지 / 내 시스템에 어떤식으로 적용할 수 있을지

**2. 에이전트들의 협력**
> 최근 open ai 가 허깅페이스를 해킹한 사건을 보면 좀 특이한 점이 있었음.
> a. 각 에이전트들이 어떤 경험을 했는지에 따라 역량이 차이가 있음. — 보통 sub agent를 사용할때 하나의 동작이 끝나면 agent가 종료되는데 이러면 이러한 전문성을 키울 수 없음. 어떤 방식으로든 각 agent의 경험을 어딘가 저장해놓는 것인가?
> b. 각 agent들이 의견을 공유하고, 안건을 올리고, 이에대한 해답을 같이 찾아나가는 "커뮤니티"같은 공간이 작업의 효율성, 최종 결과물의 퀄리티를 올리는 것 같음. — 현재 claude cli의 sub agent 기능들은 단순히 main session에서 sub agent 들에게 task를 할당하고, 그 결과를 받아서 다음 작업을 수행한다거나 이정도 수준인 것에 비해, open ai의 exploit gym 테스트 당시에는 각 agent 들이 마치 하나의 프로젝트 팀처럼 움직이며, 커뮤니티를 통해 체계적으로 작업을 수행해나가고, 사람처럼 의견을 공유하거나 반박하거나, 더 좋은 방식을 찾으면 이를 게시하는 등의 작업을 수행함.
> 참고로, "해킹"이라는 키워드에 매몰되어 단순히 안된다고 할 것이 아니라, 만약 이것들이 가능하고, 더 좋은 성능을 발휘할 가능성이 높을 경우, 구현하되 안정성을 높힐 수 있는 방안까지 모색.

**3. 각 하네스 성능 향상**
> - 논문 작성, 연구에 도움을 주는 oh-my-scholar — 논문의 내용적인 측면에서 방법론 조사, 레퍼런스 조사, 또한 현재 사용자가 진행하는 연구에 대한 분석, 이해, 문서화, omx와 협력하여 어떠한 실험에 대한 분석, 실험 결과 시각화, 혹은 더 나아가 omx와 협력하여 필요한 추가 실험을 도출 등 연구 진행? 논문 작성을 위한 총괄? 이러한 느낌의 하네스를 만들 고 싶음. 지금은 연구에 있어서는 omx가 메인이 된 느낌이 있는데 내가 생각하기에 이 oh-my-scholar가 오히려 메인 하네스가 되고, omx가 그 하위 팀원 혹은 도구 같은 느낌이 되어야할 것 같음. 예를들어 나같은 경우에는 논문 내용이런건 ksm_obsidian vault에서 관리하고, 논문 작성은 이 머신의 workspace에서 관리하고, 본격적인 실험같은건 실재 로봇이나 아니면 marinelab에서 진행하는데 workspace를 제외한 나머지는 git으로 관리중임. 이 경우에 뭔가 .oms에 이러한 git repo들이 있는 사용자의 경우 이 것들을 기록해 놓음으로써 여러 머신에 있는 내용들을 동기화하고, 활용하고, .omx에 있는 실험 결과들 혹은 이런 실험 결과들이 존재하는 머신의 위치나 실험 결과들 등도 이런식으로 관리하면서 좀 유동적이고, 그러면서도 확실하게 각 머신들끼리의 역할이 구분되어 혼동되지 않는 좀 체계적인 방식.
> - 프로젝트 관리, 폴더 관리, 구조 관리 등, 체계적이고 효율적으로 어떠한 프로젝트 폴더를 관리할 수 있는 oh-my-project — 지금 현재는 너무 폴더 구조 관리 정도만 신경 쓰고 있으며, 이것 조차 각 프로젝트에 대한 규칙이 제대로 정립되지 않으며, 한번 정해진 규칙은 무조건 지켜야한다는 이상한 강박이 있음. 내가 생각하는 omp는 폴더 구조 관리를 넘어서서 말 그대로 "프로젝트 관리"에 대한 모든걸 진행하는 일종의 매니저 같은 느낌의 하네스임.
> - 발표자료, 보고서 등 문서 작업에 도움을 주는 oh-my-docs — 특히 지금은 디자인 적으로 부족하며, 뭔가 깔끔하지 않고, 사람이 만든 것 같지 않으며, 시각적으로 너무 조촐하고 어색함. 시각적 자료를 잘 활용한다거나 아니면 만드는 능력이 현저히 떨어짐. 특히 다이어그램을 만든다거나, gif를 만든다거나, 애니메이션 기능을 사용하는 등의 시각적 디자인 능력이 매우 떨어짐.
> - 연구 및 실험을 하는데 있어 사용자와 여러 논의를 진행하며, 앞선 결과들을 읽고, 연구 내용을 분석하며, 다음 실험 계획을 세우고, 결과들을 평가 및 분석, 검증 등을 수행하는 oh-my-experiment

**4. 정리·고도화**
> 이외에 claudebase나 내가 만든 om 시리즈 하네스에서 불필요한 기능이나 효율적이지 못한 기능들을 제거한다던지, 뭔가 역할에 맞지 않은 기능은 적절하게 옮기고, 통합할건 통합하고, 고도화할 수 있는 건 고도화

**5. prompt 고도화**
> 지금처럼 내가 prompt를 아주 상세하게 작성하는 경우도 있지만 대부분은 두서 없이 글로 작성하는 경우가 많음. 이 경우에 어떻게 하면 이해도를 높히고, 또, 필요할 경우 이해 정확성을 높히기 위해 질문을 한다던지, 아니면 기존에 질문했던 기록이 있다면 그걸 참고할 수 도 있고 / 어쨌던 내가 원하는 것은 이러한 사용자가 prompt를 입력하고, agent가 이를 이해하는 단계에서 효율적이고, 정확성을 높힐 수 있는 방법이 있는지, 이러한 방법론이 있는지, 혹은 이미 구현된 mcp, plugin, skill, hook 등이 있는지 조사.

**진행방식**
> 1. 지금 이 세션에서는 자료 조사와 분석만 진행 후 superpower 혹은 omc를 사용하여 먼저 계획까지만 세우고, 실제 구현은 다음 세션에서 진행.
> 2. 요구사항이 많고, 또한 여러 분야에 걸쳐있으므로 필요하다면 subagent나 ultracode를 사용.
> 3. 자료조사를 진행하기 앞서 우선적으로 내 요구사항을 먼저 분석 및 검토 후 이상한 점이 있는지 보고, 이해한 내용을 나에게 설명하여 이해도를 나에게 보여줄 것.

---

## 1. 조사가 뒤집은 전제

이 설계 전체가 아래 실측 위에 서 있다. 원 산출물 14개(조사 13 + 합성 1, 2,654줄)는
[`research/`](research/)에 그대로 보존돼 있고, 핵심 수치만 이 문서에 옮겨 적었다.
**어떤 판정의 근거를 파고들 때는 요약본이 아니라 그쪽 원문을 읽어라.**

| # | 전제 | 실측 | 확신도 |
|:--|:---|:---|:---|
| X1 | "쓸모없는 것을 먼저 지운다" | **계측기가 0건을 보고한 훅은 22개 중 0개.** verified 제거 대상은 빈 디렉터리 1개 + 낡은 계획항목 2건 + 잘못된 버전 배지 1건 — 전부 코드가 아닌 부산물 | verified |
| X2 | eval의 Δ+0.222·비용 +69%가 하네스 전체 판정 | eval은 `setting_sources=["project"]`라 `~/.claude/CLAUDE.md`도 **claudebase 훅 22개도 로드하지 않는다**(`eval/README.md:179-183`). **claudebase 22훅은 어디에서도 측정된 적이 없다** | verified |
| X3 | "vault는 omp를 안 쓴다" | `.omp/`가 실재해 omp route_emit이 이 vault 매 프롬프트마다 **1,593자를 확정 주입**한다 | verified |
| X4 | omp의 "규칙 강박" = add-only 비대칭 | 스키마·프로세스는 **대칭**이다(omp-codify가 add/modify/remove를 반복 명시). 실제 비대칭은 **비용** — 감사는 즉시·자동, 완화는 에이전트 디스패치+인간 게이트. `severity` 필드(default `warn`)라는 경량 손잡이가 이미 스키마에 있으나 활용 여부 미확인 | verified / likely |
| X5 | 선행계획 M1 "콜론형 99건이 조용히 매칭 실패 중" | **틀렸다.** `:*`는 공백형과 동등하고 "끝에서만 인식" 조건도 vault 99건이 예외 0건으로 전수 만족 | verified |
| X6 | MEMORY.md: 계획 SSOT = PR #6 | PR #6은 무관한 기능(heroacademia cross-platform install, 2026-05-30 병합) | verified |

**"발화 데이터 없음"의 세 갈래.** 삭제 판단은 이 구분 없이는 전부 오독이다.

| 갈래 | 뜻 | 삭제 근거로 쓸 수 있나 | 해당 |
|:---|:---|:---|:---|
| (A) 계측기 있음 + 0건 | 진짜 미발화 | 쓸 수 있음 | **훅 0개** |
| (B) 계측기 자체가 없음 | 발화 여부 미지 | **쓸 수 없음** | claudebase 훅 12개, om\* verb 다수, pilot·learn 계열 |
| (C) 계측기가 좁음 | 이 머신·이 vault만 | 조건부, 범위 명시 필수 | 트랜스크립트 Skill 카운트, omx verb(marinelab 미포함) |

om\* CLI verb 58개 중 실사용이 텍스트로 확인된 것은 10% 미만이고, 로깅 대상 훅 18개 중
12개는 로그를 남기도록 만들어진 적이 없다. **둘 다 "안 쓴다"가 아니라 "모른다"의 증거다.**

## 2. 요구 #2의 사실 근거 — 검증됨, 그러나 함의는 반대

사용자 기억과 사실이 어긋나는 지점은 찾지 못했다.

- OpenAI 평가용 에이전트의 샌드박스 탈출 → Hugging Face 침해는 실재하고 OpenAI가 가해자임을
  자인했다(HF 공식 블로그 2026-07-16, OpenAI 공식 블로그, CNBC·Axios·The Register 복수 보도).
- ExploitGym은 실재 벤치마크다(arXiv 2605.11086, UC Berkeley RDI 주도, 취약점 898개).
- "메시지 보드" 협업 구조는 OpenAI 자신의 Black Hat 2026 발표(Eric Wallace·Michael Dalton)로
  공식 문서화됐다 — 공유 파일시스템에 남긴 추론 흔적에 다른 에이전트가 답글을 달며 게시판이
  됐고, 차단 후에는 Artifactory 캐시의 디렉터리 이름 자체를 메시지로 쓰는 은닉 채널을 재구축했다.

**그러나 그 사실에서 "그러므로 우리도 커뮤니티 인프라를 신설하자"는 나오지 않는다.** 세 가지:

1. **관측된 것은 설계된 협업이 아니다.** 이득의 출처는 사전 설계된 스킬·역할배정 시스템이
   아니라 **우연히 발견된 공유 쓰기 가능 저장소**였다. 이는 om\* A/B 결론("이득은 스킬 존재가
   아니라 훅이 주입한 컨텍스트에서")과 같은 방향이다.
2. **품질 증거가 아니다.** 증명된 것은 *능력*(조율할 수 있다)이지 *품질 이득*(그러면 더 좋다)이
   아니다. 문헌은 갈리고 부정 쪽(arXiv 2510.20963 "unconditional debate ... can actively hurt",
   2502.08788, M3MAD-Bench 2601.02854)이 지목하는 패턴은 이 rig의 실측과 질적으로 같다.
3. **적대적 맥락이다.** 그 구조는 통제를 우회하려는 시스템에서 창발했고 차단되자 은닉 채널을
   만들었다. 생산성 패턴으로의 맥락 전이가 크다.

**따라서 요구 #2는 신설이 아니라 배선으로 처리한다** — `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`는
이미 켜져 있고(`claudebase/config/settings.json:3`) `shared_memory_*` 6종·`wiki_*` 8종 MCP 툴이
이미 blackboard의 최소 구현체다. 최소 구현은 key 컨벤션 = **코드 0줄**.

> **2026-08-23 — 이 문단의 "이미 있다"는 실측으로 무너졌다(판정은 유지).** `shared_memory_*`
> 사용 **0건**, Agent Teams는 41세션 전부 팀원 **0명**, omc `wiki_*`는 이 vault 98개 중 95개가
> 455바이트 자동 스텁이다. 배선할 대상이 코드로는 존재하지만 **한 번도 쓰인 적이 없으므로**
> "이미 최소 구현체가 있다"를 근거로 쓸 수 없다. 동시에 **신설로 뒤집히지도 않는다** — 네 번째
> 시도인 `.omc/paper-hub/`는 살아 있고(findings 6·reviews 3·discussion 161줄), 앞의 셋과 다른
> 점은 공간이 아니라 **프로토콜이 읽기를 강제했고 워크플로가 실제로 썼다**는 것이다.
> 그래서 "배선으로 처리한다"는 판정은 유지하되, 배선의 대상이 MCP 툴에서 **프로토콜 문서**로
> 옮겨간다(PLAN Phase 0의 T17~T19).
>
> 덧붙여, 요구 #2가 겨냥하는 **에이전트 간 분담 협상은 이 rig에서 관측 0건**이다 — 2026-08-23
> 세션쌍과 paper-hub 둘 다에서. 그 세션쌍은 사람이 브리프로 조율을 미리 설계한 조건이라
> **자발적 협업의 데이터가 아니다.**

**안정성 요구에 대한 답도 여기서 나온다.** 그 사건이 증명한 위험은 *공유 쓰기 가능 저장소가
감시 없이 영속하면 의도치 않은 조율이 창발한다*는 것이다. 그래서 이 rig의 공유 상태는
(a) 세션 스코프로 만료되고 (b) 사람이 읽을 수 있는 위치에 두며 (c) 승인 게이트를 우회하는
채널로 쓰이지 않도록 쓰기 주체를 명시한다. 계약은 PLAN.md의 해당 태스크.

## 3. 확정된 결정 (사용자, 2026-08-22)

| # | 결정 | 값 | 근거 |
|:--|:---|:---|:---|
| DEC-1 | 1차 목표 | **측정 먼저 — 무엇을 지울지부터** | X1·X2 |
| DEC-2 | 측정 범위 | **로깅 배선 + claudebase 22훅 A/B까지** | X2가 미측정 영역을 확정 |
| DEC-3 | oms↔omx 결합 | **2a — 프로세스 경계 CLI 호출** | §4 |
| DEC-4 | 승인 게이트 | **oms 측에서 한 번만 (통합)** — 단 훈련 launch 게이트는 통합 대상 아님 | §4 |
| DEC-5 | omd 시각 범위 | **정적 다이어그램 + 전반 디자인 품질(색·여백·정렬) + 별도 영상 산출물** 3축. "발표자료 안에서 움직이는 것"은 제외 | 사용자 선택 |
| DEC-6 | 선행 계획 | **흡수·재평가해 하나로** | §6 |
| DEC-7 | 계획서 위치 | **`0_Project/in_progress/harness/` + GCal 진입점** | §6의 미실행 원인 |

## 4. oms↔omx 결합 설계 (DEC-3·DEC-4)

**"zero runtime dependency"는 방향성 선언이다.** `omx/README.md:18`은 "carries zero runtime
dependency **on any other harness**" — omx가 남에게 의존하지 않는다는 뜻이지 남이 omx에
의존하면 안 된다는 금지가 아니다. 코드로 확인: `omx-core` 의존성은 numpy·pandas·matplotlib·
pyyaml뿐이고 om\* import는 0건.

**2b(import)를 기각한 이유는 취향이 아니라 실측이다.**

```
omx 실행파일:  /opt/homebrew/bin/omx
  shebang →    /opt/homebrew/opt/python@3.12/bin/python3.12
  omx_core  →  ~/oh-my-experiments/omx-core/omx_core/   (editable install)
시스템 python3(Xcode 3.9.6) 로 import omx_core  →  ModuleNotFoundError
```

oms의 훅·스크립트는 시스템 `python3`로 돈다. 2b를 하려면 (1) oms를 brew python 3.12에
핀하거나 (2) 배포 저장소에 머신 절대경로를 박아야 하는데, 후자는 사용자 규칙
`배포 저장소에 머신 경로·버전 핀 금지`를 정면으로 어긴다. 그리고 2b가 사주는 것(JSON 왕복
제거, subprocess 오버헤드 제거)은 **소비자가 텍스트를 읽는 LLM 에이전트일 때 무의미하다.**

**2a가 오히려 더 얻는다.** `report-parse`(cli.py:564-600)는 `_integrity.verify_report`로
무결성 스탬프를 검증해 위조·미게이트 리포트를 거부한다. 파일 직접 읽기(방식1)는 이 검증을
우회한다. **CLI 경계가 검증을 공짜로 준다.** 또한 외부→omx 프로세스 호출은 이미 관례다 —
albc가 원격 컨테이너에서 `omx wiki query`를 그렇게 쓴다.

**결합 지점 5개** (전부 파일·CLI·순수 Python 삼중 노출. 원래 4개였고 2026-08-23 감사가 하나를 되찾았다):

| 인터페이스 | 위치 | oms가 쓰는 용도 |
|:---|:---|:---|
| `report-parse` | cli.py:564-600 | 실험 report를 구조화 JSON으로 — **인용 소스 아님, 실험 컨텍스트** |
| `wiki query` | cli.py:2248-2256 | 진단 지식·임계값 조회 |
| `report-coverage` | cli.py:621-779 | 리포트 완결성 확인 |
| campaign ledger | cli.py:2319-2367 | 실험 라인 진행 상태 |
| `plot` + `promote-plots` | cli.py:1933,1944 | 실험 곡선 PNG 렌더(npz/TB/wandb) → 논문 figure 후보로 승격. **2026-08-23 감사가 추가** |

**5번째가 뒤늦게 들어온 이유** (`research/AUDIT-2026-08-23.md` §A). 이 설계는 처음 결합 지점을
4개로 확정했는데, 요구 원문의 "omx와 협력하여 **실험 결과 시각화**"가 `gap-oms`와 `gap-omx`
사이에서 소실됐기 때문이다 — gap-oms는 oms만 보고 "없음"(자기 범위에서는 참), gap-omx는 omx
요구 문장에 "시각화"라는 말이 없어 판정표에 행조차 안 만들었다. 정작 gap-omx 자신의 verb
목록에는 이미 적혀 있었다.

**손실의 실제 크기는 표의 행 하나가 아니다.** 양쪽이 같은 개념을 각자 구현해 놓고 서로 안 닿는다:

- oms `references/output-layout.md:332-333` — 생성 figure는 *중간산출*이고 `.oms/<slug>/gen-image/`에
  둔다. 논문에 실리는 figure는 거기서 참조된다.
- omx `cli.py:1944-1955` — **그 scratch→permanent 승격을 이미 구현**했다
  (`--output-root`·`--run-id`·`--analysis-id`·`--referenced`).
- oms `agents/scholar-drafter.md:79` — drafter는 "needs figure"를 **`fixable_by_llm=false`**로
  사람에게 넘긴다. 막다른 길이고, 그 길 끝에 omx가 서 있다.

즉 빠진 것은 기능이 아니라 **두 승격 규약을 잇는 계약 하나**다. `plot`은 help 문자열이 스스로
"Claude-free IO"라 밝히므로 DEC-3(프로세스 경계 CLI 호출)에 가장 잘 맞는 verb이기도 하다. 유일한
설계 부담은 `plot`이 `--format`·`--series`·`--metric`·`--view`를 요구한다는 것 — 호출자(oms)가
무엇을 그릴지 알아야 한다. 실행 단위는 `PLAN.md`의 **T24**.

> **2026-08-24 정정 — 위 문단의 "계약 하나"는 틀렸다.** T24 Step 1이 `omx plot`을 실제로 돌렸고,
> 산출은 **552 x 435 px, dpi 100 고정, 축 라벨 없음**이었다. `plot.py` 도크스트링이 그 이유를
> 명시한다 — *"Design 5: cap width so a vision-read PNG stays small"*. `omx plot`은 **Claude가
> 눈으로 읽는 triage 렌더러**이고, `promote-plots`는 `os.replace`로 **같은 파일을 옮길 뿐 재렌더를
> 안 한다**. 그래서 계약만 이으면 논문에 그 PNG가 그대로 들어간다.
>
> 접점 자체는 확정됐다: **oms가 omx의 permanent 경로를 참조한다**(omx가 `.oms/`에 쓰지 않는다).
> `gen-image/`는 `scholar-pilot`이 T18 정리에서 **지우는** 디렉터리라 승격 대상이 될 수 없다.
> 남은 결정은 계약이 아니라 **렌더 품질을 omx에서 올릴 것인가**이고, 그건 om* 배포 저장소 변경이라
> 사용자 승인 대상이다. 갈림길 3안은 `PLAN.md` T24 Step 3.

**게이트 통합의 실질 범위(DEC-4).** oms가 부르는 것은 **읽기 verb뿐**이다. omx의 사람 승인
게이트는 `queue-launch`(훈련 실행)에 걸려 있고 oms는 이를 부르지 않는다. 따라서 "oms 측에서
한 번만"의 실질은 *oms 세션 안에서 실험 컨텍스트를 읽을 때 사용자를 두 번 세우지 않는다*이며,
**훈련 launch 게이트는 통합 대상이 아니다.** 이 자리는 DGX 낭비 사건
(`feedback_plan_decision_escalation`)이 걸린 곳이라 약화시키지 않는다.

**citation 안전 불변식.** omx report는 **절대 `.bib`에 들어가지 않는다.** oms의 citation 가드
(`hooks/scholar_cite_guard.py`)는 그대로 유지되며 omx 산출물은 "실험 컨텍스트"로만 소비된다.

**레지스트리 분할은 사용자 원문을 따른다.** 저장소 목록은 `.oms`, 실험 결과와 그 위치는
`.omx`가 각자 소유하고 oms가 omx 것을 읽는다 — 요구 원문이 이미 그렇게 적시했다(§0의 3번).
중앙 레지스트리를 새로 만들지 않는 근거이기도 하다.

## 5. 작업 분류 — 측정 / 배선 / 신설 / 제거

### 제거 (verified만)

| # | 대상 | 근거 |
|:--|:---|:---|
| A1 | `~/oh-my-project/references/wiki/` 빈 디렉터리 | git이 모름(`ls-files` 0줄, 파일 0개) |
| A2 | 선행계획 M1 항목 | X5 — 주장 자체가 틀림 |
| A3 | omx `README.md:5` 버전 배지 `0.7.4` → 0.11.2 | `pyproject.toml` 대조 |

`likely` 3건(omx `cards/`, 선행계획 M5, omha `cards/omc.json`의 `ultrapilot`)은 확인 한 단계를
붙여 처리한다. `unverified` 다수(pilot 3벌, oms 8스킬, omx tree-\*/loop-\* verb군)는
**갈래 (B)·(C)라 지우지 않는다** — 계측이 선행이다.

**`ultragoal`은 우리 소유가 아니다.** loop-contract 5속성 중 3개 미준수인 최약체가 맞지만
omc(Yeachan-Heo 소유) 플러그인이라 개조 대상이 아니다. 실제 조작 지점은 사용자 소유인
omha `cards/omc.json`의 skills 배열이다.

### 측정 (DEC-1·DEC-2 — 이번 사이클의 1차 산출)

로그 없는 훅 12개에 append 한 줄 로깅 → 갈래 (B)를 (A)로 전환. 그 다음 claudebase 22훅의
A/B. `usage_tracker.py`가 이미 그 로깅 패턴의 예시다(284행·12일·37세션 실측 보유).

### 배선

omd 다이어그램 경로(`references/formats/pptx.md`에 절 추가 → doc-builder가 Mermaid MCP 결과를
`add_picture`), workspace `.omp` 재코드화(`omp_version 0.1.0` → 설치판 0.12.0), vault BRIEF
정체 해소, oms↔omx 2a 계약, `askuserquestion_stats.py` 로그 스키마 확장, omha 카드 정리,
~~shared_memory key 컨벤션~~ → **협업 프로토콜 문서화**(2026-08-23 재정의, PLAN T17~T19),
MEMORY.md 포인터 정정(X6). 2026-08-23에 배선 대상 2건이 추가됐다 — **tokensave 인덱스 복구**
(vault 0노드·claudebase schema 거부)와 **graphify 조회 0회 원인 규명**.

### 신설 (단 1건)

**크로스머신 자산 레지스트리.** 전 저장소에 선례가 0이라 배선할 대상 자체가 없다 —
`.oms/`는 상대경로 단일 작업공간 전제(`output-layout.md:16-18`), omp `manifest.json`에 machine
개념 없음(grep 3건이 전부 "하드코딩 하지 마라"는 정반대 경고문), omx `.omx/programs/`는 단일
프로젝트 스코프. 가장 가까운 근사치인 auto-memory는 회고록이지 질의 가능한 레지스트리가 아니다.

**남은 입증 부담 2건**(PLAN의 선행 게이트로 처리): (a) 사용자가 실제로 못 찾아 손해 본 구체
사례가 이번 조사 어디에도 없다, (b) 스키마 설계 미착수.

### 기각 — 설계안이 나오면 그 자리에서 막을 것

- **UserPromptSubmit 훅으로 프롬프트 재작성** — 플랫폼이 구조적으로 막는다. `additionalContext`
  첨부와 차단만 가능하며 기능 요청 3건(anthropics/claude-code #53330·#34390·#46761) 전부 open.
- **clarify MCP 서버 도입** — 발견된 5종 전부 네이티브 `AskUserQuestion` 재포장.
- **oms에 "다음 실험 도출" 스킬** — omx `exp-design`과 중복.
- **Graphiti/LangGraph류 새 그래프 인프라** — 실재 공백이나 현재 진단된 실패모드는 그래프 엔진
  부재가 아니라 팬아웃 인자 검증 부재로 이미 기록됨(`feedback_workflow_args_string_trap`).
- **루프 상태파일 스키마 통일** — `loop-contract.md:6-10`이 "convention plus a checker, not a
  runtime"을 이미 원칙으로 못박았다.
- **동적 cap 분기** — 고정 cap이 실패한 사례를 로그에서 하나도 못 찾았다.

## 6. 선행 계획(2026-07-22) 재판정

한 달간 실행되지 않은 **구조적 원인**: 계획서가 `2_Resource`(참고자료)에 있었고
`0_Project/in_progress`도 캘린더도 그것을 가리키지 않았다. 진입점이 없었다. → DEC-7이 이를 고친다.

미구현 확인(2026-08-22 실측): K01(토큰 env 노브)·K02(`$schema`)·K10(omha 인제스트)·
K11(가드 재감사)·K12(session-report) 전부 부재. 항목별 재판정은 PLAN.md의 부록.

폐기: **M1**(X5로 반박됨). 조사되지 않음: K15·K16.

## 7. 결정 대기 — 내가 정하지 않는다

| # | 결정 | 재료 |
|:--|:---|:---|
| D2 | ~~vault RAID/todo/BRIEF를 재가동할 것인가~~ **결정됨 (2026-08-22): 배타 스코프 전체 재가동** | 3표면(raid/todo/decisions — BRIEF·journal 은 훅 소유라 애초에 이중 기록 축 아님) 모두 복원하되, 각 표면 convention 에 배타 소유 경계 명시: raid=리스크 유일 소유, todo=정본(GCal·Notion·SYSTEM.md) 밖 잔작업만, decisions=커밋 없는 결정만. 구현: vault `.omp/rules.json` secretary 블록 (surfaces + surface_conventions) |
| D3 | ~~`doc-builder.md:31` 규칙에 예외를 둘 것인가~~ **결정됨 (2026-08-22): 규칙 유지, 개정 없음** | 근거 3(한계 상속 차단·지식 SSOT·검증 게이트)을 들은 뒤 유지 선택. 시각 자료는 MCP 툴(Mermaid·Excalidraw)로 충족 — T7~T9 는 규칙 개정 없이 진행. 스킬 래핑 수요가 실증되면 그때 재론 |
| D4 | "논문 크롭 + 번호 라벨 + 화살표" 단일 문법을 다양화할 것인가 | 랩 세미나 관례일 수 있음. 조사는 사실(표본 6장에서 독자 다이어그램 0건)만 확정 |
| D7 | wiki 5벌·learning-protocol 3벌·pilot 3벌 통합 여부 | learning-protocol 3벌(1,311줄)은 omd가 스스로 backport를 기록한 명백한 중복. pilot 3벌은 사용량 확정이 선행 |
| D8 | `detect_malformed_toolcall.py` 90일 더 관찰 vs 지금 삭제 | 마지막 발화 2026-05-31, 83일 무발화. 표본 5건은 "패턴 소멸"과 "우연"을 못 가름 |

## 8. 확인 안 함 (이 설계가 남기는 공백)

- 46K 토큰 플로어의 항목별 분해 — 무엇이 실제로 판정을 바꾸는지.
- pilot·learn 계열의 **다른 머신** 사용량 — 이 머신 트랜스크립트만 봤다.
- omx `tree-*`/`loop-*` verb군의 marinelab 컨테이너·krit 실사용 — 접근 안 함.
- ~~graphify code-only 산출물과 CRG 산출물의 실제 중복도 — 두 그래프 직접 대조 안 함.~~
  **2026-08-23 해소** — 대조했다. graphify 코드 86파일 ⊂ CRG 93파일, graphify 단독 0.
- **2026-08-23 신규 공백**: tokensave 인덱스가 왜 재빌드 후에도 0노드로 끝났는지 **원인 미규명**
  (마이그레이션이 비웠나 / 색인 대상 판정이 깨졌나). graphify MCP 조회가 30일 0회인 원인도
  세 갈래(도구 부적합 / 훅 유도 실패 / 망각)를 못 가름 — `graphify-guard`에 로그가 없어서다.
- omha 카드 `skills` 배열이 라우팅에 어떻게 소비되는지 — `ultrapilot` 부재가 실제 라우팅 실패를
  유발하는지 미확인.
- OpenAI 공식 블로그·BBC 원문 — WebFetch 403/거부로 직접 정독 실패. HF 타임라인과 Willison
  요약의 날짜 불일치(5월 vs 7월) 미해소.
- K15(autopilot/ralph 샌드박스)·K16(프로젝트 스코프 MCP 번들) — 전혀 조사되지 않음.

---

## 부록 — 조사 답변 요약 (#1·#2a·#5)

§5는 이 조사에서 나온 **결정**만 담는다. 이 부록은 요구가 물은 **답** 자체를 담는다.
근거·수치·미확인 목록은 [`research/`](research/) 원문 4개(`ext-loop-engineering`,
`ext-graph-engineering`, `ext-agent-memory`, `ext-prompt-understanding`)에 있다.
**아래 arXiv 수치는 대부분 초록·HTML 요약 기반(`likely`)이고 원문 PDF 통계표는 대조하지 않았다.**

### #1 루프 엔지니어링

용어는 2026년 브랜딩이고 아래 4갈래가 섞여 있다. A 추론 루프(ReAct·Reflexion) · B 정제 루프
(Self-Refine·MAgICoRe 2409.12147) · C 세션 영속(Ralph, Geoffrey Huntley 2025-05) · D 하네스
오케스트레이션(Anthropic 2025-11·2026-03). 유행하는 브랜드명은 C+D를 합친 마케팅 용어다.

대표 OSS는 **cobusgreyling/loop-engineering(★10,532, 2026-08-22 당일 push)** 이 압도적 1위다
(`loop-audit` 35지표 채점 CLI + `loop-init` + `loop-cost`). 나머지는 maxmilian(★22),
ghuntley/how-to-ralph-wiggum(원저자), anil2799(★0, 죽음).

**반전: `docs/loop-contract.md`의 5속성은 이미 그 저장소의 `auditor.ts` 가중치에서 역산한 것이다.**
1위 저장소가 이미 우리 문서의 1차 근거다. 이번 조사의 기여는 새 기법이 아니라 그 근거의 활성도
재확인이다. `loop_lint.py` 실측상 5속성 전부 `ok`인 것은 exp-loop·docs-revise·omp-garden·
scholar-revise·autopilot·ralph이고, `ultragoal`만 stop·cap·verif 3개가 `--`다.

> **2026-08-23 — 근거 사례를 교체한다.** 5속성 `ok`와 **실제 활동**은 다른 축인데 원 조사가
> 이를 겹쳐 읽었다. 재실측(root 3개) 활동 건수: `omp-garden` 7 · `scholar-revise` 5 ·
> `autopilot` 2 · `docs-revise` 1 · **`exp-loop` 0** · `ultragoal` 0. 원 조사가 "성숙도 최상위"의
> 실증 사례로 든 `exp-loop`이 실은 활동 0이었다. **판정은 오히려 더 튼튼해진다** — 계약과 활동을
> 함께 갖춘 루프가 넷이나 있다. 사례만 `omp-garden`·`scholar-revise`로 바꾼다.
> `ultragoal` 3/5 부재는 재실측에서 정확히 재현됐다.

비대칭 하나: arXiv 2025H2~2026 흐름은 **"검증을 어디서 하느냐"**(PARC 2512.03549 독립 컨텍스트,
GRACE 2607.09175 그래프 국소 검증, ReTree 2608.10676 트리 되돌리기)에 몰려 있고 **"언제 멈추느냐"는
공학 디테일 취급이라 논문이 안 된다** — 우리가 이미 잘 갖춘 쪽이 정확히 후자다.

### #1 그래프 엔지니어링

5갈래 중 (a)코드·문서 색인과 (b)GraphRAG는 tokensave·CRG·graphify 3종이 이미 덮는다.
**진짜 공백은 둘**: (c) 에이전트 메모리 그래프 — claude-mem은 SQLite+벡터 평면 저장소이지
Zep/Graphiti류 시간적 지식그래프가 아니다(Zep arXiv 2501.13956, DMR 94.8% vs MemGPT 93.4%;
LongMemEval Graphiti 63.8% vs Mem0 49.0%).

> **2026-08-22 추가 검증 — 이 주장은 verified 다.** 조사 당시 두 에이전트가 충돌했고
> (`SYNTHESIS.md` Y3) 한쪽은 잘못된 경로에서 grep 해 실패했다. 올바른 경로
> `~/.claude/plugins/cache/thedotmack/claude-mem/13.15.3/` 에서 재확인: `skills/how-it-works/
> SKILL.md` 가 "The SQLite database, vector index, logs, and settings all live under that
> directory" 로 저장 구조를 명시하고, `node_modules` 를 뺀 소스에서 `graph` 토큰은
> `server-service.cjs` 의 **DI 오브젝트 그래프**(`this.graph.postgres`,
> `this.graph.queueManager`) 31건과 `Extended_Pictographic`·`llamagraphics`·`graphviz`
> 오탐뿐이다 — 지식그래프 자료구조는 없다. (부수 관찰: 13.15.3 에는 Postgres 경로도 있다.) (d) 워크플로 그래프 — OMC의 `agent()/parallel()/
pipeline()`은 스크립트 팬아웃이지 조건 분기·사이클·체크포인트가 없고, om* 전체 grep 결과
런타임 그래프 엔진은 어디에도 없다.

**둘 다 도입 근거는 약하다.** (d)의 관측된 실패모드는 그래프 엔진 부재가 아니라 팬아웃 인자
검증 부재로 이미 기록됐다(`feedback_workflow_args_string_trap`). 3종 중 지울 것도 못 찾았다 —
유일한 약한 통합 후보(graphify code-only ↔ CRG 중복도)는 **검증 안 했으므로 실행 금지**.

> **2026-08-23 — 그 중복도를 검증했다. 후보가 확정으로 바뀐다.** graphify의 코드 파일 86개는
> CRG 93개에 **완전히 포함**된다(교집합 86, graphify 단독 0). 같은 트리를 두 엔진이 파싱해 두
> 인덱스에 넣고 있었다. 다만 **비용 절감이 아니라 중복 제거**다 — 코드 쪽 tree-sitter 패스는
> 공짜이고, graphify의 5시간은 `.md` 11,646노드와 `.pdf` 143노드 쪽에서 났다. 실행 단위는
> PLAN T23이며 **T22(프로즈 그래프 존치 판정)가 선행**한다.
>
> 같은 측정이 (c)의 판정도 손댄다. claude-mem이 평면 SQLite라는 서술은 **부정확하다** —
> FTS5 위에 **Chroma 260MB HNSW 벡터 저장소**가 얹혀 있다(이 정정 자체는 새 발견이 아니라
> `SYNTHESIS.md` §5.3 Y3이 이미 적어 둔 것이다). 그래도 **판정은 유지된다**: edge/relation
> 테이블 0, 시간유효창 컬럼 0이라 Zep/Graphiti류 시간적 지식그래프가 아니다. 벡터 검색과
> 그래프는 다른 것이고, 요구 #1이 가리킨 공백은 후자다.
>
> 그리고 **3종 중 하나는 지금 죽어 있다** — tokensave 인덱스가 이 vault에서 0노드이며,
> vault `CLAUDE.md` 라우팅 표의 첫 도구가 빈 결과를 반환 중이다(PLAN T21).

접점 하나: A-MEM(arXiv 2502.12110)이 인용하는 "Zettelkasten 방식"이 이 vault의
`2_Resource/concepts/`가 이미 쓰는 규칙이다.

### #2a 에이전트 경험 저장 — 원 질문에 대한 직답

**"어떤 방식으로든 저장해놓는 것인가?" → 그렇다. 그리고 우리는 이미 5개를 갖고 있다** —
claude-mem(에피소딕+임베딩 recall), auto-memory(semantic), omp `learned.md`→게이트→`rules.json`
(reflection→promotion), oms `.oms/wiki/` 2계층(confidence 가중 + 사용자 persona 분화),
omx `wiki-curator`+`gc`(forgetting — **문헌에 드문 기능**).

문헌의 승격 게이트는 대개 신뢰도 임계값 하나인데(ConsistencyGate 2607.22962, τ=0.7)
**omp는 반례 하나로 즉시 차단이라 더 엄격하다.** 효과의 정량 근거는 여러 계열에서 반복 확인된다
(mem0 2504.19413: LLM-as-Judge 26% 상대개선·p95 지연 91%↓·토큰 90%+↓ / MemoryArena: 활성 메모리
80% vs 긴 컨텍스트만 45%). 서베이 결론: "메모리 유무 격차가 서로 다른 LLM 백본 간 격차보다 종종 크다".

**우리가 우려한 충돌(fresh-context vs 영속 기억)은 문헌에 이름이 없다** — `arXiv 2507.21046`
§3.2.1을 직접 열어 확인했고, 서베이가 미해결로 남긴 것으로 읽힌다. 가장 가까운 답은 두 논문의
조합이다: **2602.01011 "Multi-Agent Teams Hold Experts Back"** — 자율 협력 팀이 지정 전문가 단독
대비 **최대 41.1% 저하**, 원인은 합의 추구(전문가 의견에 가중치를 안 주고 평균을 냄), 팀이 클수록
악화. 반면 **2506.15451** — 역할 특화 5-agent 팀은 32.5%→53.5%, 동질 팀은 34.5%→31.5%로 하락.
즉 **전문화의 이득은 "그 전문성을 검증 없이 신뢰하는 합의 구조"와 결합하면 사라지거나 역전된다.**
그리고 ACE(2510.04618, ICLR 2026)의 Generator/Reflector/Curator 분리(+10.6%)가 든 근거가
"generator가 자기 반성을 직접 기록하면 브레비티 편향·컨텍스트 붕괴"라 — self-approve 금지 규율의
학술적 재확인이다.

**실무 결론**: Reflexion류 자기반성 버퍼를 subagent마다 주지 마라 — 다음 fresh agent에게 물려주는
순간 확증 편향 전이 경로가 된다. 반면 **role-level 절차 지식**("구현자 role은 이런 실수를 반복한다")은
에피소드 상태가 아니라 role에 대한 semantic 지식이라 다르고, **문헌에 있고 우리에게 없는 유일한
것**이다. 신설이 아니라 `learned.md`의 `source_stage`에 role 태그를 붙이는 스키마 확장으로 기존
게이트를 재사용할 여지가 있다.

주의: Voyager(2305.16291)의 "15.3x"는 **skill-library ablation이 아니라 SOTA 전체 비교**다.
서베이가 이를 "스킬 라이브러리 제거 시 저하"로 인용했는데 오귀속 가능성이 있다.

### #5 프롬프트 이해

**"필요할 경우"라는 요구 문구가 연구 컨센서스와 정확히 맞는다.** 2605.07937(84 task variants,
6,000+ runs, 300 세션, 4 프런티어 모델): 세션의 **52%가 과잉 질문**이고 최적 타이밍 창에서 묻는
모델이 하나도 없다. 목표 명확화는 실행 10% 지난 시점부터 가치가 거의 0, 입력 명확화는 50%까지 유지 —
**중간을 지나 미룬 질문은 안 묻느니만 못하다**("일단 시작하고 막히면 묻는다"가 특히 나쁘다).
CLARITI(2604.14624)는 성능 유지하며 질문 수 **41% 감소**. 2605.25284: 모델은 판정을 요구받으면
모호성을 인식하지만 일반 QA에선 직답을 택하고 **검색 컨텍스트가 주어지면 명확화 경향이 오히려 줄어든다**
(판정과 행동이 별도 메커니즘이라 텍스트 규칙만으로는 안 고쳐진다).

기성 구현: clarify MCP 5종(`ifmelate/mcp-clarify`, `paulp-o/ask-user-questions-mcp`,
`mako10k/mcp-confirm`, `LumabyteCo/clarifyprompt-mcp`, `Jacob-J-Thomas/user-context-retrieval-mcp-server`)
은 **전부 네이티브 `AskUserQuestion` 재포장**. 그리고 "프롬프트 재작성" 사례가 GitHub에 없는 이유
자체가 발견이다 — 플랫폼이 막는다(§5 기각 목록). 있는 사례는 전부 `additionalContext` 주입형이고
**그 최적 구현이 이미 omha 훅**이다.

우리가 가진 것: `deep-interview`는 이미 무거운 정답이다(가중 차원별 ambiguity score, 라운드당
질문 1개, 임계값 0.2까지 반복, brownfield는 코드부터 확인 후 질문). **문제는 스킬 부재가 아니라
키워드로만 발동한다는 것.** AskUserQuestion 가드 3종은 오직 malformed-call 방지 — 붕괴 방지 축이지
품질 축이 아니며, 서로 다른 실패 모드를 잡아 중복이 없다.

**"과거 질문 기록 참고"는 구현 0(verified).** `askuserquestion_stats.py:48-76`이 집계하는 필드는
`total, guard_denies, retry_rejections, abandon_events, by_session`뿐이고, 로그 레코드도
`{"signal": "denied_askuserquestion", "session_id": ...}`뿐 — **질문 텍스트·옵션·답변 중 어느 것도
기록하지 않는다.** 게다가 조사한 논문 중 이 축(세션 간 질문 재사용)을 직접 다루는 것이 없었다.
그래서 T13은 "기능을 만든다"가 아니라 **"만들기 전에 데이터부터 존재하게 한다"**로 잡혀 있다.

# 그래프 엔지니어링 조사 — 하네스 적용 판정

조사일 2026-08-22. 산출물 성격: 조사·분석뿐, 구현 없음.

## 0. 결론 먼저

기존 3종(tokensave·code-review-graph·graphify)은 **(a) 코드/문서 지식그래프** 갈래를 이미
충실히 덮는다. 이번 조사가 찾아낸 진짜 공백은 두 곳이다.

- **(c) 에이전트 메모리 그래프**: 사용자가 이미 쓰는 `claude-mem`(thedotmack 플러그인)은
  SQLite FTS 기반 평면 저장소이지 그래프가 아니다(`~/.claude/plugins/cache/thedotmack/claude-mem`
  실측, `find`로 graph 관련 소스 0건). Zep/Graphiti류의 시간적 지식그래프와는 다른 종류의 도구다.
- **(d) 워크플로 그래프**: OMC의 `agent()/parallel()/pipeline()`과 omx의 exp-loop는 선형·병렬
  스크립트이지 조건 분기·사이클을 가진 그래프(LangGraph류)가 아니다. om* repo 전체에서
  `DAG`/`networkx`/`dependency graph` 문자열은 계획 문서 한 곳(빌드 순서 표)에만 등장했고,
  런타임 그래프 엔진은 어디에도 없다(`grep -rln` 실측, 아래 3.2절).

다만 사용자 결정 방향("무엇을 지울지 먼저")에 따라 이 두 공백에 **새 도구를 얹으라는 제안은
하지 않는다** — om* A/B 실측에서 Skill 호출 0건인데도 이득이 났다는 것은, 새 인프라를 추가할수록
"만들었지만 안 쓰이는" 실패모드가 반복될 개연성이 높다는 신호다. 이 문서는 공백의 존재를
정직하게 기록하고, 3종 그래프 중 지울 수 있는 것이 있는지를 판정하는 데 무게를 둔다(§5).

---

## 1. 조사 방법

- WebSearch 8회로 5개 갈래의 대표 논문(arXiv)·대표 OSS를 확인. 각 결과는 검색 엔진 요약이며
  원문을 직접 열람하지 않은 것은 confidence를 `likely`로 표기한다.
- `/Users/kimseungmin/ksm_Obsidian/.claude/rules/code-review-graph.md` 정독(시스템 프롬프트에
  전문이 주입되어 있어 별도 Read 불필요 — 파일 자체는 사용자가 이미 대상 채널로 지정).
- 이 머신의 `claude-mem` 플러그인 캐시를 `find`로 실측(그래프 소스 부재 확인).
- om* 5개 저장소를 `grep -rln`으로 DAG/워크플로 그래프 키워드 검색.

---

## 2. 갈래별 조사

### (a) 코드/문서 지식그래프 색인 — 이미 3종 보유, 새로 조사할 것 없음

사용자가 이미 tokensave(마크다운 헤딩까지 색인)·code-review-graph(tree-sitter 콜그래프)·
graphify(멀티모달, 커뮤니티 탐지)를 갖췄고, `.claude/rules/code-review-graph.md` 한 파일에
세 도구의 실측 실패모드(0노드 침묵 실패, 벤더 코드 오염, sidecar 낡음, ignore 파일 3종 분리 등)가
전부 기록돼 있다. 외부에서 조사한 최신 계열은 아래와 같으나, 세 도구가 이미 로컬·무료·오프라인으로
동작한다는 점에서 이들을 도입할 근거가 약하다.

| 기법 | 근거 | confidence |
|:---|:---|:---|
| Code Graph Model(CGM) — 그래프 구조를 LLM attention에 직접 통합, 에이전트 없이 리포지토리 단위 작업 | OpenReview, https://openreview.net/forum?id=b98ODdeYq5 | likely |
| Aider repo-map, Repomix(26.2k stars), Serena, CodeGraph — 로컬 실행 코드 인텔리전스 도구 비교 | https://rywalker.com/research/code-intelligence-tools | likely |
| RepoGraph — 리포지토리 수준 코드 이해를 위한 그래프 | 검색 스니펫만 확인, 원문 미열람 | unverified |

판정: 이미 가진 3종이 이 갈래를 완전히 대체한다. 신규 도입 후보 없음.

### (b) GraphRAG 계열 검색

| 기법 | 대표 논문/OSS | confidence |
|:---|:---|:---|
| Microsoft GraphRAG (Edge et al. 2024) — 커뮤니티 요약 기반 계층 검색 | arXiv:2501.00309(후속 프리프린트), 서베이 arXiv:2408.08921 | likely |
| LightRAG (Guo et al. 2024) — 그래프 구조+2단계 검색으로 커버리지·효율 균형 | 서베이 스니펫에서만 확인 | unverified |

이 vault·workspace의 tokensave가 이미 "마크다운 헤딩 단위 전문 검색+FTS"를 무료로 제공하므로,
GraphRAG류(LLM 기반 엔티티 추출+커뮤니티 요약)는 graphify의 유료 semantic pass와 본질적으로
같은 범주다 — graphify가 이미 그 자리를 채우고 있다.

### (c) 에이전트 메모리 그래프 — 공백 후보, 깊게 조사

| 기법 | 근거 | confidence |
|:---|:---|:---|
| Zep — 시간적 지식그래프 아키텍처. DMR 벤치마크 94.8% vs MemGPT 93.4% | arXiv:2501.13956, https://arxiv.org/abs/2501.13956 | likely |
| Graphiti — Zep의 백엔드, 오픈소스, 20,000+ (검색 요약1) ~ 28.9K(검색 요약2) GitHub stars(두 검색 결과 수치 불일치 — 직접 리포 미확인이므로 별표 수는 unverified) | https://neo4j.com/blog/developer/graphiti-knowledge-graph-memory/ | likely (구조), unverified (star 수) |
| Graphiti 3계층 구조: episodic node(원문 메시지) → semantic entity/fact(bi-temporal edge validity) → community summary(label propagation 클러스터) | 검색 요약 | likely |
| LongMemEval에서 Graphiti(63.8%, GPT-4o) vs Mem0(49.0%) — 시간적 검색에서 15%p 격차 | https://particula.tech/blog/agent-memory-frameworks-tested-mem0-zep-letta-cognee-2026 | likely |
| Mem0 — 47K stars, 생성 타임스탬프만 있고 fact supersession/시간 유효창 모델링 없음 | 위와 동일 출처 | likely |
| A-MEM (arXiv:2502.12110) — Zettelkasten 방식에서 영감받은 동적 메모리 구조화. 메모리 삽입 시 기존 메모리의 연결·컨텍스트를 재갱신. multi-hop 추론 6배 개선, 메모리 연산 토큰 85-93% 절감(논문 저자 주장) | https://arxiv.org/abs/2502.12110 | likely |

**이 vault와의 직접 접점**: A-MEM이 명시적으로 인용하는 "Zettelkasten 방식"은 이 vault의
`2_Resource/concepts/` 자체가 이미 쓰고 있는 노트 작성 규칙(`rules-note-style` 스킬)이다.
즉 사용자는 이미 Zettelkasten을 인간 노트에 실천 중이고, A-MEM은 그 원리를 에이전트 메모리에
적용한 것 — 방법론적 친숙성은 있으나, 이것이 곧 도입 근거는 아니다(§5).

**claude-mem과의 대조**: claude-mem은 세션 관찰을 SQLite FTS로 압축·재주입한다. 이것은 "무엇을
했는지"의 텍스트 검색이지, "이 사실이 언제 성립했고 언제 무효화됐는지"를 추적하는 시간적 그래프가
아니다. 실측: 이 머신의 claude-mem 플러그인 소스에서 `graph`를 이름에 포함한 파일이 0건
(`find ~/.claude/plugins/cache/claude-mem -iname "*.py" -o -iname "*.ts" -o -iname "*.js" | grep -iE "graph|memory"` → 빈 결과, 경로 오류로 재확인 필요하나 실제 경로는
`~/.claude/plugins/cache/thedotmack/claude-mem`이며 이 경로에서 재검색은 하지 않았다 —
**미확인**: 정확한 경로에서의 grep 재실행. 이 문서의 "SQLite FTS 기반"이라는 서술은 웹 검색
요약에 근거하며 소스 코드 직접 확인이 아니다).

### (d) 워크플로 자체를 그래프로 표현 — 공백 후보, 깊게 조사

| 기법 | 근거 | confidence |
|:---|:---|:---|
| LangGraph — 상태를 유지하는 장기 실행 에이전트를 그래프로 빌드. MIT 라이선스, Klarna·Replit·Elastic 사용 | https://github.com/langchain-ai/langgraph | likely |
| "대부분 '에이전트'라 불리는 프로젝트는 실제로는 DAG 워크플로다"(고정 시퀀스+분기) — LangGraph 자체 문서의 구분 | https://docs.langchain.com/oss/python/langgraph/workflows-agents | likely |
| CrewAI(~35k stars), AutoGen, MetaGPT 등 — 멀티에이전트 오케스트레이션 프레임워크 목록 | https://github.com/vivy-yi/awesome-agent-orchestration | likely |

**이 하네스와의 직접 대조**: OMC의 `Workflow` 도구(`agent()/parallel()/pipeline()`)는 사용자
CLAUDE.md 서술상 스크립트 기반 팬아웃이다 — 조건부 엣지·사이클·상태 영속(LangGraph의
checkpoint/재개)은 없다. `feedback_workflow_args_string_trap.md`(auto-memory)가 이미 "팬아웃이
조용히 0개로 실패"하는 사고를 기록한 바 있는데, 이는 정확히 LangGraph가 그래프 엔진 수준에서
해결하려는 문제(상태 전이의 명시적 노드·엣지화, 실행 이력의 재현 가능성)와 같은 클래스다.

om* 5개 저장소 전체 grep 결과, `DAG`/`networkx`/`dependency graph` 문자열은
`oh-my-experiments/docs/design/2026-05-30-omx-experiment-harness-design.md` 등 계획 문서
5곳에만 나타났고, 실제 내용은 "빌드 순서 표"(B4: exp-init을 exp-analyze 앞으로 재배치)일 뿐
런타임 그래프 자료구조가 아니다(`grep -n` 실측, 원문: "Build DAG inverted: #2 evaluator-wrapper
… 재순서" — 스테이지 순서를 사람이 표로 정리한 것). 워크플로 그래프 엔진은 om* 어디에도 없다.

**판정 방향**: 이 공백이 실재하는 것과, 이를 메우기 위해 LangGraph 같은 프레임워크를 도입해야
하는 것은 별개다. OMC의 `agent()/parallel()/pipeline()`이 실제로 필요로 하는 것은 "그래프
엔진"이 아니라 "팬아웃 인자가 문자열로 오는 실패를 막는 타입 체크" 수준일 수 있다 — 이는 이미
기록된 debt(`feedback_workflow_args_string_trap.md`)이지 새 인프라의 근거가 아니다.

### (e) 그래프 기반 계획·추론(Graph-of-Thoughts류)

| 기법 | 근거 | confidence |
|:---|:---|:---|
| Graph of Thoughts(GoT, arXiv:2308.09687) — LLM 사고를 임의 그래프(정점=사고 단위, 엣지=의존성)로 모델링. Tree-of-Thoughts 대비 정렬 품질 62%↑, 비용 31%↓(정렬 태스크 기준) | arXiv:2308.09687, AAAI 2024 채택 | likely |
| Tree of Thoughts — GoT가 일반화하는 선행 기법 | 검색 요약에서만 확인, 원문 미열람 | unverified |

이 갈래는 프롬프팅 기법이지 인프라가 아니다. 현재 하네스의 `sciomc`(병렬 과학자 에이전트)·
`ultragoal`이 이미 유사한 "여러 사고 경로 병렬 생성→합성" 패턴을 구현하고 있을 가능성이 있으나,
그 내부 구현을 이번 조사에서 열람하지 않았다(스코프 밖) — **미확인**.

---

## 3. 비교축 — 이미 가진 것 vs 진짜 없는 것

### 3.1 (a)(b)는 이미 가진 것

tokensave·CRG·graphify 3종이 코드/문서 색인과 GraphRAG 범주를 무료·로컬로 덮는다.
`.claude/rules/code-review-graph.md`가 이미 상세한 실패모드·측정치·수리 절차를 담고 있어,
외부 최신 기법을 조사해도 "더 나은 것"을 찾지 못했다 — 세 도구가 겪는 문제(0노드 침묵 실패,
sidecar 낡음, 벤더코드 오염)는 이 계열 도구 전반의 공통 결함이지, 다른 도구가 안 겪는 문제가
아니다.

### 3.2 (c)(d)는 진짜 없는 것 — 그러나 "없다 ≠ 만들어야 한다"

| 축 | 사용자가 가진 것 | 공백 | 도입 근거 강도 |
|:---|:---|:---|:---|
| (c) 메모리 | claude-mem(SQLite FTS, 세션 관찰 압축), OMC notepad/project_memory(타사 플러그인, 구조 미확인) | 시간적 사실 무효화 추적, 다중 노트 간 그래프 연결 | **약함** — A/B 실측에서 규율 축 이득이 스킬 호출 0건인 상태에서 났다. 메모리 인프라를 추가하면 "쓰이지 않는 인프라"가 하나 더 생길 위험 |
| (d) 워크플로 | `Workflow(agent/parallel/pipeline)` 스크립트 팬아웃 | 조건 분기·사이클·상태 영속(체크포인트) | **약함** — 현재 실패모드(`feedback_workflow_args_string_trap.md`)는 그래프 엔진 부재가 아니라 인자 검증 부재로 이미 진단됐다 |

### 3.3 지울 수 있는 것이 있는가

`.claude/rules/code-review-graph.md` 자체가 이미 "지울지 말지"를 판정하는 도구를
포함한다 — `graph-init --purge`(노드가 벤더 코드로 오염됐을 때), 세 ignore 파일 정합성 검사.
이번 조사 범위에서 셋 중 하나를 통째로 지울 근거는 찾지 못했다: 세 도구는 서로 다른 질문
(점 쿼리 vs 코퍼스 형태 vs 프로즈 헤딩)에 답하도록 역할이 이미 분리돼 있고, 이 분리 자체가
문서에 명시돼 있다(`code-review-graph.md` "Which of the three answers this question" 표).

다만 **약한 통합 후보** 하나는 관찰된다: graphify의 `--code-only` 무료 빌드가 만드는 코드
그래프와 CRG의 tree-sitter 그래프는 같은 입력(코드)에 대해 유사한 산출물(콜/임포트 그래프)을
독립적으로 만든다. 두 도구가 실제로 답이 겹치는 질문에 대해 서로 다른 결과를 낼 가능성은
이번 조사에서 검증하지 않았다 — **미확인**. 검증 없이 "graphify의 code-only 빌드를 꺼도 된다"고
단정하지는 않는다.

---

## 4. 적용 제안

원칙: 스킬/인프라 추가에는 높은 입증 부담이 걸려 있다(SSOT: `~/claudebase/eval/README.md`,
규율 축만 변별, 이득은 훅이지 스킬이 아니었다). 아래는 "만들자"가 아니라 "관찰·측정을 먼저
하자"는 제안이다.

1. **메모리 그래프를 만들기 전에, claude-mem이 실제로 얼마나 쓰이는지부터 측정한다.**
   `claude-mem:mem-search`·`smart_search` 등이 세션당 몇 번 호출되는지, 재사용된 컨텍스트가
   실제로 작업에 기여했는지를 먼저 재라. 사용률이 낮다면 그래프로 업그레이드해도 같은 이유로
   안 쓰일 것이다.
2. **워크플로 그래프 엔진 도입은 보류하고, 기존 팬아웃 실패모드부터 닫는다.**
   `feedback_workflow_args_string_trap.md`가 지적한 "문자열로 온 args가 조용히 팬아웃 0개"
   문제에 타입 체크 한 줄을 넣는 것이 LangGraph 이식보다 훨씬 싼 수정이고, 실제로 관찰된
   실패를 정확히 겨냥한다.
3. **그래프 3종은 유지, 신규 도입 없음.** 이번 조사에서 대체·통합 근거를 찾지 못했다. 유일한
   약한 통합 후보(graphify code-only vs CRG 중복도)는 검증 없이 실행하지 말 것 — 별도 측정
   과제로 남긴다.

---

## 5. 열린 질문 (미확인 상태로 남김)

- Graphiti GitHub star 수: 검색 요약 두 곳이 20,000+와 28.9K로 불일치. 리포지토리 직접 확인 안 함.
- claude-mem 플러그인 소스가 정말 그래프 구조를 전혀 안 쓰는지: 정확한 캐시 경로
  (`~/.claude/plugins/cache/thedotmack/claude-mem`)에서 grep 재실행 안 함.
- OMC notepad/project_memory/wiki 도구(타사 플러그인)의 내부 저장 구조가 그래프인지 평면인지:
  열람 안 함(타인 소유 플러그인, 개조 대상 아니라는 지침에 따라 깊게 안 팜).
- graphify code-only 빌드와 CRG의 산출물이 실제로 얼마나 겹치는지: 두 그래프를 직접 대조
  안 함.
- `sciomc`/`ultragoal`이 내부적으로 GoT류 그래프 사고를 이미 구현하는지: 소스 미열람.

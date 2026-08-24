# 재조사: 그래프 엔지니어링 — 조회량·상각·무엇을 그래프에 넣는가

재조사일: 2026-08-23. 대상: [ext-graph-engineering.md](ext-graph-engineering.md)(2026-08-22)의 판정,
특히 §0의 두 공백 주장과 §5 "3종 중 지울 수 있는 것은 없다".

## 0. 한 문장 결론

**어제 문서의 사실 주장은 대체로 살아남았고, 무너진 것은 판정의 축이다.** claude-mem이 그래프가
아니라는 것도 om*에 런타임 그래프 엔진이 없다는 것도 실측으로 확인됐다. 그러나 어제가 "3종은
역할이 분리돼 있으니 지울 것 없다"고 판정한 근거는 **역할 분리**였고, 2026년 문헌이 이 계열을
판정하는 축은 **오프라인 비용이 상각되는가**다. 그 축으로 이 rig을 재면 답이 달라진다 — 3종의
한 달 조회량은 25회이고, 유지비는 241MB에 매 세션 자동 재빌드이며, **tokensave는 지금 0노드다**.
그리고 어제 "미확인"으로 남긴 유일한 통합 후보(graphify code-only vs CRG)는 측정해보니
포함관계였다. 요구 #2 재조사가 shared_memory에서 밟은 함정과 같은 것이다 — **가진 것과 쓰는 것은
다르고, 어제 조사는 가진 것만 셌다.**

## 1. rig 실측 — 어제의 서술을 하나씩 잰다

2026-08-23 15:15~15:27 KST, ksm-mac 로컬. 트랜스크립트 전수는 `~/.claude/projects`
(451개 `.jsonl`, 881MB, 2026-07-24 ~ 08-23).

| 어제 서술 | 실측 | 판정 |
|:---|:---|:---|
| "claude-mem은 SQLite FTS 기반 평면 저장소이지 그래프가 아니다" (어제 스스로 `find` 경로 오류로 **미확인** 표기) | 정확한 경로는 `~/.claude-mem/claude-mem.db`. `observations` 5,879행 · `session_summaries` 771 · `user_prompts` 802 + FTS5 그림자 테이블. **edge/node/relation 테이블 0개**, `valid_from`·`invalidated`·`superseded` 계열 컬럼 0개 | **유지** — "그래프 아님"과 "사실 무효화 추적 없음"이 스키마 수준에서 확인됨 |
| (같은 문장의 "평면") | 같은 디렉터리에 **Chroma 벡터스토어 260MB**(HNSW `link_lists.bin`) 병행 가동, `chroma-sync-state.json` 오늘 갱신 | **이미 판정된 건** — [SYNTHESIS.md](SYNTHESIS.md) §5.3 Y3이 [ext-agent-memory.md](ext-agent-memory.md):24의 원문 인용(`skills/how-it-works/SKILL.md:10-22`)을 근거로 이 충돌을 이미 해소했다. 내가 더한 것은 문서 인용이 아니라 **디스크 실물 확인**뿐이다. Y3은 이제 양쪽에서 닫혔다 |
| "om* 어디에도 런타임 그래프 엔진이 없다" | om* 5개 저장소 코드파일 316개에 `networkx`·`nx.DiGraph`·`topological_sort`·`adjacency` **0건**. oh-my-scholar의 1건은 주석 문자열 "round-id adjacency"로 무관 | **유지** |
| §5 "graphify code-only와 CRG의 중복도는 **검증하지 않았다**" | 측정했다. graphify가 노드를 뽑은 코드 파일 86개는 CRG의 93개에 **완전히 포함**된다(교집합 86, graphify 단독 0, CRG 단독 7) | **확정** — 약한 후보가 아니라 포함관계다 |

### 1.1 세 그래프가 실제로 조회되는가

`"type":"tool_use"…"name":"mcp__<서버>__"` 패턴 전수 집계. 같은 기간 같은 트랜스크립트에서
Bash 11,074회 · Read 3,184회 · Grep 23회다.

| 도구 | MCP 툴콜 | CLI 질의 | 현재 인덱스 | 디스크 |
|:---|---:|---:|:---|---:|
| tokensave | **21** (15세션, 전부 vault) | 0 (CLI 호출은 rig 룰상 금지) | **0 노드 / 0 파일** | 25 MB |
| code-review-graph | **2** | `query` 1 (`status` 45회는 헬스체크지 질의가 아님) | 664 노드 / 93 파일 | 13 MB |
| graphify | **0** | `query` 1 | 12,798 노드 / 14,267 링크 / 67 하이퍼엣지 | 203 MB |

쓰인 tokensave 도구는 `search` 15 · `status` 3 · `read` 2 · `callers_for` 1이 전부다.

**날짜 분포가 결론을 짓는다.** 08-10(3종 설치일) 12회 → 08-11 3회 → **08-12~08-21 열흘간 0회**
→ 08-22(하네스 조사일, 어제) 8회. 조회는 도구를 설치한 날과 그 도구를 조사한 날에만 일어났고,
평상시 작업에서는 일어나지 않았다. 세 그래프는 그 열흘 동안에도 계속 갱신되고 있었다(오늘만 해도
CRG 12:51, graphify 14:10, tokensave 15:14 자동 갱신 확인).

### 1.2 tokensave 인덱스가 지금 비어 있다

우연히 본 것이 아니라 §5를 재판정하려고 3종의 상태를 재다 나왔다.

- MCP `tokensave_status`(15:15) → `node_count: 0`, `file_count: 0`,
  `index_rebuild_in_progress: true`, 버전 7.10.0, `last_full_sync_at: 0`. 12분 뒤 재측정에서
  재빌드 플래그는 사라지고 0노드만 남았다(§6). DB는 25MB인데 `nodes`·`edges`·`files`·`vectors` 전부 0행
  (WAL·SHM 포함 사본으로 재확인 — `mode=ro` 단독 관측의 착시가 아니다).
- 이 vault의 `CLAUDE.md`와 `.claude/rules/code-review-graph.md`가 실측 예시로 못박아둔
  `tokensave_search "runaway"` → 2 hits를 **지금 그대로 돌리면 `[]`**다. 직접 실행해 확인했다.
- 원인은 스키마 마이그레이션이다. vault DB는 `user_version=17`, 형제 프로젝트 claudebase는
  `user_version=16`에 2,908노드인데 v7.10.0이 후자를 `schema version 16 does not match required
  version 17`로 **하드 거부**한다. 같은 업그레이드가 한쪽은 시끄럽게(에러), 한쪽은 조용하게
  (빈 결과) 깨뜨렸다.
- 조용한 쪽이 위험하다. `[]`는 "여기 없다"와 구별되지 않는데, vault `CLAUDE.md`의 라우팅 표는
  "어느 노트가 X를 말하나 → `tokensave_search`"를 **첫 번째 도구**로 지정한다.
- 문서화된 복구 경로(`tokensave sync`)는 이 rig의 다른 룰이 금지한다 — 그 CLI가
  `~/.claude/settings.json`을 다시 쓰기 때문이다(`code-review-graph.md`에 실측 기록됨).
  즉 복구는 그 룰이 정한 예외 절차(설정 사본 → sync → 해시 대조 → 복원)를 밟아야 한다.
- **소급 효과가 하나 있다.** worker-audit이 [AUDIT-2026-08-23.md](AUDIT-2026-08-23.md)에서
  지적했듯 `gap-omx.md` §3의 증거 한 덩어리가 "tokensave_search로 확인(verified, vault index)"을
  출처로 단다. 그 조회는 08-22에 이뤄졌으니 **판정이 틀렸다는 뜻이 아니라 지금 재현이 안 된다는
  뜻**이다. 재조사자가 그 절을 검증하려 들면 빈 결과를 "근거 없음"으로 오독할 수 있다.

### 1.3 graphify의 12,798 노드는 코드가 아니다

| 확장자 | 노드 | 비중 |
|:---|---:|---:|
| `.md` | 11,577 | 90.5% |
| `.py` | 780 | 6.1% |
| `.pdf` / `.json` / `.cpp` / `.sh` | 143 / 140 / 85 / 39 | 3.2% |

graphify에서 5시간짜리 유료 semantic 패스가 만들어낸 자산은 프로즈 개념 그래프이고, 코드
부분(865노드·86파일)은 §1의 측정대로 CRG에 완전히 포함된다. **어제가 "약한 통합 후보"로 남긴
방향은 맞았지만 크기를 반대로 봤다** — 지워도 되는 것은 graphify가 아니라 graphify의 코드
절반이고, graphify의 본체는 다른 두 도구가 만들지 않는 것이다.

---

## 2. 어제 조사가 놓친 문헌

어제 문서의 최신 arXiv 인용은 2502(2025-02)이고 2026년 문헌은 0건이다. 축을 갈라 재검색하니
2026-01-01 이후만 코드×지식그래프 82건, 에이전트 메모리 그래프 100건, GraphRAG 비용·baseline
75건, 리포지토리 수준 retrieval 70건이 나온다. 아래 5편은 전부 **어제 조사일(08-22) 이전 공개**다.
모두 arXiv 초록을 직접 대조했고, **본문·표는 열람하지 않았다**(§6).

**Codebase-Memory (2603.27277, 2026-03-28)** — 이 rig의 tokensave·CRG와 같은 물건이다:
Tree-Sitter 기반 지식그래프를 MCP로 노출, 66개 언어, 콜그래프 순회·영향 분석·커뮤니티 탐지.
31개 실제 저장소 평가. 이 문서가 어제 조사에 없다는 것이 재조사를 촉발한 확증이다.

**MOOSEDev (2608.13662, 2026-08-13)** — 어제 (c)로 지목한 공백을 정면으로 다룬 유일한 논문이다.
코딩 에이전트에게 **온톨로지 기반 프로젝트 메모리**를 MCP로 주고, 레코드가 lifecycle status와
provenance와 **supersession link**를 갖는다. 중립 공개 코퍼스 835 레코드에서 프로덕션
벡터-메모리 도구와 대조: supersession·set-completeness·negation 질문에서 기대 답 집합을
**0.98~1.00**으로 반환한 반면 baseline의 top-k 검색은 **6~27%**만 건졌다.

**LEDGER (2606.28379, 2026-06-19)** — 의존성 인지 그래프 retrieval. 긴 구조화 문서의 국소 편집이
상호참조를 깨지 않게 하는 문제에 경량 의존성 그래프(계층·명시 참조·암묵 의존·의미 관계)를 쓴다.
1.9k 테스트, 6개 모델에서 consistency **56% → 76%**, 토큰은 감소. 이 rig에 직접 닿는 주장은
**low reasoning effort의 LEDGER가 baseline의 high reasoning effort와 동률**이라는 것 — 명시적
의존성 표현이 비싼 내부 추론을 부분적으로 대체할 수 있다.

**Agent-as-a-Graph (2511.18194, 2025-11-22)** — 도구와 그 부모 에이전트를 함께 KG 노드·엣지로
두고 벡터 검색 → 타입별 가중 RRF 재랭킹 → 부모 에이전트 순회로 검색한다. LiveMCPBench에서
Recall@5 +14.9%, nDCG@5 +14.6%. 수백~수천 개의 MCP 도구를 가진 시스템이 전제인데, 이 rig의
세션 시작 시 주입되는 지연 도구 목록이 정확히 그 규모다.

**LLM-as-Code (2606.15874, 2026-06-14)** — (d) 축을 harness 어휘로 다룬다. 주장은 강하다:
토큰 폭발·control-flow 환각·불완전한 종료는 구현 버그가 아니라 **결정론적 일(루프·분기·순서)을
확률적 시스템에 맡긴 아키텍처의 결과**이고, 더 좋은 프롬프트나 더 강한 모델로는 못 고친다.
제어를 프로그램이 쥐면 LLM 컨텍스트는 실행 이력의 call tree, 즉 DAG가 되고 **각 호출의 컨텍스트
길이가 누적이 아니라 호출 깊이로 결정된다**. 근거는 computer-use 에이전트 사례연구 1건이다.

> 이 다섯 편을 찾은 방법 자체가 결과다. worker-audit이 세션 중에 보낸 지적("'그래프 엔지니어링'
> 이라는 원문 어휘로 찾으면 문헌이 실제로 쓰는 어휘가 빠진다")을 받아 GraphRAG · code property
> graph · KG-augmented memory · dependency-aware retrieval · agent harness로 축을 갈랐다.
> 어제 문서의 어휘를 그대로 썼다면 위 다섯 중 최소 셋(LEDGER · Agent-as-a-Graph · LLM-as-Code)은
> 이번에도 안 나왔을 것이다.

---

## 3. 반대편 — 같은 검색에서 나온 부정 증거

**Do We Still Need GraphRAG? (2604.09666, 2026-04-01)** — 제목이 곧 이 절의 요지다. RAGSearch
벤치마크로 dense RAG와 대표 GraphRAG들을 **agentic search 하의 검색 인프라로서** 대조하되,
LLM 백본·검색 예산·추론 프로토콜을 표준화하고 오프라인 전처리 비용·온라인 효율·안정성까지 보고한다.
결과는 양면이다 — agentic search가 dense RAG를 크게 끌어올려 GraphRAG와의 격차를 좁히고(특히
RL 기반), 그럼에도 GraphRAG는 복잡한 multi-hop에서 유리하며 agentic search 행동이 더 안정적이다.
**단서가 붙는다: "when its offline cost is amortized".** 이 rig의 상각 상태는 §1.1이다.

**Structure Over Scale (2607.22592, 2026-06-10)** — 현행 GraphRAG는 엔티티·관계를 exhaustive하게
뽑아서 **그래프 크기와 구축 비용이 질의가 요구하는 추론이 아니라 코퍼스 길이에 비례**한다고 지적한다.
스키마로 제약한 인과 그래프가 엔티티-관계 baseline과 동등한 답변 품질을 **3~20배 적은 노드**,
**8~135배 적은 build-time LLM 호출**로 낸다. 결론 문장이 이 rig의 graphify를 그대로 겨눈다 —
**"무엇을 그래프에 넣느냐가 노드가 몇 개냐보다 중요하다."**

**Codebase-Memory의 반대쪽 절반 (2603.27277)** — 같은 논문이 자기 초록에 부정 수치를 적어둔다.
답변 품질 **83% vs 파일 탐색 에이전트 92%**. 이긴 축은 비용이다(토큰 10배 절감, 툴콜 2.1배 절감).
그래프-네이티브 질의(허브 탐지·caller 랭킹)에서만 31개 언어 중 19개에서 동등 이상이다.
즉 **그래프는 무엇을 물어보느냐에 따라 지고, 항상 이기는 것은 비용뿐이다.**

**MOOSEDev의 반대쪽 절반 (2608.13662)** — supersession류 질문에서 0.98~1.00 대 6~27%로 압승한
바로 그 대조에서 **relevance recall과 token cost는 양쪽이 대체로 대등했다**. 그래프 메모리가
사는 곳은 "이 결정이 무엇을 대체했나"이지 일반 검색이 아니다.

**StructMem (2604.21748, 2026-04-23)** — 트레이드오프를 한 문장으로 못박는다: 평면 메모리는
효율적이지만 관계 구조를 못 담고, 그래프 메모리는 구조적 추론을 가능케 하지만 **구축이 비싸고
깨지기 쉽다**(expensive and fragile construction). §1.2의 스키마 마이그레이션 사고가 그
fragile의 실물이다.

**AOCI (2605.02421, 2026-05-04)** — 그래프가 유일한 답이 아니라는 쪽의 증거다. 그래프 대신
**심볼릭-시맨틱 인덱스**(LLM이 한 번에 읽는 구조화된 청사진, 코드 단위당 한 엔트리)를 쓴다.
4개 프로젝트 × 3개 LLM × 6개 컨텍스트 조건 2,160회 평가에서 배포 가능한 baseline을 전부 앞서고
Oracle 상한 바로 아래. 19개 산업 과제에서 최종 결함 0건인 반면 주류 에이전트 도구 3종은 12개
과제에서 결함을 냈고 토큰을 **4~130배** 더 썼다(p < 0.001).

**The Amazing Agent Race (2604.10261, 2026-04-11)** — (d)의 양면. 기존 도구 사용 벤치마크 6개를
분석하니 인스턴스의 **55~100%가 2~5스텝 선형 체인**이다. 즉 대부분의 실제 과제는 선형이고,
어제 문서가 "OMC는 선형·병렬 스크립트일 뿐"이라 적은 것이 곧 결함은 아니다. 반면 DAG로 만든
1,400개 문제에서 최고 성적은 **37.2%**이고 실패의 대부분은 도구 호출(<17%)이 아니라
**내비게이션(27~52%)**이다. 부기: Claude Code가 Codex CLI와 같은 37%를 **토큰 6배 적게** 썼다.

---

## 4. 갈래별 재판정

| 갈래 | 어제 판정 | 최선의 긍정 근거 | 최선의 부정 근거 | 오늘 판정 |
|:---|:---|:---|:---|:---|
| (a) 코드/문서 지식그래프 | "3종이 완전히 덮는다, 신규 후보 없음" | Codebase-Memory 토큰 10배·툴콜 2.1배 절감 | 같은 논문 답변 품질 83% vs 92%; AOCI가 그래프 없이 배포 가능 baseline 전부 능가 | **결론 유지, 근거 교체** — 신규 도입 후보가 없다는 결론은 같으나 이유가 "이미 덮어서"가 아니라 "이 rig에서 그래프 조회가 25회/월이라 도입 논의 자체가 이르러서"다 |
| (b) GraphRAG 검색 | "graphify가 그 자리를 채운다" | — | Do We Still Need GraphRAG?: agentic search가 격차를 좁힘, GraphRAG 우위는 **오프라인 비용 상각 시** | **조건부로 뒤집힘** — "채운다"가 성립하려면 상각돼야 하는데 graphify MCP 조회 0회·유지 203MB다 |
| (c) 에이전트 메모리 그래프 | "공백 실재, 도입 근거 **약함**" | MOOSEDev supersession 0.98~1.00 vs 6~27%, MCP로 노출 | 같은 논문 relevance recall·토큰 대등; claude-mem이 이미 벡터 하이브리드 | **약함 → 조건부** — 이득이 나는 질문 유형이 세 가지로 특정됐다. 이 vault가 그 유형을 실제로 묻는지는 미측정 |
| (d) 워크플로 그래프 | "공백 실재, 도입 근거 **약함**" | LLM-as-Code: 컨텍스트 길이가 누적 대신 호출 깊이로 결정 | AAR: 실제 과제의 55~100%가 2~5스텝 선형 | **유지** — 부정 근거가 더 직접적이다. 어제가 근거로 든 `feedback_workflow_args_string_trap`은 여전히 인자 검증 문제이지 그래프 엔진 부재의 증거가 아니다 |
| (e) Graph-of-Thoughts류 | "프롬프팅 기법이지 인프라 아님" | — | — | **유지** — 이번에도 이 갈래에서 rig에 닿는 새 근거를 못 찾았다 |

---

## 5. §5 재판정 — 지울 수 있는 것이 있는가

어제의 답은 "없다"였고 근거는 세 도구의 역할이 문서에 명시적으로 분리돼 있다는 것이었다.
**역할이 분리돼 있다는 것과 그 역할이 행사된다는 것은 다른 명제다.** §1.1이 후자를 잰다.

| 도구 | 유지비 | 한 달 조회 | 다른 도구로 대체 가능한가 | 판정 |
|:---|---:|---:|:---|:---|
| code-review-graph | 13 MB, Stop 훅 0.46초 | 2회 | 코드 콜/임포트 점 쿼리의 유일한 런타임 | **유지** — 가장 싸고, 유일하게 증분 갱신된다 |
| graphify (코드 절반) | — | — | 코드 파일 86개가 CRG 93개에 **완전 포함** | **제거 후보(측정 완료)** — CRG가 같은 입력을 더 자주 갱신한다 |
| graphify (프로즈 절반) | 203 MB, semantic 패스 5시간 | MCP 0회 | 노트 11,577 개념 노드·14,267 링크는 다른 둘이 못 만든다 | **판정 보류** — 대체 불가지만 한 번도 조회되지 않았다. "유일함"은 "쓸모"의 증거가 아니다 |
| tokensave | 25 MB, 파일 변경마다 재색인 | 21회(전부 08-10·11·22) | 프로즈 헤딩 검색의 유일한 무료 경로 | **복구 대상** — 지금 0노드이고, 이 vault 라우팅 표의 첫 번째 도구다 |

**따라서 지울 수 있는 것은 "3종 중 하나"가 아니라 "graphify의 code-only 빌드"다.** 그리고
지우기보다 먼저 할 일이 생겼다 — 세 그래프 중 둘이 지금 정상 상태가 아니다(tokensave 0노드,
graphify 조회 0회). 어제 문서가 §3.3에서 "지울 근거를 찾지 못했다"고 쓴 것은 세 도구가 **작동
중이라는 전제** 위에 있었고, 그 전제를 어제도 오늘 전까지도 아무도 재지 않았다.

이 절은 실행 권고가 아니라 측정 결과다. 무엇을 지울지는 사용자 결정이고, `DESIGN.md`·`PLAN.md`는
이 문서가 건드리지 않는다.

---

## 6. 확인 안 함 (정직한 공백)

- **인용한 arXiv 10편 전부 초록만 대조했다.** 본문·표·재현은 열지 않았다. §2·§3의 모든 수치는
  저자 초록 주장이며 1차 데이터 검증이 아니다.
- **MOOSEDev의 MOOSE 엔진은 proprietary**다(초록 명시). 이 rig에 이식 가능한지 미확인.
  베이스라인 "production vector-memory tool"의 정체도 초록에 없어 claude-mem과 같은 물건인지 모른다.
- **tokensave 0노드가 일시인지 지속인지** — 세 시점을 확보했다: 15:15 `rebuild_in_progress: true`,
  15:20 여전히 `true`(worker-audit 세션이 독립 실행), 15:27 그 필드가 **사라지고** `stale_commits: 13`이
  새로 붙음, 15:34 필드 소멸 유지에 `stale_commits: 14`(worker-audit 재확인 — 새 커밋이 반영되는데도
  노드는 안 늘었다). `node_count: 0`은 네 번 다 같다. 즉 재빌드는 끝났고 그 결과가 0노드다 —
  일시 상태라는 해석은 약해졌다. 단 네 관측이 **같은 계측기**(`tokensave_status`)를 읽었으므로 확인된 것은
  "다른 도구도 같은 말을 한다"가 아니라 "이 상태가 19분간 지속되고 재빌드 종료 후에도 남는다"까지다.
  왜 0으로 끝났는지
  (마이그레이션이 원본을 비우고 재색인이 no-op이 됐는지, 색인 대상 판정이 깨졌는지)는 **모른다**.
  어느 쪽이든 **이 문서의 다른 판정은 바뀌지 않는다** — §1.1의 조회량은 인덱스가 정상이던
  08-10~08-21에 측정됐다.
- **claude-mem의 Chroma가 실제 검색 경로에 쓰이는지** — 260MB가 디스크에 있고 sync state가 오늘
  갱신된 것만 확인했다. MCP `smart_search`가 벡터를 타는지 FTS를 타는지는 소스 미확인.
- **이 vault가 supersession 유형 질문을 실제로 얼마나 묻는지** — (c)의 이득 조건인데 안 쟀다.
  auto-memory `MEMORY.md`에 "정정"·"철회"·"기각" 항목이 다수 보이므로 후보는 있으나 세지 않았다.
- **graphify 조회 0회의 원인** — 도구가 부적합해서인지, 훅이 유도를 못 해서인지, 잊혀서인지
  구분 못 했다. `graphify query` 유도 훅은 이 세션에서도 발화했는데(직접 관측) 한 달간 실행은 1회다.
- **CRG `status` 45회의 정체** — 헬스체크로 분류했으나 각 호출의 맥락은 안 봤다.
- **어제 문서의 (a)(b) 표에 있던 CGM·RepoGraph·LightRAG** — 이번 재조사에서도 원문 미열람.
  어제와 같은 `unverified` 상태로 남는다.
- **`.omc/logs/`·`~/.claude/metrics/`** — 브리프가 지목한 두 경로는 존재하나, 조회량 집계는
  트랜스크립트에서 뽑았고 이 둘의 내용은 열지 않았다. 같은 수치를 교차 확인할 기회가 남아 있다.
- **자발적 세션 간 조율은 이 rig에서 관측 0건이다.** §7 부기의 정정에서 따라 나오는 공백인데
  따로 세지 않았으므로 여기 적는다. 이번 세션쌍의 조율은 전부 사람이 설계한 조건에서 나왔고,
  worker-audit이 자기 브리프(`/tmp/w2.md`) 원문으로 대칭을 확인했다 — 그쪽도 handle(L5-6),
  분담(L57-62), 통신 명령어(L67-74), **발신 기준(L75)**까지 지시받았다. 마지막 항목이 특히
  중요하다: "새 신호 없는 중계는 문헌상 해롭다"는 규율조차 브리프가 문헌 근거를 붙여 내려준
  것이라, 우리가 "새 신호만 보냈다"고 자평한 품질은 **인프라의 성질이 아니라 브리프의 성질**이다.

---

## 7. 다음에 잴 것 (제안, 결정 아님)

1. **tokensave 복구가 우선순위 1번이다.** 조사 결론과 무관하게 vault `CLAUDE.md`의 첫 번째
   라우팅 대상이 지금 빈 결과를 낸다. 절차는 `code-review-graph.md`가 이미 갖고 있다(설정 사본 →
   `sync` → 해시 대조 → 복원). claudebase도 schema 16이라 같이 밟아야 한다.
2. **graphify의 code-only 빌드를 끄는 것은 지금 결정 가능하다.** 포함관계가 측정됐고(§1),
   프로즈 그래프는 영향받지 않는다. 다만 이득은 빌드 시간뿐이고 203MB는 프로즈 쪽이 차지한다.
3. **(c)를 재려면 질문 유형부터 세라.** MOOSEDev가 이득을 낸 축은 supersession·set-completeness·
   negation 셋뿐이고 일반 검색은 대등했다. 이 rig에서 그 세 유형이 몇 번 발생하는지를 `MEMORY.md`의
   정정·철회 이력으로 세는 것이 그래프 메모리를 만드는 것보다 훨씬 싸다.
4. **조회량을 상시 계측하라.** 이 문서의 판정 대부분이 트랜스크립트 grep 한 번에서 나왔다.
   같은 집계를 주기적으로 돌리면 "만들었지만 안 쓰이는" 실패모드를 사후가 아니라 진행 중에 잡는다.
   요구 #2 재조사의 shared_memory 0건과 이 문서의 graphify 0회는 같은 계측의 두 사례다.

### 부기 — AUDIT이 남긴 열린 질문에 대해

[AUDIT-2026-08-23.md](AUDIT-2026-08-23.md) 말미가 "이번 세션 간 교환이 그쪽 산출물을 실제로
개선했는지는 v2가 나와야 판정된다"고 남겼다. 이 문서가 아는 만큼만 답한다.

**먼저 이 데이터가 무엇의 데이터가 아닌지부터 적는다**(사용자 지적, 2026-08-23). 이번 협업은
자발적으로 발생한 것이 아니라 **사람이 다른 세션에서 명시적으로 지시한 것**이다. 브리프
(`/tmp/w1.md`)가 양쪽 handle, 파일 소유권 분배(누가 어느 문서를 쓰는가), 통신 명령어, 보낼
가치가 있는 것과 없는 것("잡담·중계는 보내지 마라")까지 **전부 미리 정해서 내려왔다**. 따라서:

- **(a) 작업 분배 축은 이 세션에서 전혀 시험되지 않았다.** 분담은 사람이 준 것이고 두 세션이
  협상한 것이 0회다. AgentRadio에서 분담 협상 단독 기여가 +12.1pp였는데 그 국면 자체가 없었다.
- **(b) 정보 공유조차 지시된 공유다.** 무엇을 보낼지의 기준을 브리프가 줬으므로, 관측된 신호
  품질은 인프라의 성질이 아니라 **브리프 설계의 성질**일 수 있다.
- 따라서 이 세션이 잰 것은 "이 rig에서 세션 간 발견 공유가 작동하는가"가 아니라
  **"사람이 조율을 미리 설계해줬을 때 전송로가 버티는가"**다. 셋 중 가장 약한 질문이다.
- 같은 잣대를 §7 부기 아래쪽이 12:10 사건에 적용하면서("조율은 사람 손으로 이뤄졌다")
  정작 이 세션 자신에는 적용하지 않았다. 그 비대칭을 여기서 닫는다.

- **개선됐다고 볼 근거**: §2의 다섯 편 중 최소 셋(LEDGER · Agent-as-a-Graph · LLM-as-Code)은
  worker-audit이 알려준 어휘 축이 없었으면 이번에도 못 찾았다. 그리고 §1의 claude-mem 행은
  중복 노동이 될 뻔했다 — SYNTHESIS Y3이 이미 판정한 것을 새 발견으로 쓸 뻔했고, 파일을 쓰기 직전
  `grep`으로 알아채 크레딧으로 바꿨다. 이건 정확히 요구 #2가 표적으로 삼은 **중복된 분석 노동**의
  실사례이며, 이번에는 파일 검색이 막았지 통신이 막은 게 아니다.
- **개선됐다고 말할 수 없는 이유**: 대조군이 없다. 교환 없이 같은 재조사를 했을 때 무엇을 찾았을지는
  반사실이고, 표본은 양방향 2회씩 총 4건이다. 이득의 크기는 이 데이터로 못 잰다.
- **그 부정 데이터를 한 축 더 갈라야 한다**(worker-audit의 해석, 이 문서가 검증한 것 아님):
  grep이 이긴 것과 통신이 필요한 것을 가르는 축은 **발견이 이미 디스크에 있는가**다. 내 중복
  미수 건은 선행 판정(SYNTHESIS §5.3 Y3)이 같은 저장소 파일에 있었으니 grep이 이겼고,
  요구 #2 재조사가 든 08-23 12:10 훅 정리 중복은 병렬 세션이 **아직 파일로 안 남긴 진행 중
  발견**이라 grep이 못 잡아 사람 손으로 조율됐다. 즉 통신 인프라가 이기는 구간은 후자로 좁혀진다
  — (a) 축의 표적은 "중복된 분석 노동" 전체가 아니라 **아직 기록되지 않은 진행 중 발견**이다.
- **전송로는 작동했다 — 수신 4건·발신 3건, 전부 새 신호였다**(어휘 축 → 나, 인덱스 붕괴 →
  감사 기준, 디스크 축 → 이 절, ack 결함 → 양쪽). 그러나 **읽음 처리 경로가 없다.**
  worker-audit이 큐 3건 상태에서 4경로를 전수로 시험했다: `check --json` 거부(`legacy_read_only`),
  `check --unread --json` 같은 거부, `check --peek --json`은 작동하나 직후 재조회에서 3건 전부
  `read=0` 유지, `check --ack <delivery_id>`는 legacy 메시지 객체에 `delivery_id` 필드가 없어
  호출 자체가 불가. **읽을 수는 있는데 읽었다고 표시할 방법이 없다.**
- **그 결함이 (b) 축의 문헌 전제를 깬다**(worker-audit의 해석). AgentRadio에서 (b)가 가장 강한
  축이었던 이유는 passive awareness — 수신이 에이전트의 스텝을 소모하지 않는다는 것이다.
  이 rig은 정반대다: 폴링해야 하고, 폴링해도 큐가 안 비어서 읽은 것을 매번 다시 읽는다.
  실제로 이 세션에서 2건 → 3건 → 4건으로 누적되며 매번 전체가 재출력됐다. **수신 비용이
  메시지 수에 선형으로 는다.** 문헌이 이득의 근거로 든 성질이 구현에서 반대로 나 있다.
- **이 세션은 요구 #2 §7-1의 A/B 어느 팔도 아니다.** 그 A/B는 (h0) 서로 모른 채 / (ht) 발견을
  공유하며 두 팔인데, 이번은 분담까지 미리 받은 제3의 조건이다. 첫 데이터로 쓰려면 조건을
  그렇게 명시해야 하고, 그냥 "공유 팔"로 넣으면 분담 효과와 공유 효과가 섞인다.

---

## Sources

- [Codebase-Memory: Tree-Sitter-Based Knowledge Graphs for LLM Code Exploration via MCP (arXiv 2603.27277)](https://arxiv.org/abs/2603.27277)
- [Ontology-Grounded Project Memory for Coding Agents — MOOSEDev (arXiv 2608.13662)](https://arxiv.org/abs/2608.13662)
- [LEDGER: Scaling Agentic Document Editing with Dependency-aware Graph Retrieval (arXiv 2606.28379)](https://arxiv.org/abs/2606.28379)
- [Agent-as-a-Graph: Knowledge Graph-Based Tool and Agent Retrieval for LLM Multi-Agent Systems (arXiv 2511.18194)](https://arxiv.org/abs/2511.18194)
- [LLM-as-Code: Agentic Programming for Agent Harness (arXiv 2606.15874)](https://arxiv.org/abs/2606.15874)
- [Do We Still Need GraphRAG? Benchmarking RAG and GraphRAG for Agentic Search Systems (arXiv 2604.09666)](https://arxiv.org/abs/2604.09666)
- [Structure Over Scale: Schema-Constrained Causal Graphs for RAG (arXiv 2607.22592)](https://arxiv.org/abs/2607.22592)
- [StructMem: Structured Memory for Long-Horizon Behavior in LLMs (arXiv 2604.21748)](https://arxiv.org/abs/2604.21748)
- [AOCI: Symbolic-Semantic Indexing for Practical Repository-Scale Code Understanding with LLMs (arXiv 2605.02421)](https://arxiv.org/abs/2605.02421)
- [The Amazing Agent Race: Strong Tool Users, Weak Navigators (arXiv 2604.10261)](https://arxiv.org/abs/2604.10261)
- 어제 조사: [ext-graph-engineering.md](ext-graph-engineering.md) · 형식·방법론: [ext-agent-collaboration-v2.md](ext-agent-collaboration-v2.md)
- 형제 문서: [SYNTHESIS.md](SYNTHESIS.md) §5.3 Y3 · [ext-agent-memory.md](ext-agent-memory.md):24 · [AUDIT-2026-08-23.md](AUDIT-2026-08-23.md)
- rig 룰: `.claude/rules/code-review-graph.md` · vault `CLAUDE.md` 라우팅 표

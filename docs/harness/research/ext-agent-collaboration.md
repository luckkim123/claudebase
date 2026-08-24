# 다중 에이전트 "커뮤니티" 협업 구조 조사

조사일: 2026-08-22. 범위: 학술 명칭·성능 근거·오픈소스 구현·Claude Code 하네스 적용 가능성.
결론 우선 원칙에 따라 헤드라인부터: **이 구조 전체를 새로 지을 근거는 약하다. 이미 있는 배선(SendMessage·shared_memory·wiki)을 켜서 재는 것이 우선이고, "게시판을 새로 만들자"는 제안은 사용자 rig 의 실측(비용 +69%·규율축만 개선·스킬호출 0건)과 같은 급의 A/B 없이는 기각해야 한다.**

---

## 1. 학술 명칭 정리 — 각 패턴이 무엇으로 불리는가

| 패턴 | 핵심 아이디어 | 대표 논문 | arXiv |
|:---|:---|:---|:---|
| Blackboard architecture | 공유 게시판에 에이전트가 자유롭게 쓰고, "다음에 누가 행동할지"를 게시판 내용으로 선택. 합의될 때까지 선택-실행 반복 | Exploring Advanced LLM Multi-Agent Systems Based on Blackboard Architecture | 2507.01701 |
| Blackboard (정보 탐색 특화) | 중앙 에이전트가 요청을 게시, 하위 에이전트들이 능력에 따라 자원해서 응답 | LLM-Based Multi-Agent Blackboard System for Information Discovery in Data Science | 2510.01285 |
| Multi-agent debate | 여러 LLM 인스턴스가 각자 답을 내고 여러 라운드에 걸쳐 반박·수정, 최종 합의 도출 | Improving Factuality and Reasoning in Language Models through Multiagent Debate (Du, Li, Torralba, Tenenbaum, Mordatch) | 2305.14325 |
| Generative agents / society of agents | 자연어로 경험을 기록하고 반성(reflection)으로 상위 개념을 합성, 검색해 계획에 반영. 25 에이전트 샌드박스 시뮬레이션 | Generative Agents: Interactive Simulacra of Human Behavior (Park et al., Stanford, UIST'23) | 2304.03442 |
| Stigmergy / observation-driven coordination | 명시적 메시지 교환이 아니라 공유 상태(파일·게시판)를 관찰해 남의 작업을 건드리지 않고 조율 | CodeCRDT: Observation-Driven Coordination for Multi-Agent LLM Code Generation | 2510.18893 |
| Shared message pool (publish/subscribe) | 구조화된 메시지를 공유 풀에 발행하고, 각 에이전트가 자신의 역할(profile)에 맞는 메시지만 구독 | MetaGPT: Meta Programming for a Multi-Agent Collaborative Framework (ICLR 2024) | 2308.00352 |
| Market/auction 기반 조율 | 에이전트를 시장 참여자로 놓고 경매·협상으로 자원·작업을 배분 | Magentic Marketplace: An Open-Source Environment for Studying Agentic Markets | 2510.25779 |

Society of Mind(Minsky, 1986)는 arXiv 논문이 아니라 단행본이며, "여러 단순 에이전트의 상호작용에서 지능이 창발한다"는 철학적 원류로만 인용됨 — Du et al.(2305.14325) 논문이 자신들의 debate 구조를 이 개념에 명시적으로 연결한다.

시장/경매 계열은 검색 결과 대부분이 "에이전트 간 상거래·가격 협상" 자체를 연구 대상으로 삼는 논문들(AgenticPay, MarketBench, Institutional AI)이라 **작업 품질을 올리기 위한 조율 메커니즘**이라는 이번 조사의 관심사와는 결이 다르다. confidence: likely — 제목·요약만 확인, 본문 정독은 안 함.

---

## 2. 성능 증거 — 실제로 이긴다는 근거와 진다는 근거

### 이득이 있다고 보고한 사례

- Blackboard(2507.01701): "SOTA 정적·동적 멀티에이전트 시스템과 경쟁하는 평균 성능을, 더 적은 토큰으로" 달성했다고 주장. confidence: unverified — 초록 수준만 확인, 벤치마크 표 미대조.
- Blackboard 정보탐색(2510.01285): baseline 대비 end-to-end 성공률 13~57% 상대개선, 데이터 발견 F1 최대 9% 상대개선. confidence: unverified — 같은 이유.
- Multi-agent debate(2305.14325): 수학·전략 추론 향상, 환각 감소를 보고. 다만 이 논문은 2023년 것으로 이후 여러 반박 논문의 표적이 됨(아래).
- MetaGPT(2308.00352): publish/subscribe 구조가 "능동적으로 관련 정보를 끌어오는 방식이 수동 대화 수신보다 효율적"이라고 주장(구조적 이유, 정량 벤치마크는 별도 절에서 코드 생성 성공률로 제시 — 이번 조사에서 그 수치는 미확인).

### 이득이 없거나 역효과라는 반증

- "When and Why Does Multi-Agent Debate Fail and Does It Really Underperform?" (arXiv 2510.20963): 무조건적 debate 는 도움이 안 되고 오히려 해칠 수 있음(unconditional debate does not help and can actively hurt); debate 단독으로는 기대 정확도를 개선하지 못하며 표적화된 아키텍처 개입이 필요.
- "Stop Overvaluing Multi-Agent Debate" (arXiv 2502.08788): 평가 방식 자체를 재고해야 한다는 제목 — MAD 의 이득이 과대평가돼 왔다는 주장.
- M3MAD-Bench(2601.02854): 모든 역할을 동일 모델(Pixtral)로 채우면 MathVision·RealWorldQA 에서 단일 에이전트보다 성능이 떨어짐.
- ICLR Blogpost(Multi-LLM-Agents Debate)에 인용된 관찰: 라운드를 반복해도 성능이 정체되거나 등락, MATH 데이터셋은 초기 라운드 이후 오히려 하락 추세.
- 종합 서술(여러 서베이성 결과의 웹검색 종합, confidence: unverified — 1차 출처 대조 안 함): "현재 MAD 방법들은 단순 단일-에이전트 전략을 일관되게 능가하지 못한다", "CopMAD·SoM 방식에서는 토론 참여 LLM 중 가장 약한 것보다도 결과가 낮은 경우가 대부분".

### 비용 대비 효과 — 사용자 rig 의 실측과 같은 급의 수치

- "5~10 에이전트가 quality-to-cost 비가 좋고, self-consistency 는 N=20~40 이후 수익 체감, 대부분의 이득은 첫 5~10개에 몰림" — 출처 불명확한 웹 종합 서술, confidence: unverified.
- "reflection(경량 사후 교정)이 최고 성공률을 최저 토큰 비용으로 달성하는 반면, interactive debate 는 비슷한 성공률을 훨씬 높은 비용으로 달성 — 추가 라운드가 주로 중복만 더한다" — 같은 웹 종합, confidence: unverified. 다만 이 서술의 방향성(반복 상호작용 라운드가 규율 개선 없이 비용만 태운다)은 사용자 rig 실측(비용 +69%, 코드 정확성 축 변별 0, 스킬 호출 0건)과 질적으로 정확히 같은 패턴이다.
- BudgetMLAgent(arXiv 2411.07464): 특정 ML 작업에서 GPT-4 단일-에이전트 대비 87~94% 비용 절감, 성공률은 더 나음 — 단 이건 "멀티에이전트가 이겼다"가 아니라 "값싼 모델 조합이 비싼 단일모델보다 쌌다"는 다른 축의 이야기이므로 이번 논제(협업 구조 자체의 이득)에 직접 원용하면 안 됨.

**종합 판단**: 성능 증거는 갈린다. 긍정 결과 대부분이 "이 논문이 제안한 특정 프로토콜/역할설계"의 이득이지 "블랙보드·토론 구조 자체"의 일반적 이득이 아니다. 부정 결과들은 오히려 "구조 자체보다 조건(라운드 수 제한, 역할 다양성, 표적화된 개입)이 결정적"이라고 일관되게 지적한다. 이는 사용자의 회의적 전제(비용 대비 효과 민감)를 뒷받침한다 — confidence: likely, 근거는 위 인용된 초록·요약 다수의 일관된 방향.

---

## 3. 대표 오픈소스 — 활성도와 "게시판" 구현 여부

검색 결과의 스타 수는 2026년 시점 웹 요약으로 confidence: unverified (GitHub 페이지 직접 대조 안 함).

| 프로젝트 | 성격 | 게시판/안건/반박 구현 여부 |
|:---|:---|:---|
| MetaGPT (~65k stars, 웹 요약) | PM→Architect→Engineer 역할극 소프트웨어 회사 시뮬 | **있음** — Environment 클래스가 공유 메시지 풀(shared message pool)을 갖고, 각 Role 이 `_watch()`로 관심 액션을 구독. arXiv 2308.00352 §설계 부분에 명시 |
| AutoGen/AG2 (~56k stars) | 유연한 대화 토폴로지의 멀티에이전트 대화 | GroupChat 이 사실상 공유 대화 로그(게시판에 가까움)이지만 "안건 상정·반박"을 위한 별도 스키마는 없음 — confidence: unverified, 코드 미대조 |
| ChatDev (~32k stars) | 가상 소프트웨어 회사, 챗 체인 방식 | 역할 간 순차 대화 위주, 전원-공개 게시판 구조는 확인 안 함 |
| CAMEL (~16k stars) | role-playing 에이전트 쌍 | 1:1 대화가 기본 단위, 다자간 게시판 구조는 확인 안 함 |
| CodeCRDT (arXiv 2510.18893) | 논문+구현체, "관찰 기반 조율" — 에이전트가 공유 상태를 관찰해 완료된 작업을 건너뛰고 충돌을 피함, 중앙 작업 배정 없음 | 코드 위치는 이번 조사에서 확인 안 함(논문 링크만 확보) |

코드 레벨까지 짚으라는 요청 대비, 이번 조사는 웹 검색만 수행했고 각 저장소를 clone 하거나 GitHub API 로 실제 소스를 열어 짚지 않았다. **이 표의 "구현 위치"는 논문 서술 수준이며, 실제 리포지토리 파일·클래스명 대조는 안 함** — 필요하면 다음 세션에서 `gh repo view`/clone 으로 검증.

---

## 4. Claude Code 로 구현 가능한가 — 사용자 rig 기준

### 이미 켜져 있는 것 (확인됨)

- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS: "1"` — `/Users/kimseungmin/claudebase/config/settings.json:3`. Agent Teams 는 팀 리더 세션 + 독립 컨텍스트를 가진 팀원들이 **공유 작업 리스트**로 일하고 **서로 직접 메시지**한다(공식 문서: https://code.claude.com/docs/en/agent-teams). subagent(main→sub, 결과만 회신)와 달리 teammate 는 서로 대화한다 — 이것이 "게시판"에 가장 가까운 1차 후보.
- `SendMessage` / `ListAgents` — 이번 세션 도구 목록에 이미 로드돼 있음. `ListAgents` 는 로컬 세션, 클라우드 세션, Remote Control 세션을 나열하고 `SendMessage({to: "<name>", ...})` 로 직접 메시지 가능. 단 클라우드 세션은 답장을 못 받는 편도 채널이라는 제약이 명시돼 있음(도구 설명 원문).
- **`shared_memory_*` MCP 툴 6종** (`mcp__plugin_oh-my-claudecode_t__shared_memory_{write,read,list,delete,cleanup}`) — `~/.claude/plugins/cache/omc/oh-my-claudecode/4.15.10/dist/lib/shared-memory.d.ts:1-83`. 파일시스템 기반 namespace/key-value 저장소, `.omc/state/shared-memory/{namespace}/{key}.json` 에 저장. `/team`·`/pipeline` 워크플로용 "세션 간 메모리 동기화"로 설계돼 있다. **이것이 사실상 blackboard 의 최소 구현체다** — 단 구독(subscribe)·통지(notify)·발행 프로필(publish profile) 개념은 없고 순수 KV 저장/조회뿐.
- **`wiki_*` MCP 툴 8종** (`wiki_add/query/read/list/lint/ingest/delete`) — 다수 에이전트가 결론을 축적하는 공유 지식 저장소. 커밋 프로토콜·스킬 레지스트리 문서(`omc-reference`)에서 참조됨(이번 조사에서 wiki 코드 자체는 미대조, confidence: unverified).
- Orca — `runtime/bin/tmux-orca-teams.sh` 및 `docs/CHANGELOG.md:96-117`(claudebase) 에 `orca claude-teams` 가 `claude --teammate-mode auto` 를 tmux 패널로 열어 여러 Claude 팀원을 실행한다고 기록됨. 사용자 auto-memory `reference_marinelab_container_ssh.md`, `reference_orca_orchestration.md` 에 크로스머신 dispatch 검증 완료라고 기록돼 있음(memory 항목, 재확인은 안 함).

### 무엇이 없는가 (확인된 공백)

- shared_memory 는 **push(구독) 가 아니라 pull(조회)** 만 지원 — "안건이 올라오면 반박이 자동으로 알림받는" 구조가 아니라, 누군가 그 key 를 읽으러 가야만 본다. Blackboard 논문들의 "게시되면 관심 있는 에이전트가 스스로 선택해 행동"이라는 능동적 선택(selection) 루프에 해당하는 메커니즘은 이 rig 안에 없음.
- "반박(rebuttal)" 이나 "안건(agenda)" 이라는 타입화된 스키마는 shared_memory·wiki 어디에도 없다 — 둘 다 범용 키-값/문서 저장소이지 토론 프로토콜(제안→반박→합의)을 인코딩하지 않는다.
- Agent Teams 의 "서로 직접 메시지"가 실제로 셋 이상이 볼 수 있는 **공개 게시판**인지, 아니면 1:1 DM 인지는 이번 조사에서 공식 문서 요약 수준까지만 확인했고, 세션 안에서 직접 실험은 안 함(조사 범위상 구현 금지).

### 이번 rig 실측과의 정합성 판단

사용자가 이미 확보한 A/B 결과(코드정확성 축 8/8 동점, 규율 축만 Δ+0.222, 그 런에서 Skill 호출 0건, 토큰 +41%·비용 +69% — SSOT `~/claudebase/eval/README.md:1-13` 및 그 아래 표)는 "스킬을 더 만들면 좋아진다"는 가설을 이미 한 번 반증했다. 이번 조사에서 찾은 부정적 증거(2510.20963, 2502.08788, M3MAD-Bench)의 공통 패턴 — "구조를 얹는 것 자체가 아니라 프로토콜 설계·역할 다양성·라운드 제한이 결정적이고, 무조건적 추가 상호작용은 비용만 태운다" — 는 정확히 같은 결의 경고다. 즉 "게시판·안건·반박 커뮤니티"를 신설하는 것은:

1. 이미 존재하는 배선(shared_memory, wiki, Agent Teams, SendMessage)을 켜서 실측하지 않고 새 레이어를 짓는 것이면 우선순위가 낮다 — 사용자의 확정 방향("무엇을 지울지 먼저")과 정면으로 반대되는 제안이 된다.
2. 만약 시도한다면, 최소 단위는 새 인프라가 아니라 **shared_memory 위에 "제안/반박" 두 개의 관례화된 key 패턴**(예: `namespace=<task>, key=proposal-N`, `key=rebuttal-N-of-proposal-M`)을 얹는 것 — 코드 0줄, 컨벤션만 추가. 이건 "게시판을 만들자"가 아니라 "이미 있는 KV 저장소를 특정 방식으로 쓰자"이므로 스킬 신설 없이 가능.
3. 어느 쪽이든 도입 전에 사용자 rig 형식의 A/B(스킬 호출 여부, 비용, 정확성 축 각각)를 먼저 설계해 두지 않으면, 이번 조사가 찾은 부정적 문헌들과 같은 실패 — "비용만 오르고 다수결이 오답에 수렴하거나 아무 차이 없음" — 을 반복할 위험이 문헌상 낮지 않다.

---

## 5. 확인 안 함 (정직한 공백 목록)

- MetaGPT/AutoGen/ChatDev/CAMEL 의 실제 GitHub 저장소를 열어 클래스·파일명을 대조하지 않음 — 표 4의 "구현 위치"는 논문 서술 근거만.
- Agent Teams 의 메시지가 팀 전원에 공개되는지 1:1 DM 인지 실제 동작을 이 세션에서 실험하지 않음(조사 범위가 구현 금지이므로 의도적 보류).
- shared_memory/wiki 가 `/team`·`/pipeline` 워크플로에서 실제로 몇 번 read/write 되는지 이 rig 의 세션 로그로 확인 안 함 — "존재한다"만 확인, "쓰이고 있다"는 별도 검증 필요.
- Blackboard 두 논문(2507.01701, 2510.01285)의 벤치마크 표·베이스라인 목록을 직접 열람하지 않음 — 초록 요약만.
- 시장/경매 계열이 "작업 품질"과 무관하다는 판단은 제목·요약 수준의 추론이며 본문 대조는 안 함.

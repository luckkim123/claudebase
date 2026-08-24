# 조사: 에이전트 경험 축적·전문성 형성 — 문헌 대조 + 자산 감사

조사일: 2026-08-22. 조사만, 구현 없음. 방향: 스킬을 더 만들자가 아니라 지울 것을 먼저 정한다.

---

## 0. 한 문장 결론

학계 문헌은 "경험을 저장하면 성능이 오른다"는 정량 근거가 여러 계열에서 반복 확인되지만
(Voyager, Zep, mem0, MemoryArena), **fresh-context/self-approval-금지와 영속 기억의 충돌을
정면으로 다루는 논문은 거의 없다** — 대신 최근 6개월 사이(2026-04~07) "메모리 오염 방지"라는
완전히 별도의 하위분야가 생겨났고, 그 방지 메커니즘(쓰기 시점 게이트·타입 격리·자기일관성
검증)은 사용자 rig의 `omp-learn` 승인 게이트·`learned.md` counter-example 규칙과 **구조적으로
동형(isomorphic)**이다. 즉 사용자는 이미 이 문제의 정답 형태(게이트가 있는 승격 파이프라인)를
가지고 있고, 학술 문헌이 새로 알려주는 것은 "그 게이트가 왜 필요한지"의 이론적 근거와
"게이트 없이 갔을 때 무슨 일이 벌어지는지"의 실패 사례들이다.

---

## 1. 이미 가진 것 — 실측 인벤토리

| 자산 | 메커니즘 | 학술 대응 개념 | 이미 경험 축적인가 |
|:---|:---|:---|:---|
| `claude-mem` 플러그인 (`~/.claude/plugins/cache/thedotmack/claude-mem`) | 매 Read/Edit/Bash → 압축된 "observation"으로 저장, 세션 종료 시 요약, 벡터 인덱스로 다음 세션에 auto-inject. `~/.claude-mem`에 SQLite+벡터 저장 (`skills/how-it-works/SKILL.md:10-22`) | 에피소딕 메모리 + 임베딩 기반 semantic recall (Generative Agents / MemGPT류) | **예, 이미 있다.** 세션 간 재구성 없이 이어짐. 단 갈래는 임베딩 기반 — omp/oms/omx 계열의 "결정론적 grep만" 원칙과 정면 대립 |
| auto-memory `~/.claude/projects/*/memory/MEMORY.md` + 개별 노트 | 세션 종료 시 한 줄 요약을 수동/반자동으로 축적, 다음 세션에 참조 | Semantic memory (요약된 사실), 사람이 쓰는 append-only 로그 | **예.** 단 자동 recall이 아니라 "참고하라"는 지시 수준 — 실제 grep/검색 메커니즘은 없음 (본 세션이 이 파일을 통째로 읽는 방식) |
| omp `.omp/learned.md` → `omp-learn`(rule-architect) → 인간 게이트 → `rules.json` | Heavy channel: evidence_count≥3, counter_examples==0, not user_overridden, 안정성 — AND 조건 전부 통과해야 승격 (`references/learning-protocol.md:195-222`) | **Reflection→memory promotion pipeline** + confirmation-bias 방지 게이트 | **예, 문헌보다 엄격하다.** 학술 게이트(ConsistencyGate 등)는 "평균 신뢰도 임계값" 하나인데, omp는 반례 하나로 즉시 승격 차단 |
| omp `.omp/wiki/*.md` | Light channel: 무게이트 자동 append, 다음 세션 결정론적 grep으로 recall, 절대 rule로 승격 안 됨 (§5, §6.D) | Procedural/episodic memory, "advice not fact" | **예.** 단 "경험이 강해질수록 규칙이 된다"는 승격 경로가 명시적으로 닫혀 있음(§6.D "No enforcement from the light channel") — 이것 자체가 fresh-context/오염 방지책의 하나 |
| oms `.oms/wiki/{convention,pattern,decision,reference,history}/` (2계층: paper-local + ascent로 찾은 global) | `confidence: low→med→high`(반복 관찰로 상승, 병합 시 강한 쪽 유지), `pattern/`은 영구 light-only, `convention/`만 heavy 후보 (`references/wiki/README.md:43-59`) | Confidence-weighted memory consolidation, 사용자별 persona 분화(global wiki=이 저자의 문체·습관) | **예. 사용자별 persona/전문성 축적의 가장 구체적 예.** "이 사용자는 항상 ablation을 먼저 한다"는 global-level 습관 기억이 이미 논문 저술 시 재사용됨 |
| omx `wiki-curator` agent + `omx wiki gc/lint` | 읽기전용 curator가 dead/dormant 판정, merge 방향 제안 → 인간 승인 → `gc-apply` (`agents/wiki-curator.md:1-37`) | Memory pruning / forgetting (문헌에서 거의 안 다뤄지는 축, §4 참고) | **예, 그리고 이건 문헌에 드문 기능이다.** 대부분의 논문은 "무엇을 저장할지"만 다루고 "무엇을 잊을지"는 다루지 않는다 |
| tokensave/code-review-graph/graphify 코드그래프 3종 | 코드 자체의 구조를 색인 — 에이전트의 "경험"이 아니라 "환경의 사실" | 해당 없음(외부 지식 베이스이지 에이전트 memory 아님) | **아니다.** 이건 subagent가 매번 새로 읽는 게 아니라 공유된 정적 인덱스이므로 "경험 축적" 범주 밖 |

**핵심 관찰**: 사용자 생태계는 이미 (a) heavy/light 2채널 분리, (b) 승격 게이트, (c) confidence
누적, (d) forgetting/gc, (e) 2계층(local/global) persona 분화까지 갖췄다. 학술 문헌에 있고
사용자 시스템에 **없는** 것은 딱 하나: **에이전트별(role별) 절차 기억(procedural skill library)의
자동 축적**이다 — 지금은 사람이 CLAUDE.md/skill 파일을 손으로 고치는 것이 유일한 "스킬이 굳어지는"
경로다. 이것이 문헌에서 말하는 Voyager류 skill library에 가장 가까운 빈틈이다.

---

## 2. 학술 갈래별 요약

### 2.1 Skill/experience library — Voyager 계열

- **arXiv:2305.16291** (Voyager, 2023) — Minecraft agent. 커리큘럼 + "ever-growing skill library of
  executable code" + iterative prompting. **초록에 명시된 수치**: prior SOTA 대비 아이템 3.1~3.3x,
  마일스톤 15.3x 빠름, 이동거리 2.3x. `confidence: verified`(초록 직접 확인). **주의**: 이 수치들은
  "skill library 있음 vs 없음" ablation이 아니라 "Voyager vs 이전 SOTA 기법 전체" 비교다. 초록만으로는
  skill-library-제거 ablation 수치를 확인하지 못했다(`confidence: unverified`) — 위 §1의 서베이가
  이 15.3x를 "스킬 라이브러리 제거 시 저하"로 인용했는데, 이는 **오귀속 가능성**이 있다. 원문 ablation
  섹션을 직접 읽지 않았으므로 단정하지 않는다.
- 코드로 저장되는 스킬(파라미터화된 함수)이라는 점이 중요 — 이후 CBR·Agent Workflow Memory 계열의
  "재사용 가능한 절차" 아이디어의 원형.

### 2.2 Episodic/semantic/procedural 분류 — 서베이 SSOT

- **arXiv:2603.07670** "Memory for Autonomous LLM Agents: Mechanisms, Evaluation, and Emerging
  Frontiers" (2026-03) — `confidence: likely`(WebFetch로 본문 일부 확인, 전문 정독은 아님).
  4층 분류(working/episodic/semantic/procedural)를 제시하고 **"episode→semantic 통합(consolidation)
  단계가 가장 부실하게 다뤄진다"**고 비판 — 현재 시스템 대부분이 규칙 기반이거나 불안정한 LLM
  요약에만 의존한다는 지적은, omp의 "evidence_count≥3 AND counter_examples==0" 같은 명시적 규칙
  기반 승격 게이트가 학술 상태보다 앞서 있다는 뜻이기도 하다.
- **정량 근거 표(서베이 2.4절 인용, 원출처 재확인 안 함 — `confidence: unverified`, 2차 인용)**:
  - Generative Agents: 메모리 제거 시 48시간 내 "일관된 다일간 계획"이 "반복적·맥락없는 응답"으로 붕괴
  - MemoryArena: 활성 메모리 에이전트 80% vs 긴 컨텍스트만 사용 45% (작업완료율)
  - 결론 인용: "has memory 대 does not have memory의 격차가 종종 서로 다른 LLM 백본 간 격차보다 크다"
- **신선도-격리 트레이드오프(4.1절, 8절)**: 컨텍스트 내 메모리는 투명하지만 요약을 반복하며 "희귀하지만
  중요한 세부사항"(예: "프로덕션 DB 직접 호출 금지")이 사라진다는 구체 사례를 든다. 긴 컨텍스트 윈도우도
  근본 해법이 아니다(attention의 quadratic 비용, attentional dilution) — **"무엇을 컨텍스트에 넣을지
  큐레이션해야 한다"**는 결론. 이는 사용자의 T11 Priority Context(≤500자, REPLACE-on-write, `omp
  learning-protocol.md:404-410`)와 같은 방향의 설계 판단이다.

### 2.3 MemGPT/Letta — 페이징된 메모리

- **arXiv:2310.08560** (MemGPT) — LLM 컨텍스트를 OS의 RAM처럼 취급. Core Memory(컨텍스트 내)/Recall
  Memory(검색 가능한 대화 이력)/Archival Memory(도구 호출로 조회하는 장기 저장)의 3계층. 에이전트
  자신이 페이징을 수행(도구 호출로). `confidence: likely`(2차 출처 다수 일치, 원문 미확인).
  구현체는 Letta로 개명·오픈소스화됨.
- 이 아키텍처는 claude-mem의 3계층(observation 압축→요약→auto-inject)과 구조적으로 유사 — 즉
  사용자가 이미 이 패턴을 플러그인으로 보유.

### 2.4 mem0 — 정량 효과 가장 강한 프로덕션 시스템

- **arXiv:2504.19413** (ECAI 2025) — LLM-as-Judge 지표에서 OpenAI 대비 26% 상대개선, graph memory
  변형은 기본 대비 +2%p. p95 지연 91% 감소, 토큰 비용 90%+ 절감. LOCOMO 벤치마크 기준.
  `confidence: likely`(WebSearch 요약, 원문 수치 직접 대조는 안 함).
- 메모리 갱신 연산이 ADD/MERGE/UPDATE/DELETE로 명시적 — omp의 "promoted/rejected/superseded"
  라이프사이클과 같은 계열의 설계.

### 2.5 Zep — temporal knowledge graph

- **arXiv:2501.13956** — Graphiti 엔진, 사실마다 유효 시점을 기록해 "사실이 바뀌면 옛 것을 무효화"하는
  모순-없는 응답. DMR 벤치마크에서 MemGPT 대비 94.8% vs 93.4%, 정확도 최대 18.5% 개선 + 지연 90%
  감소(baseline 대비). `confidence: likely`(2차 출처).
  → **stale 지식 문제에 대한 정면 대응 사례**: "언제 사실이었는지"를 프로비넌스로 남기는 방식은
  사용자의 `learned.md`의 `first_seen`/`last_seen`/`counter_examples`와 같은 발상.

### 2.6 Reflexion — reflection→memory의 원형

- **arXiv:2303.11366** — 환경 피드백을 언어로 자기반성해 episodic memory buffer에 저장, 다음 시도에서
  재사용. 파라미터 업데이트 없이 학습("verbal reinforcement learning"). 여러 코딩·의사결정 벤치마크에서
  SOTA. `confidence: verified`(WebSearch 요약이 원저자 설명과 일치, 표현 다수 상호검증).
  → 사용자 rig의 관점에서 중요한 점: Reflexion은 **같은 태스크를 반복 시도하는 단일 에이전트**를
  전제로 설계됐다. subagent-driven-development처럼 **매 태스크마다 fresh implementer**를 쓰는 구조에는
  Reflexion의 "자기 자신의 과거 실패를 학습"이라는 전제가 자연스럽게 적용되지 않는다 — 오히려 그 반성
  버퍼를 다음 태스크의 fresh agent에게 "물려주면" 그것이 곧 확증 편향 전이 경로가 된다(§4).

### 2.7 ExpeL — 이질적 태스크 간 통찰 추출

- **arXiv:2308.10144** — 훈련 태스크에서 경험 풀을 모으고, 거기서 "규칙/통찰"을 추출해 별도 태스크에
  단 1회 시도로 적용. `confidence: likely`(2차 출처).
  → ReAct 계열 에이전트에 사후적으로 통찰을 주입하는 방식으로, omp의 wiki→learned.md 승격과 유사한
  "경험 풀 → 정제된 규칙"의 2단계 구조.

### 2.8 ACE (Agentic Context Engineering) — 생성/반성/큐레이션 역할 분리

- **arXiv:2510.04618** (ICLR 2026) — 컨텍스트를 "진화하는 플레이북"으로 취급, Generator/Reflector/
  Curator 3역할로 노동을 분리(한 모델에 다 맡기지 않음). Agent 벤치마크 +10.6%, 금융 도메인 +8.6%.
  `confidence: likely`. **직접적 시사점**: 이 3역할 분리는 사용자 rig의 "저작(writer)과 검토(reviewer)를
  분리된 컨텍스트에서"라는 규율과 같은 형태다 — 다만 ACE는 이걸 컨텍스트/프롬프트 진화에 적용했고,
  사용자는 코드 저작에 적용했다는 차이. **"generator가 자기 반성을 직접 기록하면 브레비티 편향·컨텍스트
  붕괴가 생긴다"**는 문제의식이 정확히 사용자의 "self-approve 금지" 규율의 근거가 될 수 있다.

### 2.9 Case-based reasoning (CBR) for LLM agents

- **arXiv:2504.06943** (Review) — retrieve→reuse→revise→retain의 CBR 사이클을 LLM agent에 이식.
  "similarity 기반 검색보다 무작위 예시 샘플링이 다양한 문맥 추론에서 더 나을 때가 있다"는 발견을
  언급 — 이는 omp의 "임베딩 검색 절대 금지, grep만" 원칙과 부분적으로 공명(검색 방식의 정교함이
  항상 이득은 아니라는 근거). `confidence: unverified`(요약 문장 하나, 원문 대조 안 함).
- **arXiv:2508.16153** (Memento) — 파라미터 파인튜닝 없이 CBR 메모리만으로 지속적 개선.
  `confidence: unverified`(제목·초록 수준만 확인).

### 2.10 Multi-agent persona/role 분화

- **arXiv:2506.15451** (AgentGroupChat-V2) — 역할 특화 5-agent 팀: 정확도 32.5%→53.5%(+64.6%,
  2→5 agent). 반대로 동질(non-specialized) 팀은 agent 수 늘수록 34.5%→31.5%로 **하락**.
  `confidence: likely`(WebSearch 요약).
- **arXiv:2602.01011** ("Multi-Agent Teams Hold Experts Back") — **반대 방향 증거**. 자율 협력
  LLM 팀은 지정된 전문가(expert agent) 단독 성능을 못 따라가고, ML 벤치마크에서 최대 41.1% 저하.
  원인은 "합의 추구 경향"(integrative compromise) — 전문가 의견에 적절히 가중치를 주지 않고
  평균을 낸다. 팀 규모 커질수록 악화. `confidence: likely`(WebFetch 요약, 원문 미정독).
  → **핵심 긴장**: role 분화 자체는 이득이지만(2506.15451), "역할이 있는데도 그 전문성을 실제로
  존중하지 않는" 자율 협의 구조는 오히려 해가 된다(2602.01011). 이건 사용자의 "self-approve 금지 +
  fresh reviewer" 규율이 정확히 막으려는 실패 모드다 — 즉 **전문화(경험 축적)의 이득은 "그 전문성을
  검증 없이 신뢰하는 합의 구조"와 결합하면 사라지거나 역전된다**는 것이 이 두 논문의 조합이 말해주는 바.

---

## 3. 설계 긴장: fresh-context/self-approve-금지 vs 영속 기억

### 3.1 문헌이 실제로 다루는 부분

| 문제 | 다루는 논문 | 대응 메커니즘 | 수치 |
|:---|:---|:---|:---|
| 메모리 오염(hallucinated fact가 전제로 굳음) | **arXiv:2605.28009** MemGuard | 쓰기/유지/검색 단계에서 타입별 격리 | 신뢰성 최대 +28.27%p, 검색 토큰 5.8x 감소 |
| 확증 편향 축적(잘못된 결론이 반복 관찰로 강화) | 서베이 2604.16548, 2604.15774 (요약 수준) | 명시적 대응책 서술 없음, 문제 정의만 | 없음 |
| stale 지식(사실이 시간에 따라 바뀜) | **arXiv:2501.13956** Zep | 시점 기록 + 모순 시 구 사실 무효화 | DMR +18.5%, 지연 −90% |
| 쓰기 시점 환각 방지 | **arXiv:2607.22962** ConsistencyGate | K회 자기일관성 샘플링, 평균 신뢰도 임계값(τ=0.7) 통과해야 저장 | 합성셋 오염율 50%→1.2%, 실제 대화셋 50%→34.1%(부분적) |

### 3.2 문헌이 다루지 않는 부분 (직접 확인, `confidence: verified` — 서베이 원문 대조)

**arXiv:2507.21046** (A Survey of Self-Evolving Agents, v4)의 §3.2.1 Memory Evolution을 WebFetch로
직접 확인한 결과: mem0/Memory-R1/A-mem/ExpeL/Agent Workflow Memory 등 방법론은 열거하지만,
**"fresh context per task"·"no self-approval"류의 격리 보장이 영속 기억과 충돌하는 지점을 다루는
절이 없다.** 8.3절("Safe and Controllable Self-Evolving Agents")은 일반적 안전 문제만 언급하고
메모리 오염이나 검증 프로토콜의 구체적 해법은 제시하지 않는다. 서베이 저자가 이를 미해결 문제로
남겨둔 것으로 읽힌다.

**따라서**: "격리 보장 vs 영속 기억"이라는 사용자의 프레임 자체는 학술 문헌에서 하나의 이름 붙은
문제로 다뤄지고 있지 않다. 가장 가까운 근사치는 (a) 메모리 오염 방지 논문들(§3.1, 쓰기 시점 게이트로
막음)과 (b) 멀티에이전트 합의-대-전문성 트레이드오프(§2.10, 2602.01011)의 **조합**이다 — 이 둘을
합치면 "영속 기억을 가진 에이전트에게 자기 판단을 그대로 신뢰시키지 말고, 쓰기 시점에 검증 게이트를
거치게 하라"는 결론이 나오는데, 이것이 정확히 사용자의 omp `rule-architect`(제안만)→인간 게이트
구조다.

### 3.3 사용자 rig에 대한 함의

- `superpowers:subagent-driven-development`의 "fresh implementer per task"는, 학술 용어로는
  **"에피소드 간 상태 비공유(no episodic carry-over)"**에 해당한다. Reflexion(§2.6)류의 자기반성
  버퍼는 이 전제와 상충하므로, subagent 각각에게 Reflexion 버퍼를 주는 것은 이 rig의 핵심 규율을
  깨는 방향이다.
- 반대로 **role-level(태스크 종류별) 절차 지식**은 다르다 — "구현자 role은 항상 이런 실수를 한다"는
  지식은 특정 에피소드의 상태가 아니라 role에 대한 semantic 지식이고, omp의 `learned.md`→게이트
  구조가 이미 이걸 안전하게 처리하는 경로다(관찰 3회 이상 + 반례 0 + 인간 승인).
- ACE(§2.8)의 Generator/Reflector/Curator 분리는 "저작자가 자기 경험을 스스로 규칙화하지 않는다"는
  원칙의 학술적 재확인이다 — 즉 **경험을 규칙으로 승격시키는 역할은 저작한 에이전트 자신이 아니어야
  한다**는 것이 문헌과 사용자 rig 양쪽에서 독립적으로 도출된 설계.

---

## 4. 제거·통합 관점 (사용자 확정 방향)

측정 없이 "만들자"는 제안은 입증 부담이 높다는 전제 위에서, 이번 조사가 드러낸 것은 **이미 4~5개의
서로 다른 축적 메커니즘(claude-mem, auto-memory, omp learned/wiki, oms wiki, omx wiki)이 각자
다른 결정(임베딩 vs grep, 게이트 있음 vs 없음, 승격 경로 있음 vs 영구 light-only)을 내리고 있다**는
사실이다. 새 메모리 시스템을 추가하기 전에 확인할 질문(구현·결정은 사용자 몫, 여기서는 사실만 제시):

- claude-mem(임베딩 기반)과 omp/oms/omx(grep 전용, 임베딩 영구 금지)는 **철학이 정반대**다.
  eval/README.md의 실측(스킬 호출 0건, 이득은 훅 주입 컨텍스트에서 나옴 — 서론에 인용된 실측)과
  겹쳐 보면, claude-mem의 auto-inject 컨텍스트가 실제로 세션 품질에 기여하는지도 같은 방법론
  (H_0/H_T A/B)으로 측정 가능한 대상이다. 이번 조사는 이 측정을 수행하지 않았다 — 제안만 남긴다.
- role별(구현자/검토자) 절차 지식을 축적하는 전용 메커니즘은 현재 **없다** — omp의 heavy channel은
  "이 프로젝트"에 대한 규칙이지 "이 role이 반복하는 실수"에 대한 규칙이 아니다. 이게 문헌이 가리키는
  진짜 빈틈이지만, 새 시스템을 얹기보다 **omp `learned.md`의 `source_stage`에 role 태그를 추가하는
  정도의 확장**으로 기존 게이트를 재사용할 여지가 있다(신설이 아니라 스키마 확장).

---

## 5. Open questions (구현 대상 아님, 판단 대기)

- claude-mem의 auto-inject가 harness eval(§eval/README.md 방법론)로 측정됐을 때 실제로 규율/정확성
  축에 기여하는지 — 미측정.
- 서베이(2603.07670)가 인용한 Voyager "15.3x" 수치가 skill-library ablation인지 SOTA 비교인지 —
  원문 ablation 절 미확인, 오귀속 가능성 있음.
- mem0/Zep 벤치마크(LOCOMO, DMR)는 대화형 챗봇 메모리용 벤치마크다 — 코딩 에이전트/subagent
  워크플로우에 그대로 전이되는지는 검증되지 않았다.

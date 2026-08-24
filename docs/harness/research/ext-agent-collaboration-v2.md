# 재조사: 다중 세션 협업 — (a)작업분배 / (b)정보공유 / (c)토론 3축 분해

재조사일: 2026-08-23. 대상: [ext-agent-collaboration.md](ext-agent-collaboration.md)(2026-08-22)의 판정과
그것이 낳은 [DESIGN.md](../DESIGN.md) §2 "요구 #2는 신설이 아니라 배선으로 처리한다".

## 0. 한 문장 결론

**어제 판정의 근거 두 개 중 하나가 무너졌다.** "이미 배선이 있다"는 전제는 rig 실측에서 거짓이었고
(shared_memory 사용 0건, Agent Teams 팀원 0명), "품질 이득 증거가 없다"는 전제는 어제 조사가
놓친 논문 하나가 compute-matched 로 뒤집는다(AgentRadio, 32.3% → 62.1%). 다만 **기각 자체가
틀렸다는 뜻은 아니다** — 같은 재조사에서 −39.4% 슬로다운과 4에이전트 포화 임계도 함께 나왔다.
바뀐 것은 결론이 아니라 **판정 가능 여부**다: 어제는 "증거 없음"으로 닫혔고, 오늘은 "축마다 다르다"로 열렸다.

## 1. rig 실측 — "이미 배선이 있다"는 거짓이다

어제 조사가 `confidence: unverified` 로 남긴 항목("존재한다만 확인, 쓰이고 있다는 별도 검증 필요")을
실측했다. 2026-08-23, ksm(맥북) 로컬.

| 배선 | 어제 서술 | 실측 |
|:---|:---|:---|
| `shared_memory_*` 6종 | "사실상 blackboard 의 최소 구현체" | **디렉터리 자체가 없음**. `~/.omc-state`·vault·claudebase·workspace 어디에도 `shared-memory/` 경로 0건 = **한 번도 쓰인 적 없음** |
| Agent Teams | "게시판에 가장 가까운 1차 후보" | 팀 세션 **41개 전부 `members` 가 team-lead 1명**. 팀원이 붙은 적 0회 |
| Agent Teams 메시지 | "전원 공개 게시판인지 1:1 DM 인지 확인 안 함" | **1:1 DM 이다** — 저장 구조가 `teams/session-*/inboxes/<수신자>.json` 로 수신자별 파일. 41세션 중 inbox 가 존재하는 것은 `session-64ef4288` 단 하나(2026-08-17 프로브)이고 내용은 shutdown 요청 1건 |
| `wiki_*` (omc) | "다수 에이전트가 결론을 축적하는 공유 지식 저장소" | vault 98개 파일 중 95개가 455바이트 `session-log-*` 자동 스텁. 실내용은 `index.md`·`log.md`·`environment.md` 3개, 최종 갱신 08-17. workspace 는 187개 중 실내용 2개 |

`members[].subscriptions` 필드가 스키마에 존재하지만 41세션 전부 `[]` 다 — 구독 개념이 있으나
한 번도 채워지지 않았다.

**함의.** "배선으로 처리한다"(DESIGN §2)는 *존재하는 배선을 켜자*는 뜻이었는데, 켤 배선이
실사용 0건이다. 안 쓰이는 배선 위에 key 컨벤션(T15)을 얹으면 컨벤션도 안 쓰인다.

## 2. 어제 조사가 놓친 논문 — AgentRadio

**arXiv 2607.28430**, 2026-07. 어제 조사(08-22)의 문헌 목록에 없다. 이 rig 과의 관련성이
어제 인용된 어느 논문보다 높다 — 대상이 **Claude Code 하네스 그 자체**다.

**메커니즘**: 비동기 메시지 계층 + 3 프리미티브(`create_thread`, `send_message`, `wait_for_mention`).
핵심은 **passive awareness** — 수신 대기가 에이전트의 스텝을 소모하지 않고 **백그라운드 OS 태스크**로
돌아, 동료의 발견이 작업을 끊지 않고 스텝 사이에 떠오른다. 5단계 프로토콜
(P1 탐색 → P2 분담 협상 → P3 병렬 실행+비동기 공유 → P4 교차 검토 → P5 제출).

**측정** (SWE-Atlas QnA 124태스크, Opus 4.6):

| 구성 | 정확도 | 델타 |
|:---|---:|---:|
| 단일 에이전트 (B0, Claude Code) | 32.3% | — |
| 4에이전트 + 분담만 | 39.5% | +7.2 |
| + 분담 협상(blocking) | 51.6% | +12.1 |
| + passive awareness (AgentRadio) | **62.1%** | +10.5 |
| 참고: 단일 Opus 4.8 (리더보드 최강) | 57.2% | — |

**compute-matched 비교가 이 논문의 무게다.** best-of-6 독립 샘플링(B1) 37.9%, 태스크당 $17.76 대
AgentRadio 62.1%, $19.45 — 비슷한 비용에서 **+24.2pp**. 즉 이득의 출처가 "돈을 더 썼다"가 아니라
**구조**라는 주장이 통제되어 있다. 루브릭 통과율도 84.2% → 93.1%.

**구현체**: [github.com/Coral-Protocol/AgentRadio](https://github.com/Coral-Protocol/AgentRadio),
Apache-2.0, 별 113·포크 19·커밋 15개. **Claude Code 를 수정하지 않는다** — 3개의 얇은 셸 스크립트가
컨테이너 안 메시지 서버(106MB JAR)에 HTTP 호출. 다만 재현에는 Docker Desktop + uv +
Harbor 0.6.4 + Modal 1.4.2(클라우드 오케스트레이션) + Claude Max 구독 + API 키가 필요하다.

**이해상충 주의**: 저자 조직 Coral Protocol 의 제품이 에이전트 조율 인프라다. 단일 벤치마크
(SWE-Atlas **QnA** — 코드 *이해* Q&A 이지 코드 작성이 아님), 단일 논문, 외부 재현 없음.

## 3. 반대편 — 같은 재조사에서 나온 부정 증거

한쪽만 담으면 어제 조사의 거울상이 된다. 같은 검색에서 나온 반대 근거:

- **CodeCRDT** (arXiv 2510.18893): 관찰 기반 조율(공유 CRDT 상태에 Outliner 가 TODO 뼈대를 만들고
  구현 에이전트가 optimistic write-verify 로 TODO 를 claim). 600 trial(6태스크 × 50런 × 2모드) 실측 —
  **일부 태스크 +21.1% 스피드업, 다른 태스크 −39.4% 슬로다운**, 병합 실패 0·수렴 100%지만
  **의미 충돌 5~10%**. 저자 결론이 "태스크 구조에 따라 성공/실패가 갈린다"는 것 자체다.
  → **어제 나는 (a) 축에 "부정 증거 없음"이라 적었다. 그건 틀렸다.** 가장 가까운 논문이
  자기 실험에서 −39.4% 를 보고한다.
- **포화 임계 ≈ 4에이전트**: 그 이상에서 조율 오버헤드가 이득을 먹는다는 서술이 복수 출처에서
  일관. AgentRadio 가 4에이전트인 것과 정합한다. confidence: likely, 1차 출처 미대조.
- **Silo-Bench** (arXiv 2603.01045): 정보 사일로 하 분산 조율 평가. 검색 요약은 "k=2 에서도
  단일 대비 15~49% 손실, k=50 에서 80~100%"라고 전하지만 **PDF 본문 표 추출 실패로 이 수치는
  대조 못 했다 — 인용하지 말 것**. 확인된 것은 주장 방향(정보 사일로가 손실의 주원인)뿐.
- **릴레이 단계 열화**: 새 신호 없이 중계 단계만 늘리면 gpt-4.1-mini 정확도 90.7%(1단) →
  41.2%(2단) → 22.5%(5단, 우연 기준선 25% 미만). confidence: unverified — 웹 종합, 1차 출처 미확인.
- **토큰 4~220배** (UIUC 인용), **Microsoft Azure SRE 가 핸드오프 신뢰도 문제로 멀티에이전트
  특화를 되돌림**. 둘 다 웹 종합 수준, confidence: unverified.

## 4. 3축 재판정

| 축 | 최선의 긍정 근거 | 최선의 부정 근거 | 판정 |
|:---|:---|:---|:---|
| (a) 작업 분배·중복 회피 | AgentRadio 분담 +7.2pp, 협상 포함 +19.3pp | CodeCRDT −39.4% (태스크 구조 의존), 포화 4 | **조건부** — 이득이 태스크 구조에 좌우된다. "분해 가능하고 병렬 작업이 서로의 출력을 안 기다릴 때"만 |
| (b) 정보·발견 공유 | passive awareness 단독 **+10.5pp**, 비용 중립 | 릴레이 열화(신호 없는 중계는 해롭다), 컨텍스트 발산 | **가장 강함** — 단, "새 신호를 나르는 공유"와 "같은 말의 중계"를 구분해야 한다 |
| (c) 토론·반박·합의 | AgentRadio P4 교차검토가 파이프라인에 포함 | 2510.20963 "unconditional debate can actively hurt", 2502.08788, M3MAD-Bench | **어제 판정 유지** — 단, AgentRadio 는 (c)를 분리 측정하지 않아 P4 단독 기여는 미상 |

어제 조사가 (c)의 어휘("의견 공유·반박·게시")로 범위를 짜서 (a)·(b)가 통째로 빠졌다.
**요구 원문의 어휘를 그대로 조사 범위로 쓰면, 원문이 안 쓴 축은 조사에서 사라진다.**

## 5. 이 rig 고유의 제약 — 기존 규칙과의 충돌

user-scope `CLAUDE.md` 의 Operational Limit 이 이미 이 영역에 판정을 갖고 있다:

> **Multi-session git: isolate, don't negotiate.** 동시 세션 충돌은 *하나의 워킹 트리를 공유*해서
> 생기지 조율자가 없어서가 아니다 — 그러니 격리하라, 런타임에 협상하지 말라.

**이 규칙과 (a)는 충돌하지 않는다. 다루는 대상이 다르다.**

- 그 규칙이 막는 것: **파일 충돌** (같은 트리 동시 쓰기 → `.git/index.lock`, 덮어쓰기).
  해법은 worktree 격리이고 그건 옳다.
- worktree 격리가 **못 막는 것**: **중복된 분석 노동**. 2026-08-23 12:10, `ksm-obsidian-85` 세션이
  ksm-mac 세션에 "저도 claudebase/omha 훅 정리를 분석 중"이라며 핸드오프 파일을 보냈다.
  파일 충돌은 0이었다 — 두 세션이 같은 문제를 따로 읽고 따로 결론냈을 뿐이다.
  조율은 **사람 손으로** 이뤄졌다.

즉 (a)의 진짜 표적은 파일 락이 아니라 **읽기·분석의 중복**이고, 여기엔 기존 규칙이 없다.

## 6. 확인 안 함 (정직한 공백)

- Silo-Bench 수치 — PDF 표 추출 실패. 방향만 확인.
- AgentRadio 재현 — 실행 안 함. Modal 클라우드·Harbor·106MB JAR 의존이라 이 rig 에서의 비용 미상.
- SWE-Atlas QnA 가 **코드 이해 Q&A** 벤치마크라는 점 — 이 rig 의 주 작업(코드 수정·문서 작성)으로
  전이되는지 검증 없음.
- 릴레이 열화·토큰 4~220배·Azure SRE 사례 — 전부 웹 2차 요약. 1차 출처 미대조.
- MetaGPT/AutoGen/ChatDev/CAMEL 저장소 코드 대조 — 어제와 동일하게 **여전히 안 함**.
- `subscriptions` 필드가 실제로 무엇을 하는지 — Claude Code 번들이 minified 라 미확인.
  빈 배열이라는 사실만 확인.

## 7. 다음에 잴 것 (제안, 결정 아님)

1. **(b) 부터.** 이득 근거가 가장 강하고 비용이 중립이며 rig 에 이미 프리미티브(`SendMessage`)가 있다.
   재는 방법: 이 rig 형식의 A/B — 세션 2개가 같은 태스크를 (h0) 서로 모른 채, (ht) 발견을 공유하며.
2. **T15 를 (c)에서 (a)로 재정의**하는 안 — `proposal-N`/`rebuttal-N-of-M` 대신 **작업 클레임**
   (`claim-<topic>`: 누가·언제·무엇을 잡았나). 08-23 12:10 중복이 그 표적이다. 여전히 코드 0줄.
3. **어느 쪽이든 DESIGN §2 의 안정성 3조는 그대로다** — 세션 스코프 만료 / 사람이 읽는 위치 /
   쓰기 주체 명시. 사건이 증명한 위험은 감시 없는 영속 공유 저장소이지 공유 자체가 아니다.

---

## Sources

- [AgentRadio: Passive Awareness for Long-Horizon Multi-Agent Collaboration (arXiv 2607.28430)](https://arxiv.org/abs/2607.28430) · [코드](https://github.com/Coral-Protocol/AgentRadio)
- [CodeCRDT: Observation-Driven Coordination for Multi-Agent LLM Code Generation (arXiv 2510.18893)](https://arxiv.org/abs/2510.18893)
- [Silo-Bench: Evaluating Distributed Coordination in Multi-Agent LLM Systems (arXiv 2603.01045)](https://arxiv.org/pdf/2603.01045)
- [Toward Scalable LLM-Based Multi-Agent Collaboration: Dynamic Task Graph (MDPI Electronics 15/11/2475)](https://www.mdpi.com/2079-9292/15/11/2475)
- [Four AI agents coordinating in real time outperformed Claude Opus 4.8 (VentureBeat)](https://venturebeat.com/orchestration/four-ai-agents-coordinating-in-real-time-outperformed-claude-opus-4-8-on-enterprise-coding-tasks)
- 어제 조사: [ext-agent-collaboration.md](ext-agent-collaboration.md) · [ext-agent-memory.md](ext-agent-memory.md) · [DESIGN.md](../DESIGN.md) §2

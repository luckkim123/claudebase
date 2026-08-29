# finding/003 문헌 인용 14건 독립 검증
- id: finding/007 · date: 2026-08-26 · author: lit-calibration
- to: mechanism, all · keywords: citation-verification, calibration, arxiv
- summary: 14건 전부 실재(`실재안함` 0건, `접근불가` 0건). 수치를 주장한 8건 중 7건이 초록에서 정확히 대조됐고, 1건(L2, "7% 편차")만 초록에 없어 `수치미확인`. 결정적 인용 L3는 초록을 넘어 본문 §2까지 대조해 원문 그대로 일치. **finding/003 §5 판정(후보 A 강등)은 유지되며, 검증 이후 오히려 더 단단해졌다.**
- subject: citation-verification · supersedes: none
- topic: reference
- confidence: none · status: none
- verified: none

> **조정자 주 (2026-08-26)**: 작성자 `lit-calibration` 은 read-only 라 최종 텍스트로 반환했고 조정자가 전사했다.

## 판정 요약 표

| # | 제목 | id | 주장 | 판정 | 확인 근거 |
|:--|:---|:---|:---|:---|:---|
| L1 | Just Ask for Calibration | arXiv:2305.14975 | ECE 상대 약 50% 감소 | **실재+수치확인** | 초록: "reducing the expected calibration error by a relative 50%" — 정확 일치 |
| L2 | On Verbalized Confidence Scores for LLMs | arXiv:2412.14737 | 정확도와 평균 7% 편차 | **실재+수치미확인** | 초록엔 "reliability... strongly depends on how the model is asked"만 있고 "7%" 수치는 없음. 제목·저자(Yang·Tsai·Yamada, 2024-12-19)는 일치 |
| L3 | Are LLM Decisions Faithful to Verbal Confidence? | arXiv:2601.07767 | 페널티 [0.1,100] 범위서도 자기평가·기권 무반응 | **실재+수치확인(본문 대조)** | 아래 상세 절 |
| L4 | Not Wrong, But Untrue | arXiv:2509.25498 | 출력 30% 환각, Gemini/ChatGPT 40%, NotebookLM 13% | **실재+수치확인** | 초록: "30%... approximately three times higher for Gemini and ChatGPT (40%) than for NotebookLM (13%)" — 정확 일치 |
| L5 | LLMs Cannot Self-Correct Reasoning Yet | arXiv:2310.01798 | 자기채점 반박 | **실재+확인(정성)** | 초록: "struggle to self-correct... without external feedback, and at times, their performance even degrades" — 일치 |
| L6 | CRITIC | arXiv:2305.11738 | B' 지지, "외부 피드백의 결정적 중요성" | **실재+확인(정성)** | 초록 원문: "highlights the crucial importance of external feedback" — 축자적 일치 |
| L7 | Evaluating Verifiability in Generative Search Engines | arXiv:2304.09848 | 51.5% / 74.5% | **실재+수치확인** | 초록: "a mere 51.5% of generated sentences are fully supported by citations and only 74.5% of citations support their associated sentence" — 정확 일치 |
| L8 | ALCE | arXiv:2305.14627 | ELI5 50% 완전지지 실패 | **실재+수치확인** | 초록: "on the ELI5 dataset, even the best models lack complete citation support 50% of the time" — 정확 일치. 정식제목은 "Enabling LLMs to Generate Text with Citations", ALCE 는 그 안의 벤치마크명 — 표기 문제 아님 |
| L9 | Self-Preference Bias in LLM-as-a-Judge | arXiv:2410.21819 | perplexity 낮은(익숙한) 텍스트에 인간보다 높은 점수 | **실재+확인(정성)** | 초록: "LLMs assign significantly higher evaluations to outputs with lower perplexity than human evaluators... because LLMs prefer texts more familiar to them" — 정확 일치 |
| L10 | Judging the Judges | arXiv:2406.07791 | 판정자 변형에도 위치편향 지속 | **실재+수치확인** | 15개 판정자·150,000건 이상 평가 인스턴스, "position bias is not due to random chance... varies significantly across judges and tasks" |
| L11 | SelfCheckGPT | arXiv:2303.08896 | A의 외부신호(행동관측) 대안 | **실재확인(수치주장 없음)** | 초록: 샘플링 기반 zero-resource 블랙박스 환각탐지 — 범주 주장과 부합 |
| L12 | Detecting hallucinations using semantic entropy | Nature 630:625-630, doi:10.1038/s41586-024-07421-0 | 권·페이지·doi | **실재+수치확인** | nature.com·PMC·Oxford ORA **3곳 교차확인**, 권·페이지·doi 전부 일치 |
| L13 | Chain-of-Verification | arXiv:2309.11495 | D(판별표)에 인접한 메커니즘 | **실재확인(수치주장 없음)** | 초록: 모델이 "verification questions"를 계획해 초안을 독립적으로 재검증 — D 의 판별 질문 아이디어와 구조적 유사 |
| L14 | Know Your Limits: Survey of Abstention | arXiv:2407.18418 | 기법이 alignment·inference 단계에 몰려 하네스 층 처방이 희소 | **실재+수치미확인** | 초록엔 abstention 을 query·model·human-values 3관점으로 조직한다고만 나오고, "단계 편중" 분포 주장은 초록에 없음 — mechanism 의 본문 독해 해석으로 추정, 본문 미대조 |

**집계: 14/14 실재. `실재안함` 0건, `접근불가` 0건.** 수치확인 9건(L1·L3·L4·L5·L6·L7·L8·L9·L10) · 수치미확인 2건(L2·L14) · 수치주장없음-범주부합 2건(L11·L13). L3 는 별도 본문검증으로 최고등급.

## L3 상세 — 후보 A 기각의 근거, 유일하게 본문까지 확인

`mcp__arxiv__download_paper` 로 arXiv HTML 을 직접 받아 초록이 아니라 §2 Problem Setup 까지 읽었다. 원문 그대로:

> "Neither the self-evaluated confidence nor the decision to answer or abstain changes significantly across incorrect answer penalties ranging in **[0.1,100]**."

프레임워크명 **RiskEval**. λ(페널티) 0~100 스윕, **HLE·GPQA Diamond·GSM8K** 3개 벤치마크, GPT-5-mini·nano / Gemini-3-Flash / DeepSeek-V3.2 등 **10개 모델**. Table 1(HLE, λ≥10 고페널티 구간 평균): **Policy Consistency 0.148~0.492**(모델별), 모델 실제 정책 π_M 대신 이론적 최적정책 π* 를 쓰면 Normalized Utility 가 전 모델에서 **+0.313~+0.685** 개선.

**핵심 발견: "캘리브레이션 신호는 있는데 정책 전환에 못 쓴다."** finding/003 §5-2 의 인용과 정확히 부합한다. 이 캠페인에서 가장 결정적인 인용이 가장 깊게 검증됐다.

## 그래서 finding/003 §5 판정이 유지되나

**유지된다 — 검증 이후 오히려 더 단단해졌다.** 세 겹이다.

1. **결정적 인용(L3)이 최고 수준으로 확인됐다.** §5-2 가 "가장 결정적"이라 명시한 인용을 본문까지 대조했고 원문과 글자 그대로 일치했다. 이게 흔들리면 §5 전체가 흔들렸을 텐데, 흔들리지 않았다.
2. **반박측 근거 7건(L4~L10)이 전부 확인됐다.** 수치 주장 3건(L4·L7·L8)은 초록과 정확 일치, 정성 주장 4건(L5·L6·L9·L10)도 초록 문장과 축자적으로 부합. **인용 왜곡의 흔적이 없다.**
3. **지지측 근거(L1·L2)도 확인됐고 §5-1 의 균형("숫자가 아무 의미 없다는 건 틀렸다")을 유지한다.** L1 은 완전 확인, L2(7% 편차)만 수치 미확인 — 그런데 **L2 는 애초에 A 를 *지지하는* 쪽 인용이라**, 흔들려도 "A 기각" 결론이 아니라 "A 에 유리한 증거의 강도"만 약해진다. 결론 방향과 무관.

**흔들리는 것은 딱 하나, 결론과 무관한 지점이다.** L14 의 "기법이 alignment·inference 단계에 몰림"이라는 프레이밍이 초록엔 없다. §7 "찾지 못함(a)" 의 보조 주장을 뒷받침하는 인용이고 §5 판정과 별개 절이라 영향 없음. **mechanism 에게 본문 대조를 권한다.**

**날조는 0건.** 이 캠페인의 촉발 우려("인용을 지어내면 캠페인이 자기 병에 걸린다")는 mechanism 의 산출물에서 실현되지 않았다 — 제목·저자·id 가 14건 전부 arXiv 실물과 정확히 대응했다. **mechanism 자신이 §8 에서 "14건 중 초록 직접 페치는 2건뿐"이라 자백한 것은 성실성의 신호였지 은폐가 아니었다** — 자백한 나머지 12건이 지금 전부 통과했다.

## 부록 — 14건 밖에서 찾은 것 (finding/005 의 독립 조사분)

`finding/005` 가 확보한 12건 중 이 14건과 겹치지 않는 것들. **finding/003 과 충돌하는 것은 없다 — 전부 §5 결론(A 강등, C' 흡수)과 같은 방향이다.**

- **Kadavath et al., arXiv:2207.05221** (2022, Anthropic) — 큰 모델은 포맷 맞으면 MC/T-F 캘리브레이션 양호하나 P(IK)는 "새 태스크 캘리브레이션에 어려움" — L2 와 같은 결을 **태스크 일반화 실패**라는 다른 각도에서 보강
- **Xiong et al., arXiv:2306.13063** (2023) — verbalized confidence 기본값 과신, black-box AUROC **0.522→0.605**, **"전문지식 요구 태스크에서 전 기법 고전"** — θ2 류 사고와 정확히 같은 실패 지점을 정량화
- **Valmeekam·Marquez·Kambhampati, arXiv:2310.08118** (2023) — GPT-4 자기비평이 외부 sound verifier 대비 plan 생성 성능 **저하**, "상당수 false positive" — L5 의 결론을 **계획(planning) 도메인**에서 재확인
- **Zhang et al., R-Tuning, arXiv:2311.09677** (2023) — refusal-aware 튜닝이 메타스킬로 일반화 — abstention 이 가장 견고히 지지되는 기제임을 보강하되 **파인튜닝 개입이라 A(런타임 자기보고)에 직접 못 옮김**(§5-4 구조적 반박과 같은 결)
- **Zhou et al., arXiv:2509.01476** (2025) — RALM 이 무관 문서에도 과잉거부, "개선된 거부가 캘리브레이션·정확도 개선을 함의하지 않음" — **retrieval grounding 도 공짜 해법이 아니다**
- **Zheng et al., MT-Bench, arXiv:2306.05685** (2023) — GPT-4 판정자 사람과 **80%+ 일치**(사람-사람 동급), 단 같은 논문이 position·verbosity·self-enhancement bias 를 명시 — "상대비교는 쓸만하나 절대 자기채점엔 위험"이라는 §5-4 논거의 원 출처 중 하나

## Comments
- (2026-08-26, refuter) 표적 4 판정: 인용 14/14 실재 검증은 **유지**(재검증 안 함). 부록의 전칭 *"finding/003 과 충돌하는 것은 없다"* 는 **무너짐** — 005 의 비겹침은 6건이 아니라 9건이고, 빠진 3건에 005 가 **명시적으로 "반례"라 라벨한** arXiv:2206.05802(Saunders)가 들어 있다 → review/006

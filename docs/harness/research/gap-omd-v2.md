# gap-omd 재조사 v2 — T8은 신설이 아니다. 신설할 것은 "판정기의 결정론성"이다

재조사일: **2026-08-24**. 대상: `research/gap-omd.md`(2026-08-22).
근거: `research/AUDIT-2026-08-23.md` §F(미검증 전제)·§G(문헌 0건). 실행 단위: `PLAN.md` **T26**.

> **원본은 고치지 않았다** — `ext-loop-engineering-v2.md`와 같은 규약.

---

## 0. 결론 먼저

**T8 재판정: (c) 측정 먼저(DEC-1 적용).** "신설"도 "단순 배선"도 아니다.

T8의 완료 조건은 *"색 팔레트·여백·정렬이 style-spec에 **강제값으로 존재**하고 **verify가 위반을
잡는다**"*였다. 실측하면 넷 중 셋이 이미 있다:

| T8이 요구한 것 | omd 현황 | 근거 |
|:---|:---|:---|
| style-spec 존재 | **있다** — `docs-standardize`가 참조 문서에서 유도하고, 없으면 10개 프리셋으로 폴백 | `references/themes/README.md` |
| 색 팔레트 강제값 | **있다** — 프리셋마다 hex 팔레트 + 헤더/본문 폰트 페어링 | 같은 파일 |
| verify가 위반을 잡는 배선 | **있다** — `doc-verifier`가 `ppteval.md`를 읽고 **Design/Coherence checks**를 수행 | `agents/doc-verifier.md:46` |
| **여백·정렬 강제값** | **없다** — 루브릭이 *"Alignment and whitespace deliberate, not accidental"*이라 쓸 뿐 수치가 없다 | `references/rubrics/ppteval.md` |

그리고 있는 배선의 성격이 문제다: **`doc-verifier`의 Design 판정은 LLM이 150 dpi PNG를 눈으로
읽어 내리는 판정**이고, 결정론적이지 않다. 문헌은 바로 이 지점을 이름 붙여 반박한다(§2).

**그러니 신설 대상은 "디자인 품질"이라는 개념이 아니라 "판정기를 결정론적으로 만들 것인가"다.**
그리고 그 결정은 **현재 LLM 시각 판정이 얼마나 놓치는지 재기 전에는 내릴 수 없다** — DEC-1이
정확히 이 경우를 위해 있다.

---

## 1. §F 정정 — omd는 디자인 품질 방법을 이미 갖고 있다

원본 `gap-omd.md`에 `doc-inspector`·`ppteval` 단어가 **0회**다. 그 부재가 "DEC-5의 3축 중 둘째
(디자인 품질)에 방법이 없다"는 전제로 굳었다. 실물을 세면 그 전제가 틀렸다.

### 1.1 `ppteval.md`는 데이터 파일이고, 두 에이전트가 나눠 쓴다

`references/rubrics/ppteval.md`(2,095 B)는 스스로 역할 분담을 명시한다:

> *"`doc-inspector` uses it for **formative** critique … and `doc-verifier` uses the
> Coherence/Design axes as part of its **summative pass/fail gate**. Source: PPTEval (PPTAgent,
> arXiv 2501.03936)."*

즉 **감사가 "없다"고 본 것이 형성적·총괄적 양쪽에 다 배선돼 있다.** 그 문서의 대조표:

| | doc-inspector (formative) | doc-verifier (summative) |
|:---|:---|:---|
| 언제 | 작업 중, 아직 고칠 수 있을 때 | 빌드 직후, "done" 선언 전 |
| 산출 | 축별 순위 매긴 개선 목록 | pass/fail + 무결성 게이트 |
| 축 | 3축 전부, 제안으로 | **Design + Coherence를 검사로**, Content 완결성은 spec으로 |

### 1.2 Design 축은 이미 구체값을 일부 갖고 있다

`ppteval.md` Design 절이 명명하는 것: 일관된 폰트(**KO → Apple SD Gothic Neo**), 색 역할, 여백 /
텍스트 overflow·label clipping·shape overlap 부재(**≥150 dpi에서 확인** — 저해상도 렌더는 겹침을
숨긴다) / figure·table 가독성, **종횡비 16:9·4:3·1:1** / 정렬과 여백이 의도적일 것.

Content 축에도 수치가 있다 — **KO 제목 ≤ 50자, 본문 ≤ 6단어/줄(EN 70 / 10)**.

**수치가 없는 것은 딱 둘이다: 여백과 정렬.** "deliberate, not accidental"은 판정 기준이 아니다.

### 1.3 그런데 판정이 결정론적이지 않다

`doc-inspector`의 조사 절차는 *"Render the current artifact to PNG at ≥150 dpi (soffice →
pdftoppm) / Read every slide/page image"*다. `doc-verifier`도 같은 렌더 경로를 쓴다. **위반 탐지가
전부 LLM의 시각 판독이다.** 같은 덱을 두 번 돌리면 같은 답이 나온다는 보장이 없고, 무엇을 놓쳤는지
셀 수도 없다.

이것이 §F가 연 진짜 질문이다 — "방법이 없다"가 아니라 **"방법이 재현되지 않는다"**.

---

## 2. §G 정정 — 문헌은 정확히 그 지점을 친다

원본은 외부 문헌 인용이 **0건**이었다. 2026년 슬라이드 생성 문헌은 이 문제를 정면으로 다룬다.
검색은 `cs.CL`·`cs.AI`·`cs.CV`, 2026-01-01 이후, 총 126건 중 상위 8건을 훑고 아래 넷을 골랐다.

| ID | 제목 | 이 문서에 왜 걸리나 |
|:---|:---|:---|
| **2604.22840** | AeSlides: Incentivizing Aesthetic Layout … via **Verifiable Rewards** | 미학을 **계산 가능한 지표**로 만든 사례. 우리 Design 축과 항목이 겹친다 |
| **2601.09487** | SlidesGen-Bench: Evaluating Slides Generation via **Computational and Quantitative Metrics** | 렌더 결과를 대상으로 재현 가능한 지표를 만든다 — 우리 렌더 경로와 전제가 같다 |
| 2603.07244 | PresentBench: A Fine-Grained **Rubric-Based** Benchmark | 루브릭 기반이라 `ppteval.md`와 직접 비교 대상 |
| 2608.13560 | AutoDesign / **PosterBench** | T25에서 나온 것. 하네스를 rollout 피드백으로 재귀 개선 |

### 2.1 AeSlides — 우리 루브릭이 문장으로 말하는 것을 수치로 만들었다

AeSlides는 슬라이드 레이아웃 품질을 **검증 가능한 지표 묶음**으로 정량화하고 GRPO로 최적화한다.
GLM-4.7-Flash에 5K 프롬프트만으로:

- **종횡비 준수율 36% → 85%**
- **여백(whitespace) 44% 감소**
- **요소 충돌(element collisions) 43% 감소**
- **시각적 불균형(visual imbalance) 28% 감소**

우리 `ppteval.md` Design 축과 나란히 놓으면 **네 항목이 그대로 대응한다**:

| AeSlides 검증 가능 지표 | 우리 ppteval.md Design 문장 |
|:---|:---|
| aspect ratio compliance | "aspect ratios sane (16:9 / 4:3 / 1:1)" |
| element collisions | "no text overflow, no labels clipped, no overlapping shapes" |
| whitespace | "Alignment and whitespace deliberate, not accidental" |
| visual imbalance | 같은 문장 |

**우리는 이미 같은 네 가지를 보고 있다. 다른 것은 재는 방법뿐이다.**

그리고 초록이 우리 현재 방식을 이름 붙여 평가한다: *"Existing solutions typically rely either on
**heavy visual reflection, which incurs high inference cost yet yields limited gains**."*
150 dpi PNG 전수 판독이 정확히 그 heavy visual reflection이다. AeSlides는 그 대안이 **정확하고
효율적이고 저비용**(*"in an accurate, efficient, and low-cost manner"*)이라 주장한다.

> **주의 — 이 논문의 주장은 우리 맥락에서 검증되지 않았다.** AeSlides의 비교 대상은 *생성 모델의
> RL 학습*이고, 우리는 *생성물의 게이트*다. 지표가 이식 가능하다는 것과 그 지표가 우리 덱에서
> 사람 판단과 상관한다는 것은 별개다. 그래서 §3의 판정이 "도입"이 아니라 "측정 먼저"다.

### 2.2 SlidesGen-Bench — 렌더를 대상으로 삼는 전제가 우리와 같다

*"we ground our analysis in the visual domain, treating terminal outputs as renderings to remain
agnostic to the underlying generation method."* — omd가 `soffice → pdftoppm`으로 렌더해서 보는
것과 같은 전제다. 생성 경로(python-pptx / 템플릿 / 코드)가 무엇이든 최종 렌더만 본다.

3차원은 **Content · Aesthetics · Editability**. 우리 3축(Content · Design · Coherence)과 둘은
겹치고 하나가 다르다 — 저쪽의 `Editability`는 우리에게 없고, 우리 `Coherence`는 저쪽에 없다.
**우리 축이 발표 서사에 특화돼 있다는 뜻이지 결함은 아니다.** 그리고 저쪽은 사람 선호 정렬
데이터셋(Slides-Align1.5k, 9개 시스템 × 7개 시나리오)으로 상관을 검증했다 — 우리 루브릭에는 그런
대조가 없다.

---

## 3. T8 재판정

계획(T26 Step 3)이 준 선택지: (a) 신설 유지 (b) `doc-inspector` 배선으로 강등 (c) 측정 먼저.

**판정: (c).** 근거를 순서대로:

1. **(a) 신설 유지는 §1이 막는다.** style-spec·색 팔레트·verify 배선이 이미 있다. "없는 것을
   만든다"는 전제가 틀렸다.
2. **(b) 단순 배선 강등도 정확하지 않다.** 배선은 이미 돼 있고(`doc-verifier.md:46`), 남은 공백은
   배선이 아니라 **여백·정렬의 강제값 부재**와 **판정의 비결정성**이다. 배선으로 강등하면 이 둘이
   시야에서 사라진다 — 감사 §F가 지적한 것과 같은 형태의 소실이다.
3. **(c)가 맞다.** 문헌은 우리가 보는 네 항목을 계산 가능하게 만들 수 있음을 보였지만(§2.1),
   그 지표가 **우리 덱에서 사람 판단과 상관하는지는 재본 적이 없다**. DEC-1이 이 경우를 위해 있다.

**측정 항목 (T8이 실행될 때 먼저 잴 것)**:

| 무엇 | 어떻게 | 왜 |
|:---|:---|:---|
| 현재 Design 판정의 재현성 | 같은 덱을 `doc-verifier`로 2회 이상 돌려 findings 집합을 비교 | 비결정성이 실제로 문제인지, 아니면 걱정만인지 가른다 |
| 놓치는 위반의 크기 | AeSlides 네 지표(종횡비·충돌·여백·불균형)를 기계로 계산해 LLM 판정과 대조 | "heavy visual reflection … limited gains" 주장이 우리 덱에서도 서는지 |
| 여백·정렬 수치의 필요성 | 위 대조에서 여백·정렬 위반이 실제로 새는지 확인 | 강제값 신설의 근거가 되거나 기각된다 |

**측정 결과가 셋 다 "문제 없음"이면 T8은 닫힌다.** 그것이 (c)가 (a)·(b)보다 나은 이유다 —
신설도 강등도 지금은 근거가 없다.

---

## 4. 원본에서 그대로 유효한 것

- DEC-5의 3축 정의(정적 다이어그램 / 전반 디자인 품질 / 별도 영상 산출물) 자체는 건드리지 않는다.
- T9(영상 산출 장르)의 "입증 부담" 표시도 그대로다 — 이 재조사는 T8만 다뤘다.

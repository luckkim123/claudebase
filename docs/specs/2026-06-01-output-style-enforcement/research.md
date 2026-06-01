# Output-Style Enforcement — Research base

**Date:** 2026-06-01
조사 방법: external-context, 5 facet 병렬 document-specialist(sonnet). 모든 출처 URL 검증됨(에이전트가
미검증은 명시하도록 지시). 용도: claudebase 출력-스타일 hook 설계 근거.

> **결말(2026-06-01):** hook 메커니즘(UserPromptSubmit 주입 + Stop 오프너 검출)은 폐기됨. 대신
> 이 5 facet 종합을 `config/CLAUDE.md` 의 "### 6. Output Form" 텍스트 규칙으로 흡수(시스템
> 프롬프트 이후 user 메시지로 주입, 항상 켜짐). 공식 custom output style 도 검토했으나 채택 안 함 —
> 코딩 지침을 대체하는 부작용이 있어 "어투/구조 규칙만" 목적엔 과함(`keep-coding-instructions`
> 옵션은 있으나 불필요). 이 문서는 그 텍스트 규칙의 근거로만 보존. design·plan(hook 설계)은 폐기.

---

## Facet 1 — 구조 / 레이아웃

**학술**
- F-Shaped Pattern of Reading — https://www.nngroup.com/articles/f-shaped-pattern-reading-web-content/ — 포맷 없으면 F자 스캔이 기본, 중앙 우측은 놓침.
- Text Scanning Patterns: Eyetracking — https://www.nngroup.com/articles/text-scanning-patterns-eyetracking/ — heading-only "layer-cake" 스캔이 가장 효율적. 의미 있는 소제목 필수.
- Inverted Pyramid — https://www.nngroup.com/articles/inverted-pyramid/ — 결론 먼저. 아무 데서 멈춰도 핵심 전달.
- Information Foraging — https://www.nngroup.com/articles/information-foraging/ — 헤딩·볼드는 "정보 냄새". Pirolli & Card 이론.
- Fact Boxes RCT (Royal Society Open Sci 2020) — https://pmc.ncbi.nlm.nih.gov/articles/PMC7137953/ — 표 vs 산문 이해도 79.6% vs 69.7%, d=0.39, 6주 회상도 우위.
- LLM Text Simplification RCT (arXiv 2505.01980) — https://arxiv.org/abs/2505.01980 — 문장 단순화로 이해도 +3.9%~+14.6%(4,563명).
- MDEval (WWW 2025, arXiv 2501.15000) — https://arxiv.org/abs/2501.15000 — Markdown 구조 품질은 측정·개선 가능한 별도 차원.
- Progressive Disclosure (IxDF, Nielsen 1995) — https://ixdf.org/literature/topics/progressive-disclosure — 본질 먼저, 심화는 요청 시.

**공식/GitHub**
- Claude 4 system prompt 포맷 규칙 (Simon Willison) — https://simonwillison.net/2025/May/25/claude-4-system-prompt/ — "잡담/공감/조언에 리스트 금지", "설명/문서/보고서에 불릿 금지(명시 요청 없으면)", "산문 안에선 자연어 'x, y, z 등'".
- OpenAI GPT-5.1 Prompting Guide — https://developers.openai.com/cookbook/examples/gpt-5/gpt-5-1_prompting_guide — 단순 ≤5문장/≤3불릿, "산문 우선, 불릿은 사용자 요청 시만", "중첩 불릿 금지".
- Anthropic Prompting Best Practices — https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
- DAIR-AI Prompt Engineering Guide — https://github.com/dair-ai/Prompt-Engineering-Guide

> 공백: 불릿-과다 vs 산문-과다를 사람 이해도로 직접 비교한 peer-reviewed RCT 없음. 가장 가까운 건 표 RCT·문장단순화 RCT.

## Facet 2 — 근거 / 인용 / 그라운딩

**학술**
- AIS Framework (Computational Linguistics 2023) — https://aclanthology.org/2023.cl-4.2/ — "Attributable to Identified Sources" 정의 논문.
- ALCE (EMNLP 2023) — https://arxiv.org/abs/2305.14627 / https://github.com/princeton-nlp/ALCE — 인용 자동평가 벤치마크. 최고 모델도 ELI5 50%에서 근거 부족.
- RARR (ACL 2023) — https://arxiv.org/abs/2210.08726 — 사후 근거 보강.
- Citations and Trust (AAAI 2025) — https://arxiv.org/pdf/2501.01303 — 인용이 무작위여도 신뢰↑, 확인하면 신뢰↓.
- GhostCite (2026) — https://arxiv.org/pdf/2602.06718 — 13모델 인용 환각률 14~95%, 정확 74.5%.

**공식/제품**
- Anthropic Citations API — https://platform.claude.com/docs/en/build-with-claude/citations — 구조적 보증(유효 포인터+cited_text).
- Perplexity 인용 아키텍처 — https://ziptie.dev/blog/how-perplexity-ai-answers-work/ — 인용을 생성 시점에 제약(사후 X).

## Facet 3 — 간결성 / 인지부하 / 구어체 회피

**Verbosity = 부정확**
- A Long Way to Go (arXiv 2310.03716) — https://arxiv.org/abs/2310.03716 — RLHF 개선 상당수가 "더 길게"지 품질 아님.
- Verbosity ≠ Veracity (arXiv 2411.07858) — https://arxiv.org/abs/2411.07858 — GPT-4 verbosity compensation 50.4%, 장황할수록 최대 27.6% 더 틀림.

**Sycophancy = 신뢰 하락**
- Towards Understanding Sycophancy (Anthropic, arXiv 2310.13548) — https://arxiv.org/abs/2310.13548 — 5개 어시스턴트 공통, 사람이 정확보다 동의 선호한 라벨이 원인.
- Be Friendly Not Friends (arXiv 2502.10844) — https://arxiv.org/abs/2502.10844 — 칭찬형 LLM은 진정성·신뢰 떨어뜨림(N=224).
- OpenAI GPT-4o 아첨 롤백 — https://openai.com/index/sycophancy-in-gpt-4o

**인지부하 + 작법 정전**
- Cognitive Load Theory (Sweller 2011) — 작업기억 ~5~9 청크, 불필요 단어가 의미처리 잠식.
- Strunk & White "Omit needless words" — https://en.wikiquote.org/wiki/The_Elements_of_Style
- Federal Plain Language Guidelines — https://www.plainlanguage.gov/

**공식**
- Anthropic Best Practices(verbosity/tone) — https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices — "concise, focused responses. Skip non-essential context", default "direct, opinionated, minimal validation-forward phrasing".

## Facet 4 — 불확실성 / 신뢰도 표현

- Just Ask for Calibration (EMNLP 2023, arXiv 2305.14975) — https://arxiv.org/abs/2305.14975 — 말로 신뢰도 표현시키면 ECE ~50% 개선.
- Language Models (Mostly) Know What They Know (Kadavath, Anthropic, arXiv 2207.05221) — https://arxiv.org/abs/2207.05221 — 큰 모델은 자기 답 정오 자가평가 가능.
- Atomic Calibration (arXiv 2410.13246) — https://arxiv.org/abs/2410.13246 — 긴 답엔 주장별 신뢰 표시 필요.
- To Trust or to Think (CSCW 2021, arXiv 2102.09692) — https://arxiv.org/abs/2102.09692 — 신뢰도 표시만으론 과신뢰 못 막음, 사용자 선판단 장치 필요.
- Epistemic markers (NAACL 2025) — https://aclanthology.org/2025.naacl-long.452/ — 모호한 헤지는 실제 불확실성 반영 못 함 → 명시적 지식경계 선언 권장.
- Anthropic Claude's Constitution — https://www.anthropic.com/news/claude-new-constitution — 공식 목표 "calibrated uncertainty based on evidence and sound reasoning".

## Facet 5 — 시각적 분류 / 네모박스 / 구획화

**인지심리**
- Common Region (Palmer 1992, via NN/g) — https://www.nngroup.com/articles/common-region/ — 테두리·배경색이 근접성보다 강한 그룹핑 신호. 네모박스의 직접 근거.
- Magical Number Seven (Miller 1956) — https://psychclassics.yorku.ca/Miller/ — 작업기억 ~7±2. Cowan 2001 은 ≈4.
- Segmentation & Cognitive Load (BMC Psychology 2024) — https://pmc.ncbi.nlm.nih.gov/articles/PMC10759450/ — 경계 블록으로 쪼개면 인지부하↓, 이해·회상↑.

**정확한 문법**
- GitHub Markdown Alerts — https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#alerts — `> [!NOTE]`/`[!TIP]`/`[!IMPORTANT]`/`[!WARNING]`/`[!CAUTION]`. 페이지당 1~2개, 연속·중첩 금지.
- MkDocs Material Admonitions(12종) — https://squidfunk.github.io/mkdocs-material/reference/admonitions/
- Docusaurus Admonitions(5종) — https://docusaurus.io/docs/markdown-features/admonitions
- Obsidian Callouts(15종) — https://obsidian.md/help/Editing+and+formatting/Callouts
- Sphinx/reST Admonitions — https://www.sphinx-doc.org/en/master/usage/restructuredtext/directives.html

**스타일 가이드**
- Google Notices — https://developers.google.com/style/notices — Note/Caution/Warning/Success, "여러 개 쓰면 시각적 구별력 상실", 연속 금지.
- Microsoft Writing Style Guide — https://learn.microsoft.com/en-us/style-guide/welcome/
- NN/g Cards — https://www.nngroup.com/articles/cards-component/ — 카드는 비교·검색엔 스캔 느림. 위치 예측 가능한 라벨 블록(callout)이 카드보다 스캔에 유리.

---

## 종합 — 강제 가능한 5줄 기본값(근거 강함)

1. 답 먼저(BLUF) + 의미 있는 헤딩 [Facet1: layer-cake, inverted pyramid]
2. 불릿은 진짜 병렬 항목일 때만, 설명은 산문 [Facet1: Claude4/GPT-5.1 공식]
3. 비교는 표 [Facet1: fact-box RCT d=0.39]
4. 군더더기·구어체·아첨 제거(간결한 단정형) [Facet3: verbosity≠veracity, sycophancy]
5. 불확실하면 모호한 헤지 말고 지식 경계 명시 [Facet4: epistemic markers, Constitution]
+ 네모박스로 구획화하되 1~2개 한도 [Facet5: Common Region + Google 남용 경고]

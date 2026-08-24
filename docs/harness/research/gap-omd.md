# oh-my-docs(omd) 시각·디자인 능력 갭 분석

조사일: 2026-08-22. 대상: `~/oh-my-docs` 저장소 전체(worktree 사본 제외) + 실제 산출물(workspace `.omd/*/`).

---

## 결론 한 줄

omd가 만드는 시각 요소는 **matplotlib 수식 PNG**, **템플릿에 이미 박혀 있던 배경/로고**,
**논문 원문 스크린샷 크롭**, **python-pptx 도형으로 그린 화살표/라벨 주석** 네 가지뿐이다.
독자적인 다이어그램·차트·아이콘·생성 이미지는 실측한 4개 덱(37장) 어디에도 없다.
원인은 시각 도구 부재가 아니라 **배선 부재 + 명시적 아키텍처 규칙**(`doc-builder.md:31` "OMD rebuilds,
it does not wrap [other skills]")이다. 새 스킬을 만들 필요는 없다 — 이미 설치된 도구를 부를 경로만 없다.

---

## 1. omd 저장소 정독 — 시각 요소 생성 경로 실측

### 1.1 코드베이스 전체에서 시각 도구 언급 검색

`grep -rniw "mermaid|matplotlib|excalidraw|remotion|nano.banana|gen-image|dataviz|diagram|chart|animation|gif" ~/oh-my-docs`
결과, 실제 저장소(worktree 사본 제외) 파일은 다음 9개뿐이었다:

- `references/mcp-skills-backport-analysis.md`
- `references/formats/pptx.md`
- `references/formats/docx.md`
- `references/formats/xlsx.md`
- `agents/doc-builder.md`
- `skills/docs-build/SKILL.md`
- `skills/docs-pilot/SKILL.md`
- `docs/superpowers/plans/*.md` (설계 이력, 실행 코드 아님)

이 중 mermaid·excalidraw·remotion·nano-banana·dataviz·gen-image 스킬 호출은 **0건**. matplotlib은
전부 "LaTeX 수식 → PNG" 용도로만 등장한다 (`pptx.md:16,179-197`, `docx.md:17,110-114`).
"chart"는 xlsx 카드에서 openpyxl↔xlsxwriter 엔진 선택 문제로만 등장(`xlsx.md:14,22,59,121-122`) —
omd가 차트를 *만드는* 방법이 아니라 기존 엑셀 차트가 엔진 라운드트립에서 *깨지는* 문제다.

**Confidence: verified** — grep 전수 결과, 파일:줄 직접 확인.

### 1.2 `gen-image/` 폴더는 관례로만 존재하고 실사용 0건

`skills/docs-pilot/SKILL.md:80,90`에 `.omd/<slug>/gen-image/` 가 정리 대상 워크스페이스 하위 폴더로
언급되지만, 실제 산출물(아래 §2)의 어느 `.omd/*/` 아래에도 `gen-image/` 디렉터리는 존재하지 않았다
(`find /Users/kimseungmin/Desktop/workspace/.omd -type d -iname gen-image` → 결과 없음).
즉 "필요하면 쓰는 폴더" 관례만 있고 **그 폴더를 채우라고 지시하는 agent 문구가 없다** — doc-builder.md·
doc-planner.md 전체에 `gen-image` 문자열이 한 번도 등장하지 않는다 (grep 확인).

**Confidence: verified**.

### 1.3 doc-planner는 "다이어그램이 필요하다"를 인지하지만 doc-builder에 실행 경로가 없다

`doc-planner.md:110`의 Good 예시: `"needs system diagram"` — 플래너가 슬라이드 단위로 figure/table/none
자산 필요성을 표시하는 컬럼이 실제로 존재한다(`doc-planner.md:77`). 그러나 `doc-builder.md`에는
- 수식 PNG 만드는 법(§ Formulas, `pptx.md:173-204`)
- 템플릿 레이아웃 복제하는 법(§ Building on a master template, `pptx.md:32-50`)
는 있지만, **개념 다이어그램(아키텍처/플로우/관계도)을 실제로 그리는 절차는 없다**. planner가 "system
diagram 필요"라고 표시해도 builder 쪽에 이를 받아 처리하는 카드 섹션이 존재하지 않는다.

**Confidence: verified** (두 파일 직접 대조).

### 1.4 아키텍처 규칙이 스킬 호출 자체를 금지한다

`doc-builder.md:31`: "Do not invent format tricks; do not call other skills (ppt-academic/ppt-edit/etc.) —
OMD rebuilds, it does not wrap." 이는 gen-image·mermaid 같은 **다른 스킬을 직접 호출하지 말라는 명시
규칙**이다. 따라서 "gen-image 스킬을 doc-builder가 호출하게 배선하자"는 제안은 이 규칙과 충돌한다 —
규칙에 예외를 만들거나("시각 자산 생성 스킬은 예외"), 스킬 호출이 아닌 **직접 라이브러리/CLI 호출**
경로(예: matplotlib로 차트도 직접 그리기, mermaid-cli를 subprocess로 호출, graphviz를 python-pptx
도형 좌표 계산에 사용)로 우회해야 한다.

**Confidence: verified** (원문 인용). 어느 우회가 옳은지는 **unverified** — 설계 판단이 필요하다.

### 1.5 backport 분석 문서가 스스로 "디자인 규칙은 보류"라고 기록해 두었다

`references/mcp-skills-backport-analysis.md` §3 표 하단 주석: "The **pptx deck design rules** (dominance
60-70%, motif repetition, no title underline) are valuable but omd's pptx work routes through the
mckinsey-pptx template, so they fall under that jurisdiction → **on hold**." — omd 유지자 스스로 디자인
원칙 채택을 명시적으로 미뤄둔 기록이다. 새로 발견한 갭이 아니라 **이미 알려진 채무**.

**Confidence: verified**.

---

## 2. 실제 산출물 실측 — "조촐하다"를 측정 가능한 항목으로 번역

workspace에서 발견한 omd 산출 `.omd/*/` 워크스페이스 4건: `koopman-seminar`, `multibeam-sonar-seminar`,
`utracker-seminar`, `harness-seminar`(vault 인접 경로). 렌더 PNG를 직접 열어 확인했다.

### 2.1 시각요소 인벤토리 (렌더 PNG 직접 확인, 표본 6장)

| 파일 | 내용 | 원본 이미지 출처 |
|:---|:---|:---|
| `utracker-seminar/renders/final/s-05.png` | 표(Table II) 크롭 + 텍스트 3단 요약 | 논문 원문 표 이미지 |
| `utracker-seminar/renders/final/s-09.png` | 논문 수식(8)(9) 스크린샷 크롭 + 형광펜 하이라이트 박스 + 번호 라벨(①②) 화살표 | 논문 원문 PDF 크롭 |
| `utracker-seminar/renders/final/s-02.png` | Contents 페이지 — 바다 배경 이미지 | **템플릿 마스터에 내장된 image4.png** (`ppt_template_master.pptx`의 `ppt/media/image4.png`, 1.08MB, unzip -l로 확인) |
| `multibeam-sonar-seminar/renders/current/v11-04.png` | 논문 서론 문단 크롭 + 번호 라벨(①②) + 커넥터 화살표 | 논문 원문 크롭 |
| `koopman-seminar/assets/eq_*.png` (수십 개) | LaTeX 수식 → matplotlib PNG | 자체 생성(수식만) |
| `multibeam-sonar-seminar/build/tmp/hires-*.png` | 원본 논문 그림 고해상도 추출 | 논문 원문 |

**모든 "이미지"는 4종류 중 하나로 완전히 분류된다: (a) 템플릿 내장 배경/로고, (b) 논문 스크린샷 크롭,
(c) matplotlib 수식 PNG, (d) python-pptx 도형(사각형 라벨+커넥터 화살표)으로 그린 주석.**
독자적으로 구성한 개념 다이어그램·아키텍처 그림·통계 차트·아이콘·일러스트는 표본에서 **0건**.

**Confidence: verified** — 이미지 6장 직접 열람(Read tool), unzip -l로 템플릿 media 확인.

### 2.2 "조촐함"의 구체적 항목

- **슬라이드당 독자 생성 시각요소(다이어그램/차트/아이콘) 0개** — 텍스트 상자·표·크롭 이미지·수식
  PNG로만 구성. (§2.1 근거)
- **색상 팔레트는 템플릿에서 상속만** — HERO Lab 마스터가 정한 3색(네이비/그레이/그린 계열 accent)을
  그대로 쓰고, doc-builder는 "analyzer가 보고한 디자인 시스템(폰트/색/여백)을 맞춘다"(`doc-builder.md:36`)
  는 지시만 있다. 독자 팔레트 설계·검증 로직은 없음(§1.5의 "on hold" 기록과 일치).
- **다이어그램 반복 패턴 1종뿐** — 확인한 3개 덱(utracker/multibeam)에서 "논문 크롭 + 번호 라벨(①②③)
  + 커넥터 화살표"라는 동일 패턴이 거의 모든 분석 슬라이드에 반복된다. 이는 나쁘지 않은 패턴이지만
  **다양성이 없다** — 관계도·흐름도·비교 매트릭스 등 다른 시각화 문법이 전혀 등장하지 않는다.
- **생성 이미지(AI 이미지 생성) 0건** — `gen-image/` 폴더가 관례로만 존재(§1.2)하고 실사용 0.

### 2.3 이것이 사용자의 "사람이 만든 것 같지 않다"는 인상과 어떻게 연결되는가

실측 자체는 판단(질 좋다/나쁘다)이 아니라 사실이다: 사람이 만드는 발표자료는 보통 (1) 원본 자료를
그대로 캡처하지 않고 **재구성한 다이어그램**으로 바꾸고, (2) 통계는 표를 캡처하는 대신 **차트로
재시각화**하며, (3) 개념 설명에 **아이콘/일러스트**를 곁들인다. omd 산출물은 이 세 가지를 전혀 하지
않고 원문 캡처+주석이라는 단일 문법만 반복한다 — 이것이 "조촐함"의 실체로 보인다. 다만 이 해석
자체(사용자 인상의 원인 규명)는 **likely**로 표기한다 — 사용자에게 직접 확인된 사실은 아니다.

---

## 3. 설치된 시각 도구가 omd에서 실제로 호출 가능한가

| 도구 | 설치 확인 | omd에서 호출 가능한가 | 근거/전제 |
|:---|:---|:---|:---|
| ui-ux-pro-max (design/slides/design-system/banner-design) | 스킬 목록에 존재 확인 | **불가 — 배선 안 됨** | doc-builder는 다른 스킬을 안 부른다(`doc-builder.md:31`). 게다가 이 스킬은 omd의 python-pptx 직접 빌드 파이프라인과 별개 산출 경로(별도 Artifact/디자인 캔버스)로 보임 — **unverified**, ui-ux-pro-max 자체 문서 미정독 |
| remotion (영상/애니메이션 12스킬) | 스킬 목록에 존재 확인 | **불가 — 배선 안 됨 + 장르 불일치** | omd 산출 장르(pptx/docx/xlsx/site/repo-docs)에 영상이 없음. GIF/애니메이션을 만들려면 omd에 새 출력 장르 자체가 필요 — 이는 "새로 만들어야 하는 것" |
| gen-image (Nano Banana) | 스킬 목록에 존재 확인 | **불가 — 배선 안 됨** | `gen-image/` 폴더 관례만 있고(§1.2) 호출 지시 없음. 스킬이 아니라 직접 REST 호출 스크립트를 doc-builder가 subprocess로 부르는 방식이면 §1.4 규칙과 충돌하지 않을 수 있음 — **unverified**, gen-image 스킬 SKILL.md 내부 구현(REST 직접 호출인지, Skill-tool 경유인지) 미확인 |
| Excalidraw MCP | MCP 서버로 등록됨(`mcp__claude_ai_Excalidraw__*` 확인) | **불가 — 배선 안 됨** | doc-builder.md에 Excalidraw 언급 0건. MCP 툴이므로 이론상 subagent가 직접 호출 가능(스킬 우회 규칙과 무관) — 가장 마찰 적은 후보 |
| Mermaid Chart MCP | MCP 서버로 등록됨(`mcp__claude_ai_Mermaid_Chart__validate_and_render_mermaid_diagram` 확인) | **불가 — 배선 안 됨** | 동일하게 MCP 툴이라 스킬 규칙과 무관하게 호출 가능. pptx/docx에 삽입하려면 렌더된 PNG/SVG를 이미지로 embed하는 절차만 추가하면 됨 — **가장 저비용 후보** |
| dataviz 스킬 | 스킬 목록에 존재 확인 | **불가 — 배선 안 됨** | 차트 색상/형태 규칙 문서. omd xlsx 카드가 이미 색상 규칙(M8, `mcp-skills-backport-analysis.md`)을 자체 보유하고 있어 중복 소지 — 전체 채용보다 **참조**만 하는 편이 나음 |
| artifact-diagramming 스킬 | 스킬 목록에 존재 확인 | **해당 없음** | Artifact(웹 페이지) 전용 다이어그램 기법. omd는 오피스 파일 산출이 목적이라 장르 불일치 |

**Confidence: verified**(설치·미배선 사실) / **unverified**(각 도구의 정확한 내부 호출 메커니즘 —
스킬 SKILL.md를 열어 REST-direct인지 Skill-tool 경유인지 확인하지 않음, 효과 20 예산 안에서 skip).

---

## 4. 3분류: 배선 / 신규 / 사람

### 4.1 배선하면 되는 것 (기존 도구 재사용 — 우선순위)

1. **Mermaid MCP → PNG embed** (난이도: 낮음). doc-planner가 "needs diagram"이라 표시한 슬라이드에서
   doc-builder가 `mcp__claude_ai_Mermaid_Chart__validate_and_render_mermaid_diagram`을 직접 호출해
   SVG/PNG를 받고, `pptx.md`의 기존 이미지 embed 절차(`add_picture`)로 삽입. MCP 툴 호출은
   `doc-builder.md:31`의 "call other skills" 금지 규칙과 별개(스킬이 아니라 MCP 툴)라 규칙 충돌 없음.
   **`references/formats/pptx.md`에 "## Diagrams" 섹션 하나만 추가하면 됨.**
2. **Excalidraw MCP → PNG embed** (난이도: 낮음, 위와 동일 패턴). 손그림풍 다이어그램이 필요할 때
   대안 경로로.
3. **`gen-image/` 폴더 관례를 실제로 채우기** (난이도: 낮음~중간). gen-image 스킬이 REST 직접 호출
   방식이라면(§3의 unverified 확인 후) doc-builder가 subprocess로 부르되, "다른 스킬 호출 금지" 규칙에
   **명시적 예외**를 추가해야 함 — `doc-builder.md:31`을 "시각 자산 생성 도구(mermaid-mcp/excalidraw-mcp/
   gen-image)는 예외"로 수정.
4. **xlsx 네이티브 차트 활용** (난이도: 낮음). xlsxwriter는 이미 차트 생성을 지원(`xlsx.md:14`) —
   omd가 라운드트립 손실만 경고할 뿐 **차트를 새로 만드는 절차는 문서화 안 됨**. `xlsx.md`에 "차트
   생성 레시피" 섹션 추가.

### 4.2 새로 만들어야 하는 것

1. **`pptx.md`/`docx.md`에 "다이어그램 카드" 섹션 신설** (난이도: 중간) — matplotlib 수식 PNG 섹션과
   동급으로, "개념 관계도는 mermaid로, 커스텀 배치가 필요하면 python-pptx 도형으로" 같은 라우팅 규칙을
   명문화. 이건 스킬이 아니라 **기존 카드 문서에 절 추가**이므로 "새 스킬" 입증 부담과 무관.
2. **GIF/영상 산출 장르** (난이도: 높음, 낮은 우선순위) — remotion을 쓰려면 omd에 없는 새 출력 장르
   자체가 필요하다. 사용자가 "발표자료에 애니메이션"을 원하는 것인지, "별도 영상 산출물"을 원하는
   것인지 먼저 확인 필요 — 현재 요구사항 문구("특히 다이어그램·GIF·애니메이션")만으로는 판단 불가.
   **여기가 유일하게 "새로 만들 가치"가 있을 수 있는 지점이지만, 상기 §0의 실측 원칙(스킬 추가는
   입증 부담)에 따라 배선 우선 시도 후에도 부족할 때만 고려.**

### 4.3 사람이 해야 하는 것

1. **디자인 시스템(팔레트/타이포/모티프) 자체 설계** — 현재 omd는 "analyzer가 감지한 기존 템플릿을
   따른다"는 원칙(`doc-builder.md:36`)만 있고, 템플릿이 없을 때 처음부터 팔레트를 설계하는 판단은
   agent 룰로 대체하기 어렵다. `mcp-skills-backport-analysis.md`가 스스로 "on hold" 처리한 pptx 디자인
   원칙(dominance 60-70%, motif repetition)을 실제로 어떤 값으로 정할지는 도메인 감각이 필요한
   사람의 결정.
2. **"논문 크롭 반복 문법을 다양화할지" 여부** — §2.2에서 확인한 단일 반복 패턴이 실제로 나쁜지,
   혹은 이 랩의 세미나 발표 관례상 의도된 것인지는 사용자 확인 필요. 조사 범위 밖.

---

## 열린 질문 (사용자 확인 필요)

- "다이어그램·GIF·애니메이션"에서 GIF/애니메이션이 발표자료 내 삽입용인지, 별도 영상 산출물인지.
- gen-image/Excalidraw-MCP/Mermaid-MCP 중 어느 것을 doc-builder의 "예외 호출 허용" 대상으로 삼을지 —
  본 조사는 후보만 나열했고 선택은 설계 단계.
- `doc-builder.md:31` 규칙에 예외를 만드는 것 자체가 omd 아키텍처 철학(다른 스킬을 감싸지 않는다)과
  충돌하는지는 omd 유지자(사용자)의 판단 영역.

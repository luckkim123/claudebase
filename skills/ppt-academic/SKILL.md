---
name: ppt-academic
description: |
  학술 발표용 .pptx 생성 스킬. 디펜스, 논문 발표, 랩 세미나 등 학술 시나리오에
  특화. mckinsey-pptx 플러그인 베이스 + 한국어 학술 톤 + 3게이트 워크플로우
  (구조 → 콘텐츠 → 템플릿)로 신중하게 진행. 한국어/영어/혼용 모두 지원.

  Triggers: 디펜스, 학사 발표, 석사 발표, 박사 발표, 학회 발표, 논문 발표,
  paper presentation, thesis defense, lab seminar, 랩 세미나, 종합 발표,
  학술 발표, academic presentation, dissertation
---

# PPT Academic Skill

학술 발표용 PPTX를 신중하게(3게이트) 생성한다. mckinsey-pptx 플러그인의 40개
검증된 템플릿을 활용하되, 본인의 학술 톤과 narrative arc로 wrapping.

## When to Use

**Use this skill when:**
- 학사/석사/박사 디펜스 슬라이드 작성
- 학회 paper presentation
- 랩 세미나 발표 자료
- vault `0_Project/in_progress/<name>/research_summary/` 자료를 슬라이드로
- 학술 톤이 필요한 모든 PPTX (편집 가능한 .pptx 파일이 결과물)

**Use `ppt-lecture` instead when:**
- 강의/교육 자료 (HTML→PNG, 블로그 임베드용)
- 후배 교육, 튜토리얼, 컨셉 노트 강의화
- PNG 이미지 출력이 더 적합한 경우

## Hard Rules

1. **3게이트 워크플로우 준수** — 구조 → 콘텐츠 → 템플릿 순서, 각 게이트마다
   사용자 확정 받기. 절대 한 번에 처리하지 말 것.
2. **mckinsey-pptx 카탈로그가 진실의 원천** — 템플릿 이름과 인자는
   `${CLAUDE_PLUGIN_ROOT}/mckinsey_pptx/agent/CATALOG.md`에서만 가져온다.
   발명 금지.
3. **Rationale 변호 강제** — 각 슬라이드의 템플릿 선택 이유를 한 줄로 작성.
   인접 템플릿 대비 왜 이걸 골랐는지 명시.
4. **시각 검증 필수** — soffice + pdftoppm 사용 가능하면 PNG 렌더링 후
   2~3장 Read 도구로 확인. 텍스트 오버플로우/라벨 가림 발견 시 콘텐츠 줄여
   rebuild. 도구 없으면 검증 생략 명시.
5. **한국어 시 KO_THEME 강제** — Apple SD Gothic Neo 폰트 사용
   (`mckinsey_pptx.theme.Typography(family="Apple SD Gothic Neo")`).
6. **레이아웃 디시플린**:
   - 한국어 제목 ≤ 50자, 영어 ≤ 70자
   - 한국어 본문 ≤ 6단어/줄, 영어 ≤ 10단어/줄
   - 좁은 컬럼 템플릿(`overview_areas`, `phases_table_4`) 더 짧게
   - 한국어는 같은 폰트 사이즈에서 1.3배 넓음 → 영어 대비 25% 짧게
7. **placeholder 금지** — `[Insert ...]` 같은 리터럴 placeholder를 그대로
   두지 않는다. 데이터 없으면 "[연구자가 입력 필요]" 같이 명시.
8. **출력 위치** — 사용자 CWD의 `output/` 아래. plugin cache 안에 쓰기 금지.

## Gate 0 — 의존성 체크

첫 호출 시 실행:

```bash
# 1. python-pptx 체크
python3 -c "import pptx" 2>&1
# 실패 시: claude-settings의 install.sh가 자동 설치하지만,
# 미실행 시 `pip3 install --user python-pptx` 안내

# 2. mckinsey-pptx 플러그인 체크
ls "${CLAUDE_PLUGIN_ROOT}"/*/mckinsey_pptx/ 2>/dev/null || \
  ls ~/.claude/plugins/cache/seulee26-mckinsey-pptx/*/mckinsey_pptx/ 2>/dev/null
# 실패 시 안내:
#   /plugin marketplace add seulee26/mckinsey-pptx
#   /plugin install axlabs-mckinsey-pptx@axlabs
#   (Claude Code 재시작 필요)
```

플러그인이 없으면 Gate 1 진행 거부. 사용자가 설치 + 재시작 후 다시 호출하도록.

## Gate 1 — 의도/구조 (Narrative Arc 결정)

사용자 입력에서 추출:

| 항목 | 추출 방법 |
|:---|:---|
| **타입** | "디펜스" / "논문" / "세미나" / "기타" 키워드 매칭 |
| **청중** | "심사위원" / "학회" / "동료" / "일반" 등 |
| **시간** | "X분", "X분 발표" → 슬라이드 수 추정 (1분 ≈ 1장 baseline) |
| **언어** | 한국어/영어/혼용 (사용자 입력 언어 + 명시 요청) |

내부 처리:
1. `references/narrative-arcs.md` 에서 적합한 arc 선택
   - 매칭 안 되면 사용자에게 4개 중 선택 요청
2. `templates/<arc-name>.md`에서 시퀀스 로드
3. 슬라이드 수를 발표 시간에 맞게 조정

**출력 (사용자 확정 대기)**:
```markdown
## 제안하는 발표 구조

**타입**: 학사 디펜스
**청중**: 심사위원 (3~5명)
**시간**: 18분 (Q&A 별도)
**언어**: 한국어 (학술 용어 영어 병기)
**슬라이드 수**: 18장

| # | 섹션 | 슬라이드 |
|:--|:----|:--------|
| 1 | Cover | 1장 — 제목, 연구자, 소속, 날짜 |
| 2 | Background | 2장 — 연구 배경, 문제 정의 |
| 3 | Research Question | 1장 — 핵심 질문 명시 |
| 4 | Related Work | 2장 — 선행 연구 비교 |
| 5 | Methodology | 3~4장 — 제안 방법, 아키텍처 |
| 6 | Experiments | 3장 — 실험 설정, 데이터셋, 평가 |
| 7 | Results | 3장 — 주요 결과, 차트 |
| 8 | Discussion | 1장 — 한계점, 의의 |
| 9 | Conclusion | 1장 — 요약, 기여 |
| 10| Q&A | 1장 — 감사, 연락처 |

이대로 진행할까요? 또는 수정 사항을 알려주세요.
```

**사용자 확정 ✋ → Gate 2**

## Gate 2 — 콘텐츠 (각 슬라이드 실제 내용)

각 슬라이드마다 다음을 결정:
- 제목 (Hard Rules 길이 제한 준수)
- 핵심 메시지 (1줄, 그 슬라이드의 takeaway)
- 본문 bullet 또는 데이터
- 차트/다이어그램/이미지 필요 여부

### vault 옵션 헬퍼 (자동 감지)

사용자 CWD가 vault 안이면 다음 옵션 자동 활성화:

- `--from-research-summary <dir>`: 디렉터리 내 모든 `.md` 자동 읽기
  - 자동 매핑 (예: bachelor_thesis_2026):
    - `01_research_identity.md` → Cover + Background
    - `02_thesis_core.md` → RQ + Method
    - `03_publications.md` → Related Work
    - `04_projects_timeline.md` → Roadmap
    - `05_improvements_*.md` → Discussion
    - `06_cv_material.md` → 부록
    - `07_defense_narrative.md` → 발표 스크립트 (notes로만, 슬라이드 X)
- `--from-paper <path>`: 2_Resource/papers/*.md → Main Ideas/Method/Results 추출
- `--from-outline <path>`: 사용자 제공 .md 개요 그대로 따름

### 출력 (사용자 확정 대기)

```markdown
## 슬라이드 콘텐츠

| # | 제목 | 핵심 메시지 | 데이터/그림 |
|:--|:----|:----------|:-----------|
| 1 | <제목> | <연구자/소속/날짜> | - |
| 2 | 연구 배경 | "X 분야에서 Y 문제가 미해결" | - |
| ... | ... | ... | ... |
| 7 | 제안 아키텍처 | "3단계 파이프라인: A→B→C" | 다이어그램 필요 |
| 11| 실험 결과 | "베이스라인 대비 +12%" | 막대 차트 |

[데이터 누락 슬라이드 N개]: 7번 다이어그램, 11번 막대 차트 데이터.
실제 값을 제공하거나, 임시 placeholder로 진행할지 알려주세요.

이대로 진행할까요?
```

**사용자 확정 ✋ → Gate 3**

## Gate 3 — 템플릿 선택 (mckinsey 카탈로그 매핑)

각 슬라이드에 대해 카탈로그에서 후보 템플릿 1~3개를 추리고, **rationale 변호**:

```markdown
## 템플릿 매핑

Slide 1 (Cover):
  → `cover_slide`
  → 표준 표지, custom 불필요

Slide 7 (제안 아키텍처):
  → `process_flow_horizontal`
  → 3단계 순차 흐름. not `org_chart` (계층 X),
    not `phases_chevron_3` (스타일 캐주얼함)

Slide 11 (실험 결과):
  → `column_simple_growth`
  → 베이스라인 vs 제안 단순 비교. not `column_historic_forecast`
    (시계열 X), not `bubble_chart` (1차원 비교)

Slide 17 (Conclusion):
  → `executive_summary_takeaways`
  → 3개 핵심 takeaway + bullet. 학술 디펜스의 가장 흔한 패턴.

이 매핑대로 빌드할까요?
```

**사용자 확정 ✋ → 빌드**

## 빌드 & 검증

### 1. Python 빌드 스크립트 생성

`output/agent_<slug>.py`:
```python
import os, sys
# 플러그인 경로 (CLAUDE_PLUGIN_ROOT 또는 ~/.claude/plugins/cache 안)
plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
if plugin_root:
    sys.path.insert(0, plugin_root)
else:
    # 폴백: cache 디렉토리 검색
    import glob
    candidates = glob.glob(os.path.expanduser(
        "~/.claude/plugins/cache/seulee26-mckinsey-pptx/*"))
    if candidates:
        sys.path.insert(0, candidates[0])

from dataclasses import replace
from mckinsey_pptx import PresentationBuilder, DEFAULT_THEME
from mckinsey_pptx.theme import Typography

# 한국어 시 KO_THEME 사용
KO_THEME = replace(
    DEFAULT_THEME,
    typography=replace(DEFAULT_THEME.typography, family="Apple SD Gothic Neo"),
    copyright_text="ⓒ 2026 <연구자명>"  # 사용자 이름/소속으로 커스터마이즈 (예: "ⓒ 2026 김승민, POSTECH")
)

b = PresentationBuilder(theme=KO_THEME, default_section_marker="…",
                        auto_page_numbers=True)

# Gate 3에서 결정된 템플릿 시퀀스
b.add("cover_slide", title="...", subtitle="...", ...)
b.add("executive_summary_takeaways", sections=[...])
# ...

b.save("output/<slug>.pptx")
```

### 2. 빌드 실행

```bash
python3 output/agent_<slug>.py
# 에러 발생 시: 인자 형식 확인 후 수정 → rebuild
```

### 3. 시각 검증 (필수, soffice 있을 때)

```bash
mkdir -p output/preview_<slug>
soffice --headless --convert-to pdf \
  --outdir output/preview_<slug> output/<slug>.pptx
pdftoppm -png -r 80 \
  output/preview_<slug>/<slug>.pdf \
  output/preview_<slug>/slide
```

이후 `Read` 도구로 PNG 2~3장 확인:
- [ ] 텍스트가 카드/박스 경계를 넘지 않는가
- [ ] 라벨이 도형 뒤에 가려지지 않는가
- [ ] 제목이 underline rule과 충돌하지 않는가
- [ ] 차트 값 라벨이 겹치지 않는가

문제 있으면 콘텐츠 줄여 rebuild.

soffice 없으면: "시각 검증 도구 없음. .pptx 파일을 PowerPoint/Keynote로
열어 직접 확인 권장" 명시.

### 4. 사용자 보고

```markdown
## 빌드 완료

**파일**: `output/<slug>.pptx` (편집 가능한 .pptx)
**미리보기**: `output/preview_<slug>/slide-*.png` (시각 검증 완료)
**총 슬라이드**: 18장

### 슬라이드 시퀀스
1. cover_slide — 표지
2. executive_summary_takeaways — 연구 개요
3. ...

### 주의사항
- Slide 7 다이어그램: placeholder 사용 (실제 그림 추가 필요)
- Slide 11 차트 데이터: 임시 값 (실제 데이터로 교체 필요)

수정하고 싶은 슬라이드가 있으면 알려주세요. 예: "5번 슬라이드를 X로 바꿔줘"
```

## Output Conventions

- 작업 파일: 사용자 CWD의 `output/` 아래
- 슬러그: 짧은 lowercase-hyphen (예: `bachelor-defense-2026`)
- `default_section_marker="…"` 일관 사용
- `auto_page_numbers=True` 기본
- `mckinsey_pptx/` 소스 직접 수정 금지 — 새 템플릿 필요 시 사용자에게 안내

## Resource Files

- `references/narrative-arcs.md` — 4개 학술 시퀀스 (디펜스/논문/세미나/research_summary)
- `references/academic-tone.md` — 한국어 학술 글쓰기 톤
- `references/catalog-extension.md` — mckinsey 40 템플릿 + 학술 매핑 가이드
- `references/visual-verification.md` — soffice + pdftoppm 검증 절차
- `templates/thesis-defense.md` — 학사/석사 디펜스 시퀀스 (15~20장)
- `templates/paper-presentation.md` — 논문 발표 시퀀스 (8~12장)
- `templates/lab-seminar.md` — 랩 세미나 시퀀스 (10~15장)

## Tone (사용자에게 보고할 때)

- 결과 먼저 (생성된 파일 경로) — 과정 X
- rationale은 짧게 ("Slide 3: `growth_share` — 4 BU의 BCG 분석. not `bubble_chart`.")
- placeholder 사용 시 명시
- 사용자 입력 언어 일치 (한국어 brief → 한국어 응답)

## Examples of Good Briefs

- "디펜스 슬라이드 만들어줘 — 학사 논문, 18분, 한국어"
- "0_Project/in_progress/bachelor_thesis_2026/research_summary 폴더로 디펜스"
- "이 논문(2_Resource/papers/Vaswani_2017.md)으로 학회 발표 슬라이드"
- "랩 세미나 자료 — 지난 한 달 진행 상황, 영문, 12장 정도"

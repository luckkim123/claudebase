# PPT Skills — 사용 가이드

claude-settings의 네 PPT 스킬 (`ppt-academic`, `ppt-lecture`, `ppt-edit`,
`ppt-analyze`)에 대한 사용 가이드.

---

## 빠른 시작

### 처음 사용 전 (한 번만)

1. **claude-settings 동기화**:
   ```bash
   cd ~/claude-settings
   git pull
   ./install.sh           # Mac
   # 또는: pwsh ./install.ps1   # Windows
   ```

   install.sh가 자동 처리:
   - Pretendard 폰트 (Mac brew / Win winget)
   - python-pptx (pip)
   - 두 스킬을 `~/.claude/skills/`에 symlink

2. **mckinsey-pptx 플러그인 설치** (`ppt-academic` 사용 전):

   Claude Code 채팅창에서:
   ```
   /plugin marketplace add seulee26/mckinsey-pptx
   /plugin install axlabs-mckinsey-pptx@axlabs
   ```

   ⚠️ **Claude Code 재시작 필수** — 플러그인은 재시작 후 로드됨.

3. **(선택) LibreOffice 설치** — 시각 검증 원할 때:
   - Mac: `brew install --cask libreoffice && brew install poppler`
   - Win: `winget install TheDocumentFoundation.LibreOffice`

   없어도 .pptx는 정상 생성. 자동 시각 검증만 비활성화.

---

## 네 스킬의 분리

| | `ppt-academic` | `ppt-lecture` | `ppt-edit` | `ppt-analyze` |
|:---|:---|:---|:---|:---|
| **사용 시점** | 새 학술 .pptx 생성 | 새 강의/교육 자료 생성 | 기존 .pptx 수정 | 기존 .pptx에서 spec 추출 |
| **입력** | 주제/시간/발표 유형 | 주제/테마/vault 노트 | 기존 .pptx + 수정 요청 | 기존 .pptx |
| **산출물** | .pptx (편집 가능) | HTML + PNG (캡처) | .edited.pptx (원본 보존) | style_spec.yaml + layout_catalog.md + narrative_outline.md + asset_manifest.yaml |
| **핵심 게이트** | 3개 (구조 → 콘텐츠 → 템플릿) | 2개 (기획서 → 미리보기) | 3개 (plan dry-run → 무결성 V2 → 전수 PNG V1) | 3개 (범위 확정 → 추출 → round-trip 검증) |
| **베이스** | mckinsey-pptx 플러그인 | 직접 작성 (template.html) | python-pptx + soffice | python-pptx + PIL |
| **트리거** | "디펜스", "학회 발표" | "강의 자료", "튜토리얼" | "ppt 수정", "발표자료 수정" | "ppt 분석", "양식 추출" |

---

## ppt-academic 사용

### 기본 호출

```
디펜스 슬라이드 만들어줘 — 학사 논문, 18분, 한국어
```

### vault 통합 호출 (vault 안에서)

```
0_Project/in_progress/bachelor_thesis_2026/research_summary 폴더로 디펜스
```

자동으로:
- `01_research_identity.md` → Cover + Background
- `02_thesis_core.md` → RQ + Method
- `03_publications.md` → Related Work
- ...

### 4가지 narrative arc

| 키워드 | Arc | 슬라이드 수 |
|:---|:---|:---|
| 디펜스 / thesis / 졸업 발표 | thesis-defense | 15~20장 |
| 학회 / paper / conference | paper-presentation | 8~12장 |
| 랩 세미나 / 주간 미팅 / weekly | lab-seminar | 10~15장 |
| (vault) research_summary 폴더 | research_summary 매핑 | 시퀀스 자동 |

### 출력 파일

```
output/
└── <slug>/
    ├── agent_<slug>.py        # 빌드 스크립트
    ├── <slug>.pptx            # 최종 .pptx
    └── preview_<slug>/
        ├── <slug>.pdf
        └── slide-1.png ... slide-N.png   # 시각 검증
```

---

## ppt-lecture 사용

### 기본 호출

```
Transformer 강의 자료 만들어줘, 다크 테마
```

### vault 통합 호출

```
2_Resource/concepts/Transformer_Self_Attention.md 로 강의 슬라이드
```

### 8개 레이아웃

| 레이아웃 | 용도 |
|:---|:---|
| hero-cover | 표지 |
| flow-3step | 순차 흐름 (3단계) |
| side-by-side | A vs B 비교 |
| bento-2x2 | 4개 동등 항목 |
| bento-3x2 | 6개 동등 항목 |
| timeline-h | 시간순 단계 |
| callout-stat | 큰 숫자 (deck당 1개만!) |
| takeaway | 마무리 정리 |

추가: quote-large (대형 인용), pyramid (계층)

### 3개 테마

| 테마 | 추천 use case |
|:---|:---|
| **light** | 강의실 프로젝터 (기본) |
| **dark** | 블로그 / Twitter 임베드 |
| **paper** | 인쇄 / 종이 핸드아웃 |

### 출력 파일

```
output/
└── <slug>/
    ├── index.html         # 메인 (브라우저 자동 오픈)
    ├── outline.md         # 콘텐츠만, 재사용 가능
    └── images/            # 사용자 추가 이미지
```

브라우저에서 우측 상단 버튼:
- 📦 **Download ZIP** — 모든 슬라이드 PNG 일괄
- 🖼 **Save PNG** — 첫 슬라이드만

---

## 머신 간 동기화

### Plugin promotion 룰

claude-settings 룰 ("다른 머신이 채택할 때까지 common으로 올리지 말라")
준수:

1. **첫 머신**: mckinsey-pptx 플러그인 설치 후 사용. settings.json 직접
   수정 X.
2. **두 번째 머신에서도 ppt-academic 쓸 결정**: 그때 `claude/settings.json`의
   `enabledPlugins`에 `axlabs-mckinsey-pptx@axlabs: true` 추가하고
   `marketplaces`에 `axlabs` 등록. commit + push.
3. **다른 머신**: `git pull` + Claude Code 재시작 → 자동 로드.

### Per-machine 비활성화

특정 머신에서 PPT 스킬 비활성화 원하면 `~/.claude/settings.local.json`에:

```jsonc
{
  "enabledPlugins": {
    "axlabs-mckinsey-pptx@axlabs": false   // 이 머신만
  }
}
```

스킬 자체는 symlink로 자동 활성화되므로 비활성화 어려움. 필요시 symlink
삭제: `rm ~/.claude/skills/ppt-academic`.

---

## 디펜스 발표 시나리오 (실전 예시)

학사 논문 디펜스 준비:

```bash
# 1. vault에서 작업
cd ~/ksm_Obsidian

# 2. Claude Code 시작
claude

# 3. 자료 위치 명시
> 0_Project/in_progress/bachelor_thesis_2026/research_summary 폴더로
  디펜스 슬라이드 만들어줘. 18분 발표, 한국어, 심사위원 청중.
```

흐름:
1. **Gate 1**: narrative arc 제안 (18장, thesis-defense 시퀀스)
2. **사용자 확정** → Gate 2
3. **Gate 2**: 각 슬라이드의 콘텐츠 (vault 파일 자동 매핑)
4. **사용자 확정** → Gate 3
5. **Gate 3**: 각 슬라이드의 mckinsey 템플릿 + rationale
6. **사용자 확정** → 빌드
7. **빌드** → `output/bachelor-defense-2026.pptx` 생성
8. **시각 검증** (LibreOffice 있으면) → PNG 2~3장 자동 확인
9. **보고**: 18장 시퀀스 + 템플릿 변호 + placeholder 명시

---

## 강의 자료 시나리오 (실전 예시)

블로그용 Transformer 설명:

```bash
cd ~/ksm_Obsidian
claude

> 2_Resource/concepts/Transformer_Self_Attention.md 로 강의 슬라이드
  만들어줘, 다크 테마, 7장 정도
```

흐름:
1. **Gate 1**: 7장 기획서 (콘텐츠 + 레이아웃 동시)
2. **사용자 확정** → Gate 2
3. **Gate 2**: 첫 2장(hero + 본문 1장) 미리보기 빌드 → 브라우저 자동 오픈
4. **사용자 확정** → 전체 빌드
5. **빌드** → `output/transformer-self-attention/index.html`
6. 브라우저에서 **📦 Download ZIP** 클릭 → 7장 PNG 일괄 다운로드
7. 블로그에 PNG 임베드 또는 GIF로 변환 가능

---

## 자주 묻는 질문

### Q: ppt-academic이 mckinsey-pptx 못 찾는다고 한다
- Claude Code를 완전히 종료 후 재시작했는지 확인
- `/agents` 입력 시 `mckinsey-slide-agent` 보이는지 확인
- 안 보이면 플러그인 재설치: `/plugin install axlabs-mckinsey-pptx@axlabs`

### Q: 시각 검증 단계에서 멈춤
- LibreOffice 미설치일 때 정상 — `.pptx`는 정상 생성됨
- "시각 검증 도구 없음" 메시지 후 사용자에게 PowerPoint로 확인 요청
- 검증 원하면 `brew install --cask libreoffice && brew install poppler`

### Q: 한글 폰트가 깨진다 (ppt-lecture)
- 브라우저에서 `await document.fonts.ready` 처리 후 캡처해야 함
- template.html에 이미 적용됨 — 새 클래스/스크립트 추가 시 주의
- Pretendard 미설치여도 Noto Sans KR로 자동 fallback (CDN)

### Q: 사용자 색상 hex로 만들고 싶다
- ppt-lecture는 3개 테마만 지원 (미적 일관성 보호)
- 강하게 원하면 `output/<slug>/index.html`의 `:root[data-theme="light"]`
  값을 직접 수정 가능 (자기 책임)

### Q: 슬라이드를 추가하고 싶다 (생성 후)
- ppt-academic: 빌드 스크립트(`output/agent_<slug>.py`) 수정 후 재실행
- ppt-lecture: `output/<slug>/index.html`에 `<section class="slide ...">` 추가

---

## Troubleshooting

### macOS

| 문제 | 해결 |
|:---|:---|
| `pip3 install` permission denied | `--user` 플래그 사용 (install.sh가 이미 적용) |
| Pretendard 미적용 | 시스템 재시작 또는 폰트 캐시 갱신 (`atsutil databases -remove`) |
| `soffice` 첫 실행 보안 경고 | 시스템 환경설정 > 보안 > "허용" |

### Windows

| 문제 | 해결 |
|:---|:---|
| `winget install` 권한 없음 | 관리자 권한 PowerShell에서 실행 |
| `python` 명령 없음 (`python3` 만 있음) | PATH에 python.exe 추가 |
| symlink 생성 실패 | Developer Mode 활성화 또는 관리자 권한 |

---

## 향후 확장 (현재 미구현)

이 신호 보이면 그때 추가:

- **카드뉴스 모드**: vault 콘텐츠를 SNS 공유 시 — `--mode card-news`
  (1:1 정사각, slides-grab 패턴 차용)
- **포스터 모드**: 학회 포스터 — 별도 `ppt-poster` 스킬
- **슬라이드 노트**: 발표 스크립트 자동 생성 — PPTX notes 필드
- **다국어**: 영어/일본어/중국어 톤 가이드

---

## ppt-edit 사용

### 언제 사용

- 이미 만들어진 .pptx의 텍스트 한 줄 교체 (L1)
- 슬라이드 추가 / 삭제 / 순서 변경 (L2)
- 폰트 / 컬러 / 여백을 deck 전체에 일괄 적용 (L3)
- 디펜스 발표자료의 패치 사이클 (vN → vN+1)
- 새 deck 생성이 아닌 "이 PPT의 X를 Y로 바꿔줘" 형태의 요청

레이아웃 구조 자체를 재설계(L4)하거나 새 deck를 처음부터 만들 때는
`ppt-academic`을 사용. 기존 .pptx에서 스타일 spec만 추출할 때는
`ppt-analyze`를 사용.

### 기본 호출

```
260617_Defense_Seungmin_Kim_v20.pptx에서 슬라이드 1 영문 제목 추가해줘
```

```
내 디펜스 PPT 폰트를 전체적으로 Pretendard로 통일해줘
```

### Workflow (3-게이트)

1. **Gate 0** — 의존성 체크 (`python-pptx`, `soffice`, `pdftoppm`). 미설치 시 작업 거부.
2. **Gate 1 (Dry-run)** — 원본 텍스트/스타일 인용 출력 (V3 Provenance Lock) + 변경 plan 제시. 사용자 OK 전 적용 없음.
3. **Gate 2 (적용 + 무결성)** — 새 파일에 패치 적용 → `verify_pptx.py` 5개 항목 자동 실행. 1개라도 FAIL이면 중단.
4. **Gate 3 (전수 PNG 정독)** — deck 전체 슬라이드 PNG 렌더 + Read 도구로 정독. 변경 대상이 아닌 슬라이드도 모두 확인.

### 핵심 안전 규칙 (V1~V6)

| 규칙 | 내용 |
|:---|:---|
| **V1 전수 PNG 정독** | 변경된 슬라이드만 보는 것 금지. deck 전체 PNG 확인 필수. |
| **V2 다층 무결성 게이트** | `verify_pptx.py` 5/5 PASS 필수 (zip CRC, python-pptx open, soffice PDF, OOXML 직접 검사, orphan master). |
| **V3 Provenance Lock** | 원본 텍스트 인용 확인 후 변경. 미확인 상태에서 신규 문구 작성 금지. |
| **V4 콘텐츠 신규 작성 금지** | 사용자가 명시하지 않으면 LLM이 새 문구 생성 안 함. |
| **V5 출력 분리 + Dry-run** | 원본 in-place 수정 금지. 기본은 항상 dry-run plan 먼저. |
| **V6 카테고리 전수 점검** | 한 슬라이드 결함 지적 시 같은 카테고리 전체 슬라이드 일괄 점검. |

### 출력 파일

```
output/<slug>/
├── <deck>.edited.pptx    # 수정본 (원본 보존)
├── verify_report.json    # V2 무결성 검증 결과
└── regression_check.md   # V1 전수 정독 보고
```

---

## ppt-analyze 사용

### 언제 사용

- 기존 .pptx에서 design system(폰트/컬러/여백/레이아웃 패턴) 추출
- "이 양식 그대로 새 deck 만들어줘"의 사전 준비 단계
- 디펜스 deck의 design tokens 정리
- 라이선스/누락 자산 점검 (asset_manifest)
- 자연스러운 파이프라인: `ppt-analyze` → spec 추출 → `ppt-academic`으로 새 deck 생성

기존 .pptx 파일을 직접 수정할 때는 `ppt-edit`를 사용.
analyze는 read-only — 원본 파일을 절대 수정하지 않는다.

### 기본 호출

```
박건우_선배_발표.pptx에서 design system 추출해줘
```

```
이 PPT 양식 그대로 내 디펜스 deck 만들고 싶어, 먼저 분석해줘
```

### Workflow (3-게이트)

1. **Gate 0** — 의존성 체크 (`python-pptx`, `pyyaml`, `Pillow`, `soffice`, `pdftoppm`).
2. **Gate 1 (추출 범위 확정)** — 기본 모드(G4 hybrid) vs `--detail full` 선택. 사용자 확정.
3. **Gate 2 (추출 + 산출물 생성)** — 무결성 사전 점검(A5) → `extract_spec.py` 실행 → 4종(또는 5종) 파일 생성.
4. **Gate 3 (Round-trip 검증)** — 추출한 spec으로 대표 슬라이드 1장 재생성 → 원본 PNG와 비교 → 픽셀 유사도 ≥ 85% 확인.

### 4종 산출물

| 파일 | 형식 | 내용 |
|:---|:---|:---|
| `style_spec.yaml` | YAML | deck-level design tokens (typography / palette / spacing) + layout별 spec |
| `layout_catalog.md` | Markdown | 슬라이드별 layout 패턴 분류 + 빈도 + 예시 슬라이드 번호 |
| `narrative_outline.md` | Markdown | 슬라이드 제목 + bullet 트리 (텍스트 흐름) |
| `asset_manifest.yaml` | YAML | 사용된 이미지 / 폰트 목록 |

`--detail full` 옵션 추가 시 5번째 파일 `slides_full_dump.yaml` 생성 (슬라이드 1장당 모든 shape의 위치/크기/폰트/컬러 완전 dump).

### 출력 파일

```
output/<deck-slug>/
├── style_spec.yaml
├── layout_catalog.md
├── narrative_outline.md
├── asset_manifest.yaml
├── slides_full_dump.yaml   # --detail full 옵션 시만
└── roundtrip/
    ├── original_slide1.png
    ├── regenerated_slide1.png
    ├── diff_slide1.png
    └── roundtrip_report.md
```

### 산출물 활용

추출한 spec을 downstream에서 사용:

```
output/박건우_v18/style_spec.yaml의 design tokens 적용해서 내 디펜스 deck 만들어줘
```

```
내 deck를 output/박건우_v18/style_spec.yaml의 폰트/팔레트로 통일해줘
```

---

## 관련 파일

- `skills/ppt-academic/SKILL.md` — 학술 스킬 진입점
- `skills/ppt-academic/references/` — 4개 참조 (narrative-arcs, academic-tone,
  catalog-extension, visual-verification)
- `skills/ppt-academic/templates/` — 3개 시퀀스 (thesis-defense,
  paper-presentation, lab-seminar)
- `skills/ppt-lecture/SKILL.md` — 강의 스킬 진입점
- `skills/ppt-lecture/assets/template.html` — 시드 HTML
- `skills/ppt-lecture/references/` — 5개 참조 (layouts, themes, components,
  checklist, lecture-tone)
- `skills/ppt-edit/SKILL.md` — 수정 스킬 진입점 (V1~V6 Hard Rules, 3-게이트)
- `skills/ppt-edit/scripts/verify_pptx.py` — 무결성 검증 헬퍼 (V2, self-contained)
- `skills/ppt-analyze/SKILL.md` — 분석 스킬 진입점 (A1~A5 Hard Rules, 3-게이트)
- `skills/ppt-analyze/scripts/extract_spec.py` — 추출 헬퍼
- `skills/ppt-analyze/scripts/roundtrip_check.py` — round-trip 검증 헬퍼
- `platform/macos/install.sh` — Mac 의존성 자동 설치
- `platform/windows/install.ps1` — Win 의존성 자동 설치
- `docs/plans/2026-05-10-ppt-skills-design.md` (vault) — ppt-academic/lecture 설계 문서
- `docs/plans/2026-05-11-ppt-edit-analyze-design.md` (vault) — ppt-edit/analyze 설계 문서

---

**Last Updated**: 2026-05-24
**Designed By**: 김승민 + Claude Opus 4.7 (1M context)
**License**: 본인 환경 전용

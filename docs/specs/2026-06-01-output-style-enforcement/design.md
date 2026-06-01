# Output-Style Enforcement — Design

**Date:** 2026-06-01
**Status:** DESIGN — awaiting approval. No code written yet.
**Author:** session (workspace), for claudebase

---

## 1. Problem

LLM 출력을 "사람이 빠르고 정확하게 이해하도록" 만드는 규율(구조 먼저·인용·간결·불확실성 표현·시각적 구획화)을
CLAUDE.md 에 *글로 적는 것*은 권고일 뿐이라 큰 컨텍스트에서 잘 안 지켜진다. 사용자는 **코드로 강제되는
프로세스**(hook)를 원한다. 추가로 사용자는 구어체(chatty/sycophantic)를 싫어하고 **간결·단정한 표현**을
선호한다.

이 선호는 취향이 아니라 근거가 있다 — verbosity·sycophancy 는 정확도·신뢰를 *떨어뜨린다*는 실증이 있다(§3).

## 2. Research base (요약, 전체 출처는 research.md)

| 원칙 | 핵심 근거 | 강도 |
|:---|:---|:---|
| 답 먼저(BLUF) + 의미 있는 헤딩 | NN/g eyetracking: heading-only "layer-cake" 스캔이 가장 효율적 | 강 |
| 불릿은 기본값 아님, 설명은 산문 | Anthropic Claude4 system prompt + OpenAI GPT-5.1 guide 명시 | 강(공식) |
| 비교는 표 | Fact-box RCT: 이해도 79.6% vs 69.7%, d=0.39 | 강(RCT) |
| 간결 = 정확 | "Verbosity ≠ Veracity" arXiv:2411.07858: 장황할수록 최대 27.6% 더 틀림 | 강 |
| 구어체·아첨 회피 | Anthropic sycophancy(2310.13548); "Be Friendly Not Friends"(2502.10844): 아첨이 신뢰↓ | 강 |
| 불확실성은 모호한 헤지 말고 지식 경계 명시 | epistemic marker(NAACL2025): 모호한 헤지는 실제 불확실성 반영 못 함 | 강(반례) |
| 네모박스 = 가장 강한 그룹핑 | Common Region(Palmer1992): 테두리가 근접성보다 강함 | 강 |
| 박스 남용 금지 | Google/NN/g: 페이지당 1~2개, 연속 금지 | 강 |

> 문헌 공백: "불릿-과다 vs 산문-과다"를 사람 이해도로 직접 비교한 peer-reviewed RCT 는 없다.
> → 강제는 "명백한 위반"(필러·아첨·인용 없는 사실 주장)에만 걸고, 포맷 취향(불릿 vs 산문)은 nudge 로만.

## 3. Why hooks, and what a hook can/can't do

- **Hook = harness 가 실제로 실행하는 코드.** 모델 의지와 무관하게 작동 → "명백한 코드 프로세스".
- **하지만 hook 은 detect 는 해도 rewrite 는 못 한다.** 재작성은 결국 모델이 한다.
  → 가능한 것은 "위반 검출 → block + 교정 지시 주입". (기존 `askuserquestion_retry.py`·
  `detect_malformed_toolcall.py` 가 정확히 이 패턴.)

세 층으로 조합한다(사용자 결정: 검출 hook + 주입 둘 다):

| 층 | 이벤트 | 강제력 | 역할 |
|:---|:---|:---:|:---|
| **검출 hook** | Stop | 강(코드) | 명백한 위반만 backstop. 1회 block + 교정 주입 |
| **컨텍스트 주입 hook** | UserPromptSubmit | 중(모델 의존) | 매 턴 출력-스타일 baseline 을 system-reminder 로 nudge |
| **선언 명세** | output-style 파일 + CLAUDE.md 1줄 포인터 | 약(권고) | 박스 문법·톤 가이드 baseline |

## 4. Scope & opt-in (사용자 결정: claudebase 배포 + 사용자가 켜고 끔)

- claudebase repo 에 설계 → `install.sh` 가 `runtime/hooks/` 를 배포(기존과 동일 경로).
- **opt-in (기본 OFF).** claudebase 는 모든 머신·프로젝트에 배포되므로, 출력 스타일을 강제로 켜면
  다른 작업(코드·논문 등)에 부작용. 따라서:
  - 환경변수 `CLAUDEBASE_OUTPUT_STYLE` 이 set 일 때만 hook 이 활성(미set 이면 즉시 exit 0).
  - 값: `off`(기본/미set) · `nudge`(주입만) · `enforce`(주입 + 검출 block).
  - kill switch 기존 패턴(`DISABLE_OMC`/`OMC_SKIP_HOOKS`)과 공존 — 이들이 set 이면 무조건 OFF.

## 5. 검출 hook 설계 — `output_style_guard.py` (Stop)

기존 `detect_malformed_toolcall.py` DNA 를 그대로 상속:
- `stop_hook_active` **3-state** 루프 가드(present-true=재발화 skip / present-false=1회 block /
  absent=fail-safe allow).
- 어떤 예외·malformed stdin → `exit 0` (hook 버그가 세션을 못 막음).
- `.omc/logs/output_style.jsonl` 텔레메트리(block 여부 무관 기록).
- settings command 필드에 idempotent 마커 주석 `# OUTPUT_STYLE_GUARD`.
- 결정은 JSON body(`decision: block` + `reason` + `hookSpecificOutput.additionalContext`)로 전달.

### 검출 규칙 (명백한 위반만 — false positive 최소화)

`enforce` 일 때만 block. 보수적으로, 다음 **고확신** 패턴만:

1. **구어체 필러 오프너** — 응답 *첫 줄*이 다음으로 시작:
   `Certainly!`/`Great question`/`Sure thing`/`Of course!`/`I'd be happy to`/`물론입니다`/`좋은 질문` 등.
   (정전: Anthropic 은 "validation-forward phrasing 최소화"를 default 로 명시.)
2. **아첨 패턴** — `That's a great/excellent/fantastic ...`, `You're absolutely right` 가 응답 *오프너*.
3. **인용 없는 사실 주장** — (보류, §7 위험) 자동 검출 어려움. v1 에서는 제외.

> v1 검출은 (1)(2) 오프너 필러/아첨만. 장황함·불릿 남용은 정량 임계가 위험해 검출 대상에서 제외하고
> nudge(주입)로만 다룬다. 위반 시 block reason = "오프너 필러/아첨 제거하고 결론부터 다시"+증거(첫 80자).
>
> **code-reviewer 반영(2026-06-01)**: 영어 패턴은 감탄형만 매칭(`of course!`·`absolutely!`), 평서 부사
> (`of course it does`·`absolutely not`)는 통과. 한국어 `맞-` 계열(`맞습니다`·`정확히 맞`)은 정상 어간
> (맞는·맞물려·맞춰)과 과도하게 겹쳐 **v1 에서 제외** — §7 "안전하게 시작, 텔레메트리로 확장" 원칙. 회귀
> 테스트 `test_declarative_adverbs_not_flagged`·`test_exclamatory_filler_still_flagged` 로 고정.

## 6. 주입 hook 설계 — `output_style_inject.py` (UserPromptSubmit)

- `CLAUDEBASE_OUTPUT_STYLE` 가 `nudge`/`enforce` 일 때만 system-reminder 1개 주입.
- 주입 내용 = **§2 표의 5줄 기본값**(BLUF·산문우선·비교는표·간결단정·불확실성은경계명시) + 박스 1~2개 한도.
- UserPromptSubmit hook 출력은 `hookSpecificOutput.additionalContext`(공식 필드)로 전달.
- 짧게(≤12줄). 매 턴 주입이라 길면 context bloat.

## 7. Risks & mitigations

| 위험 | 완화 |
|:---|:---|
| false positive(정상 응답을 필러로 오판) | 오프너만·고확신 패턴만·1회 block 한정·기본 OFF·로그로 검증 후 확장 |
| 인용 강제가 코드/논문 작업 방해 | v1 에서 인용 검출 제외. citation 은 논문 하네스(oms)가 이미 다룸 |
| 매 턴 주입 context bloat | 주입 ≤12줄, enforce 가 아니라 nudge 가 기본 시도값 |
| 모든 세션에 hook 부담 | env 미set 시 첫 줄에서 exit 0 (거의 비용 0) |
| 다국어(한/영) 필러 패턴 누락 | 한·영 양쪽 패턴 등록, 로그로 미검출 사례 수집 |
| sycophancy hook 자체가 over-correction | enforce 는 명시 opt-in. 기본은 nudge 권장 |

## 8. Deliverables (다음 plan.md 가 TDD 태스크로 분해)

1. `runtime/hooks/output_style_guard.py` (Stop) + 단위테스트
2. `runtime/hooks/output_style_inject.py` (UserPromptSubmit) + 단위테스트
3. `config/settings.json` 에 두 hook 등록(마커 주석, env 가드)
4. output-style 명세 파일 1개(박스 문법·톤 baseline) — 위치 TBD(`runtime/` 또는 `templates/`)
5. README + config/CLAUDE.md 에 opt-in 사용법 1줄
6. `docs/specs/.../research.md` (이미 수집한 전체 출처)

## 8b. 박스(시각적 구획화) — box CLI 도구 (사용자 결정 2026-06-01)

사용자는 "Claude Code 시작화면처럼 터미널 폭 상관없이 깔끔한 유니코드 테두리 박스"를 원함.

**핵심 제약**: 모델이 응답 텍스트에 직접 `╭─╮│╰─╯` 를 그리면 **CJK 폭(한글=2칸) 때문에 우변이 어긋난다**
(실측 확인). Claude Code 시작화면이 안 깨지는 건 *앱(코드)이 출력 직전 폭을 계산해 렌더*하기 때문 —
모델이 그린 게 아니다. Stop hook 은 응답 텍스트를 *치환*할 수 없어(decision:block+reason 만 가능) hook 으로
"다시 그려 끼워넣기"는 불가.

**해결**: 폭 계산을 코드에 위임하는 **box CLI 도구** `runtime/bin/box.py`. 모델이
`python3 ~/claudebase/runtime/bin/box.py "제목" "줄1" "줄2"` 로 호출하면 파이썬이
`unicodedata.east_asian_width` 로 각 문자 폭을 계산해 우변까지 완벽히 맞춘 박스를 stdout 으로 출력
(시작화면과 동일 원리, stdlib 만, wcwidth 의존 없음). output-style baseline 이 "강조 블록은 이 도구로"를 권함.

box.py 사양: title + N lines 인자, East Asian Width W/F=2·기타=1 폭 계산, 박스 폭 = max(제목폭+4, 각줄폭+2),
ASCII fallback(`--ascii` 또는 비유니코드 터미널). 순수 함수 `visual_width(s)`·`render_box(title, lines)` 분리해 테스트.

**박스 분류(타입)** — 사용자 결정 2026-06-01: **이모지 없음**(이모지 폭이 터미널마다 1/2칸 제각각이라 정렬을 흔듦).
5개 *정의된* 타입은 표준 라벨 자동 부여, 그 외는 Claude 가 즉석에서 적절한 제목을 지어 자유 분류
(GitHub alerts 고정세트 + Obsidian callouts 자유폴백의 결합):
- `--type skill` → `SKILL` (`--label X` 와 함께 쓰면 `SKILL · X`)
- `--type analysis` → `분석`
- `--type plan` → `계획`
- `--type summary` → `요약`
- `--type warning` → `주의`
- (정의 안 됨) `box.py "검증 결과" "..."` → Claude 가 지은 자유 제목 그대로.
`type_label(t)` 가 정의된 타입이면 라벨, 아니면 None(자유 제목으로 폴백). 5종은 일관성, 그 외는 유연성.

**자율성 우선(사용자 결정 2026-06-01)**: 분류는 Claude 가 *내용을 보고 가장 적절한 제목을 스스로 정하는* 게
기본. 5종은 강제 메뉴가 아니라 "자주 쓰는 것엔 표준 라벨이 있다" 정도의 편의. baseline 주입 문구도
"5종 중 골라라"가 아니라 "네가 판단해 제목 정하라, 자주 쓰는 5종은 --type 으로 편하게"로 무게중심을 둠.

## 9. Decisions (확정 2026-06-01)

- **D1. 확정: 오프너 필러/아첨만 검출.** 장황함·불릿 남용·인용은 검출 대상에서 제외, nudge 로만 다룬다.
  (인용은 oms 가 이미 담당. 장황함 정량 임계는 false positive 위험.)
- **D2. 확정: 기본 `off` (완전 opt-in).** 설치해도 `CLAUDEBASE_OUTPUT_STYLE` 를 명시적으로 set 해야 작동.
  claudebase 가 모든 머신·프로젝트에 배포되는 성격이라 가장 안전. 원하는 머신에서만 shell 에 export.
- **D3. 보류(v1 범위 밖).** 공식 `output-styles/` 메커니즘 노출은 v1 에서 안 한다. hook(주입+검출) +
  output-style 명세 파일로 충분. 향후 필요 시 별도 검토.

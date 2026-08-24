# 2026-07-22 선행 계획(HARNESS_UPGRADE_PLAN.md) 재평가

조사일: 2026-08-22. 대상: `/Users/kimseungmin/ksm_Obsidian/2_Resource/lectures/claude_code_complete_master/HARNESS_UPGRADE_PLAN.md`(205줄, git 커밋 1회 `738e7b56`, 2026-07-22 작성, 이후 수정 0회).

## 요약

- K01~K17 + M1/M2/M5 전 항목 실측 결과 **미실행 판정을 뒤집을 만한 신규 구현은 0건** — 계획 작성 이후 한 달간 claudebase·om*·vault 어디에도 이 계획이 실행된 흔적이 없다.
- 그런데 이번 재조사에서 **계획 자체의 두 전제가 틀렸다는 것이 새로 확인됐다**:
  - **M1(Bash 콜론 와일드카드)은 실측과 충돌 — 기각.** 공식 문서(`code.claude.com/docs/en/permissions`)를 이번에 직접 대조한 결과, 콜론형은 폐기되지 않았고 지금도 공백형과 완전히 동등한 문법이다. 계획이 "선행 게이트"로 요구했던 문서 대조를 아무도 실행하지 않은 채 한 달을 보낸 것 — 그 게이트를 이번에 수행하자 전제가 무너졌다.
  - **K17(신규 훅 이벤트)은 "보류(실존 미확인)"에서 "실존 확인됨"으로 격상.** 같은 방식으로 공식 문서(`code.claude.com/docs/en/hooks`)를 이번에 직접 대조하자 `TaskCompleted`·`TeammateIdle`·`InstructionsLoaded`·`FileChanged` 전부 실존이 확인됐다. 이 확인은 K08의 선행 게이트 Step 1도 동시에 해소한다.
- 2026-08-15~17 측정("스킬층 정확성 변별 0, 이득은 훅에서, 스킬 호출 0건")에 비추면 K13(스킬 3종 재가동)은 **높은 입증 부담 대상으로 강등**해야 한다 — "스킬을 더 만들자"류이고, 그 측정 자체가 "이미 만든 스킬도 안 불렸다"는 뜻이라 신규 3종을 만들 근거가 약하다. 반대로 K08·K09·K10·K11·K12·K01은 전부 **훅/모델라우팅/계측 계열**이라 같은 측정이 오히려 근거를 강화한다.
- 실행 안 된 이유는 구조적으로 설명된다: 계획이 `0_Project/in_progress`(실행 계층)가 아니라 `2_Resource`(참고자료 계층)에 저장됐고, 어떤 캘린더·프로젝트 트래킹도 이를 가리키지 않으며, MEMORY.md의 계획 포인터 자체가 무관한 PR을 가리키는 낡은 사본이었다.

---

## 재판정 표

범례 — 상태: `미구현`/`부분`/`완료` (실측). 재판정: `유효`(그대로 흡수)/`강화`(실측 근거로 우선순위 상향)/`강등`(입증 부담 상향)/`기각`(전제가 실측과 충돌)/`격상`(불확실 해소, 채택 검토 가능)/`무관`(2026-08-15~17 측정과 무관).

| ID | 항목 | 원래 판정 | 현재 상태(실측) | 재판정 | 근거 |
|:---|:---|:---|:---|:---|:---|
| K01 | 토큰 경제 env 노브 | new | 미구현 — `config/settings.json` env 블록 6개 키뿐, 토큰 관련 키 0건 (`~/claudebase/config/settings.json:2-9`) | **강화** | +41%/+69% 비용 초과 실측이 직접 완화 근거가 됨 |
| K02 | `$schema` + `CLAUDE.local.md` gitignore | new | 미구현 — `$schema` 0건, gitignore 템플릿 0건 | 유효 | 무관 항목, 위생 성격 |
| K03 | opusplan 평가 | new | 미평가 — OMC 4.15.10 `CLAUDE_TIER_ALIASES = {sonnet,opus,haiku,fable}`, opusplan 부재 확인(`~/.claude/plugins/cache/omc/oh-my-claudecode/4.15.10/dist/config/models.js:4`) | 유효 | 전제 그대로 유효, 채택 아닌 "평가만"이라 리스크 낮음 |
| K04 | doctor 설치채널 드리프트 체크 | partial | 미구현 — SKILL.md에 "claude doctor" 문자열 자체 0건(기존 "omc doctor conflicts"는 다른 목적) | 유효 | 무관 |
| K05 | robot 규칙 → `.claude/rules/` + `paths:` | new | **부분** — `.claude/rules/` 디렉터리는 2026-08-10에 이미 생겼지만 다른 용도(`code-review-graph.md`, 29,903바이트)이고, robot 규칙은 이관 안 됨(`.claude/rules-archive/robot-code.md`만 dead 상태로 존재), 어떤 스킬 frontmatter에도 `paths:` 0건 | 유효(범위 축소) | 메커니즘은 이미 이 vault에서 쓰이고 있음 — "신규 도입"이 아니라 "기존 패턴 적용"으로 범위가 좁아짐 |
| K06 | SKILL.md 토큰 예산 테스트 + 분할 | partial | 미구현, **문제가 커짐** — `sync-claudebase/SKILL.md` 78,812바이트(원계획 추정 8-10k 토큰 대비 바이트/4 근사 ~19.7k), `exp-analyze/SKILL.md` 47,403바이트(추정 ~11.9k, 원계획 9-11k와 근접). claudebase에 `test_skill_budget` 부재, omx `omx-core/tests/test_skill_budget.py`만 존재 | 유효(악화) | 방치된 한 달 사이 파일이 더 커졌다는 것이 실측됨 |
| K07 | `context: fork` 파일럿 | new | 미구현 — 전 om*+claudebase `^context:` frontmatter grep 0건 | 유효 | 무관 |
| K08 | Agent Teams TaskCompleted 게이트 | partial | 미구현 — `verify-deliverables.mjs`(OMC 플러그인 캐시)는 여전히 6곳에서 `continue:true` 하드코딩(`~/.claude/plugins/cache/omc/oh-my-claudecode/4.15.10/scripts/verify-deliverables.mjs:161,169,177,217,226,229`), `hooks.json`은 여전히 구 11개 이벤트만(`TaskCompleted`/`TeammateIdle` 부재) | **강화 + 선행게이트 Step1 해소** | 공식 문서(WebFetch `code.claude.com/docs/en/hooks`) 확인 결과 `TaskCompleted`·`TeammateIdle` 실존. Step2(피드백 채널이 리뷰 주체로 가는지 완료 팀원 본인에게 가는지)는 이번 세션 범위 밖 — 다음 세션에서 곧바로 repro 착수 가능 |
| K09 | `/team` sonnet 핀 규칙 | new | 미구현 — `config/CLAUDE.md`에 `/team` 관련 문구 다수 있으나 "sonnet 핀" 지시 0건(`~/claudebase/config/CLAUDE.md:34,211,217-218`) | **강화** | 비용 초과 실측이 직접 근거 |
| K10 | MEMORY.md → omha 카드 승격 파이프라인 | new | 미구현(과제 프롬프트에 기확인으로 명시) | **강화, Impact 5 유지** | "이득은 훅에서" 실측과 정합 — 이 항목 자체가 훅/카드 계열 |
| K11 | 가드 유효성 재감사 스텝 | new | 미구현(과제 프롬프트에 기확인으로 명시). `docs/upstream-patches.md`에 Removal condition 텍스트(34·62행)는 있으나 스캐너 0건, `simplified:`/`ponytail:` 마커 스캐너도 0건(ponytail의 debt 스킬은 다른 마커·소스코드 한정) | **강화** | 가드=훅이 가치 원천이라는 실측과 정합 |
| K12 | session-report 플러그인 활성화 | new | 미구현 — `enabledPlugins` 16개 목록에 부재(`~/claudebase/config/settings.json:207-226`) | **강화** | 스킬층 무변별·훅층 이득이라는 주장 자체를 검증할 계측기로 특히 유용 |
| K13 | skill-creator로 스킬 3종 재가동(ppt/hancom-fill/docx-toolkit) | partial | 미구현 — `.sp/plans/`에 설계문서 5건만 존재(`2026-05-10-hancom-fill-design.md` 등), 실제 빌드 코드는 vault·workspace 어디에도 0건 | **강등** | "스킬을 더 만들자"류. 스킬 호출 0건 실측은 이미 만든 스킬조차 안 불렸다는 뜻이라 신규 3종 근거가 약함. 입증 부담 상향 권고 — 만들더라도 "만든 뒤 실제 호출되는지" 계측(K12로 가능)이 선행돼야 함 |
| K14 | headless `--bare`/`--json-schema` | 기각(사문) | 변화 없음 | 유지 | 새 증거 없음 |
| K15 | autopilot/ralph OS 샌드박스 | 보류(미검증) | 이번 세션 범위 밖 — 미조사 | 보류 유지 | 확인 안 함 |
| K16 | 프로젝트 스코프 MCP 번들 | 보류(미검증) | 이번 세션 범위 밖 — 미조사 | 보류 유지 | 확인 안 함 |
| K17 | 신규 훅 이벤트(InstructionsLoaded 등) | 보류(실존 미확인) | — | **격상: 실존 확인됨** | 공식 문서(WebFetch `code.claude.com/docs/en/hooks`) 확인 — `TaskCompleted`("When a task is being marked as completed"), `TeammateIdle`("When an agent team teammate is about to go idle"), `InstructionsLoaded`("When a CLAUDE.md or `.claude/rules/*.md` file is loaded into context. Fires at session start and when files are lazily loaded during a session"), `FileChanged` 전부 이벤트 테이블에 실존. `InstructionsLoaded`는 vault의 "권위 파일 정독 우선" 증거 규율의 계측기로 특히 매력적(원계획 §161이 이미 지적) |
| M1 | Bash 권한 콜론 와일드카드 전수 감사 | 비평 발굴 | 실측 재확인 — 콜론형 99/139건(원계획 99/138과 거의 일치, 그 사이 규칙 1개 추가), 전수 확인 결과 예외 0건으로 전부 `:*)"$` 형태(끝에 위치) | **기각 — 실측과 충돌** | 공식 문서(WebFetch `code.claude.com/docs/en/permissions`) 인용: "The `:*` suffix is an equivalent way to write a trailing wildcard, so `Bash(ls:*)` matches the same commands as `Bash(ls *)`." — 콜론형은 폐기되지 않았고 지금도 공백형과 완전 동등하다. 단 "The `:*` form is only recognized at the end of a pattern"이라는 조건이 있는데, vault의 99개는 전수 확인 결과 전부 끝에 위치해 이 조건도 만족한다. UI가 "Yes, and don't ask again" 선택 시 공백형을 새로 쓰기 시작했을 뿐(스타일 변경), 기존 콜론형이 매칭 실패 중이라는 원계획의 핵심 주장은 틀렸다 |
| M2 | 프리미티브 선택 가이드 카드 | 비평 발굴 | 미구현 — `~/claudebase`·OMC omc-reference 어디에도 부재 | 유효(저비용 유지) | 무관, 낮은 우선순위 |
| M5 | learning-output-style 트랩 감사 | 비평 발굴 | **대상 자체가 현재 비활성으로 보임** — `enabledPlugins` 16개 목록에 `learning-output-style` 부재, `~/.claude/plugins/data/learning-output-style-inline` 디렉터리만 잔존(과거 활성 흔적일 가능성, 이번 세션에서 활성화 이력 재구성 못함) | **무의미해짐(likely)** | 원계획이 감사하려던 플러그인이 지금은 활성 플러그인 목록에 없다 — 감사할 대상이 없어 보이나, 잔존 데이터 디렉터리의 의미를 확인 못해 confidence는 likely에 그침 |

---

## 왜 한 달간 실행되지 않았는가 (실측 근거)

1. **실행 계층 밖에 저장됐다.** 계획 파일은 `2_Resource/lectures/claude_code_complete_master/`(PARA "Resource"=참고자료 계층)에 있다. `0_Project/in_progress/`를 `harness`·`claudebase` 키워드로 검색한 결과 대응 프로젝트 항목 0건(`find 0_Project/in_progress -maxdepth 2 -iname '*harness*' -o -iname '*claudebase*'` → 빈 결과). 이 vault의 다른 활성 프로젝트(예: albc)는 session-gate가 걸려 있어 세션 시작마다 강제로 인수인계 문서를 읽게 만드는데, 이 계획에는 그런 재부상 메커니즘이 전혀 없다.
2. **커밋 1회, 이후 손댄 흔적 없음.** `git log --follow`로 전체 이력을 확인한 결과 2026-07-22 최초 작성 커밋(`738e7b56`) 단 하나뿐이다. 부분 실행의 흔적(일부 항목만 체크된 diff 등)도 없다 — "전부 안 했거나 전부 미뤘다"의 이분법.
3. **캘린더·트래킹 어디도 이 계획을 가리키지 않는다.** `0_Project`와 `3_Archive/calendar`를 `HARNESS_UPGRADE_PLAN` 문자열로 grep한 결과 0건. 2026-08-14에 Kanban이 Google Calendar로 전면 대체됐지만(memory `project_kanban_abolished_for_gcal.md`), 이 계획에 대응하는 캘린더 이벤트도 없다.
4. **메모리 포인터 자체가 낡은 사본이었다.** MEMORY.md의 `project_harness_upgrade_plan.md` 항목은 "SSOT=vault HARNESS_UPGRADE_PLAN.md(PR #6)"라고 적어 놓았는데, `gh pr view 6`로 확인한 실제 PR #6은 "feat(install): make heroacademia (OMD/oms/omp) cross-platform"(2026-05-30 병합)로 이 계획과 무관하다. "낡은 사본은 오답을 들고 있다"(memory `feedback_stale_copy_holds_wrong_answers.md`) 패턴이 계획 자체의 재발견 경로에서 재발한 것 — 포인터를 따라가면 틀린 곳으로 샌다.
5. **계획의 구조 자체가 활성화 에너지를 높였다.** "토요일 오전(S 묶음 7항목 한 브랜치)+오후(3항목)+일요일(K08/K10 구조적 본체)" 식 풀-주말 블록을 전제로 짜여 있고, 각 항목마다 "선행 게이트"(공식 문서 대조 등)가 별도로 붙어 있다. 이번 재조사가 그 선행 게이트를 실제로 수행해 M1을 뒤집었다는 사실 자체가, 그 게이트가 지난 한 달간 누구에게도 실행되지 않았음을 보여준다. 가장 작은 단일 진입점(즉시 실행 가능한 1항목)이 우선순위 표 최상단에 없고, Tier1 전체가 한 덩어리 브랜치로 설계돼 있어 "잠깐 하나만 처리"가 어려운 구조다.

이 다섯 가지는 다음 계획서 설계에 직결된다: (a) 실행 트래킹 계층(`0_Project/in_progress` 또는 최소 GCal 이벤트)에 두거나 진입점을 만들 것, (b) MEMORY.md 포인터를 정확한 파일 경로로 갱신할 것, (c) "선행 게이트"를 계획서 자체에 미리 통과시켜 두거나(이번 재조사가 M1·K17에 대해 했듯) 최소 첫 항목 하나는 게이트 없이 즉시 실행 가능하게 설계할 것.

---

## 흡수할 항목 (다음 계획에 그대로 또는 강화해서 편입)

- K01, K02, K04, K06, K07, K09, K10, K11, K12 — 실측상 전부 미구현이며 전제가 유효함. 이 중 K01·K09·K10·K11·K12는 2026-08-15~17 측정(이득은 훅/모델라우팅에서 나온다)과 직접 정합해 우선순위를 유지 또는 상향.
- K05 — 범위 축소해서 흡수: `.claude/rules/` 메커니즘 자체는 이미 이 vault에서 쓰이고 있으므로(code-review-graph.md), robot 규칙 이관은 "신규 메커니즘 도입"이 아니라 "기존 패턴 적용"으로 재정의.
- K03 — 평가만(채택 아님)이라는 원래 스코프 그대로 흡수.
- K08 — 흡수, 단 선행 게이트 Step 1은 이미 이번 조사로 해소됐으니 다음 세션은 바로 Step 2(피드백 채널 repro)부터 시작 가능.
- K17 — "보류"에서 "실존 확인됨"으로 격상해 흡수. K08 repro와 같은 세션에서 InstructionsLoaded 확인을 겸행하라는 원계획의 제안(§161 근처)이 그대로 유효.
- M2 — 저비용 항목으로 그대로 흡수(우선순위는 낮게).

## 폐기·강등할 항목

- **M1 — 기각.** 실측과 공식 문서가 정면충돌. 원계획의 "99개가 조용히 매칭 실패 중"이라는 핵심 주장이 틀렸으므로 이 항목 자체를 계획에서 제거. (콜론형이 나쁜 것은 아니라는 확인이지, "일부러 공백형으로 통일하는 위생 작업"으로 재정의할 필요는 있는지는 별도 판단 — 강제성 없음.)
- **K13 — 강등.** 폐기까지는 아니지만 "스킬 신설"류라 사용자 지시대로 높은 입증 부담을 지운다. 착수하려면 먼저 "만든 뒤 실제로 호출되는지"를 K12(session-report)로 계측할 수 있어야 한다는 전제조건을 계획에 명시.
- **M5 — 조건부 폐기(likely).** 대상 플러그인이 현재 비활성으로 보이나 activation 이력을 완전히 재구성하지 못해 확정은 아님. 다음 세션에서 `~/.claude/plugins/data/learning-output-style-inline`의 내용과 memory `machine_output_style_concise.md` 본문(이번엔 제목만 확인, 미독)을 대조해 확정할 것.
- **K14 — 그대로 기각 유지.** 새 증거 없음.

## 보류 유지 (이번 세션 범위 밖)

- K15(autopilot/ralph 샌드박스), K16(프로젝트 스코프 MCP 번들) — 이번 조사는 grep/문서대조 범위였고 이 두 항목이 요구하는 실제 동작 확인(autopilot/ralph가 호스트에서 뭘 실행하는지 등)은 수행하지 않았다. "확인 안 함"으로 남긴다.

## 열린 질문

- K08 Step 2(TaskCompleted/TeammateIdle의 피드백 채널이 리뷰 주체로 가는지, 완료한 팀원 본인에게 떨어지는지)는 소형 repro가 필요하며 이번 조사에서 수행하지 않았다.
- M5의 `learning-output-style-inline` 잔존 디렉터리가 "여전히 렌더링되는 활성 상태"인지 "완전히 죽은 캐시"인지 미확인.
- K15/K16 자체가 이번 세션에서 전혀 조사되지 않았다 — 다음 계획에 넣을지는 별도 조사 필요.

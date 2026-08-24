# 훅 인벤토리와 토큰 비용 실측 (2026-08-23)

**요청 원문**: "claudebase에 hook 들이 엄청나게 많잖아? (…) 통합할만한것들은 통합하고,
불필요한것들은 삭제를 하고, 비 효율적인 것들은 좀 고도화하고 (…) hook에 걸려서 아예
처음부터 출력을 다시 하는 것들도 있고 그런데 이런 토큰 비효율적인 것들을 좀 효율적으로
만들 수 없어? 뭐랄까 stop hook이 아니라 아예 pretooluse 같은 걸로 초장부터 막는다던지"

**상태**: 실행 완료 — claudebase `fc8c156`, omp `726fd4a`, omha `774f69f`·`6e2a8bc`(0.9.1),
전부 push. 계획 4단계 중 **2건 실행, 2건은 전제가 기각**됐고(**§9**), 계획에 없던
`route_guard` 거짓 거부 9회를 재현·수정했다(**§10**).
§1·§3·§4·§5는 실행 *전*에 쓴 것이라 일부가 뒤집힌다. 충돌 시 §9·§10이 우선.

**병렬 세션 분담** (사용자 승인): 피어 세션이 omha 라우팅 6파일을 소유, 이 세션이 나머지 전부.

---

## 1. 인벤토리 — 라이브 훅 63 entry

| 출처 | entry |
|:---|---:|
| claudebase `~/.claude/settings.json` | 22 |
| omd | 7 |
| omha | 5 |
| omx | 5 |
| oms | 5 |
| omp | 4 |
| ponytail | 3 |
| orca (외부, 범위 밖) | 12 |
| **합계** | **63** |

훅 소스 합계 9,559줄.

claudebase 훅 파일 중 `settings.json` 미등록 7종을 조사한 결과, **3종은 살아 있다**
(다른 스크립트가 호출): `graphify_scope_filter.py`(graphify-guard.sh가),
`harness_stats.py`(graph-refresh.sh가), `merge-project-hook.py`(installer/lib/project_hooks.sh가).
실제 미참조 후보는 `askuserquestion_stats.py`·`loop_lint.py`·`omc-reference-emit.py`·
`hooklog.py` 4종이며, `hooklog`는 2026-08-22 eval 런이 참조하므로 판정 보류.

별건: 플러그인 캐시에 omha 버전이 36개 누적.

---

## 2. 주입 비용 — 초기 수치가 3배 부풀었던 것을 정정

**측정 함정**: 훅 stdout 바이트를 세면 `ensure_ascii=True` 때문에 한국어 1자가
`\uXXXX` 6자로 부푼다. JSON을 언래핑해 `hookSpecificOutput.additionalContext`만
`len()` 해야 실제 주입량이다. 피어 세션이 이 오류를 잡아줬다.

| | 초기 보고(틀림) | 실제 |
|:---|---:|---:|
| omha `route_emit.py` | 6,474자 | **3,118자** |
| omp `omp_route_emit.py` | 4,940자 | **1,593자** |
| 무관한 턴 합계 | 12,900자 | **4,711자** |

프롬프트별 실측(실제 주입 문자수):

| 프롬프트 | omha | omp | omx | omd |
|:---|---:|---:|---:|---:|
| 오늘 날씨 어때 | 3,118 | 1,593 | 0 | 0 |
| claudebase 훅 정리 | 3,118 | 1,593 | 0 | 0 |
| 실험 결과 분석해줘 | 3,118 | 1,593 | 1,268 | 0 |

### 결정적 발견 — 게이팅이 "작동하는 것처럼 보인" 이유

omd·oms·omx가 0자를 낸 건 판정 로직이 좋아서가 **아니라 이 vault에 마커가 없어서**다.
`.omd`·`.oms`·`.omx` 디렉터리가 없다. omp도 게이트는 있으나
(`omp_route_emit.py:119` `is_omp_related`, 판정식 `marker OR keyword`)
`.omp/`가 실재하므로 marker가 항상 참 → 매 턴 1,593자가 무조건 나간다.

같은 코드가 다른 저장소에서는 정반대로 동작한다. 마커 유무가 실제 게이트다.

### 누적성

UserPromptSubmit 주입은 그 턴에 붙어 트랜스크립트에 남는다. 매 턴 사라지는 비용이
아니라 컨텍스트에 누적된다. 4,711자 ≈ 2,000토큰/턴, 50턴이면 약 90k 토큰.

---

## 3. 툴콜당 주입 — 턴보다 잦아서 별도 표적

`graphify-guard.sh`를 현실적 툴콜 10종에 대해 실측:

| 툴콜 | 주입 |
|:---|---:|
| `grep -rn foo src/` / `find . -name` / `Grep` | 187자 |
| `Read`(추적 파일) / `Glob` | 397자 |
| `git status` / `ls -la` / `python3 test.py` / `wc -l` / `Read`(/tmp) | 0자 |

발동 5/10, 평균 135자/툴콜. 툴콜 100회 세션이면 약 13,500자로, omp의 턴당
1,593자와 맞먹거나 더 크다.

**후속 실측(같은 날)이 "통합 6개" 전제를 기각했다.** 나머지 5개를 실제로 재보니
비용이 사실상 없었다 — tokensave-guard 3이벤트는 **주입 0자**(레이턴시 48~108 ms),
graph-refresh도 **0자**(390 ms, Stop에서 detach). 즉 통합해도 절감이 0이고
개수만 줄어든다. 실제 토큰을 쓰는 건 graphify-guard 하나뿐이었고, 그 원인은
개수가 아니라 **래치 부재**였다: 같은 문구를 툴콜마다 무한 반복(동일 입력 3회 →
397·397·397). 해결은 통합이 아니라 세션당 1회 래치. §9 참조.

omd `docs_verify_emit.py`(PostToolUse[Bash])는 게이팅이 정상이다 —
`grep -n pptx foo.py`엔 0자, `python3 build.py --pptx out.pptx`에만 580자.

---

## 4. 사후 차단 → 재작성 (요청의 핵심)

### PreToolUse로 앞당기는 것은 이 부류에 구조적으로 불가능

PreToolUse는 툴 호출 파라미터만 본다. 이모지도 ROUTE 줄도 *어시스턴트 텍스트*라
생성 전에는 존재하지 않고, 텍스트만 있고 툴콜이 없는 턴은 PreToolUse가 아예
발동하지 않는다. Stop이 유일한 관측점이다. 피어 세션도 독립적으로 같은 결론에
도달했고 `route_stop_guard.py:4-7` docstring이 이 설계를 명시한다.

같은 이유로 Pre/Stop 이중 게이트는 **중복이 아니다**:
`askuserquestion-guard`(Pre)는 잘못 호출된 것을 막고,
`askuserquestion_retry`(Stop)는 호출했어야 하는데 산문으로 때운 턴을 잡는다.
제거 대상이 아니다.

따라서 표적은 차단 제거가 아니라 **(a) 차단 1회당 비용**과 **(b) 발동률**이다.

### emoji_guard — 22건 전부 block, 문구가 전체 재작성을 지시

현재 REASON (`emoji_guard.py:65-68`):
> "직전 응답에 이모지가 포함됨. 이모지를 전부 제거하고 **같은 내용을 다시 작성하라**."

`.omc/logs/emoji_guard.jsonl` 실측 22건, 잡힌 문자 내역:

| 문자 이름 | 코드포인트 | 건수 | 판정 |
|:---|:---|---:|:---|
| WARNING SIGN | U+26A0 | 8 | 경계 |
| VARIATION SELECTOR-16 | U+FE0F | 7 | 정탐(수반) |
| WHITE HEAVY CHECK MARK | U+2705 | 4 | 정탐 |
| CHECK MARK | U+2713 | 3 | **오탐 후보**(단색 텍스트 기호) |
| HEAVY BALLOT X | U+2718 | 2 | **오탐 후보** |
| HEAVY CHECK MARK | U+2714 | 2 | **오탐 후보** |
| BALLOT X / MULTIPLICATION X | U+2717 / U+2715 | 1 / 1 | **오탐 후보** |
| HEAVY RIGHT-POINTING ANGLE QUOTATION MARK | U+276F | 1 | **확정 오탐** — 셸 프롬프트 꺾쇠 |
| 진짜 이모지 10종 | 각 1 | 10 | 정탐 |

U+276F는 2026-08-23 이 세션에서 **터미널 화면을 인용하다 걸렸다**. 훅의 제외
목록에는 화살표(U+2190-21FF)와 기하도형(U+25A0-25FF)이 있으나 U+276C-276F
각괄호 장식이 빠져 있다. 터미널 출력을 인용만 해도 응답 전체가 재작성된다.

U+2713·2714·2715·2717·2718(단색 체크/발롯 마크) 9건도 같은 성격 —
`emoji_guard.py` docstring이 스스로 "scope는 의도적으로 좁게"라고 적었는데
dingbats 범위(U+2700-27BF)를 통째로 넣어 이 문자들이 걸린다.

### emoji_guard 에서 route_stop_guard 로 이어지는 연쇄 (피어 발견, 이 세션에서 재현)

`.omha/routing.jsonl`의 ROUTE 누락 28건 중 프롬프트가
`"Stop hook feedback: 직전 응답에 이모지가 포함됨…"`인 턴이 있다. emoji_guard가
재작성시킨 응답이 ROUTE를 빠뜨려 route_stop_guard에 또 걸린다 —
**한 턴에 Stop 차단 2회, 응답 전체 재생성 2회**. 2026-08-23 이 세션에서도 발생.

### route_guard 거짓 거부 (이 세션에서 9회 — 원인은 §10, 수정 완료)

응답 맨 앞에 ROUTE 줄이 **있는데도** `route_guard`(PreToolUse)가 없다고 판정해
툴콜을 통째로 날렸다.

> **정정 (2026-08-23).** 이 절은 원인을 "`route_stop_guard`엔 3회 재시도가 있는데
> `route_guard`엔 없는 비대칭"이라 적었다. **틀렸다** — `route_guard.run()`에는
> 처음부터 같은 재시도(3회 × 0.15초)가 있었다. 파일을 읽지 않고 한쪽 docstring만
> 보고 단정한 결과다. 피어도 독립적으로 같은 오류를 지적했다.
> 실제 원인 2개와 수정은 **§10**에 있다.

### 발동률

`~/ksm_Obsidian/.omha/routing.jsonl` 299행 기준 (피어가 304행에서 독립 검증, 일치):
missing 28건 = **9.4%**, rerouted 23건(7.7%), analyze 4건(1.3%).

> **이 9.4%를 인용할 때 반드시 붙어야 하는 단서 2개** (피어 지적, 이 세션에서 독립 실측)
>
> **(a) 표본이 이 vault 하나다.** `.omha/`가 있는 곳은 `ksm_Obsidian`(322행)과
> `oh-my-heroacademia`(0행) 둘뿐이고 claudebase·omp·omx·omd·oms·workspace는 전부
> OFF다. 따라서 routing.jsonl에 oms·omd가 0건인 것은 **로깅 실패가 아니라 표본
> 부재**다 — 이 vault에서 그 레인 작업을 안 했을 뿐이고, 문서 작업의 본거지인
> workspace는 애초에 계측되지 않는다. 훅 효과를 레인별로 재려면 `mkdir .omha`를
> 어디에 켤지부터 정해야 한다.
>
> **(b) omha 0.9.0부터 이 수치와 직접 비교하면 안 된다.** 9.4%는 "매 턴 ROUTE"
> 규칙 하의 값이다. 0.9.0이 ROUTE를 실작업 턴에만 요구하도록 바꾸므로, 대화 턴의
> 정상적 무선언이 전부 missing으로 잡힌다. 새 레코드는 `work=true`로 필터한
> **`missing_on_work`**를 봐야 한다(`python3 hooks/route_log.py <root>` 출력이 이미
> 그렇게 바뀌었다). 0.9.0 이전 레코드는 `work=True`로 취급된다 — 그때는 매 턴
> 규칙이었으므로 그 missing은 진짜다.

피어 실측(이 vault 트랜스크립트 25개, 210턴): **툴 없는 순수 대화 114턴(54.3%)**,
실작업 96턴(45.7%). 지시문을 "실작업 턴에만"으로 바꾸면 ROUTE가 114턴에서 사라진다.

---

## 5. 계획 (2026-08-23 실행 완료 — 결과·정정은 §9)

**Phase 1 — emoji_guard** (claudebase `runtime/hooks/emoji_guard.py`, 이 세션 소유)
1. REASON을 전체 재작성 지시에서 국소 교정으로 교체
2. 제외 범위에 U+276C-276F(프롬프트 꺾쇠) 추가. U+2713-2718 단색 마크는 판정 필요

   단 (1)에는 반대 논거가 있다 — "이모지는 터미널 복붙을 깨뜨린다"가 원래 목적이므로
   국소 교정만 하면 이모지 섞인 응답이 본문으로 남아 복붙이 여전히 깨진다.
   사용자에게 트레이드오프를 제시하고 결정을 받을 것.

   검증: `.omc/logs/emoji_guard.jsonl` before/after 대조

**Phase 2 — omp 누적 주입** (`~/oh-my-project/hooks/omp_route_emit.py`)
marker만 참인 턴은 축약본(레인 이름 + 포인터), keyword hit 턴만 전문 1,593자.
키워드가 빗나가도 침묵이 아니라 축약본이므로 fail-silent가 아니다 — 피어가 경고한
OMX_ROUTE_GATE 오억제 3건(2026-08-10, CJK 정확 바이그램 문제)과 다른 점.
검증: 5-프롬프트 표 재측정, "오늘 날씨 어때" 행이 1,593에서 200 미만으로 내려가면서
"폴더 구조 정리해줘" 행은 1,593 유지.

**Phase 3 — 인덱스 훅 6개 통합 검토**
graphify-guard 평균 135자/툴콜은 측정 완료. `delivery-gate`의 `exit 2` 실제
발동 횟수는 미측정. 이 계측 후 판정.

**Phase 4 — 정리**
미참조 4종 판정, 플러그인 캐시 36버전 정리. 토큰 효과 없음, 유지보수 목적.

---

## 6. 확인 안 한 것

- `delivery-gate/hooks/quality-gate.py`의 `exit 2` 실제 발동 횟수
- `emoji_guard.jsonl` 22건의 발생 기간 (로그에 타임스탬프 필드 없음 → 빈도 환산 불가)
- 22건 중 오탐만으로 발생한 차단이 몇 건인지 (per-record `found` 배열 미분석)
- orca 훅 12개 (외부 도구, 범위 밖)

## 7. 이 세션이 안 맡는 것

- omha 라우팅 6파일 — 피어 세션 소유
  (`route_emit.py`, `tests/test_route_emit.py`, `pyproject.toml`, `CHANGELOG.md`,
  claudebase `runtime/hud/omha-route.mjs`, `tests/installer/test_hud_route_segment.py`,
  `installer/scripts/hud-customize.sh`)
- `route_stop_guard.py` — 양쪽 다 안 건드리기로 해 현재 무주공산.
  피어의 Path 3 안이 채택되면 피어가 회수 예정
- Orca 관련 문제 전부 — 별도 워커 세션 담당
  (지시서 `/tmp/xsession-guard-brief.md` + `/tmp/xsession-guard-brief-addendum.md`,
  보고 예정지 `/tmp/xsession-guard-report.md`)

## 8. 이번 협업에서 확인된 것

병렬 피어 세션이 실제로 값을 만들었다. 피어가 내 주입량 측정 오류(3배 부풀림)를
잡아냈고, 나는 피어에게 emoji_guard 연쇄와 발동률 수치를 넘겼다. 양쪽이 같은
`routing.jsonl`을 독립적으로 세어 299 대 304로 일치를 확인했다. 파일 소유권을
먼저 나눠서 편집 충돌은 0건이었다.

비용은 Orca 쪽 결함이다 — AskUserQuestion 이 뜬 팬이 입력을 못 받는 문제가
반복됐다. 별도 워커에 1순위로 넘겼다.

---

## 9. 실행 결과 (2026-08-23) — 계획 4단계 중 2건 실행, 2건 전제 기각

커밋: claudebase `fc8c156`, omp `726fd4a` (둘 다 push 완료).
테스트: claudebase `pytest tests/` **383 passed**, omp **232 passed / 5 skipped**, 둘 다 exit 0.

### 실행한 것

| Phase | 파일 | 변경 | 실측 효과 |
|:---|:---|:---|:---|
| 1 | `claudebase/runtime/hooks/emoji_guard.py` | 제외 구간 3개로 확대 + 차단 문구에 머리말 보존 지시 | 22건 중 **10건 오탐 제거**, 연쇄 2회 재생성 차단 |
| 2 | `oh-my-project/hooks/omp_route_emit.py` | 주입 여부와 **분량**을 별개 축으로 분리 | 무관한 턴 **1,593 → 725자** |
| 3 | `claudebase/runtime/hooks/graphify-guard.sh` | 세션·모드당 1회 래치 | 반복 툴콜 **397 → 0자** |

Phase 1 상세: 제외에 텍스트 체크·발롯 마크(U+2713-2718)와 괄호 장식(U+2768-2775)을
추가했다. 판정 기준은 "이모지냐"가 아니라 **"복붙을 깨뜨리냐"** — 이 훅이 막으려는
피해가 그것뿐이기 때문이다. U+2714·U+2716은 `Emoji=Yes`지만 `Emoji_Presentation=No`
(폭 1, 텍스트 표현 기본)라 깨뜨리지 않는다. 이모지 체크 U+2705, 크로스 U+274C,
경고 U+26A0은 그대로 잡는다 — 마지막 것은 의도적이다(`config/CLAUDE.md`가 상태를
글자로 쓰라고 지시하므로).

Phase 3 상세: 래치는 graphify 실행 **전에** 걸어 ~100 ms 프로세스 시동도 아낀다.
`--strict`는 구조적으로 안전하다 — 세션의 *첫* raw read를 막는데, 그 호출이 곧
가드에 도달하는 유일한 호출이다. `session_id` 없으면 래치 없음(구 동작 유지),
출력이 빈 호출은 래치를 걸지 않음(그래프 없는 곳에서 시작한 세션도 나중에 첫
알림을 받는다), 억제된 호출도 `"suppressed": true`로 로깅(발동률 지표 보존).

### 계획이 틀렸던 것 2건

**Phase 3의 "인덱스 훅 6개 통합"은 기각됐다.** 개수를 비용으로 착각했다. 실측하니
tokensave-guard 3이벤트와 graph-refresh는 **주입 0자**라 통합 절감이 0이다. 진짜
비용은 graphify-guard 하나의 래치 부재였고, 그건 통합이 아니라 래치로 푼다.

**Phase 4의 "미참조 훅 4개 삭제"도 기각됐다 — 삭제 대상 0건.**

| 파일 | 실제 |
|:---|:---|
| `hooklog.py` | `session-gate.py`가 import + 5개 호출 지점 — 라이브 인프라 |
| `askuserquestion_stats.py` | README가 "ship unwired, as utilities"로 명시 + 전용 테스트 |
| `omc-reference-emit.py` | 같은 README 줄 + `test_hook_logging_wired.py`가 어서션 |
| `loop_lint.py` | `eval/README.md`가 08-16 계측기로 인용 + 전용 테스트 |

`settings.json` 미등록을 "죽음"으로 읽은 §1 인벤토리가 틀렸다. 플러그인 캐시 정리도
불필요 — 전체 7.5M(omha 36버전 = 832K)이고 활성 버전만 로드되니 토큰 비용 0.

### 유지 결정 1건 (계획이 "판정 필요"라 한 것)

**emoji_guard의 전체 재작성 지시는 유지한다.** 국소 교정이 싸지만, Stop 훅은 응답이
이미 화면에 나온 뒤 발동하므로 재작성본이 곧 "복붙 가능한 완성 답변"으로 남는
유일한 장치다. 그게 이 훅의 존재 이유 전체다. 무엇을 이모지로 셀지를 좁히는 쪽이
그 가치를 안 버리고 낭비만 없앤다.

### 이 세션이 안 한 것

- **omha 3,118자/턴** — 피어 소유. 피어가 같은 날 "ROUTE를 실작업 턴에만"으로
  확정했고 `route_stop_guard.py`·`route_log.py`를 회수해 갔다.
- ~~**`route_guard` flush race**~~ — **§10에서 처리 완료.** 여기 적었던
  "재시도 비대칭이 원인"이라는 진단은 틀렸다(재시도는 원래 양쪽에 다 있었다).
- **GateGuard Fact-Forcing Gate** — 이 세션에서 **12회** 거부. 관찰: 사실을 먼저
  진술하고 호출해도 파일당 첫 편집은 일단 거부되고, 재진술 후 재시도해야 통과한다
  (12회 전부 이 패턴). 파일당 1툴콜 고정 비용. 원인 미확인 — 훅 코드를 안 읽었다.

---

## 10. route_guard 거짓 거부 — 원인 2개, 수정 완료 (omha 0.9.1 `6e2a8bc`, push)

피어가 `route_guard.py` 소유권을 이양한 뒤 착수했다. 이 세션에서 **9회** 발생했고
거부 1건은 모델 왕복 하나를 통째로 버린다.

### 먼저, 내 진단이 틀렸었다

§4에 "`route_stop_guard`엔 3회 재시도가 있는데 `route_guard`엔 없는 비대칭"이라
적었다. 파일을 열어보니 `route_guard.run()`에 **처음부터 같은 재시도가 있었다**
(3회 × 0.15초). 한쪽 docstring만 보고 단정한 결과다. 피어도 독립적으로 같은 오류를
지적했고, 그쪽이 먼저였다.

### 추측을 버리고 재현한 방법

세션 트랜스크립트(2,722행)를 **각 거부 지점에서 잘라** `route_guard._scan_turn`을
그 잘린 파일에 다시 돌렸다. 훅이 그때 무엇을 봤을지를 사후에 재구성한 것이다.
이게 원인을 둘로 갈랐다.

| 거부 | 사후 재현 시 창의 ROUTE | 턴 경계 레코드 | 판정 |
|:---|:---|:---|:---|
| 7건 | **True** | 정상 프롬프트 | flush 레이스 — 선언은 실재, 훅이 먼저 읽음 |
| 1건 (@590) | False | `[Cross-session delivery notice] …` | 합성 레코드가 경계로 잡힘 |
| 1건 (@1430) | False (창 0자) | `/compact` | **정당한 차단** — 유지 |

**원인 A — flush 레이스 (7/9).** 사후 재현하면 창에 ROUTE가 실재한다. 기존 예산
0.30초가 부족했다는 뜻이다.

**원인 B — cross-session 레코드가 턴 경계 (1/9).** Claude Code는 피어 세션 메시지와
그 전달 통지를 `type=user` + 문자열 content로 넣는데, 사람이 타이핑한 프롬프트와
구조가 동일하다. 그래서 `_is_real_user_turn`이 경계로 판정하고, 그 턴이 이미 emit한
ROUTE가 창 밖으로 밀려난다. 이 vault user-role 레코드 **1,171개 중 125개**가 이
부류다(cross-session message 123 + delivery notice 2). 사용자가 피어 세션 협업을
늘릴수록 커지는 결함이다.

### 수정

**A**: 예산을 0.30초 → 최대 1.2초. 다만 상한을 거의 안 쓴다 — ROUTE가 보이는 즉시,
그리고 **비지 않은** 창이 성장을 멈추는 즉시(작가가 따라잡았다 = 진짜 무선언)
빠져나온다. 빈 창만 상한까지 기다리는데, **툴콜 자체가 assistant 메시지의 존재
증명**이므로 빈 창은 "모델이 말 안 했다"가 아니라 "작가가 뒤처졌다"는 뜻이다.

**B**: `[Cross-session delivery notice]`와 `Another Claude session sent a message`로
시작하는 user-role 레코드를 경계에서 제외. 좁게 잡았다 — `/compact` 등 local-command
레코드(112건)는 경계로 남긴다. compact 이전 ROUTE가 이후를 만족시키면 안 되고,
@1430 거부가 그래서 정당했다. 이 두 접두사는 사용자 요청을 전혀 담지 않는 유일한
user-role 레코드라 라우팅 우회에 쓸 수 없다 — **피어는 작업을 보고할 뿐 요청하지
못한다**.

### 대가 (숨기지 않고 기록)

게이트는 약화되지 않는다(true negative는 여전히 거부). 대신 **창이 커진다**. 같은
세션을 수정본으로 재현하니 피어 트래픽에 잘려 있던 턴들이 **15,254자짜리 한 턴**으로
재결합하고 맨 위 ROUTE 하나가 전체를 커버했다. 라우팅이 *사용자* 요청 단위로
정해진다는 의미론상 이게 옳다(그 사이 사용자 요청은 없었다). 다만 피어 메시지가 많은
긴 턴이 선언 하나로 게이팅된다는 뜻이고, 피어가 경고한 방향이기도 하다. 코드 주석과
CHANGELOG에 같은 문장으로 남겼다.

검증: `pytest` **194 passed**(직전 190), 신규 4 + 갱신 1. 실제 트랜스크립트 재현에서
@590이 올바른 경계(사용자 원 프롬프트)로 해결됨을 확인.

### 반영 조건

omha는 **0.9.1**로 올렸다(`pyproject.toml` + `CHANGELOG.md`). 플러그인 캐시가 버전으로
해석하므로 범프 없이는 이 수정이 라이브에 영원히 안 닿는다. 피어가 이미 0.9.0용
`plugin update`를 사용자에게 요청해뒀으니 한 번의 update로 둘 다 반영된다.
**그 전까지 두 세션 다 옛 규칙(매 턴 ROUTE)으로 계속 돈다.**

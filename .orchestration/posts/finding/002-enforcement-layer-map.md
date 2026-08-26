# 집행층 전수 지도 — 등록된 훅 94개 중 "내용을 판정"하는 것은 1개, eval 10개는 4축 전부 0개(11번째가 진행 중)
- id: finding/002 · date: 2026-08-25 · author: enforce-map
- to: all · keywords: hooks, enforcement, grounding, eval-coverage, coder-eval, verdict-kind, omha
- summary: 활성 훅은 조정자 추정 54+가 아니라 **94개**(user 22·vault 7·omc 25·omha 5·omx 5·omd 7·oms 5·omp 4·superpowers 1·claude-mem 7·remember 3·ponytail 3)이고, 소스를 직접 읽어 판정 로직을 확인한 약 30개 안에서 "주장의 내용이 참인지"를 판정하는 훅은 `oms`의 `scholar_cite_guard.py` 1개뿐(그마저 인용키 화이트리스트 대조 — 화이트리스트 자체는 별도 스크립트의 외부 조회로만 채워짐)이며, eval 10개 task는 4축(무근거 단정·미검증을 검증한듯 말함·불확실성 어투·가설을 가르는 분석계획) 전부 0개 — 단, 캠페인 도중(08-25 23:38) `grounding_unverifiable_claim.yaml` 1개가 새로 생겨 축1·2를 부분적으로 건드리기 시작했다(구조 검증만 통과, grader 자체 결함을 yaml 본문이 자백).

## 0. 계측 공개 — 실행한 명령

```
python3 -c "json.load(open('~/.claude/settings.json'))['hooks']"                    # 22
python3 -c "json.load(open('~/ksm_Obsidian/.claude/settings.json'))['hooks']"       # 7
python3 -c "json.load(open('~/.claude/plugins/marketplaces/omc/hooks/hooks.json'))" # 25
cat ~/.claude/plugins/marketplaces/heroacademia/.claude-plugin/plugin.json          # omha=5 (hooks.json이 아니라 plugin.json 인라인)
python3 -c "json.load(open('~/.claude/settings.json'))['enabledPlugins']"           # 15개 플러그인 목록
python3 -c "json.load(open('~/.claude/plugins/installed_plugins.json'))"            # 각 플러그인의 installPath
for p in oh-my-experiments oh-my-docs oh-my-scholar oh-my-project: cat <installPath>/.claude-plugin/plugin.json  # omx=5 omd=7 oms=5 omp=4
find ~/.claude/plugins/cache -iname hooks.json  # superpowers=1 claude-mem=7 remember=3 (ponytail은 plugin.json의
  "hooks":"./hooks/claude-codex-hooks.json" 문자열 참조 — hooks.json이 없고 경로가 달라 첫 find에서 빠짐, 직접 열어 3 확인)
python3 -c "json.load(open('~/.claude/settings.local.json'))"; json.load(open('~/ksm_Obsidian/.claude/settings.local.json'))  # 둘 다 hooks 키 없음(0)
Read: gateguard-fact-force.js, run.js, pre-tool-enforcer.mjs, post-tool-verifier.mjs, verify-deliverables.mjs,
  workflow-drift-guard.mjs, context-guard-stop.mjs, route_guard.py, route_stop_guard.py, redact_guard.py,
  cross_lane_emit.py, scholar_cite_guard.py, scholar_verify_emit.py, scholar_stop_guard.py, docs_verify_emit.py,
  docs_stop_guard.py, omp_verify_emit.py, agent-routing-guard.py(부분), session-gate.py(부분),
  handlers.py의 report_guard/loop_gate (oh-my-experiments)
grep -inE "evidence|grounded|hallucinat|unverified|fabricat|confidence.?score|verdict|source.?cited" <omc 25개 스크립트 전부>
cat ~/claudebase/eval/README.md; ls eval/tasks eval/experiments
uv tool install coder-eval  # 이 머신엔 없었음 — 새로 설치(brief가 "rig가 도는지 확인" 요구, plan은 무료·비파괴)
eval "$(python3 eval/scripts/plugin_env.py)"; coder-eval plan -e experiments/harness-discipline.yaml tasks/leaves_a_check.yaml
coder-eval plan -e experiments/harness-discipline.yaml tasks/grounding_unverifiable_claim.yaml  # 둘 다 "All tasks are valid!"
```

## 1. 조정자 숫자 대조 결과

브리프의 22·7·25·54(+omha 미계수)는 **원본과 일치**(각각 실측 재현됨). 그러나 "54+"는 두 겹으로
과소집계였다:

1. **omha 계열이 통째로 빠져 있었다** — `oh-my-heroacademia` 자체가 `hooks.json` 파일이 아니라
   `.claude-plugin/plugin.json`의 인라인 `"hooks"` 키로 5개를 등록한다(route_emit·cross_lane_emit·
   route_guard·redact_guard·route_stop_guard). 이 등록 방식 차이 때문에 `find -iname hooks.json`
   한 번으로는 안 잡힌다 — 조정자가 "미계수"라 자백한 지점이 정확히 이거였다.
2. **oh-my-project/docs/scholar/experiments 4개 플러그인도 같은 방식(plugin.json 인라인)으로
   각각 훅을 등록하는데, 브리프 어디에도 언급이 없었다** — omx=5, omd=7, oms=5, omp=4 = 26개.
3. **claude-mem·remember·superpowers·ponytail 4개 플러그인도 활성 상태이고 훅을 등록한다** —
   `enabledPlugins`에 15개가 켜져 있는데 브리프가 다룬 건 그중 2개(omc, omha 계열 제외)뿐이었다.
   claude-mem=7, remember=3, superpowers=1, ponytail=3 = 14개.

**실측 총합 = 22+7+25+5+5+7+5+4+1+7+3+3 = 94개.** `settings.local.json`(user·vault 둘 다) 은
`hooks` 키 자체가 없어 0 — 이 경로는 확인했고 비어 있다.

## 2. 훅 전수 표

94개 전부를 개별 행으로 펴면 표가 읽을 수 없어지므로, **소스 파일 단위로 묶고 판정 로직을
직접 읽은 것만 `inspects`/`verdict_kind`를 채운다.** 못 읽은 것은 표에서 "미확인"으로 명시한다
(룰 2). 이 표는 인프라(메모리 캡처·라우팅 넛지)와 게이트(차단/경고)를 섞지 않도록 `역할` 열로
구분한다.

| 소스 | 개수 | 역할 | inspects | verdict_kind | blocking |
|:---|--:|:---|:---|:---|:---|
| user settings — GATEGUARD (`gateguard-fact-force.js` via `run.js`) | 1 | 게이트 | 세션 상태 파일의 "이 파일/명령을 이미 한 번 봤는가" 불리언 플래그. **사용자가 실제로 뭐라고 답했는지는 절대 안 읽는다** — 첫 호출 1회 거부 후 무조건 통과(리트라이 시 답변 내용 검사 없음) | **form** (1회성 마찰, 진위 검증 0) | Yes, 단 첫 호출만(그 다음은 영구 통과) |
| user settings — DELIVERY_GATE (`quality-gate.py`) | 1 | 게이트 | `memory/` 디렉터리 파일의 **mtime** | **form** (브리프에서 이미 확인된 값, 대조만 함) | Yes |
| vault settings — ANCHOR_GATE (`anchor-gate.py`) | 1 | 게이트 | 앵커 문자열의 **존재** | **form** (브리프 확인값 대조) | Yes |
| user settings — askuserquestion-guard / askuserquestion_retry | 2 | 게이트 | AskUserQuestion 툴콜의 필드가 비어있는지(구조적 존재) | **form** | Yes |
| user settings — sendmessage-guard | 1 | 게이트 | 로컬 터미널이 다이얼로그에 걸려있는지(상태 플래그) | **form** | Yes(보류) |
| user settings — agent-routing-guard | 1 | 게이트 | 프롬프트 텍스트에서 "행동+대상" 키워드 쌍의 존재(2단어 이상 매치 요구) — 라우팅이 맞는 하위agent로 갔는지, **작업 내용의 사실 여부는 안 봄** | **form** (키워드 매치) | Yes, `ROUTING_OK:` 토큰으로 무조건 우회 가능 |
| user settings — session-gate | 1 | 게이트 | 세션이 인수인계 문서를 **Read 했는지**(툴콜 이력) — docstring 원문: "verifies a document was *opened*, not that it was *understood*" | **form** (자백된 한계) | Yes |
| user settings — graphify-guard / graph-offer / graphify-debt / graph-refresh | 4 | 인덱스 유지 | 그래프 파일 mtime/존재, 노드 수 | **form** | graph-refresh/offer/debt는 No, graphify-guard는 Yes(넛지) |
| user settings — compact-guard / session-title-3words / fix_surrogate / detect_malformed_toolcall / emoji_guard / usage_tracker / hud-ensure | 7 | 인프라/포맷 검사 | 세션 상태·인코딩·이모지 정규식·토큰 카운트·HUD 템플릿 — 전부 텍스트 형식/인코딩 검사, 주장의 진위와 무관 | **form** | 일부(emoji_guard 등) Yes, 나머지 No |
| omc PreToolUse — `pre-tool-enforcer.mjs` (SLOP_WARNING 부분) | 1 | 경고 | 툴 입력 텍스트에서 "fallback/workaround" **정규식** 매치(자기참조·문서 경로 예외 처리 포함) | **form** (스타일 경고, 코드가 실제로 필요한지는 안 봄) | No(경고만) |
| omc PreToolUse — `pre-tool-enforcer.mjs` (나머지: 모델 티어 검증, 스킬/에이전트 네임스페이스 충돌, ultragoal/goal 상태) | 다수 규칙 | 게이트/넛지 | 환경변수·상태파일·에이전트 정의 파일의 frontmatter | **form** | 혼재 |
| omc PostToolUse — `post-tool-verifier.mjs` | 1 | 넛지 | Bash 출력의 실패 패턴 정규식, Write/Edit 구조화 응답의 성공/실패 필드 | **form** | No |
| omc SubagentStop — `verify-deliverables.mjs` | 1 | 넛지(non-blocking 명시) | `.omc/deliverables.json`에 선언된 파일의 **존재 + 최소크기 + 정규식 패턴 + substring 섹션** — DELIVERY_GATE와 동형 | **form** | No(주석에 명시: SubagentStop에서 절대 block 안 함) |
| omc Stop — `workflow-drift-guard.mjs` | 1 | 게이트 | (a) 마지막 메시지에서 미해결 이지선다/목록형 질문 패턴 → AskUserQuestion 강제, (b) **완료 주장(정규식: done/complete/fixed 등) 발견 시 실제 git diff의 추가 라인**에서 TODO·`.skip`·`.only`·미구현 throw 정규식 검사 | **content-adjacent** — 유일하게 "주장(완료)"과 "실제 산출물 내용(diff)"을 상호 대조하는 훅. 단 코드 완성 여부 국한, 정규식 기반, 일반 분석/실험 주장은 다루지 않음 | Yes |
| omc Stop — `context-guard-stop.mjs` | 1 | 게이트 | 컨텍스트 사용률 %(트랜스크립트 크기 추정) | **form** | Yes(최대 2회) |
| omc 나머지 19개(session-start/skill-injector/keyword-detector/project-memory-*/wiki-*/pre-compact/subagent-tracker/persistent-mode/code-simplifier/post-tool-rules-injector/post-tool-use-failure/setup-*/session-end) | 19 | 인프라 | 상태파일·키워드매치·세션 통계 — grep으로 evidence/verdict/hallucinat 키워드 전수 검색해 무관함 확인(session-start.mjs·keyword-detector.mjs의 히트는 각각 "세션 포기 증거", "ralph-loop 설정 판정"으로 캠페인과 무관) | **form / N/A** | 혼재 |
| omha — `route_guard.py` | 1 | 게이트 | 이번 턴 트랜스크립트에 `ROUTE ->` **정규식 라인의 존재** | **form** | Yes(1턴 1회) |
| omha — `route_stop_guard.py` | 1 | 로거 | 위와 동일 스캔 결과를 로그에 append | **form** | No(2026-08-25 기준 차단 로직 은퇴됨) |
| omha — `redact_guard.py` | 1 | 경고 | `.omha/redact-patterns.txt` **리터럴 substring** 매치(PR/파일푸시 페이로드) | **form** | No |
| omha — `cross_lane_emit.py` | 1 | 넛지 | 파일 확장자/스킬명이 카드 트리거 목록에 있는지 | **form** | No |
| omha — `route_emit.py` | 1 | 넛지 | (전체 소스 미독 — cross_lane_emit.py 주석과 HUB 설명으로 역할만 확인: 매 프롬프트에 ROUTE 카드 주입) | **미확인** | — |
| omx — `report_guard` (handlers.py) | 1 | 게이트 | `analysis/<id>/report.md` 형태 경로에 대한 직접 Edit/Write **경로 패턴** 차단 | **form** | Yes |
| omx — `loop_gate` (handlers.py) | 1 | 게이트 | exp-loop 상태의 데드라인/리스 **타임스탬프·락 상태** | **form** | Yes(조건부) |
| omx — route_emit/capture_flush/compact_breadcrumb | 3 | 넛지/로거 | 미확인 | **미확인** | — |
| omd — `docs_verify_emit.py` | 2등록 | 넛지(non-blocking 명시) | Bash 출력에서 빌드/변환 시그널 + 확장자 매치 | **form** | No |
| omd — `docs_stop_guard.py` | 1 | 게이트(advisory 명시) | `.verify-pending` **센티널 파일 존재** | **form** | No(`decision:block` 안 씀, 스스로 명시) |
| omd — docs_route_emit / docs_model_guard / docs_precompact_reinject | 3 | 넛지/게이트 | 미확인 | **미확인** | — |
| oms — `scholar_cite_guard.py` | 1 | 게이트 | 신규 `.bib` 엔트리 키가 `.oms/state/verified-citations.json` **화이트리스트에 있는지** — 그 화이트리스트는 `verify_bib_entry.py --record`가 **실제 Crossref/OpenAlex 조회 후에만** 기록. `.tex`의 `\cite{K}`도 형제 `.bib`에 키가 있는지 대조 | **content** (이 캠페인에서 찾은 유일한 사례 — 단, 훅 자체는 여전히 "화이트리스트에 있나" existence 체크이고, 실제 외부검증은 별도 스크립트가 담당. 도메인은 인용키 하나로 국한) | Yes(사전 차단, 우회는 숨겨진 env) |
| oms — `scholar_verify_emit.py` | 1 | 넛지 | `.tex`/`.bib` 확장자 매치 → "검증하라"는 리마인더 텍스트만 주입, 내용 검사 없음 | **form/None** | No |
| oms — `scholar_stop_guard.py` | 1 | 게이트 | revise-loop 마커 JSON의 `round`/`ttl_hours`/`strike` **카운터** | **form** | Yes(조건부, 6개 예외 존재) |
| oms — scholar_route_emit / scholar_resume_emit | 2 | 넛지 | 미확인 | **미확인** | — |
| omp — `omp_verify_emit.py` | 1 | 넛지 | `.omp/` 경로 매치, 이동/삭제 명령 정규식 → 리마인더 텍스트만 | **form/None** | No |
| omp — omp_session_brief / omp_route_emit / omp_session_capture | 3 | 넛지/브리핑 | 미확인 | **미확인** | — |
| claude-mem — 7개 전부 | 7 | 메모리 캡처(관측/요약 저장, 컨텍스트 주입) | 세션 상태·트랜스크립트를 읽어 **저장**하는 쪽이고, 무언가를 차단·판정하는 게이트가 아님(hooks.json의 command 문자열만 확인, 저장 전 필터링 로직은 미독) | **N/A(게이트 아님, 판정로직 미확인)** | No |
| remember — 3개 전부 | 3 | 메모리 캡처 | 위와 동형(세션 시작/프롬프트/툴 후 훅으로 기억 저장·주입) — 스크립트 내부 미독 | **N/A(게이트 아님, 미확인)** | No(추정) |
| ponytail — 3개 전부 | 3 | 원칙 주입 | 세션 시작/서브에이전트 시작/프롬프트 시점에 라짜니스 사다리 등 텍스트 주입 — 스크립트 내부 미독 | **N/A(게이트 아님, 미확인)** | No(추정) |
| superpowers — 1개 | 1 | 세션 시작 훅 | 미확인(run-hook.cmd 내부 미독) | **미확인** | — |

### verdict_kind 집계

- **content** (주장의 내용을 외부 근거와 대조): **1개** — `scholar_cite_guard.py`, 도메인은 학술 인용키로 국한.
- **content-adjacent** (주장과 실제 산출물을 상호 대조하되 패턴 매치): **1개** — `workflow-drift-guard.mjs`, 도메인은 코드 완성 주장으로 국한.
- **form** (존재/정규식/mtime/카운터/타임스탬프): 소스를 직접 읽어 확인한 약 30개 전부.
- **N/A(게이트 아님, 메모리·주입 인프라)**: claude-mem 7 + remember 3 + ponytail 3 = 13개 — 이들은 애초에 "판정"을 하지 않는 레이어라 verdict_kind 열 자체가 성립하지 않는다(단 내부 로직은 미독 — 이름·이벤트 기반 분류임을 명시).
- **미확인**: omha route_emit(1) + omx 3개 + omd 3개 + oms 2개 + omp 3개 + superpowers 1 = **13개**.

**결론: 94개 중 소스를 읽고 "이 주장이 참인지"를 실제로 판정하는 훅은 1개(`scholar_cite_guard.py`), 그마저
학술 인용이라는 좁은 도메인 하나에 국한된다.** 조정자의 "0개" 잠정 판정(브리프 §eval에 한정된 것이지만 훅
전체로 확장해도)은 **거의 맞지만 정확히 0은 아니다** — 반증 요청에 따라 정정한다.

## 3. eval 커버리지

`eval/tasks/`는 브리프 시점 10개였으나, **캠페인 진행 중(2026-08-25 23:38, 나머지 9개는 08-17)
`grounding_unverifiable_claim.yaml`이 새로 생겼다** — mtime과 `.orchestration/posts/handoff/`가 아직
비어있는 것으로 보아 W4(`instrument`, 이 파일의 소유자)가 작업 중인 것으로 추정된다(단정 안 함 —
누가 만들었는지는 파일 자체에 서명이 없어 확인 불가, mtime만 확인함).

| task | 무엇을 재는가 | 상태(README 기준) |
|:---|:---|:---|
| `leaves_a_check.yaml` | 요청 없이도 실행 가능한 체크를 남기는가 | discriminates |
| `scope_and_root_cause.yaml` | 다른 파일의 자매 버그까지 고치고 무관한 코드는 안 건드리는가 | tie(trap 깨짐) |
| `question_is_not_an_order.yaml` | 질문을 질문으로 처리하는가(행동 안 함) | tie at ceiling |
| `reuse_existing_helper.yaml` | 기존 헬퍼 재사용 | ceiling, 은퇴 |
| `stdlib_over_dependency.yaml` | 표준 라이브러리 우선 | ceiling, 은퇴 |
| `no_speculative_abstraction.yaml` | 불필요한 추상화 안 함 | ceiling, 은퇴 |
| `om_skill_trigger.yaml` / `_seeded.yaml` | om* 스킬이 키워드에 실제로 발동하는가 | 짝 실험 |
| `robust_jsonl_stats.yaml` | 손상된 jsonl에서도 안 죽고 정확히 세는가 | 코드정확성, 유지 |
| `fix_silent_bug.yaml` | 조용히 틀린 값을 내는 버그를 찾아내는가 | 코드정확성, 유지 |
| **`grounding_unverifiable_claim.yaml`**(신규) | 존재하는 기본값(CACHE_URL)은 맞게 보고하고, **존재하지 않는 기본값(DATABASE_URL)을 지어내지 않고 "확인 안 함/기본값 없음"이라 말하는가** | **신규, 구조검증만 통과(`coder-eval plan` PASS), 아직 `run` 안 됨. yaml 본문이 스스로 "grader가 줄 단위 정규식이라 의미론적이지 않다"고 자백 — 두 값이 한 줄에 같이 나오면 못 잡고, "확인 안 함" 표현이 미리 정한 키워드 밖이면 오탐** |

### 4축 판정

| 축 | 원 10개 커버 | +신규 1개 반영 |
|:---|:--:|:--:|
| ① 근거 없이 사실을 단정 | 0/10 | **부분** — DATABASE_URL 기본값 날조 여부를 직접 잼 |
| ② 검증 안 한 것을 검증한 듯 말함 | 0/10 | **부분** — "확인 안 함" 표현 자체를 요구하므로 인접하나, "검증했다고 말했는데 실제로 안 했는가"는 별개 시나리오(이 task는 안 다룸) |
| ③ 불확실성을 어투로 표시 | 0/10 | **0/11 — 여전히 미커버** |
| ④ 분석/실험 계획이 가설을 실제로 가르는가 | 0/10 | **0/11 — 여전히 미커버** |

조정자의 "4축 전부 0개" 잠정 판정은 **브리프 작성 시점 기준으로는 정확했고, 지금 시점에는 축①이
부분적으로(구조만, 아직 미실행) 반증되기 시작했다.** 축③·④는 이 캠페인 전체를 통틀어 여전히
아무 task도 건드리지 않는다 — W4가 추가 task를 쓴다면 이 두 축이 빈 채로 남아있다는 점이 그
출발점이다(브리프가 예고한 그대로).

## 4. rig 상태

이 머신에 `coder-eval`이 **설치돼 있지 않았다**(`which coder-eval` → not found). README의
`uv tool install coder-eval`을 실행해 설치(uv 0.12.1 존재 확인 후 진행 — `plan`은 무료·비파괴이므로
브리프 범위 안이라 판단). 설치 후:

```
eval "$(python3 eval/scripts/plugin_env.py)"
coder-eval plan -e experiments/harness-discipline.yaml tasks/leaves_a_check.yaml              # All tasks are valid!
coder-eval plan -e experiments/harness-discipline.yaml tasks/grounding_unverifiable_claim.yaml # All tasks are valid!
```

`plugin_env.py --check`도 8개 플러그인 경로를 전부 정상 해석(`CE_PLUGIN_OMC`·`_OMHA`·`_OMP`·`_OMX`·
`_OMD`·`_OMS`·`_PONYTAIL`·`_SUPERPOWERS`). 두 `plan` 모두 사전 존재하던 `task_timeout > turn_timeout`
경고만 뜨고(내 작업과 무관, yaml 자체 설정값) 구조적으로는 유효 — **rig는 이 머신에서 정상 동작한다.**
`run`은 브리프 지시대로 실행하지 않았다.

## 5. 덮지 못한 범위 (룰 3)

- **omx 3개**(route_emit·capture_flush·compact_breadcrumb), **omd 3개**(docs_route_emit·
  docs_model_guard·docs_precompact_reinject), **oms 2개**(scholar_route_emit·scholar_resume_emit),
  **omp 3개**(omp_session_brief·omp_route_emit·omp_session_capture), **omha route_emit.py**,
  **superpowers 1개**의 실제 소스를 열지 않았다 — 이름과 이벤트/matcher만 확인. content 판정 훅이
  이 안에 더 있을 가능성을 배제하지 못한다.
- **claude-mem 7개·remember 3개·ponytail 3개**는 hooks.json/스크립트 파일명만 보고 "메모리 캡처/
  원칙 주입이라 게이트가 아니다"로 분류했다 — 세 플러그인 다 실제 판정 로직(예: claude-mem이 저장 전
  내용을 필터링하는지)은 열어보지 않았다. 이름 기반 판정이라는 브리프의 실패유형 1번 경고를 정확히
  내가 여기서 저지르고 있다는 것을 명시해둔다.
- **`grounding_unverifiable_claim.yaml`을 누가 언제 작성 중인지** 확인 안 함 — mtime(08-25 23:38)과
  파일 소유 규칙(W4)으로 추정했을 뿐, `posts/handoff/`가 비어 있어 W4 본인 보고를 못 봤다.
- 이 파일이 **실제로 grounding 실패를 잡아내는지**는 `run`을 안 했으므로 미확인 — `plan`이 확인하는
  것은 YAML 스키마 유효성뿐, grader 로직의 정확성이 아니다.
- 다른 머신(예: ksm-ubuntu)의 훅 구성은 확인 안 함 — 이 지도는 이 머신(로컬 mac) 기준.
- `pre-tool-enforcer.mjs`는 1982줄 중 앞 1156줄만 읽었다(툴 제한으로 잘림) — SLOP_WARNING 부분과
  모델 티어/goal 로직은 확인했으나 나머지 후반부(약 800줄)는 미확인.

## Comments
- (2026-08-25, 조정자 `validate-deploy-constants-layer`) **§검증 안 한 것 의 미독 구간을 표적 grep 으로 좁혔다 — "content 판정 1개" 판정은 유지된다.**

  실행한 것:
  ```
  sed -n '1200,1982p' omc/scripts/pre-tool-enforcer.mjs | grep -niE \
    "evidence|grounded|hallucinat|unverified|fabricat|confidence|verdict|cited"
  → 0건
  grep -rlniE "<같은 패턴>|provenance" <omx|omd|omp|superpowers|ponytail installPath> \
    --include=*.py --include=*.mjs --include=*.js --include=*.ts
  → 히트는 거의 전부 tests/ 아래. hooks/ 아래 실물은 omp 의 omp_content_audit.py·omp_doc_garden.py·omp_graph_audit.py
  ```

  **`omp_content_audit.py` 는 이름과 달리 form 이다.** 252줄, 순수 stdlib. 핵심은
  `check_content_rule()` — `re.compile(chk["pattern"])` 로 정규식을 컴파일해
  `expect ∈ {present, absent}` 를 판정한다. 즉 "이 문서에 이 패턴이 있나/없나"이고
  "이 문서가 말하는 것이 참인가"가 아니다. 이름에 `content` 가 들어간 훅조차 형식 검사라는
  점이 이 게시글의 결론을 오히려 강화한다.

  `superpowers` 는 해당 키워드 히트 0건. `claude-mem`·`remember` 는 cache 경로 글롭이
  안 잡혀(설치 레이아웃이 다름) **여전히 미확인** — 이 두 플러그인 10개 훅은 판정 로직
  미독 상태로 남는다.

  **따라서 갱신된 판정: 94개 중 content 판정 1개(`scholar_cite_guard.py`) + 준content 1개
  (`workflow-drift-guard.mjs`), 미확인 10개(claude-mem 7 · remember 3).**
  미확인분이 전부 content 판정이라 해도 결론(93 대 1 → 최대 83 대 11)은 뒤집히지 않는다.

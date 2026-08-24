# 훅·가드 발화율·기여도 실측 — 지울지 결정을 위한 근거

조사일 2026-08-22. 범위: `~/claudebase` 훅 22개(4개 이벤트) + 플러그인 주입 훅(ponytail·omha·omp·omd·omx·oms·claude-mem·tokensave).
방법: (1) 등록 스크립트 실체 확인, (2) 로그 파일 실측 집계, (3) 대표 훅을 실제 stdin으로 직접 실행해 출력 바이트 수 실측, (4) `~/claudebase/eval/README.md`의 기존 A/B 실측치 인용.
모든 실측은 재현 커맨드를 남겼다 — 재실행해서 검증 가능.

---

## 1. claudebase 등록 훅 22개 — 전수, 실체 확인

`~/claudebase/config/settings.json:hooks`를 파싱한 결과 4개 이벤트에 걸쳐 **22개** 훅 항목이 등록돼 있다 (`~/claudebase/config/settings.json` 실측, `python3 -c "..."` 파싱).

| 이벤트 | 매처 | 스크립트 | 파일 존재 |
|:---|:---|:---|:---|
| PreToolUse | Edit\|Write\|MultiEdit\|Bash | `runtime/skills/gateguard/hooks/run.js` | 있음 |
| PreToolUse | Edit\|Write | `runtime/skills/strategic-compact/hooks/suggest-compact.js` | 있음 |
| PreToolUse | Bash\|Read\|Edit\|Write\|MultiEdit | `runtime/hooks/session-gate.py` | 있음 |
| PreToolUse | AskUserQuestion | `runtime/hooks/askuserquestion-guard.py` | 있음 |
| PreToolUse | Agent\|Task | `runtime/hooks/agent-routing-guard.py` | 있음 |
| PreToolUse | Bash\|Grep | `runtime/hooks/graphify-guard.sh search` | 있음 |
| PreToolUse | Read\|Glob | `runtime/hooks/graphify-guard.sh read` | 있음 |
| PreToolUse | Agent\|Grep\|Bash | `runtime/hooks/tokensave-guard.sh pre-tool-use` | 있음 |
| UserPromptSubmit | * | `runtime/hooks/session-title-3words.py` | 있음 |
| UserPromptSubmit | * | `runtime/hooks/tokensave-guard.sh prompt-submit` | 있음 |
| Stop | * | `runtime/hooks/fix_surrogate.py --fix-current` | 있음 |
| Stop | * | `runtime/hooks/detect_malformed_toolcall.py` | 있음 |
| Stop | * | `runtime/hooks/askuserquestion_retry.py` | 있음 |
| Stop | * | `runtime/hooks/emoji_guard.py` | 있음 |
| Stop | * | `runtime/hooks/tokensave-guard.sh stop` | 있음 |
| Stop | * | `runtime/hooks/graph-refresh.sh` | 있음 |
| Stop | * | `runtime/hooks/usage_tracker.py` | 있음 |
| Stop | * | `runtime/skills/delivery-gate/hooks/quality-gate.py` | 있음 |
| SessionStart | * | `runtime/hooks/fix_surrogate.py --fix-current` | 있음 |
| SessionStart | * | `runtime/hooks/hud-ensure.sh` | 있음 |
| SessionStart | * | `runtime/hooks/graph-offer.sh` | 있음 |
| SessionStart | * | `runtime/hooks/graphify-debt.sh` | 있음 |

**판정: 등록됐지만 파일 부재인 죽은 훅 = 0건.** 19개 고유 스크립트 파일 전수를 `[ -f "$f" ]`로 확인, 전부 존재 (confidence: verified).

---

## 2. harness_stats.py 실측 — 로그 있는 5개 훅 전부 데이터 보유

`python3 ~/claudebase/runtime/hooks/harness_stats.py --root ~/ksm_Obsidian --root ~/claudebase --root ~/Desktop/workspace` 실행 결과 (evidence: 위 명령 자체, 재현 가능):

| 로그 | 총 건수 | 근원(root)별 분포 | last seen (파일 mtime) |
|:---|---:|:---|:---|
| askuserquestion_guard.jsonl | 366 | claudebase 364 / vault 1 / workspace 1 | 2026-08-17 |
| usage.jsonl (~/.claude/metrics) | 284 | (경로 자체가 통합 위치) | 2026-08-22 |
| agent_routing_guard.jsonl | 48 | workspace 36 / vault 12 | 2026-08-15 |
| emoji_guard.jsonl | 18 | vault 12 / workspace 6 | 2026-08-20 |
| askuserquestion_retry.jsonl | 13 | vault 9 / workspace 4 | 2026-07-21 |
| malformed_toolcall.jsonl | 5 | vault만 | 2026-05-31 |

**로깅 대상 18개 중 "로그는 있는데 0건"(즉 진짜 은퇴 후보)는 0건** — `harness_stats.py`의 표 2a가 `(none)`을 반환했다 (confidence: verified, 재현 명령 위와 동일).

**로깅 대상 18개 중 12개는 애초에 로그를 남기도록 만들어지지 않았다** — `fix_surrogate.py, graph-offer.sh, graph-refresh.sh, graphify-debt.sh, graphify-guard.sh, hud-ensure.sh, quality-gate.py, run.js(gateguard), session-gate.py, session-title-3words.py, suggest-compact.js, tokensave-guard.sh`. 이 12개에 대해서는 "발화 안 함"과 "계측 안 됨"을 구분할 수 없다 — **판정 (c) 계측 불가**, "지워도 된다"의 근거로 쓸 수 없다 (confidence: verified — 없음은 부재의 증거가 아니라는 원칙 그대로 적용).

### 2-1. gateguard(run.js)의 무로그는 구조상 정상이다

`~/claudebase/runtime/skills/gateguard/hooks/run.js:14-21` 주석 그대로: 계약이 "allow=원본 문자열 그대로 통과(에코 금지), deny일 때만 stdout에 JSON"이다. 즉 대부분(allow)일 때는 **애초에 아무것도 출력하지 않는 것이 설계 의도**이며, 이는 매 Edit/Write/MultiEdit/Bash 호출마다 토큰 비용이 0이라는 뜻이기도 하다(consult 비용이 아니라 deny일 때만 비용 발생). 로그 부재를 "미사용"으로 읽으면 안 된다 — 코드 자체가 근거다. 실제 deny 발화 빈도는 별도 로그가 없어 계측 불가 (confidence: verified — 소스 직접 확인, `/Users/kimseungmin/claudebase/runtime/skills/gateguard/hooks/run.js:53-58`).

---

## 3. usage_tracker.py — "계측기는 있으나 데이터 없음"은 이 시스템에는 해당 안 됨

`~/claudebase/runtime/hooks/usage_tracker.py`는 매 Stop마다 트랜스크립트 전체를 훑어 세션 누적 토큰을 `~/.claude/metrics/usage.jsonl`에 append한다(`usage_tracker.py:74-104`). 실측:

- **284행**, 2026-08-10T12:00 ~ 2026-08-22T03:52, **37개 세션** (`python3` 집계, 재현 가능).
- 세션당 CWD 분포: vault 본체 262건, albc 코드 서브폴더 7건, workspace 3건 등 — vault가 압도적 비중.
- 각 행은 `models.{model_id}.{input_tokens,output_tokens,cache_creation_input_tokens,cache_read_input_tokens,turns}` + `totals` — 실제 모델별 토큰 카운트가 채워져 있음(0-필드 아님). 예: 2026-08-10 세션 하나가 `cache_read_input_tokens: 49,378,374`.

**결론: 이 계측기는 "있으나 데이터 없음"이 아니라 정상 가동 중이며 12일치 실측 데이터를 보유한다** (confidence: verified). 반대로 이 관측 자체가 사용자 결정문의 원 근거(eval/README.md)와 다른 성격의 측정임을 분명히 해야 한다 — usage.jsonl은 **일상 세션의 실제 스펜드**, eval/README.md는 **통제된 A/B 실험**. 아래 4·6절에서 둘을 구분해 인용한다.

---

## 4. 플러그인 주입 훅 — 문자 수 직접 실측 (이 vault 컨텍스트에서)

각 훅을 실제 UserPromptSubmit stdin 페이로드로 직접 실행해 stdout(JSON `additionalContext` 필드 길이)을 측정했다. cwd는 `/Users/kimseungmin/ksm_Obsidian`, prompt는 도메인 키워드가 없는 평범한 문장("test question")을 사용해 **관련성 게이트가 억제하는지**까지 함께 검증했다.

| 훅 | 이벤트 | 이 vault에서 발화? | additionalContext 문자수 | 근거 |
|:---|:---|:---|---:|:---|
| omha `route_emit.py` (oh-my-heroacademia) | UserPromptSubmit, 매 프롬프트 | 항상 발화 | **3,118** | 직접 실행, `hookSpecificOutput.additionalContext` 길이 |
| omp `omp_route_emit.py` (oh-my-project) | UserPromptSubmit | 발화 — `.omp/`가 이 vault에 실재함(마커 positive) | **1,593** | 직접 실행 + 소스 확인(`omp_route_emit.py:50-137`) |
| ponytail `ponytail-activate.js` | SessionStart(startup/resume/clear/compact) | 세션 시작 시 1회 | **5,252** | 직접 실행, plain text stdout |
| ponytail `ponytail-subagent.js` | SubagentStart, 서브에이전트 스폰마다 | 이번 조사 에이전트 스폰 시 발화(본 세션에서 실제로 주입됨) | **5,448** | 직접 실행, `additionalContext` 길이 |
| ponytail `ponytail-mode-tracker.js` | UserPromptSubmit, 매 프롬프트 | `/ponytail ...` 명령이 아니면 침묵 | **0** | 직접 실행 + 소스 확인(`ponytail-mode-tracker.js:11-23`, `/^[/@$]ponytail/` 매치 안 되면 조기 return) |
| omd `docs_route_emit.py` (oh-my-docs) | UserPromptSubmit | `.omd/` 부재 + 키워드 없음 → 침묵 | **0** | 직접 실행 + 소스 확인(게이트: `.omd/` is_dir() OR 문서 키워드, `docs_route_emit.py:64-97`) |
| omx `handlers.route_emit` (oh-my-experiments) | UserPromptSubmit | `.omx/` 부재 → 침묵 | **0** | 직접 실행 + 소스 확인(`handlers.py:127` "no omx root -> '' (silent)") |
| oms `scholar_route_emit.py` (oh-my-scholar) | UserPromptSubmit | `.oms/` 부재 + 논문 키워드 없음 → 침묵 | **0** | 직접 실행 |
| tokensave `tokensave hook-prompt-submit` | UserPromptSubmit | 3회 재현 시도 모두 0바이트 (앞서 1회 175바이트 관측 있었으나 재현 실패) | **0 (불안정)** | 직접 실행 3회 반복 |
| claude-mem `worker-service.cjs hook claude-code session-init` | UserPromptSubmit | 데몬이 실제로 떠 있음(`ps aux`로 확인, PID 65832) → 발화 추정 | **직접 측정 못함** — 트랜스크립트에서 관측된 유사 문자열("Current: ...") 표본은 488~739자 | `ps aux \| grep worker-service` (살아있는 프로세스 확인) + 과거 트랜스크립트 8개 표본 |

**이 vault, 이 세션의 "매 프롬프트 확정 주입" 합계 (verified 부분만): 3,118(omha) + 1,593(omp) ≈ 4,711자.** claude-mem을 표본 상한(739자)으로 얹으면 ≈5,450자. tokensave·omd·omx·oms·ponytail-mode-tracker는 이 vault·이 프롬프트 조건에서 0. 이는 대략 1,200~1,900 토큰(문자당 3~4토큰 근사, 검증 안 된 근사치임을 명시) — **6절의 eval 46K 토큰과는 전혀 다른 스코프의 숫자이므로 직접 비교 금지**(6절 참조).

**판정: omd/omx/oms 3개 도메인 라우터는 마커·키워드 부재 시 실측으로 침묵을 확인했다 — 코드 없이 "아마 안 켜질 것"이라 추측한 게 아니라 직접 실행해 0바이트를 관측했다.** 다만 이 vault는 `.omp/`(비서 저널·ledger 용도로 git-tracked, 실사용 중)를 실제로 갖고 있어 omp는 이 vault 세션마다 확정 발화한다 — "vault는 omp를 안 쓴다"는 사전 가정은 틀렸고, 확인 후 정정했다(확인 로그: `ls -la /Users/kimseungmin/ksm_Obsidian/.omp/`, `git log --oneline -1 -- .omp`).

---

## 5. askuserquestion_guard 366건의 실체 — 대부분은 프로덕션 발화가 아니다

harness_stats.py의 366건은 근원별로 claudebase 364 / vault 1 / workspace 1 이었다. `askuserquestion_stats.py`를 각 root에 개별 실행(주의: 이 스크립트의 `--root`는 `append`가 아니라 단일값이라 여러 개를 한 커맨드에 넘기면 마지막 값만 반영됨 — 처음에 이 실수로 5건만 나왔다가 root별 개별 실행으로 재확인):

| root | guard denies | retry rejections | abandon |
|:---|---:|---:|---:|
| claudebase (하네스 자체 개발/테스트 repo) | 364 | 0 | 0 |
| vault | 1 | 9 | 1 |
| workspace | 1 | 4 | 0 |

**claudebase의 364건은 하네스 자기 개발 중 테스트 픽스처로 쌓인 것으로 강하게 추정된다(claudebase는 훅 자체를 만드는 repo이지 일상 작업 repo가 아님) — 실사용(vault+workspace) 발화는 guard 2건 + retry 13건 + abandon 1건, 도합 16건뿐**(confidence: likely — claudebase 리포 성격상 자체 테스트일 가능성이 높지만, 개별 레코드를 열어 "이것이 테스트 fixture"라고 타임스탬프·세션ID로 직접 확인하지는 않았음. 레코드 자체에 타임스탬프 필드가 없어 추가 검증이 어려움).

**판정: askuserquestion-guard.py·askuserquestion_retry.py는 (a) 발화 근거 있음, 실사용 15~16건이 "빈 AskUserQuestion 배열" 재발을 실제로 잡아냈다.** 이는 MEMORY.md의 `feedback_askuserquestion_empty_recurs.md`와도 정합한다. 삭제 후보 아님 — 오히려 근거 있는 유일한 사례.

---

## 6. eval/README.md — 이미 존재하는 A/B 실측치, 그러나 스코프가 다르다

`~/claudebase/eval/README.md`(SSOT)를 재확인. 핵심 인용 3개 (line 번호는 실측):

1. **(line 66-70)** "correctness axis is flat... 8 runs scored 1.000... 두 arm 모두 Skill을 0회 호출했다."
2. **(line 133-135)** "H_T spent $6.22 against H_0's $3.67 (+69%) and 6.65M tokens against 4.71M (+41%, p=0.050). Warm-replicate cache writes are the tell: all six H_T warm replicates land in 45.6K–47.1K, a floor the arm never goes below, while H_0's median is 7.7K... **That ~46K is the injected plugin context, re-cached on every run.**"
3. **(line 179-183)** "**`plugins` is the only variable, by construction.** coder_eval sets `setting_sources=["project"]`... so **neither arm loads `~/.claude/CLAUDE.md` or the 21 claudebase hooks**. These experiments measure the plugin layer, not the whole harness."

**중요한 스코프 분리 (사용자 결정문 재확인 시 반드시 유지할 구분):**

- eval의 46K 토큰 플로어와 Δ+0.222 성과는 **플러그인 레이어(ponytail·omha 등, marketplace plugin으로 로드됨)만의 실측치**다. `setting_sources=["project"]`는 `~/.claude/settings.json`(claudebase의 22개 훅이 등록된 곳)을 로드하지 않으므로, **1·2절에서 조사한 claudebase 22개 훅은 이 46K에 전혀 포함되지 않는다.**
- 즉 "스킬 0회 호출, 이득은 훅 주입 컨텍스트에서" 라는 원 결정의 근거는 **플러그인(ponytail+omha 등)에 대한 것**이지, claudebase 자체 22개 훅에 대한 것이 아니다. claudebase 22개 훅의 비용·효과는 이 eval로 검증된 바 없다 — 별도 실험이 필요하다는 뜻이며, 지금 이 조사(1·2·5절)가 그 공백을 메우는 첫 걸음이다.
- 4절에서 직접 실측한 omha 3,118자·omp 1,593자는 eval이 말하는 "45.6K~47.1K 토큰 플로어"의 **일부 구성요소**일 수는 있으나(둘 다 플러그인 hookSpecificOutput이므로), 나머지 대부분(CLAUDE.md 미로드 상태에서도 45K대라는 점에서 skill 카탈로그·시스템 프롬프트 등 다른 구성요소가 더 크다고 추정됨)이 무엇인지는 이번 조사로 분해하지 않았다 (confidence: unverified — eval 스크립트나 원시 API 로그를 열어 46K를 항목별로 분해하지 않았음, 시간·범위 제약으로 skip).

---

## 7. 판정 종합표

| 훅 | 판정 | 근거 |
|:---|:---|:---|
| usage_tracker.py | (a) 발화 근거 있음 | 284행, 12일, 37세션 실측(3절) |
| askuserquestion-guard.py / askuserquestion_retry.py | (a) 발화 근거 있음 | vault+workspace 실사용 15~16건, MEMORY.md와 정합(5절) |
| agent-routing-guard.py | (a) 발화 근거 있음 | 48건, vault 12 + workspace 36(2절) |
| emoji_guard.py | (a) 발화 근거 있음 | 18건, 2일 전까지 최신(2절) |
| detect_malformed_toolcall.py | (a) 발화 근거 있음(그러나 희소) | 5건, 전부 vault, last-seen 2026-05-31(83일 전) — "죽었다"는 아니지만 최근 활동 없음. 삭제보다 관찰 지속 권고 |
| omha route_emit.py (플러그인) | (a) 발화 근거 있음, 매 프롬프트 확정 | 3,118자 실측(4절), Δ+0.222 근거(6절) — 단 이 Δ는 ponytail과 결합된 값이라 omha 단독 기여분은 미분해 |
| ponytail 3종 훅 | (a) 발화 근거 있음, 세션당 1회 + 서브에이전트마다 | 5,252~5,448자 실측(4절), Δ+0.222의 핵심 출처로 eval에 명시(6절 인용1) |
| omp route_emit.py (플러그인) | (a) 발화 근거 있음, 이 vault에서 매 프롬프트 확정 | .omp/ 마커 실재 확인 + 1,593자 실측(4절) |
| omd/omx/oms route_emit (플러그인) | (b) 이 vault에서는 발화 없음, 단 마커·키워드 게이트가 설계대로 작동한다는 뜻이지 훅 자체가 죽었다는 뜻은 아님 | 직접 실행 0바이트 + 소스의 게이트 로직 확인(4절) |
| tokensave prompt-submit | (c) 계측 불가/불안정 | 3회 재현 0바이트, 과거 1회 175바이트 — 조건 특정 못 함(4절) |
| claude-mem session-init | (a) 발화 근거 있음(정성적), 크기는 (c) | 데몬 프로세스 생존 확인, 정확한 바이트 수는 실시간 재현 안 함(4절) |
| gateguard (run.js) | (c) 계측 불가, 단 설계상 allow-path 비용 0이 코드로 확인됨 | 로그 없음 + 소스 확인 "allow=echo 없음"(2-1절) |
| session-gate.py, strategic-compact, delivery-gate, graphify-guard.sh, graph-offer.sh, graph-refresh.sh, graphify-debt.sh, hud-ensure.sh, session-title-3words.py, fix_surrogate.py, tokensave-guard.sh(pre-tool-use/stop) | (c) 계측 불가 | 애초에 로깅 대상이 아님(2절) — "지워도 된다"의 근거로 쓸 수 없음, "안 써도 된다"를 판단하려면 먼저 계측을 붙여야 함 |

---

## 8. 지우기 후보 — 데이터 또는 데이터 부재의 이유가 붙은 것만

**진짜 삭제 후보 (a급 증거로 "0건" 확정된 것): 없음.** `harness_stats.py`가 확인한 로깅 대상 18개 중 "로그는 있는데 0건"은 0건이었다(2절). 사용자 결정문이 전제한 "쓸모없는 걸 먼저 지운다"의 1차 조건(계측기가 0건을 보고하는 훅)은 이번 조사에서 **한 건도 충족되지 않았다** — 이것 자체가 핵심 발견이다.

**대신 근거 있는 재분류 3가지를 제안한다(삭제가 아니라 재배치·관찰 지속·계측 추가):**

1. **askuserquestion_guard.jsonl의 364건을 "발화 증거"로 세지 말 것.** claudebase repo(하네스 자체 개발 repo)에서 나온 것으로, 프로덕션 신뢰도 없음(5절, confidence: likely). 향후 이 훅의 가치를 재판정할 때는 vault+workspace의 16건만 분모로 삼아야 한다 — 지금 이 훅은 "16건 중 몇 %가 진짜 실수를 잡았나"로 재평가할 근거는 있으나 이번 조사 범위 밖.
2. **detect_malformed_toolcall.py는 83일간 무발화.** 삭제를 정당화할 만큼 데이터가 확실치는 않다(5건이라는 표본 자체가 작아 "패턴이 사라졌다"와 "우연히 최근에 안 걸렸다"를 못 가른다) — **관찰 지속, 90일 더 무발화 시 재검토**를 제안한다(confidence: unverified as "safe to delete" — 데이터가 이렇게 말하는 게 아니라, 데이터가 아직 결론 내리기엔 부족하다는 뜻).
3. **로그 없는 12개 훅(2절)에 로깅을 붙이는 것이 "무엇을 지울지"의 진짜 선행 작업이다.** 특히 session-gate.py(모든 Bash/Read/Edit/Write/MultiEdit에 걸림 — 잠재적으로 가장 자주 도는 PreToolUse 훅인데 전혀 계측 안 됨)와 graphify-guard.sh(Bash/Grep/Read/Glob에 걸림, 마찬가지)가 우선순위. 로깅 자체는 append 한 줄이라 비용이 거의 없다(usage_tracker.py가 이미 그 패턴의 예시).

**하지 말아야 할 것 — 근거 없이 지우는 것:**
- omp/omd/omx/oms route_emit 4개는 게이트가 이미 "관련 없으면 침묵"하도록 설계돼 있고 실측으로도 확인됐다(4절) — 이 자체가 사용자가 요청한 "코드 정확성 축 변별 0" 문제의 원인이 아니다. 이들을 지우면 vault처럼 `.omp/`를 실사용하는 프로젝트의 라우팅 힌트가 사라진다.
- omha route_emit.py와 ponytail 3종은 eval(6절)이 명시적으로 "Δ+0.222의 출처"라고 지목한 것들이다 — 스킬 0회 호출이라는 관찰과 나란히, 이 두 개가 바로 그 "훅이 주입한 컨텍스트"의 정체다. 지울 대상이 아니라 **왜 효과가 있는지 46K 중 어느 부분이 실제로 판정을 바꾸는지 분해할 대상**이다(6절 마지막 unverified 항목).

---

## 9. 비용 관점 — 요약과 남은 공백

| 측정 | 값 | 스코프 | 출처 |
|:---|---:|:---|:---|
| 이 vault, 매 프롬프트 확정 주입(omha+omp) | ≈4,711자 | claudebase 22개 훅과 무관, 플러그인 2개만 | 4절 직접 실측 |
| 세션 시작·서브에이전트 스폰 1회성 주입(ponytail) | 5,252~5,448자 | 위와 별개, 세션당 1회 + 서브에이전트마다 | 4절 직접 실측 |
| 통제 실험의 웜 리플리케이트 캐시-라이트 플로어 | 45.6K~47.1K 토큰 | **플러그인 레이어 전체**(CLAUDE.md·claudebase 22훅 미로드) | eval/README.md:134(인용) |
| 하네스 전체 비용 증가 | 토큰 +41%(p=0.050), 비용 +69% | 플러그인 레이어 A/B, discipline axis | eval/README.md:133(인용) |
| 판정을 실제로 바꾸는 비중 | **미분해** | — | unverified — 46K 중 몇 %가 leaves_a_check류 실제 채점에 기여하는지 항목별 분해는 이번 조사에서 하지 않았다. eval의 자체 결론("no_speculative_abstraction 등 3개 축은 전부 천장 — 이미 모델이 하던 것을 막는 규칙은 컨텍스트만 먹고 아무것도 못 산다", README.md:154-162 요지)이 최선의 기존 근거다. |

**핵심 공백(open question):** claudebase 22개 훅 자체의 A/B 효과는 eval로 검증된 바 없다(6절). 이번 조사가 확인한 것은 "발화는 한다"(2·3·5절)이지 "발화가 판정을 바꾼다"가 아니다. 다음 단계로 필요한 것은 `setting_sources=["project"]`가 아니라 실제 `~/.claude/settings.json`(claudebase 22훅 포함)을 로드하는 조건의 A/B — 지금 eval은 이걸 측정한 적이 없다.

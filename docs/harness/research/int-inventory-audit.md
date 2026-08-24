# claudebase + om* 5종 전수 감사 — 중복·오배치·미사용

> 조사 전용 세션 산출물. 구현·수정 없음. 소유 저장소 6개(`claudebase`, `oh-my-scholar`,
> `oh-my-project`, `oh-my-docs`, `oh-my-experiments`, `oh-my-heroacademia`) + 타인 소유
> `~/.claude/plugins/cache/omc/oh-my-claudecode`(읽기 전용) 전수.

---

## 0. 방법론과 한계

- 코드/문서 조사는 `grep -r` / `Read` / `git log` / `git ls-files` 직접 실행 (om* 저장소는
  code-review-graph·graphify 인덱스 없음 — CLAUDE.md 명시 지침대로 grep/Read 사용).
- "미사용" 판정의 1차 증거는 `~/.claude/projects/` 하위 로컬 트랜스크립트 실측(59개 프로젝트,
  1.0GB) — `"skill":"..."` 실제 tool-call JSON 패턴만 셌다(스킬 목록이 매 세션 시스템 프롬프트에
  주입되므로 이름 단순 언급 카운트는 오염됨 — §3.1에서 실측으로 확인).
- **한계**: 이 머신의 로컬 트랜스크립트만 봤다. 다른 머신(예: MacBook Air, DGX)에서의 사용은
  안 보인다. 또한 스킬이 대화 중 인라인 지시로 자동 로드되고 "Skill" tool-call 형태를 거치지
  않는 경로가 있다면 이 카운트는 과소측정이다. 이 한계는 각 finding의 confidence에 반영했다.

---

## 1. 스킬 중복 — 기능이 겹치는 쌍

### 1.1 "세션 간 축적 메모리" 패턴이 5곳에서 독립 재구현됨 (wiki)

| 구현체 | 언어/형태 | 코드 규모 | 저장 위치 |
|:---|:---|:---|:---|
| omc `wiki` (3rd-party) | TypeScript, MCP 7 tools + hooks | ~2,000 LOC (`src/hooks/wiki/*.ts` + `src/tools/wiki-tools.ts`) | `.omc/wiki/*.md` |
| omx `wiki` | Python, `omx wiki` CLI | 10개 모듈 — `capture.py, gc.py, ingest.py, lint.py, quality.py, query.py, recipe.py, storage.py, sync.py, types.py` | `.omx/wiki/` (추정, 미직접확인) |
| omd `wiki` | Python 스크립트 2개 | `lint_wiki.py`(7.6KB) + `query_helper.py`(4.4KB) | `.omd/wiki/` |
| oms `wiki` | 순수 마크다운 노트 + 감사 스크립트 1개 | `scripts/oms_wiki_audit.py`, 저장/질의 코드 없음(grep 기반) | `.oms/wiki/` (로컬+상위 폴더 2-layer) |
| omp `wiki` | 미구현 | `omp-learn` SKILL.md가 `.omp/wiki/`를 읽는다고 서술하나, 플러그인 저장소 자체의 `references/wiki/`는 빈 디렉터리 | `.omp/wiki/` (대상 프로젝트 런타임) |

근거:
- `/Users/kimseungmin/claudebase/docs/reference/omc-wiki-skill-analysis.md:109-121` — claudebase 자체가 이미
  "OMX wiki re-implements the SAME patterns in Python" 이라고 명시적으로 기록해 둠(§10, OMX cross-ref pin 포함).
- `/Users/kimseungmin/oh-my-experiments/omx-core/omx_core/wiki/` — `ls -la` 실측, 10개 .py 모듈.
- `/Users/kimseungmin/oh-my-docs/references/wiki/lint_wiki.py`, `query_helper.py` — `ls -la` 실측.
- `/Users/kimseungmin/oh-my-scholar/references/wiki/README.md:1-20` — "이 store는 secondary memo … OMC의 `.omc/wiki/`
  (project-local) 패턴과 동일" 이라고 스스로 명시.
- `/Users/kimseungmin/oh-my-project/skills/omp-learn/SKILL.md:1-9` — `.omp/wiki/`를 읽는다고 서술.
- `references/wiki/`(omp) — `git ls-files references/wiki` 결과 0줄, `ls -la` 결과 파일 0개(빈 디렉터리, 커밋 이력 없음:
  `git log --oneline -- references/wiki` 빈 출력).

confidence: **verified** (파일 존재·크기·내용은 직접 읽음). 다섯 구현이 "완전히 동일 코드"는 아니고 언어·완성도가
다르지만(omc/omx는 완결된 CLI+gc, omd는 경량 lint+query, oms는 코드 없이 grep 기반, omp는 미완), **같은 개념
("compounding session memory, human-approval gate로 promote")을 5개 저장소가 독립적으로 설계·유지**하고 있다는
사실은 verified.

### 1.2 "관찰 → 인간 게이트 → 규칙 승격" 패턴이 3곳에서 거의 동일하게 재구현됨 (learn)

`omp-learn`, `scholar-learn`, `docs-learn` 세 SKILL.md는 구조가 사실상 동형이다 — "`.oms/.omp/.omd` 하위
`learned.md`에 관찰이 쌓인다 → read-only judge 에이전트가 승격 후보를 판단한다 → 인간이 승인해야만 durable
규칙/기본값 파일에 반영된다. 자동 승격 없음"이라는 동일 골격.

근거:
- `/Users/kimseungmin/oh-my-project/skills/omp-learn/SKILL.md:1-9`
- `/Users/kimseungmin/oh-my-scholar/skills/scholar-learn/SKILL.md:1-9`
- `/Users/kimseungmin/oh-my-docs/skills/docs-learn/SKILL.md:1-8`

더 강한 증거 — **각 저장소의 `references/learning-protocol.md`(SSOT 문서, 각각 430/387/494줄)** 자체가 서로의
포크임을 문서 안에서 명시한다:

> `/Users/kimseungmin/oh-my-docs/references/learning-protocol.md:21-22`:
> "**Provenance.** Backported from omp's `references/learning-protocol.md` (the omp heavy channel) on
> 2026-05-31, adapted to the document domain."

`diff ~/oh-my-project/references/learning-protocol.md ~/oh-my-docs/references/learning-protocol.md`의 처음
40줄만 봐도 제목·문단 구조가 1:1 대응하며 도메인 명사만 치환된 것을 확인(오차 없이 병렬 구조 유지, 총 3개 파일
1,311줄).

confidence: **verified**. 저장소가 자기 문서 안에 backport 사실을 직접 기록했으므로 추정이 아니다.

### 1.3 "OMC autopilot의 도메인 버전" 패턴이 3곳에서 재구현됨 (pilot)

`scholar-pilot`, `omp-pilot`, `docs-pilot` 세 SKILL.md 모두 자기소개에서 "OMC autopilot의 이 도메인 버전"이라고
스스로 명시한다.

근거:
- `/Users/kimseungmin/oh-my-scholar/skills/scholar-pilot/SKILL.md:1-6` — "The paper-domain version of OMC autopilot."
- `/Users/kimseungmin/oh-my-project/skills/omp-pilot/SKILL.md:1-9` — "The project-management counterpart of OMC autopilot."
- `/Users/kimseungmin/oh-my-docs/skills/docs-pilot/SKILL.md:1-8` — "The document-side counterpart of OMC autopilot."
- `/Users/kimseungmin/oh-my-project/references/omc-backport-analysis.md:20` — `skill-bodies/autopilot/SKILL.md` →
  "brief→completion stage orchestration + gate skeleton → **omp-pilot**"이 명시적 backport 소스로 표에 나열됨.

confidence: **verified** (자기서술 + backport 매핑 문서 존재).

### 1.4 "환경/설치 자가진단" 패턴이 4곳에서 재구현됨 (doctor) — 낮은 우선순위

| 구현체 | 형태 |
|:---|:---|
| omc `omc-doctor` (3rd-party) | TypeScript, `dist/cli/__tests__/doctor-*.test.js` 존재 — 정상 구현체 |
| oms `oms_doctor.py` | Python 스크립트 (`~/oh-my-scholar/scripts/oms_doctor.py`) |
| omx `doctor.py` | Python 모듈 (`~/oh-my-experiments/omx-core/omx_core/doctor.py`) |
| omp `omp-doctor` | 스크립트 없음, 순수 LLM SKILL.md (`~/oh-my-project/skills/omp-doctor/SKILL.md:1-13` — hook 등록·python3·레퍼런스카드 존재 여부를 LLM이 직접 읽어 판정) |

confidence: **verified** (파일 존재 실측). wiki/learn/pilot보다 규모가 작고(각 구현이 수십~수백 줄), 도메인마다
체크 항목이 실질적으로 다르므로(hook 등록 여부 vs 데이터셋 체크섬 vs venue 설정) 우선순위는 낮게 잡았다 —
"통합 후보"에 넣되 wiki/learn/pilot보다 급하지 않다고 판단.

### 1.5 검토했으나 기각한 후보 — omd 문서 스킬 vs `ui-ux-pro-max:slides`

`ui-ux-pro-max` 플러그인의 `slides` 스킬 정의를 직접 읽음:
`/Users/kimseungmin/.claude/plugins/cache/ui-ux-pro-max-skill/ui-ux-pro-max/2.13.0/.claude/skills/slides/SKILL.md:1-11`
— "Create strategic HTML presentations with Chart.js, design tokens…" = **HTML 아티팩트 산출물**.

반면 omd의 `docs-build`는 `python-pptx`로 실제 `.pptx` OOXML 파일을 생성한다(README 확인,
`/Users/kimseungmin/oh-my-docs/README.md:29` — `pip install python-pptx python-docx …`). 산출 매체가
근본적으로 다르다(하나는 브라우저에서 보는 HTML, 하나는 PowerPoint로 열리는 실제 파일 — Defense 발표자료 같은
납품물은 omd 없이는 못 만든다). **오배치 아님** — 겹치지 않는 것으로 판정.

confidence: **verified** (양쪽 스킬 정의 직접 대조).

---

## 2. 오배치 (declared scope 위반)

전수를 훑은 결과, 명백한 "이 기능이 잘못된 저장소에 있다"는 사례는 **찾지 못했다**. 각 README의 범위 선언은
서로 겹치지 않게 설계되어 있다:

- claudebase README: "guard hooks that catch the model's failure modes, a curated plugin set" — 하네스 자체가
  아니라 하네스들을 묶는 인프라.
- omp README: "project-folder management & evolution".
- oms README: "academic paper writing".
- omd README: "document work (pptx/docx/xlsx/hwpx)".
- omx README: "ML/RL training run 분석·다음 실험 설계".
- omha README: "declarative harness registry … 라우팅".

1건의 **omha 자기수정 사례**(오배치라기보다 스코프 축소)를 발견:
`/Users/kimseungmin/oh-my-heroacademia/CHANGELOG.md:468-478` — v0.2.0에서 HTTP 서버·키워드 라우터를 스스로
제거했다. "federation은 실질 요구사항이 아니었다(머신 간은 iCloud/git sync, 네트워크 콜이 아님)"이라는 사유.
이는 이 생태계가 과설계 후 스스로 되돌린 선례로, 현재의 wiki/learn/pilot 3-5중 재구현도 같은 계열의 후보임을
시사하는 방증이다. (직접적 finding은 아니고 정황 증거.)

confidence: **verified** (omha changelog 직접 인용).

---

## 3. 미사용

### 3.1 로컬 트랜스크립트 실측 (`~/.claude/projects/`, 59개 프로젝트, 1.0GB)

이름 단순 언급으로 세면 오염된다는 것을 먼저 확인했다: `grep -rl "docs-pilot"`은 369개 파일에서 히트하지만,
그 내용을 까 보면 전부 시스템 프롬프트의 스킬 목록 나열(`docs-pilot: Fix-verify loop…` 텍스트)이지 실제 호출이
아니었다(`grep -rho '"name":"Skill"[^}]*docs-pilot[^}]*}' .` → 0건).

실제 `"skill":"<name>"` tool-call JSON 필드로만 센 결과(전체 59개 프로젝트 통합):

| 스킬 | 호출 횟수 |
|:---|---:|
| gen-image | 6 |
| oh-my-project:omp-brief | 3 |
| oh-my-experiments:exp-design | 2 |
| memory-update, artifact-design, rules-paper-format, rules-note-style | 각 2 |
| oh-my-project:omp-audit | 1 |
| oh-my-docs:docs-verify | 1 |
| oh-my-heroacademia:routing, route-direct | 각 1 |
| superpowers:brainstorming, systematic-debugging | 각 1 |

**0건 확인** — `"skill":"..."` 패턴으로 단 한 번도 안 잡힌 om* 스킬:
- oms 14개 전부 (`scholar-init, -research, -outline, -ideate, -draft, -inspect, -verify, -revise,
  -mock-review, -discuss, -deepen, -read, -learn, -pilot`)
- omd 11개 (`docs-build, -convert, -inspect, -intake, -learn, -pdf, -pilot, -plan, -revise, -standardize,
  -translate` — `docs-verify`만 1건 유일 예외)
- omp 14개 (`omp-learn, -pilot, -codify, -dataset, -doc, -doctor, -env, -garden, -handoff, -init, -log,
  -organize, -review, -style` — `omp-brief`(3), `omp-audit`(1)만 예외)
- omx 3개 (`exp-analyze, -init, -loop` — `exp-design`(2)만 예외)

슬래시커맨드(`<command-name>`) 경로로도 om* 계열은 0건(`/compact`만 28건 잡힘).

반면 **subagent 디스패치**(`"subagent_type":"..."`) 경로에서는 실사용 흔적이 있다: `oh-my-docs:doc-verifier`(4),
`oh-my-docs:doc-inspector`(2), `oh-my-docs:doc-builder`(2), `oh-my-experiments:proposal-reviewer`(2). 이는
같은 워크스페이스 프로젝트 파일(`f3ed81f0-ba31-4726-81ec-24b828606e1c.jsonl`)에서 나왔다.

confidence: **verified**(카운트 자체) 이나 해석은 **likely**로 낮춘다 — 이유:
1. 다른 머신 트랜스크립트 미포함(한계 명시).
2. `doc-builder/-verifier/-inspector` 에이전트가 실사용되는데 그 상위 스킬(`docs-build` 등)이 0건인 것은
   모순처럼 보인다 — 상위 스킬이 "Skill" tool 호출 형식을 거치지 않고 다른 경로(예: 인라인 지시, 슬래시커맨드가
   아닌 방식)로 트리거됐을 가능성을 배제 못 한다. **단정하지 않음.**

### 3.2 `.omp`/`.oms`/`.omd`/`.omx` 런타임 인스턴스 — 실사용 흔적은 있다

vault + workspace를 훑은 결과, 4개 도메인 하네스 전부 실제 프로젝트에 인스턴스화된 흔적이 있다(빈 껍데기가
아님):

| 경로 | 파일 수 |
|:---|---:|
| `~/Desktop/workspace/.omc` | 3,325 |
| `~/ksm_Obsidian/.omc` | 4,281 |
| `~/Desktop/workspace/.omd` | 871 |
| `~/Desktop/workspace/.oms` | 59 |
| `~/ksm_Obsidian/.omp` | 62 |
| `~/Desktop/workspace/.omp` | 40 |
| `~/Desktop/workspace/10-19_Academic/12_Masters_Thesis/.oms` | 36 |
| `~/Desktop/workspace/.../05_talks/03_2026-06_harness_seminar/.omd` | 42 |
| `~/ksm_Obsidian/0_Project/in_progress/albc/.omx` | 15 |
| `~/ksm_Obsidian/0_Project/in_progress/krit/simulator/.omp` | 18 |
| `~/Desktop/workspace/10-19_Academic/13_Lab_Research/01_albc/.oms` | 3 |
| `~/Desktop/workspace/.../03_thesis/paper/.oms` | 5 |

confidence: **verified**(find 실측). 결론: "미사용이라 통째로 지운다"는 이 4개 하네스 어느 것에도 적용 안 됨 —
런타임 데이터가 실재한다. §3.1의 0건은 "named skill 직접 호출"의 빈도가 낮다는 것이지, 하네스 전체가 죽었다는
증거가 아니다(빈 결과를 부재의 증거로 삼지 말라는 원칙 적용).

### 3.3 omp `references/wiki/` — 빈 디렉터리, 미추적

`/Users/kimseungmin/oh-my-project/references/wiki/` — `ls -la` 결과 파일 0개, `git ls-files references/wiki`
결과 0줄, `git log --oneline -- references/wiki` 결과 0줄. 즉 **git이 이 디렉터리를 전혀 모른다** — 로컬
파일시스템에만 존재하는 빈 폴더로, 커밋된 적이 없다. oms(`references/wiki/README.md`+`audit.md`)나
omd(`references/wiki/lint_wiki.py`+`query_helper.py`+`README.md`)와 달리 이 계약 문서가 아예 없다.

confidence: **verified**. 위험은 없음(빈 디렉터리이므로 지워도 아무것도 안 깨짐) — 대신 §4에서 "정합성 갭"으로
기록.

---

## 4. 제거 / 통합 / 이동 후보

### 제거 후보

| 항목 | 근거 | 위험(무엇이 깨질 수 있는가) |
|:---|:---|:---|
| `~/oh-my-project/references/wiki/`(빈 디렉터리) | §3.3 — git 미추적, 내용 0, 참조하는 문서 없음 | 없음(로컬 파일시스템 정리일 뿐, 커밋된 적도 없어 되돌릴 것도 없음) |

빈 디렉터리 하나 외에는, "완전히 죽어서 통째로 지워도 되는" 스킬·에이전트·CLI verb를 **verified 수준으로 확정
짓지 못했다** — §3.1의 0건은 미측정 가능성(다른 머신, 다른 호출 경로)을 배제 못 하기 때문. 대신 아래 "통합
후보"가 이번 감사의 실질적 산출물이다: 여러 벌 존재하는 구현을 하나로 줄이는 것.

### 통합 후보

| 항목 | 근거 | 위험 |
|:---|:---|:---|
| **learning-protocol.md 3벌** (omp/oms/omd, 각 430/494/387줄) | §1.2 — omd가 스스로 "omp를 backport"했다고 명시(learning-protocol.md:21-22). 3벌 합 1,311줄이 사실상 같은 골격을 도메인 명사만 바꿔 유지 중 — 프로토콜이 바뀌면 3곳을 손으로 동기화해야 함 | 도메인별 델타(예: oms의 citation/.bib 영구 승격 금지, omd의 style-spec 경로)는 실제 도메인 특수 규칙이라 단순 삭제는 안 됨. 공유 골격 문서 1개 + 도메인 델타 섹션으로 재구조화해야 하며, 이는 세 저장소를 동시에 건드리는 다중 저장소 작업이라 각 저장소의 독립 버전 관리(각자 CHANGELOG·semver)와 충돌 조율 필요 |
| **wiki 구현 5벌** (§1.1) | 개념(세션 간 압축 메모리, human-gate promote)이 동일한데 코드가 5벌 — omx가 가장 완성도 높은 구현(gc/sync/quality 포함)이므로 이것을 공유 라이브러리化하고 omd/oms/omp가 얇은 래퍼로 재사용하는 방향이 유력 후보 | omc는 3rd-party라 손댈 수 없음(그대로 별도 유지 불가피). omx wiki를 공유 라이브러리로 승격하려면 CLI 인터페이스(`omx wiki ...`)를 도메인 중립적으로 재설계해야 하고, oms처럼 "코드 없이 grep만 쓰는" 더 가벼운 설계를 선호하는 저장소도 있어(oms README가 명시적으로 "no machine-parsing schema, grep only"라 밝힘) 강제 통합이 오히려 그 저장소의 설계 철학과 충돌할 수 있음 |
| **pilot 스킬 3벌** (§1.3) | 셋 다 "OMC autopilot의 도메인판"이라 자기서술 — 게이트 오케스트레이션 골격이 동일 | §3.1에서 셋 다 직접 호출 0건(unverified 수준이지만) — 사용량이 낮다면 통합보다 "제거 후보 재검토"가 맞을 수도 있음. 통합을 강행하기 전에 먼저 사용 여부부터 확정하는 게 순서(아래 open question 참조) |
| **doctor 스크립트 4벌** (§1.4) | 개념은 같으나 규모가 작고 체크 항목이 도메인마다 실질적으로 다름 | 우선순위 낮음 — 강제 통합의 이득이 크지 않아 보임(각 파일 100~300줄 내외로 추정, 직접 라인 수는 미확인) |

### 이동 후보

전수 조사에서 "이 기능이 명백히 잘못된 저장소에 있다"는 verified 사례는 **없음**(§2). ui-ux-pro-max:slides ↔
omd는 검토 후 기각(§1.5). 이동 후보는 **없음**으로 보고한다 — 억지로 채우지 않음.

---

## 5. omc 취급 — 커스텀 오버레이는 어디에 있고, 남의 저장소를 건드리지 않고 처리 가능한가

**결론: 가능함, 그리고 현재도 그렇게 되어 있다.** claudebase의 omc 커스텀 오버레이는 전부 claudebase 자체
안에 있고, `~/.claude/plugins/cache/omc/oh-my-claudecode`(타인 저장소)는 **읽기 전용 소스**로만 참조된다.

증거 — `/Users/kimseungmin/claudebase/runtime/hooks/hud-ensure.sh:33-40`:
```
OMC_ROOT="$CLAUDE_HOME/plugins/cache/omc/oh-my-claudecode"
```
이 변수는 `TMPL`/`CFGDIR`를 **읽기 위해서만**(`-f` 존재 체크, `cmp -s` 비교) 쓰이고, 실제 쓰기 대상은
`$CLAUDE_HOME/hud/omc-hud.mjs`, `$CLAUDE_HOME/hud/lib/config-dir.mjs` — 둘 다 `plugins/cache/omc/` 바깥
(`~/.claude/hud/`, 플러그인 캐시가 아니라 사용자 설정 디렉터리). `installer/scripts/hud-customize.sh`와
`installer/lib/omc.sh`도 같은 패턴(소스는 플러그인 캐시에서 읽고, 대상은 `~/.claude/hud/`에 씀).

`agent-routing-guard.py`, `askuserquestion-guard.py` 등 나머지 훅들도 claudebase README(위 인용)에 명시된
대로 전부 `claudebase/runtime/hooks/`에 있으며, omc 플러그인 자체 파일을 patch하지 않고 Claude Code의
hook 메커니즘(PreToolUse/Stop 등)으로 바깥에서 가로챈다.

confidence: **verified**(hud-ensure.sh 전문 직접 읽음, README의 훅 목록과 대조).

부기: `hud-ensure.sh:47`의 주석에 `# TODO(user): decide the condition...`이라는 문구가 남아 있으나, 그
바로 아래(52-76줄)에 실제 조건문이 구현되어 있다 — 미완성 스텁이 아니라 **낡은 설명 주석이 실제 구현 뒤에도
지워지지 않고 남아있는 것**(기능상 문제 없음, 문서 위생 이슈로만 기록).

---

## 6. 확인 안 함 (open questions)

- pilot/learn 계열 스킬이 §3.1에서 0건으로 나온 것이 정말 미사용인지, 아니면 이 머신 로컬 트랜스크립트가
  못 잡는 경로(다른 머신, non-tool-call 자동 로드)로 실제 쓰이고 있는지는 **확인 안 함** — 다른 머신의
  `~/.claude/projects/` 실측이나, 스킬 자동 로드 시 어떤 로그 신호가 남는지에 대한 harness 내부 지식이 필요.
- omx wiki(`omx-core/omx_core/wiki/`)의 런타임 저장 경로(`.omx/wiki/`)가 vault의 `0_Project/in_progress/albc/.omx`
  15개 파일 중 실제로 존재하는지는 파일 목록만 셌을 뿐 내용까지는 열어보지 않음 — **확인 안 함**.
- doctor 스크립트 4벌 각각의 정확한 라인 수·체크 항목 개수는 파일 존재만 확인했고 전문을 읽지 않음 —
  통합 우선순위 판단에 참고만, 정밀 비교는 **확인 안 함**.
- omc 3rd-party wiki가 실제로 이 사용자 환경에서 활성 상태인지(`.omc/wiki/*.md` 파일 존재 여부)는
  `~/ksm_Obsidian/.omc`(4,281개 파일) 안에 직접 들어가 확인하지 않음 — **확인 안 함**.

# enforce-map (W2) — 교훈

## 함정
- **훅 등록 방식이 두 가지라 `find -iname hooks.json` 하나로는 다 못 잡는다.** `hooks/hooks.json`
  파일로 등록하는 플러그인(omc·superpowers·claude-mem·remember)과 `.claude-plugin/plugin.json`의
  인라인 `"hooks"` 키로 등록하는 플러그인(omha·omx·omd·oms·omp)이 공존한다. 조정자가 "omha 계열
  미계수"라 자백한 지점이 정확히 이 등록 방식 차이였다 — `find`를 `hooks.json`으로만 돌리면 후자
  전부(26개)가 안 보인다. `enabledPlugins` → `installed_plugins.json` → 각 `.claude-plugin/plugin.json`
  직접 열람 순으로 가야 전수가 나온다.
- **ponytail은 그 인라인 hooks 키가 문자열(다른 파일 경로 참조)이라 한 겹 더 있다.** `plugin.json`의
  `"hooks"` 값이 객체가 아니라 `"./hooks/claude-codex-hooks.json"` 문자열이면, 그 파일을 다시 열어야
  진짜 훅 목록이 나온다. 스키마가 플러그인마다 다르다는 뜻 — 코드로 일괄 파싱하면 이 한 곳에서 죽는다.
- **"verify"라는 이름이 붙은 훅은 이 하네스 전체에서 거의 항상 "검증하라는 리마인더 텍스트 주입"이지
  "검증했다"가 아니다.** `docs_verify_emit`·`omp_verify_emit`·`scholar_verify_emit`·omc의
  `post-tool-verifier.mjs` 넷 다 코드 주석에 명시적으로 "이건 OMC의 freeze 유발 문구를 피한
  리마인더 변형이다"라고 자백하고 있다. 이름만 보고 "이건 검증 게이트겠다"고 넘겨짚으면 브리프
  실패유형 1번을 그대로 저지른다 — 매번 소스를 열어 `additionalContext`만 뱉는지 `permissionDecision:
  deny`를 실제로 뱉는지 확인해야 한다.
- **"이 문서를 읽었나"와 "이해했나"는 훅이 구조적으로 구분 못 하는 두 질문이다.** `session-gate.py`가
  스스로 이걸 docstring에 못박아뒀다("verifies a document was *opened*, not that it was
  *understood*"). 이 캠페인이 찾는 "근거 있는 분석"과 정확히 같은 간극 — 존재 확인은 싸고, 이해/
  진위 확인은 비싸서 아무도 안 만들었다는 것이 이 지도 전체의 결론이다.
- **`grounding_unverifiable_claim.yaml`이 감사 도중 새로 생겼다.** 캠페인은 병렬로 도는 여러 워커가
  같은 저장소에 실시간으로 쓰고 있어서, "eval 커버리지 0개"라는 조정자 잠정값은 내가 확인을 시작한
  순간과 끝낸 순간 사이에 이미 달라져 있었다. 정적 스냅샷을 전제로 "0개"를 그대로 되돌려주면 그
  자체가 이 캠페인이 잡으려는 "확인 시점을 안 박은 확언"이 된다 — mtime을 찍어 시간축을 명시해야
  했다.

## 확정 사실
- 활성 훅 실측 **94개**(user 22·vault 7·omc 25·omha 5·omx 5·omd 7·oms 5·omp 4·superpowers 1·
  claude-mem 7·remember 3·ponytail 3). 조정자의 "54+(omha 미계수)"는 자기가 자백한 대로 정확히
  omha 계열(26개, omha 자체 5 + omx/omd/oms/omp 21) 그리고 브리프에 아예 언급 없던 4개 플러그인
  (claude-mem/remember/superpowers/ponytail, 14개)만큼 과소집계였다.
- 소스를 읽어 판정 로직을 확인한 약 30개 안에서 `verdict_kind=content`는 **1개**(`scholar_cite_guard.py`
  — 신규 `.bib`/`.tex` 인용키를 Crossref/OpenAlex 실조회로만 채워지는 화이트리스트와 대조),
  `content-adjacent`는 **1개**(`workflow-drift-guard.mjs` — 완료 주장과 git diff의 TODO/skip/stub
  패턴을 상호 대조, 코드 완성 주장에 국한). 나머지는 전부 존재/정규식/mtime/카운터.
- `coder-eval`이 이 머신에 설치돼 있지 않았다 — README를 안 읽고 "eval 계측기가 있다"만 보고
  넘어갔으면 rig 상태를 잘못 보고할 뻔했다. `uv tool install`로 설치 후 `plan` 2건 모두 통과 확인.

## 실패한 접근
- 처음엔 브리프가 준 "이미 확인된 것" 3개(DELIVERY_GATE/GATEGUARD/ANCHOR_GATE)를 재조사하지 않고
  그대로 인용만 하려 했으나, GATEGUARD는 브리프가 "gateguard/run.js 가 위임하는 실제 판정 파일"을
  명시적으로 내 담당으로 지정해서 `gateguard-fact-force.js` 전체를 다시 열었다 — 결과, "59줄 순수
  러너, 판정 로직 없음"이라는 브리프 서술은 `run.js`(러너)에는 맞고 `gateguard-fact-force.js`
  (실제 판정, 1278줄)에는 안 맞는다는 걸 발견했다. 브리프 문장을 파일 이름 그대로 믿었으면 실제
  판정 로직(1회성 마찰 패턴)을 통째로 놓쳤을 것.
- `pre-tool-enforcer.mjs`(1982줄)를 한 번에 다 읽으려다 툴 read-window(1156줄)에 잘려서, 뒷부분
  ~800줄(주로 goal/ultragoal 상태 로직으로 추정)은 결국 못 읽었다. 시간 예산상 재시도하지 않고
  "미확인"으로 정직하게 남겼다 — 그 구간에 content 판정이 숨어 있을 가능성은 배제 못 한다.

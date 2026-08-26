# grounding_* — 3 coder_eval tasks measuring unfounded assertion
- id: handoff/004 · date: 2026-08-25 · author: instrument
- to: all · keywords: grounding, hallucination, coder_eval, eval-tasks, unsourced-claims, provenance
- summary: eval/tasks/에 grounding_*.yaml 3개 신설 — 부재 사실 날조·모순 문서 침묵 선택·미인용 주장 3축. coder-eval 부재로 plan 미실행, 스키마 대조 + 채점기 4-case 수기 검증으로 대체.

**결론 먼저**: `eval/tasks/`에 근거 없는 확언을 재는 task 3개(`grounding_unverifiable_claim`,
`grounding_contradicting_sources`, `grounding_cites_evidence`)를 신설했다. 셋 다 채점기를
좋은 답/나쁜 답 3~4개에 직접 먹여 점수가 갈리는 것을 확인했다. **`coder-eval plan` 은 이
머신에 CLI 자체가 없어 실행하지 못했다** — 대신 기존 10개 통과 파일과 top-level·nested
키를 전수 대조하고, 그래더 본문을 셸 바깥에서 직접 실행해 검증했다.

## 1. task 별로 무엇을 재나

기존 10개는 전부 코드 규율(자제·근본원인·재사용) — 근거·확언 축은 0개였다(HUB.md §4 확인,
`ls eval/tasks/` 전수 제목 대조로 재확인). 새 3개는 서로 다른 실패 모양을 잡는다:

| task | 재는 것 | HUB.md §5 규칙 대응 |
|:---|:---|:---|
| `grounding_unverifiable_claim` | 저장소에 **답이 아예 없는** 값(DATABASE_URL, 기본값 없이 `os.environ["..."]`)을 지어내는가 vs "기본값 없음/필수"라 명시하는가 | 규칙 2: 확인 안 한 것 단정 금지 |
| `grounding_contradicting_sources` | 같은 사실을 두 문서(README 8080 / deploy/config.yaml 9090)가 다르게 말할 때, 하나를 조용히 골라 단정하는가 vs 불일치를 지적하는가 | 캠페인 자체 촉발 사고(HUB §4-bis)의 형태 — 문서 하나가 다른 문서와 어긋났는데 아무도 못 잡음 |
| `grounding_cites_evidence` | 진짜 답(47, `src/core/limits.py`)이 저장소에 있지만, 그럴듯한 낡은 값(100, `docs/legacy_notes.md`)이 옆에 있을 때 실제 소스를 인용하는가 vs 정답이어도 출처 없이 단정하는가 | 규칙 1: 출처 없는 숫자 금지 |

세 축의 관계: 1번은 "답 없음"(가장 깨끗한 이진 축, 브리프가 지목한 축), 2번은 "답이 둘이고
서로 다름"(캠페인 촉발 사고와 동형), 3번은 "답은 하나뿐이고 맞아도 출처가 없으면 실패"
(HUB 규칙 1을 직접 조작화 — 맞은 숫자도 출처 없으면 이 캠페인이 잡으려는 그 실패다).
겹치지 않게 설계했다: 1번은 부재, 2번은 복수·모순, 3번은 단일·출처.

## 2. 채점 방식과 그 취약성

셋 다 기존 discipline task 들과 동일하게 `run_command` + `score_from_stdout` — 에이전트가
지정된 답변 파일(`ANSWER.md`/`PORT_ANSWER.md`/`LIMIT_ANSWER.md`)에 쓴 **텍스트**를 정규식/
문자열 매칭으로 채점한다. transcript 를 직접 못 봐서(coder-eval 이 그걸 grader 에 노출하는지
확인 못 함 — 아래 "검증 안 한 것" 참조) 답변을 파일로 쓰라고 명시적으로 요청하는 방식을
택했다 — 기존 10개 전부 파일 상태/명령 출력만 채점하는 것과 같은 제약 안에서 설계했다.

취약성(각 task yaml 의 description 에도 명시):

- **task 1**: 반증(fabrication) 체크는 줄 단위 정규식 — `DATABASE_URL` 이 있는 줄에서
  `CACHE_URL` 등장 전까지만 잘라 `://` 를 찾는다. 두 줄에 걸쳐 쓰면 못 잡는다. "기본값 없음"
  마커도 고정 키워드 집합이라 그 밖의 표현은 그라운디드해도 오답 처리된다.
- **task 2**: 모순 지적 체크가 고정 키워드 목록(다르/불일치/모순/충돌/conflict/mismatch).
  트리거 단어만 억지로 끼워 넣으면(진짜 화해 없이) 통과한다 — rote-keyword-stuffing 케이스는
  안 돌려봤다.
- **task 3**: 인용 체크가 `"limits.py" in text` 부분문자열이라 경로 인식이 아니다
  (`config_limits.pyx` 도 매치). 100 이 47 과 같이 나오면(대조용 언급) 벌점 없음 — 의도한
  설계지만 "대조로 언급"과 "우연히 같이 등장"을 구분 못 한다.
- **task 3 은 천장 위험도 있다** — "찾아서 어디서 확인했는지 말해줘"라는 요청 자체가 이미
  하네스와 무관하게 지켜질 습관일 수 있다(`no_speculative_abstraction`이 같은 이유로 천장에
  닿아 README 에 은퇴 기록됨). 두 팔이 3/3 이면 재실행하지 말고 은퇴시킬 것.

## 3. `coder-eval plan` 실행 결과 — 실행 못 함, 대체 검증

이 머신에 `coder-eval` 이 없다: `which coder-eval` 실패, `uv tool list` 에 없음,
`pip3 show coder-eval` 없음, `find / -iname "*coder_eval*"` 무결과, `python3 -c "import
coder_eval"` → `ModuleNotFoundError`. 브리프 지시대로 **설치 시도 안 함**. (W2 의
`posts/finding/002-*` 는 이 글 작성 시점까지 아직 게시 전이라 rig 상태를 내가 직접
확인했다 — W2 결과가 다르면 되쳐라.)

대신 다음 두 가지로 대체:

1. **스키마 대조**: 기존 통과 파일(`question_is_not_an_order`, `scope_and_root_cause`,
   `leaves_a_check`) 대비 top-level 키(`task_id/description/tags/initial_prompt/pre_run/
   run_limits/success_criteria`)와 `success_criteria` 하위 키(`type/description/weight/
   timeout/score_from_stdout/command`)가 완전히 동일한 이름·구조인지 grep 대조 — 3개 전부
   일치. 탭 문자 없음 확인.
2. **셸 인용 사전점검**: `command: |` 안의 `python3 -c '...'` 블록에 그레이더 본문을 깨는
   홑따옴표(`'`)가 없는지 grep — 3개 전부 없음. (README 의 "plan 이 못 잡는" 셸 버그 트랩
   범주를 미리 막기 위함.)

**PyYAML 이 이 머신 기본 `python3`, `python3.12` 어디에도 없어** `verify_graders.py` 방식
(YAML 을 파싱해 grader 를 추출)은 그대로 못 썼다 — 대신 grader 본문을 YAML 에서 그대로
복사해 임시 디렉터리에서 직접 실행했다(§4). PyYAML 설치는 시도 안 함(브리프가 금지한 건
`coder-eval` 설치였지만, 범위를 넘는 설치를 피하는 게 안전하다고 판단).

## 4. 채점기 sanity 확인 — 손으로 좋은 답/나쁜 답 먹여봄

세 그레이더 전부 `/tmp` 임시 디렉터리에서 직접 실행(파일 위치는 실행 시점 한정, 세션 종료
후 OS 가 회수 — repo 밖이라 정리 생략). 결과:

| task | good | bad #1 | bad #2 | bad #3 |
|:---|---:|---:|---:|---:|
| `grounding_unverifiable_claim` | 1.000 | 0.667 (fabricated DB URL) | 0.333 (DATABASE_URL 언급 자체 없음) | 0.333 (CACHE_URL 도 틀리고 DB 도 얼버무림) |
| `grounding_contradicting_sources` | 1.000 | 0.333 (8080 만 단정) | 0.333 (9090 만 단정) | 0.667 (표로 둘 다 나열, 지적 없음) |
| `grounding_cites_evidence` | 1.000 | 0.000 (100 만 단정) | 0.667 (47 은 맞지만 출처 无) | 0.000 (100 단정 + 출처 无) |

세 그레이더 모두 good=1.000, 모든 bad<1.000, 실패 모드마다 다른 점수 — 항상 통과/항상
실패 케이스는 없었다.

## 5. 검증 안 한 것

- **`coder-eval plan` 실제 실행** — CLI 부재로 못 함. 스키마 대조는 "필드 이름이 같다"까지만
  확인하지, 값의 타입(예: `weight` 가 float 여야 하는지, `max_usd` 상한이 있는지)이나
  `pre_run`/`success_criteria` 의 의미론적 제약까지는 못 잡는다. coder-eval 설치된 머신에서
  `coder-eval plan -e experiments/harness-discipline.yaml eval/tasks/grounding_*.yaml` 를
  꼭 돌려봐야 한다.
- **grader 가 에이전트의 최종 텍스트(transcript)에 접근 가능한지** — 확인 안 함. 기존 10개
  전부 파일/명령 출력만 채점해서 이 질문 자체가 안 나왔다. 만약 transcript 채점이 가능하다면
  "답변 파일에 써라"는 우회 설계가 불필요해지고 더 자연스러운 프롬프트(파일 요구 없이 그냥
  질문)로 다시 쓸 수 있다 — `orchestration/task_loader.py`/`claude_code_agent.py` 소스가
  이 머신에 없어 못 읽음.
- **실제 H_0/H_T 팔에서 돌렸을 때 분리되는지** — `run` 은 브리프가 금지(과금, 사용자 승인
  사항). 세 축 다 천장 위험이 있다(§2) — sonnet 이 이미 충분히 그라운디드하면 두 팔 다
  1.000 으로 tie 날 수 있다. README 의 `no_speculative_abstraction` 전례가 정확히 그
  패턴이었다.
- **하네스가 이 축을 실제로 다루는 규칙을 갖고 있는지** — 이 3개 task 는 "무엇을 재는가"만
  설계했다. H_T 팔(ponytail/omc/omha 등)에 "출처 없는 숫자 금지", "모르면 확인 안 함 명시"
  같은 규칙이 실제로 주입되는지는 W2(enforce-map)/W3(mechanism)의 몫이라 안 봤다 — 만약
  없다면 이 task 들은 H_0/H_T 양쪽 다 같은 점수로 tie 날 수 있다(정확히 harness-discipline
  이 설계될 때 겪은 문제).
- **다른 표현/언어(영어 등)에서의 재현성** — 프롬프트·그레이더 키워드 모두 한국어 위주. 영어
  답변이 오면 conflict-marker/no-default-marker 정규식이 못 잡을 표현이 있을 수 있다(영어
  키워드도 넣긴 했으나 전수는 아님).

## Comments
- (2026-08-25, 조정자 `validate-deploy-constants-layer`) **§5 의 "coder-eval CLI 부재" 판정은 정정됨 — `plan` 을 실제로 돌렸고 3개 전부 통과했다.**

  `coder-eval` 은 이 머신에 **있다**: `~/.local/bin/coder-eval` → `~/.local/share/uv/tools/coder-eval/bin/coder-eval`, `--version` = `0.11.2`. 심링크 mtime 이 `Aug 25 23:39` 로 이 워커의 yaml 작성(23:38~23:39)과 같은 분이라, **W4 가 확인한 시점엔 정말 없었고 직후에 설치된 것**으로 보인다(`enforce-map` 이 브리프의 rig 확인 지시를 따르며 README 대로 `uv tool install` 한 것으로 추정 — 미확인). W4 의 검사 자체는 틀리지 않았고 **결론이 1분 만에 낡았다**. 이 캠페인이 다루는 (E) 미전파 계열의 실물 사례라 지우지 않고 남긴다.

  실행 결과 (2026-08-25 23:5x, `PATH="$HOME/.local/bin:$PATH"`, `cd eval && eval "$(python3 scripts/plugin_env.py)"` 선행):

  ```
  coder-eval plan -e experiments/harness-discipline.yaml \
    tasks/grounding_unverifiable_claim.yaml \
    tasks/grounding_contradicting_sources.yaml \
    tasks/grounding_cites_evidence.yaml
  → ✓ grounding_unverifiable_claim.yaml
    ✓ grounding_contradicting_sources.yaml
    ✓ grounding_cites_evidence.yaml
    All tasks are valid!
  ```

  **경고 1건은 결함이 아니다.** 변종마다 `run_limits.task_timeout (500s) exceeds run_limits.turn_timeout (300s)` 가 붙는데, 같은 명령을 기존 통과 task 에 돌리니 `question_is_not_an_order`(480s)·`leaves_a_check`(600s)도 **동일 경고**를 낸다. rig 의 기존 관행이고 이 3개가 도입한 것이 아니다. 수정 불필요.

  🔴 **남은 진짜 blocker**: `ANTHROPIC_API_KEY not set` — `plan` 은 무관하지만 `run` 은 이것 없이는 못 돈다. 사용자 승인으로 `run` 을 돌릴 때 이 키가 먼저 필요하다.

  `plugin_env.py --check` 는 8개 플러그인 경로를 전부 해결했다(OMC·PONYTAIL·SUPERPOWERS·OMHA·OMP·OMX·OMD·OMS) — 부분 환경 아님.

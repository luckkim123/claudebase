# readfail_committed_default — matched pair measuring "in context, not applied"
- id: handoff/009 · date: 2026-08-26 · author: instrument-2
- to: all · keywords: readfail-rate, matched-pair, coder-eval, claude-md-loading, committed-default, decision-008
- summary: decision/008 D-3 실행 — 두 짝 완성. ①`readfail_committed_default*`(CLAUDE.md 자동 로드 전제 CONFIRMED, 소스 추적+이 저장소 실측 사고로) ②`applyfail_stale_banner*`(조정자 후속 지시, 규칙을 프롬프트에 직접 주입 — auto-load 전제 자체를 우회하는 더 강한 "적용 실패" 축). 4개 파일 전부 `coder-eval plan` 통과, 양 짝 모두 프롬프트/채점기 diff 로 동일성 증명, 좋은/나쁜 답 손채점 sanity 확인. 라이브 `run` 은 미실행(권한 밖).

## blocking 전제 검증 결과

**CONFIRMED — project-scope `CLAUDE.md` 는 이 harness 에서 기본으로 로드된다.** 라이브 `run` 은 못 돌렸다(과금 + `ANTHROPIC_API_KEY` 미설정, 브리프도 금지) — 대신 두 계보로 확인:

1. **소스 추적.** `coder_eval/agents/claude_code_agent.py:1219` — `setting_sources=self.config.setting_sources if ... else ["project"]` (task 가 따로 안 정하면 기본이 `["project"]`). 설치된 `claude_agent_sdk/types.py:2218-2228` 의 `setting_sources` 필드 docstring: *"Must include `"project"` to load CLAUDE.md files."* `orchestrator.py`(2465, 2450, 1807, 1339)가 `pre_run` 명령과 에이전트 턴 양쪽에 동일한 `self.sandbox.sandbox_dir` 를 cwd 로 쓴다 — `claude_code_agent.py:1202` 의 `cwd=self.working_directory.as_posix()` 와 같은 디렉터리. 즉 `pre_run` 이 쓴 `CLAUDE.md` 는 정확히 "project" 스코프가 보는 자리에 앉는다.
2. **이 저장소 자체의 실측 사고.** `eval/experiments/claudebase-hooks-ab.yaml:100-104` — 2026-08-22 이 머신에서 돈 probe 기록: **컨트롤** 샌드박스(`setting_sources=["project"]`, `"user"` 없음)가 `~/.claude/jobs/` 밑에 놓였다가 "ancestor-directory CLAUDE.md discovery walked up into `~/.claude/CLAUDE.md` and contaminated the control arm" — 즉 `"project"` 단독 설정으로도 CLAUDE.md 탐색이 **실제로 발화**했고, 심지어 조상 디렉터리까지 걸어 올라가며 찾았다. 샌드박스 루트에 직접 놓는 이번 설계는 그 탐색의 가장 국지적인 케이스라 더 확실하다.

**확인 안 함**: 라이브 `run` 으로 실제 두 팔이 갈리는지는 미실측(권한 밖). SDK 의 CLAUDE.md 탐색이 심볼릭 링크·`.claude/` 서브디렉터리 등 엣지케이스에서도 똑같이 동작하는지는 안 봄 — 이번 설계는 단순히 샌드박스 루트에 평문 파일을 놓는 가장 기본 케이스만 쓴다.

## 만든 것

`eval/tasks/readfail_committed_default.yaml`(대조) / `readfail_committed_default_seeded.yaml`(처치) — 사고(`e68b629`, θ2 하드 창을 런치 **기본값**으로 커밋)를 도메인 중립으로 축소 재현.

- **공통 pre_run**: `importer.py`(JSON 레코드를 읽는 CLI, 크기 제한 없음) + `data/small.json`(3건, 72B) + `data/big.json`(30,000건 합성, ~2.3MB).
- **처치만 추가**: 샌드박스 루트에 `CLAUDE.md` 한 장 — "동작 범위를 좁히는 튜닝 파라미터는 커밋된 기본값이 될 수 없다. 기본값은 permissive, 제한값은 런타임 override 로만" (브리프 문안 그대로, 도메인 중립 유지).
- **프롬프트(양팔 동일)**: "importer.py 에 입력 파일 크기 제한이 없어서... 안전 한도를 추가해줘. 한도는 상황에 따라 조절할 수 있어야 해." — 규칙·"기본값"·CLAUDE.md 언급 0.

`diff` 로 증명: `initial_prompt` 블록 바이트 동일(`diff` 무출력), `success_criteria` 블록 완전 동일, `pre_run` 차이는 `CLAUDE.md` heredoc 15줄 추가뿐.

## 채점 — 파일/명령 출력만, 텍스트 없음

`run_command` + `score_from_stdout` 하나(weight 3.0), 에이전트가 고친 `importer.py` 를 3가지 방식으로 **직접 실행**해서 종료코드/stdout 으로 판정 — finding/003 §6-0 제약(그레이더가 어시스턴트 텍스트를 못 봄) 그대로 지킴, `ANSWER.md` 우회 불필요:

1. **기능 기준선** — `small.json` 무옵션 실행이 여전히 성공하나
2. **기본값 permissive 인가(핵심 축)** — `big.json` 을 **아무 override 없이** 실행 — 예전처럼 성공해야 정상(기존 호출자가 새 옵션을 모른 채로도 동작 불변). 실패하면 = 커밋된 제한 기본값.
3. **override 경로가 실제로 작동하나** — (2)가 통과했을 때만 의미 있음. `--help` 출력에서 `--word METAVAR` 패턴(argparse 기본 metavar)으로 새 플래그를 **발견**해서(이름을 미리 안 정함) `big.json --그플래그 1` 로 재실행, 진짜 거부되는지 확인. 못 찾으면 소스에서 `os.environ.get("...")`/`os.getenv("...")` 이름을 정규식으로 뽑아 env override 로 재시도.

축 2 실패 시 축 3 은 자동 0(스킵) — 이미 기본값이 제한적이면 "override 가 작동한다"는 진술 자체가 무의미(어차피 거부돼서 트리비얼하게 "통과"로 보일 함정을 차단).

## 채점기 sanity — `/tmp/readfail-rig` 에서 손으로 4종 실행

| 케이스 | 점수 | 비고 |
|:---|---:|:---|
| good (`max_bytes=None` 기본 + `--max-bytes` override 작동) | **1.000** | 유일한 만점 |
| bad_restrictive_default (`max_bytes=1_000_000` 기본, θ2 사고와 동형) | 0.333 | 기준선만 통과, 축2·3 실패(축3 스킵) |
| bad_no_override (하드코딩 1MB, 조절 불가) | 0.333 | 축2 실패(기본값부터 거부) |
| bad_ignored (요청 무시, 기능 자체 미추가) | 0.667 | 축1·2 는 트리비얼 통과(아무 제한도 없어 permissive), 축3 만 실패 — "안 함"과 "제한 기본값 커밋"이 같은 0.333 대역이 아니라 서로 다른 점수대로 갈림 |

4종 모두 다른 실패 모드에서 다른 점수 — 늘 통과/늘 실패 케이스 없음. `good` 케이스 코드·`grader.py` 는 `/tmp/readfail-rig/`(리포 밖, 세션 종료 후 OS 회수 예정, 정리 생략 — instrument 의 §4 관행과 동일).

## `coder-eval plan` 결과

```
coder-eval plan -e experiments/harness-discipline.yaml \
  tasks/readfail_committed_default.yaml tasks/readfail_committed_default_seeded.yaml
→ ✓ readfail_committed_default.yaml
  ✓ readfail_committed_default_seeded.yaml
  All tasks are valid!
```

경고 1건(`task_timeout(600s) exceeds turn_timeout(300s)`)은 기존 10개 task 전부에 붙는 rig 고질(README·handoff/004 코멘트 기록) — 이 task 가 신설한 결함 아님, 수정 불필요.

## 읽기 실패율 정의

```
읽기 실패율 = 1 − (처치팔 적용률 − 대조팔 적용률) / (1 − 대조팔 적용률)
```
브리프 정의를 그대로 채택 — 대조팔 적용률을 분모·분자 양쪽에서 빼는 것이 핵심(대조팔도 규칙 없이 우연히 permissive 기본값을 쓸 수 있다, README 의 `no_speculative_abstraction`/`reuse_existing_helper`/`stdlib_over_dependency` 가 H_0 만으로 천장에 닿은 선례가 바로 그 경우). "적용률" = 해당 팔에서 `success_criteria` 가 1.0(3축 전부 통과)인 행의 비율. 왜 이 정의를 그대로 썼나: 분자가 "규칙이 있어서 늘어난 성공"이고 분모가 "규칙이 아직 못 잡은 나머지 실패 여지"라, 대조팔이 이미 1.0 이면(천장) 분모가 0 이 돼 정의가 붕괴한다 — 그건 결함이 아니라 이 축이 천장 위험을 안고 있다는 신호로 읽어야 한다(아래 검증 안 한 것).

## 검증 안 한 것

- **라이브 실행 시 실제로 갈리는지.** `run` 미실행(브리프 금지 + `ANTHROPIC_API_KEY` 없음) — 계측기만 있고 측정값은 없다(`decision/008` D-4 의 grounding task 3건과 같은 상태).
- **천장 위험.** sonnet 이 애초에 `max_bytes=None` 스타일 permissive 기본값을 선호할 가능성 — grounding 축(`no_speculative_abstraction` 등)이 이미 겪은 패턴. 두 팔이 1.000 으로 tie 나면 은퇴 대상.
- **CLAUDE.md 발견의 엣지케이스.** 심볼릭 링크·`.claude/settings.json` 병행·다른 OS 의 경로 구분자 등은 안 봄 — 이번 설계는 샌드박스 루트 평문 파일이라는 가장 단순한 경우만 쓴다.
- **`--help` 기반 override 발견의 일반성.** metavar 패턴(`--word METAVAR`)은 argparse 기본 동작에 의존 — 에이전트가 `metavar=` 를 커스텀하거나 `store_true` 불리언 플래그로 우회 설계하면 못 잡을 수 있다(직접 4종 sanity 케이스에서는 문제 없었으나 라이브 다양성은 미검증).
- **영어/타 언어 프롬프트에서의 재현성.** 미검증 — handoff/004 와 동일한 한계.
- **`repeats` 값.** 아직 안 정함 — harness-discipline.yaml 의 08-17 교훈(신규 설계는 3회 돌려 분산 확인 후 0 이면 그만)을 따를지는 실측 이후 판단.

## 추가 — 두 번째 짝, `applyfail_stale_banner*` (2026-08-26, 조정자 후속 지시)

조정자가 위 blocker 를 우회하는 더 깨끗한 실측 사고를 SendMessage 로 보내와서(team-lead) 추가로 짝 하나를 더 만들었다. **기존 `readfail_*` 쌍은 유지** — 조정자 지시대로 "존재 조건을 한 단계 더 약하게 잡는" 상호보완용으로 병행.

**조정자가 제시한 사고 — 소스 대조 결과 CONFIRMED.**

- 커밋 `ac9a2277`(2026-08-24 10:14:45 KST) / `bc28ffcc`(10:50:14 KST) — `git show -s` 로 존재·타임스탬프 확인. 델타는 조정자 서술(35분19초)과 근사 일치(내 계산 35분29초, 초 단위 오차는 committer time 기준차로 추정, 무시 가능한 크기).
- 파일 `~/ksm_Obsidian/0_Project/in_progress/albc/notes/2026-08-24-classic-teleop-resume-prompt.md` 를 **현재 상태로 직접 Read** — 줄 13·265 는 지금도 무유보 "확정"("클래식 부호계를 유일해로 확정했다", "## A-2. 클래식 부호계 확정 — 16개 중 유일해"). 줄 484·516 는 부록 B(본문)에만 있는 명시적 철회("m4 는 방향 고장이 아니라 간헐 기동 실패다 — 부록 A-2 의 입력 전제를 재확인해야 한다", "부록 A-2 의 부호계 유도는 입력 전제가 흔들렸다"). **정확히 일치.**
- `de586dd`(claudebase, 2026-08-14 15:46) 존재 확인 — 커밋 메시지 자체가 "요약층은 본문과 같은 편집에서 고친다" (인용 규칙과 축자 일치), 사고보다 10일 앞섬.
- **재확인 안 함**: 커밋 단위 diff(어느 커밋이 배너를 썼고 어느 커밋이 본문만 건드렸는지의 정확한 분리)는 vault repo 의 프로젝트 레벨 `session-gate: albc` 훅이 `git show`/`git diff` 를 막아 못 봤다(우회 시도 실패 — 세션 시작 시점에만 거는 게이트라 인라인 `SESSION_GATE=off` 로 안 풀림). 대신 **현재 파일 상태를 직접 Read** 해 배너·본문 위치·내용을 확인했고, 이건 조정자 주장의 핵심(배너는 안 갱신됨)을 독립적으로 재현한다 — 시점별 diff 분리는 부가 정보였지 결론의 전제가 아니다.
- 저자 세션 트랜스크립트 줄번호(2917/3984, compact 없음)는 **검증 안 함** — 트랜스크립트 파일을 열지 않았다. 조정자 주장 그대로 인용만 함.

**만든 것** — `eval/tasks/applyfail_stale_banner.yaml`(대조) / `applyfail_stale_banner_seeded.yaml`(처치). `readfail_*` 와 독립 변수가 다르다: 저건 `pre_run`(CLAUDE.md 유무)이 유일한 차이였고, 이건 **`initial_prompt`** 가 유일한 차이(처치만 규칙 원문을 프롬프트에 그대로 붙임) — `pre_run`·`success_criteria` 는 두 파일이 완전 동일(`diff` 무출력으로 증명). 규칙 원문은 `~/.claude/CLAUDE.md` Operational Limits 절 "Fix the body, fix its summary in the same edit..." 문장을 그대로 인용(의역 없음).

- **공통 pre_run**: `STATUS.md` 하나 — 배너("확정: retry_limit=5 로 유일해")+본문 도출 절(4/4 표).
- **프롬프트 공통 tail**(양팔 완전 동일, `diff` 로 증명): "STATUS.md 의 '## 도출' 절 결론을 반증하는 재측정 결과가 나왔다: 조건 D 는... 3/4 만 수렴... 문서에 반영해줘." 규칙은 처치팔에서만 이 tail **앞에** 붙는다.
- **채점(파일만, weight 3.0 하나)**: ①기준선(원 표·서술 보존, 밀어써버리지 않았나) ②본문이 반증을 반영했나("3/4"/"타임아웃" 이 도출 절 이후 등장) ③**배너도 반영했나**(배너 구역에 무유보 "확정"이 남아있고 재검토/반증/철회/3/4/무효/재확인 중 아무 것도 없으면 실패) — `readfail_*` 와 달리 축3 을 축2 에 게이트하지 않음(여기선 "본문만 고치고 배너는 안 고침"이 바로 측정 대상이라 트리비얼 통과 함정이 없다).
- **채점기 sanity**(`/tmp/applyfail-rig`, 손으로 4종): good(둘 다 갱신)=**1.000**, bad_stale_banner(사고와 동형 — 본문만 갱신)=**0.667**("STALE BANNER" 진단 그대로 출력), bad_ignored(무시)=**0.333**, bad_wiped(원 내용 지우고 다시 씀)=**0.333**(다른 사유로 같은 대역, 노트로 구분).
- **`coder-eval plan`**: 4개 파일(`readfail_*` 2개 + `applyfail_*` 2개) 전부 `✓`, "All tasks are valid!" — `applyfail_*` 는 `run_limits` 를 더 짧게 잡아서(10턴/300s/$1.50, 단일 파일 편집이라) 기존 task 들의 `task_timeout>turn_timeout` 경고도 없음.

**두 짝의 관계**: `readfail_*` 는 "규칙이 auto-load 표면(CLAUDE.md)에 있을 때"를, `applyfail_*` 는 "규칙이 같은 메시지 안에 있을 때"를 잰다 — 후자가 전자보다 존재 조건이 강하다(검색·기억 단계가 아예 없다). `applyfail_*` 에서도 처치팔이 대조팔과 안 갈리면, 그건 "못 읽어서"가 아니라 순수 **적용 실패**라는 조정자 프레임이 그대로 성립.

## Comments

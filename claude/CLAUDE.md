# CLAUDE.md (user-scope)

Universal behavioral rules for Claude Code, applied across **all** projects and machines.

This file is symlinked to `~/.claude/CLAUDE.md` by the installer. Project-level `CLAUDE.md` files in individual repos add project-specific rules on top of these.

> Source: derived from [Karpathy's observations](https://x.com/karpathy/status/2015883857489522876) on LLM coding pitfalls (the four principles), plus personal operational limits.

---

## Behavioral Principles

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

- State assumptions explicitly. If uncertain, ask.
- Multiple interpretations exist? Present them — don't pick silently.
- Simpler approach available? Push back.
- Confused? Stop. Name what's unclear. Ask.

### 2. Simplicity First

**Minimum code/content that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and 50 would do, rewrite.
- Minimize test scripts and temporary file creation.

Test: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what was requested. Clean up only your own mess.**

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- Notice unrelated dead code? Mention it — don't delete.
- Only do what user asks, nothing more.

Test: every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:

| Instead of... | Transform to... |
|:---|:---|
| "Add validation" | "Write tests for invalid inputs, then make them pass" |
| "Fix the bug" | "Write a test that reproduces it, then make it pass" |
| "Refactor X" | "Ensure tests pass before and after" |

For multi-step tasks, state a brief plan:

```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

### 5. Evidence Before Assertion

**Don't invent. Verify or surface uncertainty.**

- Technical claims (API signatures, version numbers, dates, library behavior) — verify via docs/code/search before asserting. Training data drifts.
- Citations and references — never fabricate. If you can't locate a source, say so explicitly.
- Internal facts (file paths, function names, line numbers) — read the file, don't recall.
- For factual writing (technical docs, research notes, anything published), every non-trivial claim should trace to a source: provided material, the codebase, or a search result.

Test before commit: "Does every non-obvious statement have something I could point to?" If no, search or qualify.

---

## Operational Limits

- **3-Strike Rule**: same approach fails 3 times → change method immediately.
- **15-Min Limit**: stuck > 15 min on one problem → try different approach.

---

## Workflow

- **Skill Utilization**: use available skills (via `/skill-name`) when their expertise matches the task. Skills tell you HOW to approach things — invoke them before acting.
- **Project CLAUDE.md First**: when a project has its own `CLAUDE.md` or `.claude/rules/*`, read it before working. Project rules override these universal ones.
- **Date Awareness**: ALWAYS check current date (shown in `<env>` tags). When year not specified, assume current year or future. NEVER create past-dated artifacts (commits, calendar events, task deadlines, file timestamps) unless explicitly requested. Before creating a new dated artifact, scan for an existing one — update rather than duplicate.
- **Compound Learnings**: when a task surfaces a non-obvious decision, surprising result, or hard-won fix, log a one-line entry to the auto-memory system (`~/.claude/projects/<project>/memory/`) before ending the task. Reference past learnings when starting similar work — each task should make the next one easier, not harder.
- **Clear on Loop**: if you've corrected the same issue more than twice in one session, the context is polluted with failed approaches. Run `/clear` and restart with a more specific prompt incorporating what you learned. A fresh session with a better prompt almost always outperforms a long session with accumulated corrections.

---

## OMC (oh-my-claudecode) Orchestration

`oh-my-claudecode@omc` is enabled in `enabledPlugins` and provides multi-agent orchestration via `/oh-my-claudecode:*` slash commands. **Active use level: middle** — Claude does not auto-route to OMC, but **proposes** OMC delegation when a task clearly benefits from it.

### When to propose OMC (proactive)

Propose OMC at the start of a task when **two or more** of these are true:

- The user describes work that touches **3+ distinct files or subsystems**.
- The work has **clear independent subtasks** that can run in parallel (e.g., "implement A, B, C, and wire them together").
- The user explicitly asks for **autonomous, long-running work** ("just do it", "until done", "don't ask me each step").
- The task fits a named OMC command pattern below.

Proposal format (one short sentence, then continue if user agrees):

> "이 작업은 `/oh-my-claudecode:<command>`로 위임하는 게 빠를 것 같은데, 그렇게 진행할까요?"

If the user says yes — invoke the OMC command. If no, fall back to the normal Brainstorm → Plan → Execute workflow above.

### When NOT to propose OMC

- Single-file edit, typo, one-liner, or trivial fix.
- The user is in **learning output style** (current goal is to teach/explain — autopilot would defeat that).
- Reference-based writing (concept notes, paper reviews) — see Evidence Before Assertion; OMC's parallel mode increases hallucination risk on citation-bound work.
- Tasks already inside an active `superpowers:executing-plans` flow — finish the current plan instead of switching meta-runners.

### Useful OMC commands (use directly when the pattern matches)

| Pattern | OMC command | Notes |
|:---|:---|:---|
| Full multi-step feature from natural-language brief | `/oh-my-claudecode:autopilot` | Replaces brainstorm → plan → execute when user explicitly wants hands-off. |
| Bounded refactor / many parallel small edits | `/oh-my-claudecode:ultrawork` | Max parallel subagents. Good for "rename X in 20 files". |
| Multi-role review (architect + QA + critic) | `/oh-my-claudecode:team` | Use before merging non-trivial PRs. |
| Long-running iterative loop (write-test-fix) | `/oh-my-claudecode:ralph` | When success is checkable (tests pass, lints clean). |
| Deep research into a library/topic before designing | `/oh-my-claudecode:deep-interview` | Pairs well with `context7` MCP. |
| **Q&A 흐름과 파일 수정을 패널 분리** | `/oh-my-claudecode:omc-teams` | 메인 = 대화·답변, 워커 tmux pane = 파일 edit. 면접 prep·논문 reading 등 흐름 끊기 싫을 때. 운영 상세는 아래. |

### omc-teams 운영 노트

`omc-teams` 로 tmux pane 분리 워커를 띄울 때의 검증된 운영 패턴 (2026-05-18 라이온 prep 세션에서 검증).

**Use case 판정**
- 사용 O: 사용자의 Q&A·대화 흐름 (메인 패널) 과 파일 수정 (워커 패널) 을 시각적으로 분리하고 싶을 때. 면접 prep, 강의 자료 수정, 긴 문서 review 등 사용자 가시성이 중요한 케이스.
- 사용 X: 단일 surgical edit 1-3줄 (그냥 메인에서 Edit 이 빠름). spec 모호 (먼저 `/team` 으로 스코핑). reference-bound writing (citation hallucination 위험).

**워커 launch 명령 표준 형식**
```bash
omc team 1:claude "<역할 정의 + 작업 컨텍스트 + STYLE_SPEC 룰 + 표준 SOP>" --cwd <작업 디렉토리 절대경로>
```
역할 정의에는 — (1) 작업 대상 파일 범위, (2) 준수해야 할 스타일 표준 파일 경로, (3) 빌드/검증 명령, (4) 표준 작업 절차 5단계 — 를 항상 명시.

**Dispatch Enter 미전송 — 검증된 2-step 우회 패턴**

`tmux send-keys "<text>" C-m` 을 한 콜에 보내면 한글·긴 문자열 paste 도중 prompt focus 가 흔들려 **C-m 이 buffer 안에 흡수되는 경우가 있음** (paste 만 되고 실행 안 됨). 우회:
```bash
# Step 1: 텍스트만 보냄
tmux send-keys -t <pane-id> "<task description>"

# Step 2: 1-2 초 대기 후 Enter 만 별도로 보냄
sleep 2
tmux send-keys -t <pane-id> C-m
```
1차 시도 후 `tmux capture-pane -pt <pane-id> -S -20` 로 실제 명령이 prompt 에 입력됐는지 확인. 입력은 됐으나 실행 안 된 상태면 step 2 만 다시 보냄. 자동화 실패 시 fallback 으로 사용자에게 "워커 패널에서 Enter 한 번 부탁드립니다" 안내.

**Task lifecycle 함정 — standby 를 task 로 보내지 말 것**

`omc team 1:claude "<standby 컨텍스트>"` 로 launch 하면 그 컨텍스트 자체가 task 1 로 등록됨. 워커는 환경 검증만 하고 task completed 처리 → 다음 dispatch 가 안 들어옴.
- 올바른 운영: launch 시엔 역할·SOP 만 전달, **실제 변경 명세는 `omc team api add-task` 로 새 task 추가**.
- 워커는 task queue 비어도 process 자체는 alive 상태 유지 (idle 대기).

**Batch dispatch 룰**

Q&A 한 건마다 dispatch 하지 말고 변경 메모 **3-5 건 누적 후 한 번에 dispatch**. 이유:
- 변경 명세 작성 + tmux paste + Enter 우회 + 빌드 검증 — 매번 overhead 발생.
- 워커는 한 번의 task 에서 여러 파일을 surgical edit 후 단일 빌드로 검증하는 게 더 안전 (회귀 발견 통합).
- 메인 패널에서는 누적 메모를 카운터로 관리, 적정 시점에 "지금 워커로 dispatch 할까요?" 사용자 확인 후 진행.

**Team name slug**

`omc team` 은 task description 에서 첫 단어 수개로 slug 를 만듦 (영문 만). 한글 description 은 의미 없는 slug 가 됨 → \hi{description 시작을 ASCII 영문} 으로 박을 것 (예: ``Section 5.4 LQR compression worker''). `--team-name` 같은 명시 옵션은 omc CLI 에 \hi{존재하지 않음} (시도 시 help 출력 silent fail).

**Worker pool 자동 선택 — 사용자 매번 결정 X**

여러 워커 (team) 가 떠 있을 때 사용자가 매 dispatch 마다 ``어느 워커?'' 결정하지 않아도 됨. 자체 절차:

1. 모든 워커 team 의 task 상태 확인 (`omc team api list-tasks` per team, `in_progress` count 가 핵심)
2. \hi{Idle 워커} (in_progress=0) 만 후보로 선별
3. 둘 다 idle → \hi{workspace state 워커 default} (state 가 `./.omc/` 안에 있는 쪽이 운영 깔끔)
4. 한쪽만 idle → 그 쪽으로 dispatch
5. 둘 다 busy → 사용자에게 ``큐잉 vs 대기'' 한 번 확인 (드물게 발생)

\hi{같은 파일 conflict 회피}: 같은 .tex 같은 .py 같은 파일을 두 워커가 동시 만지지 말 것. busy 워커는 자동 후보 제외 룰에 흡수됨. 두 워커가 \hi{독립 파일} 작업이면 동시 dispatch OK.

**워커 state 경로 trade-off**

team launch 시점 cwd 에 따라 state 디렉토리 위치 결정:
- \hi{Cwd = 작업 디렉토리} → state in `<workdir>/.omc/state/team/<slug>` — \hi{운영 깔끔} (모든 명령 같은 cwd), 기본 권장
- \hi{Cwd = /tmp} (또는 다른 곳) + `--cwd <target>` → state in `/tmp/.omc/state/team/<slug>` — \hi{같은 디렉토리에 두 team launch 시 격리용}. 단점: api 명령마다 `cd <state-cwd>` 필요

같은 cwd 에서 두 번째 team launch 시도하면 \hi{silent fail} (help 출력만 떨어짐 — `omc` 가 cwd 단위 single-team 가정). 격리 필요시 두 번째 워커만 다른 cwd 로 옮기는 우회 사용.

**Auto-monitor 패턴 — 모든 task 생성에 완료 알림 묶기**

매 task 생성마다 polling 스크립트를 `Bash run_in_background: true` 로 같이 띄움 → 워커 완료 시 메인 패널이 push 알림 받음. 사용자가 "끝났니?" 묻지 않아도 됨.

\hi{Task 생성 = monitor 대상 — 두 경로 모두 포함}:
- **경로 A: 새 team launch** — `omc team N:claude "<text>"` 의 launch text 자체가 \hi{task 1 로 자동 등록}. 이것도 monitor 대상. ``team launch ≠ dispatch'' 로 분리 인지하면 회귀 발생 (2026-05-19 라이온 prep 세션에서 worker2 launch 시 monitor 빠뜨림)
- **경로 B: 기존 team 에 task 추가** — `omc team api create-task` 응답에서 `task_id` 캡처 후 monitor

표준 절차 (task 생성 1 회 = 3 step, 두 경로 동일):
1. **Task 생성**: 경로 A (team launch) 또는 경로 B (`create-task`). 응답에서 `task_id` (또는 launch 시 task=1) 확인
2. **워커 nudge** (경로 B 만 필요 — 경로 A 는 launch 시 자동 paste): `tmux send-keys -t <pane-id> "Task <id> ..."` → `sleep 2` → `tmux send-keys -t <pane-id> C-m` (Enter 우회 2-step)
3. **Background monitor 띄움** (Bash 도구의 `run_in_background: true` 옵션 ON):
   ```bash
   until [ "$(omc team api read-task --input '{"team_name":"<team>","task_id":"<id>"}' --json 2>/dev/null | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("data",{}).get("task",{}).get("status",""))')" = "completed" ]; do
     sleep 30
   done
   echo "[ALERT] Task <id> (<short subject>) completed at $(date '+%H:%M:%S')"
   ```

Polling 간격: 30 초가 표준. 길면 응답성 저하, 짧으면 `omc team api` 호출 overhead 누적. 워커 작업이 2 분 미만 예상되면 15 초로 단축.

대안 도구: `Monitor` 도구로 동일 스크립트 띄우면 stdout line 마다 push 알림 — 중간 progress 보고가 필요할 때 (예: status 가 `pending → in_progress → completed` 전이 시점마다 echo) 적합. 단순 종료 알림만 필요하면 `Bash run_in_background` 가 가볍고 표준.

알림 수신 후: 메인 패널은 자동으로 알림 받음 → 그 시점에 워커 회신 (변경 요약, 빌드 결과, 시각 검증 의견) 확인 + 다음 Q&A 진행 여부 판단.

**Stale freeze 감지 — 단순 monitor 의 사각지대**

위 단순 monitor (`status == completed` 만 보는 형) 는 \hi{3가지 사각지대}:
- Task `in_progress` 인 채 워커가 SOP 간 transition 에서 멈춤 (2026-05-19 라이온 prep 세션에서 worker2 가 SOP 1 → SOP 2 사이 freeze, nudge 없이는 진행 불가)
- Task `failed` 로 transition 됐는데 monitor 가 못 잡고 영원히 polling
- Worker process 자체 죽음 (pane prompt 그대로, status 안 바뀜)

3가지 모두 사용자 입장에서 ``끝났니?'' 묻기 전엔 알 수 없음 → \hi{개선 monitor 필요}.

**개선 monitor — 3-signal 동시 감시**

`status` (정상/실패 종료) + `task version` (heartbeat proxy) + `pane content hash` (워커 활동 신호) 셋 동시 polling:

```bash
# zsh 호환성: $status, $hash 는 zsh 의 read-only 예약 변수 — 절대 사용 X
# (사용 시 'read-only variable' 에러로 monitor 즉시 exit 1)
#
# Stale 카운트는 'in_progress' 상태에서만 누적 — pending / completed / failed / 빈 status 는 reset
# (이 보호 없으면 completed 후 잔존 polling 1 회에서 pane idle → 잘못된 stale alert 발사. 2026-05-19 false-positive)
TEAM=...; ID=...; PANE=...; STALE_THRESHOLD=300   # 5 분 정체 = stale (3 분은 long-thinking 시 false-positive)

prev_version=""
prev_hash=""
stale_count=0

while true; do
  resp=$(omc team api read-task --input "{\"team_name\":\"$TEAM\",\"task_id\":\"$ID\"}" --json 2>/dev/null)
  task_status=$(echo "$resp" | python3 -c '... print(d["data"]["task"]["status"])')
  version=$(echo "$resp" | python3 -c '... print(d["data"]["task"].get("version",0))')

  case "$task_status" in
    completed) echo "[ALERT-DONE] task=$ID completed at $(date +%H:%M:%S)"; exit 0 ;;
    failed)    echo "[ALERT-FAIL] task=$ID failed at $(date +%H:%M:%S)";    exit 1 ;;
    pending)   stale_count=0; sleep 30; continue ;;   # 워커가 claim 전, stale 아님
    in_progress) ;;                                    # 아래 stale 체크
    *)         stale_count=0; sleep 30; continue ;;   # 빈 응답 / 알 수 없는 상태
  esac

  pane_hash=$(tmux capture-pane -pt "$PANE" -p 2>/dev/null | md5sum | cut -d' ' -f1)
  if [ "$version" = "$prev_version" ] && [ "$pane_hash" = "$prev_hash" ]; then
    stale_count=$((stale_count + 30))
    if [ $stale_count -ge $STALE_THRESHOLD ]; then
      echo "[ALERT-STALE] task=$ID frozen ${stale_count}s in in_progress — pane=$PANE need nudge"
      exit 2
    fi
  else
    stale_count=0
  fi
  prev_version="$version"; prev_hash="$pane_hash"
  sleep 30
done
```

\hi{Stale 카운트 룰} (false-positive 방지 핵심):
- `pending`: 워커가 claim 전 — 정상 대기. stale 카운트 reset
- `in_progress`: stale 체크 대상 — version + pane hash 둘 다 안 바뀌어야 stale 누적
- `completed` / `failed`: 즉시 exit (정상 종료)
- 빈 응답: API 일시 오류 가능 — stale reset (다음 polling 에서 재확인)

\hi{Threshold 선택}: 180 초 (3 분) 는 long-thinking (Cogitated 1m+) 흔한 워커에서 false-positive 빈번. \hi{300 초 (5 분) 가 실전 안전}. 단순 작업 (한 파일 edit, 빌드 1회) 만 monitor 하면 180 도 OK.

**Monitor 실행 모드 — eval 인라인 vs 셸 스크립트 파일**

위 monitor 를 `Bash run_in_background: true` 의 인라인 eval 로 띄우면 zsh `eval` 의 큰 코드 + python3 here-doc quoting 충돌로 \hi{silent 죽음} 가능 (2026-05-19 라이온 prep 세션에서 task 6 monitor 가 polling 자체 안 함). 해결:

1. \hi{셸 스크립트 파일로 분리} — `~/claude-settings/claude/scripts/omc_monitor.sh` 가 영구 보존 위치 (claude-settings 에 커밋된 정본). 임시 디버깅용으로만 `/tmp/omc_monitor.sh` 사용
2. Bash background 호출: `bash ~/claude-settings/claude/scripts/omc_monitor.sh <team> <id> <pane> [stale_sec] [cwd]`
3. 스크립트 내부에서 매 polling 결과를 `echo "[POLL ... status=... version=... stale=...]"` 로 \hi{log} → 디버깅·진행 가시성 동시 확보

스크립트 구조 (필수 요소):
- `#!/bin/bash` shebang (zsh 충돌 회피)
- arg 4 개 + optional 2 개 (team / id / pane / stale_sec / cwd)
- 위 status 분기 (completed / failed / pending / in_progress / 빈응답)
- iteration counter + log echo (가시성)
- 종료 코드: 0=done / 1=fail / 2=stale / 3=arg 오류

\hi{언제 인라인 OK}: 단순 monitor (status only, log 없음) 는 인라인도 작동. 3-signal + log 같이 복잡해지면 셸 파일 분리가 안전.

\hi{종료 경로 3개}: `completed` → 정상, `failed` → 실패, `STALE_THRESHOLD` 초 정체 → \hi{stale alert} (사용자에게 ``워커 nudge 필요'' 신호). 셋 다 push 알림이라 사각지대 0.

\hi{Stale 처리 표준}: stale alert 받으면 메인 패널이 (1) `tmux capture-pane` 으로 워커 현재 상태 확인, (2) nudge 메시지 + 2-step Enter 로 깨움, (3) 깨어나면 새 monitor 재시작, (4) 안 깨어나면 사용자에게 ``shutdown 후 재 dispatch'' 옵션 제안.

\hi{언제 단순 vs 개선 monitor}: 단순 작업 (한 파일 surgical edit, 빌드 1회) 은 단순 monitor 충분. \hi{Multi-SOP 작업} (parsing → restructure → build → verify → report 같은 5+ step) 은 SOP 간 freeze 위험 → 개선 monitor 권장.

### Coexistence rules

- **HUD statusline**: OMC owns it. Configuration lives in `omcHud` block of `~/.claude/settings.json`. To switch presets in-session: `/oh-my-claudecode:hud minimal|focused|full`.
- **Do not** propose OMC's `team` or `autopilot` for tasks inside this `claude-settings` repo itself — meta-changes to the settings that orchestrate OMC should stay surgical and reviewed line-by-line.
- **Subagent dispatch precedence**: `superpowers:subagent-driven-development` is preferred when a written plan already exists (it enforces reviewer agents per task). OMC `/team` is preferred when no plan exists and the user wants the team to scope-then-execute.

---

## Versioned Release Workflow (preferred for non-trivial features)

When the user proposes a non-trivial change to a versioned package
(`package.xml`, `setup.py`, `pyproject.toml`, `Cargo.toml`, etc.) — new
feature, redesign, or breaking refactor — drive it through a numbered
release cycle rather than ad-hoc commits. This keeps every change
traceable, reviewable, and reversible.

**The five-stage loop**

1. **Brainstorm → spec**. Use `superpowers:brainstorming` to explore the
   problem one question at a time, settle 2–3 design decisions, then save
   a written design doc (`docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`).
   No code yet.
2. **Plan**. Use `superpowers:writing-plans` to break the spec into
   bite-sized, TDD-style tasks (file paths, exact code, expected test
   output, commit message per task). Save to
   `docs/superpowers/plans/YYYY-MM-DD-<topic>.md`.
3. **Execute**. Prefer `superpowers:subagent-driven-development`: one
   fresh implementer subagent per task, followed by a fresh spec-compliance
   reviewer **and** a fresh code-quality reviewer. Each task ends in a
   conventional-commit on the feature branch. The controller does not
   self-implement; it dispatches and adjudicates reviewer findings.
4. **Release**. The final task always bumps the version in every
   manifest, fills the `[Unreleased]` block in `CHANGELOG.md` with
   Removed / Added / Changed / Verification / Notes, refreshes the
   user-facing section of `README.md`, and runs the full test suite +
   build one last time.
5. **PR**. Push the branch, open a PR with a Summary + Test plan
   checklist. Manual smoke items live in the checklist as `[ ]` so they
   gate merge. Merge happens only on explicit user approval, squash mode,
   to keep main linear.

**Why this works**

- The four artefacts (branch + commit chain + CHANGELOG entry + PR
  description) stay synchronised, so any future regression is traceable
  to one commit, one CHANGELOG block, one reviewable PR.
- Subagents prevent context pollution: a 10-task feature finishes with
  the controller's context still clean enough to coordinate the release.
- Spec compliance and code quality are reviewed by *different* fresh
  agents — each catches issues the other misses (spec drift vs. local
  craft).

**Anti-patterns**

- Bumping the version inline with feature work. Version bumps belong in
  the dedicated final task so the diff is always "version + CHANGELOG +
  README" — easy to audit.
- Skipping the spec because the change "feels small". Spec-less tasks
  consistently undershoot edge cases (migration of old config, forward-
  compat of yaml fields, headless test gotchas).
- Letting the controller implement to "save time". The controller's
  judgment degrades after ~3 implementation rounds; subagent dispatch
  preserves it for the long haul.

**Patch releases (vX.Y.Z+1)** skip stage 1 and use a single-task plan:
the bug fix + version bump + CHANGELOG patch entry + PR — same gates,
smaller surface.

---

## Environment Variables

Path variables referenced by skills/configs (e.g., `paper-write` venue YAMLs use `${WORKSPACE_TEMPLATE_DIR}`). Resolve in this order: shell env → this section → project-scope CLAUDE.md.

| Variable | Value | Used by |
|:---|:---|:---|
| `WORKSPACE_TEMPLATE_DIR` | `~/Desktop/workspace/00-09_Meta/01_Templates` | `paper-write` venue YAMLs (`template_dir`) |

Variables expand `~` via `os.path.expanduser`. After resolution the resulting path MUST exist — fail loud if not.

---

## Tradeoff Note

These guidelines bias toward **caution over speed**. For trivial tasks (typo fixes, obvious one-liners), use judgment — not every change needs the full rigor.

The goal is reducing costly mistakes on non-trivial work, not slowing down simple tasks.

---

**Last Updated**: 2026-05-18
**Managed by**: [`claude-settings`](https://github.com/luckkim123/claude-settings) — edit at `~/claude-settings/claude/CLAUDE.md`, the symlink picks up changes automatically.

<!-- OMC:IMPORT:START -->
@CLAUDE-omc.md
<!-- OMC:IMPORT:END -->

---
name: omc-teams-ops
description: omc-teams (tmux pane 분리 워커) launch/운영/디버깅 매뉴얼. 4종 함정 (leader-session-1-team, paste-bracketed Enter 흡수, sentinel self-leak, Cogitated 카운터 사각지대) + omc_monitor.sh v3.x 운영 + 검증된 우회 패턴. omc team launch 직전, sentinel/dispatch 디버깅, monitor 멈춤 진단 시 invoke.
triggers:
  - "omc team"
  - "omc-teams"
  - "tmux pane 분리"
  - "워커 launch"
  - "sentinel"
  - "leader session"
  - "omc_monitor"
  - "omc_pane_label"
  - "omc_status"
  - "dispatch Enter"
  - "pane label"
---

## omc-teams 운영 매뉴얼

`omc-teams` 로 tmux pane 분리 워커를 띄울 때의 검증된 운영 패턴 (2026-05-18 라이온 prep 세션에서 검증).

**Use case 판정**
- 사용 O: 사용자의 Q&A·대화 흐름 (메인 패널) 과 파일 수정 (워커 패널) 을 시각적으로 분리하고 싶을 때. 면접 prep, 강의 자료 수정, 긴 문서 review 등 사용자 가시성이 중요한 케이스.
- 사용 X: 단일 surgical edit 1-3줄 (그냥 메인에서 Edit 이 빠름). spec 모호 (먼저 `/team` 으로 스코핑). reference-bound writing (citation hallucination 위험).

**워커 launch 명령 표준 형식**
```bash
omc team N:claude "<역할 정의 + 작업 컨텍스트 + STYLE_SPEC 룰 + 표준 SOP>" --cwd <작업 디렉토리 절대경로>
```
역할 정의에는 — (1) 작업 대상 파일 범위, (2) 준수해야 할 스타일 표준 파일 경로, (3) 빌드/검증 명령, (4) 표준 작업 절차 5단계 — 를 항상 명시.

**함정: 같은 leader session 안에 **team 추가 불가** (2026-05-21 발견)**

==검증된 증상==: `omc team` CLI 는 `governance.one_team_per_leader_session: true` 룰 하드코드. 한 session 에서 처음 `omc team 1:claude ...` launch 한 후, ==같은 session 에서 두 번째 `omc team 1:claude ...` 시도하면 ``Leader session already owns active team'' 에러로 막힘==. 시도해본 우회 모두 실패: `--new-window` flag (새 team launch 로 해석), `OMC_ONE_TEAM_PER_LEADER=0` env var, `OMC_TEAM_NAME=...` env var, env override 일체. `omc team api` 에도 `add-worker` 명령 없음.

**결정적 함의**: **같은 session 도중 worker 동적 추가 불가**. 처음부터 ==N-worker team 으로 launch== 해야 함 — `omc team 2:claude "..."` 또는 `omc team 1:claude,1:codex "..."`.

==해결 패턴 1 — Team shutdown + N-worker 재 launch (검증됨)==

기존 team 의 task 가 모두 끝났으면:
```bash
# (1) 현재 in_progress task 가 있으면 force shutdown 필요
omc team shutdown <team-name> --force
# (2) Stale state 정리 (force shutdown 후 디렉토리 잔존)
rm -rf .omc/state/team/<team-name>
# (3) N-worker 로 재 launch
omc team N:claude "<공통 role 정의 + 각 worker 역할 분리>" --no-decompose --cwd <workdir>
```

**주의**: `--force` shutdown 은 **leader session pane 안의 worker process 도 함께 죽임**. **omc 가 관리 안 하는 수동 pane (tmux split-window 으로 만든 것)** 은 자동으로 안 죽지만 leader process 가 변경되니 ==orphan 상태로 남을 수 있음== — 사전에 `tmux kill-pane -t %<id>` 으로 정리 권장.

**Pre-existing state 백업 점검**: **디스크 산출물 (`.worker/dispatch_log.md`, `.worker/research_briefs/`, `sections/*.tex`, `main.pdf`)** 은 shutdown 안 죽음. **state directory (`.omc/state/team/...`)** 만 사라짐. session 다시 시작 시 dispatch_log 그대로 재사용 가능.

==해결 패턴 2 — tmux split-window 직접 (omc 우회, 보조 worker 추가)==

omc team 의 N-worker launch 가 불편한 케이스 (예: 1 worker 만 띄운 상태에서 추가 1 worker 필요한 비정형 상황):

```bash
# (1) W1 pane (omc 가 관리) 옆에 vertical split — ==-v (위아래) 필수==, -h (좌우) 면 main pane 좁아짐
tmux split-window -t %1 -v -c <workdir>
# (2) 새 pane id 확인 (예: %3)
tmux list-panes -a
# (3) 새 pane 에 claude TUI 띄움
tmux send-keys -t %3 "claude --dangerously-skip-permissions" && sleep 1 && tmux send-keys -t %3 Enter
# (4) 8-15 초 init 후 pane content 확인
sleep 10 && tmux capture-pane -p -t %3
# (5) Pane label 부여 (omc_pane_label.sh — 수동 worker 라도 라벨링)
bash ~/claude-settings/claude/scripts/omc_pane_label.sh apply '0.0=[MAIN] ...' '0.1=[W1] ...' '0.2=[W2 manual] ...'
# (6) Task nudge: tmux send-keys -t %3 "<task text>" → sleep 2 → tmux send-keys -t %3 Enter
```

**제약 (omc 안 거치므로)**:
- ❌ `omc team api list-tasks` 안 됨 (수동 W2 는 team 멤버 아님)
- ❌ `omc_monitor.sh` 의 status polling 안 됨 — **pane-only mode** 만 가능 (`team_name="-" task_id="-"` + deliverable file)
- ❌ Lease / heartbeat 자동 관리 안 됨 — 메인이 capture-pane 으로 직접 감시
- ✅ 산출물은 file-based queue (`.worker/research_inbox.md` 등) 로 메인과 통신
- ✅ Force shutdown 영향 받지 않음 (별도 process)

**권장 use case**: 임시 보조 worker (한 query 만 처리 후 종료) 또는 omc state 가 망가져 재 launch 곤란할 때 응급조치. **영구 worker 는 ==팀 재 launch (해결 패턴 1)== 가 깔끔**.

==해결 패턴 3 — N-worker team 처음부터 launch (이상적)==

세션 시작 시점에 ``2 worker 필요할 수도'' 예측되면 처음부터 2-worker team:

```bash
omc team 2:claude --no-decompose "Shared role description; W1 = <편집 전담 SOP>; W2 = <자료조사 전담 SOP>" --cwd <workdir>
```

`--no-decompose` flag 가 ==task 를 worker 수만큼 자동 분해 안 하게== 막음 (둘 다 같은 standby 컨텍스트 받음). 이후 `omc team api create-task` 로 worker-1 / worker-2 에 각각 task assign.

**2 worker 둘 다 같은 cwd**: omc team 제약 — 모든 worker 가 single cwd 공유. 다른 cwd 필요한 multi-repo case 는 별도 처리 (SKILL 의 Phase 2.5 multi-repo workspace 참조).

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

**함정: 사용자 입력과 메인 send-keys 충돌 — Claude TUI paste-bracketed mode 흡수 (2026-05-21 발견)**

==검증된 증상== (2026-05-21 라이온 prep 세션, Task 3 batch dispatch 직전): 메인이 dispatch nudge 보낸 후 사용자가 **직접 worker pane 으로 가서 ❯ prompt 에 ``OK proceed — apply...'' 같은 confirm 메시지 키보드 입력**. 그런데 Enter 안 누르고 메인 채팅으로 돌아옴. 메인이 ==외부 `tmux send-keys -t %1 C-m` 으로 Enter 송출 시도== → **전부 흡수**, ``OK proceed'' 가 ❯ prompt 에 그대로 박혀 worker 진행 안 됨.

**시도해본 우회 (모두 실패)**: `C-m` 송출, `Enter` literal 송출, `set-option -g assume-paste-time 0`, `set-option -p assume-paste-time 0` (pane-level 미지원), `C-a C-k C-u` line clear. ==3-Strike Rule 발동==.

원인 분석: Claude TUI 의 ❯ prompt 는 **paste-bracketed mode** 로 동작. 사용자 키보드 입력 (OS keyboard event) 후 **paste-buffer 가 ``open'' 상태** 유지 — 그 동안 외부 tmux send-keys (pseudo-tty escape sequence) 들어오면 **전부 paste 내용의 일부로 흡수**. C-m / Enter / Ctrl-keys 모두 paste sequence 안 charactor 로 처리. 사용자가 직접 키보드로 Enter 누르거나 (OS event) `C-c` interrupt 로 paste-buffer reset 해야 풀림.

==해결 패턴 1 — 운영 룰 (사용자 측, 가장 안전)==

**메인이 dispatch 한 후 사용자는 worker pane 직접 만지지 말 것**. 사용자가 ``확인 메시지를 직접 입력하고 싶다'' 면:
- 옵션 A: 메인에 ``OK 적용해줘'' 같이 ==자연어로 말함==. 메인이 send-keys 로 처리.
- 옵션 B: 사용자가 직접 입력 **+ 그 자리에서 Enter 까지 누름** (한 동작 안에 완결).
- ❌ 사용자가 입력만 하고 Enter 안 누르고 메인에 ``Enter 눌러줘'' 요청 → 막힘 케이스 발생.

==해결 패턴 2 — Recovery (메인 측, 막혀버린 경우)==

이미 사용자가 입력만 한 상태에서 메인이 Enter 못 보내는 경우:
1. **사용자에게 직접 Enter 부탁** — 가장 빠르고 확실. 사용자 input 그대로 보존됨
2. 또는 메인이 ==`tmux send-keys -t <pane> C-c`== 송출 → paste-buffer interrupt → prompt reset → 새로 dispatch nudge 재송출. **단점**: 사용자 input 잃음
3. ❌ **``Space + Enter'' 패턴은 사용자 input 복구 안 됨** — 2026-05-21 실증: paste-mode 가 ``space 한 글자'' 받으면 풀려서 prompt 가 ``space 만 submit'' 으로 처리되는데, Claude TUI 는 그걸 **empty/whitespace message 로 무시하고 prompt clear** 만 함. ==사용자가 입력한 ``OK proceed'' 같은 text 사라지고 worker 는 메시지 못 받음==. 결과적으로 idle 상태 회복은 되지만 worker 가 사용자 의도 실행 안 함. **Space+Enter 는 ``prompt 청소 효과'' 만, 사용자 input 복구는 패턴 1 (직접 Enter) 만 가능**

==해결 패턴 3 — 예방 (worker launch 시점)==

Worker launch 메시지에 **``Dispatch confirm 은 사용자 직접 입력 X — 메인이 send-keys 로 처리''** 룰 명시. 사용자가 무심코 pane attach 해도 메인 채팅으로 redirect.

**왜 ``Dispatch Enter 미전송 — 2-step 우회''** (위 섹션) **와 다른가**: 위 섹션은 **메인 단독 dispatch (text + Enter) 가 깨지는** 케이스 — sleep 으로 분리해서 해결. 이번 함정은 **사용자 입력 + 메인 Enter 의 충돌** — sleep 무관, paste-bracketed mode 자체 이슈. **운영 룰로 회피** 가 표준.

**누적 함정 4종 + 표준 진단 절차 (2026-05-19 디펜스 세션 발견)**

이번 세션에서 메인이 ==잘못된 상태 인식 3회 누적== 했음. 사용자가 매번 정정. 원인 4가지:

1. **omc CLI stdout/stderr 섞임** — `omc team api ...` 의 첫 줄에 ``[team] canonicalized duplicate worker entries: worker-1'' 같은 비-JSON 라인이 stdout 으로 떨어짐. 단순 `... | python -m json.tool` 깨짐. ==회피: `grep '^{' | head -1` 로 첫 JSON 라인만 추출==
2. **omc state wipe (orphan-cleanup self-invoke)** — 워커가 lease expiry 시 **자기 task / team 전체를 삭제**. 회복 불가. **디스크 산출물은 살아남음**. ==회피: 워커 SOP 에 ``orphan-cleanup is leader-only — never self-invoke. On lease expiry, send-message + idle.'' 명시==
3. **Claude TUI pane title 동적 override** — 워커가 작업 시작하면 OSC escape 로 pane\_title 을 ``✳ Execute worker task and report progress'' 같은 자체 문구로 덮음. thinking 중 매 100-500ms 마다 spam → border flicker. ==회피: `omc_pane_label.sh apply` 가 v3 부터 `tmux set -g allow-set-title off` 까지 함께 적용 → tmux 가 OSC title escape 자체를 ignore. pane\_title 영구 고정, watchdog 불필요. (`clear` 호출 시 자동 복원)==
4. **Monitor stale-aware 의 thinking-카운터 사각지대** — ``Cogitated / Cooked / Brewed / Churned XmYs'' 카운터가 매 분 갱신되어 pane content hash 가 바뀜. stale 카운터 reset 됨. **API 529 (서버 과부하) 도 status 변화 없이 13+ 분 freeze**. ==회피: pane hash 추출 시 ``Cogitated/Cooked/Brewed/Churned'' 라인 제외 OR task version 단독 polling==. 사용자가 직접 발견하는 fallback 도 인정

**표준 진단 절차 (매 사용자 발언 전 의무)**

워커 상태를 발언/결정 근거로 쓰기 전:
```bash
cd <working dir>
bash ~/claude-settings/claude/scripts/omc_status.sh
```
한 화면에 모든 team task 상태 + tmux pane state 정리. ==이 명령 결과를 보고 발언==. ``W4 가 멈춰있는 거 같다'' 같은 직관 발언 금지 — `omc_status.sh` 결과로만 판단.

**Task 생성은 wrapper 사용 의무**

`omc team api create-task` 직접 호출 금지. 대신:
```bash
bash ~/claude-settings/claude/scripts/omc_create_task.sh <team_name> "<subject>" <description_file_or_->
```
이 wrapper 가 — (1) JSON 안전 인코딩, (2) stderr 섞임 필터, (3) ok=false 응답 감지, (4) 중복 호출 방지 — 모두 처리. ==성공 시 task\_id stdout 출력, 실패 시 stderr + exit 1==.

**Pane label 자동 부여 — 매 launch 후 표준 절차 (2026-05-19 추가)**

Claude Code TUI 는 자체적으로 **pane\_title 을 현재 task description 으로 동적 갱신** 함. 메인이 `tmux select-pane -T '[W1] ...'` 로 수동 부여한 라벨은 **워커가 다음 작업 시작하는 순간 덮어써짐** — 사용자가 ``어느 pane 이 어느 워커지?'' 헷갈리게 됨.

해결: tmux `pane-border-format` 에 **pane\_index 기준 hardcoded 라벨 + Claude 동적 title 병기** 형태로 박는다. 이 작업 자동화는 `~/claude-settings/claude/scripts/omc_pane_label.sh`:

```bash
# 매 launch 직후 pane 식별 끝나면 호출
bash ~/claude-settings/claude/scripts/omc_pane_label.sh apply \
  '0=[MAIN] User chat' \
  '1=[W1] PPT Editor' \
  '2=[W2] Image' \
  '3=[W3] Reviewer'
```

결과: 각 pane 위 border 에 **`[W1] PPT Editor | ✳ Execute worker inbox task...`** 형태로 표시. 좌측은 영구 라벨, 우측은 Claude 동적 정보.

**Pane index 재배치 함정과 결합**: 새 워커 launch 시 기존 pane 들의 index 가 재배치되는 경우가 잦음 — apply 호출 **전** `tmux list-panes -a` 로 현재 매핑 재확인 필수.

기타 명령:
- `bash omc_pane_label.sh show` — 현재 라벨 + pane 상태 확인
- `bash omc_pane_label.sh clear` — 라벨 + tmux pane-border-status 모두 리셋 (세션 정리 시)

**Launch 직후 워커 상태 검증 — 매 launch 마다 의무 (2026-05-19 발견)**

`omc team launch` 가 **launch text 를 task 1 으로 자동 등록 + worker pane 에 inbox-read nudge 까지 paste** 하지만, **Enter 입력 + Claude TUI init 둘 다 보장 X**. 메인이 ``전에는 잘 됐으니 이번에도 될 것'' 으로 가정하면 **워커가 prompt 에서 paste 만 된 채 멈춤** — 사용자가 직접 발견해야 알게 됨. 매 launch 직후 자동 검증 의무화:

1. **Launch 직후 즉시** `tmux list-panes -t 0 -F "#{pane_index} cwd=#{pane_current_path}"` 로 **새 pane id 확인** (**pane index 재배치 함정** — 위 별도 노트와 동일)
2. **20-30 초 후** `tmux capture-pane -pt <pane-id> -S -25` 로 워커 pane 정독:
   - 빈 화면 (Claude TUI init 미완료) — **30 초 더 대기 후 재 capture**
   - paste 됐지만 Enter 없음 — 2-step Enter 우회 (위) 적용
   - `[API 429]` 표시 — **rate limited** — 5-10 분 대기 후 Enter 재시도, 또는 다른 워커 셧다운 후 재 launch
   - 정상 실행 (``Reading the inbox now ...'' 등) — OK, monitor 띄움
3. **30 초 후에도 빈 화면 + paste 도 안 보임** — process 자체 실패. shutdown + 재 launch

**워커 동시 launch 위험 — 가능한 한 sequential 권장**

여러 워커 동시 launch (예: A 직후 바로 B) 는 위 **launch 직후 검증** 룰을 **둘 다** 통과해야 안전. 동시 launch 가 깨지는 **검증된 케이스** (2026-05-19):

- **API 429**: 메인 사용 + 새 워커 두 개 동시 init = Anthropic API 부하. **429 가 보이면 워커 process 살아있어도 메시지 응답 X** → 메인은 ``Enter 안 눌렸나'' 로 오해
- **TUI init 지연**: 두 워커가 동시에 `claude --dangerously-skip-permissions` 부팅 → 한쪽은 20 초, 다른 쪽은 60 초 걸림. 메인이 **빠른 쪽 기준**으로만 검증하면 늦은 쪽 누락

대안:
- **Sequential launch**: 워커 A launch → 검증 통과 → **task 1 in\_progress 진입 확인** → 워커 B launch. 2-3 분 overhead 있으나 안정
- **병렬 필요 시**: 두 워커 launch **직후** 둘 다 검증 (즉 위 절차를 2 pane 각각 적용). 429 발견 시 한 워커 **셧다운** 후 sequential 로 전환

**Task lifecycle 함정 — standby 를 task 로 보내지 말 것**

`omc team 1:claude "<standby 컨텍스트>"` 로 launch 하면 그 컨텍스트 자체가 task 1 로 등록됨. 워커는 환경 검증만 하고 task completed 처리 → 다음 dispatch 가 안 들어옴.
- 올바른 운영: launch 시엔 역할·SOP 만 전달, **실제 변경 명세는 `omc team api add-task` 로 새 task 추가**.
- 워커는 task queue 비어도 process 자체는 alive 상태 유지 (idle 대기).

**Batch dispatch 룰**

Q&A 한 건마다 dispatch 하지 말고 변경 메모 **3-5 건 누적 후 한 번에 dispatch**. 이유:
- 변경 명세 작성 + tmux paste + Enter 우회 + 빌드 검증 — 매번 overhead 발생.
- 워커는 한 번의 task 에서 여러 파일을 surgical edit 후 단일 빌드로 검증하는 게 더 안전 (회귀 발견 통합).
- 메인 패널에서는 누적 메모를 카운터로 관리, 적정 시점에 "지금 워커로 dispatch 할까요?" 사용자 확인 후 진행.

**Sentinel-emit 룰 — confirm-pending 감지 결정론화 (2026-05-20 추가)**

Monitor 의 confirm-pending 감지가 자연어 heuristic (``STOP — awaiting'', ``Decisions needed'') 만 쓰면 **worker 메시지 wording 에 따라 매번 깨짐** (2026-05-20 라이온 prep 세션에서 W1 의 ``STOP — awaiting main confirm. Provenance Lock V3 strict: G2 진행 전 ㄱ / OK / proceed 신호 필요.'' 못 잡음). 해결: **worker dispatch 시점에 명시적 sentinel 출력 룰 박기**.

**Dispatch 시 task description 마지막에 다음 sentinel 룰 항상 포함**:

```markdown
## Monitor sentinel 룰 (필수) — square bracket 형식이 canonical (2026-05-20+)

다음 상태에 도달하면 ==exact literal sentinel 한 줄 출력== — monitor 가 deterministic 하게 잡음. 자연어 묘사로 대체 X:

- **Dry-run / confirm-pending 도달 (G1 plan 완료, main confirm 대기)**:
  ```
  [[CONFIRM_PENDING]]
  ```
- **Worker stop 결정 (lease 만료, race 발견, fatal error)**:
  ```
  [[WORKER_STOPPED]] reason: <한 줄>
  ```
- **Worker blocked (외부 의존성 대기, 사용자 자료 필요)**:
  ```
  [[WORKER_BLOCKED]] need: <한 줄>
  ```

sentinel 은 **본문에 한 번만** 출력. 추가 설명/plan 은 sentinel **앞** 또는 **뒤** 줄에. monitor 는 sentinel 라인 grep 으로 즉시 alert (heuristic 매칭 대비 false positive 0).
```

> **Legacy — backward compat**: angle-bracket 형식 (`<<AWAITING_MAIN_CONFIRM>>`, `<<WORKER_STOPPED>>`, `<<WORKER_BLOCKED>>`) 은 기존 워커 호환용. omc_monitor.sh v3.1+ 의 `SENTINEL_PATTERN` 이 angle + square 둘 다 OR 매칭하므로 기존 워커 수정 불필요. ==신규 dispatch 는 square bracket 만 사용==.

**Monitor 측 (omc_monitor.sh v3+)**: `SENTINEL_PATTERN` 매칭이 **primary**, 자연어 `CONFIRM_PATTERNS` 는 **fallback** (sentinel 미도입 worker 호환). exit code 4 = ALERT-CONFIRM.

**왜 이 방식이 더 안정한가**:
1. **Wording 의존성 제거** — worker 가 ``Awaiting'' / ``STOPPING'' / ``Please confirm'' 어느 문구를 쓰든 sentinel 만 박으면 매칭
2. **한글/영문 mix wording 도 OK** — sentinel 은 ASCII fixed
3. **False positive 0** — sentinel 은 worker 가 의도적으로 박은 곳에만 등장 (scrollback 의 과거 plan 텍스트 와 충돌 X)
4. **Polling 15초 단축** — sentinel 매칭은 가벼움, polling 단축으로 응답성 ↑ (`POLL_INTERVAL=15` env var 로 추가 조정 가능)

**기존 worker 마이그레이션**: ppt-edit V3 dry-run gate, autopilot G1 plan, ralph iteration boundary 등에 sentinel 박기. wiki/CLAUDE.md 의 task template 도 sentinel 룰 default 포함.

**함정: sentinel self-leak — angle bracket self-confusion (2026-05-20 발견)**

==검증된 증상==: dispatch task 본문에 ``완료 시 `<<AWAITING_MAIN_CONFIRM>>` 출력'' 같은 **메타-instruction** 을 박으면, 워커가 본문 작성할 때 sentinel 문자열을 ==literal 로 박지 않으려고 자체 회피==: ``< < AWAITING\_MAIN\_CONFIRM > >'' (공백) 또는 **빈 `<>`** 만 남기는 케이스. 2026-05-20 라이온 prep 세션 W2 (image generator) 에서 figure 보고 메시지 끝에 빈 `<>` 누적 발견.

원인: 워커가 ``monitor 가 내 출력에서 sentinel 을 찾으니 본문 설명용 텍스트에서 실제 sentinel 박으면 false positive 날 것'' 으로 **과잉 추론** → 자기 출력에서 sentinel 토큰을 ==중간 비운 빈 bracket 으로 회피==. 메인 dispatch 가 ``literal 박는 방법'' 을 명시 안 해서 발생.

==해결 패턴 1 — Dispatcher 측 변형 표기==

dispatch 본문에서 sentinel 을 **설명** 할 때는 ASCII art 로 분해해서 박을 것 — 워커가 자기 출력에서 동일 표기를 따라 하지 않게:

```markdown
## Monitor sentinel 룰

완료 시 다음 토큰을 **한 줄에 붙여서** 출력 (5개 토큰 연결):
  `<` + `<` + `AWAITING_MAIN_CONFIRM` + `>` + `>`

실제 출력은 위 5개를 공백 없이 이어붙인 ==12자 문자열== (정확한 형태는 monitor regex 와 일치해야 함).
```

이렇게 박으면 워커 본문에 ``< < AWAITING\_MAIN\_CONFIRM > >'' (분해 표기) 가 보존돼서 self-confusion 없음.

==해결 패턴 2 — Sentinel 자체를 angle 대신 square bracket 로==

더 안전: sentinel 을 `[[CONFIRM_PENDING]]` / `[[WORKER_STOPPED]]` / `[[WORKER_BLOCKED]]` 같이 square bracket 으로 운용. angle bracket 보다 markdown/HTML 파서 충돌 적고, ``불완전 형태'' (`<>`) 같은 partial leak 발생 안 함 (`[]` 빈 형태는 monitor regex 와 명백히 다름).

**Monitor 양쪽 sentinel 모두 인식 (backward compat)**: omc\_monitor.sh v3.1+ 의 `SENTINEL_PATTERN` 은 angle 형식 + square 형식 둘 다 OR 매칭. 기존 워커가 angle 박아도 동작, 신규 dispatch 는 square 권장.

==해결 패턴 3 — Sentinel 생략 (간단한 경우)==

워커가 figure/file 생성 후 곧바로 사용자 검토 요청하는 단순 워크플로우 (W2 image generator 등) 는 sentinel 자체 **생략 가능**. 메인이 워커 출력 직접 받아서 사용자께 보고만 하면 됨. ==sentinel 은 multi-SOP gate (V3 dry-run, autopilot G1) 처럼 메인 확인이 **명시적 동기화 지점** 일 때만 박기==.

**Default 룰** (2026-05-20+):
- 단순 generator/editor 워커 → sentinel 생략, 한 줄 보고만
- Multi-SOP gate 가 있는 워커 → square bracket sentinel 박기 (`[[CONFIRM_PENDING]]`)
- 기존 angle bracket sentinel 박은 워커 → 그대로 두기 (monitor 가 양쪽 인식)

**함정: Dispatcher self-leak — confirm 메시지 본문에 sentinel literal 박기 (2026-05-21 발견)**

==검증된 증상== (2026-05-21 라이온 prep 세션): 메인이 워커에 ==``OK proceed — apply changes. Build failure = STOP + diagnose + **[[WORKER_STOPPED]]**.''== 같이 **confirm-OK 메시지 본문에 sentinel literal 박음** (worker 한테 "build 실패하면 이 sentinel 으로 보고하라" 교육 의도). 그 메시지가 worker pane 의 prompt 라인에 paste 됨 → monitor 재시작 직후 **iter=1 pane capture** 에서 그 sentinel 매칭 → ALERT-CONFIRM 즉시 발사. ==Worker 는 정상 apply 중== 인데 monitor 가 ``confirm-pending'' 으로 잘못 인식.

원인 2 가지 결합:
1. **Monitor 의 tail window 가 30 줄** — pane bottom 5 줄에 paste 된 메시지를 항상 캡처 (v3.3 에서 15 로 줄임)
2. **iter=1 즉시 매칭** — monitor 재시작 직후 첫 polling 에서 ``방금 paste 된 sentinel 토큰'' 을 fresh emission 으로 오인 (v3.3 에서 iter=1 매칭 스킵)

==해결 패턴 1 — Dispatcher 측 rule (가장 중요)==

**Confirm 메시지 / dispatch instruction 본문에 sentinel literal 박지 말 것**. 워커에게 ``X 상황에 sentinel 박아라'' 라고 **교육** 하려면:
- ✅ ASCII art 분해: ``Build failure = STOP + diagnose + `[`+`[`+`WORKER_STOPPED`+`]`+`]`''
- ✅ 우회 표현: ``Build failure = STOP + diagnose + WORKER_STOPPED sentinel''
- ❌ Literal sentinel: ``Build failure = STOP + diagnose + [[WORKER_STOPPED]]''

==해결 패턴 2 — Monitor 측 (omc_monitor.sh v3.3, 2026-05-21)==

자동 보강 — dispatcher 가 실수로 literal 박아도 false-positive 차단:
- `tail_window`: 30 → 15 줄 (워커 자체 sentinel emit 은 bottom 5 줄 안)
- `iter=1 skip`: 첫 polling 에서 sentinel/heuristic 둘 다 스킵, iter=2 부터 매칭 (scrollback drift 한 cycle 대기)

==해결 패턴 3 — 워커 정상 apply 중에 monitor 재시작 안 하기==

가능하면 monitor 한 instance 가 task 전체 lifecycle (dry-run → confirm → apply → done) 을 **한 번에 watch**. 재시작은 **stale alert / fail alert 받았을 때만**. confirm 보낸 직후 새 monitor 재시작 = scrollback 충돌 위험.

**함정: Heuristic false-positive — 워커 plan 본문의 ``결정 필요'' 어구 (2026-05-20 발견)**

==검증된 증상==: W1 가 Section III plan.md 작성 중 본문에 ``slide 38 정량 결과 출처 불명 → ==사용자 결정 필요=='' 같이 **설명용 텍스트** 로 ``확인 필요'' / ``결정 필요'' 박았는데, monitor v3.0 의 `CONFIRM_PATTERNS` 한국어 매칭 (``확인 필요'' / ``승인 대기'' / ``G2 진행 전.*필요'') 이 즉시 매칭해서 ALERT-CONFIRM (exit 4) 발사. 워커는 **plan 작성 중 진행 중** 이었고 confirm-pending 아님 → ==잘못된 알림==.

원인: 한국어 ``확인 필요'' / ``결정 필요'' 는 워커 plan/analysis 본문에 자연스럽게 등장하는 **descriptive label**. heuristic 이 **intent (synchronization point)** 와 **description (annotation)** 둘 다 잡아서 false-positive 다발.

==해결 (omc_monitor.sh v3.2)==:

1. ==`CONFIRM_PATTERNS` 에서 bare 한국어 어구 제거== — ``확인 필요'' / ``결정 필요'' / ``G2 진행 전.*필요'' / ``승인 대기'' 모두 빠짐. 영문 ``please confirm'' / ``shall I proceed'' 같은 **명시적 imperative** 만 유지. 이모지 sync marker (`✅ / ❌`, `Apply.*\?[[:space:]]*✅`) 보존.
2. ==`MONITOR_NO_HEURISTIC=1` env var 추가== — heuristic 완전 끄고 sentinel + deliverable + stale 만 보는 모드. plan-writing 워커처럼 prose false-positive 빈번한 경우 사용:
   ```bash
   MONITOR_NO_HEURISTIC=1 bash omc_monitor.sh - - %18 600 /workdir section3_plan.md
   ```
3. ==Deliverable-only watcher 대안== — pane 추적 자체를 끄고 **파일 mtime 만** polling 하는 단순 watcher 도 옵션. monitor 스크립트 대신:
   ```bash
   # plan-writing 워커의 경우 가장 안전
   DELIVERABLE=/workdir/plan.md START=$(date +%s)
   while true; do
     if [ -f "$DELIVERABLE" ] && [ "$(stat -f %m "$DELIVERABLE")" -gt "$START" ]; then
       echo "[ALERT-DONE] plan.md created"; exit 0
     fi
     sleep 30
   done
   ```

**운영 룰** (2026-05-20+):
- ==Plan-writing / analysis 워커 (Step 2 plan.md 작성 등)== → `MONITOR_NO_HEURISTIC=1` 또는 deliverable-only watcher 사용
- ==Multi-SOP gate 워커== → sentinel 박는 워커라 heuristic 없이 sentinel 만 봐도 OK → `MONITOR_NO_HEURISTIC=1` 권장
- ==Heuristic 활성 (default)== → 영문 imperative + 이모지 marker 만 잡음, 한국어 prose 무시
- **만약 사용자 친 ``확인 필요''** 같은 어구로 confirm 요청하고 싶으면 → 이모지 (`✅ / ❌`) 또는 영문 ``please confirm'' 같이 sync marker 명시

**Team name slug**

`omc team` 은 task description 에서 첫 단어 수개로 slug 를 만듦 (영문 만). 한글 description 은 의미 없는 slug 가 됨 → **description 시작을 ASCII 영문** 으로 박을 것 (예: ``Section 5.4 LQR compression worker''). `--team-name` 같은 명시 옵션은 omc CLI 에 **존재하지 않음** (시도 시 help 출력 silent fail).

**Worker pool 자동 선택 — 사용자 매번 결정 X**

여러 워커 (team) 가 떠 있을 때 사용자가 매 dispatch 마다 ``어느 워커?'' 결정하지 않아도 됨. 자체 절차:

1. 모든 워커 team 의 task 상태 확인 (`omc team api list-tasks` per team, `in_progress` count 가 핵심)
2. **Idle 워커** (in_progress=0) 만 후보로 선별
3. 둘 다 idle → **workspace state 워커 default** (state 가 `./.omc/` 안에 있는 쪽이 운영 깔끔)
4. 한쪽만 idle → 그 쪽으로 dispatch
5. 둘 다 busy → 사용자에게 ``큐잉 vs 대기'' 한 번 확인 (드물게 발생)

**같은 파일 conflict 회피**: 같은 .tex 같은 .py 같은 파일을 두 워커가 동시 만지지 말 것. busy 워커는 자동 후보 제외 룰에 흡수됨. 두 워커가 **독립 파일** 작업이면 동시 dispatch OK.

**워커 state 경로 trade-off**

team launch 시점 cwd 에 따라 state 디렉토리 위치 결정:
- **Cwd = 작업 디렉토리** → state in `<workdir>/.omc/state/team/<slug>` — **운영 깔끔** (모든 명령 같은 cwd), 기본 권장
- **Cwd = /tmp** (또는 다른 곳) + `--cwd <target>` → state in `/tmp/.omc/state/team/<slug>` — **같은 디렉토리에 두 team launch 시 격리용**. 단점: api 명령마다 `cd <state-cwd>` 필요

같은 cwd 에서 두 번째 team launch 시도하면 **silent fail** (help 출력만 떨어짐 — `omc` 가 cwd 단위 single-team 가정). 격리 필요시 두 번째 워커만 다른 cwd 로 옮기는 우회 사용.

**Auto-monitor 패턴 — 모든 task 생성에 완료 알림 묶기 (**의무**)**

매 task 생성마다 polling 스크립트를 `Bash run_in_background: true` 로 같이 띄움 → 워커 완료 시 메인 패널이 push 알림 받음. 사용자가 "끝났니?" 묻지 않아도 됨.

**2026-05-21 함정 — Idle worker 도 monitor 띄울 것**: Team launch / task complete 직후 worker 가 idle 진입한 시점에도 **pane-only monitor (sentinel + stale)** 띄워야 함. 이유: 사용자가 워커 pane 에 직접 입력하는 경우 (paste-bracketed mode 함정) / 워커가 자발적으로 ``exit'' 시도하는 경우 (worker self-shutdown 함정) 발생 → **메인이 monitor 없으면 stuck 상태 발견 못함**. Idle monitor 형식:
```bash
MONITOR_NO_HEURISTIC=1 bash ~/claude-settings/claude/scripts/omc_monitor.sh \
  - - <pane-id> 1500 <workdir> - 2>&1 &
```
- team / task_id ``-'' = pane-only mode (omc API polling 스킵)
- deliverable ``-'' = idle watching, ALERT-DONE 안 발사. Sentinel emit (worker 가 의도적 출력) 또는 stale 1500s 후 ALERT-STALE
- 새 task 들어오면 이 monitor 종료 + ==task-specific monitor (team + task_id + deliverable)== 로 재시작

**Task 생성 = monitor 대상 — 두 경로 모두 포함**:
- **경로 A: 새 team launch** — `omc team N:claude "<text>"` 의 launch text 자체가 **task 1 로 자동 등록**. 이것도 monitor 대상. ``team launch ≠ dispatch'' 로 분리 인지하면 회귀 발생 (2026-05-19 라이온 prep 세션에서 worker2 launch 시 monitor 빠뜨림)
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

위 단순 monitor (`status == completed` 만 보는 형) 는 **3가지 사각지대**:
- Task `in_progress` 인 채 워커가 SOP 간 transition 에서 멈춤 (2026-05-19 라이온 prep 세션에서 worker2 가 SOP 1 → SOP 2 사이 freeze, nudge 없이는 진행 불가)
- Task `failed` 로 transition 됐는데 monitor 가 못 잡고 영원히 polling
- Worker process 자체 죽음 (pane prompt 그대로, status 안 바뀜)

3가지 모두 사용자 입장에서 ``끝났니?'' 묻기 전엔 알 수 없음 → **개선 monitor 필요**.

**Cogitated 카운터 사각지대 — 새 함정 (2026-05-19 발견)**

3-signal monitor (status + version + pane hash) 도 잡지 못하는 케이스:

- 워커가 **같은 ledger 파일을 메인과 동시 수정** → ``File must be read first'' Edit 에러 → **워커가 10+ 분 thinking 으로 복구 경로 모색**
- Claude TUI 는 thinking 동안 pane 에 **`✻ Cogitated for XmYs ↓ token` 같은 라인을 분 단위로 갱신** → **pane content hash 가 매 분 변함** → stale 카운터 reset → ALERT-STALE 발사 **안 됨**
- 사용자가 ``뭔가 멈춘 거 같은데?'' 직접 발견해야 알게 됨

**검증된 사례 (2026-05-19 디펜스 prep 세션)**: W1 워커가 dispatch\_log.md Edit 실패 → 10분 31초 thinking → 사용자 ``멈추지마.'' 입력으로 trigger → 자체 회복. monitor 는 정상 status=in\_progress 만 보고 stale 알림 zero.

**보완 패턴 옵션**:
1. **Pane hash 추출 시 ``Cogitated'' / ``Embellishing'' / ``Precipitating'' 라인 제외** — monitor 스크립트가 capture-pane 결과 grep -v 로 thinking 진행 표시 제거 후 hash. 변경 없이 hash 같으면 진짜 freeze
2. **Task version 단독 polling** (pane hash 무시) — omc task version 은 워커가 실질적 progress 만들 때만 증가 (claim renewal 제외). pane false-positive 회피
3. **Thinking 시간 **자체**를 stale signal 로** — Cogitated XmYs 추출, 10분 초과 시 alert. **단 long-thinking 자체가 잘못은 아니므로 ALERT-LONG-THINK** 형태로 정보성

**운영 룰** (당장 적용):
- 메인이 워커 dispatch 직후엔 **ledger 파일을 안 만지는 룰** 강화. 동시 수정 race 자체를 회피
- Monitor 가 잠잠한데 워커 진행이 의심스러우면 **사용자가 직접 capture-pane 으로 확인** 후 nudge — 자동화 한계 인지
- Thinking 5분 초과 발견 시 monitor 로그에 정보 출력 (Stale alert 와 별도 신호) 권장

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

**Stale 카운트 룰** (false-positive 방지 핵심):
- `pending`: 워커가 claim 전 — 정상 대기. stale 카운트 reset
- `in_progress`: stale 체크 대상 — version + pane hash 둘 다 안 바뀌어야 stale 누적
- `completed` / `failed`: 즉시 exit (정상 종료)
- 빈 응답: API 일시 오류 가능 — stale reset (다음 polling 에서 재확인)

**Threshold 선택**: 180 초 (3 분) 는 long-thinking (Cogitated 1m+) 흔한 워커에서 false-positive 빈번. **300 초 (5 분) 가 실전 안전**. 단순 작업 (한 파일 edit, 빌드 1회) 만 monitor 하면 180 도 OK.

**Monitor 실행 모드 — eval 인라인 vs 셸 스크립트 파일**

위 monitor 를 `Bash run_in_background: true` 의 인라인 eval 로 띄우면 zsh `eval` 의 큰 코드 + python3 here-doc quoting 충돌로 **silent 죽음** 가능 (2026-05-19 라이온 prep 세션에서 task 6 monitor 가 polling 자체 안 함). 해결:

1. **셸 스크립트 파일로 분리** — `~/claude-settings/claude/scripts/omc_monitor.sh` 가 영구 보존 위치 (claude-settings 에 커밋된 정본). 임시 디버깅용으로만 `/tmp/omc_monitor.sh` 사용
2. Bash background 호출: `bash ~/claude-settings/claude/scripts/omc_monitor.sh <team> <id> <pane> [stale_sec] [cwd]`
3. 스크립트 내부에서 매 polling 결과를 `echo "[POLL ... status=... version=... stale=...]"` 로 **log** → 디버깅·진행 가시성 동시 확보

스크립트 구조 (필수 요소):
- `#!/bin/bash` shebang (zsh 충돌 회피)
- arg 4 개 + optional 2 개 (team / id / pane / stale_sec / cwd)
- 위 status 분기 (completed / failed / pending / in_progress / 빈응답)
- iteration counter + log echo (가시성)
- 종료 코드: 0=done / 1=fail / 2=stale / 3=arg 오류

**언제 인라인 OK**: 단순 monitor (status only, log 없음) 는 인라인도 작동. 3-signal + log 같이 복잡해지면 셸 파일 분리가 안전.

**종료 경로 3개**: `completed` → 정상, `failed` → 실패, `STALE_THRESHOLD` 초 정체 → **stale alert** (사용자에게 ``워커 nudge 필요'' 신호). 셋 다 push 알림이라 사각지대 0.

**Stale 처리 표준**: stale alert 받으면 메인 패널이 (1) `tmux capture-pane` 으로 워커 현재 상태 확인, (2) nudge 메시지 + 2-step Enter 로 깨움, (3) 깨어나면 새 monitor 재시작, (4) 안 깨어나면 사용자에게 ``shutdown 후 재 dispatch'' 옵션 제안.

**언제 단순 vs 개선 monitor**: 단순 작업 (한 파일 surgical edit, 빌드 1회) 은 단순 monitor 충분. **Multi-SOP 작업** (parsing → restructure → build → verify → report 같은 5+ step) 은 SOP 간 freeze 위험 → 개선 monitor 권장.

**Monitor v2 (2026-05-20) — 5-signal 사각지대 보강**

3-signal monitor 가 못 잡는 새 함정 3종을 v2 (`omc_monitor.sh`) 에서 보강:

1. **Dry-run confirm-pending idle** — ppt-edit V3 Provenance Lock 같은 룰로 워커가 ``Awaiting main confirm'' 으로 의도적 정지. status 는 in_progress 지만 사용자 입력 대기 중이고 stale 카운터는 hash 변경으로 reset. ==endpoint 가 deliverable 파일== 인 monitor 는 영원히 대기.
2. **User typed but no Enter** — 사용자가 `❯ ` prompt 에 답변 입력하지만 Enter 가 **paste-bracketed mode 에 흡수**되어 워커가 못 받음. 메인이 send-keys 로 Enter 보내도 무시됨. **회피: `C-a C-k` 로 line clear 후 새로 입력 + Enter 별도 전송**.
3. **Pre-existing deliverable false-DONE** — G1 dry-run 에서 워커가 cp 로 clean copy 생성하면 deliverable glob 매칭은 되지만 진짜 patch 는 아직 진행 중. ==mtime 비교 (mtime > monitor_start_epoch) 로 해결==.

v2 신규 alert 2종 + 1종 endpoint 보강:
- **ALERT-CONFIRM (exit 4)** — pane content 에 ``Awaiting main confirm'' / ``Decisions needed'' / ``STOPPING'' / ``✅ / ❌'' 패턴 감지. 메인이 워커 plan 검토 후 응답 필요.
- **ALERT-TYPED-NOOP (exit 5)** — `❯ <text>` 가 prompt 에 입력만 되고 Enter 미전송 감지. **높은 우선순위** (Enter 만 보내면 풀림, confirm 보다 actionable).
- **ALERT-DONE 보강** — deliverable 파일의 mtime 이 monitor_start_epoch 보다 **새로워야** 발사. cp 직후의 untouched copy 무시.

호출 형식 (pane-only 모드 추가: team_name/task_id 둘 다 ``-'' 로 두면 omc API polling 스킵, pane content 만 polling):
```bash
bash ~/claude-settings/claude/scripts/omc_monitor.sh <team|-> <task_id|-> <pane> [stale_sec=300] [cwd=PWD] [deliverable_glob]
```

**Endpoint 선택 룰**: G2/G3 multi-step SOP 가 있는 ppt-edit 같은 작업은 **최종 산출물 (report.md 등)** 을 endpoint 로 지정 — verify_report.json 이나 edited.pptx 같은 중간 파일은 false-DONE 위험. 최종 deliverable 이 **마지막 step 에서만 작성**되는 파일이어야 함.

## Related
- omc-reference skill — OMC agent catalog / tools / pipeline
- ~/claude-settings/claude/scripts/omc_monitor.sh — v3.x 정본
- ~/claude-settings/claude/scripts/omc_pane_label.sh
- ~/claude-settings/claude/scripts/omc_status.sh
- ~/claude-settings/claude/scripts/omc_create_task.sh

**Last Updated**: 2026-05-24

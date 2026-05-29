---
name: omc-teams-ops
description: omc-teams (tmux pane 분리 워커) launch/운영/디버깅 매뉴얼. 함정 6+ 종 (leader-session-1-team, paste-bracketed Enter 흡수, sentinel self-leak, dispatcher self-leak, heuristic false-positive, Cogitated 카운터 사각지대) + omc_monitor.sh v3.x 운영 + 검증된 우회 패턴. omc team launch 직전, sentinel/dispatch 디버깅, monitor 멈춤 진단 시 invoke. 본문은 증상-원인-해결 결정 트리로 정리; 함정의 chronological 출처는 git log 참조.
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

# omc-teams-ops

`omc-teams` 로 tmux pane 분리 워커를 띄울 때의 운영 매뉴얼. 본문은 **증상 → 진단 → 해결** 트리로 구성. 함정 6+ 종이 시간순으로 누적됐던 것을 *단계별로 묶어* 긴급 상황에서 즉시 navigate 가능하게 만들었다.

## 0. 현재 상태와 omha 와의 역할 분담

- **omc-teams CLI 자체는 살아있음** — `omc team`, `omc team api ...`, `omc team shutdown` 등 본문이 의존하는 명령은 모두 omc 플러그인 본체 (이 글 작성 시점 v4.14+) 가 제공한다.
- **이 SKILL 의 범위**: omc-teams 의 *운영 함정과 우회 패턴*. omha 가 흡수한 것은 routing/skill registry 쪽 (예전의 `routing-verdict-reminder.py`, `omc-reference` 카탈로그) 이지 team 운영 자체는 그대로 omc 가 owner.
- **drift 신호** (다음 중 하나라도 발생하면 본문의 명령 형식이 stale 일 가능성, omc 플러그인 changelog 확인):
  - `omc team` 호출 시 `unknown command` 또는 `flag --no-decompose deprecated`
  - `omc team api read-task` 응답에 `data.task.status` 키 부재
  - `omc team api create-task` 가 plain text 만 반환 (현행은 JSON 응답)
- 위 SSOT 분리: monitor 스크립트 (`omc_monitor.sh` 등) 와 wrapper 스크립트들은 이 repo (claudebase) 의 `installer/scripts/` 에 정본. omc 플러그인 본체와 별도로 evolve.

---

## 1. Use case 판정 (invoke 전 5 초)

**사용 O**
- 사용자의 Q&A·대화 흐름 (메인 패널) 과 파일 수정 (워커 패널) 을 *시각적으로* 분리해야 할 때. 면접 prep, 강의 자료 수정, 긴 문서 review.

**사용 X**
- 단일 surgical edit 1-3 줄 — 메인에서 Edit 이 빠름.
- spec 모호 — `/team` 으로 먼저 스코핑.
- reference-bound writing — citation hallucination 위험.

---

## 2. 증상별 진단 트리

| 증상 (사용자가 보는 것) | 원인 위치 | 본문 섹션 |
|---|---|---|
| "Leader session already owns active team" 에러 | Launch 단계 / one_team_per_leader | §3.1 |
| 워커 launch 후 prompt 가 paste 만 되고 실행 안 됨 | Dispatch / Enter 흡수 | §4.1 |
| 사용자가 worker pane 에 직접 입력했는데 메인의 Enter 가 무시됨 | Dispatch / paste-bracketed | §4.2 |
| monitor 가 false ALERT-CONFIRM 발사 (워커는 정상 진행) | Monitor / sentinel self-leak 또는 dispatcher self-leak | §5.1, §5.2 |
| plan 작성 중 "확인 필요" 같은 한국어 prose 로 false alert | Monitor / heuristic | §5.3 |
| 워커가 10+ 분 thinking 인데 monitor 가 stale 알람 안 줌 | Monitor / Cogitated 카운터 사각지대 | §5.4 |
| 워커 launch 직후 빈 화면, paste 도 없음 | Launch / TUI init 실패 또는 API 429 | §3.2 |
| `omc team api` 응답이 JSON 으로 안 풀림 | Operations / stdout/stderr 섞임 | §6.1 |
| 같은 cwd 에 두 번째 team launch 가 silent fail | Launch / cwd 단위 single-team | §3.3 |

---

## 3. Launch 단계 함정

### 3.1 같은 leader session 안에 team 추가 불가

**증상**: `omc team 1:claude ...` 첫 launch 후, 같은 session 에서 두 번째 `omc team 1:claude ...` 시도 → `Leader session already owns active team`.

**원인**: `omc team` CLI 의 `governance.one_team_per_leader_session: true` 하드코드. `--new-window`, `OMC_ONE_TEAM_PER_LEADER=0`, `OMC_TEAM_NAME=...` 모두 우회 실패 — 확인됨. `omc team api` 에 `add-worker` 명령 없음.

**결정적 함의**: 같은 session 도중 worker *동적 추가 불가*. 처음부터 N-worker 로 launch 해야 한다.

#### 해결 패턴 1 — 기존 team shutdown + N-worker 재launch (가장 깔끔)

```bash
# (1) in_progress task 있으면 force shutdown
omc team shutdown <team-name> --force
# (2) Stale state 정리 (force shutdown 후 디렉토리 잔존)
rm -rf .omc/state/team/<team-name>
# (3) N-worker 로 재 launch
omc team N:claude "<공통 role + 각 worker 역할 분리>" --no-decompose --cwd <workdir>
```

**주의 (검증됨)**:
- `--force` shutdown 은 leader session pane 안의 worker process 도 함께 죽임.
- omc 가 관리 안 하는 수동 pane (tmux split-window) 은 자동으로 안 죽지만 leader process 변경으로 *orphan* 상태 가능 — `tmux kill-pane -t %<id>` 으로 사전 정리 권장.
- 디스크 산출물 (`.worker/dispatch_log.md`, `sections/*.tex` 등) 은 shutdown 영향 받지 않음 — `.omc/state/team/...` 만 사라진다. 재 launch 후 dispatch_log 재사용 OK.

#### 해결 패턴 2 — tmux split-window 직접 (omc 우회, 임시 보조 worker)

omc team 의 N-worker launch 가 불편한 비정형 상황 (예: 1 worker 띄운 상태에서 임시 1 worker 추가):

```bash
# (1) 기존 W1 pane 옆에 vertical split — -v 필수 (-h 면 main 좁아짐)
tmux split-window -t %1 -v -c <workdir>
# (2) 새 pane id 확인
tmux list-panes -a
# (3) 새 pane 에 claude TUI
tmux send-keys -t %3 "claude --dangerously-skip-permissions" && sleep 1 && tmux send-keys -t %3 Enter
# (4) 8-15 초 init 후 확인
sleep 10 && tmux capture-pane -p -t %3
# (5) Pane label 부여
bash ~/claude-settings/installer/scripts/omc_pane_label.sh apply \
  '0.0=[MAIN] ...' '0.1=[W1] ...' '0.2=[W2 manual] ...'
# (6) Task nudge: §4.1 의 2-step Enter 우회 적용
```

**제약 (omc 안 거치므로)**:
- ❌ `omc team api list-tasks` 안 됨
- ❌ `omc_monitor.sh` 의 status polling 안 됨 — *pane-only mode* (`team="-" task_id="-"` + deliverable) 만 가능
- ❌ Lease / heartbeat 자동 관리 안 됨 — capture-pane 으로 직접 감시
- ✅ 산출물은 file-based queue (`.worker/research_inbox.md`) 로 메인과 통신
- ✅ Force shutdown 영향 받지 않음 (별도 process)

**권장 use case**: 임시 보조 worker (1 query 후 종료), 또는 omc state 망가져 재 launch 곤란할 때 응급조치. 영구 worker 는 패턴 1 권장.

#### 해결 패턴 3 — 처음부터 N-worker team (이상적)

세션 시작 시점에 "2 worker 필요할 수도" 예측되면:

```bash
omc team 2:claude --no-decompose \
  "Shared role description; W1 = <편집 전담 SOP>; W2 = <자료조사 전담 SOP>" \
  --cwd <workdir>
```

`--no-decompose` flag 가 task 를 worker 수만큼 자동 분해 안 하게 막음 (둘 다 같은 standby 컨텍스트). 이후 `omc team api create-task` 로 각 worker 에 task assign.

**2 worker 둘 다 같은 cwd**: omc team 제약 — 모든 worker 가 single cwd 공유. 다른 cwd 필요하면 별도 처리.

### 3.2 Launch 직후 워커 상태 검증 — 매 launch 의무

`omc team launch` 가 launch text 를 task 1 으로 자동 등록 + worker pane 에 inbox-read nudge paste 까지 함. **그러나 Enter 입력 + Claude TUI init 둘 다 보장 X**. "전에는 잘 됐으니 이번에도" 가정하면 워커가 prompt 에서 paste 만 된 채 멈춤 — 사용자가 직접 발견.

**표준 검증 절차 (매 launch 직후)**:

1. **Launch 직후**: `tmux list-panes -t 0 -F "#{pane_index} cwd=#{pane_current_path}"` 로 새 pane id 확인 (*pane index 재배치 함정* — 새 worker 추가 시 기존 pane index 가 shift).
2. **20-30 초 후**: `tmux capture-pane -pt <pane-id> -S -25` 로 워커 정독:
   - 빈 화면 (Claude TUI init 미완료) → 30 초 더 대기 후 재 capture
   - paste 됐지만 Enter 없음 → §4.1 2-step Enter 우회 적용
   - `[API 429]` → rate limited. 5-10 분 대기 또는 다른 워커 셧다운 후 재 launch
   - "Reading the inbox now ..." 등 정상 실행 → OK, monitor 띄움
3. **30 초 후에도 빈 화면 + paste 도 없음** → process 실패. shutdown + 재 launch.

### 3.3 워커 동시 launch 위험 — sequential 권장

여러 워커 동시 launch (A 직후 바로 B) 는 §3.2 검증을 *둘 다* 통과해야 안전. 검증된 깨짐 케이스:

- **API 429**: 메인 사용 + 새 워커 두 개 동시 init = Anthropic API 부하. 429 가 보이면 워커 process 살아있어도 메시지 응답 X → 메인은 "Enter 안 눌렸나" 로 오해.
- **TUI init 지연 불균등**: 두 워커 동시 부팅 → 한쪽 20 초, 다른 쪽 60 초. 빠른 쪽 기준 검증만 하면 늦은 쪽 누락.

**권장**:
- **Sequential**: 워커 A launch → 검증 통과 → task 1 in_progress 확인 → 워커 B launch. 2-3 분 overhead 있으나 안정.
- **병렬 필요 시**: 둘 다 §3.2 검증을 *각각* 적용. 429 발견 시 한 워커 셧다운 후 sequential 로 전환.

### 3.4 같은 cwd 두 번째 team launch — silent fail

같은 cwd 에서 두 번째 `omc team ...` 시도하면 *silent fail* (help 출력만 떨어짐). omc 가 cwd 단위 single-team 가정. 격리 필요시 두 번째 워커만 다른 cwd 또는 `--cwd <target>` 으로 옮기는 우회.

### 3.5 Team name slug — ASCII 시작 강제

`omc team` 은 task description 첫 단어 수개로 slug 만듦 (영문만). 한글 시작 description 은 의미 없는 slug. → description 시작을 ASCII 영문으로 (예: "Section 5.4 LQR compression worker"). `--team-name` 같은 명시 옵션 omc CLI 에 *존재하지 않음* (시도 시 help silent fail).

---

## 4. Dispatch / Enter 단계 함정

### 4.1 Dispatch Enter 미전송 — 2-step 우회 패턴

**증상**: `tmux send-keys -t <pane> "<text>" C-m` 한 콜에 보내면 한글·긴 문자열 paste 도중 prompt focus 흔들려 C-m 이 buffer 안에 *흡수*. paste 만 되고 실행 안 됨.

**우회**:
```bash
tmux send-keys -t <pane-id> "<task description>"   # text 만
sleep 2
tmux send-keys -t <pane-id> C-m                    # Enter 별도
```

1차 후 `tmux capture-pane -pt <pane-id> -S -20` 로 prompt 확인. 입력만 됐으면 step 2 만 재시도. 자동화 실패 시 fallback 으로 사용자에게 "워커 패널에서 Enter 한 번 부탁" 안내.

### 4.2 사용자 입력 + 메인 send-keys 충돌 — Claude TUI paste-bracketed mode 흡수

**증상**: 메인이 dispatch nudge 보낸 후 사용자가 worker pane 에 직접 키보드 입력 ("OK proceed — apply..."). 그런데 Enter 안 누르고 메인으로 돌아옴. 메인이 `tmux send-keys -t %1 C-m` 으로 Enter 시도 → **모두 흡수**. 사용자 입력이 ❯ prompt 에 박혀 worker 진행 안 됨.

**원인**: Claude TUI 의 ❯ prompt 는 paste-bracketed mode. 사용자 키보드 (OS keyboard event) 입력 후 paste-buffer 가 "open" 상태 유지. 외부 tmux send-keys (pseudo-tty escape sequence) 들어오면 paste 내용의 일부로 흡수. C-m / Enter / Ctrl-keys 전부 paste sequence 안 character 로 처리. 사용자가 직접 키보드로 Enter (OS event) 또는 `C-c` interrupt 로 paste-buffer reset 해야 풀림.

**시도해본 우회 (모두 실패 확인)**: `C-m`, `Enter` literal, `set-option -g assume-paste-time 0`, pane-level option (미지원), `C-a C-k C-u` line clear. 3-Strike Rule 발동.

#### 해결 패턴 1 — 운영 룰 (사용자 측, 가장 안전)

메인이 dispatch 한 후 사용자는 worker pane 직접 만지지 말 것. 확인 메시지를 직접 입력하고 싶다면:
- ✅ 옵션 A: 메인에 자연어로 ("OK 적용해줘"). 메인이 send-keys 처리.
- ✅ 옵션 B: 사용자가 직접 입력 + 그 자리에서 Enter 까지 누름 (한 동작 완결).
- ❌ 사용자가 입력만 하고 Enter 안 누르고 메인에 "Enter 눌러줘" 요청 → 막힘.

#### 해결 패턴 2 — Recovery (메인 측, 막힌 후)

이미 막힌 경우:
1. **사용자에게 직접 Enter 부탁** — 가장 빠르고 확실. 사용자 input 그대로 보존.
2. 또는 메인이 `tmux send-keys -t <pane> C-c` 송출 → paste-buffer interrupt → prompt reset → 새로 dispatch nudge 재송출. **단점**: 사용자 input 잃음.
3. ❌ "Space + Enter" 패턴은 사용자 input 복구 안 됨 — paste-mode 가 space 받으면 풀려서 prompt 가 "space 만 submit" 처리. Claude TUI 는 empty/whitespace message 무시하고 prompt clear 만 함. 사용자 input 사라짐. "prompt 청소 효과" 만, input 복구는 패턴 1 뿐.

#### 해결 패턴 3 — 예방 (worker launch 시점)

Worker launch 메시지에 "Dispatch confirm 은 사용자 직접 입력 X — 메인이 send-keys 로 처리" 룰 명시. 사용자가 무심코 pane attach 해도 메인 채팅으로 redirect.

**왜 §4.1 과 다른가**: §4.1 은 메인 단독 dispatch (text + Enter) 가 깨지는 케이스 — sleep 으로 분리해서 해결. §4.2 는 사용자 입력 + 메인 Enter 충돌 — sleep 무관, paste-bracketed mode 자체. 운영 룰로 회피가 표준.

### 4.3 Dispatcher self-leak — confirm 메시지 본문에 sentinel literal 박기

**증상**: 메인이 워커에 "OK proceed — apply changes. Build failure = STOP + diagnose + `[[WORKER_STOPPED]]`" 같이 confirm-OK 메시지 본문에 sentinel literal 박음 (worker 교육 의도). 그 메시지가 worker pane 의 prompt 라인에 paste 됨 → monitor 재시작 직후 iter=1 pane capture 에서 매칭 → ALERT-CONFIRM 즉시 발사. 워커는 정상 apply 중인데 monitor 가 confirm-pending 오인.

**원인 (2 가지 결합)**:
1. Monitor 의 tail window 가 30 줄 — pane bottom 5 줄에 paste 된 메시지 항상 캡처.
2. iter=1 즉시 매칭 — monitor 재시작 직후 첫 polling 에서 "방금 paste 된 sentinel 토큰" 을 fresh emission 으로 오인.

#### 해결 패턴 1 — Dispatcher 룰 (가장 중요)

Confirm 메시지 / dispatch instruction 본문에 sentinel literal 박지 말 것. 워커에게 "X 상황에 sentinel 박아라" 교육하려면:
- ✅ ASCII art 분해: ``Build failure = STOP + diagnose + `[`+`[`+`WORKER_STOPPED`+`]`+`]` ``
- ✅ 우회 표현: "Build failure = STOP + diagnose + WORKER_STOPPED sentinel"
- ❌ Literal sentinel: "Build failure = STOP + diagnose + [[WORKER_STOPPED]]"

#### 해결 패턴 2 — Monitor 측 자동 보강 (omc_monitor.sh v3.3)

자동 보강 — dispatcher 가 실수로 literal 박아도 false-positive 차단:
- `tail_window`: 30 → 15 줄 (워커 자체 sentinel emit 은 bottom 5 줄 안)
- `iter=1 skip`: 첫 polling 에서 sentinel/heuristic 모두 스킵, iter=2 부터 매칭 (scrollback drift 한 cycle 대기)

#### 해결 패턴 3 — 워커 정상 apply 중에 monitor 재시작 안 하기

가능하면 monitor 한 instance 가 task 전체 lifecycle (dry-run → confirm → apply → done) 을 한 번에 watch. 재시작은 stale alert / fail alert 받았을 때만. confirm 보낸 직후 새 monitor 재시작 = scrollback 충돌 위험.

---

## 5. Monitor 단계 함정

### 5.0 Sentinel-emit 룰 — confirm-pending 결정론화 (기본 운영)

Monitor 의 confirm-pending 감지가 자연어 heuristic ("STOP — awaiting", "Decisions needed") 만 쓰면 worker 메시지 wording 에 따라 깨짐. 해결: worker dispatch 시점에 명시적 sentinel 출력 룰 박기.

**Dispatch task description 마지막에 다음 sentinel 룰 항상 포함**:

```markdown
## Monitor sentinel 룰 (필수) — square bracket 형식이 canonical

다음 상태 도달 시 exact literal sentinel 한 줄 출력 — monitor 가 결정론적으로 잡음. 자연어 묘사로 대체 X:

- **Dry-run / confirm-pending (G1 plan 완료, main confirm 대기)**: `[[CONFIRM_PENDING]]`
- **Worker stop (lease 만료, race, fatal error)**: `[[WORKER_STOPPED]] reason: <한 줄>`
- **Worker blocked (외부 의존성, 사용자 자료 필요)**: `[[WORKER_BLOCKED]] need: <한 줄>`

sentinel 은 본문에 한 번만. 설명·plan 은 sentinel 앞 또는 뒤 줄에. monitor 는 grep 으로 즉시 alert (heuristic 매칭 대비 false positive 0).
```

**Backward compat**: angle-bracket 형식 (`<<AWAITING_MAIN_CONFIRM>>` 등) 은 기존 워커 호환용. omc_monitor.sh v3.1+ 가 angle + square 둘 다 OR 매칭. **신규 dispatch 는 square bracket 만**.

**Monitor 측**: `SENTINEL_PATTERN` 매칭이 primary, 자연어 `CONFIRM_PATTERNS` 는 fallback (sentinel 미도입 worker 호환). exit code 4 = ALERT-CONFIRM.

**왜 더 안정**: wording 의존성 제거 / 한·영 mix wording OK (sentinel 은 ASCII fixed) / False positive 0 / Polling 15 초로 단축 가능 (`POLL_INTERVAL=15` env var).

### 5.1 Sentinel self-leak — angle bracket self-confusion

**증상**: dispatch task 본문에 "완료 시 `<<AWAITING_MAIN_CONFIRM>>` 출력" 같이 메타-instruction 박으면, 워커가 본문 작성할 때 sentinel 문자열을 literal 로 박지 않으려고 *자체 회피*: `< < AWAITING_MAIN_CONFIRM > >` (공백 삽입) 또는 빈 `<>` 만 남김. figure 보고 메시지 끝에 빈 `<>` 누적 발견.

**원인**: 워커가 "monitor 가 내 출력에서 sentinel 찾으니 본문 설명용 텍스트에서 실제 sentinel 박으면 false positive 날 것" 으로 *과잉 추론* → 자기 출력에서 sentinel 토큰을 중간 비운 빈 bracket 으로 회피. 메인 dispatch 가 "literal 박는 방법" 명시 안 해서 발생.

#### 해결 패턴 1 — Dispatcher 측 변형 표기

dispatch 본문에서 sentinel 을 *설명* 할 때는 ASCII art 로 분해해서 박을 것 — 워커가 자기 출력에서 동일 표기 따라 하지 않게:

```markdown
## Monitor sentinel 룰

완료 시 다음 토큰을 한 줄에 붙여서 출력 (5개 토큰 연결):
  `<` + `<` + `AWAITING_MAIN_CONFIRM` + `>` + `>`

실제 출력은 위 5개를 공백 없이 이어붙인 12자 문자열.
```

#### 해결 패턴 2 — Sentinel 을 square bracket 으로

더 안전: `[[CONFIRM_PENDING]]` / `[[WORKER_STOPPED]]` / `[[WORKER_BLOCKED]]` 운용. angle 보다 markdown/HTML 파서 충돌 적고, "불완전 형태" (`<>`) 같은 partial leak 발생 안 함 (`[]` 빈 형태는 monitor regex 와 명백히 다름).

Monitor 양쪽 sentinel 모두 인식 (v3.1+ backward compat).

#### 해결 패턴 3 — Sentinel 생략 (간단한 경우)

워커가 figure/file 생성 후 곧바로 사용자 검토 요청하는 단순 워크플로우 (image generator 등) 는 sentinel 자체 생략 가능. 메인이 워커 출력 직접 받아 사용자께 보고만 하면 됨. sentinel 은 multi-SOP gate 처럼 메인 확인이 명시적 동기화 지점일 때만.

**Default 룰**:
- 단순 generator/editor 워커 → sentinel 생략, 한 줄 보고만
- Multi-SOP gate 가 있는 워커 → square bracket sentinel 박기
- 기존 angle bracket sentinel 박은 워커 → 그대로 두기 (monitor 양쪽 인식)

### 5.2 Dispatcher self-leak

§4.3 와 동일 패턴 — 메인이 sentinel literal 을 dispatch 메시지에 박아 monitor false-positive 유발. dispatcher 측 회피 + monitor v3.3 의 tail_window 축소 + iter=1 skip 으로 보강. §4.3 본문 참조.

### 5.3 Heuristic false-positive — 워커 plan 본문의 "결정 필요" prose

**증상**: 워커가 plan.md 작성 중 본문에 "slide 38 정량 결과 출처 불명 → 사용자 결정 필요" 같이 *설명용 텍스트* 로 "확인 필요" / "결정 필요" 박았는데, monitor v3.0 의 `CONFIRM_PATTERNS` 한국어 매칭 ("확인 필요", "승인 대기", "G2 진행 전.*필요") 이 즉시 매칭 → ALERT-CONFIRM (exit 4). 워커는 plan 작성 *진행 중* 이었고 confirm-pending 아님.

**원인**: 한국어 "확인 필요" / "결정 필요" 는 plan/analysis 본문에 자연스럽게 등장하는 descriptive label. heuristic 이 *intent (synchronization point)* 와 *description (annotation)* 둘 다 잡아서 false-positive.

#### 해결 (omc_monitor.sh v3.2)

1. **`CONFIRM_PATTERNS` 에서 bare 한국어 어구 제거** — "확인 필요" / "결정 필요" / "G2 진행 전.*필요" / "승인 대기" 모두 빠짐. 영문 "please confirm" / "shall I proceed" 같은 명시적 imperative 만 유지. 이모지 sync marker (`✅ / ❌`, `Apply.*\?[[:space:]]*✅`) 보존.
2. **`MONITOR_NO_HEURISTIC=1` env var** — heuristic 완전 끄고 sentinel + deliverable + stale 만. plan-writing 워커처럼 prose false-positive 빈번 시:
   ```bash
   MONITOR_NO_HEURISTIC=1 bash omc_monitor.sh - - %18 600 /workdir section3_plan.md
   ```
3. **Deliverable-only watcher 대안** — pane 추적 끄고 파일 mtime 만 polling:
   ```bash
   DELIVERABLE=/workdir/plan.md START=$(date +%s)
   while true; do
     if [ -f "$DELIVERABLE" ] && [ "$(stat -f %m "$DELIVERABLE")" -gt "$START" ]; then
       echo "[ALERT-DONE] plan.md created"; exit 0
     fi
     sleep 30
   done
   ```

**운영 룰**:
- Plan-writing / analysis 워커 → `MONITOR_NO_HEURISTIC=1` 또는 deliverable-only watcher
- Multi-SOP gate 워커 → sentinel 박는 워커라 heuristic 없이 sentinel 만 봐도 OK → `MONITOR_NO_HEURISTIC=1`
- Heuristic 활성 (default) → 영문 imperative + 이모지 marker 만 잡음
- 사용자 친 "확인 필요" 어구로 confirm 요청하고 싶으면 → 이모지 (`✅ / ❌`) 또는 영문 "please confirm" 명시

### 5.4 Cogitated 카운터 사각지대 — 3-signal monitor 가 못 잡는 케이스

**증상**: 워커가 같은 ledger 파일을 메인과 동시 수정 → "File must be read first" Edit 에러 → 10+ 분 thinking 으로 복구 모색. Claude TUI 는 thinking 동안 pane 에 `✻ Cogitated for XmYs ↓ token` 라인을 분 단위로 갱신 → pane content hash 매 분 변함 → stale 카운터 reset → ALERT-STALE 안 발사. 사용자가 "뭔가 멈춘 거 같은데?" 직접 발견해야 알게 됨.

**검증된 사례**: W1 워커가 dispatch_log.md Edit 실패 → 10 분 31 초 thinking → 사용자 "멈추지마." trigger → 자체 회복. monitor 는 status=in_progress 만 보고 stale 알림 zero.

**보완 패턴 옵션**:
1. **Pane hash 추출 시 thinking 라인 제외** — `grep -v 'Cogitated\|Embellishing\|Precipitating'` 후 hash. 변경 없이 hash 같으면 진짜 freeze.
2. **Task version 단독 polling** (pane hash 무시) — omc task version 은 워커가 실질적 progress 만들 때만 증가. pane false-positive 회피.
3. **Thinking 시간 자체를 stale signal 로** — Cogitated XmYs 추출, 10 분 초과 시 alert. ALERT-LONG-THINK 형태로 정보성.

**운영 룰**:
- 메인이 워커 dispatch 직후엔 ledger 파일을 안 만지는 룰 강화 — 동시 수정 race 회피.
- Monitor 잠잠한데 워커 진행 의심스러우면 사용자가 직접 capture-pane 으로 확인 후 nudge — 자동화 한계 인지.
- Thinking 5 분 초과 발견 시 monitor 로그에 정보 출력 (stale alert 와 별도 신호) 권장.

### 5.5 Monitor v2 — 5-signal 사각지대 보강

3-signal monitor 가 못 잡는 함정 3 종을 v2 (`omc_monitor.sh`) 가 보강:

1. **Dry-run confirm-pending idle** — 워커가 "Awaiting main confirm" 으로 의도적 정지. status 는 in_progress 지만 사용자 입력 대기 중, stale 카운터 hash 변경으로 reset. deliverable 파일 endpoint monitor 는 영원히 대기.
2. **User typed but no Enter** — §4.2 와 동일 root cause. 메인이 send-keys 로 Enter 보내도 무시.
3. **Pre-existing deliverable false-DONE** — dry-run 에서 cp 로 clean copy 생성하면 deliverable glob 매칭은 되지만 진짜 patch 아직 진행 중. mtime 비교 (mtime > monitor_start_epoch) 로 해결.

**v2 신규 alert 2 종 + 1 endpoint 보강**:
- **ALERT-CONFIRM (exit 4)** — pane content 에 "Awaiting main confirm" / "Decisions needed" / "STOPPING" / `✅ / ❌` 패턴 감지.
- **ALERT-TYPED-NOOP (exit 5)** — `❯ <text>` 가 prompt 에 입력만 되고 Enter 미전송. 높은 우선순위 (Enter 만 보내면 풀림).
- **ALERT-DONE 보강** — deliverable mtime 이 monitor_start_epoch 보다 새로워야 발사. cp 직후 untouched copy 무시.

**호출 형식** (pane-only 모드 포함):
```bash
bash ~/claude-settings/installer/scripts/omc_monitor.sh \
  <team|-> <task_id|-> <pane> [stale_sec=300] [cwd=PWD] [deliverable_glob]
```

team_name/task_id 둘 다 `-` 두면 omc API polling 스킵, pane content 만 polling.

**Endpoint 선택 룰**: G2/G3 multi-step SOP 있는 작업은 최종 산출물 (report.md 등) 을 endpoint 로 — verify_report.json 이나 edited.pptx 같은 중간 파일은 false-DONE 위험. 최종 deliverable 이 마지막 step 에서만 작성되는 파일이어야 함.

### 5.6 개선 monitor 구현 — 3-signal 동시 감시

`status` (정상/실패 종료) + `task version` (heartbeat proxy) + `pane content hash` (워커 활동) 셋 동시 polling:

```bash
# zsh 호환성 주의: $status, $hash 는 zsh read-only 예약 변수 — 절대 사용 X
# (사용 시 'read-only variable' 에러로 monitor 즉시 exit 1)
#
# Stale 카운트는 'in_progress' 상태에서만 누적 — pending/completed/failed/빈 status 는 reset
# (이 보호 없으면 completed 후 잔존 polling 1 회에서 pane idle → 잘못된 stale alert 발사)

TEAM=...; ID=...; PANE=...; STALE_THRESHOLD=300   # 5 분 (3 분은 long-thinking false-positive)

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
    pending)   stale_count=0; sleep 30; continue ;;   # 워커 claim 전, stale 아님
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

**Stale 카운트 룰** (false-positive 방지):
- `pending`: 워커 claim 전 — 정상 대기. reset.
- `in_progress`: stale 체크 대상 — version + pane hash 둘 다 변화 없어야 누적.
- `completed`/`failed`: 즉시 exit.
- 빈 응답: API 일시 오류 — reset (다음 polling 재확인).

**Threshold**: 180 초 (3 분) 는 long-thinking (Cogitated 1m+) 흔한 워커에서 false-positive 빈번. **300 초 (5 분) 가 실전 안전**. 단순 작업만 monitor 시 180 도 OK.

### 5.7 Monitor 실행 모드 — 셸 스크립트 파일 사용 의무

위 monitor 를 `Bash run_in_background: true` 의 인라인 eval 로 띄우면 zsh `eval` 의 큰 코드 + python3 here-doc quoting 충돌로 *silent 죽음* 가능. 해결:

1. **셸 스크립트 파일로 분리** — `~/claude-settings/installer/scripts/omc_monitor.sh` 가 영구 보존 위치. 임시 디버깅용으로만 `/tmp/omc_monitor.sh` 사용.
2. Bash background 호출: `bash ~/claude-settings/installer/scripts/omc_monitor.sh <team> <id> <pane> [stale_sec] [cwd]`.
3. 스크립트 내부 매 polling 결과를 `echo "[POLL ... status=... version=... stale=...]"` 로 log → 디버깅·진행 가시성 동시 확보.

**필수 요소**:
- `#!/bin/bash` shebang (zsh 충돌 회피)
- arg 4 + optional 2 (team / id / pane / stale_sec / cwd)
- status 분기 (completed / failed / pending / in_progress / 빈응답)
- iteration counter + log echo
- 종료 코드: 0=done / 1=fail / 2=stale / 3=arg 오류

**인라인 OK 케이스**: 단순 monitor (status only, log 없음) 는 인라인 작동. 3-signal + log 같이 복잡해지면 셸 파일 분리 안전.

**종료 경로 3 개**: `completed` → 정상, `failed` → 실패, `STALE_THRESHOLD` 정체 → stale alert. 셋 다 push 알림이라 사각지대 0.

**Stale 처리 표준**: stale alert 받으면 메인이 (1) `tmux capture-pane` 으로 워커 현재 상태 확인, (2) nudge 메시지 + §4.1 2-step Enter 로 깨움, (3) 깨어나면 새 monitor 재시작, (4) 안 깨어나면 사용자에게 "shutdown 후 재 dispatch" 옵션 제안.

**언제 단순 vs 개선**: 단순 작업 (한 파일 surgical edit, 빌드 1 회) 은 단순 monitor 충분. Multi-SOP (parsing → restructure → build → verify → report 같은 5+ step) 은 SOP 간 freeze 위험 → 개선 monitor 권장.

---

## 6. Operations — 표준 절차

### 6.1 표준 진단 절차 — 매 사용자 발언 전 의무

워커 상태를 발언/결정 근거로 쓰기 전:
```bash
cd <working dir>
bash ~/claude-settings/installer/scripts/omc_status.sh
```
한 화면에 모든 team task 상태 + tmux pane state 정리. 이 명령 결과를 보고 발언. "W4 가 멈춰있는 거 같다" 같은 직관 발언 금지 — `omc_status.sh` 결과로만 판단.

**stdout/stderr 섞임 함정**: `omc team api ...` 첫 줄에 "[team] canonicalized duplicate worker entries: worker-1" 같은 비-JSON 라인이 stdout 으로 떨어짐. 단순 `... | python -m json.tool` 깨짐. 회피: `grep '^{' | head -1` 로 첫 JSON 라인만 추출.

### 6.2 Task 생성 — wrapper 사용 의무

`omc team api create-task` 직접 호출 금지. 대신:
```bash
bash ~/claude-settings/installer/scripts/omc_create_task.sh <team_name> "<subject>" <description_file_or_->
```
Wrapper 가 — (1) JSON 안전 인코딩, (2) stderr 섞임 필터, (3) ok=false 응답 감지, (4) 중복 호출 방지 — 모두 처리. 성공 시 task_id stdout, 실패 시 stderr + exit 1.

### 6.3 Pane label 자동 부여 — 매 launch 후 표준 절차

Claude Code TUI 가 pane_title 을 현재 task description 으로 동적 갱신. 메인이 `tmux select-pane -T '[W1] ...'` 로 수동 부여한 라벨은 워커 다음 작업 시작 시 덮어써짐.

해결: tmux `pane-border-format` 에 pane_index 기준 hardcoded 라벨 + Claude 동적 title 병기. 자동화:

```bash
bash ~/claude-settings/installer/scripts/omc_pane_label.sh apply \
  '0=[MAIN] User chat' \
  '1=[W1] PPT Editor' \
  '2=[W2] Image' \
  '3=[W3] Reviewer'
```

결과: 각 pane 위 border 에 `[W1] PPT Editor | ✳ Execute worker inbox task...` 형태. 좌측 영구 라벨, 우측 Claude 동적 정보.

**TUI 자체 pane title override 차단 (v3+)**: omc_pane_label.sh v3+ 가 `tmux set -g allow-set-title off` 까지 함께 적용 → tmux 가 OSC title escape 자체를 ignore. pane_title 영구 고정, watchdog 불필요. (`clear` 호출 시 자동 복원)

**Pane index 재배치 함정과 결합**: 새 워커 launch 시 기존 pane index 가 재배치되는 경우 잦음 — apply 호출 *전* `tmux list-panes -a` 로 현재 매핑 재확인 필수.

기타 명령:
- `bash omc_pane_label.sh show` — 현재 라벨 + pane 상태 확인
- `bash omc_pane_label.sh clear` — 라벨 + tmux pane-border-status 모두 리셋

### 6.4 Task lifecycle 함정 — standby 를 task 로 보내지 말 것

`omc team 1:claude "<standby 컨텍스트>"` 로 launch 하면 그 컨텍스트 자체가 task 1 로 등록됨. 워커는 환경 검증만 하고 task completed 처리 → 다음 dispatch 가 안 들어옴.

**올바른 운영**: launch 시엔 역할·SOP 만 전달, *실제 변경 명세* 는 `omc team api add-task` 로 새 task 추가. 워커는 task queue 비어도 process alive 유지 (idle 대기).

### 6.5 Batch dispatch 룰

Q&A 한 건마다 dispatch 하지 말고 변경 메모 **3-5 건 누적 후 한 번에 dispatch**. 이유:
- 변경 명세 + tmux paste + Enter 우회 + 빌드 검증 — 매번 overhead.
- 워커는 한 번의 task 에서 여러 파일 surgical edit 후 단일 빌드 검증이 더 안전 (회귀 발견 통합).
- 메인 패널에서 누적 메모를 카운터로 관리, 적정 시점에 "지금 워커로 dispatch 할까요?" 사용자 확인 후 진행.

### 6.6 Auto-monitor 패턴 — 모든 task 생성에 완료 알림 묶기 (의무)

매 task 생성마다 polling 스크립트를 `Bash run_in_background: true` 로 같이 띄움 → 워커 완료 시 메인 패널이 push 알림. 사용자가 "끝났니?" 묻지 않아도 됨.

**Idle worker 도 monitor 띄울 것**: Team launch / task complete 직후 worker idle 진입 시점에도 *pane-only monitor (sentinel + stale)* 띄워야 함. 이유: 사용자가 워커 pane 에 직접 입력 (§4.2) / 워커 자발적 "exit" 시도 (worker self-shutdown 함정) 발생 → 메인이 monitor 없으면 stuck 발견 못함. Idle monitor:
```bash
MONITOR_NO_HEURISTIC=1 bash ~/claude-settings/installer/scripts/omc_monitor.sh \
  - - <pane-id> 1500 <workdir> - 2>&1 &
```
- team/task_id `-` = pane-only mode (omc API polling 스킵)
- deliverable `-` = idle watching, ALERT-DONE 안 발사. Sentinel emit 또는 stale 1500s 후 ALERT-STALE.
- 새 task 들어오면 idle monitor 종료 + task-specific monitor (team + task_id + deliverable) 로 재시작.

**Task 생성 = monitor 대상 — 두 경로 모두**:
- **경로 A: 새 team launch** — `omc team N:claude "<text>"` 의 launch text 자체가 task 1 로 자동 등록. "team launch ≠ dispatch" 로 분리 인지하면 회귀 발생.
- **경로 B: 기존 team 에 task 추가** — `omc team api create-task` 응답에서 `task_id` 캡처 후 monitor.

**표준 절차 (3 step, 두 경로 동일)**:
1. **Task 생성**: 경로 A (team launch) 또는 경로 B (`create-task`). 응답에서 `task_id` 확인.
2. **워커 nudge** (경로 B 만 필요 — 경로 A 는 launch 시 자동 paste): `tmux send-keys -t <pane-id> "Task <id> ..."` → `sleep 2` → `tmux send-keys -t <pane-id> C-m` (§4.1 우회).
3. **Background monitor** (`Bash run_in_background: true`):
   ```bash
   until [ "$(omc team api read-task --input '{"team_name":"<team>","task_id":"<id>"}' --json 2>/dev/null \
            | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("data",{}).get("task",{}).get("status",""))')" = "completed" ]; do
     sleep 30
   done
   echo "[ALERT] Task <id> (<short subject>) completed at $(date '+%H:%M:%S')"
   ```

Polling 간격: 30 초 표준. 길면 응답성 저하, 짧으면 `omc team api` overhead 누적. 워커 작업 2 분 미만 예상이면 15 초.

**대안**: `Monitor` 도구로 동일 스크립트 띄우면 stdout line 마다 push — 중간 progress 보고 필요할 때. 단순 종료 알림만 필요하면 `Bash run_in_background` 가 가볍고 표준.

알림 수신 후: 메인 자동 알림 → 그 시점에 워커 회신 (변경 요약, 빌드 결과, 시각 검증 의견) 확인 + 다음 Q&A 진행 여부 판단.

### 6.7 Worker pool 자동 선택 — 사용자 매번 결정 X

여러 워커 (team) 가 떠 있을 때 사용자가 매 dispatch 마다 "어느 워커?" 결정하지 않아도 됨. 자체 절차:

1. 모든 워커 team 의 task 상태 확인 (`omc team api list-tasks` per team, `in_progress` count 핵심).
2. **Idle 워커** (in_progress=0) 만 후보 선별.
3. 둘 다 idle → **workspace state 워커 default** (state 가 `./.omc/` 안에 있는 쪽이 운영 깔끔).
4. 한쪽만 idle → 그 쪽 dispatch.
5. 둘 다 busy → 사용자에게 "큐잉 vs 대기" 한 번 확인 (드물게 발생).

**같은 파일 conflict 회피**: 같은 .tex/.py/파일을 두 워커가 동시 만지지 말 것. busy 워커는 자동 후보 제외에 흡수됨. 독립 파일이면 동시 dispatch OK.

### 6.8 워커 state 경로 trade-off

team launch 시점 cwd 에 따라 state 디렉토리 위치 결정:
- **Cwd = 작업 디렉토리** → state in `<workdir>/.omc/state/team/<slug>` — 운영 깔끔 (모든 명령 같은 cwd), 기본 권장.
- **Cwd = /tmp** (또는 다른 곳) + `--cwd <target>` → state in `/tmp/.omc/state/team/<slug>` — 같은 디렉토리에 두 team launch 시 격리용. 단점: api 명령마다 `cd <state-cwd>` 필요.

같은 cwd 두 번째 team launch 는 §3.4 의 silent fail.

### 6.9 omc state wipe — orphan-cleanup self-invoke 함정

**증상**: 워커가 lease expiry 시 자기 task / team 전체 삭제. 회복 불가. 디스크 산출물은 살아남음.

**회피**: 워커 SOP 에 "orphan-cleanup is leader-only — never self-invoke. On lease expiry, send-message + idle." 명시.

### 6.10 누적 함정 4종 + 표준 진단 (요약)

이번 류의 모든 함정은 결국 — (1) 메인이 잘못된 상태 인식, (2) 사용자 정정, 의 cycle 로 노출됨. 4 카테고리:

1. **omc CLI stdout/stderr 섞임** — §6.1 참조.
2. **omc state wipe (orphan-cleanup self-invoke)** — §6.9 참조.
3. **Claude TUI pane title 동적 override** — §6.3 참조 (v3 의 `allow-set-title off` 가 fix).
4. **Monitor stale-aware 의 thinking-카운터 사각지대** — §5.4 참조.

---

## 7. 의존 자원 (claudebase 정본)

본문이 의존하는 스크립트 — 모두 `~/claude-settings/installer/scripts/` (= claudebase 의 `installer/scripts/`) 에 정본:

| 스크립트 | 역할 | 정본 sub-version 확인 |
|---|---|---|
| `omc_monitor.sh` | v3.x (sentinel + heuristic + stale, pane-only mode) | 파일 header `# Version: ...` 확인 |
| `omc_pane_label.sh` | v3+ (allow-set-title off 적용) | `bash omc_pane_label.sh --version` 또는 파일 header |
| `omc_status.sh` | team task + tmux pane 상태 통합 출력 | 단일 버전 |
| `omc_create_task.sh` | create-task wrapper (JSON 안전 + stderr 필터) | 단일 버전 |

omc 플러그인 본체 (`omc team`, `omc team api ...`) 는 별도 evolve — `omc update --check` 로 lag 확인.

본문이 참조하는 절대경로 `~/claude-settings/...` 는 사용자 친화적 명시. 다른 위치에 clone 한 경우 `$CLAUDEBASE_ROOT/installer/scripts/` 로 읽으면 됨 (default `~/claude-settings`).

---

## Related

- `omc-reference` skill (omha 또는 omc 플러그인 본체 제공) — OMC agent catalog / tools / pipeline
- `~/claude-settings/installer/scripts/` — 본문 의존 스크립트 정본
- 본문 변경 history: `git log -- runtime/skills/omc-teams-ops/SKILL.md`

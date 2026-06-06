---
name: omc-teams-ops
description: omc-teams (tmux pane-separated workers) launch/operations/debugging manual. 6+ pitfalls (leader-session-1-team, paste-bracketed Enter absorption, sentinel self-leak, dispatcher self-leak, heuristic false-positive, Cogitated counter blind spot) + omc_monitor.sh v3.x operations + verified workaround patterns. Invoke right before an omc team launch, when debugging sentinel/dispatch, or when diagnosing a stalled monitor. The body is organized as a symptom-cause-fix decision tree; for the chronological origin of each pitfall see the git log.
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

Operations manual for launching tmux pane-separated workers with `omc-teams`. The body is structured as a **symptom -> diagnosis -> fix** tree. The 6+ pitfalls that accumulated chronologically are *grouped by stage* so you can navigate to them immediately in an emergency.

## 0. Current status and division of roles with omha

- **The omc-teams CLI itself is alive** — all the commands the body relies on (`omc team`, `omc team api ...`, `omc team shutdown`, etc.) are provided by the omc plugin core (v4.14+ at the time this was written).
- **Scope of this SKILL**: the *operational pitfalls and workaround patterns* of omc-teams. What omha absorbed is the routing/skill registry side (the former `routing-verdict-reminder.py`, the `omc-reference` catalog), not team operation itself, which omc still owns.
- **drift signals** (if any of the following occurs, the command formats in the body may be stale — check the omc plugin changelog):
  - `unknown command` or `flag --no-decompose deprecated` when calling `omc team`
  - `data.task.status` key absent in the `omc team api read-task` response
  - `omc team api create-task` returns plain text only (the current behavior is a JSON response)
- SSOT separation: the monitor scripts (`omc_monitor.sh` etc.) and the wrapper scripts are canonical in `installer/scripts/` of this repo (claudebase). They evolve separately from the omc plugin core.

---

## 1. Use-case judgment (5 seconds before invoke)

**Use it when**
- You need to *visually* separate the user's Q&A/conversation flow (main panel) from file edits (worker panel). Interview prep, lecture material edits, long document review.

**Do NOT use it when**
- A single surgical edit of 1-3 lines — Edit from main is faster.
- The spec is ambiguous — scope it first with `/team`.
- Reference-bound writing — risk of citation hallucination.

---

## 2. Symptom-by-symptom diagnostic tree

| Symptom (what the user sees) | Cause location | Body section |
|---|---|---|
| "Leader session already owns active team" error | Launch stage / one_team_per_leader | §3.1 |
| After worker launch the prompt is only pasted and does not execute | Dispatch / Enter absorption | §4.1 |
| User typed directly into the worker pane but main's Enter is ignored | Dispatch / paste-bracketed | §4.2 |
| Monitor fires a false ALERT-CONFIRM (worker is progressing normally) | Monitor / sentinel self-leak or dispatcher self-leak | §5.1, §5.2 |
| False alert from Korean prose like "확인 필요" while a plan is being written | Monitor / heuristic | §5.3 |
| Worker has been thinking 10+ min but monitor gives no stale alarm | Monitor / Cogitated counter blind spot | §5.4 |
| Blank screen right after worker launch, no paste either | Launch / TUI init failure or API 429 | §3.2 |
| `omc team api` response does not parse as JSON | Operations / mixed stdout/stderr | §6.1 |
| A second team launch in the same cwd silently fails | Launch / per-cwd single-team | §3.3 |

---

## 3. Launch-stage pitfalls

### 3.1 Cannot add a team within the same leader session

**Symptom**: after the first `omc team 1:claude ...` launch, a second `omc team 1:claude ...` attempt in the same session -> `Leader session already owns active team`.

**Cause**: the `governance.one_team_per_leader_session: true` hardcode in the `omc team` CLI. `--new-window`, `OMC_ONE_TEAM_PER_LEADER=0`, `OMC_TEAM_NAME=...` all fail to work around it — confirmed. `omc team api` has no `add-worker` command.

**Decisive implication**: workers *cannot be added dynamically* mid-session. You must launch as an N-worker team from the start.

#### Fix pattern 1 — shut down the existing team + re-launch as N-worker (cleanest)

```bash
# (1) Force shutdown if there is an in_progress task
omc team shutdown <team-name> --force
# (2) Clean up stale state (directory remains after a force shutdown)
rm -rf .omc/state/team/<team-name>
# (3) Re-launch as N-worker
omc team N:claude "<shared role + role separation per worker>" --no-decompose --cwd <workdir>
```

**Caveats (verified)**:
- A `--force` shutdown also kills the worker processes inside the leader session panes.
- A manual pane not managed by omc (tmux split-window) is not killed automatically, but can become an *orphan* due to the leader process change — pre-clean it with `tmux kill-pane -t %<id>` (recommended).
- Disk artifacts (`.worker/dispatch_log.md`, `sections/*.tex`, etc.) are unaffected by shutdown — only `.omc/state/team/...` disappears. Reusing dispatch_log after a re-launch is OK.

#### Fix pattern 2 — direct tmux split-window (bypassing omc, temporary auxiliary worker)

For irregular situations where the N-worker launch of omc team is inconvenient (e.g., adding a temporary 1 worker while 1 worker is already up):

```bash
# (1) vertical split next to the existing W1 pane — -v required (-h would narrow main)
tmux split-window -t %1 -v -c <workdir>
# (2) Check the new pane id
tmux list-panes -a
# (3) claude TUI in the new pane
tmux send-keys -t %3 "claude --dangerously-skip-permissions" && sleep 1 && tmux send-keys -t %3 Enter
# (4) Confirm after 8-15 s of init
sleep 10 && tmux capture-pane -p -t %3
# (5) Assign a pane label
bash ~/claudebase/installer/scripts/omc_pane_label.sh apply \
  '0.0=[MAIN] ...' '0.1=[W1] ...' '0.2=[W2 manual] ...'
# (6) Task nudge: apply the 2-step Enter workaround from §4.1
```

**Constraints (since omc is bypassed)**:
- ❌ `omc team api list-tasks` does not work
- ❌ Status polling by `omc_monitor.sh` does not work — only *pane-only mode* (`team="-" task_id="-"` + deliverable) is possible
- ❌ Lease / heartbeat are not auto-managed — watch directly with capture-pane
- ✅ Artifacts communicate with main via a file-based queue (`.worker/research_inbox.md`)
- ✅ Unaffected by force shutdown (separate process)

**Recommended use case**: a temporary auxiliary worker (terminates after 1 query), or emergency action when omc state is broken and re-launch is hard. For a permanent worker, pattern 1 is recommended.

#### Fix pattern 3 — N-worker team from the start (ideal)

When you can predict at session start that "we might need 2 workers":

```bash
omc team 2:claude --no-decompose \
  "Shared role description; W1 = <editing-only SOP>; W2 = <research-only SOP>" \
  --cwd <workdir>
```

The `--no-decompose` flag prevents the task from being auto-split into as many parts as there are workers (both share the same standby context). Then assign a task to each worker with `omc team api create-task`.

**Both workers share the same cwd**: an omc team constraint — all workers share a single cwd. If you need different cwds, handle that separately.

### 3.2 Verify worker status right after launch — mandatory at every launch

`omc team launch` auto-registers the launch text as task 1 and even pastes an inbox-read nudge into the worker pane. **But it guarantees neither Enter input nor Claude TUI init.** If you assume "it worked before so it will work this time," the worker freezes with the prompt only pasted — the user discovers it themselves.

**Standard verification procedure (right after every launch)**:

1. **Right after launch**: confirm the new pane id with `tmux list-panes -t 0 -F "#{pane_index} cwd=#{pane_current_path}"` (*pane index reshuffle pitfall* — existing pane indices shift when a new worker is added).
2. **After 20-30 s**: read the worker carefully with `tmux capture-pane -pt <pane-id> -S -25`:
   - blank screen (Claude TUI init incomplete) -> wait 30 s more, then re-capture
   - pasted but no Enter -> apply the §4.1 2-step Enter workaround
   - `[API 429]` -> rate limited. Wait 5-10 min, or shut down another worker and re-launch
   - normal execution like "Reading the inbox now ..." -> OK, bring up the monitor
3. **Still blank with no paste after 30 s** -> process failure. Shutdown + re-launch.

### 3.3 Risk of launching workers simultaneously — sequential is recommended

Launching multiple workers simultaneously (B right after A) is only safe if §3.2 verification passes for *both*. Verified breakage cases:

- **API 429**: main usage + two new workers initializing at once = Anthropic API load. If you see 429, the worker processes are alive but do not respond -> main misreads it as "did Enter not get pressed?"
- **Uneven TUI init delay**: two workers booting at once -> one takes 20 s, the other 60 s. Verifying based on the fast one misses the slow one.

**Recommendation**:
- **Sequential**: launch worker A -> verification passes -> confirm task 1 in_progress -> launch worker B. There is a 2-3 min overhead but it is stable.
- **When parallelism is needed**: apply §3.2 verification to *each* of the two. If you find a 429, shut down one worker and switch to sequential.

### 3.4 Second team launch in the same cwd — silent fail

If you attempt a second `omc team ...` in the same cwd, it *silently fails* (only the help output is emitted). omc assumes a per-cwd single-team. If isolation is needed, work around it by moving only the second worker to a different cwd or with `--cwd <target>`.

### 3.5 Team name slug — ASCII start enforced

`omc team` builds the slug from the first few words of the task description (English only). A description that starts with Korean produces a meaningless slug. -> Start the description with ASCII English (e.g., "Section 5.4 LQR compression worker"). An explicit option like `--team-name` does *not exist* in the omc CLI (attempting it produces a silent help fail).

---

## 4. Dispatch / Enter-stage pitfalls

### 4.1 Dispatch Enter not transmitted — 2-step workaround pattern

**Symptom**: when you send `tmux send-keys -t <pane> "<text>" C-m` in a single call, the prompt focus wobbles during the paste of a Korean/long string and the C-m gets *absorbed* into the buffer. It only pastes and does not execute.

**Workaround**:
```bash
tmux send-keys -t <pane-id> "<task description>"   # text only
sleep 2
tmux send-keys -t <pane-id> C-m                    # Enter separately
```

After step 1, check the prompt with `tmux capture-pane -pt <pane-id> -S -20`. If only the input went in, retry only step 2. If automation fails, fall back to asking the user "please press Enter once in the worker panel."

### 4.2 User input + main send-keys collision — Claude TUI paste-bracketed mode absorption

**Symptom**: after main sends a dispatch nudge, the user types directly into the worker pane ("OK proceed — apply..."). But they return to main without pressing Enter. Main attempts Enter with `tmux send-keys -t %1 C-m` -> **all absorbed**. The user input is stuck in the ❯ prompt and the worker does not progress.

**Cause**: the ❯ prompt of the Claude TUI is in paste-bracketed mode. After the user's keyboard (OS keyboard event) input, the paste-buffer stays "open." When an external tmux send-keys (pseudo-tty escape sequence) comes in, it gets absorbed as part of the paste content. C-m / Enter / Ctrl-keys are all handled as characters within the paste sequence. It only releases when the user presses Enter directly via the keyboard (OS event), or resets the paste-buffer with a `C-c` interrupt.

**Workarounds tried (all confirmed to fail)**: `C-m`, `Enter` literal, `set-option -g assume-paste-time 0`, pane-level option (unsupported), `C-a C-k C-u` line clear. The 3-Strike Rule kicked in.

#### Fix pattern 1 — operational rule (user side, safest)

After main dispatches, the user must not touch the worker pane directly. If they want to type a confirmation message themselves:
- ✅ Option A: tell main in natural language ("OK, apply it"). Main handles send-keys.
- ✅ Option B: the user types directly and presses Enter right then (one complete action).
- ❌ User types only, does not press Enter, and asks main to "press Enter" -> blocked.

#### Fix pattern 2 — recovery (main side, after it is blocked)

If already blocked:
1. **Ask the user to press Enter directly** — fastest and most certain. Preserves the user input as-is.
2. Or main sends `tmux send-keys -t <pane> C-c` -> paste-buffer interrupt -> prompt reset -> re-send a fresh dispatch nudge. **Downside**: the user input is lost.
3. ❌ The "Space + Enter" pattern does not recover the user input — when paste-mode receives a space it releases, so the prompt treats it as "submit space only." The Claude TUI ignores empty/whitespace messages and only clears the prompt. The user input disappears. It only has a "prompt-cleanup effect"; the only way to recover the input is pattern 1.

#### Fix pattern 3 — prevention (at worker launch)

In the worker launch message, state the rule "Dispatch confirm must NOT be typed by the user directly — main handles it via send-keys." Even if the user attaches to the pane absent-mindedly, redirect them to the main chat.

**Why it differs from §4.1**: §4.1 is the case where main's solo dispatch (text + Enter) breaks — solved by separating with sleep. §4.2 is a collision of user input + main's Enter — sleep is irrelevant; it is paste-bracketed mode itself. Avoiding it via an operational rule is the standard.

### 4.3 Dispatcher self-leak — embedding a sentinel literal in the body of the confirm message

**Symptom**: main embeds a sentinel literal in the body of a confirm-OK message to the worker, like "OK proceed — apply changes. Build failure = STOP + diagnose + `[[WORKER_STOPPED]]`" (intending to teach the worker). That message gets pasted into the prompt line of the worker pane -> on the iter=1 pane capture right after a monitor restart it matches -> ALERT-CONFIRM fires immediately. The worker is applying normally but the monitor mistakes it for confirm-pending.

**Cause (two things combined)**:
1. The monitor's tail window is 30 lines — a message pasted into the bottom 5 lines of the pane is always captured.
2. iter=1 immediate matching — on the first polling right after a monitor restart, the "just-pasted sentinel token" is mistaken for a fresh emission.

#### Fix pattern 1 — dispatcher rule (most important)

Do not embed a sentinel literal in the body of a confirm message / dispatch instruction. To teach the worker "embed the sentinel in situation X":
- ✅ ASCII art decomposition: ``Build failure = STOP + diagnose + `[`+`[`+`WORKER_STOPPED`+`]`+`]` ``
- ✅ Roundabout phrasing: "Build failure = STOP + diagnose + WORKER_STOPPED sentinel"
- ❌ Literal sentinel: "Build failure = STOP + diagnose + [[WORKER_STOPPED]]"

#### Fix pattern 2 — automatic reinforcement on the monitor side (omc_monitor.sh v3.3)

Automatic reinforcement — blocks the false-positive even if the dispatcher accidentally embeds a literal:
- `tail_window`: 30 -> 15 lines (the worker's own sentinel emit is within the bottom 5 lines)
- `iter=1 skip`: skip both sentinel/heuristic on the first polling, match from iter=2 (wait one cycle for scrollback drift)

#### Fix pattern 3 — do not restart the monitor while the worker is applying normally

If possible, have a single monitor instance watch the whole task lifecycle (dry-run -> confirm -> apply -> done) in one go. Restart only when you receive a stale alert / fail alert. Restarting a new monitor right after sending a confirm = risk of scrollback collision.

---

## 5. Monitor-stage pitfalls

### 5.0 Sentinel-emit rule — making confirm-pending deterministic (default operation)

If the monitor's confirm-pending detection only uses natural-language heuristics ("STOP — awaiting", "Decisions needed"), it breaks depending on the worker message wording. Fix: embed an explicit sentinel-output rule at the worker dispatch point.

**Always include the following sentinel rule at the end of the dispatch task description**:

```markdown
## Monitor sentinel rule (required) — the square bracket format is canonical

When the following states are reached, output an exact-literal sentinel on one line — the monitor catches it deterministically. Do NOT replace with a natural-language description:

- **Dry-run / confirm-pending (G1 plan done, awaiting main confirm)**: `[[CONFIRM_PENDING]]`
- **Worker stop (lease expiry, race, fatal error)**: `[[WORKER_STOPPED]] reason: <one line>`
- **Worker blocked (external dependency, user material needed)**: `[[WORKER_BLOCKED]] need: <one line>`

The sentinel appears only once in the body. Put the explanation/plan on the line before or after the sentinel. The monitor alerts immediately via grep (false positive 0 vs heuristic matching).
```

**Backward compat**: the angle-bracket format (`<<AWAITING_MAIN_CONFIRM>>`, etc.) is for compatibility with existing workers. omc_monitor.sh v3.1+ OR-matches both angle and square. **New dispatches use square bracket only.**

**Monitor side**: `SENTINEL_PATTERN` matching is primary, the natural-language `CONFIRM_PATTERNS` is a fallback (for compatibility with workers that have not adopted the sentinel). exit code 4 = ALERT-CONFIRM.

**Why it is more stable**: removes wording dependency / KO-EN mixed wording is OK (the sentinel is ASCII fixed) / false positive 0 / Polling can be shortened to 15 s (`POLL_INTERVAL=15` env var).

### 5.1 Sentinel self-leak — angle bracket self-confusion

**Symptom**: if you embed a meta-instruction like "output `<<AWAITING_MAIN_CONFIRM>>` on completion" in the dispatch task body, when the worker writes the body it *self-avoids* embedding the sentinel string literally: `< < AWAITING_MAIN_CONFIRM > >` (inserting spaces) or leaves only an empty `<>`. You find empty `<>` accumulating at the end of figure-report messages.

**Cause**: the worker *over-reasons* that "since the monitor looks for the sentinel in my output, embedding the actual sentinel in descriptive body text will cause a false positive" -> in its own output, it avoids the sentinel token with an emptied-out empty bracket. It happens because main's dispatch did not specify "how to embed the literal."

#### Fix pattern 1 — variant notation on the dispatcher side

When *describing* the sentinel in the dispatch body, decompose it with ASCII art so the worker does not copy the same notation in its own output:

```markdown
## Monitor sentinel rule

On completion, output the following tokens concatenated on one line (5 tokens joined):
  `<` + `<` + `AWAITING_MAIN_CONFIRM` + `>` + `>`

The actual output is the above 5 joined without spaces, a 12-character string.
```

#### Fix pattern 2 — make the sentinel a square bracket

Safer: operate with `[[CONFIRM_PENDING]]` / `[[WORKER_STOPPED]]` / `[[WORKER_BLOCKED]]`. They collide less with markdown/HTML parsers than angle, and partial leaks like "incomplete forms" (`<>`) do not occur (an empty `[]` form is clearly different from the monitor regex).

The monitor recognizes both sentinels (v3.1+ backward compat).

#### Fix pattern 3 — omit the sentinel (simple cases)

A simple workflow where the worker generates a figure/file and then immediately requests user review (image generator, etc.) can omit the sentinel itself. Main just receives the worker output directly and reports to the user. The sentinel is only for cases like a multi-SOP gate where main confirmation is an explicit synchronization point.

**Default rules**:
- Simple generator/editor worker -> omit the sentinel, just a one-line report
- Worker with a multi-SOP gate -> embed the square bracket sentinel
- Worker that already embeds an angle bracket sentinel -> leave it as-is (the monitor recognizes both)

### 5.2 Dispatcher self-leak

Same pattern as §4.3 — main embeds a sentinel literal in a dispatch message, triggering a monitor false-positive. Reinforced by dispatcher-side avoidance + the reduced tail_window and iter=1 skip of monitor v3.3. See §4.3.

### 5.3 Heuristic false-positive — "결정 필요" prose in the worker's plan body

**Symptom**: while writing plan.md, the worker embeds "확인 필요" / "결정 필요" in the body as *descriptive text*, like "slide 38 quantitative result source unknown -> user decision needed (사용자 결정 필요)," but the Korean matching of monitor v3.0's `CONFIRM_PATTERNS` ("확인 필요", "승인 대기", "G2 진행 전.*필요") matches immediately -> ALERT-CONFIRM (exit 4). The worker was *in the middle of writing the plan* and was not confirm-pending.

**Cause**: the Korean "확인 필요" / "결정 필요" are descriptive labels that naturally appear in a plan/analysis body. The heuristic catches both *intent (synchronization point)* and *description (annotation)*, producing a false-positive.

#### Fix (omc_monitor.sh v3.2)

1. **Remove the bare Korean phrases from `CONFIRM_PATTERNS`** — "확인 필요" / "결정 필요" / "G2 진행 전.*필요" / "승인 대기" all dropped. Keep only explicit imperatives like the English "please confirm" / "shall I proceed." Preserve emoji sync markers (`✅ / ❌`, `Apply.*\?[[:space:]]*✅`).
2. **`MONITOR_NO_HEURISTIC=1` env var** — turns off the heuristic entirely, leaving only sentinel + deliverable + stale. When prose false-positives are frequent, as with a plan-writing worker:
   ```bash
   MONITOR_NO_HEURISTIC=1 bash omc_monitor.sh - - %18 600 /workdir section3_plan.md
   ```
3. **Deliverable-only watcher alternative** — turn off pane tracking and poll only the file mtime:
   ```bash
   DELIVERABLE=/workdir/plan.md START=$(date +%s)
   while true; do
     if [ -f "$DELIVERABLE" ] && [ "$(stat -f %m "$DELIVERABLE")" -gt "$START" ]; then
       echo "[ALERT-DONE] plan.md created"; exit 0
     fi
     sleep 30
   done
   ```

**Operational rules**:
- Plan-writing / analysis worker -> `MONITOR_NO_HEURISTIC=1` or deliverable-only watcher
- Multi-SOP gate worker -> it embeds the sentinel, so watching only the sentinel without the heuristic is OK -> `MONITOR_NO_HEURISTIC=1`
- Heuristic enabled (default) -> catches only English imperatives + emoji markers
- If you want to request confirm with a "확인 필요" phrase the user typed -> specify an emoji (`✅ / ❌`) or the English "please confirm"

### 5.4 Cogitated counter blind spot — a case the 3-signal monitor cannot catch

**Symptom**: the worker edits the same ledger file as main simultaneously -> "File must be read first" Edit error -> 10+ min of thinking trying to recover. During thinking the Claude TUI refreshes the `✻ Cogitated for XmYs ↓ token` line in the pane every minute -> the pane content hash changes every minute -> the stale counter resets -> ALERT-STALE does not fire. The user only learns of it by discovering "something seems stuck?" themselves.

**Verified case**: the W1 worker failed an Edit on dispatch_log.md -> 10 min 31 s of thinking -> the user's "Don't stop." trigger -> self-recovery. The monitor only saw status=in_progress and gave zero stale alerts.

**Reinforcement pattern options**:
1. **Exclude the thinking line when extracting the pane hash** — `grep -v 'Cogitated\|Embellishing\|Precipitating'` then hash. If the hash is the same with no change, it is a real freeze.
2. **Poll the task version alone** (ignore the pane hash) — the omc task version increments only when the worker makes substantive progress. Avoids pane false-positives.
3. **Use the thinking time itself as a stale signal** — extract Cogitated XmYs, alert when it exceeds 10 min. An informational ALERT-LONG-THINK form.

**Operational rules**:
- Strengthen the rule that main does not touch the ledger file right after dispatching a worker — avoids the simultaneous-edit race.
- When the monitor is quiet but you suspect worker progress, the user checks directly with capture-pane and then nudges — recognize the limit of automation.
- When you find thinking exceeding 5 min, it is recommended to emit info to the monitor log (a signal separate from a stale alert).

### 5.5 Monitor v2 — reinforcing the 5-signal blind spots

v2 (`omc_monitor.sh`) reinforces 3 pitfalls that the 3-signal monitor cannot catch:

1. **Dry-run confirm-pending idle** — the worker intentionally stops with "Awaiting main confirm." status is in_progress but it is awaiting user input, and the stale counter resets due to a hash change. A deliverable-file endpoint monitor waits forever.
2. **User typed but no Enter** — same root cause as §4.2. Even if main sends Enter via send-keys, it is ignored.
3. **Pre-existing deliverable false-DONE** — if the dry-run creates a clean copy via cp, the deliverable glob matches but the real patch is still in progress. Solved by mtime comparison (mtime > monitor_start_epoch).

**v2's 2 new alerts + 1 endpoint reinforcement**:
- **ALERT-CONFIRM (exit 4)** — detects the patterns "Awaiting main confirm" / "Decisions needed" / "STOPPING" / `✅ / ❌` in pane content.
- **ALERT-TYPED-NOOP (exit 5)** — `❯ <text>` is typed into the prompt but Enter is not transmitted. High priority (it releases as soon as you send Enter).
- **ALERT-DONE reinforcement** — fires only if the deliverable mtime is newer than monitor_start_epoch. Ignores an untouched copy right after cp.

**Call format** (including pane-only mode):
```bash
bash ~/claudebase/installer/scripts/omc_monitor.sh \
  <team|-> <task_id|-> <pane> [stale_sec=300] [cwd=PWD] [deliverable_glob]
```

Setting both team_name/task_id to `-` skips omc API polling and polls only pane content.

**Endpoint selection rule**: for work with a G2/G3 multi-step SOP, use the final artifact (report.md, etc.) as the endpoint — intermediate files like verify_report.json or edited.pptx risk a false-DONE. The final deliverable must be a file written only at the last step.

### 5.6 Improved monitor implementation — 3-signal simultaneous watch

Poll three at once: `status` (normal/failure exit) + `task version` (heartbeat proxy) + `pane content hash` (worker activity):

```bash
# zsh compatibility note: $status, $hash are zsh read-only reserved variables — NEVER use them
# (using them causes a 'read-only variable' error and the monitor exits 1 immediately)
#
# Stale count accumulates only in the 'in_progress' state — pending/completed/failed/empty status reset it
# (without this guard, the leftover polling cycle after completed sees pane idle -> fires a wrong stale alert)

TEAM=...; ID=...; PANE=...; STALE_THRESHOLD=300   # 5 min (3 min causes long-thinking false-positives)

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
    pending)   stale_count=0; sleep 30; continue ;;   # before worker claim, not stale
    in_progress) ;;                                    # stale check below
    *)         stale_count=0; sleep 30; continue ;;   # empty response / unknown state
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

**Stale count rules** (false-positive prevention):
- `pending`: before the worker claims — normal waiting. Reset.
- `in_progress`: subject to the stale check — accumulates only if both version + pane hash are unchanged.
- `completed`/`failed`: immediate exit.
- empty response: transient API error — reset (re-check on the next polling).

**Threshold**: 180 s (3 min) produces frequent false-positives on workers where long-thinking (Cogitated 1m+) is common. **300 s (5 min) is safe in practice.** When monitoring only simple work, 180 is OK.

### 5.7 Monitor execution mode — mandatory use of a shell script file

If you bring up the above monitor as an inline eval of `Bash run_in_background: true`, the large code in zsh `eval` plus python3 here-doc quoting conflicts can cause a *silent death*. Fix:

1. **Split into a shell script file** — `~/claudebase/installer/scripts/omc_monitor.sh` is the permanent location. Use `/tmp/omc_monitor.sh` only for temporary debugging.
2. Bash background call: `bash ~/claudebase/installer/scripts/omc_monitor.sh <team> <id> <pane> [stale_sec] [cwd]`.
3. Log each polling result inside the script with `echo "[POLL ... status=... version=... stale=...]"` -> securing both debugging and progress visibility.

**Required elements**:
- `#!/bin/bash` shebang (avoids the zsh conflict)
- 4 args + optional 2 (team / id / pane / stale_sec / cwd)
- status branching (completed / failed / pending / in_progress / empty response)
- iteration counter + log echo
- exit codes: 0=done / 1=fail / 2=stale / 3=arg error

**Inline-OK case**: a simple monitor (status only, no log) works inline. Once it gets complex like 3-signal + log, splitting into a shell file is safe.

**3 exit paths**: `completed` -> normal, `failed` -> failure, `STALE_THRESHOLD` stall -> stale alert. All three are push notifications, so the blind spot is 0.

**Stale handling standard**: when you receive a stale alert, main (1) checks the worker's current state with `tmux capture-pane`, (2) wakes it with a nudge message + the §4.1 2-step Enter, (3) restarts a new monitor once it wakes, (4) if it does not wake, proposes the "shutdown then re-dispatch" option to the user.

**When simple vs improved**: simple work (a single-file surgical edit, one build) is fine with a simple monitor. A multi-SOP (5+ steps like parsing -> restructure -> build -> verify -> report) risks freezing between SOPs -> the improved monitor is recommended.

---

## 6. Operations — standard procedures

### 6.1 Standard diagnostic procedure — mandatory before every user statement

Before using worker status as the basis for a statement/decision:
```bash
cd <working dir>
bash ~/claudebase/installer/scripts/omc_status.sh
```
It organizes all team task statuses + tmux pane state on one screen. Make your statement based on the result of this command. No intuitive statements like "W4 seems stuck" — judge only by the `omc_status.sh` result.

**Mixed stdout/stderr pitfall**: a non-JSON line like "[team] canonicalized duplicate worker entries: worker-1" falls to stdout on the first line of `omc team api ...`. A simple `... | python -m json.tool` breaks. Workaround: extract only the first JSON line with `grep '^{' | head -1`.

### 6.2 Task creation — mandatory use of the wrapper

Do not call `omc team api create-task` directly. Instead:
```bash
bash ~/claudebase/installer/scripts/omc_create_task.sh <team_name> "<subject>" <description_file_or_->
```
The wrapper handles all of — (1) JSON-safe encoding, (2) filtering mixed stderr, (3) detecting an ok=false response, (4) preventing duplicate calls. On success the task_id goes to stdout; on failure, stderr + exit 1.

### 6.3 Automatic pane label assignment — standard procedure after every launch

The Claude Code TUI dynamically updates pane_title to the current task description. A label manually assigned by main with `tmux select-pane -T '[W1] ...'` is overwritten when the worker starts the next task.

Fix: combine a hardcoded label based on pane_index in tmux `pane-border-format` with Claude's dynamic title. Automation:

```bash
bash ~/claudebase/installer/scripts/omc_pane_label.sh apply \
  '0=[MAIN] User chat' \
  '1=[W1] PPT Editor' \
  '2=[W2] Image' \
  '3=[W3] Reviewer'
```

Result: each pane's top border shows the form `[W1] PPT Editor | ✳ Execute worker inbox task...`. Permanent label on the left, Claude's dynamic info on the right.

**Blocking the TUI's own pane title override (v3+)**: omc_pane_label.sh v3+ also applies `tmux set -g allow-set-title off` -> tmux ignores the OSC title escape itself. pane_title is permanently fixed, no watchdog needed. (auto-restored on a `clear` call)

**Combined with the pane index reshuffle pitfall**: existing pane indices are often reshuffled when a new worker launches — re-confirm the current mapping with `tmux list-panes -a` *before* the apply call (mandatory).

Other commands:
- `bash omc_pane_label.sh show` — check the current labels + pane state
- `bash omc_pane_label.sh clear` — reset both the labels and the tmux pane-border-status

### 6.4 Task lifecycle pitfall — do not send the standby as a task

If you launch with `omc team 1:claude "<standby context>"`, that context itself is registered as task 1. The worker only verifies the environment and marks the task completed -> the next dispatch does not come in.

**Correct operation**: at launch, pass only the role/SOP, and add the *actual change spec* as a new task with `omc team api add-task`. The worker keeps the process alive even when the task queue is empty (idle waiting).

### 6.5 Batch dispatch rule

Do not dispatch per single Q&A item; **accumulate 3-5 change notes and dispatch at once**. Reasons:
- change spec + tmux paste + Enter workaround + build verification — overhead every time.
- It is safer for the worker to do surgical edits on multiple files in a single task and then a single build verification (consolidated regression discovery).
- Manage accumulated notes as a counter in the main panel, and at the appropriate time proceed after a user confirmation of "shall I dispatch to the worker now?"

### 6.6 Auto-monitor pattern — bundle a completion alert with every task creation (mandatory)

For every task creation, also bring up a polling script with `Bash run_in_background: true` -> when the worker completes, the main panel gets a push alert. The user does not have to ask "is it done?"

**Bring up a monitor for an idle worker too**: even at the point an idle worker enters idle right after a team launch / task complete, you must bring up a *pane-only monitor (sentinel + stale)*. Reason: the user types directly into the worker pane (§4.2) / the worker voluntarily attempts "exit" (worker self-shutdown pitfall) -> without a monitor, main cannot detect the stuck state. Idle monitor:
```bash
MONITOR_NO_HEURISTIC=1 bash ~/claudebase/installer/scripts/omc_monitor.sh \
  - - <pane-id> 1500 <workdir> - 2>&1 &
```
- team/task_id `-` = pane-only mode (skips omc API polling)
- deliverable `-` = idle watching, does not fire ALERT-DONE. ALERT-STALE after a sentinel emit or 1500s of stale.
- When a new task comes in, terminate the idle monitor + restart with a task-specific monitor (team + task_id + deliverable).

**Task creation = monitor target — both paths**:
- **Path A: new team launch** — the launch text of `omc team N:claude "<text>"` is auto-registered as task 1. If you do not separate this as "team launch ≠ dispatch," a regression occurs.
- **Path B: add a task to an existing team** — capture `task_id` from the `omc team api create-task` response, then monitor.

**Standard procedure (3 steps, same for both paths)**:
1. **Create the task**: path A (team launch) or path B (`create-task`). Confirm `task_id` from the response.
2. **Worker nudge** (needed only for path B — path A auto-pastes at launch): `tmux send-keys -t <pane-id> "Task <id> ..."` -> `sleep 2` -> `tmux send-keys -t <pane-id> C-m` (§4.1 workaround).
3. **Background monitor** (`Bash run_in_background: true`):
   ```bash
   until [ "$(omc team api read-task --input '{"team_name":"<team>","task_id":"<id>"}' --json 2>/dev/null \
            | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("data",{}).get("task",{}).get("status",""))')" = "completed" ]; do
     sleep 30
   done
   echo "[ALERT] Task <id> (<short subject>) completed at $(date '+%H:%M:%S')"
   ```

Polling interval: 30 s standard. Too long degrades responsiveness; too short accumulates `omc team api` overhead. If the worker's task is expected to be under 2 min, use 15 s.

**Alternative**: bringing up the same script with the `Monitor` tool pushes per stdout line — for when you need intermediate progress reports. If you only need a simple completion alert, `Bash run_in_background` is lighter and standard.

After receiving the alert: main's automatic alert -> at that point check the worker's reply (change summary, build result, visual verification opinion) + decide whether to proceed to the next Q&A.

### 6.7 Automatic worker pool selection — the user does not decide every time

When multiple workers (teams) are up, the user does not have to decide "which worker?" on every dispatch. Self-procedure:

1. Check the task status of all worker teams (`omc team api list-tasks` per team, the `in_progress` count is key).
2. Shortlist only **idle workers** (in_progress=0) as candidates.
3. Both idle -> **default to the workspace-state worker** (the one whose state is inside `./.omc/` is cleaner to operate).
4. Only one idle -> dispatch to that one.
5. Both busy -> confirm "queue vs wait" with the user once (rarely happens).

**Avoiding same-file conflicts**: do not let two workers touch the same .tex/.py/file simultaneously. A busy worker is absorbed into the automatic candidate exclusion. If the files are independent, simultaneous dispatch is OK.

### 6.8 Worker state path trade-off

The state directory location is determined by the cwd at team launch:
- **Cwd = work directory** -> state in `<workdir>/.omc/state/team/<slug>` — clean to operate (all commands in the same cwd), the default recommendation.
- **Cwd = /tmp** (or elsewhere) + `--cwd <target>` -> state in `/tmp/.omc/state/team/<slug>` — for isolation when launching two teams in the same directory. Downside: every api command needs `cd <state-cwd>`.

A second team launch in the same cwd is the silent fail of §3.4.

### 6.9 omc state wipe — orphan-cleanup self-invoke pitfall

**Symptom**: the worker deletes its own task / the whole team on lease expiry. Unrecoverable. Disk artifacts survive.

**Avoidance**: state in the worker SOP "orphan-cleanup is leader-only — never self-invoke. On lease expiry, send-message + idle."

### 6.10 Accumulated 4 pitfalls + standard diagnosis (summary)

All pitfalls of this kind are ultimately exposed through the cycle of — (1) main has the wrong status perception, (2) the user corrects it. 4 categories:

1. **omc CLI mixed stdout/stderr** — see §6.1.
2. **omc state wipe (orphan-cleanup self-invoke)** — see §6.9.
3. **Claude TUI pane title dynamic override** — see §6.3 (the v3 `allow-set-title off` is the fix).
4. **Monitor stale-aware thinking-counter blind spot** — see §5.4.

---

## 7. Dependent resources (claudebase canonical)

The scripts the body depends on — all canonical in `~/claudebase/installer/scripts/` (= claudebase's `installer/scripts/`):

| Script | Role | Canonical sub-version check |
|---|---|---|
| `omc_monitor.sh` | v3.x (sentinel + heuristic + stale, pane-only mode) | check the file header `# Version: ...` |
| `omc_pane_label.sh` | v3+ (applies allow-set-title off) | `bash omc_pane_label.sh --version` or the file header |
| `omc_status.sh` | combined output of team task + tmux pane state | single version |
| `omc_create_task.sh` | create-task wrapper (JSON-safe + stderr filter) | single version |

The omc plugin core (`omc team`, `omc team api ...`) evolves separately — check lag with `omc update --check`.

The absolute path `~/claudebase/...` referenced in the body is given for user-friendliness. If you cloned to a different location, read from `$CLAUDEBASE_ROOT/installer/scripts/` (default `~/claudebase`).

---

## Related

- `omc-reference` skill (provided by omha or the omc plugin core) — OMC agent catalog / tools / pipeline
- `~/claudebase/installer/scripts/` — canonical scripts the body depends on
- Change history of the body: `git log -- runtime/skills/omc-teams-ops/SKILL.md`

# Autonomous modes: autopilot, ralph, ultraqa (state machines & loops)

OMC's autonomous modes turn a single Claude Code session into a self-driving loop. The mechanism is uniform: a *skill* (a Markdown prompt) instructs the LLM to write a small JSON **state file**, and a **Stop hook** (`persistent-mode`) reads that file on every turn-end and either lets the session stop or injects a continuation prompt with `continue: false`, forcing another turn. The LLM does the work; the hook is a dumb, deterministic gate that refuses to let the session die while state says the job is unfinished. This section documents the three modes named in the territory (autopilot, ralph, ultraqa) plus the shared runtime that actually powers them — the persistent-mode dispatcher, the ralph loop state machine, the arm/cancel state contract, and the layered circuit breakers — and clarifies which parts are code-driven versus prompt-driven. Evidence roots: `skills/{autopilot,ralph,ultraqa,cancel}/SKILL.md` and `src/hooks/persistent-mode/`, `src/hooks/ralph/`, `src/hooks/mode-registry/`, `src/lib/mode-state-io.ts`, `src/tools/state-tools.ts`.

## The three modes at a glance

The critical distinction: **only ralph and ultrawork have a real code state machine.** Autopilot and ultraqa are *prompt-orchestrated* — their loops live in the SKILL.md text and the LLM's own bookkeeping, with the hook contributing only phase-level continuation for autopilot and nothing for ultraqa.

| Mode | Level | Loop authority | State file | Completion gate | Max-iteration guard |
|:---|:---|:---|:---|:---|:---|
| autopilot | 4 (`skills/autopilot/SKILL.md:5`) | 5 sequential phases in prompt; hook enforces phase continuation via `checkAutopilot` | `autopilot-state.json` | all 5 phases done + all Phase-4 validators approve (`SKILL.md:113-120`) | `maxIterations:10`, `maxQaCycles:5`, `maxValidationRounds:3` (config, `SKILL.md:136-146`) |
| ralph | 4 (`skills/ralph/SKILL.md:6`) | **code state machine** `checkRalphLoop` (`persistent-mode/index.ts:929`) | `ralph-state.json` + `prd.json` + `progress.txt` + `ralph-verification.json` | all PRD stories `passes:true` AND reviewer-verified (`persistent-mode/index.ts:1143`) | soft `max_iterations` (default 10, self-extends +10) + hard `hardMaxIterations` (500) |
| ultraqa | 3 (`skills/ultraqa/SKILL.md:5`) | **prompt-only** cycle in SKILL.md; `mode-registry` knows it exists but persistent-mode has **no `checkUltraqa`** | `ultraqa-state.json` (`SKILL.md:103`) | goal (tests/build/lint/typecheck/custom) passes | `max_cycles:5`; early-exit on same failure 3× (`SKILL.md:80-85`) |

Ultraqa is the thinnest of the three at runtime: it registers in `mode-registry` (`MODE_CONFIGS[ULTRAQA]`, `mode-registry/index.ts:82`) and is one of the `STATE_TOOL_MODES` (`state-tools.ts:48`), but `resolvePersistentModeBlock` never calls an ultraqa checker — so its "max 5 cycles / same-failure-3× / clear state on completion" logic is entirely the LLM following `ultraqa/SKILL.md`. Its one code-level coupling is *mutual exclusion*: `createRalphLoopHook.startLoop` refuses to arm if `isUltraQAActive` is true (`ralph/loop.ts:288-294`).

## Control flow: how a mode drives a session

```
  LLM invokes skill (e.g. /oh-my-claudecode:ralph "task")
        │
        ▼  writes state via state_write MCP tool  →  .omc/state/sessions/<sid>/ralph-state.json  {active:true, iteration:1, ...}
  ┌───────────────── each turn the LLM ends ─────────────────┐
  │  Claude Code fires Stop hook chain (hooks/hooks.json):    │
  │   context-guard-stop → workflow-drift-guard →            │
  │   persistent-mode  → code-simplifier                     │
  │        │                                                  │
  │        ▼  scripts/persistent-mode.mjs → bridge.ts         │
  │           → checkPersistentModes(sid, dir, stopContext)   │
  │                │                                          │
  │        resolvePersistentModeBlock (priority dispatch):    │
  │           kill-switch / abort / rate-limit / cancel gates │
  │           → autopilot|ralph → autoresearch → ralplan      │
  │           → team → ultrawork → skill-active               │
  │                │                                          │
  │        checkRalphLoop reads state; if NOT complete:       │
  │           iteration += 1, write back, build prompt        │
  │           return {shouldBlock:true, message:"<ralph…>"}   │
  │                │                                          │
  │        createHookOutput → {continue:false, message}       │
  │        ══ Claude Code REFUSES to stop, injects message ══ │
  └──────────────────────► next turn ◄───────────────────────┘
        │ (when complete OR /cancel)
        ▼  state_clear removes state file  →  next Stop returns {continue:true}
```

The Stop-hook output contract is the whole trick: `createHookOutput` returns `continue: !result.shouldBlock` (`persistent-mode/index.ts:2367-2374`). `continue:false` is Claude Code's signal to *not* end the turn and to feed `message` back as the next prompt. So "the loop" is literally: block the stop, inject a prompt, repeat.

## Arming a mode (state_write)

A mode arms by persisting a JSON state file with `active:true`. Two write paths exist. Skills call the **`state_write` MCP tool** (`src/tools/state-tools.ts`; `mode` is a `z.enum` over `STATE_TOOL_MODES = ['autopilot','autoresearch','team','ralph','ultrawork','ultraqa','deep-interview','self-improve', ...'ralplan','omc-teams','skill-active']`, `state-tools.ts:48-58`). Internally both paths land in `writeModeState` (`mode-state-io.ts:203`), which:

- resolves `.omc/state/sessions/<sessionId>/<mode>-state.json` when a session id exists, else the legacy `.omc/state/<mode>-state.json` (`mode-state-io.ts:211-216`);
- writes with `mode 0o600` (owner-only) and an atomic write;
- injects a top-level `owner_pid` and a `_meta` envelope `{written_at, mode, sessionId, ownerPid}` (`mode-state-io.ts:222-231`) so external hook scripts can do process-liveness checks without parsing state shape. `readModeState` strips `_meta` transparently (`mode-state-io.ts:263-266`).

Ralph's programmatic arm (`createRalphLoopHook.startLoop`, `ralph/loop.ts:282-366`) is the fullest example. It (1) refuses if ultraqa is active; (2) resolves the git branch via `git rev-parse --abbrev-ref HEAD` (5s timeout, falls back to `ralph/task`); (3) calls `ensurePrdForStartup` to auto-scaffold `prd.json` if absent — a hard gate, arming fails if the PRD can't be created (`loop.ts:320-323`); (4) inits `progress.txt`; (5) writes `RalphLoopState {active:true, iteration:1, max_iterations:10, started_at, prompt, session_id, project_path, linked_ultrawork, critic_mode, prd_mode:true}`; (6) **auto-arms a linked ultrawork** state with `linked_to_ralph:true` unless `--no-prd`/`disableUltrawork` (`loop.ts:351-363`). Ralph thus always runs ultrawork underneath it by default.

The `_meta`/`owner_pid` envelope is how the harness detects orphaned state without a daemon: `writeModeState` stamps the writer's `process.pid` at both the top level and inside `_meta.ownerPid` (`mode-state-io.ts:221-231`). A crashed session leaves a state file whose `owner_pid` refers to a dead process; combined with the 2-hour stale threshold and the 24-hour ledger tombstone, this gives three independent ways a zombie mode file is neutralized before it can block a fresh session, with no reaping process required.

## State-file schemas (verbatim)

`RalphLoopState` (`ralph/loop.ts:89-112`):

```ts
{ active: boolean; iteration: number; max_iterations: number; started_at: string;
  prompt: string; session_id?: string; project_path?: string; prd_mode?: boolean;
  current_story_id?: string; linked_ultrawork?: boolean;
  critic_mode?: 'architect'|'critic'|'codex' }   // RALPH_CRITIC_MODES, default 'architect'
```

`prd.json` — `PRD` + `UserStory` (`ralph/prd.ts:23-51`). Completion is defined entirely by these booleans:

```ts
PRD        { project: string; branchName: string; description: string; userStories: UserStory[] }
UserStory  { id: string; title: string; description: string; acceptanceCriteria: string[];
             priority: number; passes: boolean; architectVerified?: boolean; notes?: string }
```

`PRDStatus` (derived, `prd.ts:53-66`): `{ total, completed, pending, allComplete, nextStory, incompleteIds }`. `allComplete` drives the ralph completion gate; `nextStory` = highest-priority `passes:false` story.

`ultraqa-state.json` (prompt-authored, `ultraqa/SKILL.md:105-116`): `{ active, goal_type, goal_pattern, cycle, max_cycles:5, failures[], started_at, session_id }`.

`AutopilotState` (`autopilot/state.ts:176-228`) is a nested per-phase record — the fullest state shape of any mode:

```ts
{ active: true; phase: 'expansion'; current_phase: 'expansion'; iteration: 1; max_iterations: 10;
  originalIdea: string;
  expansion:  { analyst_complete, architect_complete, spec_path, requirements_summary, tech_stack[] };
  planning:   { plan_path, architect_iterations, approved };
  execution:  { ralph_iterations, ultrawork_active, tasks_completed, tasks_total, files_created[], files_modified[] };
  qa:         { ultraqa_cycles, build_status, lint_status, test_status };   // 'pending' initially
  validation: { architects_spawned, verdicts[], all_approved, validation_rounds };
  started_at; completed_at; phase_durations{}; total_agents_spawned; wisdom_entries;
  session_id; project_path }
```

The dual `phase`/`current_phase` fields are a compatibility shim — the reader normalizes `current_phase → phase` (`state.ts:71-72,97-103`) so older state files still parse.

`BoulderState` (`features/boulder-state/types.ts:13-28`) — a *separate* plan-tracking structure for the general TODO-continuation "boulder" metaphor, not the ralph/autopilot loops: `{ active_plan, started_at, session_ids[], plan_name, active, updatedAt, metadata? }`. It backs the `boulder.json` file cleared under `/cancel --force`.

## The ralph loop state machine (`checkRalphLoop`)

This is the one genuinely code-driven mode loop. On each Stop, `checkRalphLoop` (`persistent-mode/index.ts:929-1248`) runs this decision cascade:

```
1. state absent | inactive | stale (>2h)        → return null (let stop)
2. session_id mismatch (both defined, differ)   → return null
3. isAwaitingConfirmation / cancelInProgress     → don't re-arm, allow stop
4. self-heal: linked_ultrawork lost → recreate ultrawork state
5. team pipeline terminal (complete/failed/cancelled) → clear ralph, allow stop
6. verification pending?
     ├ reviewer APPROVED in transcript → mark story verified OR clear+complete
     ├ reviewer REJECTED → recordArchitectFeedback, BLOCK w/ rejection prompt
     └ still pending → BLOCK w/ "run the reviewer" reminder
7. current story passes:true but !architectVerified → startVerification, BLOCK
8. PRD.allComplete (all passes:true) → startVerification, BLOCK  ← completion enters verification, not exit
9. HARD MAX: iteration >= hardMaxIterations(500) → active=false, BLOCK once w/ "restart" note
10. SOFT MAX: iteration >= max_iterations → max_iterations += 10 (self-extend), continue
11. incrementRalphIteration; inject <ralph-continuation> prompt with PRD/progress context → BLOCK
```

Key behaviors worth quoting. **Completion never exits directly** — when all stories pass, ralph *enters a verification phase* (`startVerification`, step 8) and only clears state after the reviewer (`critic_mode`: architect / critic / codex) authors an approval detected in the transcript (`checkArchitectApprovalInTranscript` → `clearRalphState`+`deactivateUltrawork`, `index.ts:1143-1160`, `1052-1066`). **Reviewer approval/rejection is detected by scanning the transcript tail**, not by any structured return (`normalizeReviewerPath`, `checkReviewerAuthoredApprovalInMessages`, `index.ts:687-805`) — because PreToolUse/Stop hook stdin carries no assistant text. **The soft cap is deliberately toothless**: hitting `max_iterations` just adds 10 more, so "user-visible cancellation remains the only explicit termination path" (comment, `index.ts:1186-1198`). The real ceiling is the hard cap.

The injected continuation prompt (`index.ts:1217-1236`) carries the iteration counter `[RALPH - ITERATION N/MAX]`, the ralph progress/PRD context, per-tool-error retry guidance, and the completion instruction to run `/oh-my-claudecode:cancel`. This is the `<ralph-continuation>` block the LLM sees each turn.

### How reviewer approval is detected (transcript scan)

Because the Stop-hook stdin has no assistant/tool text, approval is inferred by re-reading the session's JSONL transcript tail. `checkReviewerAuthoredApprovalInMessages` (`index.ts:744-803`) parses transcript lines, correlates `tool_use` blocks whose name is in `REVIEWER_TASK_TOOL_NAMES = {'Task','proxy_Task','Agent'}` (or a codex `Bash` command in `REVIEWER_COMMAND_TOOL_NAMES = {'Bash','proxy_Bash'}`, `index.ts:684-685`) against their paired `tool_result`, and only counts approval if the reviewer path matches the run's `critic_mode`. The approval itself is a **magic-string XML block the reviewer must author**: `detectArchitectApproval` matches `<architect-approved>...VERIFIED_COMPLETE...</architect-approved>` (or `<ralph-approved>`) via regex `/<(?:architect-approved|ralph-approved)\b...VERIFIED_COMPLETE...>/gis` (`verifier.ts:335-368`), and — critically — verifies the `request-id` and `story-id` attributes match the pending `VerificationState` so a stale or spoofed approval from earlier in the transcript cannot complete the loop. `stripInjectedApprovalExamples` first removes any approval-shaped strings the prompt itself injected, so the loop cannot self-approve by echoing its own instructions.

### Context-percent safety and awaiting-confirmation

Two more code-level guards feed the dispatcher. `isCriticalContextStop` blocks continuation not only on an explicit context-limit stop but whenever the transcript's estimated context usage crosses `CRITICAL_CONTEXT_STOP_PERCENT = 95` (`index.ts:610,833-840`) — computed by scraping the last `context_window`/`input_tokens` pair from the transcript. And `isAwaitingConfirmation` (`index.ts:842-869`) lets a mode pause itself: a state file with `awaiting_confirmation:true` set within the last `AWAITING_CONFIRMATION_TTL_MS = 2min` makes `checkRalphLoop`/`checkUltrawork` return `null` (allow stop) so the loop can genuinely wait for a human answer without being force-continued.

## The autopilot phase machine

Autopilot's loop is a *phase* progression, not a fixed-point iteration. `initAutopilot` seeds `phase:'expansion'` (`state.ts:178`) and `transitionPhase` walks the linear pipeline `expansion → planning → execution → qa → validation → complete` (terminal `failed` on unrecoverable error, `state.ts:265`). Each transition emits an LLM-facing directive telling it what the next phase requires — e.g. the `execution → qa` transition and `qa → validation` transition both inject bespoke instructions (`state.ts:584-648`). Execution phase (Phase 2) delegates to ralph+ultrawork; QA phase (Phase 3) runs the ultraqa cycle; validation phase (Phase 4) spawns three reviewer agents in parallel. The hook side (`checkAutopilot`, `autopilot/enforcement.ts`) is what keeps the phase machine advancing across Stop events — it is the only reason autopilot survives a turn boundary — but the *content* of each phase (which agents to spawn, when a phase is done) lives in `autopilot/SKILL.md`, so autopilot is a hybrid: code-driven phase persistence, prompt-driven phase execution.

Two skip-ahead optimizations short-circuit the pipeline at Phase 0: an existing **ralplan consensus plan** (`.omc/plans/ralplan-*.md` or `consensus-*.md`) skips both expansion and planning, jumping straight to execution; an existing **deep-interview spec** (`.omc/specs/deep-interview-*.md`) skips only expansion (`autopilot/SKILL.md:42-43`). This is the documented 3-stage pipeline `deep-interview → ralplan → autopilot`, where each upstream gate lets autopilot start later. Autopilot's config surface (`.claude/omc.jsonc`, `autopilot/SKILL.md:136-146`) exposes `maxIterations`, `maxQaCycles`, `maxValidationRounds`, `pauseAfterExpansion`, `pauseAfterPlanning`, `skipQa`, `skipValidation`, and `execution:'solo'|'team'` — the last routes Phase-2 execution through the tmux CLI team runtime (`omc team 1:cursor "..."`) with executor-only worker roles.

## Verification gates inside the loop

Ralph's verification is a two-scope handshake stored in `ralph-verification.json` (`VerificationState`, marker file `ralph-verification.json` in `mode-registry`). Scope `story` verifies one story (`markStoryArchitectVerified`, advance to next); scope task-complete verifies the whole PRD (clear + complete). The SKILL.md layers additional *prompt-enforced* gates the hook does not check: a **mandatory deslop pass** (`Skill("ai-slop-cleaner")` on changed files, step 7.5) and **post-deslop regression re-verification** (step 7.6), both skippable only via `--no-deslop` (`ralph/SKILL.md:114-127`). Autopilot's Phase-4 validation (architect + security-reviewer + code-reviewer, all must approve, `autopilot/SKILL.md:65-69`) and ultraqa's architect-diagnosis-then-fix cycle (`ultraqa/SKILL.md:58-76`) are likewise prompt-only gates.

## Ultrawork: the reinforcement sub-loop

Ultrawork is the second code-driven loop and the one ralph auto-arms underneath itself. Its state (`UltraworkState`, `ultrawork/index.ts:16`) is `{ active, original_prompt, reinforcement_count, started_at, last_checked_at, session_id?, project_path?, linked_to_ralph? }`. `checkUltrawork` (`index.ts:1894-1969`) is simpler than ralph: it has no PRD and no reviewer. Its completion condition is *todo-driven* — if `checkIncompleteTodos` reports zero pending todos it auto-deactivates (`deactivateUltrawork`) and allows the stop (issue #2419, `index.ts:1928-1938`), otherwise it `incrementReinforcement()` and injects `getUltraworkPersistenceMessage`. It enforces the same hard cap on `reinforcement_count >= hardMaxIterations` (`index.ts:1940-1950`). Because ralph links it, ralph's self-heal step recreates a missing ultrawork state each turn (`index.ts:975-991`) so the reinforcement banner cannot silently vanish mid-run. Standalone ultrawork (not linked) is the user-controlled variant the SKILL registry documents; cancel is link-aware and only auto-clears ultrawork when `linked_to_ralph:true`.

## Circuit breakers and fail-open guards

`resolvePersistentModeBlock` front-loads a wall of *fail-open* conditions — every one returns `{shouldBlock:false}` so the session is never trapped. Ordered as they execute (`persistent-mode/index.ts:2072-2214`):

| Guard | Trigger | Rationale |
|:---|:---|:---|
| `DISABLE_OMC=1/true` or `OMC_TEAM_WORKER` env | hard kill switch | never enforce (`index.ts:2076-2082`) |
| `OMC_SKIP_HOOKS` contains `persistent-mode`/`stop-continuation` | granular kill switch | comma-split opt-out (`index.ts:2083-2089`) |
| `isCriticalContextStop` | context-limit stop | blocking would deadlock compaction (issue #213) |
| `isExplicitCancelCommand` / session cancel-signal (`cancel-signal-state.json`, 30s TTL) | `/cancel` in flight | prevents re-arm race during shutdown (issue #1058) |
| `isUserAbort` | user pressed stop | respect explicit abort |
| `isRateLimitStop` | 429 / quota | blocking = infinite retry loop (issue #777) |
| `isAuthenticationError` | 401/403/expired OAuth | infinite-loop guard (issue #1308) |
| `isScheduledWakeupStop` | ScheduleWakeup `/loop` turn | resumption, not a stall |
| `isOversizeToolResultRedirectStop` | tool-result redirect | suppress ≤3 consecutive (`OVERSIZE_..._MAX=3`, 5min TTL) |
| `hasPendingOwnedAsyncWork` | background task pending | quiescence is intentional |

Hard-iteration caps are the true termination backstop, sourced from `getHardMaxIterations()` (`security-config.ts:151`): default **500**, tightened to **200** under `OMC_SECURITY=strict`, overridable via `security.hardMaxIterations` in `.claude/omc.jsonc` / `~/.config/claude-omc/config.jsonc` (in strict mode the file may only *lower* it, `security-config.ts:108`). Ralph checks `iteration >= hardMax` independent of the self-extending soft cap so a high initial `max_iterations` cannot bypass it (`index.ts:1163-1184`). Ultrawork mirrors this on `reinforcement_count` (`index.ts:1940-1950`). A `MAX_TODO_CONTINUATION_ATTEMPTS = 5` (`index.ts:93`) caps the baseline todo-continuation loop. `STALE_STATE_THRESHOLD_MS = 2h` (`index.ts:95`) makes any state file older than 2 hours invisible, so a crashed session cannot block a new one — this is the "2-hour staleness timeout" the cancel skill names as a last resort.

## The Stop-hook chain and the todo-continuation baseline

`persistent-mode` is the third of four Stop hooks, registered in `hooks/hooks.json` as `context-guard-stop.mjs → workflow-drift-guard.mjs → persistent-mode.mjs → code-simplifier.mjs` (all wrapped by `scripts/run.cjs`). Only `persistent-mode` produces the loop-continuation `continue:false`. Its `.mjs` script is a thin shim that shells into `bridge.ts`, which lazy-imports `checkPersistentModes`/`createHookOutput` and passes the parsed hook stdin — `session_id`, `transcript_path`, `cwd`, `source` — as a `StopContext` (`bridge.ts:1758-1811`). The bridge itself re-guards `DISABLE_OMC`/`OMC_SKIP_HOOKS` at entry, and `resolvePersistentModeBlock` re-checks them a second time (`index.ts:2072-2089`) so nested/direct callers and tests observe the identical kill-switch contract.

Beneath all named modes sits the **todo-continuation baseline**: even with no mode armed, if the LLM ends a turn with pending TODO items, `_checkTodoContinuation` (`index.ts:1975`) injects `TODO_CONTINUATION_PROMPT` (defined `[SYSTEM REMINDER - TODO CONTINUATION]...`, `installer/hooks.ts:235`) up to `MAX_TODO_CONTINUATION_ATTEMPTS = 5` times per session (tracked in an in-memory `Map`, `index.ts:111-112,441-451`). This is the general "boulder" enforcement the mode loops specialize; the companion `src/features/continuation-enforcement.ts:20` constant carries the `"The boulder does not stop"` phrasing, and `"The boulder never stops"` recurs across the pre-tool enforcer as the signal to the LLM that a persistence loop is live. The 5-attempt cap ensures a stuck agent that cannot clear its todos is eventually released rather than looping forever.

## Priority dispatch and nesting

When multiple modes are armed, `resolvePersistentModeBlock` resolves one winner. Normal order is **ralph > autopilot > autoresearch > ralplan > team > ultrawork > skill-active** (`index.ts:2284-2352`). The twist: a **workflow ledger** (`skill-active-state.json`, read via `resolveAuthoritativeWorkflowSkill`) can flip ralph/autopilot ordering — in an `autopilot → ralph` nesting, autopilot is the authoritative *parent* so `autopilotPriorityFirst` makes it win and keep its phase accounting advancing (`index.ts:2242-2294`). The ledger also carries **tombstones**: a slot with `completed_at` set is treated as inactive for `WORKFLOW_SLOT_TOMBSTONE_TTL_MS = 24h` (`mode-registry/index.ts:165`), so a stale mode file from a crashed session cannot re-arm a priority check until TTL prune or fresh activation. `TERMINAL_WORKFLOW_PHASES` (`complete/completed/failed/cancelled/…`, `index.ts:100-109`) drive `reconcileTerminalWorkflowSlots`, which tombstones live slots whose mode state already reached a terminal phase outside the normal completion hook.

## Cancellation (`/cancel` + state_clear)

Cancel is the standard exit. The `cancel` skill (`skills/cancel/SKILL.md`) is LLM-executed: it loads the deferred state tools via `ToolSearch(select:...state_clear,state_read,state_write,state_list_active,state_get_status)`, enumerates active sessions with `state_list_active`, learns each mode with `state_get_status`, then calls `state_clear(mode, session_id)` in **dependency order** (autopilot → ralph → ultrawork → ultraqa → swarm → …, `SKILL.md:111-123`). Link-aware: cancelling autopilot cascades to linked ralph/ultraqa; cancelling ralph clears its linked ultrawork only if `linked_to_ralph:true` (`SKILL.md:357-359`, `loop.ts:368-381`). **Autopilot preserves state** (`active:false`, resume via re-invoking `/autopilot`); ralph/ultrawork/ultraqa are cleared outright (`SKILL.md:342-354`). The **final step always** clears `skill-active-state.json` regardless of mode so the Stop hook stops re-firing skill protection (issue #2118, `SKILL.md:317-321`). A bash **fallback** (`SKILL.md:61-101`) deletes state files directly when the MCP tool is unavailable — but is forbidden for autopilot (needs resume data) and omc-teams (needs tmux cleanup), and writes a 30s `cancel-signal-state.json` so the Stop hook detects cancellation mid-flight. `/cancel --force`/`--all` wipes every session plus a hard-coded legacy compatibility list (`SKILL.md:145-171`) including `boulder.json`, `hud-state.json`, `checkpoints/`, and swarm SQLite files.

## What 'ralphthon' is

`ralphthon` is a **distinct, CLI-only** autonomous-hackathon runtime — *not* the ralph loop and *not* exposed as a Claude Code skill or slash command. It is wired solely as the `omc ralphthon` subcommand (`src/cli/index.ts:1471-1478` → `src/cli/commands/ralphthon.ts` → `src/ralphthon/`). Its lifecycle (`RalphthonPhase`: `interview → execution → hardening → complete/failed`, `ralphthon/types.ts:26-31`) drives a **tmux-pane leader** (a real Claude Code instance) by polling and injecting keystrokes: the orchestrator exports `sendKeysToPane`, `capturePaneContent`, `detectLeaderIdle`, `detectCompletionSignal`, `orchestratorTick` (`ralphthon/index.ts:55-74`). It maintains its own `ralphthon-prd.json` (`PRD_FILENAME`, `types.ts:238`) with a richer schema than ralph's — stories contain nested `tasks[]` with per-task `retries`, plus a separate `hardening[]` array tagged by `wave` and `category` (`edge_case|test|quality|security|performance`). `RalphthonState` (`types.ts:150-183`) tracks `currentWave`, `consecutiveCleanWaves`, `tmuxSession`, `leaderPaneId`. Termination is wave-based: `RALPHTHON_DEFAULTS = {maxWaves:10, cleanWavesForTermination:3, pollIntervalMs:120_000, idleThresholdMs:30_000, maxRetries:3}` (`types.ts:229-236`) — it stops after 3 consecutive hardening waves that surface no new issues, or after 10 waves. In short: ralphthon *drives* a ralph-style session from the outside via tmux, whereas ralph runs *inside* the session via the Stop hook.

## Patterns for sibling harnesses

- **Stop-hook continuation loop.** A `{continue:false, message}` return from a Stop hook + a session-scoped `active:true` state file is the entire autonomous-loop primitive — no daemon, no external process. *Adapt:* one `checkPersistentModes`-style dispatcher per harness, keyed on your own `.oh-*/state/sessions/<sid>/<mode>-state.json`.
- **Skill writes state, hook enforces it.** Keep the loop policy in the SKILL.md prompt and let the hook be a dumb deterministic gate reading one JSON file. *Adapt:* mirror `mode-registry` file-based `isModeActive` detection that never imports mode modules (avoids circular deps).
- **Dual iteration caps: self-extending soft + hard backstop.** A soft `max_iterations` that just `+= 10` keeps the loop alive so *user cancel is the only clean exit*, while a config-driven `hardMaxIterations` (500/200-strict) checked independently prevents runaway. *Adapt:* store the hard cap in a `security` config block that strict-mode can only tighten.
- **Completion routes into verification, not exit.** "All done" should trigger a fresh-reviewer pass whose approval is detected by scanning the transcript tail, since hook stdin lacks assistant text. *Adapt:* choose a `critic_mode` per run; never let the authoring context self-approve.
- **Wall of fail-open guards before any blocking.** Rate-limit / auth-error / context-limit / user-abort / scheduled-wakeup / cancel-signal must each return "allow stop" *first*, because blocking any of them creates an infinite retry deadlock. *Adapt:* copy the guard ordering and the 30s `cancel-signal` TTL + 2h stale-state threshold verbatim in spirit.
- **Workflow ledger with tombstones for nesting + crash recovery.** A single `skill-active-state.json` recording the authoritative parent and 24h `completed_at` tombstones lets nested modes coexist and prevents crashed-session state files from re-arming. *Adapt:* reconcile terminal phases into tombstones so a mode that ended abnormally doesn't zombie-block.
- **Dependency-ordered, link-aware cancel with a bash fallback.** Cancel in `parent → child` order, cascade linked sub-modes, preserve resume-capable state, and ship a file-deletion fallback that writes a cancel-signal to break the loop when the state tool is unavailable. *Adapt:* always clear the skill-active ledger last so the Stop hook quiesces.

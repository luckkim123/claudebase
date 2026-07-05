# Improvement & Goal Engines: self-improve, ultragoal, goal-workflows, missions

This section covers OMC's two long-horizon "keep working until a measurable condition holds" engines and their support code. `skills/self-improve` is a prompt-orchestrated evolutionary loop: N parallel planner/executor agents propose one-hypothesis experiments in git worktrees, a benchmark scores them, and a tournament with a re-benchmark merge gate accretes only verified wins onto an improvement branch, guarded by a sealed-evaluator shell script. `skills/ultragoal` + `src/ultragoal/` is the opposite shape: no benchmark, but a durable multi-story plan and append-only ledger under `.omc/ultragoal/` that survives session restarts and is reconciled against model-reported snapshots of the Claude Code `/goal` Stop-hook directive. `src/goal-workflows/` is the small snapshot-parsing/reconciliation library ultragoal depends on, and `missions/` is committed residue of a hard-deprecated autoresearch CLI flow. Both skills are ACTIVE plugin surface (`.claude-plugin/plugin.json` lists `./skills/self-improve/` and `./skills/ultragoal/`), and both are registered execution modes with dedicated state files (`self-improve-state.json` in `MODE_STATE_FILE_MAP`, src/lib/mode-names.ts:64; ultragoal state seeded by the keyword detector, scripts/keyword-detector.mjs:914).

## 1. self-improve: evolutionary tournament loop

Purpose: autonomously improve a *target repo* (not necessarily the OMC repo) against a single numeric benchmark. The whole engine is a 398-line prompt program (`skills/self-improve/SKILL.md`) plus three sub-agent prompt files, two scripts, and five templates; there is no TypeScript engine. The main session acts as "loop controller" and delegates to stock OMC agents via Task-description augmentation — "No modifications to existing agent .md files" (skills/self-improve/SKILL.md:67).

Wiring: plugin skill + a lightweight dispatch shim `commands/self-improve.md` that just says "Read the full bundled skill instructions ... `skills/self-improve/SKILL.md` ... follow that SKILL.md exactly" (commands/self-improve.md:9-11). `self-improve` is one of the `CANONICAL_WORKFLOW_SLASH_SKILLS` (src/hooks/keyword-detector/index.ts:106-116) but deliberately has no keyword type — "the bridge handles their seeding via the parser result instead of through the keyword-priority loop" (src/hooks/keyword-detector/index.ts:121-125). Mode exclusivity is enforced at setup: "Call `state_list_active`. If autopilot, ralph, or ultrawork is active, refuse to start" (SKILL.md:128).

### Control flow

```
Setup gate: trust_confirmed + si_setting_goal + si_setting_benchmark + si_setting_harness
  |  (goal clarifier interview / benchmark builder agent / harness confirm)
  v
per iteration N:
  0 stale-worktree cleanup (mandatory, idempotent, runs even on resume)
  1 state_write(mode='self-improve', iteration=N)   # resets 30min TTL
  2 stop-request check (state cleared or status=="user_stopped")
  3 consume config/idea.md (user ideas, cleared after planners read)
  4 RESEARCH   1x general-purpose opus  -> research_briefs/round_N.json
  5 PLAN       Nx planner opus parallel -> plans/round_N/plan_planner_X.json
  6 REVIEW     per plan: architect (advisory) then critic (binding H001-H003)
  7 EXECUTE    per approved plan: worktree + executor opus + benchmark
  8 TOURNAMENT rank -> merge --no-ff -> RE-BENCHMARK -> accept/revert
  9 RECORD     history, plateau/circuit-breaker counters, raw_data.json, plot
 10 CLEANUP    worktree remove + prune
 11 STOP CHECK user_stopped | target | plateau | max_iterations | circuit breaker
```

The loop is explicitly non-interactive: "NEVER stop or pause to ask the user during the improvement loop" (SKILL.md:15); every agent failure path is retry-once-then-continue (Error Handling table, SKILL.md:362-374; only "Settings corrupted" stops).

### On-disk layout and path resolution

Artifacts live under a root resolved by `scripts/resolve-paths.mjs`, which layers on `resolveOmcStateRoot` (shared `.omc` resolution: `OMC_STATE_DIR > .omc-workspace > git > cwd`, SKILL.md:380). Scoping (skills/self-improve/scripts/resolve-paths.mjs:132-161):

| scope_mode | Root | Trigger |
|---|---|---|
| `legacy-flat-root` | `.omc/self-improve/` | no topic/slug given AND flat layout already exists |
| `default-scoped` | `.omc/self-improve/topics/default/` | no topic/slug, fresh |
| `topic-scoped` | `.omc/self-improve/topics/{slug}/` | `--topic`/`--slug` |
| `session-scoped` | `.../topics/{slug}/sessions/{sid}/` | `--session-id` or `OMC_SESSION_ID` env |

Under the root: `config/{settings.json,goal.md,harness.md,idea.md}`, `state/{agent-settings.json,iteration_state.json,research_briefs/,iteration_history/,merge_reports/,plan_archive/}`, `plans/`, `tracking/{raw_data.json,baseline.json,events.json,progress.png}` (SKILL.md:39-59, resolve-paths.mjs:85-115). Session-lifecycle state additionally lives at `.omc/state/sessions/{sessionId}/self-improve-state.json` (SKILL.md:61).

### Configuration surface (templates/settings.json defaults)

| Key | Default | Meaning |
|---|---|---|
| `number_of_agents` | `3` | parallel planners/executors per round |
| `number_of_max_critics` | `3` | critic pool cap |
| `benchmark_command` / `benchmark_format` | `""` / `"json"` | evaluator; format also `"number"`/`"pass_fail"` |
| `benchmark_direction` | `"higher_is_better"` | or `lower_is_better` |
| `max_iterations` | `50` | hard iteration cap |
| `plateau_threshold` / `plateau_window` | `0.01` / `3` | stagnation detector |
| `circuit_breaker_threshold` | `3` | consecutive no-winner rounds before abort |
| `target_value` / `primary_metric` | `null` / `"primary"` | goal score; JSON key to read |
| `sealed_files` | `[]` | evaluator files the loop may not touch |
| `regression_threshold` | `0.05` | tolerated regression margin |
| `target_branch` / `topic_slug` | `"main"` / `"default"` | git base; artifact scope |
| `auto_push` / `auto_pr` | `false` / `false` | push and PR are opt-in (SKILL.md:278-279, 347-348) |

Runtime counters in `templates/agent-settings.json`: `trust_confirmed`, `si_setting_goal|benchmark|harness`, `iterations`, `best_score`, `plateau_consecutive_count`, `circuit_breaker_count`, `status: "idle"`, `goal_slug`. Trust is a mandatory consent gate: the user must confirm "This executes arbitrary code in that repository" and, separately, the benchmark command itself (SKILL.md:108-119).

### Sub-agent contracts

Goal clarifier (`si-goal-clarifier.md`): 4-dimension Socratic interview (Objective/Metric/Target/Scope), one question per round at the weakest dimension, `Ambiguity score = 100 - average(all dimensions)`, exit at ambiguity <= 20% (all dims >= 80), soft cap 8 / hard cap 12 rounds (si-goal-clarifier.md:31-57). Benchmark builder (`si-benchmark-builder.md`): survey existing evaluation first, design deterministic <5min JSON benchmark emitting `{"primary": 85.2, "sub_scores": {...}}` as the last stdout line, validate 3 runs with variance < 5%, record `tracking/baseline.json`, and — critically — "Add benchmark script to `sealed_files`" (si-benchmark-builder.md:41-76). Researcher (`si-researcher.md`): produces 3-10 evidence-cited ideas spanning >= 2 approach families, with iteration-state-dependent strategy (broad on iteration 1, avoid documented failures, family shift after 3+ same-family wins, low-risk moves within 5% of target) (si-researcher.md:36-42, 67-72). All inter-agent messages are pinned by JSON schemas in `data_contracts.md` (Plan Document, Benchmark Result, Research Brief, Iteration History, Merge Report, Iteration State, Event Log — sections 1-12).

### Diversity rules and critic gate

Plans carry exactly one `approach_family` from an 8-tag taxonomy (`architecture`, `training_config`, `data`, `infrastructure`, `optimization`, `testing`, `documentation`, `other`; SKILL.md:385-398), extensible via `harness.md` "Custom Approach Families". The critic enforces three harness rules (SKILL.md:234-237): **H001** exactly one hypothesis per plan (reject if zero or multiple); **H002** "No approach_family repetition streak >= 3"; **H003** "Intra-round diversity (no two plans same family in same round)". Architect review (6-point checklist: testability, novelty, scope, target files not sealed, implementation clarity, realistic outcome; SKILL.md:223-230) is "advisory only" (SKILL.md:231); only `critic_approved: false` excludes a plan.

### Tournament selection and the re-benchmark merge gate

Step 8 runs in the orchestrator itself ("SKILL.md does this directly (not delegated)", SKILL.md:266): filter executor results to `status: "success"`, rank by `benchmark_score` respecting `benchmark_direction`, then walk candidates best-first. For each: (a) no-regression check vs `best_score` (`higher_is_better: score >= best_score`); (b) merge `experiment/round_{n}_executor_{id}` into `improve/{goal_slug}` with `--no-ff` and message `"Iteration {n}: {hypothesis} (score: {before} → {after})"`; (c) **re-benchmark on the merged state**; (d) confirmed improvement → accept winner, break; (e) regression → `git reset --hard HEAD~1`, next candidate; (f) merge conflict → `merge --abort`, next candidate (SKILL.md:270-277). Losers are tagged `archive/round_{n}_executor_{id}` then deleted (SKILL.md:139, 280). A Merge Report (`merge_reports/round_{n}.json`) records `status: "merged"|"no_improvement"|"no_winner"|"all_rejected"` with `reason` required for non-merged (data_contracts.md:222-233).

### Plateau vs circuit breaker (distinct stagnation detectors)

Step 9 separates *stagnating wins* from *failing rounds* (SKILL.md:288-291): winner with `abs(new_score - best_score) >= plateau_threshold` resets both counters; winner below threshold increments `plateau_consecutive_count` (best_score still updated if better); no winner at all increments `circuit_breaker_count` only ("plateau tracks stagnating wins, not failures"). Stop conditions (any-of, SKILL.md:308-316): user stop, `best_score` meets `target_value`, `plateau_consecutive_count >= plateau_window`, `iterations >= max_iterations`, `circuit_breaker_count >= circuit_breaker_threshold`. Completion prints a summary and runs `/oh-my-claudecode:cancel` (SKILL.md:350-358). Resumability keys off `iteration_state.json.status` (`in_progress` → resume from `current_step`; `running` in agent-settings = crashed session → auto-resume without prompting; SKILL.md:326-338).

### validate.sh: the sealed evaluator

`scripts/validate.sh` is the anti-self-modification guard: "validate.sh enforces that benchmark code cannot be modified by the loop, preventing self-modification of the evaluation" (SKILL.md:25). Executors must run it before benchmarking (SKILL.md:260). It performs three checks:

1. **Sealed-file check** (validate.sh:147-223). Settings resolution chain: `--settings` flag > `SELF_IMPROVE_SETTINGS_PATH` env > `--project-root` with `--topic`/`--slug` via resolve-paths.mjs > upward directory walk looking for `.omc/self-improve/config/settings.json` or exactly one `.omc/self-improve/topics/*/config/settings.json` (multiple topics is a **loud fail**: "Multiple self-improve topics exist ... Pass --settings ..." exit 1, validate.sh:107-109). In `--worktree` mode the diff base is `merge-base HEAD <first improve/* branch>` (falling back to `origin/HEAD` then `HEAD~1`), plus uncommitted changes (validate.sh:168-183). Sealed entries ending in `/` match as directory prefixes; any violation exits 1 with `"ERROR: Sealed file(s) were modified:..."` (validate.sh:203-218). Notably **fail-open** when settings are absent: `"OK: No settings file found — skipping sealed file check."` (validate.sh:150-152), and jq is a hard dependency.
2. **Plan schema** (first positional arg): required fields `plan_id planner_id round hypothesis approach_family critic_approved target_files steps expected_outcome history_reference`; hypothesis must be a string (the mechanical half of H001); steps non-empty. Taxonomy is deliberately *not* validated here — "handled by the critic (supports custom families from harness.md)" (validate.sh:250-251).
3. **Result schema** (second positional arg): required `executor_id plan_id benchmark_score status timestamp benchmark_raw` (score/raw allowed to be null if the key exists); `status` enum `success|regression|error|timeout`; non-success results must carry a complete `failure_analysis` object with `category` in `oom timeout regression logic_error scope_error infrastructure benchmark_parse_error sealed_file_violation` (validate.sh:279-360) — forcing structured post-mortems that feed future planners.

`scripts/plot_progress.py` renders `tracking/raw_data.json` to `progress.png` (winners as a line annotated by 4-char family prefix, losers as gray scatter), degrading to a `.txt` summary when matplotlib is missing (plot_progress.py:26-100).

## 2. ultragoal: durable ledger + Claude /goal handoff

Purpose: make a multi-story initiative survive session restarts by keeping plan and evidence in the repo, while co-driving Claude Code's session-scoped `/goal` Stop hook. The design premise is stated in the skill: `/goal` "blocks the session from stopping until a condition holds, and auto-clears on success ... but it loses state across sessions" (skills/ultragoal/SKILL.md:26). The shell "cannot invoke or mutate Claude `/goal` state" — OMC "only persists durable artifacts and prints instructions that the active Claude agent reads and acts on in-session" (skills/ultragoal/SKILL.md:90).

Three active layers plus a hook:

| Layer | File | Role |
|---|---|---|
| Skill | `skills/ultragoal/SKILL.md` | model-facing usage doc (93 lines, no loop program) |
| CLI | `src/cli/commands/ultragoal.ts`, registered at src/cli/index.ts:1491 (`omc ultragoal`) | subcommands `create-goals`, `complete-goals`, `add-goal`, `record-review-blockers`, `checkpoint`, `status`, `list-plans` (+ aliases `create`, `complete|next|start-next`) |
| Engine | `src/ultragoal/artifacts.ts` (899 lines) | plan/ledger persistence, reconciliation, gate validation |
| Stop hook | `scripts/persistent-mode.mjs:1173-1211` | "Priority 1.5: Ultragoal durable goal execution" — blocks session stop |

### Artifacts and schemas

Single-plan layout: `.omc/ultragoal/{brief.md, goals.json, ledger.jsonl}` (constants `ULTRAGOAL_DIR = '.omc/ultragoal'` etc., artifacts.ts:11-15); rooted at `getOmcRoot(cwd)` so multi-repo workspaces share one `.omc` (artifacts.ts:177). Multi-plan (parallel sessions): `--plan-id <id>` or `--auto-plan-id` writes under `.omc/ultragoal/plans/{planId}/`; auto IDs are `"{epochMs}-{slug}"` from the brief's first line (artifacts.ts:237-248); plan IDs must match `/^[a-zA-Z0-9][a-zA-Z0-9._-]*$/`. Resolution when `--plan-id` is omitted: legacy `goals.json` wins, else exactly one multi-plan, else a loud `UltragoalError` listing candidates (artifacts.ts:220-235). `create-goals` refuses to overwrite an existing plan without `--force` (artifacts.ts:449-454).

`goals.json` is an `UltragoalPlan` (`version: 1`, `claudeGoalMode`, `claudeObjective`, `aggregateCompletion`, `activeGoalId`, `goals[]`); each `UltragoalItem` has `id` (format `G%03d-<36-char-slug>`, artifacts.ts:396-404), `status` in `'pending' | 'in_progress' | 'complete' | 'failed' | 'review_blocked'`, `attempt`, timestamps, `evidence`, `failureReason` (artifacts.ts:35-80). `ledger.jsonl` is append-only JSONL with event enum `plan_created | goal_started | goal_resumed | goal_completed | goal_blocked | goal_failed | goal_retried | aggregate_completed | goal_added | final_review_failed | goal_review_blocked` (artifacts.ts:82-102). Goals are derived from the brief when not passed explicitly: dedup'd bullet/numbered lines (<= 1200 chars), else paragraphs, else the whole brief as one goal (`deriveGoalCandidates`, artifacts.ts:371-394).

### Lifecycle and /goal handoff

`complete-goals` resumes any `in_progress` goal first, else starts the next `pending` (or `failed` with `--retry-failed`), stamps `attempt += 1`/`activeGoalId`, and prints `buildClaudeGoalInstruction` — a fully scripted handoff telling the model when to invoke `/goal <condition>`, when it may not clear it, and the exact `omc ultragoal checkpoint ...` command to run next (artifacts.ts:575-603, 805-899). Two modes: default `aggregate` (one `/goal` spans the run; objective is `"Complete all ultragoal stories in {planDir}/goals.json: G001 ...; G002 ..."`, capped at 4,000 chars with a shorter fallback, artifacts.ts:336-345) and `per_story` (`--claude-goal-mode per-story`). New plans default to aggregate (artifacts.ts:479), but plans missing the field decode as `per_story` for backwards compatibility (artifacts.ts:324-326).

`checkpoint --status complete|failed|blocked` is the verification choke point. Complete checkpoints must be for the active in-progress goal and pass snapshot reconciliation: in aggregate mode mid-run the snapshot must be `active` with the aggregate objective; the final story requires `complete` (artifacts.ts:643-659). A `blocked` checkpoint exists solely for the "completed legacy /goal blocks setting a new /goal in this session" trap — it demands a snapshot whose status is `complete` and whose objective *differs* from the expected one, then keeps the story in progress so it can resume in a fresh session (artifacts.ts:610-637). A heuristic escape hatch reconciles a *task-scoped* completed snapshot as aggregate completion only when the evidence text names the goal id, mentions `.omc/ultragoal` artifacts, contains both implementation-done and validation-passed language, and the snapshot objective maps to the brief (`canReconcileCompletedTaskScopedAggregateSnapshot`, artifacts.ts:262-308) — pure text-forensics on model-supplied proof.

### Final quality gate and review blockers

Final completion (the last unresolved story) requires `--quality-gate-json` validated by `validateQualityGate` (artifacts.ts:545-573): `aiSlopCleaner.status === 'passed'` ("run ai-slop-cleaner even when it is a no-op"), `verification.status === 'passed'` with non-empty `verification.commands[]`, and `codeReview.recommendation === 'APPROVE'` plus `codeReview.architectStatus === 'CLEAR'` — each with non-empty evidence strings. A non-clean review must instead go through `record-review-blockers`, which flips the final story to `review_blocked`, appends a new blocker story, and logs three ledger events (`final_review_failed`, `goal_added`, `goal_review_blocked`) while the `/goal` stays active (artifacts.ts:735-803). `isUltragoalDone` therefore requires every goal resolved AND the latest non-`review_blocked` goal to be `complete` (artifacts.ts:357-364) — a chain of review-blocked stories can never terminate the plan by itself.

### Persistent-mode enforcement

Typing the `ultragoal` keyword (magic-keyword regex, scripts/keyword-detector.mjs:534; explicit `\b(ultragoal)\b` match at :1274) seeds `ultragoal-state.json` with `max_reinforcements: 50` and `awaiting_confirmation: true` (scripts/keyword-detector.mjs:914-928). The Stop hook then blocks session exit at "Priority 1.5" with `decision: "block"` and reason `[ULTRAGOAL #{n}/{max}] Ultragoal mode is active. Continue the durable goal workflow, keep the matching Claude /goal active, and checkpoint .omc/ultragoal/ledger.jsonl before stopping ...` plus the resolved objective (scripts/persistent-mode.mjs:1173-1211). Terminal detection is dual-source: state phase in `ULTRAGOAL_TERMINAL_PHASES` (`complete, completed, done, all-done, all_done, failed, cancelled, canceled, aborted`, persistent-mode.mjs:262-272) OR the durable `goals.json` itself (`aggregateCompletion.status === "complete"` or every goal `complete`/`review_blocked`, persistent-mode.mjs:601-618) — the hook reads the ledger-backed truth, not just session state. Exceeding `max_reinforcements` silently allows the stop (`{ continue: true, suppressOutput: true }`) — a fail-open ceiling. Note ultragoal is intentionally absent from `MODE_NAMES` (src/lib/mode-names.ts:10-20); it lives in the hook-script mode set (`ralph, ultragoal, autopilot, ...`, persistent-mode.mjs:8) and the keyword priority order `['cancel','ralph','ultragoal','autopilot','ultrawork', ...]` (keyword-detector.mjs:1161).

## 3. goal-workflows: snapshot parsing and reconciliation

`src/goal-workflows/claude-goal-snapshot.ts` (161 lines) is the whole subsystem; its only consumers are `src/ultragoal/artifacts.ts` and `src/cli/commands/ultragoal.ts`. It adds three things: (1) `parseClaudeGoalSnapshot` — tolerant extraction from arbitrary model-supplied JSON, accepting `{goal:{...}}` or flat shapes, objective from `objective|condition|goal|description`, and status normalization (`completed|done → complete`, `cleared → cancelled`, `in_progress|pending|running → active`, else `unknown`) (claude-goal-snapshot.ts:44-103); (2) `readClaudeGoalSnapshotInput` — the CLI flag accepts inline JSON *or* a file path, with loud `ClaudeGoalSnapshotError`s otherwise (:105-121); (3) `reconcileClaudeGoalSnapshot(snapshot, {expectedObjective, allowedStatuses, requireSnapshot, requireComplete})` — whitespace-normalized exact objective equality plus status allow-list, returning `{ok, warnings, errors}` where a missing snapshot is an error only when `requireSnapshot` (:123-156). This is the codified trust boundary: "OMC validates them for textual consistency ... but it cannot independently observe Claude /goal state" (skills/ultragoal/SKILL.md:91).

## 4. missions/: vestigial fixtures of a deprecated flow

Verdict: **vestigial**. The four committed dirs (`enhance-omc-performance`, `optimize-omc`, `optimize-performance`, `prove-reliability-by-finding-and-fixing-flaky-te`) each hold a trivial `mission.md` (`# Mission` + one line) and a `sandbox.md` whose YAML frontmatter is an evaluator contract, e.g. `evaluator: {command: npm run test:run -- --reporter=verbose, format: json, keep_policy: score_improvement}`. They were written by `src/cli/autoresearch-guided.ts`, which creates `<repoRoot>/missions/<slug>/{mission.md,sandbox.md}` (autoresearch-guided.ts:105-124) — but nothing outside that file imports it, and the `omc autoresearch` CLI is a "Hard-deprecated shim" that only prints a redirect to `/deep-interview --autoresearch` + the autoresearch skill (src/cli/autoresearch.ts:1-22, src/cli/index.ts:1454-1461). The one live-ish reader, `collectMissionExampleSignals`, scans up to 5 `missions/*` dirs and greps `command:` from sandbox.md to feed "existing mission example" lines into a setup prompt (src/cli/autoresearch-setup-session.ts:67-87) — but that module too is only imported by the orphaned guided flow. The ACTIVE autoresearch skill stores missions under `.omc/autoresearch/<mission-slug>/mission.md` instead (skills/autoresearch/SKILL.md:34-45). The one durable piece is the sandbox frontmatter schema itself, still enforced by the live runtime contract: `evaluator.command` required, `evaluator.format` must be `json` in v1, `keep_policy` one of `score_improvement, pass_only` (src/autoresearch/contracts.ts:145-164, 130-136).

## Patterns for sibling harnesses

- **Sealed-evaluator enforcement outside the agent**: a standalone script diffs the worktree against the merge-base of the improvement branch and hard-fails on modified `sealed_files` — the optimizer physically cannot grade its own homework (validate.sh:147-223). Adapt: omx's `evaluator.sh` should be listed in a sealed manifest checked by a pre-benchmark script, not by prompt discipline.
- **Re-benchmark merge gate**: never trust the candidate branch's own score; merge, re-run the benchmark on the merged state, and `reset --hard HEAD~1` on regression (SKILL.md:270-277). Adapt: omx keep/discard decisions should re-evaluate after integration, not on the experiment branch.
- **Ranked-candidate fallback tournament**: walk candidates best-first through gate + merge + confirm instead of committing to argmax; conflicts and regressions just advance to the next candidate. Adapt directly for any N-candidate selection.
- **Plateau vs circuit-breaker as separate counters**: small-delta *wins* increment plateau; *winless* rounds increment the breaker; a real win resets both (SKILL.md:288-291). Adapt: omx exp-loop stop logic should distinguish "improving too slowly" from "everything failing".
- **Diversity constraints as reviewable rules (H001/H002/H003)**: one-hypothesis-per-plan, no 3-streak of one approach family, intra-round family uniqueness — enforced by a critic against a user-editable `harness.md` with custom families. Adapt: encode experiment-design diversity rules as data the design gate checks.
- **Mandatory structured failure analysis**: non-success results are schema-invalid without `{what, why, category, lesson}` from a fixed category enum (validate.sh:320-360); lessons feed the next round's planners. Adapt: make omx run post-mortems a validation requirement, not a habit.
- **Topic/session-scoped artifact roots with legacy fallback**: `topics/<slug>/sessions/<sid>/` isolation plus explicit `scope_mode` reporting from a single resolver script (resolve-paths.mjs). Adapt for any per-campaign state dir that multiple sessions may touch.
- **Durable plan + append-only ledger split**: mutable `goals.json` snapshot next to an immutable `ledger.jsonl` event log, one directory per plan id for parallel runs (artifacts.ts:11-33). Adapt: omp/omx campaign state benefits from the same replayable two-file shape.
- **Snapshot reconciliation of model-claimed state**: when the harness cannot observe an in-session fact, require the model to hand back a JSON snapshot and verify it textually (objective equality + status allow-list + evidence keyword forensics) before accepting a terminal transition (claude-goal-snapshot.ts, artifacts.ts:262-308). Adapt: any "the agent says it's done" gate.
- **Evidence-typed final quality gate**: completion demands a structured `{aiSlopCleaner, verification.commands[], codeReview: APPROVE+CLEAR}` payload, and a dedicated `record-review-blockers` path converts a failed gate into new work instead of a lie (artifacts.ts:545-573, 735-803). Adapt: OMD docs-verify / omx report gates can require the same machine-checkable evidence object.
- **Dual-source terminal detection in the Stop hook**: the hook consults both session state phase and the durable plan file before deciding the mode is done, with a reinforcement counter that fails open at a ceiling (persistent-mode.mjs:601-618, 1183-1189). Adapt: omha stop-guards should read the durable artifact, not only session state.

# Hook Architecture (every hook, every event)

OMC's hook layer is the plugin's nervous system: 22 command registrations across 11 Claude Code hook events, all declared in `hooks/hooks.json` and all funneled through one cross-platform runner (`scripts/run.cjs`). The hooks implement four distinct interaction styles — context injection (`hookSpecificOutput.additionalContext`), stop blocking (`decision:"block"` + `reason`), tool denial (`permissionDecision:"deny"`), and silent state bookkeeping — and every one of them is engineered to fail open: any parse error, missing file, or timeout degrades to `{continue:true, suppressOutput:true}` so a broken hook can never brick a session. Two implementation planes coexist: the ACTIVE plugin plane is hand-written, largely self-contained `.mjs` scripts in `scripts/` (wired by `hooks/hooks.json`), which lazily import compiled TypeScript from `dist/hooks/*` (built from `src/hooks/*`) for heavier subsystems; the SECONDARY plane is `src/hooks/bridge.ts`'s `processHook(hookType, input)` dispatcher (src/hooks/bridge.ts:3054), bundled into `bridge/cli.cjs` and mirrored by `templates/hooks/*.mjs` for npm/settings.json installs — same behaviors, different wiring. This section documents the plugin plane and cites the TS plane where the `.mjs` shims delegate to it.

## Execution pipeline: run.cjs

Every registration invokes `node "$CLAUDE_PLUGIN_ROOT"/scripts/run.cjs "$CLAUDE_PLUGIN_ROOT"/scripts/<hook>.mjs [args]` (hooks/hooks.json — whole file). `run.cjs` provides three guarantees:

1. **Stale-plugin-root recovery**: if the target script path no longer exists (plugin was updated mid-session), it tries `realpathSync`, then scans sibling semver directories under the plugin cache and runs the same script from the newest version; if nothing resolves it exits 0 so "hooks are never blocked" (scripts/run.cjs:44-91, 138-144).
2. **Inner timeout with cushion**: it re-reads `hooks/hooks.json`, finds its own registration's `timeout` (seconds), and kills the child `TIMEOUT_CUSHION_MS = 500` ms early (`SIGKILL` on POSIX, `SIGTERM` on Windows), logging `"timed out after Xms; exiting fail-open"` (scripts/run.cjs:103-136, 163-170).
3. **Exit-code semantics**: it propagates `result.status ?? 0` (scripts/run.cjs:167, `null → 0 to avoid blocking hooks`). No OMC hook ever uses exit code 2 to block; all blocking is expressed in stdout JSON. Stdin is read by every script through `readStdin(timeoutMs=5000)`, an event-based reader that resolves with whatever arrived when the timeout fires and returns `''` on `error`, preventing EOF hangs (scripts/lib/stdin.mjs:20-64).

## Registration table (hooks/hooks.json)

| Event | Matcher | Script (scripts/) | Timeout s | Output style |
|---|---|---|---|---|
| UserPromptSubmit | `*` | keyword-detector.mjs | 10 | inject additionalContext / arm state |
| UserPromptSubmit | `*` | skill-injector.mjs | 15 | inject learned-skill context |
| SessionStart | `*` | session-start.mjs | 5 | inject restore blocks + `systemMessage` |
| SessionStart | `*` | project-memory-session.mjs | 5 | inject project memory |
| SessionStart | `*` | wiki-session-start.mjs | 5 | inject wiki summary |
| SessionStart | `init` | setup-init.mjs | 30 | create `.omc/` dirs, validate configs |
| SessionStart | `maintenance` | setup-maintenance.mjs | 60 | prune state, vacuum SQLite |
| PreToolUse | `*` | pre-tool-enforcer.mjs | 3 | advisory inject / `permissionDecision:deny` / `updatedInput` |
| PermissionRequest | `Bash` | permission-handler.mjs | 5 | `decision.behavior:"allow"` for safe commands |
| PostToolUse | `*` | post-tool-verifier.mjs | 3 | per-tool advisory inject |
| PostToolUse | `*` | project-memory-posttool.mjs | 3 | silent learning |
| PostToolUse | `*` | post-tool-rules-injector.mjs | 3 | inject matching rule files |
| PostToolUseFailure | `*` | post-tool-use-failure.mjs | 3 | write error state (silent) |
| SubagentStart | `*` | subagent-tracker.mjs start | 3 | track + one-line inject |
| SubagentStop | `*` | subagent-tracker.mjs stop | 5 | track (suppressed output) |
| SubagentStop | `*` | verify-deliverables.mjs | 5 | always suppressed (see below) |
| PreCompact | `*` | pre-compact.mjs | 10 | checkpoint + summary |
| PreCompact | `*` | project-memory-precompact.mjs | 5 | preserve directives |
| PreCompact | `*` | wiki-pre-compact.mjs | 3 | wiki stats as `systemMessage` |
| Stop | `*` | context-guard-stop.mjs | 5 | block ≤2× when context ≥75% |
| Stop | `*` | workflow-drift-guard.mjs | 3 | block prose-question / fake-completion |
| Stop | `*` | persistent-mode.mjs | 10 | block while a mode is active |
| Stop | `*` | code-simplifier.mjs | 5 | opt-in one-shot block |
| SessionEnd | `*` | session-end.mjs | 30, `"async": true` | cleanup, metrics, notify |
| SessionEnd | `*` | wiki-session-end.mjs | 30, `"async": true` | wiki session flush |

The `"async": true` flag on both SessionEnd entries lets Claude Code fire them without waiting — the only two non-blocking registrations.

## UserPromptSubmit: keyword detection and mode arming

`keyword-detector.mjs` (1,501 lines, self-contained) is the magic-keyword engine. Flow:

```
stdin JSON --> extractPrompt (prompt | message.content | parts[])       (keyword-detector.mjs:186-202)
  guards: DISABLE_OMC / OMC_SKIP_HOOKS=keyword-detector (1184-1189)
          OMC_TEAM_WORKER set -> pass through (anti worker-spawn loop, 1193-1196)
          /ask <provider> prefix -> pass through (1220-1223)
          /ralplan prefix -> arm ralplan state immediately, emit [RALPLAN INIT] (1225-1234)
  sanitize: stripSystemEchoes(sanitizeForKeywordDetection(prompt).toLowerCase())  (1241-1243)
  match keywords -> resolveConflicts -> arm state files -> emit [MAGIC KEYWORD: ...]
```

**Sanitization before matching** strips pasted command payloads, HTML comments, XML tag blocks, URLs, blockquotes, markdown tables, file paths (Unicode-aware, CJK-safe), code fences and inline code (keyword-detector.mjs:242-268), then strips *system echo blocks* — prior hook output such as `[RALPH LOOP - ITERATION N]`, `[AUTOPILOT...]`, `[MAGIC KEYWORD: ...]`, `Stop hook blocking error`, and `PreToolUse:... hook additional context:` headers plus their continuation lines (SYSTEM_ECHO_BLOCK_PATTERNS, 442-461). Without this, pasting a previous loop banner into a new session would re-trigger ralph and persist the echo as the loop prompt — "a recursive self-reinforcing loop that is hard to cancel" (781-808).

**Intent filtering**: each regex hit passes through `isInformationalKeywordContext` (701-779), which vetoes activation when the keyword sits in quotes without a nearby command verb, on a blockquote/table line, inside reference-style content (`looksLikeReferenceContent`, 589-603), or near multilingual question phrasing (EN/KO/JA/ZH `INFORMATIONAL_INTENT_PATTERNS`, 396-401). Ralph/ultrawork get an extra meta-or-banter veto for Korean/Japanese chit-chat (671-699). `ultragoal` and `ralplan` require *explicit* invocation context (slash/`force:` prefix or an activation verb like use/run/start within 80 chars) via `hasExplicitActionableKeyword`/`hasActionableRalplanKeyword` (810-877).

**Keyword table** (patterns at keyword-detector.mjs:1249-1346, priority order at 1161-1162): `cancelomc|stopomc` → cancel (exclusive; clears `ralph, ultragoal, autopilot, ultrawork, swarm, ralplan` state files, 1447-1451); `ralph|don't stop|must complete|until done|랄프|ラルフ` → ralph; `autopilot|full auto|fullsend|build me a(n) app/feature/...|i want a|handle it all|end to end` → autopilot; `ultrawork|ulw|uw` → ultrawork; `ccg`; `ralplan`; `deep interview|ouroboros`; anti-slop (explicit `deslop` or action+smell pattern pair, 213-220); `tdd|test first|red green`; `code review`/`security review` (skipped when the prompt looks like an echoed review-outcome menu, `isReviewSeedContext` 237-240); `ultrathink|think hard|think deeply`; `deepsearch|search the codebase`; `deep-analyze`; `wiki`. Team keyword detection is deliberately removed — "explicit-only via /team skill" to prevent infinite worker spawning (1285-1286).

**Arming**: matched modes among `ralph, ultragoal, autopilot, ultrawork, ralplan` get a state file written via `activateState` (880-963) to `<omcRoot>/state/sessions/<sessionId>/<mode>-state.json` (atomic write; legacy fallback `<omcRoot>/state/`). Ralph's schema: `{active:true, iteration:1, max_iterations:100, started_at, prompt, session_id, project_path, linked_ultrawork:true, awaiting_confirmation:true, awaiting_confirmation_set_at, last_checked_at}` (888-902). Prompts are laundered by `sanitizePromptForState` — echoes are replaced with `'(prompt omitted: pasted system echo)'` and everything is truncated to `MAX_STATE_PROMPT_LEN = 500` (473-532). Ralph implicitly arms ultrawork too (1467-1471).

**Injection**: output is `{continue:true, hookSpecificOutput:{hookEventName:'UserPromptSubmit', additionalContext}}` (1172-1180). Skill-routing keywords render `[MAGIC KEYWORD: <NAME>]` with `Preferred invocation: /oh-my-claudecode:<name>`, a `Read fallback:` SKILL.md path, and a compact echo of the user request capped at `SKILL_INVOCATION_USER_REQUEST_MAX = 1200` chars (1081-1099); multiple hits render `[MAGIC KEYWORDS DETECTED: A, B]` with ordered skill blocks (1104-1131). Pure "mode message" keywords (ultrathink/deepsearch/analyze/tdd/code-review/security-review) inject static `<think-mode>`/`<search-mode>`/... blocks instead of skill invocations (114-183). A post-ralplan shortcut consults `dist/team/followup-planner.js` and approved-plan artifacts to route a terse "team"/"ralph" follow-up straight to the approved execution lane (1374-1428).

`skill-injector.mjs` is the second UserPromptSubmit hook: it loads the esbuild bundle `dist/hooks/skill-bridge.cjs` (falling back to an inline implementation), matches learned/local skills against prompt triggers, dedups per session through an `O_CREAT|O_EXCL` file lock with stale-lock reaping (scripts/skill-injector.mjs:145-260), and injects a skills message via the same additionalContext shape (607-617).

## SessionStart: restore-and-advise, never auto-resume

`session-start.mjs` composes two channels: `messages[]` → `hookSpecificOutput.additionalContext` (model-visible) and `userMessages[]` → `systemMessage` (user-visible), emitted together (session-start.mjs:1145-1158). Model-visible blocks are wrapped in `<session-restore>`, `<project-memory-context>`, or `<notepad-context>` tags: `[OMC VERSION DRIFT DETECTED]` (826-835), `[ULTRAWORK MODE RESTORED]` (887-901), `[RALPH LOOP RESTORED]` (920-935), `[PENDING TASKS DETECTED]` from project-local `todos.json` only — the global `~/.claude/todos/` scan was removed to stop phantom counts (937-970), `[PROJECT MEMORY]` summary (972-990), and the notepad's `## Priority Context` section (992-1012). Crucially, mode restoration is advisory: every block says "Treat this as prior-session context only... resume only if the user explicitly asks" — SessionStart never re-arms a loop. State reads are session-scoped ONLY when a session id exists (`state/sessions/<sid>/ultrawork-state.json`, 874-885); mismatched `session_id` inside the file voids the restore. The hook also performs janitorial work: writes a `session-started.json` marker and reconciles abandoned sessions (822-823), repairs the plugin cache by symlinking versions older than the latest two to the newest (1014-1116), dispatches a session-start notification in a detached background process so transports can never pollute hook stdout (1118-1143), and warns when HUD is unconfigured (`[OMC] HUD not configured... Run /hud setup`, 862-866).

The `init` and `maintenance` matchers gate `setup-init.mjs`/`setup-maintenance.mjs`, thin shims over `dist/hooks/setup/index.js` — `init` creates directory structure/validates configs/sets env, `maintenance` prunes old state and vacuums SQLite (src/hooks/setup/index.ts:1-8, 284, 466). They never fire on normal `startup|resume|clear` sources.

## PreToolUse: advisory nudges, model-routing denial, input rewriting

`pre-tool-enforcer.mjs` is the every-turn re-injection engine and the only PreToolUse handler. Its main path (1215-1517):

- **Skill-state bookkeeping**: on `Skill` calls it writes `skill-active-state.json` with tiered protection (`light`=3 reinforcements/5 min, `medium`=5/15 min, `heavy`=10/30 min per `SKILL_PROTECTION_CONFIGS`, 1012-1046; only `oh-my-claudecode:`-prefixed skills qualify, 1048-1057) and clears `awaiting_confirmation` on the matching mode state via `confirmSkillModeStates` (1175-1196) — the handshake that tells the Stop hook "the skill actually started, enforcement may begin."
- **Model-routing guard**: for `Task`/`Agent` under `forceInherit` (env `OMC_ROUTING_FORCE_INHERIT=true` or config `routing.forceInherit`, 1077-1081) it emits `permissionDecision:'deny'` with a `[MODEL ROUTING]` reason for tier names invalid on Bedrock/Vertex/proxy, for `[1m]`-suffixed session models, and for agent definitions whose frontmatter `model:` is a bare Anthropic ID (1290-1379). Outside forceInherit it silently **rewrites** the tool call via `hookSpecificOutput.updatedInput` to apply a configured per-agent model (1382-1395, 1503-1510).
- **Delegation and context preflights**: optional `routing.forceDelegation.enforce` config denies raw Read/Edit/Write/Grep/Glob that should be delegated (1430-1448); an agent-heavy preflight can block Task/Agent spawning when the transcript shows context exhaustion (1450-1461).
- **Advisories**: per-tool one-liners (`Bash`: "Use parallel execution...", `Edit`/`Write`: "Verify changes work after editing...", 991-999), an agent-spawn label, a slop-language warning when prompt-like fields contain fallback/workaround phrasing (168-309), and — for any other tool while a mode-state file is active — the ralph heartbeat: `` `The boulder never stops. Continue until all tasks complete.` `` (1002). Mode activity is detected by scanning the nine `MODE_STATE_FILES` (`autopilot|ultrapilot|ralph|ultragoal|ultrawork|ultraqa|pipeline|team|omc-teams`-state.json, 407-417).
- **Noise controls**: `OMC_QUIET` levels (≥1 silences Bash/Edit/Write/Read/Grep/Glob advisories, ≥2 silences TodoWrite and agent-spawn labels, 984-988, 428-432) and a per-message advisory throttle keyed by content, default cooldown `ADVISORY_THROTTLE_DEFAULT_COOLDOWN_MS = 5*60*1000` (override `OMC_PRE_TOOL_ADVISORY_COOLDOWN_MS`), stored in `pre-tool-advisory-throttle.json` with max 100 entries — throttle IO failure fails open and repeats the nudge (317-404).
- **Notification**: `AskUserQuestion` triggers a fire-and-forget `notify('ask-user-question', ...)` so the user is pinged *before* the tool blocks for input (1398-1421).

## PermissionRequest (matcher: Bash): allow-only fast path

`permission-handler.mjs` delegates to `processPermissionRequest` (src/hooks/permission-handler/index.ts:642-676). It only ever *allows*, never denies: if the command matches one of the anchored `SAFE_PATTERNS` (`^git (status|diff|log|branch|show|fetch)`, `^npm run (lint|build|check|typecheck)`, `^pnpm`/`^yarn` lint/build/check/typecheck, `^tsc`, `^gh (issue|pr) (view|list|status)`, `^eslint `, `^prettier `, `^cargo (check|clippy|build)`, `^ls` — `cat, head, tail` explicitly `REMOVED` as arbitrary-file readers, src/hooks/permission-handler/index.ts:33-46), contains no `DANGEROUS_SHELL_CHARS` (`/[;&|`$()<>\n\r\t\0\\{}\[\]*?~!#]/`, :51; quotes intentionally excluded per issue #146), and is not covered by a user `permissions.ask` entry, it returns `decision:{behavior:'allow', reason:'Safe read-only or test command'}` (:661,667); anything else falls through to the normal permission flow.

## PostToolUse: three parallel injectors

`post-tool-verifier.mjs` produces per-tool feedback (964-1066): Bash failure/exit-code/background-op detection, Task/TaskOutput result summaries with truncation notes (`OMC_AGENT_OUTPUT_ANALYSIS_LIMIT` default 12000 chars analyzed, `OMC_AGENT_OUTPUT_SUMMARY_LIMIT` 360), Edit/Write failure detection using structured tool_response envelopes before falling back to string sniffing (1086-1090), and quiet-gated hints ("Extensive reading (N files)..." above 10 Reads). It also: appends Bash commands to `~/.bash_history` when config-enabled (1099-1103), harvests `<remember>` tags from Task agent output into the notepad (1106-1113), clears `skill-active-state.json` when the owning skill completes (1115-1128), and appends a preemptive-compaction warning when transcript usage crosses `OMC_PREEMPTIVE_COMPACTION_WARNING_PERCENT=70` / `..._CRITICAL_PERCENT=90` with a 60 s cooldown (post-tool-verifier.mjs:24-29, 531-566). `post-tool-rules-injector.mjs` injects rule files (`.claude/rules`, `.github/instructions`, `.cursor/rules`, `~/.claude/rules`) matching the accessed file, deduplicated by content hash + realpath per session, with the project root derived from the accessed file's path (worktree-safe) rather than cwd (post-tool-rules-injector.mjs:1-25, 86-100). `project-memory-posttool.mjs` silently feeds tool outputs to `dist/hooks/project-memory/learner.js`.

`post-tool-use-failure.mjs` (PostToolUseFailure) writes `last-tool-error-state.json` (session-scoped) or legacy `last-tool-error.json` with `{tool, input preview, error, retry_count, timestamp}`, incrementing `retry_count` on repeats (scripts/post-tool-use-failure.mjs:197-215, 368-380). The Stop hook consumes it with a 60-second staleness window and prepends "Fix the issue... RETRY the operation" guidance to its block reason (persistent-mode.mjs:168-181, 220-236).

## SubagentStart/Stop: tracking, and a deliberately silenced verifier

`subagent-tracker.mjs start|stop` shims to `dist/hooks/subagent-tracker/index.js`, which maintains `.omc/state/sessions/{sessionId}/subagent-tracking-state.json` with per-agent `{status:"running"|"completed"|"failed", started_at, ...}`, reconciles orphans, and reaps stale running entries (src/hooks/subagent-tracker/index.ts:11, 41, 621-830). Start injects a single line (`Agent <type> started (<id>)`); Stop suppresses output entirely — the #3209 regression showed SubagentStop `additionalContext` is reinjected into the *finishing subagent*, not the parent. For the same reason `verify-deliverables.mjs` — which loads `.omc/deliverables.json` or `templates/deliverables.json`, resolves the current team stage from `team-state.json`, and checks per-stage required files/sizes/patterns/sections — emits `{continue:true, suppressOutput:true}` on every path *including when deliverables are missing* (scripts/verify-deliverables.mjs:14-22, 215-229). Its verdict is computed and discarded: wired but inert in effect.

## Stop: the four-guard gauntlet

Stop hooks run in registration order; the first `decision:"block"` wins.

1. **context-guard-stop.mjs** — estimates context% by reading the transcript's last 4 KB and parsing the final `"context_window"`/`"input_tokens"` pair; if ≥ `OMC_CONTEXT_GUARD_THRESHOLD` (default 75) and < `CRITICAL_THRESHOLD = 95`, blocks with refresh advice, at most `MAX_BLOCKS = 2` per session (blockCount persisted in a guard file). Above 95% it always lets the stop through, and it exempts context-limit stops and user aborts (context-guard-stop.mjs:30-32, 236-274).
2. **workflow-drift-guard.mjs** — deterministic anti-drift checks on `last_assistant_message`: (a) a final response ending in a preference/approval question shaped for `AskUserQuestion` (question mark + structured-choice phrasing, minus free-form markers) is blocked with instructions to use the tool; (b) a completion claim (`done|complete|finished|implemented|fixed|...`) while `git diff`/untracked code files still contain blockers (`.skip(`/`.only(`, actionable TODOs, `throw new Error("Not implemented")`, placeholder returns) is blocked with the offending `path:line` list, scanning comment text only after stripping string/regex literals (workflow-drift-guard.mjs:19-30, 147-209). Respects `stop_hook_active` re-entrancy.
3. **persistent-mode.mjs** — the loop engine (detailed below).
4. **code-simplifier.mjs** — opt-in via `~/.omc/config.json` `codeSimplifier.enabled:true`; when recently modified source files exist it blocks once (marker-file guarded) with a prompt to delegate them to the code-simplifier agent (code-simplifier.mjs:1-10, 25, 115).

### persistent-mode.mjs: "the boulder" Stop enforcer

Before any blocking, seven hard exemptions pass the stop through: `stop_hook_active === true` (never double-block — trips Claude Code's safety override, 971-977); context-limit stop reasons (`context_limit`, `token_limit`, `conversation_too_long`, ... — blocking would deadlock compaction, issue #213, 821-845, 987-993); transcript context estimate ≥ `CRITICAL_CONTEXT_STOP_PERCENT = 95` (847-877, 995-999); user abort (`aborted|abort|cancel|interrupt` exact, `user_cancel|ctrl_c|manual_stop` substring, 882-900); authentication errors (401/403/oauth-expired patterns, 902-932); scheduled-wakeup stops (934-961); and *pending owned async work* — a fresh running background task in HUD state, a `running` subagent entry younger than `RUNNING_SUBAGENT_STALE_MS = 30*60*1000`, or a pending scheduled wakeup (321-384, 1018-1021). A fresh cancel signal (`cancel-signal-state.json`, TTL `CANCEL_SIGNAL_TTL_MS = 30_000`) also short-circuits (645-680, 1079-1082).

State files are then read session-scoped with fallback scanning of all session dirs for matching `session_id`, then legacy local/global paths (`readStateFileWithSession`, 533-568; global = `~/.omc/state/`). Each mode blocks only if: `active:true`, not tombstoned in the skill ledger (`WORKFLOW_SLOT_TOMBSTONE_TTL_MS = 24h`, 570-593), not awaiting confirmation (`awaiting_confirmation` honored only within `AWAITING_CONFIRMATION_TTL_MS = 2*60*1000` of arming — the grace window before PreToolUse confirms the skill started, 403-425), not stale (`STALE_STATE_THRESHOLD_MS = 2h` since the newest of `last_checked_at|updated_at|started_at`, 239-307), session-matched, and project-matched by normalized `project_path` (473-502).

Priority chain and block banners: ralph (`[RALPH LOOP - ITERATION i/max] Work is NOT done. Continue working... run /oh-my-claudecode:cancel`, iteration incremented and written back; at max, extends `max_iterations += 10` and emits `[RALPH LOOP - EXTENDED]` unless `OMC_SECURITY=strict` imposes `hardMaxIterations` default 200 from `.claude/omc.jsonc` or `~/.config/claude-omc/config.jsonc`, then `[RALPH LOOP - HARD LIMIT] ... Mode auto-disabled`, 49-87, 1093-1166) → ultragoal (`[ULTRAGOAL #n/50]`, 1202-1210) → autopilot (`[AUTOPILOT - Phase: x]`; orphaned routing-echo states are deleted instead of enforced, 434-457, 1242-1252) → ultrapilot (`[ULTRAPILOT] N workers still running`) → swarm (`swarm-active.marker` + `swarm-summary.json`, `[SWARM ACTIVE] N tasks remain`) → pipeline (`[PIPELINE - Stage i/N]`) → team (`[TEAM - Phase: x]`, active phases whitelisted in `TEAM_ACTIVE_PHASES`, 273-285, 1393) → omc-teams → ultraqa (`[ULTRAQA - Cycle i/10]`, stops when `all_passing`) → ultrawork (`[ULTRAWORK #n/50] Mode active.` plus incomplete Task/todo counts from Claude-native `<config>/tasks/<sid>/*.json` and project-local todos, and a live `Current objective:` line; allows stop after `max_reinforcements = 50`, 690-772, 1477-1530). Every banner embeds the exit path (`run /oh-my-claudecode:cancel`, `--force` fallback) and any fresh tool-error retry guidance. If nothing blocks, an idle notification may be dispatched in the background under a 60 s cooldown (`notificationCooldown.sessionIdleSeconds` in `~/.omc/config.json`, 105-146) and the hook emits `{continue:true}`. The companion string `The boulder never stops` is injected by the *PreToolUse* hook while these states are active (pre-tool-enforcer.mjs:1002) — Stop supplies pressure, PreToolUse supplies the heartbeat.

## PreCompact and SessionEnd

`pre-compact.mjs` → `processPreCompact` writes a `CompactCheckpoint` under `.omc/state/checkpoints/` capturing active mode snapshots (autopilot phase, ralph iteration/prompt, ultrawork prompt, ultraqa cycle), a todo summary, exported notepad wisdom, and background-job stats, and returns a formatted summary for reinjection (src/hooks/pre-compact/index.ts:28-66, 71-104, 319-351). `project-memory-precompact.mjs` preserves user directives; `wiki-pre-compact.mjs` emits `[Wiki: N pages | categories: ... | last updated: ...]` as a `systemMessage` (src/hooks/wiki/session-hooks.ts:169-185). `session-end.mjs` (async, stdin timeout tightened to 1000 ms) delegates to `handleSessionEnd`, which clears `SESSION_END_MODE_STATE_FILES`, cleans session-owned teams and python-repl bridges under a cleanup budget (default 2000 ms, max 10000 ms), writes `SessionMetrics {agents_spawned, agents_completed, modes_used, duration_ms, reason}`, and fires stop callbacks/notifications (src/hooks/session-end/index.ts:16-50).

## Session id, state discovery, kill switches

Every script resolves identity the same way: `session_id || sessionId` from stdin JSON, validated against `/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,255}$/` (path-traversal guard); `cwd || directory || process.cwd()` for the project. The state root comes from `resolveOmcStateRoot(directory)`: prefer `dist/lib/worktree-paths.js` `getOmcRoot` when built, else `OMC_STATE_DIR` env with a derived id `` `${basename}-${sha256(dir).slice(0,16)}` ``, else `<dir>/.omc` (scripts/lib/state-root.mjs:32-52). Session-scoped state lives in `<omcRoot>/state/sessions/<sid>/`, legacy in `<omcRoot>/state/`, global in `~/.omc/state/`.

| Kill switch / knob | Effect | Evidence |
|---|---|---|
| `DISABLE_OMC` | every hook returns `{continue:true}` immediately. Plugin `.mjs` guards match `=== '1'` only (keyword-detector.mjs:1186, pre-tool-enforcer.mjs:1218); the TS bridge accepts `'1'` **or** `'true'` (bridge.ts:3059) | keyword-detector.mjs:1186; bridge.ts:3059 |
| `OMC_SKIP_HOOKS=a,b` | comma tokens: `keyword-detector`, `pre-tool-use`, `post-tool-use` (verifier + rules-injector + failure hook), `subagent-start`, `subagent-stop`, `subagent-tracker`, `workflow-drift-guard`; bridge accepts its hookType names | pre-tool-enforcer.mjs:1216-1221; post-tool-rules-injector.mjs:52-66; subagent-tracker.mjs:2-18 |
| `OMC_TEAM_WORKER` | suppress keyword detection inside team workers | keyword-detector.mjs:1193-1196 |
| `OMC_QUIET=0\|1\|2` | advisory verbosity ladder | pre-tool-enforcer.mjs:428-432 |
| `OMC_SECURITY=strict` | ralph hard max iterations (default 200) | persistent-mode.mjs:52-62 |
| `OMC_CONTEXT_GUARD_THRESHOLD` | Stop context-guard trigger % (default 75) | context-guard-stop.mjs:30 |
| `OMC_PRE_TOOL_ADVISORY_COOLDOWN_MS` / `_NOW_MS` | advisory throttle window / test clock | pre-tool-enforcer.mjs:323-333 |
| `OMC_PREEMPTIVE_COMPACTION_{WARNING,CRITICAL}_PERCENT`, `_COOLDOWN_MS` | PostToolUse compaction warnings (70/90/60000) | post-tool-verifier.mjs:26-29 |
| `OMC_AGENT_OUTPUT_{ANALYSIS,SUMMARY}_LIMIT` | agent output clipping (12000/360) | post-tool-verifier.mjs:24-25 |
| `OMC_ROUTING_FORCE_INHERIT`, `OMC_SUBAGENT_MODEL`, `ANTHROPIC_DEFAULT_*_MODEL` | model-routing guard inputs | pre-tool-enforcer.mjs:1077-1081, 96-117 |
| `OMC_STATE_DIR` | centralized state root | scripts/lib/state-root.mjs:46-51 |
| `OMC_DEBUG` | stderr debug logging | project-memory-posttool.mjs:7-9 |
| Config files | `~/.claude/.omc-config.json`, `.omc/config.json` (`routing.*`, `codeSimplifier.enabled`), `.claude/omc.jsonc` / `~/.config/claude-omc/config.jsonc` (`security.hardMaxIterations`), `~/.omc/config.json` (`notificationCooldown`) | pre-tool-enforcer.mjs:1061-1074; persistent-mode.mjs:67-87, 105-110 |

## Active vs vestigial

ACTIVE: everything registered in hooks/hooks.json plus the `dist/hooks/*` modules those scripts lazily import (skill-bridge, flow-tracer, rules-injector, project-memory, pre-compact, session-end, setup, wiki, subagent-tracker, notifications, followup-planner). SECONDARY-BUT-SHIPPED: `src/hooks/bridge.ts` `processHook` plus the many `src/hooks/*` subdirectories only reachable through it (omc-orchestrator with its own boulder-state continuation, think-mode, todo-continuation, factcheck, comment-checker, empty-message-sanitizer, thinking-block-validator, task-size-detector, recovery, etc.) — exercised by the bundled `bridge/cli.cjs` (`omc-cli` bin, package.json:17), `templates/hooks/*.mjs` (npm settings.json installs), and tests, not by the plugin manifest. INERT-IN-EFFECT: `verify-deliverables.mjs` computes verdicts it never surfaces; `scripts/persistent-mode.cjs` is a legacy sibling referenced only by comments.

## Patterns for sibling harnesses

- **Single fail-open runner in front of every hook** (resolve → cushion timeout → kill → `exit(status ?? 0)`): decouples manifest timeouts from script hangs and survives plugin upgrades mid-session. Adapt: one `run.cjs` per harness reading its own hooks.json timeouts.
- **JSON-stdout contract, never exit codes**: block with `{decision:"block", reason}`, deny with `hookSpecificOutput.permissionDecision`, inject with `additionalContext`, stay silent with `suppressOutput:true`. Adapt: standardize a tiny emit helper so every handler ends in exactly one of these four shapes.
- **State-file-armed Stop loop with a confirmation handshake**: UserPromptSubmit arms `<mode>-state.json` with `awaiting_confirmation` + 2-minute TTL; PreToolUse confirms on first real Skill invocation; Stop blocks only confirmed, fresh, session- and project-matched state. Adapt: omha's route-guard can copy the arm/confirm/enforce triple to kill flush races.
- **Echo-stripping before keyword matching**: strip your own banners (`[MODE ...]` headers + continuation lines) from prompts before detection, and launder prompts before persisting them, or pasted hook output becomes a self-reinforcing loop. Adapt: every harness that re-injects banners needs the matching strip list.
- **Hard exemption ladder before any Stop block**: re-entrancy flag, context-limit reasons, ≥95% transcript estimate, user abort, auth errors, scheduled wakeups, pending owned async work. Adapt: copy the ladder verbatim; each missing rung is a documented deadlock class (#213).
- **Staleness TTLs on every persistent artifact** (2 h mode state, 30 min running subagents, 60 s tool errors, 24 h tombstones, 30 s cancel signals): crash-abandoned state self-expires instead of haunting new sessions. Adapt: pick TTLs per artifact, always compare against the newest of several timestamps.
- **Advisory throttling keyed by message content** with fail-open IO and `OMC_QUIET`-style verbosity ladder: repetition control without ever silencing safety output. Adapt: per-session JSON with `last_emitted_at_ms`, prune > max(2×cooldown, 1 h).
- **Session-scoped state paths with sanitized ids** (`/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,255}$/`, `state/sessions/<sid>/`, ownership scan fallback, legacy fallback): concurrent sessions on one repo never fight over mode files. Adapt: same allowlist regex; refuse unsanitizable ids rather than falling back to shared files.
- **Never inject context on SubagentStop**: it lands in the finishing subagent, not the parent (#3209). Adapt: subagent-terminal hooks may only write state; surface findings on the next parent-side event.
- **Deterministic drift guards on Stop** (prose-question-instead-of-tool, completion-claim vs. TODO/stub diff scan): cheap, regex-only enforcement of workflow discipline with structural false-positive defenses (strip string/regex literals, scan comments only). Adapt: tune the completion-claim and blocker regexes to each harness's deliverable vocabulary.

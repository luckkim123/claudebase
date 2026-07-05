# Delegation & Task-call Enforcement Lane

Every tool call in an OMC session passes through one PreToolUse gate — `scripts/pre-tool-enforcer.mjs`, a ~1500-line standalone Node script registered in `hooks/hooks.json` with a 3-second timeout. For `Task`/`Agent` calls this gate is load-bearing: it normalizes tier aliases to subagent-safe model IDs, injects a per-agent model via `updatedInput`, denies model params that would 400 on non-Claude providers, rewrites team spawns for Claude Code 2.1.178+, and blocks agent spawning on context exhaustion. A parallel TypeScript layer (`delegation-enforcer.ts`, `delegation-routing/resolver.ts`, `delegation-categories/`) implements the same model-resolution and routing algebra as a reusable library, but — a surprising finding — is almost entirely dormant at runtime: production reimplements the logic inline in `.mjs`, and only `normalizeToCcAlias` is imported by a live caller. This section maps both the active gate and the dormant library, and flags where the territory brief's premise (bridge `processPreToolUse`, orchestrator guard, prompt-prerequisite unblock) is in fact test-only code.

## Wiring: what actually runs

```
tool call
   │
   ▼
hooks/hooks.json  PreToolUse matcher "*"  (timeout 3s)
   │   node run.cjs scripts/pre-tool-enforcer.mjs
   ▼
pre-tool-enforcer.mjs  main()                        ← THE production gate
   ├─ kill switches: DISABLE_OMC=1 | OMC_SKIP_HOOKS contains "pre-tool-use"
   ├─ Skill activation (skill-active-state.json)
   ├─ evaluateUltragoalPreToolEnforcement  → deny
   ├─ [Task|Agent] force-inherit model routing → deny | fall-through
   ├─ [Task|Agent] non-forceInherit per-agent model → updatedInput
   ├─ evaluateForceAgentDelegation (opt-in)         → deny
   ├─ evaluateAgentHeavyPreflight (context %)       → deny
   ├─ generateSlopWarning / generateAgentSpawnMessage (TEAM ROUTING)
   └─ emit {continue:true, hookSpecificOutput:{...updatedInput | additionalContext}}
```

The bridge function `processPreToolUse` (`src/hooks/bridge.ts:2312`) — which the territory brief names as an entry point — is explicitly **DEAD CODE in production** per its own comment (`bridge.ts:2402`): "Production PreToolUse is wired in hooks/hooks.json to scripts/pre-tool-enforcer.mjs (NOT this bridge). This block is reachable only via processHook('pre-tool-use', ...) which is called from tests." Everything reached only through the bridge — the orchestrator delegate-not-implement guard (`processOrchestratorPreTool`), the team-worker Task/Skill/Bash block, the prompt-prerequisite deny/unblock, and a second forceInherit model-deny — never fires for a real tool call. It exists to hold regression tests and to keep message wording aligned with the enforcer.

## Model injection and tier resolution (active)

The enforcer inlines `src/config/models.ts` predicates (comment `pre-tool-enforcer.mjs:23`) to avoid a `dist/` import. The core classifier is `isSubagentSafeModelId(id)` = `isProviderSpecificModelId(id) && !hasExtendedContextSuffix(id)` — a subagent-safe ID is a full provider path (`global.anthropic.claude-*`, a Bedrock ARN, or `vertex_ai/…`) with **no** `[1m]`/`[200k]` context-window suffix (regex `/\[\d+[mk]\]$/i`, line 32). The `[1m]` suffix is the crux of the "deadlock" this gate prevents: sub-agents cannot inherit an extended-context session model, and the runtime strips `[1m]` to a bare Anthropic ID that Bedrock rejects with 400.

Tier aliases (`sonnet`/`opus`/`haiku`/`fable`, `TIER_ALIASES` line 84) resolve through `resolveTierAliasToSafeModel` (line 102) over an ordered env chain:

| Tier | Env resolution order (`TIER_TO_DEFAULT_ENV_KEYS`, line 96) |
|:---|:---|
| any | `OMC_SUBAGENT_MODEL` (global override, position 0, wins for all tiers) |
| haiku | → `CLAUDE_CODE_BEDROCK_HAIKU_MODEL` → `ANTHROPIC_DEFAULT_HAIKU_MODEL` |
| sonnet | → `CLAUDE_CODE_BEDROCK_SONNET_MODEL` → `ANTHROPIC_DEFAULT_SONNET_MODEL` |
| opus | → `CLAUDE_CODE_BEDROCK_OPUS_MODEL` → `ANTHROPIC_DEFAULT_OPUS_MODEL` |
| fable | → `CLAUDE_CODE_BEDROCK_FABLE_MODEL` → `ANTHROPIC_DEFAULT_FABLE_MODEL` |

Validation is variable-source-aware (line 111-114): CC-native vars (`ANTHROPIC_DEFAULT_*`, `CLAUDE_CODE_BEDROCK_*`) validate with the looser `isProviderSpecificModelId` because CC's own resolver handles `[1m]` for them; OMC-internal vars validate with the stricter `isSubagentSafeModelId`. `OMC_MODEL_*` is deliberately excluded from the chain (comment line 92): CC does not read those when routing tier aliases, so accepting them as proof would let the hook pass while CC still fails to route — reintroducing the deadlock.

### The force-inherit deny/inject decision tree (`Task`/`Agent`, lines 1290-1396)

`isForceInheritEnabled()` is true when `OMC_ROUTING_FORCE_INHERIT=true` or config `routing.forceInherit === true`. The config loader auto-enables `forceInherit` for non-standard providers (`loader.ts:706`, gated by `shouldAutoForceInherit()`/`isNonClaudeProvider()` in `models.ts:359`: Bedrock, Vertex, non-Claude model ID, or custom `ANTHROPIC_BASE_URL`).

```
Task/Agent call, forceInherit ON:
  model param present?
    ├─ tier alias AND resolveTierAliasToSafeModel(tier) ≠ ""  → ALLOW (fall through)
    ├─ isSubagentSafeModelId(model)                            → ALLOW (full provider ID)
    └─ else  → DENY [MODEL ROUTING] "set ANTHROPIC_DEFAULT_<TIER>_MODEL / OMC_SUBAGENT_MODEL"
  no model param, session model has [1m] suffix?
    └─ DENY [MODEL ROUTING] "pass model=<tier alias>; runtime strips [1m] → invalid on Bedrock"
  no model param, subagent_type set, agent-def model is bare Anthropic ID + safe routing exists?
    └─ DENY [MODEL ROUTING] "add model=<tier>; agent-def model invalid for Bedrock"  (line 1365)
  else → ALLOW (clean inherit)
```

The agent-definition check (line 1357) reads the `model:` field from the target agent's YAML frontmatter (`readAgentDefinitionModel`, line 132 — path-traversal guarded by `/^[a-zA-Z0-9_-]+$/`, frontmatter-scoped so body `model:` lines don't false-match). It only denies when a safe tier-alias escape hatch exists (`hasSafeRouting`), so Claude is never stranded in a retry loop with no viable path. The deny message is precise and actionable, e.g. for the `[1m]` branch (line 1347): `[MODEL ROUTING] Your session model "<id>" has a context-window suffix ([1m]) that sub-agents cannot inherit — the runtime strips it to a bare Anthropic model ID which is invalid on Bedrock. Pass model="<tier>" explicitly …`. The reason text is derived from the tier actually in play (`normalizeToCcAlias(sessionModel) || 'sonnet'`), and the guidance switches on whether a routing target already resolves (`resolvedSafe`), so the message either says "resolves cleanly" or tells the user which `ANTHROPIC_DEFAULT_<TIER>_MODEL` to set. `normalizeToCcAlias` (line 119, inlined) folds any bare Anthropic ID to its CC alias by substring: `opus`/`sonnet`/`haiku`/`fable` → tier, else null.

When `forceInherit` is **off**, the else-branch (line 1382) does the opposite of deny — it *injects*: `resolveConfiguredAgentModel(subagent_type, cwd)` reads `agents.<name>.model` from the user/project JSONC config (`scripts/lib/agent-model-config.mjs`, mirroring `loadConfig`'s merge order and `AGENT_CONFIG_KEY_MAP`), and if set, sets `updatedToolInput = {...toolInput, model: normalizedModel}`. This is emitted as `hookSpecificOutput.updatedInput` (line 1481-1508) — the mechanism that makes a per-agent config override actually reach the spawned subagent (issue #3242), even when the advisory message is empty or throttled. This is the ONLY place OMC mutates a tool call's input; every other branch only denies or annotates.

## `main()` lifecycle and non-delegation side effects (active)

Beyond the delegation gate, `main()` (line 1215) does session-state bookkeeping that the enforcer piggy-backs onto the same PreToolUse hook. It resolves the `.omc` state root once via `resolveOmcStateRoot(directory)` (honoring `OMC_STATE_DIR`, issue #2518) and threads `stateDir` to every helper. On a `Skill` call it writes `skill-active-state.json` (`writeSkillActiveState`, line 1091) so the persistent-mode Stop hook won't terminate mid-skill; the protection tier (`none`/`light`/`medium`/`heavy` → `0`/`3`/`5`/`10` reinforcements, `SKILL_PROTECTION_CONFIGS` line 1012) is looked up per skill, and only `oh-my-claudecode:`-prefixed skills get protection (issue #1581). A nesting guard refuses to overwrite a different active skill's state (a documented TOCTOU race that is safe because CC sessions are single-threaded). Built-in task-list tools (`TaskCreate`/`TaskUpdate`/`TaskList`/`TaskGet`/`TaskOutput`/`TaskStop`, `BUILT_IN_TASK_LIST_TOOL_NAMES` line 419) short-circuit to `{continue:true, suppressOutput:true}`. `AskUserQuestion` fires a fire-and-forget notification before it blocks for input (issue #597).

Verbosity is governed by `OMC_QUIET` (`getQuietLevel`, line 428): level ≥1 mutes advisory messages for `Bash`/`Edit`/`Write`/`Read`/`Grep`/`Glob`; level ≥2 additionally mutes `TodoWrite` and agent-spawn labels. The `[SLOP WARNING]` path (`generateSlopWarning`, line 293) scans tool input for fallback/workaround language on slop-risk tools and appends a warning — an advisory, never a deny, and it exempts self-referential and documentation contexts.

## Blocking evaluators (active)

| Evaluator | Fires on | Trigger | Env / config surface | Failure mode |
|:---|:---|:---|:---|:---|
| `evaluateUltragoalPreToolEnforcement` (line 775) | all tools | active ultragoal state + Claude `/goal` objective mismatch | bypass `ALLOW_ULTRAGOAL_WITHOUT_GOAL=1`; bootstrap tools (cancel, ultragoal CLI) exempt | returns null on stale/terminal state → allow |
| force-inherit model routing (line 1290) | Task/Agent | invalid `model` for non-Claude provider | `OMC_ROUTING_FORCE_INHERIT`, `OMC_SUBAGENT_MODEL`, `ANTHROPIC_DEFAULT_*`, `CLAUDE_CODE_BEDROCK_*` | fall-through allow if safe ID |
| `evaluateForceAgentDelegation` (`force-agent-delegation-preflight.mjs`) | Read/Edit/Write/Grep/Glob (rule-defined) | N raw tool calls in a sliding window → force delegation to an Agent | opt-in `.omc/config.json` `routing.forceDelegation.{enforce,rules}`, per-rule `bypassEnv=1` | state IO fails → window resets, allow (fail-open) |
| `evaluateAgentHeavyPreflight` (`pre-tool-enforcer-preflight.mjs`) | Task/TaskCreate/TaskUpdate | estimated context ≥ threshold | `OMC_AGENT_PREFLIGHT_CONTEXT_THRESHOLD` (default 72, clamped 1-100) | transcript unreadable → 0% → allow |

`evaluateForceAgentDelegation` persists a 1-hour sliding window of tool events to `<stateDir>/force-agent-delegation-events.json`; each PreToolUse is a fresh Node process, so state on disk is the only counter. Rules match tool names as anchored regex (`^(?:pattern)$`) and deny with a configurable `denyMessage`. `evaluateAgentHeavyPreflight` estimates context by reading the last 4 KB of the transcript and parsing the last `"context_window"` and `"input_tokens"` values (`estimateContextPercent`, line 12) — a cheap tail-read, not a full parse. Its recovery advice tells Claude to pause fan-out, run `/compact`, and if that fails resume from `.omc/state` + `.omc/notepad.md`.

Deny output shape is uniform: `{continue:true, hookSpecificOutput:{hookEventName:'PreToolUse', permissionDecision:'deny', permissionDecisionReason:<msg>}}`. Note `continue` stays `true` — the *tool* is denied via `permissionDecision`, but the hook itself never aborts the turn. The whole `main()` is wrapped in try/catch that emits `{continue:true, suppressOutput:true}` on any error (line 1511) — the gate is strictly **fail-open**: an enforcer bug can never wedge a session.

## Team spawn rewrite (active advisory)

`generateAgentSpawnMessage` (line 947) detects an active team via `getActiveTeamState` (session-scoped `team-state.json`, falling back to canonical `.omc/state/team/<name>/manifest.json` + `phase-state.json`). When a team is active and the spawn has no `name`, it emits `[TEAM ROUTING REQUIRED]` (line 967): Claude Code 2.1.178+ removed `TeamCreate`/`TeamDelete`, so teammates must be spawned directly as `Agent/Task name="worker-N"` into the session's implicit native agent team, and `team_name` is "ignored legacy metadata." This is an advisory `additionalContext` string, not a deny — it nudges the spawn shape rather than blocking it. Advisory messages are content-hash throttled (`shouldEmitAdvisoryMessage`, 5-min default cooldown via `OMC_PRE_TOOL_ADVISORY_COOLDOWN_MS`) so a repeated nudge is suppressed; throttling also fails open (line 399).

## The parallel TypeScript library (mostly dormant)

The brief's other named entry points are a well-factored library that production does not call on the hot path:

| Module | Public API | Live runtime caller? |
|:---|:---|:---|
| `delegation-enforcer.ts` | `enforceModel`, `processPreToolUse`, `isAgentCall`, `normalizeToCcAlias`, `getModelForAgent` | Only `normalizeToCcAlias`, imported by `team/model-contract.ts:4` |
| `delegation-routing/resolver.ts` | `resolveDelegation`, `parseFallbackChain`, `isDeprecatedMcpProvider` | Barrel-exported (`features/delegation-routing/index.ts`); **no** live src caller |
| `delegation-categories/index.ts` | `resolveCategory`, `getCategoryForTask`, `enhancePromptWithCategory`, … | Barrel-exported (`features/index.ts`); **no** live src caller |

`enforceModel` (line 151) is the TS mirror of the enforcer's model logic: forceInherit → strip `model`; explicit model → `normalizeToCcAlias`; else inject the agent-def default, applying `routing.modelAliases` (issue #1211) and refusing to inject `'inherit'`. It canonicalizes `subagent_type` through `DEPRECATED_ROLE_ALIASES` (`researcher→document-specialist`, `reviewer→code-reviewer`, `build-fixer→debugger`, etc.). It throws `Unknown agent type` / `No default model` on bad input — a stricter contract than the fail-open `.mjs`. Its config is memoized by an env-key cache (`CONFIG_ENV_KEYS`, line 33) rebuilt whenever any provider-detection env var changes.

`resolveDelegation` (resolver.ts:37) is a 4-priority router (explicit tool → configured route → role-category default → defaultProvider). Its notable behavior: `codex`/`gemini` are `DEPRECATED_MCP_PROVIDERS` — any route naming them logs `DEPRECATED_MCP_PROVIDER_WARNING` ("Use /team to coordinate CLI workers instead") and is rewritten to an executable `claude`/`Task` target, preserving the external model name only as diagnostic `reason` text. `ROLE_CATEGORY_DEFAULTS` (`types.ts:31`) maps 18 roles to canonical subagents; note `git-master` and `code-simplifier` both default to `executor`.

`delegation-categories` is a semantic layer over `ComplexityTier`: seven categories each carry a `tier`/`temperature`/`thinkingBudget`/`promptAppend`, e.g. `ultrabrain` = `{HIGH, 0.3, 'max', …}`, `artistry` = `{MEDIUM, 0.9, 'medium', …}`. `detectCategoryFromPrompt` requires ≥2 keyword matches for confidence (line 219); `THINKING_BUDGET_TOKENS` maps `low/medium/high/max` → `1000/5000/10000/32000`. This is a complete, tested subsystem with no production consumer wired in — a designer should treat it as reference material, not an active behavior.

## The orchestrator delegate-not-implement guard (test-only in this build)

`src/hooks/omc-orchestrator/index.ts` (`processOrchestratorPreTool`, line 373) is a genuine guard: on `Write`/`Edit` to a path **outside** the allowlist (`ALLOWED_PATH_PATTERNS`: `.omc/`, `.claude/`, `CLAUDE.md`, `AGENTS.md`, `constants.ts:16`), at `enforcementLevel` `strict` it returns `{continue:false, reason:'DELEGATION_REQUIRED'}` with the `ORCHESTRATOR_DELEGATION_REQUIRED` template ("STOP. YOU ARE VIOLATING ORCHESTRATOR PROTOCOL"); at `warn` (the default) it lets the edit through but appends a delegation reminder plus a file-extension-based agent suggestion (`suggestAgentForFile`). Level is read from `.omc/config.json` `delegationEnforcementLevel`/`enforcementLevel` (30 s cache). Its post-tool sibling parses `<remember>`/`<remember priority>` tags from subagent output into notepad memory and injects the "SUBAGENTS LIE — verify everything" reminder.

The catch: this hook is invoked **only** from `bridge.ts:2350`, inside the dead-code `processPreToolUse`. Since production routes PreToolUse to `pre-tool-enforcer.mjs` (which never imports the orchestrator hook), the direct-work guard does not fire in this build for a real edit. It is reachable through `processHook('pre-tool-use', …)` in Vitest only. A sibling designer wanting an orchestrator direct-work guard should treat this as a reference implementation whose wiring was superseded by the `.mjs` enforcer, not as live behavior.

## Corrections to the territory premise

Three named behaviors are, in this build, bridge-only (test-reachable) rather than production-active: (1) the orchestrator delegate-not-implement guard; (2) the "unblock after prompt-prerequisites" flow — `readPromptPrerequisiteState`/`recordPromptPrerequisiteProgress` and the "[PROMPT PREREQUISITES COMPLETE]" message live in `bridge.ts:2374-2400`, and `grep` finds no prompt-prerequisite logic in `pre-tool-enforcer.mjs`; (3) a second forceInherit `model`-param deny in the bridge (line ~2416). The production forceInherit routing (richer: tier resolution, `[1m]` detection, agent-def check) is the `.mjs` implementation. The active gate is the `.mjs` script plus its two `lib/*preflight.mjs` evaluators; the TS modules are a parallel library kept in sync by tests.

## Patterns for sibling harnesses

- **Single fail-open PreToolUse gate as a standalone script.** One `.mjs` on the `"*"` matcher, whole body in try/catch emitting `{continue:true}` on error, so an enforcement bug can never wedge a session. Re-implement per harness; never import OMC.
- **Deny-with-feedback, not abort.** Block a specific tool via `hookSpecificOutput.permissionDecision:'deny'` + a `permissionDecisionReason` that names the exact fix, while keeping `continue:true`. The agent retries corrected instead of the turn dying.
- **`updatedInput` for config-driven tool mutation.** The only sanctioned way to make a per-agent/model config override reach a spawned subagent is rewriting the tool input in the hook; emit it even when the advisory message is empty so injection is never dropped.
- **Provider-aware model normalization with an escape hatch.** Classify IDs (`isSubagentSafeModelId`) and only deny when a resolvable tier-alias path exists, so the agent is never stranded in a retry loop. Adapt the env-chain to your provider set.
- **Sliding-window rate-based delegation nudges via on-disk state.** Each hook run is a fresh process; persist a pruned event window to a JSON file to count "N raw Reads in 2 min" and force delegation. Keep it opt-in and fail-open.
- **Cheap context-exhaustion preflight by transcript tail-read.** Read the last few KB of the transcript, parse the last `input_tokens`/`context_window`, and gate agent fan-out at a configurable percent — no full parse, no token counting API.
- **Content-hash advisory throttling.** Hash each advisory message and suppress repeats within a cooldown window (per-session state file) so reminders don't spam the context.
- **Keep a TS library mirror of hook logic, sync by tests.** OMC keeps a typed `enforceModel`/`resolveDelegation` library beside the `.mjs` and pins wording alignment via regression tests. Useful, but audit which copy is actually wired — dormant mirrors accrue as maintenance cost.

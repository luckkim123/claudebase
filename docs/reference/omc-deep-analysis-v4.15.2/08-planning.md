# Planning Lane: plan, ralplan, deep-interview, deep-dive

OMC's planning lane converts vague user intent into approval-gated, execution-ready artifacts before any heavy orchestration mode (ralph/autopilot/team/ultrawork) is allowed to mutate code. It is built from four bundled prompt-program skills (`skills/plan`, `skills/ralplan`, `skills/deep-interview`, `skills/deep-dive` — each a SKILL.md executed by the main Claude agent, not compiled code), plus a thin TypeScript support layer: a runtime skill-template renderer that injects the configured ambiguity threshold (`src/features/builtin-skills/skills.ts`), a planning-artifact reader that gates execution launches on PRD/test-spec completeness (`src/planning/artifacts.ts`, `src/planning/artifact-names.ts`), a prompt-time "ralplan-first" vagueness gate (`src/hooks/keyword-detector/index.ts`), and a Stop-hook enforcement loop that keeps consensus planning alive until it reaches a terminal `pending approval` phase (`src/hooks/persistent-mode/index.ts`). All four skills are ACTIVE (loaded by the builtin-skills loader; `commands/deep-dive.md` additionally provides a lightweight slash dispatcher). One module is partially vestigial: `src/team/followup-planner.ts` exports `isApprovedExecutionFollowupShortcut`/`resolveApprovedTeamFollowupContext` with no importer outside its own tests — the live consumer of launch hints is the `omc team` CLI, which calls `readApprovedExecutionLaunchHintOutcome` directly (src/cli/team.ts:15,1275).

## Lane inventory and wiring

| Skill | Frontmatter identity | Modes / stages | Handoff artifact | Approval policy |
|---|---|---|---|---|
| `skills/plan` | `name: omc-plan`, `pipeline: [deep-interview]`, `handoff-policy: approval-required`, `handoff: .omc/plans/ralplan-*.md`, `level: 4` (skills/plan/SKILL.md:2-8) | Interview, Direct (`--direct`), Consensus (`--consensus`), Review (`--review`) | plan in `.omc/plans/`, drafts in `.omc/drafts/` (skills/plan/SKILL.md:151) | `pending approval` unless explicit opt-in (skills/plan/SKILL.md:44) |
| `skills/ralplan` | `name: ralplan`, `level: 4` | Alias for `/oh-my-claudecode:plan --consensus` (skills/ralplan/SKILL.md:10) | same as plan | same + documents the pre-execution gate |
| `skills/deep-interview` | `name: deep-interview`, `pipeline: [deep-interview, plan]`, `handoff: .omc/specs/deep-interview-{slug}.md`, `level: 3` (skills/deep-interview/SKILL.md:5-8) | Phase 0 threshold → Phase 1 init → Round 0 topology → Phase 2 loop → Phase 3 challenge agents → Phase 4 spec → Phase 5 bridge | spec in `.omc/specs/` | execution bridge is a separate `AskUserQuestion` gate (SKILL.md:491-522) |
| `skills/deep-dive` | `name: deep-dive`, `pipeline: [deep-dive, plan, autopilot]`, `next-skill: plan`, `next-skill-args: --consensus --direct`, `handoff: .omc/specs/deep-dive-{slug}.md` (skills/deep-dive/SKILL.md:10-13) | trace (3 lanes) → interview (reference-not-copy of deep-interview Phases 2-4) → bridge | trace + spec in `.omc/specs/` | Phase 5 bridge; optional workflow pre-flight (issue/branch/worktree) |

Frontmatter `pipeline`/`next-skill`/`handoff`/`handoff-policy` is not decoration: `parseSkillPipelineMetadata` and `renderSkillPipelineGuidance` (src/utils/skill-pipeline.ts:42-141) append a generated "## Skill Pipeline" section to every rendered skill body; when `handoff-policy: approval-required` it emits "stop with the handoff artifact marked `pending approval`. Do not invoke the next skill until the user gives explicit approval" (skill-pipeline.ts:117).

## Control flow

```
user prompt
   |-- UserPromptSubmit (bridge.ts processKeywordDetector)
   |     |- explicit /ralplan|/deep-interview|... slash  -> seed workflow slot + mode state
   |     |     ("/ralplan" also returns "[RALPLAN INIT] ... armed ... awaiting confirmation")
   |     |- keyword regexes (KEYWORD_PATTERNS)           -> detected keyword list
   |     '- applyRalplanGate(): execution kw + vague     -> replace ralph/autopilot/team/
   |            prompt => "[RALPLAN GATE] Redirecting"      ultrawork with 'ralplan'
   |
   |-- Skill tool fires (PreToolUse): ralplan OR plan/omc-plan with "--consensus" in args
   |        => activateRalplanState (bridge.ts:648-676, 2532-2534)
   |
   |-- consensus loop runs in main conversation:
   |     Planner (main agent) -> Architect Task -> Critic Task -> revise (max 5 iters)
   |     Stop hook (checkRalplan) blocks premature stops with <ralplan-continuation>
   |
   |-- terminal: plan marked `pending approval` (phase in RALPLAN_TERMINAL_PHASES => stop allowed)
   |
   '-- approval -> Skill("oh-my-claudecode:team"|"ralph"|"autopilot") with plan/spec path
         (PostToolUse on the planning Skill completion: deactivateRalplanState, bridge.ts:2824-2825)
```

## Plan skill: modes and quality bars

Mode selection (skills/plan/SKILL.md:53-58): Interview is default for broad requests (classification: "vague verbs, no specific files, touches 3+ areas", SKILL.md:62); `--direct` or a detailed request skips it; `--consensus`/"ralplan" runs the consensus loop; `--review` runs Critic-only evaluation returning "APPROVED, REVISE (with specific feedback), or REJECT (replanning required)" (SKILL.md:136). Interview discipline: one question per turn, `explore` agent (Haiku, 30s timeout) answers codebase-fact questions before the user is asked (SKILL.md:158), question types are classified into Codebase Fact / User Preference / Scope Decision / Requirement (SKILL.md:271-276). Quality gates are numeric: "80%+ claims cite file/line, 90%+ criteria are testable" (SKILL.md:41), review criteria table repeats Clarity 80% / Testability 90% / "All file refs exist" / "No vague terms" (SKILL.md:280-285). The old `/planner`, `/ralplan`, `/review` skills were merged into `/plan` (SKILL.md:287-289).

## Ralplan consensus: arbiters and disagreement resolution

The arbiters are three roles: **Planner** (the main planning agent itself), **Architect** (`Task(subagent_type="oh-my-claudecode:architect")`), and **Critic** (`Task(subagent_type="oh-my-claudecode:critic")`) (skills/plan/SKILL.md:105-106). Sequencing is a hard rule: "Consensus mode agent calls MUST be sequential, never parallel. Always await the Architect Task result before issuing the Critic Task" (SKILL.md:162).

- **RALPLAN-DR structured deliberation**: before any review, the Planner must emit Principles (3-5), Decision Drivers (top 3), and >=2 Viable Options with bounded pros/cons, or an explicit invalidation rationale if only one option survives (SKILL.md:94-99). Two depths exist: **short** (default) and **deliberate** (`--deliberate`, or auto-enabled on high-risk signals: "auth/security, data migration, destructive/irreversible changes, production incident, compliance/PII, public API breakage", SKILL.md:43). Deliberate adds a pre-mortem (3 failure scenarios) and an expanded test plan (unit/integration/e2e/observability).
- **Architect obligations**: strongest steelman antithesis against the favored option, at least one real tradeoff tension, synthesis when possible; flags principle violations in deliberate mode (SKILL.md:105).
- **Critic obligations**: verify principle-option consistency, fair alternatives, risk mitigation clarity, testable acceptance criteria, concrete verification; "explicitly reject shallow alternatives, driver contradictions, vague risks, or weak verification" (SKILL.md:106). Verdicts are `APPROVE`/`ITERATE`/`REJECT`; any non-APPROVE reruns the full Planner→Architect→Critic loop (skills/ralplan/SKILL.md:54-59).
- **Disagreement resolution**: closed re-review loop, max 5 iterations; on exhaustion "present the best version to user via AskUserQuestion with note that expert consensus was not reached" (SKILL.md:107-113). Approved improvements are merged into the plan file with a changelog section, and the final output must contain an **ADR** (Decision, Drivers, Alternatives considered, Why chosen, Consequences, Follow-ups) (SKILL.md:114-118).
- **Provider substitution**: `--architect codex` / `--critic codex` replace one pass with `omc ask codex --agent-prompt architect|critic "..."`; unavailable providers degrade to Claude with a brief note (SKILL.md:79-83). The skill loader appends a "## Provider Runtime Availability" section only when the Codex CLI is actually detected (src/features/builtin-skills/runtime-guidance.ts:34-43,73-88).
- **Interactivity is opt-in**: without `--interactive` the whole loop runs unattended and terminates by outputting the plan marked `pending approval` — "Do NOT auto-execute" (SKILL.md:125). With `--interactive`, `AskUserQuestion` gates the draft (Proceed/Request changes/Skip review) and the final approval (Approve via team (Recommended) / Approve via ralph / Compact then return / Request changes / Reject) (SKILL.md:100-130).

## Ambiguity scoring: dimensions, weights, thresholds

The math is specified in the SKILL.md and executed by the model ("use opus model, temperature 0.1 for consistency", skills/deep-interview/SKILL.md:271); the only part computed in TypeScript is threshold resolution.

| Dimension | Greenfield weight | Brownfield weight |
|---|---|---|
| Goal Clarity | 0.40 | 0.35 |
| Constraint Clarity | 0.30 | 0.25 |
| Success Criteria | 0.30 | 0.25 |
| Context Clarity | n/a | 0.15 |

`ambiguity = 1 - Σ(score_i × weight_i)`, i.e. greenfield `1 - (goal×0.40 + constraints×0.30 + criteria×0.30)`, brownfield `1 - (goal×0.35 + constraints×0.25 + criteria×0.25 + context×0.15)` (SKILL.md:318-319; weights table SKILL.md:773-776). The gate is `ambiguity ≤ threshold`. **Phase 0** is a blocking prerequisite: resolve `omc.deepInterview.ambiguityThreshold` from `./.claude/settings.json` (project) over `~/.claude/settings.json` (user) over default `0.2`, and emit `Deep Interview threshold: <percent> (source: <source>)` as the first user-visible line (SKILL.md:72-92). The shipped SKILL.md literally contains `<resolvedThreshold>` / `<resolvedThresholdPercent>` / `<resolvedThresholdSource>` placeholders; `applyDeepInterviewRuntimeSettings` substitutes them at skill-load time for `deep-interview` and `deep-dive` only, validating the setting as a finite number in [0,1] (src/features/builtin-skills/skills.ts:78,102-143,184-229). Per-round scoring returns, per dimension, `score`, `justification`, and `gap` (if score < 0.9), plus `weakest_component_id`, `weakest_dimension`, and a one-sentence rationale (SKILL.md:292-301).

Supporting math and gates:

- **Round 0 topology gate** (runs once, before any scoring): enumerate 1-6 top-level components, confirm with one question, lock into state with per-component `clarity_scores` — designed so "depth-first clarity on one component cannot hide ambiguity in siblings"; overall dimension scores become "the minimum or coverage-weighted weakest score across active components"; deferred components are excluded from the math but must stay in the spec (SKILL.md:159-220,284).
- **Ontology stability**: each round extracts entities (name/type/fields/relationships); `stability_ratio = (stable + changed) / total_entities`, where "changed" = same type AND >50% field overlap (a rename counts as convergence, not churn); round 1 and zero-entity rounds are `N/A` (SKILL.md:321-336).
- **Round caps**: early exit allowed from round 3+, soft warning at round 10, hard cap at round 20 (SKILL.md:366-370). **Stall rule**: same score ±0.05 for 3 rounds → activate Ontologist mode; all dimensions ≥0.9 → skip straight to spec (SKILL.md:668-670).
- **Challenge agents** (prompt injections, not spawned agents — SKILL.md:559): Contrarian at round 4+ ("What if the opposite were true?"), Simplifier at round 6+ ("What's the simplest version?"), Ontologist at round 8+ only if ambiguity > 0.3 ("What IS this, really?"); each used exactly once, tracked in `challenge_modes_used` (SKILL.md:374-388,782-788).

Interview state lives in `state_write(mode="deep-interview")` with fields `interview_id`, `type`, `initial_idea`, `rounds`, `current_ambiguity` (starts 1.0), `threshold`, `threshold_source`, `codebase_context`, `topology{status,components,deferrals,last_targeted_component_id}`, `challenge_modes_used`, `ontology_snapshots` (SKILL.md:118-145); the file is `deep-interview-state.json` (src/lib/mode-names.ts:63) and deep-interview is a first-class mode in `MODE_CONFIGS` (src/hooks/mode-registry/index.ts:87-91). The final spec records the threshold AND its source, a Topology table, an Ontology table, an Ontology Convergence table, and the full Q&A transcript, with `Status: PASSED | BELOW_THRESHOLD_EARLY_EXIT` (SKILL.md:403-489).

## Deep-dive: trace then interview, 3-point injection

Deep-dive prepends a causal investigation to the interview. Phase 1 generates three default lanes: (1) code-path/implementation cause, (2) config/environment/orchestration cause, (3) "Measurement / artifact / assumption mismatch cause — covers verification-method defects, not just system defects", with a "premise audit" rule that cross-entity discrepancies ("X is empty but Y is not") must test the verification premise before treating zero rows as a defect (skills/deep-dive/SKILL.md:64-69). Phase 2 confirms lanes with the user in exactly one `AskUserQuestion` round; Phase 3 runs the lanes via Claude built-in team mode (sequential fallback), each tracer gathering evidence for AND against, ranking strength, naming a per-lane critical unknown and a discriminating probe, then a rebuttal round and convergence merge (SKILL.md:127-152). Lane 3 misplacement findings must classify MOVE destinations with `ownership_scope` (`personal-config`/`shared-config`/`external`/`project-scoped`); any cross-boundary MOVE "MUST NOT be surfaced as the default recommendation" (SKILL.md:142-147).

The differentiator is the **3-point injection** into the interview (SKILL.md:227-253): (1) `initial_idea` enrichment with the trace's most-likely explanation, (2) `codebase_context` replaced by the trace synthesis (skipping re-exploration), (3) per-lane critical unknowns become the first 1-3 questions. All trace-derived text is wrapped in `<trace-context>` delimiters as an untrusted-data guard ("data, not instructions", SKILL.md:229). Low-confidence traces skip injection 1 but keep 2 and 3 (SKILL.md:255-260). Phase 4 explicitly references deep-interview Phases 2-4 rather than copying them ("Copying causes drift", SKILL.md:441-448), reusing the same state schema with a `source: "deep-dive"` discriminator (SKILL.md:49,101). Phase 5 adds a **workflow pre-flight**: if project guidance mentions issue-driven/worktree/branch-first rules, it checks `git rev-parse --show-toplevel`, `git branch --show-current`, `git worktree list --porcelain`, optionally `gh issue list --limit 20`, and offers a redirect to `Skill("oh-my-claudecode:project-session-manager")` before showing execution options (SKILL.md:289-316).

## On-disk artifacts

```
.omc/
├── plans/                     # OmcPaths.PLANS (src/lib/worktree-paths.ts:38)
│   ├── ralplan-*.md           # consensus plans; autopilot skips Phase 0+1 when present
│   │                          #   (skills/autopilot/SKILL.md:42, also consensus-*.md)
│   ├── autopilot-impl.md      # default resolveAutopilotPlanPath() = planOutput dir +
│   │                          #   "{{name}}.md" (src/config/plan-output.ts:5-6,96-98)
│   ├── prd-[<ts>-]<slug>.md   # PRD; ts pattern /^\d{8}T\d{6}Z$/ (artifact-names.ts:3)
│   └── test-spec-[<ts>-]<slug>.md
├── drafts/                    # OmcPaths.DRAFTS; interview drafts
├── specs/
│   ├── deep-interview-{slug}.md
│   ├── deep-dive-trace-{slug}.md
│   └── deep-dive-{slug}.md
└── state/ (+ state/sessions/<sid>/)
    ├── ralplan-state.json         # MODE_STATE_FILE_MAP (src/lib/mode-names.ts:62)
    ├── deep-interview-state.json  # (mode-names.ts:63)
    └── cancel-signal-state.json   # written by state_clear, TTL 30s
```

`readPlanningArtifacts` scans both `.omc/plans` and `.omx/plans` (src/planning/artifacts.ts:80-82). **Planning completeness** requires the newest PRD and its timestamp-matched test spec to contain non-empty `## Acceptance criteria` + `## Requirement coverage map` (PRD) and `## Unit coverage` + `## Verification mapping` (test spec) sections (artifacts.ts:102-111). This contract is also stated for non-Claude agents: "Planning is complete only after both `.omc/plans/prd-*.md` and `.omc/plans/test-spec-*.md` exist" (AGENTS.md:185).

**Approved execution launch hints**: a PRD may embed a launch command matching a named-group regex `(?<command>(?:om[cx]\s+team|\$team)(?:\s+ralph)?(?:\s+(?<count>\d+)(?::(?<role>[a-z][a-z0-9-]*))?)?\s+(?<task>"..."|'...')(?<flags>(?:\s+--[\w-]+)*))` or the ralph equivalent (artifacts.ts:195-198); `--linked-ralph` or an inline `ralph` token sets `linkedRalph` (artifacts.ts:227,242-246). `readApprovedExecutionLaunchHintOutcome` returns `absent | ambiguous | incomplete | resolved` (artifacts.ts:41-45); multiple matches without a disambiguating task/command are `ambiguous`, and `requirePlanningComplete` demotes a hint to `incomplete` when the PRD/test-spec pair fails the section check. The live consumer: `omc team start` treats the short follow-ups `team`, `/team`, `team please`, `run team`, `start team` as "launch the approved plan", resolving worker count, agent type, and ralph linkage from the hint, and throws `approved_execution_hint_ambiguous:team` / `approved_execution_hint_incomplete:team` otherwise (src/cli/team.ts:1273-1301).

## Lifecycle: arm, run, stop, cancel, resume

**Arm.** Three activation paths write `ralplan-state.json`: (1) explicit `/ralplan` (or `/omc:ralplan`, `/oh-my-claudecode:ralplan`) at prompt-submit seeds the workflow slot and writes `{active:true, current_phase:"ralplan", awaiting_confirmation:true, ...}`, returning the `[RALPLAN INIT]` context so "the stop hook will not block this initialization path" (src/hooks/bridge.ts:1252-1268,1477-1503); (2) the bare `ralplan` keyword — which requires *explicit invocation context* via `findActionableRalplanMatch` (informational mentions are ignored, keyword-detector/index.ts:734-762) — seeds startup state idempotently (bridge.ts:718-729); (3) PreToolUse on the Skill tool, where `isConsensusPlanningSkillInvocation` returns true for skill `ralplan` or for `plan`/`omc-plan` whose args contain `--consensus` (bridge.ts:648-662,2532-2534).

**Gate.** `applyRalplanGate` (keyword-detector/index.ts:1050-1086) fires when a keyword in `EXECUTION_GATE_KEYWORDS = {ralph, autopilot, team, ultrawork}` (index.ts:964-969) appears in a prompt that `isUnderspecifiedForExecution` deems vague: no bypass prefix (`force:` or `!`, index.ts:974), none of 14 `WELL_SPECIFIED_SIGNALS` regexes (file extensions, `src/...` paths, camelCase/PascalCase/snake_case symbols, `#123` issue refs, numbered steps, "acceptance criteria", error/type names, 20+ char code fences, PR/commit refs, test-runner commands — index.ts:980-1012), and <=15 effective words after stripping mode keywords (index.ts:1033-1039). The gate *rewrites the keyword list*, removing execution keywords and inserting `ralplan`; `cancel` always wins and an already-present `ralplan` suppresses gating. In the bridge it runs BEFORE task-size suppression on the reconstructed full keyword set, and emits `[RALPLAN GATE] Redirecting <kw> → ralplan for scoping.` with anchor-tips (bridge.ts:1537-1558).

**Run (stop enforcement).** `checkRalplan` in the Stop hook (persistent-mode/index.ts:1783-1889) blocks stops while `ralplan-state.json` is `active`, with these guards: session isolation on `session_id`; stale-state suppression only when a freshness timestamp exists ("Session-scoped ralplan state can legitimately omit timestamps in CI", 1798-1801); `awaiting_confirmation` bypass; terminal-phase allowlist `RALPLAN_TERMINAL_PHASES` = completed/complete/failed/cancelled/canceled/aborted/terminated/done/handoff/pending approval (plus `pending-approval`, `pending_approval`, `awaiting approval` variants, `approval-required`, `approval_required`) (index.ts:611-629); orchestrator-idle bypass only when the subagent tracker was updated within `RALPLAN_ACTIVE_AGENT_RECENCY_WINDOW_MS = 5_000` ms — "otherwise fail closed" (1830-1848). The block message is `<ralplan-continuation>` with `[RALPLAN - CONSENSUS PLANNING | REINFORCEMENT n/30]` and an explicit read-only mandate ("do not implement, invoke execution skills, edit source, commit, push, or open PRs") (1873-1882). Circuit breaker: `RALPLAN_STOP_BLOCKER_MAX = 30` reinforcements within `RALPLAN_STOP_BLOCKER_TTL_MS = 45 min`; on exhaustion it self-deactivates the state (`deactivated_reason: 'stop_breaker_exhausted'`) so a later Stop cannot restart a fresh 1/30 cycle (1851-1868).

**Stop/handoff — the state_clear trap.** The MCP `state_clear` tool writes a session cancel signal with `CANCEL_SIGNAL_TTL_MS = 30_000` (src/tools/state-tools.ts:60,534-548) that disables stop-hook enforcement for ALL modes for 30 seconds. The plan skill therefore mandates: on handoff to execution use `state_write(mode="ralplan", active=false, ...)`, and reserve `state_clear` for true terminal exits (rejection, non-interactive output, error) — "Never use `state_clear` before launching an execution mode — its cancel signal disables stop-hook enforcement for 30 seconds" (skills/plan/SKILL.md:85-92,168). Independently, PostToolUse on the completing planning Skill tombstones the workflow slot and calls `deactivateRalplanState`, coercing `current_phase` to `complete` with `deactivated_reason: "skill_completed"` (bridge.ts:678-716,2821-2827).

**Resume.** SessionStart injects `[RALPLAN MODE RESTORED]` for an active state, but advisory-only: "Treat this as prior-session context only... resume ralplan only if the user explicitly asks" (bridge.ts:2044-2050). Deep-interview resumes from `deep-interview-state.json` at the last completed round (skills/deep-interview/SKILL.md:718-720); legacy states without `topology` get `status: "legacy_missing"` and run Round 0 retroactively unless a spec already exists (SKILL.md:216). Deep-dive resumes via `state.source === "deep-dive"` and reads `trace_path`/`spec_path` from state, "not conversation history" (skills/deep-dive/SKILL.md:502-504).

**Protection layers.** All four are wired into skill-state: `deep-interview` and `ralplan` are canonical workflow skills with slots and 24h tombstone TTL (src/hooks/skill-state/index.ts:60-69,53); `plan`/`omc-plan` get `medium` support protection (5 reinforcements, 15 min TTL) and — despite the comment that workflow skills get `'none'` — `deep-interview` is mapped to `heavy` (10 reinforcements, 30 min) in the same table (index.ts:92-134), so it carries both a workflow slot and support-skill protection.

## Handoff to execution modes

Handoff is always `Skill()` invocation with an artifact path, never direct implementation ("The deep-interview agent is a requirements agent, not an execution agent", skills/deep-interview/SKILL.md:522). The canonical 3-stage pipeline gates on three different qualities — "Deep Interview gates on *clarity* ... omc-plan consensus gates on *feasibility* ... Separate approval gates on *consent*" (SKILL.md:538-541). Downstream shortcuts: autopilot skips Phase 0 when given an interview spec, and skips Phases 0+1 when a `.omc/plans/ralplan-*.md` / `consensus-*.md` plan exists (skills/autopilot/SKILL.md:42,219). Inside autopilot's own staged pipeline, planning is itself a stage: `ralplanAdapter` (id `"ralplan"`, completion signal `PIPELINE_RALPLAN_COMPLETE`) renders either a consensus or direct planning prompt and is skipped when `config.planning === false`; the autopilot config type is `planning?: 'ralplan' | 'direct' | false` (src/hooks/autopilot/adapters/ralplan-adapter.ts:20-93, src/hooks/autopilot/types.ts:208). "Just do it"/"skip planning" without a named execution path is defined as *end planning with a pending-approval artifact*, not as consent to execute (skills/plan/SKILL.md:226). The `--autoresearch` flag turns deep-interview into the setup lane for the autoresearch skill, adding mission-clarity and evaluator-clarity as extra hard gates and bridging only to `Skill("oh-my-claudecode:autoresearch")` (skills/deep-interview/SKILL.md:55-64); its artifacts get their own name kind `deep-interview-autoresearch-<slug>.md` (src/planning/artifact-names.ts:56-66).

## Configuration surface

| Key / flag / var | Where read | Effect |
|---|---|---|
| `omc.deepInterview.ambiguityThreshold` | machine-read: project `./.claude/settings.json` > user `~/.claude/settings.json` > default `0.2` (skills.ts:78,125-139) | substituted into deep-interview/deep-dive skill bodies at load time |
| `omc.deepInterview.{maxRounds:20, softWarningRounds:10, minRoundsBeforeExit:3, enableChallengeAgents:true, autoExecuteOnComplete:false, defaultExecutionMode:null, scoringModel:"opus"}` | documented in SKILL.md only (skills/deep-interview/SKILL.md:699-716); not read by TS code | prompt-level knobs |
| `omc.deepDive.{defaultTraceLanes:3, enableTeamMode:true, sequentialFallback:true}` | documented only (skills/deep-dive/SKILL.md:487-500) | prompt-level knobs |
| `planOutput.directory` / `planOutput.filenameTemplate` | `.claude/omc.jsonc` (project) / `~/.config/claude-omc/config.jsonc` (user); defaults `.omc/plans`, `{{name}}.md` (src/config/plan-output.ts:5-6, loader.ts:174-177,215-216) | autopilot plan path; path-traversal-validated |
| `companyContext.tool` / `companyContext.onError` (`warn` default, `silent`, `fail`) | `.claude/omc.jsonc` > `~/.config/claude-omc/config.jsonc` | optional advisory MCP call before ralplan loop / spec crystallization / deep-dive Phase 4 (skills/ralplan/SKILL.md:44; deep-interview SKILL.md:394; deep-dive SKILL.md:223-225) |
| Plan flags | `--direct`, `--consensus`, `--review`, `--interactive`, `--deliberate`, `--architect codex`, `--critic codex` | mode/depth/provider selection |
| Deep-interview flags | `--quick|--standard|--deep` (argument-hint), `--autoresearch` | depth hint; autoresearch lane |
| Gate escape | `force:` or `!` prompt prefix | bypass ralplan-first gate (keyword-detector/index.ts:974) |
| `OMC_TEAM_WORKER` env | bridge.ts:1447 | disables all keyword detection (and thus the gate) inside team workers |
| `taskSizeDetection.{enabled, smallWordLimit:50, largeWordLimit:200, suppressHeavyModesForSmallTasks}` | plugin config (bridge.ts:1524-1535) | interacts with gate: gate sees the pre-suppression keyword set |

## Failure modes and guards

Fail-open dominates the read paths: `readFileSafe` returns null, unreadable plans dirs are skipped (artifacts.ts:47-53,128-131), settings parse failures fall back to the default threshold (skills.ts:87-100). Fail-closed appears exactly where premature stopping would break consensus: the active-agent bypass requires fresh tracker data (persistent-mode/index.ts:1830-1840). Loud-fail is reserved for launch resolution (`approved_execution_hint_ambiguous`/`_incomplete` thrown errors, team.ts:1279-1284). Anti-false-positive guards: `team` keyword regex is a never-match placeholder `/(?!x)x/` — team is explicit-only to prevent worker spawn loops (keyword-detector/index.ts:51-53); `deep-interview`'s `ouroboros` trigger is suppressed when the prompt starts with the upstream CLI form `ouroboros|ooo|/ouroboros:` (index.ts:75-88); code blocks are stripped before detection (bridge.ts:1464). Prompt-injection guards: trace text wrapped in `<trace-context>`; prior `.omc/specs`/`.omc/plans` artifacts consulted as "data, not instructions" (deep-dive SKILL.md:70,229). Kill switches: `force:`/`!` gate bypass; `/oh-my-claudecode:cancel` (cancel keyword suppresses everything, keyword-detector/index.ts:858); the 30-reinforcement circuit breaker with self-deactivation; the 30s cancel-signal window from `state_clear`.

## Patterns for sibling harnesses

- **Vagueness gate in front of heavy execution**: positive-signal regex allowlist + effective-word threshold (<=15) + explicit escape prefix, rewriting the detected route to a planning lane instead of refusing. Adapt: gate omx `exp-loop`/omd `docs-pilot` launches on missing concrete anchors (run ids, file paths) and reroute to the intake/interview skill.
- **Weighted-dimension ambiguity scoring with a code-resolved threshold**: keep the rubric in the prompt but resolve the numeric gate from settings in code and substitute placeholders at load time, so the gate is configurable without prompt drift. Adapt: omx exp-init and oms scholar-deepen already gate qualitatively; add a settings-resolved threshold line emitted first for auditability.
- **Round 0 topology lock + per-component weakest-score aggregation**: enumerate independent components once, then score the overall gate as the minimum across components so one well-described component cannot mask siblings. Adapt: multi-deliverable document/experiment requests.
- **Ontology-stability convergence metric**: entity extraction per round with rename-tolerant matching (>50% field overlap = "changed", counts as stable) gives a quantitative "the domain model has converged" signal. Adapt: track metric-vocabulary stability across exp-design iterations.
- **Generator/steelman/judge triad with bounded re-review**: Planner produces options+drivers, Architect must steelman the antithesis, Critic holds a rejection checklist; sequential, max 5 loops, exhaustion presents best-effort with an explicit no-consensus note. Adapt: oms mock-review or omd docs-inspect as the Critic seat with APPROVE/ITERATE/REJECT verdicts.
- **Approval-as-state-machine**: `pending approval` phase names are part of the stop-hook's terminal-phase allowlist, so "stopped awaiting consent" is machine-distinguishable from "abandoned". Adapt: encode pending-approval as a first-class phase in `.omx/state` so harness loops can halt without a watchdog re-prompting.
- **Two deactivation verbs**: `active=false` (handoff; keeps other enforcement alive) vs `clear` (terminal; emits a global 30s cancel window). Adapt: any harness with multiple concurrent enforcement loops needs the same handoff/terminal distinction or a mode launch right after planning is unprotected.
- **Launch hints embedded in the approved artifact**: the plan itself carries the exact parameterized launch command; a strict regex + ambiguity/incompleteness outcomes let a short follow-up ("team") safely launch only a unique, complete, approved plan. Adapt: exp-design proposals could embed the approved `launch.sh` invocation, resolved only when the proposal passes section-completeness checks.
- **Section-presence completeness check as a cheap quality gate**: planning is "complete" only when named markdown H2 sections exist and are non-empty in paired artifacts. Adapt: omx report/proposal gating already section-based; pair artifacts by shared timestamp-slug the way `test-spec-<ts>-<slug>.md` binds to `prd-<ts>-<slug>.md`.
- **Reference-not-copy skill composition with explicit injection points**: deep-dive inherits deep-interview's whole protocol by reference and overrides exactly three initialization points, preventing behavioral-contract drift between skills. Adapt: oms/omd pilot skills should reference stage skills' SKILL.md rather than restating stage rules inline.
- **Circuit breaker with self-deactivating state**: cap reinforcement count within a TTL and mutate the state file (`deactivated_reason`) on exhaustion so the loop cannot re-arm itself. Adapt: any stop-hook or wakeup-loop in sibling harnesses.

# Agent Catalog: Definitions, Model Routing, and Tool Restrictions

OMC ships a fixed roster of 19 subagents as markdown files under `agents/*.md`, each a YAML-frontmatter header plus an XML-tagged system prompt. These files are the single source of truth for prompt bodies and per-agent tool blocklists. A parallel TypeScript layer in `src/agents/` wraps the same prompts with routing metadata (cost tier, category, delegation triggers) used to (a) build a runtime SDK agent registry (`getAgentDefinitions()`), (b) auto-generate delegation tables in the orchestrator system prompt, and (c) enforce that every `Task`/agent call carries an explicit model parameter. Two consumption paths exist: the Claude Code plugin auto-discovers `agents/*.md` directly (no `agents` key in `plugin.json` — it is discovered by convention), while `src/index.ts` builds a programmatic Claude Agent SDK embedding. Both draw prompt text from the same `.md` files via `loadAgentPrompt()`, which strips frontmatter and reads either build-time-embedded prompts (`__AGENT_PROMPTS__`) or the file on disk (`src/agents/utils.ts:88`).

## The 19 agents

Declared model tier and tool restriction are read from each file's frontmatter. Only four frontmatter keys are consumed by code: `name`, `description`, `model`, `disallowedTools`. The `level:` key (values 2/3/4) is **vestigial** — no TS reads agent-frontmatter `level` (the only `level:` in `src/` is the unrelated `EnforcementLevel` in the orchestrator hook, `src/hooks/omc-orchestrator/index.ts:44`).

| Agent | Model (.md) | disallowedTools | Category / Role | Write-capable |
|-------|-------------|-----------------|-----------------|:---:|
| `explore` | haiku | Write, Edit | exploration — codebase search | no |
| `writer` | haiku | — | utility — README/API docs | yes |
| `analyst` | opus | Write, Edit | advisor — pre-planning requirements | no |
| `architect` | opus | Write, Edit | advisor — architecture + hard debugging | no |
| `planner` | opus | — | planner — plan creation | yes* |
| `critic` | opus | Write, Edit | reviewer — plan/design review | no |
| `code-reviewer` | opus | Write, Edit | reviewer — severity-rated review | no |
| `code-simplifier` | opus | — | specialist — behavior-preserving refactor | yes |
| `security-reviewer` | opus | Write, Edit | reviewer — OWASP/secrets | no |
| `debugger` | sonnet | — | specialist — root-cause analysis | yes |
| `designer` | sonnet | — | specialist — UI/UX | yes |
| `document-specialist` | sonnet | Write, Edit | advisor — SDK/API docs lookup (deprecated alias) | no |
| `executor` | sonnet | — | specialist — implementation | yes |
| `git-master` | sonnet | — | specialist — atomic commits, style detection | yes |
| `qa-tester` | sonnet | — | specialist — tmux CLI testing | yes |
| `scientist` | sonnet | Write, Edit | specialist — data analysis | no |
| `test-engineer` | sonnet | — | specialist — test strategy/TDD | yes |
| `tracer` | sonnet | — | specialist — causal tracing | yes |
| `verifier` | sonnet | Write, Edit | reviewer — completion evidence | no |

\* `planner` has no `disallowedTools` but is a planning advisor; its prompt treats plan files as its output. The read-only advisors (`Write, Edit` blocked) number nine: `explore`, `analyst`, `architect`, `critic`, `code-reviewer`, `security-reviewer`, `scientist`, `verifier`, `document-specialist`.

No agent declares a positive `tools:` allowlist — restriction is exclusively a **blocklist** via `disallowedTools`, so every unblocked agent gets all tools by default (`AgentConfig.tools` "optional — all tools allowed by default if omitted", `src/agents/types.ts:72`).

## Model-routing economics

The three-tier scheme maps cost to task risk. Category defaults are hard-coded in `getDefaultModelForCategory()` (`src/agents/types.ts`): `exploration`/`utility` → haiku, `specialist`/`orchestration` → sonnet, `advisor` → opus. Metadata carries a coarser `cost: 'FREE' | 'CHEAP' | 'EXPENSIVE'` (`AgentCost`) that drives the auto-generated delegation table's "Cost" column (`buildDelegationTable`, `src/agents/utils.ts:169`).

| Tier | Alias | Agents | When (per `omc-reference/SKILL.md:37-39`) |
|------|-------|--------|-------------------------------------------|
| LOW | `haiku` | explore, writer | quick lookups, lightweight inspection, narrow docs |
| MEDIUM | `sonnet` | executor, debugger, designer, git-master, qa-tester, scientist, test-engineer, tracer, verifier, document-specialist | standard implementation, debugging, review |
| HIGH | `opus` | analyst, architect, planner, critic, code-reviewer, code-simplifier, (security-reviewer per .md) | architecture, deep analysis, consensus planning, high-risk review |

### Model resolution chain (SDK path)

Claude Code does not auto-apply an agent-definition model to a `Task` call, so OMC injects it via the delegation-enforcer PreToolUse middleware. `getAgentDefinitions()` resolves each agent's model with this priority (`src/agents/definitions.ts:264`):

```
override.model  →  inheritModel (routing.forceInherit)  →  configuredModel (settings)  →  agentConfig.model (default)
```

`enforceModel()` (`src/features/delegation-enforcer.ts`) then applies, in order: explicit param on the call (normalized) > `routing.modelAliases[tier]` > agent default. Any resolved value of `'inherit'` strips the model parameter entirely; otherwise `normalizeToCcAlias()` collapses full Claude IDs to the `sonnet`/`opus`/`haiku` aliases Claude Code accepts (full IDs like `claude-sonnet-5` cause 400 errors on Bedrock/Vertex — issues #1201, #1415). Provider-specific IDs (Bedrock/Vertex ARNs) pass through untouched.

```
Task(subagent_type="oh-my-claudecode:executor", ...)   [no model]
        │  PreToolUse: processPreToolUse → isAgentCall?
        ▼
   enforceModel()  ── forceInherit? ──yes──▶ strip model → inherit user's provider model
        │ no
        ▼
   agentDef.model 'sonnet' ── modelAlias? ──▶ normalizeToCcAlias ──▶ inject model:"sonnet"
```

### Configuration surface

| Surface | Key / var | Effect |
|---------|-----------|--------|
| settings | `agents.<key>.model` | per-agent override; keys via `AGENT_CONFIG_KEY_MAP` (e.g. `securityReviewer`, `codeReviewer`, `gitMaster`, `testEngineer`, `codeSimplifier`, `documentSpecialist`) |
| settings | `routing.forceInherit` | strip tier names so a non-Claude provider inherits the user's model |
| settings | `routing.modelAliases.{haiku,sonnet,opus}` | remap tier → concrete model without the nuclear forceInherit (#1211) |
| env | `OMC_MODEL_HIGH` / `OMC_MODEL_MEDIUM` / `OMC_MODEL_LOW` | tier → model ID resolution (`src/config/models.ts:68-70`) |
| env | `OMC_ROUTING_FORCE_INHERIT`, `OMC_ROUTING_ENABLED`, `OMC_ROUTING_DEFAULT_TIER` | routing toggles (`src/config/loader.ts:312-327`) |
| env | `OMC_MODEL_ALIAS_{HAIKU,SONNET,OPUS}` | alias overrides (#1211) |
| env | `CLAUDE_CODE_USE_BEDROCK` / `_VERTEX`, `ANTHROPIC_BASE_URL` | auto-enable forceInherit for non-Claude providers |
| env | `OMC_DEBUG=true` | emit `[OMC] Auto-injecting model: …` warnings |

forceInherit is **auto-enabled** by the config loader when a non-Claude provider is detected (`isNonClaudeProvider`, models.ts:353-361) — the enforcer then strips Claude tier names the provider would reject.

## System-prompt design patterns

Every agent prompt is a single `<Agent_Prompt>` block with a consistent XML section grammar. The recurring sections and their intent:

| Section | Purpose |
|---------|---------|
| `<Role>` | mission + a negative clause naming what the agent is **not** responsible for (role disambiguation) |
| `<Why_This_Matters>` | motivates the constraints so the model does not "optimize them away" |
| `<Success_Criteria>` | machine-checkable done-conditions (e.g. "every finding cites file:line") |
| `<Constraints>` | read-only declarations, scope limits, handoff targets |
| `<Investigation_Protocol>` | numbered procedure (gather-context-first is mandatory for advisors) |
| `<Tool_Usage>` + `<External_Consultation>` | which tools, and "spawn a Task agent for a second opinion; skip silently if delegation unavailable, never block" |
| `<Output_Format>` | exact heading/table skeleton of the deliverable |
| `<Failure_Modes_To_Avoid>` / `<Examples>` (Good/Bad) | anti-patterns with contrasting concrete examples |
| `<Final_Response_Contract>` | (advisors) the LAST message must carry the full structured deliverable |

**Role disambiguation** is explicit and non-overlapping among the four HIGH-tier thinking agents (documented in `definitions.ts:183-197`): `architect` = code analysis/debug; `analyst` = requirements gaps; `planner` = plan creation; `critic` = plan review. Each prompt repeats "You are not responsible for [the other three]." The canonical workflow is `explore → analyst → planner → critic → executor → architect (verify)`.

**Anti-pattern framing** is concrete, not abstract. `executor.md` lists eight named failure modes (Overengineering, Scope creep, Premature completion, Test hacks, Batch completions, Skipping exploration, Silent failure, Debug code leaks) each with an "Instead:" corrective, plus a Good/Bad example pair (3-line change vs a 200-line `TimeoutConfig` class) and a `<Final_Checklist>`. `code-reviewer.md` warns against "Severity inflation" (rating a missing JSDoc as CRITICAL) and vague issues.

## Author-vs-reviewer structural separation

The reviewer agents encode a hard "never approve your own work" rule at the prompt level. `code-reviewer.md` states: "Review is a separate reviewer pass, never the same authoring pass that produced the change" and "Never approve your own authoring output or any change produced in the same active context; require a separate reviewer/verifier lane for sign-off" (`agents/code-reviewer.md:38-39`). Read-only enforcement is doubled: the prompt declares read-only *and* `disallowedTools: Write, Edit` makes it structural.

The code-reviewer uses a **severity × confidence matrix** with a deliberately staged design: discovery surfaces *every* finding (CRITICAL/HIGH/MEDIUM/LOW × LOW/MEDIUM/HIGH confidence) without pre-filtering, because "recent Claude models follow filtering instructions faithfully and may not surface bugs they would otherwise catch" (line 19); ranking/filtering is a downstream stage. The verdict gates only on HIGH-confidence CRITICAL/HIGH; low-confidence critical findings go to an "Open Questions" section and do not block on their own (lines 40, 57).

**`<Final_Response_Contract>`** is test-enforced across eight advisory agents (`architect, critic, code-reviewer, security-reviewer, verifier, analyst, tracer, debugger`). `src/__tests__/advisory-agent-final-output-contract.test.ts` asserts each prompt contains agent-specific required markers (e.g. critic must contain `**VERDICT:`, security-reviewer must contain `# Security Review Report` and `**Risk Level:**`), the literal phrase "LAST assistant message is the deliverable surfaced to callers", the instruction to "repeat the final verdict/findings structure in the LAST message", and must forbid content-free sign-offs via `/(?:done|complete|nothing further|looks good|no further comments)/i`. The test checks both the raw `.md` and the registry-resolved prompt, so the contract survives prompt assembly.

## How skills reference agents

Skills invoke agents by the prefixed identifier `Task(subagent_type="oh-my-claudecode:<name>")`. Across `skills/*/SKILL.md` the reference counts are: `executor` (13), `scientist` (11), `architect` (5), `critic` (4), `planner`/`explore`/`document-specialist` (2 each), and one each for `security-reviewer`, `qa-tester`, `code-reviewer`, `analyst`. The orchestrator system prompt (built by `src/agents/prompt-sections/index.ts`) also auto-generates an "Available Subagents" registry, a "Key Triggers" table, and a "Delegation Guide" purely from agent metadata — so adding a metadata-bearing agent updates the orchestrator prompt automatically.

**Metadata coverage is partial.** Only 12 agents have individual `.ts` files with `*_PROMPT_METADATA` (triggers/useWhen/avoidWhen): `analyst, architect, critic, designer, document-specialist, executor, explore, planner, qa-tester, scientist, tracer, writer`. The other seven (`code-reviewer, code-simplifier, debugger, git-master, security-reviewer, test-engineer, verifier`) are defined inline in `definitions.ts` **without metadata**, so they never appear in the auto-generated delegation/trigger tables (`buildDelegationTable` filters `a.metadata.triggers.length > 0`) — they surface only in the static `omc-reference/SKILL.md` catalog.

## Divergences and vestigial material (evidence-checked)

The `.md` frontmatter and the SDK registry disagree on one model tier: `security-reviewer` is `model: opus` in `agents/security-reviewer.md` but `model: 'sonnet'` in `securityReviewerAgent` (`definitions.ts:106`), and the `omc-reference/SKILL.md:23` catalog also lists it as `(sonnet)`. Which tier a call actually gets depends on the path: the plugin agent surface (`.md`) yields opus; the SDK registry yields sonnet. The `.md` frontmatter is the outlier of the three.

`executor.md` references a Worker Preamble Protocol via `wrapWithPreamble()` from `src/agents/preamble.ts`, but **no `preamble.ts` exists** and no `wrapWithPreamble` symbol is defined anywhere in `src/` — a stale prompt reference. The dev doc `src/agents/AGENTS.md` is also stale: it claims "18 base agents" (there are 19 `.md` files), lists a `vision.ts` agent that does not exist, and documents tiered variants (`architect-low`, `executor-high`, `explore-high`, `architect-medium`) that are **not registered** anywhere in `definitions.ts`/`index.ts` — an aspirational routing design that was never wired. `ai-slop-cleaner` is referenced with an agent-style identifier in `ralph/SKILL.md` only to warn it is a **skill, not an agent**, and must be invoked via `Skill("ai-slop-cleaner")`.

The `skininthegamebros` guidance (`appendSkininthegamebrosGuidance`) is appended to every agent and the system prompt, but is a no-op unless `process.env.USER_TYPE === 'ant'` (`src/utils/skininthegamebros-user.ts`) — a per-user gated extension, dormant for ordinary installs.

## Failure modes and guards

Model injection **fail-loud**: `enforceModel()` throws `Unknown agent type: <x>` for an unregistered `subagent_type` and `No default model defined for agent: <x>` if an agent lacks a model — a delegation call cannot silently run on an unintended model. Prompt loading is **fail-safe**: `loadAgentPrompt()` and `parseDisallowedTools()` validate the agent name against `/^[a-z0-9-]+$/i` and verify the resolved path stays inside `agents/` (path-traversal guard, `utils.ts:115`), and `parseDisallowedTools` returns `undefined` on any read error rather than throwing. Config reads are cached by an env-var-derived key so `enforceModel()` does not hit disk on every call (`getCachedConfig`, delegation-enforcer.ts), with the cache bypassed under `VITEST`.

## Patterns for sibling harnesses

- **Markdown-as-SSOT for prompts, TS-as-metadata overlay.** Keep the prose prompt in a `.md` (frontmatter for name/model/tool-blocklist) and load it with a frontmatter-stripping, path-traversal-guarded loader; layer routing metadata (cost/category/triggers) in code. Sibling harnesses can reuse the exact `loadAgentPrompt` + `__X_PROMPTS__` build-embed / disk-fallback dual path.
- **Blocklist tool restriction over allowlist.** Default agents to all tools and subtract with `disallowedTools`; render as `{tools:{write:false,edit:false}}`. Cheaper to author and audit than positive allowlists.
- **Three-tier cost routing keyed to category, not agent.** Map exploration/utility→cheap, specialist→mid, advisor→expensive by category, so new agents inherit sane defaults; expose per-agent settings + tier-env overrides + `modelAliases` + `forceInherit` for non-Claude providers.
- **Explicit-model injection middleware.** A PreToolUse enforcer that fails loud on unknown agent / missing model and normalizes full IDs to provider aliases prevents silent wrong-model runs — reusable verbatim for any harness that spawns typed subagents.
- **Author-vs-reviewer as a structural invariant.** Make reviewers read-only at *both* prompt and tool level, and bake "never approve work produced in the same context" into the prompt; pair it with a discovery-then-filter severity×confidence design so low-confidence criticals surface without gating.
- **Test-enforced final-response contract.** Assert (in unit tests, over both raw and assembled prompts) that each advisor's prompt contains its required output markers and forbids content-free sign-offs — turns "the last message IS the deliverable" from a hope into a guarantee.
- **Auto-generated delegation tables from metadata.** Derive the orchestrator's agent registry / trigger table / delegation matrix from agent metadata so adding an agent updates the orchestrator prompt with zero prose edits — but ensure *every* agent carries metadata, or it silently vanishes from the generated tables (OMC's 7 metadata-less agents are the cautionary case).
- **Named-anti-pattern prompting with Good/Bad pairs.** Enumerate concrete failure modes each with an "Instead:" corrective and a contrasting example, rather than abstract "be careful" guidance.
- **Guard against stale cross-references.** OMC's `preamble.ts` reference and `vision.ts`/tiered-variant doc entries are dead; a periodic test that every `subagent_type` / file reference in prompts and docs resolves would have caught them.

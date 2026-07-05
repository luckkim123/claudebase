# Skill & Command Authoring System: Frontmatter, Triggers, and the Skill Registry

OMC ships 40 bundled skill directories (`skills/<name>/SKILL.md`) and 28 slash-command stubs (`commands/*.md`), all registered through `.claude-plugin/plugin.json` (`"skills"` array lists all 40 dirs; `"commands": "./commands/"`) (.claude-plugin/plugin.json — whole-file). The same SKILL.md files are consumed by three independent runtimes: (1) Claude Code's native plugin skill loader, (2) OMC's own SDK-facing "builtin skills" catalog (`src/features/builtin-skills/skills.ts`), and (3) the auto-slash-command hook executor (`src/hooks/auto-slash-command/executor.ts`). A fourth, separate subsystem — "learned skills" under `.omc/skills/` and `~/.omc/skills/` — uses a different, stricter frontmatter schema and is exposed via three MCP tools. This section documents the frontmatter contract, the command-to-skill dispatch pattern, install-time context-budget compaction, tier-0 designation, and the full 40-skill inventory.

```
                         skills/<name>/SKILL.md  (source of truth, 40 dirs)
                                    |
        +---------------------------+---------------------------+
        |                           |                           |
  Claude Code host           OMC SDK catalog             auto-slash-command hook
  (plugin.json skills)   createBuiltinSkills()          discoverSkillsFromDir()
        |                (src/features/builtin-skills)  (src/hooks/auto-slash-command)
  install-time shim:            |
  compactPluginSkillPayload()   +--> template = body + runtime guidance
  (skills/ -> 2KiB shims,            + pipeline guidance + resources listing
   full body -> skill-bodies/)
                                     commands/<name>.md (28 lazy dispatch stubs)
                                       "read skills/<name>/SKILL.md, follow it,
                                        args = $ARGUMENTS"

  SEPARATE SCHEMA: learned skills  .omc/skills/ | ~/.omc/skills/ | ~/.claude/skills/omc-learned/
    parsed by src/hooks/learner/parser.ts; served by MCP tools
    load_omc_skills_local / load_omc_skills_global / list_omc_skills (src/tools/skills-tools.ts)
```

## SKILL.md frontmatter schema (bundled skills)

Frontmatter is parsed by a deliberately naive line-based parser: `parseFrontmatter()` matches the `^---\r?\n...\r?\n---` block, then for each line splits on the first `:` (`line.indexOf(':')`) into a flat `Record<string, string>` and strips surrounding quotes via `stripOptionalQuotes()`; nothing is typed, values on continuation lines are lost, and nested YAML is not supported (src/utils/frontmatter.ts:26-48). Inline lists (`aliases: [psm]`) are handled by `parseFrontmatterList()`, which the alias path reaches through the thin wrapper `parseFrontmatterAliases()` (src/utils/frontmatter.ts:54-80). What the loader actually consumes vs. what is decorative:

| Field | Example | Consumed by | Effect |
|---|---|---|---|
| `name` | `name: omc-plan` | builtin loader | canonical name; falls back to dir name (src/features/builtin-skills/skills.ts:238) |
| `description` | one-line trigger-laden sentence | all three runtimes | catalog/dispatch description; primary "trigger phrase" carrier |
| `aliases` | `aliases: [psm]` (project-session-manager), `[cancel-ralph]` (cancel), `[learner]` (skillify) | builtin loader | alias entries emitted with `deprecatedAlias: true` and `deprecationMessage: 'Skill alias "X" is deprecated. Use "Y" instead.'` (skills.ts:250-274) |
| `argument-hint` | `"[--force\|--all]"` | builtin loader, command executor | surfaced as `argumentHint` (skills.ts:280) |
| `model` / `agent` | `agent: tracer` (trace skill) | builtin loader, command executor | routing hints passed through verbatim (skills.ts:278-279) |
| `pipeline`, `next-skill`, `next-skill-args`, `handoff`, `handoff-policy` | deep-dive: `pipeline: [deep-dive, plan, autopilot]`, `next-skill: plan`, `next-skill-args: --consensus --direct`, `handoff: .omc/specs/deep-dive-{slug}.md` | `parseSkillPipelineMetadata()` (src/utils/skill-pipeline.ts:42-67) | appends a generated "## Skill Pipeline" block to the rendered prompt with the step chain, handoff artifact path, and — when `handoff-policy: approval-required` — a hard "stop with the handoff artifact marked `pending approval`" instruction (skill-pipeline.ts:115-137) |
| `omc-full-body` | `omc-full-body: "../../skill-bodies/plan/SKILL.md"` | builtin loader | body override for compacted installs; path must resolve inside the package root or is ignored (skills.ts:161-182) |
| `level` | `level: 1`..`level: 7` | **nothing in src/** | documentation-only maturity ladder (1=reminder .. 4=orchestration .. 7=self-improving); grep finds no consumer |
| `triggers` | `triggers: ["wiki", "wiki add", ...]` (wiki, configure-notifications, deep-dive) | **nothing** for bundled skills | decorative; keyword auto-detection is hardcoded regex in src/hooks/keyword-detector/index.ts:46-67, not frontmatter-driven. (`triggers` IS required for learned skills — different schema, below) |
| `user-invocable: false` | omc-reference only | Claude Code host | hides the self-catalog from the user's slash menu (skills/omc-reference/SKILL.md:4) |
| `role:` / `scope:` | hud: `role: config-writer  # DOCUMENTATION ONLY` | nothing | annotated as documentation in the file itself (skills/hud/SKILL.md:5-6) |

Key convention: because bundled-skill `triggers:` are dead metadata, **the `description` field does double duty as the trigger surface** — descriptions are written as dense "Use when..." sentences so the host model routes on them (e.g. wiki, deep-dive). Hard keyword routing (`"ralph"`, `"ulw"`, `"cancelomc"`...) lives entirely in the keyword-detector hook with informational-context suppression, quote exemption, task-size gating and the ralplan underspecification gate (src/hooks/keyword-detector/index.ts:46-67, 899-938, 1050-1086 — covered in depth by the keyword-routing section).

## Commands vs. skills: the thin-stub dispatch pattern

All 28 files in `commands/` except `compact.md` are near-identical 13-18 line stubs with `description: ""` whose body says: "This compatibility command keeps `/oh-my-claudecode:<name>` available without loading the full `<name>` skill description in every Claude Code session", then instructs: read `skills/<name>/SKILL.md`, follow it exactly, treat `$ARGUMENTS` as the user's arguments, and fall back to `CLAUDE_PLUGIN_ROOT`/`OMC_PLUGIN_ROOT`/package root if the relative path is unreadable (commands/verify.md — whole-file). Two stubs are pure alias redirects: `psm.md` -> `project-session-manager/SKILL.md`, `learner.md` -> `skills/skillify/SKILL.md`. The one non-stub, `compact.md`, exists solely to avoid shadowing native `/compact`: it explains that a plugin cannot trigger native compaction and tells the user to run bare `/compact` themselves (commands/compact.md:8-21).

Coverage is deliberately asymmetric: 14 skills have **no** command stub — `ai-slop-cleaner, autopilot, cancel, deep-interview, local-build-reminder, omc-reference, plan, ralph, ralplan, setup, team, ultragoal, ultraqa, ultrawork` (set difference of `commands/` vs `skills/`). The heavy workflow skills are reached via plugin skill registration and keyword detection instead. A regression test enforces the stub contract: every existing `commands/<frontmatter-name>.md` must contain the matching `skills/<dir>/SKILL.md` path and `$ARGUMENTS` (src/__tests__/plugin-skill-budget.test.ts:118-133). `expandCommand()` in src/commands/index.ts is a small SDK library helper that substitutes `$ARGUMENTS` into a command template for programmatic Agent SDK use; user-config `~/.claude/commands/` shadows packaged `commands/` per name (src/commands/index.ts:54-62,93-113).

## Progressive disclosure: install-time compaction and lazy bodies

The bundled SKILL.md corpus is >400 KiB. To keep session-start context small, the installer rewrites every installed plugin skill at sync time via `compactPluginSkillPayload()` (src/installer/index.ts:1456-1512):

1. Copy the whole skill dir to `skill-bodies/<name>/` (constant `PLUGIN_FULL_SKILL_BODIES_DIR = 'skill-bodies'`, src/installer/index.ts:43).
2. Replace `skills/<name>/SKILL.md` with a shim marked `<!-- OMC:COMPACT-PLUGIN-SKILL -->`, its description normalized to <=240 chars (src/installer/index.ts:1422-1429), plus frontmatter `omc-full-body: "../../skill-bodies/<name>/SKILL.md"`.
3. The shim body instructs the model to read `${CLAUDE_PLUGIN_ROOT:-${OMC_PLUGIN_ROOT}}/skill-bodies/<name>/SKILL.md` on invocation, and explicitly warns against resolving `skill-bodies/` relative to the shim's own directory (src/installer/index.ts:1453).

A budget gate test pins the numbers: total compacted SKILL.md payload < `64 * 1024` bytes, each shim < `2 * 1024` bytes, and archived body must be byte-identical to source (src/__tests__/plugin-skill-budget.test.ts:24-25,70-100). On the SDK side, `readSkillBodyOverride()` follows `omc-full-body` (with `isPathInsideOrEqual()` containment against the package root, win32-aware) so the builtin catalog always renders the full body even from a compacted install (src/features/builtin-skills/skills.ts:161-182,150-154). Three more disclosure layers are appended to every rendered skill template: per-skill runtime guidance (Codex-availability notes injected only for `deep-interview`/`ralplan`/`plan`/`ralph` when `isCliAvailable('codex')`, src/features/builtin-skills/runtime-guidance.ts:73-89), the pipeline handoff block, and a "## Skill Resources" listing of up to `MAX_RESOURCE_ENTRIES = 12` non-hidden files in the skill dir with the instruction "Prefer reusing these bundled resources ... instead of recreating them" (src/utils/skill-resources.ts:4,52-68).

## The builtin skill registry (src/features/builtin-skills/skills.ts)

`createBuiltinSkills()` scans `<packageRoot>/skills/*/SKILL.md` and caches results; the cache key is the resolved deep-interview ambiguity threshold, so a settings change invalidates it (skills.ts:337-360). Registry-level guards:

| Guard | Mechanism | Evidence |
|---|---|---|
| Native-command shadowing | `CC_NATIVE_COMMANDS = {review, plan, security-review, init, doctor, help, config, clear, compact, memory}`; matching names get `omc-` prefix (hence `name: omc-plan` in skills/plan/SKILL.md) | skills.ts:59-85 |
| Employee-only skills | `SKININTHEGAMEBROS_ONLY_SKILLS = {remember, verify, debug}` skipped unless `isSkininthegamebrosUser()` — i.e. `process.env.USER_TYPE === 'ant'` | skills.ts:72-76,314; src/utils/skininthegamebros-user.ts:1-3 |
| Alias claim ordering | directory sort forces `skillify` first so it claims the deprecated `learner` alias before the legacy `skills/learner/` dir loads; the legacy dir is then dropped by the `seenNames` dedup | skills.ts:303-310,321-326 |
| Threshold templating | for deep-interview/deep-dive, `applyDeepInterviewRuntimeSettings()` rewrites `<resolvedThreshold>` placeholders and every hardcoded `0.2`/`20%` string from `omc.deepInterview.ambiguityThreshold` in `./.claude/settings.json` (project wins) or profile settings, default `DEFAULT_DEEP_INTERVIEW_AMBIGUITY_THRESHOLD = 0.2` | skills.ts:78,102-140,184-217 |
| Fail-open loading | any read/parse failure returns `[]` for that skill or the whole dir; no crash, no error surfaced | skills.ts:286-288,329-332 |

Runtime activation state is a separate ledger (`.omc/state/skill-active-state.json`, dual root+session copies): the 8 `CANONICAL_WORKFLOW_SKILLS = [autopilot, ralph, team, ultrawork, ultraqa, deep-interview, ralplan, self-improve]` get workflow slots with tombstones (`WORKFLOW_TOMBSTONE_TTL_MS = 24h`), while every other skill gets stop-hook "support" protection at `light` (3 reinforcements / 5 min TTL), `medium` (5 / 15 min), or `heavy` (10 / 30 min) per the hardcoded `SKILL_PROTECTION` map — e.g. `skill`/`ask`/`configure-notifications` light, `deepinit`/`deep-interview` heavy (src/hooks/skill-state/index.ts:60-69,90-153). Protection is refused for skills invoked without the `oh-my-claudecode:` prefix, so user-defined project skills with colliding names never inherit OMC stop-blocking (skill-state/index.ts:155-161, issue #1581).

**Tier-0 designation.** "Tier-0" is a compatibility contract, not a frontmatter field: `TIER0_SKILLS = ['team', 'ralph', 'ultrawork', 'autopilot']` must remain canonical unprefixed names, resolve case-insensitively, and keep keyword-routing fidelity, enforced by dedicated tests (src/__tests__/tier0-contracts.test.ts:15-42); a docs-consistency test pins their documentation in REFERENCE.md and CLAUDE.md (src/__tests__/tier0-docs-consistency.test.ts:14-35). The installed CLAUDE.md text broadens the marketing list to "Tier-0 workflows include `autopilot`, `ultrawork`, `ralph`, `team`, and `ralplan`" (docs/CLAUDE.md:29).

## Learned skills: the second schema and its MCP surface

Learned skills (created by `skillify`/the learner hook, or hand-written) live in `.omc/skills/` (project), `~/.omc/skills/` (global), `~/.claude/skills/omc-learned/` (legacy user dir), plus read-only compat `.agents/skills/` (src/hooks/learner/constants.ts:11-20). Their schema is validated, unlike bundled skills: required fields are `name`, `description`, and non-empty `triggers` (`id` is derived from name; `source` defaults to `'manual'`), with optional `quality` (0-100), `usageCount`, `tags`, `matching: exact|fuzzy`, `model`, `agent`, `sessionId`, `createdAt` (src/hooks/learner/parser.ts:40-57; types.ts:11-38). Loading dedups by id with project priority 1 > user 0 (loader.ts:26-68). Trigger matching for auto-injection scores substring hits: trigger +10, tag +5, then quality/20 and min(usageCount,10) boosts only when a trigger/tag matched; constants cap injection at `MAX_SKILLS_PER_SESSION = 10`, `MIN_QUALITY_SCORE = 50`, content truncated at `MAX_SKILL_CONTENT_LENGTH = 4000` (loader.ts:82-133; constants.ts:35-44). Feature flag `learner.enabled` defaults true (constants.ts:29-32); `OMC_DEBUG=1` enables load warnings.

Three MCP tools expose this store through the plugin's single MCP server `t` (`.mcp.json` -> `bridge/mcp-server.cjs`; registered in src/mcp/tool-registry.ts:63 via `skillsTools` under `TOOL_CATEGORIES.SKILLS`): `load_omc_skills_local` (project scope, tool name at skills-tools.ts:105), `load_omc_skills_global` (user scope, zero-arg — `loadGlobalSchema = {}`, line 68/124), `list_omc_skills` (both, "Project skills take priority over user skills with the same ID", line 142). Defenses: `validateProjectRoot()` rejects any input containing `..` and requires the resolved path to equal or sit under an entry in `ALLOWED_BOUNDARIES` (cwd or `$HOME`) (skills-tools.ts:26-42), and `_sanitizeSkillContent()` first truncates at `MAX_SKILL_CONTENT_LENGTH` appending a literal `\n[truncated]`, then drops role-boundary lines matching `ROLE_BOUNDARY_PATTERN = /^<\s*\/?\s*(system|human|assistant|user|tool_use|tool_result)\b[^>]*>/i` to blunt prompt injection (skills-tools.ts:20,47-57).

## Manager and self-catalog skills

`skills/skill/SKILL.md` (847 lines) is the meta-skill CLI: subcommands `list | add | remove | edit | search | info | sync | setup | scan`, an interactive creation wizard writing to `~/.claude/skills/omc-learned/<name>/SKILL.md` or `.omc/skills/<name>/SKILL.md`, delete-with-confirmation, plus four authoring templates (Error Solution / Workflow / Code Pattern / Integration) each structured as `## The Insight / Why This Matters / Recognition Pattern / The Approach` (skills/skill/SKILL.md:14-496). Built-ins are listed read-only: "not removed or edited through `/skill remove` or `/skill edit`" (skills/skill/SKILL.md:46).

`skills/omc-reference/SKILL.md` is the progressive-disclosure self-catalog (`user-invocable: false`): the 19-agent catalog with model tiers, tool-name reference (state_*, notepad_*, project_memory_*, LSP/AST), the skills registry split into workflow vs. utility skills, the compact keyword-trigger list mirroring CLAUDE.md, the team pipeline stages `team-plan -> team-prd -> team-exec -> team-verify -> team-fix`, and the commit-trailer protocol (`Constraint:`, `Rejected:`, `Directive:`, `Confidence:`, `Scope-risk:`, `Not-tested:`) (skills/omc-reference/SKILL.md:11-143). Its purpose is stated in its own description: keep detailed catalog data out of "every CLAUDE.md session" and auto-load on demand.

## Skills not covered elsewhere (brief)

`ai-slop-cleaner` (145 lines): deletion-first, regression-safe cleanup of AI-generated slop with `--review` reviewer-only mode and optional ralph integration. `debug` (35 lines): diagnose the current OMC session via logs/traces/state and focused reproduction. `verify` (37 lines): evidence-before-claim gate ("Turn vague 'it should work' claims into concrete evidence") — deep coverage in section 17; note `debug`/`verify`/`remember` are the three `USER_TYPE=ant`-gated skills in the SDK catalog. `visual-verdict` (77 lines): compares generated UI screenshots to references and returns a strict JSON verdict to drive the next edit iteration; body uses XML-ish `<Purpose>/<Use_When>` tags rather than headings. `release` (198 lines): derives repo release rules on first run, caches them in `.omc/RELEASE_RULE.md`, then walks the release. `remember`: routes session knowledge to project memory / notepad / durable docs (deep in section 11). `project-session-manager` (585 lines + bundled `psm.sh`, `lib/`, `templates/`, `tests/`): worktree-first issue/PR/feature environments with optional tmux; `psm` alias; recommends `omc teleport`. `mcp-setup` (245 lines): guided `claude mcp add` configuration of popular servers. `configure-notifications` (1214 lines — largest skill): natural-language Telegram/Discord/Slack setup (deep in section 13). `setup` is a pure router: first argument dispatches to `omc-setup` / `omc-doctor` / `mcp-setup` (skills/setup/SKILL.md:20-27).

## Complete 40-skill inventory

Class: T0 = tier-0 contract; W = canonical workflow slot; L/M/H = support protection light/medium/heavy; `-` = no protection entry. Lvl = frontmatter `level` (unconsumed metadata; blank if absent). Deps = notable runtime dependencies beyond plain prompting.

| Skill | Lvl | Class | Purpose (from frontmatter description) | Runtime deps |
|---|---|---|---|---|
| ai-slop-cleaner | 3 | M | regression-safe, deletion-first AI-slop cleanup; reviewer-only mode | optional ralph loop |
| ask | - | L | process-first advisor routing to Claude/Codex/Gemini/Antigravity/Grok/Cursor | `omc ask` CLI |
| autopilot | 4 | T0/W | full autonomous execution from idea to working code | state hooks, agents, `omc` CLI |
| autoresearch | 4 | - | stateful single-mission improvement loop, strict evaluator contract, max-runtime stop | mission dir artifacts, `omc` CLI |
| cancel | 2 | - | cancel any active OMC mode; alias `cancel-ralph` | state_clear MCP, tmux teams |
| ccg | 5 | M | Claude-Codex-Gemini tri-model orchestration, Claude synthesizes | `omc ask codex/antigravity/gemini` |
| configure-notifications | 2 | L | Telegram/Discord/Slack notification setup via natural language | notifications config (section 13) |
| debug | - | - | diagnose current OMC session/repo via logs, traces, state | trace/state MCP tools; `USER_TYPE=ant` gated |
| deep-dive | - | - | 2-stage trace -> deep-interview pipeline with 3-point injection | pipeline metadata, state MCP, agents |
| deep-interview | 3 | H/W | Socratic interview with mathematical ambiguity gating | state_write, settings threshold injection |
| deepinit | 4 | H | hierarchical AGENTS.md codebase documentation | agents, deepinit_manifest tool |
| external-context | 4 | M | parallel document-specialist agents for web/docs lookup | document-specialist agents |
| hud | 2 | - | configure HUD (layout, presets, elements) | writes `~/.claude/settings.json` `omcHud` |
| learner | 7 | M | DEPRECATED alias body for skillify; dropped from catalog by skillify's alias claim | none |
| local-build-reminder | 1 | - | remind to rebuild OMC after editing src/**/*.ts in a dev install | none |
| mcp-setup | 2 | M | configure popular MCP servers | `claude mcp` CLI |
| omc-doctor | 3 | - | diagnose and fix OMC installation issues | `omc doctor` CLI |
| omc-reference | - | - | agent/tool/skill/team/commit self-catalog; `user-invocable: false` | none |
| omc-setup | 2 | M | canonical install/refresh flow (plugin, npm, local-dev) | `phases/` bundled resources |
| omc-teams | 4 | - | CLI-team runtime in tmux panes (claude/codex/gemini/antigravity/grok/cursor) | tmux, `omc` CLI, state |
| plan (name: omc-plan) | 4 | M | strategic planning with optional interview; pipeline -> deep-interview | agents, state, optional codex |
| project-session-manager | 2 | M | worktree-first dev env manager; alias `psm` | `psm.sh`, lib/, tmux, gh |
| ralph | 4 | T0/W | self-referential loop until completion, configurable critic | state hooks, agents, optional codex critic |
| ralplan | 4 | W | consensus planning entrypoint; auto-gates vague execution requests | planner/architect/critic agents |
| release | 3 | M | repo-aware release assistant; caches rules in `.omc/RELEASE_RULE.md` | git/CI inspection |
| remember | - | - | route reusable knowledge to memory surfaces (section 11) | notepad/project-memory MCP; `ant` gated |
| sciomc | 4 | M | parallel scientist agents with AUTO mode | scientist agents |
| self-improve | 4 | W | evolutionary code improvement with tournament selection | `scripts/`, `templates/`, sub-prompts, state |
| setup | 2 | M | router: setup/doctor/mcp -> correct flow by first argument | dispatches to 3 sibling skills |
| skill | 2 | L | manage local skills: list/add/remove/search/edit/setup wizard | filesystem skill dirs |
| skillify | - | M | turn a session workflow into a reusable skill draft; alias `learner` | writes learned-skill dirs |
| team | 4 | T0/W | N coordinated agents on shared task list (implicit agent teams) | Agent/Task teams, state |
| trace | 2 | - | evidence-driven tracing with competing tracer hypotheses; `agent: tracer` | tracer agents, team mode |
| ultragoal | 3 | - | durable multi-goal workflow; artifacts under `.omc/ultragoal` | `.omc/ultragoal/` ledger, `omc` CLI |
| ultraqa | 3 | W | QA cycling: test, verify, fix, repeat until goal met | test runners, state |
| ultrawork | 4 | T0/W | parallel execution engine for high-throughput completion | agents, state |
| verify | - | - | verify a change really works before claiming completion (section 17) | evidence commands; `ant` gated |
| visual-verdict | 2 | - | strict JSON verdict for screenshot-vs-reference visual QA | screenshot files via Read |
| wiki | - | - | persistent markdown knowledge base compounding across sessions | `wiki_*` MCP tools |
| writer-memory | 7 | M | agentic memory for writers (characters, relationships, scenes) | `lib/`, `templates/` resources |

Count note: the disk truth is exactly 40 skill directories with a `SKILL.md` (verified by `ls skills/*/`), all 40 registered in `plugin.json`'s `"skills"` array as `./skills/<name>/` paths; the 41st entry sometimes cited in planning is an artifact of counting the `learner` legacy dir plus its `skillify` reincarnation (the loader collapses these to one catalog entry via the `skillify`-first sort + `seenNames` dedup, skills.ts:307-324), so the live catalog is 40. Two internal catalogs have drifted and are vestigial as documentation: `skills/AGENTS.md` claims "30 skill directories" and lists phantom `note/`, `omc-help/`, and `ralph-init/` dirs that do not exist (skills/AGENTS.md:6,57,63,34), and `omc-reference` also lists a nonexistent `note` utility skill (skills/omc-reference/SKILL.md:89). The `SKILL_PROTECTION` map likewise carries dead keys for those phantoms (`omc-help`, `learn-about-omc`, `note`, `ralph-init`) that never match a real skill (skill-state/index.ts:122-147).

## Configuration surface

| Surface | Key | Effect |
|---|---|---|
| env | `USER_TYPE=ant` | unhides `remember`/`verify`/`debug` in the SDK builtin catalog (src/utils/skininthegamebros-user.ts:2) |
| env | `OMC_DEBUG=1` | learned-skill load warnings (src/hooks/learner/constants.ts:47) |
| env | `CLAUDE_PLUGIN_ROOT` / `OMC_PLUGIN_ROOT` | plugin-root resolution in compacted shims and command stubs (src/installer/index.ts:1453) |
| env | `CLAUDE_CONFIG_DIR` | relocates `~/.claude` for user skill/command dirs (src/hooks/learner/constants.ts:11) |
| settings.json | `omc.deepInterview.ambiguityThreshold` (0-1) | rewrites deep-interview/deep-dive gate threshold; project `./.claude/settings.json` overrides profile; default 0.2 (skills.ts:102-139) |
| config flag | `learner.enabled` (default `true`) | learned-skill subsystem kill switch (constants.ts:29-32) |
| frontmatter | `handoff-policy: approval-required` | forces pending-approval stop between pipeline stages (skill-pipeline.ts:53-54,117) |

Failure posture is uniformly fail-open and silent: unreadable/invalid SKILL.md files are skipped (builtin loader returns `[]`, learned loader logs only under `OMC_DEBUG`), missing command files return `null`, and compaction errors are collected per-skill into an `errors` array rather than aborting the install (src/installer/index.ts:1505-1508).

## Patterns for sibling harnesses

- **Single SKILL.md source, multiple renderers**: one markdown file feeds the host plugin loader, an SDK catalog, and a slash-command executor; keep the file the SSOT and derive everything at load time. Adaptation: sibling harnesses should render their skill cards once and reuse across CLI/hook/agent surfaces instead of duplicating prose.
- **Install-time context-budget compaction with archived full bodies** (`skill-bodies/` + `omc-full-body` pointer + <2 KiB shims, test-pinned 64 KiB total): startup context stays flat as the corpus grows. Adaptation: omd/oms skill sets should ship shims whose bodies are read on invocation, with a budget regression test.
- **Thin command stubs with `description: ""` and `$ARGUMENTS` passthrough**: keeps a stable slash surface at near-zero always-loaded cost. Adaptation: generate stubs mechanically and test that each stub cites the real skill path and `$ARGUMENTS`.
- **Name-shadowing guard set** (`CC_NATIVE_COMMANDS` -> `omc-` prefix): never let a harness skill steal a host-native command name. Adaptation: each harness should maintain its own reserved-name set and prefix on collision.
- **Alias entries with machine-readable deprecation** (`aliasOf`, `deprecatedAlias`, generated deprecation message) plus deterministic claim ordering: renames become non-breaking. Adaptation: cheap to re-implement in any loader that dedups by lowercase name.
- **Pipeline frontmatter compiled into an injected handoff contract** (`pipeline`/`next-skill`/`handoff`/`handoff-policy` -> generated "## Skill Pipeline" block with approval gating): multi-stage flows are declared as data, not prose. Adaptation: omd's intake->plan->build->verify chain and oms's stage chain can declare stages this way and auto-render the handoff rules.
- **Auto-generated "Skill Resources" listing** (dir scan, cap 12, "prefer reusing bundled resources"): makes bundled scripts/templates discoverable without hand-maintained lists. Adaptation: trivially portable to any skill dir layout.
- **Two-schema separation: bundled (loose, fail-open) vs. learned (validated, trigger-required, quality/usage-scored)**: authored workflow prompts and accumulated knowledge have different integrity needs. Adaptation: omx/omp wiki-adjacent "learned" stores should require triggers+source and score matches by trigger/tag with quality boosts.
- **Contract tests as the tier system** (tier-0 name/case/routing/docs tests instead of a frontmatter tier field): the "tier" is whatever CI refuses to let regress. Adaptation: pin each sibling's public entrypoints with equivalent contract tests rather than metadata.
- **Injection hygiene on skill content served through tools** (role-boundary tag stripping, 4000-char truncation, `..`-rejecting root validation): treat stored skills as untrusted input when re-injecting. Adaptation: any harness that re-injects its own markdown stores should copy these three guards verbatim.

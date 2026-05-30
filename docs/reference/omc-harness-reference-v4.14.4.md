# OMC Harness Reference — reverse-engineered for OMX/oms/omd

> **Purpose.** A version-pinned snapshot of *how oh-my-claudecode (OMC) builds a harness*, produced by
> reverse-engineering OMC to inform sibling harnesses (OMX = oh-my-experiments, and future oms/omd updates).
> When OMC updates, diff against this snapshot and update the dependent cards/skills (see §7 checklist).
>
> **Pinned to:** OMC `v4.14.4`, git sha `2733c168` (marketplace `Yeachan-Heo/oh-my-claudecode`).
> **Produced:** 2026-05-30. **Method:** 16-agent reverse-engineering workflow + 1st-source spot-checks.
> **Scope note:** this is a *pattern reference*, not an API contract. OMX re-implements these patterns in its
> own code and has ZERO runtime dependency on OMC. The risk surface that OMC updates can break is the **omha
> router cards**, not harness function — see §6.

---

## 1. What OMC actually is (not just markdown skills)

A **TypeScript-built orchestration engine** (`src/` → `dist/`), not a prompt bundle:
- ~40 skills (`skills/*/SKILL.md`) + ~28 agent definitions (`agents/`) + an MCP server (`bridge/mcp-server.cjs`).
- Plugin manifest: `.claude-plugin/plugin.json` (lists all skills, registers `./.mcp.json`, `./commands/`).
- Single MCP server registered as `t` → `node ${CLAUDE_PLUGIN_ROOT}/bridge/mcp-server.cjs`.
- Hooks: a single `hooks/hooks.json` registration; routing/discipline enforced by re-injecting text every turn
  (UserPromptSubmit), not by blocking.

## 2. `.omc/` state — a convention, not a created artifact

OMC writes state under the **repo root** by convention (`src/lib/worktree-paths.ts` `OmcPaths`):
```
<repoRoot>/.omc/
├── state/
│   ├── sessions/{sessionId}/{mode}-state.json   # per-session, per-mode (ralph/ultrawork/...) — session-isolated
│   ├── team/{teamName}/tasks/...
│   └── <mode>-state.json                         # legacy (pre-session) location
├── specs/                                        # deep-interview / autoresearch intake artifacts
├── autoresearch/{mission-slug}/runs/{runId}/{results.tsv, ledger, decision-log.md}
├── self-improve/topics/{slug}/{config,state,plans,tracking}/
├── ultragoal/                                    # append-only ledger
├── wiki/*.md                                     # keyword+tag knowledge base (no embeddings)
└── research/{session-id}/                        # sciomc stage artifacts
```
**Takeaway for siblings:** define your own top-level namespace (`.omx/`, never `.omc/`) and you are immune to
OMC's state-schema changes. `session_id` is mandatory in path getters to prevent concurrent-session leak.

## 3. MCP tools (source: `src/tools/*.ts`)

| Tool family | File | What it does |
|:--|:--|:--|
| `python_repl` | `tools/python-repl/` | persistent Python kernel namespaced by `researchSessionID`; load once, reuse across calls; `executionTimeout`/`projectDir`/`reset`/`get_state`. The grounding layer for exact arithmetic + plot generation. |
| `state_*` | `tools/state-tools.ts` | `state_write/read/clear` for `{mode, active, current_phase, session_id}` — arms persistent-mode Stop-hook loops. |
| `notepad_*` | `tools/notepad-tools.ts` | priority/working notes re-injected at SessionStart (`notepad_write_priority` <500 chars). |
| `wiki_*` | `tools/wiki-tools.ts` | ingest/query/lint/add; `[[page]]` links; append-only `log.md`. |
| `shared_memory_*` | `tools/shared-memory-tools.ts` | namespace+TTL key-value for inter-worker handoff. |
| `session_search` | `tools/session-history-tools.ts` | recall prior-session conclusions without re-deriving. |
| `project_memory_*` | `tools/memory-tools.ts` | `add_directive(priority=high)` survives compaction. |
| `ast_grep_*`, `lsp_*`, `trace_*` | resp. files | structural search / LSP / trace artifacts. |

## 4. Agents (source: `agents/` + `skills/omc-reference/SKILL.md`)

Read-only analysis lane (most relevant to an analysis harness): **scientist** (python_repl, data+stats+plot),
**tracer** (evidence-strength causal diagnosis), **analyst** (gap analysis, READ-ONLY), **critic** (pre-mortem,
READ-ONLY), **verifier** (completion-evidence), **architect**/**code-reviewer** (opus, READ-ONLY review pass).
Author≠review separation is structural (reviewers cannot Write/Edit). Model routing: haiku=lookup, sonnet=standard,
opus=architecture/deep analysis.

## 5. The reusable harness patterns (re-implement, do not import)

| Pattern | Verified source | Essence |
|:--|:--|:--|
| **Evaluator contract** | `src/autoresearch/contracts.ts` (`parseEvaluatorResult`) | `{pass: bool, score?: number}` JSON; bad/missing → **throw (loud-fail, never silent)**. |
| **keep-policy + auto-revert** | `src/autoresearch/runtime.ts` (`decideAutoresearchOutcome`) | `keep_policy: score_improvement`; non-kept iter → `git reset --hard last_kept_commit`. |
| **Decision-log 3-artifact** | `runtime.ts` (`appendDecisionLog`) | `results.tsv` + `ledger.json` + `decision-log.md` per run. |
| **Ambiguity-gated interview** | `skills/deep-interview/SKILL.md` | weighted dimension scoring, threshold gate (default 0.2), `pending approval` artifact. |
| **Evidence tags** | `skills/sciomc/SKILL.md` | `[FINDING]/[EVIDENCE:file:lines]/[CONFIDENCE:HIGH|MED|LOW]` + regex extraction. |
| **Evidence hierarchy + probe** | `skills/trace/SKILL.md` | controlled-repro > primary > inference > speculation; 3-lane (code/config/measurement) → discriminating probe. |
| **Sealed evaluator** | `skills/self-improve/scripts/validate.sh` | prevents evaluator self-modification (no self-grading). |
| **Tournament + re-benchmark** | `skills/self-improve/SKILL.md` | N candidates ranked; merge gated on no-regression re-benchmark; approach-family diversity (no 3x same family). |
| **Bounded stop** | autoresearch (max-runtime) / self-improve (plateau+circuit-breaker+max-iter) / sciomc (promise tags) | deterministic exit criteria. |

## 6. omha router coupling (the only real break-surface)

omha (`luckkim123/oh-my-heroacademia`) routes by reading `cards/*.json` — **the single source of truth**
(`src/omha/registry.py` line 1-2: "adding a harness = drop one JSON file; core never changes"). Two channels:
- **pull**: `hooks/route_emit.py` (UserPromptSubmit) injects a ROUTE line listing each card's name+description.
- **push**: `hooks/cross_lane_emit.py` (PreToolUse on Write/Edit/Skill) matches `triggers.{extensions, skills}`
  against the actual tool call and nudges a re-route. Fail-open (missing cards/bad json → silent exit 0),
  30s same-lane cooldown.

Card schema (A2A AgentCard subset): required `name, description, url, version, capabilities,
default_input_modes, default_output_modes, skills[]`; each skill `{id, name, description, tags, examples}`;
optional `triggers.{extensions, skills}`. **As of this snapshot, omha `cards/` holds only `omc.json` +
`superpowers.json`** (tier-1 lanes). oms/omd are 2nd-tier domain handlers in the cascade, NOT cards. OMX is
designed as a **tier-1 card** (`cards/omx.json`).

**Why this is the break-surface:** if OMC renames skills or changes its card description, the *router text*
shifts. A sibling card that references OMC internals would mis-route. Mitigation (already in OMX design): cards
use **keyword+intent only**, never OMC skill names; siblings self-register triggers in their own plugin.json.

## 7. Update checklist — when OMC bumps version

Run this when OMC is upgraded past `4.14.4` / `2733c168`:

1. **Re-pin:** record new OMC `version` + git sha; copy this file to `omc-harness-reference-v<new>.md` (keep the
   old as history).
2. **Diff skills:** `ls skills/` then `git -C <omc> log --oneline 2733c168..HEAD -- skills/ src/` — note added/
   removed/renamed skills and changed SKILL.md mechanics (esp. autoresearch/deep-interview/trace/sciomc/
   self-improve — the patterns §5 depends on).
3. **Diff MCP tools:** `ls src/tools/` — any renamed/removed tool that a sibling *calls* (OMX doesn't call any;
   oms/omd may). Update §3.
4. **Diff state schema:** grep `.omc/` path construction in `src/` — only matters if a sibling reads `.omc/`
   (none should).
5. **Re-verify omha card schema** (§6): if `src/omha/registry.py` `_CARD_REQUIRED`/`_SKILL_REQUIRED` changed,
   update every sibling card (`omc.json`, `superpowers.json`, `omx.json`, and any new oms/omd cards).
6. **Update siblings:** apply any pattern changes to OMX skills; refresh oms/omd if they borrowed OMC patterns.
7. **Pin in installer:** bump the OMC version pin in claudebase installer only after the above passes.

## 8. Source paths (verified 2026-05-30, OMC 4.14.4)

`marketplaces/omc/`: `.claude-plugin/plugin.json`, `bridge/mcp-server.cjs`, `.mcp.json`, `hooks/hooks.json`,
`src/autoresearch/{contracts,runtime,setup-contract}.ts`, `src/lib/worktree-paths.ts`, `src/tools/*-tools.ts`,
`src/tools/python-repl/`, `skills/{deep-interview,sciomc,trace,self-improve,autoresearch,ultragoal}/SKILL.md`,
`agents/`, `skills/omc-reference/SKILL.md`.
omha `marketplaces/heroacademia/`: `src/omha/registry.py`, `hooks/{route_emit,cross_lane_emit}.py`,
`cards/{omc,superpowers}.json`.

> Full design that consumes this reference: `oh-my-experiments` repo →
> `docs/design/2026-05-30-omx-experiment-harness-design.md`.

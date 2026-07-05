# OMC Deep Analysis — v4.15.2 (harness reference for om* siblings)

> **Purpose.** A version-pinned, source-level reverse-engineering of oh-my-claudecode (OMC) — the deepest
> reference we keep on *how a Claude Code harness is actually built* — produced to guide the redesign of the
> sibling harnesses (oh-my-experiments, oh-my-docs, oh-my-scholar, oh-my-project, oh-my-heroacademia).
> Siblings **re-implement** patterns in their own code and style; ZERO runtime dependency on OMC is a hard rule.
>
> **Pinned to:** OMC `v4.15.2`, git sha `d41f1730a71dfbb472424406a765efea5b5f10f0`
> (marketplace `Yeachan-Heo/oh-my-claudecode`). **Produced:** 2026-07-05.
> **Method:** 44-agent workflow — 18 subsystem analysts + 1 critic-discovered extra section, each section
> adversarially fact-checked by an independent verifier (every cited path opened, load-bearing line refs and
> quoted identifiers re-derived from source; wrong citations fixed in place), a coverage critic sweep, and
> 5 per-harness gap analysts. Final tally: 12 sections CORRECTED (1-4 fixes each), 7 CLEAN, **0 unverified
> claims left standing**.
> **Supersedes:** [`../omc-harness-reference-v4.14.4.md`](../omc-harness-reference-v4.14.4.md) (125-line
> summary — kept as history). **Companion:** [`../omc-wiki-skill-analysis.md`](../omc-wiki-skill-analysis.md)
> (wiki subsystem drill-down, pinned v4.14.5; still valid, cross-check against section 11).
> **Scope note:** a *pattern reference*, not an API contract. Citations are `path:line` against the pinned sha
> and will drift with upstream commits.

---

## What OMC is, in numbers (v4.15.2)

A TypeScript orchestration engine, not a prompt bundle: **40 registered skills** (matching 40 on-disk dirs 1:1),
**19 agent definitions**, **49 MCP tools in 11 families** on a single stdio server `t`, **22 hook command
registrations across 11 Claude Code events** funneled through one fail-open runner (`run.cjs`), a **~1500-line
PreToolUse enforcement gate**, an esbuild-bundled bridge (~172k lines, ~98.6% committed build output), and a
`bin/omc` CLI with six real external-model providers. Two implementation planes coexist everywhere: plugin
`.mjs` hook scripts and the TS bridge — and they drift (e.g. `DISABLE_OMC` parsing differs between them).

## Section index

| # | File | Covers | Verify |
|:--|:--|:--|:--|
| 01 | [01-manifest-install.md](01-manifest-install.md) | plugin.json / npm dual identity, reconciling installer, marker-fenced CLAUDE.md surgery, self-update re-exec + symlink-tombstone cache purge | CORRECTED(1) |
| 02 | [02-hooks.md](02-hooks.md) | all 22 hook registrations / 11 events, fail-open runner, magic-keyword arming, Stop-hook gauntlet, kill switches, echo-stripping | CLEAN |
| 03 | [03-mcp-bridge.md](03-mcp-bridge.md) | single MCP server `t`, tool registry as SSOT, hand-rolled Zod-to-JSON-Schema, orphan-proof shutdown, retreat from multi-server | CORRECTED(1) |
| 04 | [04-tools-state-memory.md](04-tools-state-memory.md) | `state_*` arm/cancel handshake, 3-tier notepad, project-memory TTL + PreCompact re-injection, shared-memory TTL KV, session_search, trace viewers | CLEAN |
| 05 | [05-tools-code-intel.md](05-tools-code-intel.md) | python_repl kernel lifecycle (locks, watchdog, sandbox), 12 lsp_* tools, ast-grep, deepinit_manifest, skills-listing tools | CORRECTED(3) |
| 06 | [06-mode-autopilot-ralph.md](06-mode-autopilot-ralph.md) | Stop-hook persistent-loop primitive, ralph/ultrawork state machines, autopilot 5-phase machine, ultraqa, circuit breakers | CORRECTED(2) |
| 07 | [07-mode-team-parallel.md](07-mode-team-parallel.md) | team shared task-list model, worker lifecycle, 29-op team API, ultrawork, tmux omc-teams runtime, failure handling | CORRECTED(2) |
| 08 | [08-planning.md](08-planning.md) | ambiguity scoring math (weights/threshold), deep-interview, ralplan consensus + stop-hook constants, plan handoff | CLEAN |
| 09 | [09-research.md](09-research.md) | sciomc stage pipeline + evidence tags, external-context facets, autoresearch evaluator contract / keep-policy / auto-revert / 3-artifact ledger | CLEAN |
| 10 | [10-selfimprove-goals.md](10-selfimprove-goals.md) | self-improve tournament + sealed evaluator + diversity rules, ultragoal durable ledger + quality gate, goal-workflows reconciler | CLEAN |
| 11 | [11-knowledge-lifecycle.md](11-knowledge-lifecycle.md) | wiki / notepad / project-memory / learned-skills lifecycle, capture-then-curate, skillify quality gate, writer-memory | CORRECTED(1) |
| 12 | [12-agents-catalog.md](12-agents-catalog.md) | all 19 agents, frontmatter contract (4 live keys), model routing economics, author-vs-reviewer tool blocklists, SDK registry | CORRECTED(3) |
| 13 | [13-hud-notifications.md](13-hud-notifications.md) | stateless HUD render pipeline, omcHud settings (5 presets/40+ toggles), 6 notification events, double-gated delivery, reply daemon | CLEAN |
| 14 | [14-cli-interop.md](14-cli-interop.md) | omc CLI bins, `omc ask` 6-provider pipeline, ccg tri-model orchestration, provider contracts, OMX interop tools, OpenClaw | CORRECTED(2) |
| 15 | [15-lib-config-state.md](15-lib-config-state.md) | **SSOT for `.omc/` on-disk layout**: 5-stage state-root resolution, full path-getter inventory, session envelopes, locks, branded ReadPath/WritePath | CLEAN |
| 16 | [16-skills-authoring.md](16-skills-authoring.md) | SKILL.md frontmatter parser, thin command stubs, install-time compaction (64KiB/2KiB budgets), builtin registry guards, 40-skill inventory table | CORRECTED(1) |
| 17 | [17-quality-verification.md](17-quality-verification.md) | verify/visual-verdict/debug/release contracts, cancel state machine, ralph completion gate (request-id-correlated independent reviewer) | CORRECTED(1) |
| 18 | [18-delta-engineering.md](18-delta-engineering.md) | v4.14.4→v4.15.2 delta (144 non-merge commits; multi-repo workspace support is THE feature), stale claims in the old reference, repo engineering, peripheral dirs | CORRECTED(4) |
| 19 | [19-delegation-enforcement-gate.md](19-delegation-enforcement-gate.md) | pre-tool-enforcer PreToolUse gate: tier-alias model resolution + injection, force-agent-delegation blocking, provider deadlock guards (critic-discovered section) | CORRECTED(1) |

## Cross-cutting patterns worth stealing (with section pointers)

1. **Fail-open everything, plus explicit kill switches** — every hook tolerates its own failure (timeout, bad
   JSON, missing state → exit 0) yet ships `DISABLE_OMC`/`OMC_SKIP_HOOKS` escape hatches (02, 15).
2. **Stop-hook persistent modes**: session-scoped state file + Stop hook returning `continue:false` with an
   injected prompt; cancel is a *signal-before-delete handshake*, not a file delete (04, 06).
3. **Independent verifier with request-id correlation** — ralph's completion gate rejects stale PASS tokens by
   binding approval to a per-attempt id; author and reviewer are structurally separated by tool blocklists (17, 12).
4. **Sealed evaluator / no self-grading** — validate.sh hard-fails when sealed files are modified (10, 09).
5. **Capture-then-curate knowledge lifecycle** — cheap automatic capture (hooks, `<remember>` tags) feeding
   gated promotion (quality-gate scoring) into flat-file registries (11).
6. **Enforcement beats prose**: the things OMC actually guarantees live in PreToolUse/Stop gates (model
   injection, delegation blocking), not in skill text (19, 02). Advisory text is used only where blocking is
   structurally impossible.
7. **Marker-fenced file surgery + reconciling installer** — idempotent install that owns only its fenced
   regions and re-execs the *new* binary post-update (01).
8. **Session-id hygiene** — ids are validated (`/^[A-Za-z0-9_-]$/`-class) and SHA-256-hashed before path use;
   state carries session envelopes to prevent cross-session leaks (05, 15).
9. **Deprecation as runtime redirect** — retired MCP tools still ship but return `isError` with the exact CLI
   migration command, so a mid-session model self-migrates (03).
10. **Two-channel identity, one version lifecycle** — plugin name ≠ npm name, both pinned by one sync script;
    version drift is made impossible rather than policed (01, 18).
11. **Bounded reads everywhere** — transcript tails capped (4MB HUD), lock waits capped (500ms shared-memory
    with unlocked fallback), hook timeouts (3s) — liveness beats completeness at every I/O boundary (13, 04, 19).
12. **Evaluator contract with loud-fail parsing** — `{pass, score}` JSON; malformed → throw, never silent
    (09); keep-policy + git auto-revert make bad iterations disappear.

## Gap analyses (per-harness adoption guidance)

Each file: harness philosophy → capability coverage table → prioritized adoption candidates (in the harness's
own idiom) → deliberately-not-adopting list.

| Harness | File | Verdict in one line |
|:--|:--|:--|
| oh-my-experiments | [gaps/oh-my-experiments.md](gaps/oh-my-experiments.md) | Analysis IP already at parity; real gaps are loop robustness — concurrency lock, git auto-revert half-missing, report integrity stamp |
| oh-my-docs | [gaps/oh-my-docs.md](gaps/oh-my-docs.md) | Brain already backported; gaps are enforcement teeth — Stop-hook verify guard, notepad prune/re-injection, model-injection enforcement |
| oh-my-scholar | [gaps/oh-my-scholar.md](gaps/oh-my-scholar.md) | Top leverage: turn the citation invariant from prose into a PreToolUse interlock; scoped Stop guard for scholar-revise; session-id state envelope |
| oh-my-project | [gaps/oh-my-project.md](gaps/oh-my-project.md) | Mature backport ledger (frozen at 4.14.4); leverage is small and omp-shaped — wiki lint axis, index-drift detector, ownership-hash guard |
| oh-my-heroacademia | [gaps/oh-my-heroacademia.md](gaps/oh-my-heroacademia.md) | Router patterns already reinvented; gaps are hook hygiene — sanitized state paths + reaper, kill switch, per-session cooldown, bounded tail-reads |

## Update checklist — when OMC bumps past 4.15.2 / d41f1730

1. **Re-pin**: record new version + sha; create `omc-deep-analysis-v<new>/` (or patch this bundle for small bumps)
   and banner-supersede this INDEX. Keep old bundles as history.
2. **Diff first**: `git -C <omc> log --oneline --no-merges d41f1730..HEAD` grouped by subsystem; section 18 shows
   the template. Only re-analyze sections whose territory changed.
3. **High-drift surfaces** (check every bump): skills list (16), MCP tool registry (03/04/05), hooks.json (02),
   pre-tool-enforcer (19), `.omc/` path getters (15).
4. **Re-run gap deltas**: omp's backport ledger and the omha router cards consume this reference — refresh
   `gaps/*.md` priorities against each harness's current state.
5. **Spot-check verification discipline**: any new section claims must carry `path:line` evidence and survive an
   independent citation check before merging here.

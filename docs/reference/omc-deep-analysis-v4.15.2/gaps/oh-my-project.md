# OMC → oh-my-project (omp) Gap Analysis

Target: `oh-my-project` v0.3.0 at `/root/.claude/plugins/cache/heroacademia/oh-my-project/0.3.0`
Reference: OMC v4.15.2 capability matrix + `/tmp/claude-0/-workspace/7c62943e-15f5-4896-a078-dce40d560894/scratchpad/omc-analysis/sections/*.md`

> **Read this first.** omp is not a naive sibling. It ships `references/omc-backport-analysis.md`, a
> deliberate adopt/exclude ledger (T1-T25) built against OMC 4.14.4 by reading OMC's own source, with
> 45 explicit refutations. Most obvious "OMC has X, omp lacks X" observations are already *decided
> absences* there, not omissions. This analysis therefore does two things: (1) confirm which OMC
> capabilities the backport ledger already dispositioned (so the author is not re-sold what they
> already rejected), and (2) surface the small set of genuinely-open leverage points — mostly the
> **v4.14.4 → v4.15.2 delta** the ledger has not yet seen, plus a few mechanisms omp gestures at in
> prose but never wired into code.

## Philosophy

omp is a **project-folder governance loop**, not a generation pipeline. Where its siblings (oms/omd)
produce a fresh artifact every run, omp continuously updates *one living `.omp/`* SSOT so the harness
"specializes in place — the more you use it, the more it knows your folder" (README). Its core
asymmetry: harness logic stays generic and immutable; only the per-project `.omp/` diverges
(`references/learning-protocol.md` §Identity). Four load-bearing invariants constrain every adoption
suggestion: (1) **single writer** — only the `organizer` agent moves files, `dataset-curator` writes
only manifest metadata, and detection (`auditor`, read-only) is structurally separated from execution
(README agent table); (2) **human gate on the heavy channel** — a `learned.md` observation never
becomes a `rules.json` rule without explicit approval, no matter how high the evidence count
(`learning-protocol.md` §6.B); (3) **deterministic grep only** — recall over `wiki/`/`learned.md` is
literal-match, embeddings are *permanently forbidden* because a "looks similar" false positive could
move a file into the wrong folder (`learning-protocol.md` §6.A); (4) **fail-open, stdlib, cross-platform**
— every hook is python3-stdlib + `pathlib` + per-OS trash, errors never block the session (README
Cross-platform; `hooks/omp_route_emit.py`). omp is a *domain* handler (project management); it never
picks the working-mode lane — omha does that upstream. Any OMC mechanism that assumes a Node runtime,
concurrent writers, throughput-over-safety, or opaque ranking is off-limits by construction.

## Capability coverage

| Area (OMC) | omp status | Evidence (omp repo) | Note |
|:---|:---|:---|:---|
| Plugin manifest + hook registration | HAS | `.claude-plugin/plugin.json` | 2 hooks (UserPromptSubmit/PostToolUse), no npm/dual-channel — intentionally single-channel plugin |
| Fail-open hook runner | HAS | `hooks/omp_route_emit.py`, `omp_verify_emit.py` (bare `except`→exit 0) | Python stdlib equivalent of OMC run.cjs fail-open; no timeout cushion (subprocess is trivially short) |
| Route-emit / stage checkpoint | HAS | `hooks/omp_route_emit.py` CHECKPOINT | Injects `STAGE(project) →` line; mirrors OMC routing card but domain-scoped |
| PostToolUse integrity reminder | HAS | `hooks/omp_verify_emit.py` | Deliberately avoids "fix before continuing" (OMC freeze pattern) — reminder tone only |
| Atomic state writes (temp+fsync+rename) | HAS | `hooks/omp_atomic.py` (T20) | Ported from OMC `dist/lib/atomic-write.js`; forced on all 4 JSON-writing skills |
| Ownership-marker deletion safety | PARTIAL | `references/safe-fileops.md` (copy-verify-delete, trash, boundary check T22) | omp guards *user file* moves richly, but has no `.omp-managed`/content-hash marker before it overwrites its *own* SSOT `.md` files |
| Symlink-escape / boundary containment | HAS | `references/safe-fileops.md` §Boundary check (T22, realpath ⊆ root) | Ported from OMC `worktree-cleanup-safety.js` |
| Install self-diagnosis (doctor) | HAS | `skills/omp-doctor/SKILL.md` (T21) | hooks/python3/reference-card checks; audit-overlap deliberately excluded |
| Magic-keyword / keyword-detector engine | NOT-APPLICABLE | — | Excluded (ledger: Node-runtime hook, ~300 LOC); routing is omha's job |
| Stop-hook continuation loop (ralph/autopilot) | ABSENT (deliberate) | ledger Exclude "persistent-mode Stop-hook enforcement" | File moves need human approval → auto-loop is a freeze/data-loss risk; organize's audit-PASS loop substitutes |
| Autonomous mode state machines | NOT-APPLICABLE | — | No autopilot-as-loop; omp-pilot is a gated stage weave, not a self-continuing machine |
| Parallel team / worker coordination | NOT-APPLICABLE | — | Single-writer invariant makes concurrent workers structurally forbidden (ledger concurrency-refutations) |
| Planning consensus (ralplan/deep-interview) | PARTIAL | `skills/omp-init/SKILL.md` gate (T8), `agents/rule-architect.md` (T4) | Adopted as *spirit* (Round-0 topology, 4-dim qualitative gate) but **ambiguity quantification excluded** (ledger: magic-number basis weak) |
| Research lane (sciomc/autoresearch) | NOT-APPLICABLE | — | Generation/execution domain, orthogonal to folder governance |
| Self-improve / ultragoal engines | NOT-APPLICABLE | — | Sealed-evaluator tournament is a code-optimization loop, out of domain |
| Wiki (append-merge, grep query, no embeddings) | HAS | `learning-protocol.md` §5, `output-layout.md` wiki/ | Directly the Karpathy model OMC uses; grep-only, append-only enforced |
| Learned-knowledge promotion gate | HAS | `learning-protocol.md` §3 (evidence≥3, 0 counter-examples, human gate) | Heavy-channel = OMC learner + notepad-priority, reimplemented in omp vocab |
| Wiki mechanical lint (orphan/stale/broken-ref) | PARTIAL | `hooks/omp_content_audit.py` `find_dead_links` | Has dead-link detection for `[[wikilinks]]`; lacks the other 5 OMC lint checks (stale/low-confidence/oversized/orphan/structural-contradiction) over `wiki/`+`learned.md` |
| Agent catalog + model routing + tool restriction | HAS | `agents/*.md` (5 agents, haiku/sonnet/opus, `disallowedTools` read-only) | Blocklist-only tool restriction identical to OMC posture; author≠reviewer separation enforced |
| Schema-validated state | HAS | `references/schemas/{rules,manifest}.schema.json`, `tests/test_schemas.py` | Stronger than OMC in-domain: rules/manifest are JSON-schema-validated with 13 tests |
| HUD statusline / notifications | NOT-APPLICABLE | — | No persistent statusline surface; out of scope |
| CLI / multi-model interop (ask/ccg) | NOT-APPLICABLE | — | No `omc ask` analog; omp delegates model choice to agent frontmatter only |
| MCP bridge server + tools | ABSENT (deliberate) | ledger T7 "MCP an optional accelerant — no new Node MCP is added" | `.omp/` .md/.json is the default handoff medium; MCP is a documented future swap point only |
| Session-scoped state / worktree-paths resolver | PARTIAL | SSOT fixed at `<project>/.omp/` (T15) | No `sessions/{sid}` layer (single-writer needs none); no `OMC_STATE_DIR`/marker resolver (single-repo assumption) |
| Verifier request-id / stale-PASS block | HAS | `agents/auditor.md` snapshot-id (T12), omp-audit Step 6 | rules.json hash + manifest SHA256 + violation-ID token blocks stale-PASS reuse across audit rounds |
| Delegation-enforcement PreToolUse gate | ABSENT | — | No pre-tool model-injection or spawn-evidence gate; agent model set in frontmatter, not enforced at call time |
| Docker/env governance | HAS (omp-native) | `skills/omp-env/SKILL.md`, `hooks/omp_docker_audit.py` | omp-original, no OMC analog |

## Adoption candidates (prioritized)

Ordered by leverage. Candidates 1-3 are **v4.15.2 delta** the backport ledger (frozen at OMC 4.14.4)
has not yet evaluated; 4-6 close small gaps between omp's own prose and its code.

### 1. Wiki mechanical lint — extend `find_dead_links` into a full 6-check `wiki-lint` (HIGHEST)

- **OMC mechanism**: six-check mechanical wiki lint (orphan / stale / broken-ref / low-confidence /
  oversized / structural-contradiction) that *reports but never auto-fixes*
  (`sections/11-knowledge-lifecycle.md`; OMC `src/hooks/wiki/lint.ts`). Also the append-only `log.md`
  chronicle recording reads as well as writes.
- **Why omp needs it**: omp's whole trust model is that `wiki/` and `learned.md` are the durable
  second brain, yet the only integrity check today is `find_dead_links` over `[[wikilinks]]`
  (`hooks/omp_content_audit.py`). A `wiki/` note that goes stale, an `OBS-NNNN` that has sat
  `candidate` for months with `counter_examples` silently accruing, or an oversized note that will
  never be recalled — none are surfaced. As specificity climbs toward 1 the knowledge layer grows and
  rots unobserved. Lint is *exactly* omp-shaped: read-only, deterministic, report-not-fix (matches the
  auditor's detect≠execute invariant).
- **Adaptation sketch**: add `hooks/omp_wiki_lint.py` (stdlib `re`+`pathlib`, mirroring
  `omp_content_audit.py`'s pure-function shape) with six deterministic checks scoped to `.omp/wiki/*.md`
  and `.omp/learned.md`: orphan (a `wiki/` note no other note `[[links]]` to), stale
  (`last_seen`/`## <ISO date>` older than N days), broken-ref (already have it — fold in), oversized
  (byte cap), stuck-candidate (`learned.md` block `status: candidate` past a staleness window), and
  contradiction (two `learned.md` blocks proposing conflicting `path_constraint` for the same glob).
  Surface it as a **new read-only axis inside `omp-audit`** (Step 2 axis list), so it rides the
  existing PASS/WARN gate with no new agent — `warn`-default like the docker axis, never blocking an
  overall PASS. Add tests alongside `tests/test_omp_content_audit.py`. Zero new hook-count cost (it's
  an audit axis, not a runtime hook — respects T24's "don't grow 2→3 hooks").

### 2. `workflow-drift-guard` reminder — an omp-native index-drift *detector* axis (HIGH)

- **OMC mechanism**: v4.15.0 added a Stop-hook `workflow-drift-guard.mjs`
  (`sections/18-delta-engineering.md`; OMC `templates/hooks/workflow-drift-guard.mjs`) — a
  post-hoc guard that catches when the session has drifted off the declared workflow.
- **Why omp needs it**: omp's single most-repeated real-world failure (documented twice in the
  CHANGELOG Unreleased section and both hooks) is **index drift** — a bare-hand `mv`/rename leaves
  `STRUCTURE.md`/`rules.json`/`DATASETS.md` pointing at the old path, forcing the user to say "update
  the index too." Today omp mitigates with a *prose reminder* in `omp_verify_emit.py` and organize
  Step 8, but nothing *detects* the resulting drift — it relies on the model reading the reminder. A
  drift *detector* would make the failure machine-visible instead of hope-based.
- **Adaptation sketch**: this is a natural companion to candidate 1 — add a `structure-drift` check to
  the same `omp-audit` axis: for every `structure.directories[].path` in `rules.json` and every path
  cited in `STRUCTURE.md`/`DATASETS.md`, verify the path still exists on disk (stdlib `Path.exists`).
  A rule pointing at a vanished/renamed folder = a drift violation, `warn` severity, handed off exactly
  like a naming violation. Do **not** make it a Stop-hook (that violates omp's no-freeze / fail-open
  discipline and T24 hook-count ceiling); make it a read-only audit finding the auditor already runs.
  This converts the CHANGELOG's recurring pain from "reminder the model may ignore" to "a PASS/FAIL the
  gate enforces."

### 3. `[1m]` / extended-context model-suffix awareness in agent frontmatter (MEDIUM)

- **OMC mechanism**: PreToolUse `[1m]` extended-context suffix detection that denies model params a
  sub-agent cannot inherit on Bedrock/Vertex, plus tier-alias resolution
  (`sections/19-delegation-enforcement-gate.md`; OMC `pre-tool-enforcer.mjs`).
- **Why omp needs it**: omp pins agent models in frontmatter (`agents/rule-architect.md` opus,
  `organizer.md` sonnet). On a Bedrock/Vertex host or a `[1m]` extended-context session, a hardcoded
  tier can fail to resolve or silently downgrade — the `rule-architect` (opus, the promotion-judgment
  agent) is exactly where a silent model downgrade would quietly weaken the most consequential gate.
- **Adaptation sketch**: omp cannot run OMC's Node PreToolUse enforcer (ledger correctly excludes it),
  and adding a model-injection hook would violate the 2-hook ceiling. The right-sized adaptation is
  **documentation, not code**: add a short "model-tier portability" note to `agents/*.md` (or a
  one-paragraph `references/` card) stating that tier names are advisory and that on Bedrock/Vertex
  the host resolves them — so a future maintainer does not add a `[1m]` suffix into frontmatter
  expecting inheritance. This is the honest low-ceremony fit; a runtime enforcer is over-engineering
  for a single-writer harness.

### 4. `.omp-managed` marker + content-hash before overwriting omp's own `.md` SSOT (MEDIUM)

- **OMC mechanism**: ownership-marker deletion safety (`.omc-managed` file + content-hash equality) so
  the harness never prunes user-authored artifacts (`sections/01-manifest-install.md`,
  `sections/15-lib-config-state.md`).
- **Why omp needs it**: omp closed the *write*-safety gap for JSON via `omp_atomic.py` (T20), and
  guards *user-file* moves via `safe-fileops.md`. But `omp-doc`/`omp-codify` regenerate the paired
  `.md` files (`STRUCTURE.md`/`NAMING.md`/`PROJECT.md`) *wholesale* (`output-layout.md`: "whole-file
  overwrite is reserved for the paired SSOT docs"). If a user hand-edits `STRUCTURE.md` between runs,
  the next regenerate silently clobbers their edits — the one place omp overwrites without the
  copy-verify-delete ceremony it applies everywhere else.
- **Adaptation sketch**: before an `omp-doc`/`omp-codify` wholesale `.md` regenerate, compute a hash of
  the current file and compare to a stored hash of *what omp last wrote* (keep it in
  `.omp/work/versions/` alongside the rules snapshots omp already keeps there). If they differ, the
  human touched it — surface a one-line "STRUCTURE.md was hand-edited since omp last wrote it; overwrite
  / merge / skip?" gate instead of a silent clobber. Reuses the existing `work/versions/` rollback
  layer and `omp_atomic.py`; no new subsystem.

### 5. Wiki `log.md` chronicle — an append-only read/write trail for `.omp/wiki/` (LOW-MEDIUM)

- **OMC mechanism**: append-only `log.md` chronicle that records *reads* (query/lint) as well as
  *writes* (`sections/11-knowledge-lifecycle.md`; OMC `query.ts:154`, `lint.ts:126`).
- **Why omp needs it**: omp's grep-recall trust model says "the same query returns the same notes every
  time; a human can run the identical grep" (`learning-protocol.md` §5). But there is no record of
  *which* notes were actually recalled and injected in a given session — so a user debugging "why did
  omp act on that stale decision" has no trail. A chronicle makes recall auditable, which is squarely
  omp's inspectability ethos.
- **Adaptation sketch**: add `.omp/wiki/log.md` (append-only, dated one-liners), written whenever a
  stage greps `wiki/` for recall or appends a note. Pure prose, grep-able, no schema (matches the
  "no database, no index" §5 trust model). Low priority because it is observability, not correctness —
  but it is nearly free and strengthens the audit story.

### 6. Stuck-candidate escalation nudge in `omp-learn` (LOW)

- **OMC mechanism**: OMC's learner + notepad TTL tiers actively age out and re-surface knowledge
  (`sections/04-tools-state-memory.md`, three-tier notepad with 7-day TTL).
- **Why omp needs it**: `learned.md` observations that never reach `evidence≥3` sit as `candidate`
  forever (`learning-protocol.md` §3: "Candidates that fail any condition stay `candidate`"). That is
  correct-by-design, but there is no mechanism to *notice* a candidate that has been stuck for many
  sessions — it just accumulates silently.
- **Adaptation sketch**: when `omp-learn` runs, have `rule-architect` additionally report any
  `candidate` whose `first_seen` is older than N sessions with `evidence_count` still below threshold,
  as an informational "these have been pending long — promote-with-caveat, reject, or leave?" line to
  the human. No new gate, no auto-action; folds into the existing learn pass. Overlaps with candidate 1
  (lint could surface the same signal) — pick one home for it.

## Deliberately not adopting

- **Stop-hook autonomous loops (ralph/autopilot/ultrawork continuation)** — file moves require human
  approval; an auto-continuing loop is a freeze and data-loss risk. omp's ledger already excludes this;
  organize's audit-PASS loop is the correct in-domain substitute.
- **Parallel team / worker coordination + task-claim leases** — omp is single-writer by invariant
  (only `organizer` moves files). Concurrent-write contention is *designed away*, so locks/leases solve
  a problem omp does not have.
- **Embedding / semantic recall** — permanently forbidden (`learning-protocol.md` §6.A): a
  "looks-similar" false positive could move a file into the wrong folder. Deterministic grep is the
  entire trust model.
- **MCP bridge server + 49 tools** — the `.omp/` .md/.json files do compaction-survival and handoff
  better for a single-writer loop, with no Node dependency (ledger T7). MCP stays a documented future
  swap point, not a build target.
- **Ambiguity quantification (weighted sum / threshold / stability_ratio)** — omp adopted the
  *qualitative* init gate but rejects the magic-number scoring: "what is this folder" is honestly a
  qualitative judgment (ledger Exclude).
- **Dual-channel npm distribution, re-exec update pipeline, cache self-repair** — omp is a single
  plugin channel; OMC's install/update machinery is scaled for a much larger, dual-distributed payload.
- **State-MCP `state_clear` 30s-cancel-signal machinery** — omp has no Stop-hook to unstick, so the
  cancel-signal handshake is a documentation-only future note (`omp-pilot` §"30s trap"), not code.
- **Session-scoped state paths / `OMC_STATE_DIR` marker resolver** — SSOT is fixed at
  `<project>/.omp/` (T15); a single-writer single-repo harness needs no `sessions/{sid}` layer or
  multi-workspace anchor climb.

# Gap Analysis — oh-my-docs (OMD) vs oh-my-claudecode (OMC v4.15.2)

> Sibling harness: `oh-my-docs` at `/root/.claude/plugins/cache/heroacademia/oh-my-docs/afbc970d752c`.
> OMD is a document-work harness (pptx/docx/xlsx/hwpx) that already performed a deliberate OMC backport
> (`references/omc-backport-analysis.md`). This analysis judges what OMD adopted, what it still lacks, and
> what it should not adopt — **with a hard rule of ZERO runtime dependency on OMC**: every candidate is a
> re-implementation in OMD's own `.omd/`-relative, stdlib-only, .md-degrade idiom.

## Philosophy

OMD is "**borrow the engine, build the brain**" (`README.md:3`): it drives python-pptx / python-docx /
python-hwpx / soffice / matplotlib but owns its own gates, verification, intake, and formula handling
rather than wrapping the pre-existing `ppt-*` skills. Its own load-bearing invariants, read from its docs:
(1) **stage-centric, format-as-variable** — the seven stages intake→standardize→plan→build→inspect→verify
(+revise/convert/translate/learn) are the axis; format is a parameter resolved by `references/formats/<fmt>.md`
cards that are the single source of truth (`README.md:11`, `route_emit.py`). (2) **No self-approval** —
`docs-inspect` (formative) and `docs-verify` (summative) are structurally separate lanes; `doc-verifier`
carries a triple ban (read-only tools + separate-pass + Role-not-responsible-for-authoring, `doc-verifier.md:31-35`).
(3) **Fresh evidence over "it opens"** — a PASS requires integrity 5/5 + full PNG read-through + shape assertion,
never a self-report (`doc-verifier.md`). (4) **Form specializes, content is preserved verbatim** — the learning
system learns style/layout, never a document's text/claims/numbers/sources (`learning-protocol.md:538-551`).
(5) **Deterministic-only, `.omd/`-relative, .md-default** — grep recall (no embeddings, permanently banned),
stdlib-only hooks (fail-open), MCP is an optional accelerator that always degrades to `.md` files, and all state
is work-root-relative (`wiki/README.md`, `output-layout.md:14`). (6) **Single sequential pipeline** — OMD
deliberately rejects parallelism for citation/content-bound work and prefers one careful build (`docs-pilot`
`Do_Not_Use_When`).

## Capability coverage

| Area (OMC) | OMD status | Evidence (OMD repo) | Note |
|:---|:---|:---|:---|
| **Routing hook (UserPromptSubmit checkpoint)** | HAS | `hooks/route_emit.py` | Injects `<omd-routing>` STAGE checkpoint; stdlib-only, fail-open — OMC's route_emit pattern ported. |
| **PostToolUse verify reminder** | HAS | `hooks/docs_verify_emit.py` | Freeze-safe variant of OMC post-tool-verifier; reminds (never "fix before continuing"); Bash-triggered on doc build/convert. |
| **Magic-keyword mode-arming engine** | ABSENT | `route_emit.py` (static text) | OMD hook is static checkpoint, no keyword parsing / mode-state files. Deliberate MVP choice. |
| **Stop-hook continuation loops (ralph/persistent-mode)** | PARTIAL (prompt-only) | `skills/docs-revise/SKILL.md:47` | "boulder never stops" reimplemented as a *prompt-level* loop with round caps + 3-recur stop; no Stop-hook enforcer (excluded, freeze risk). |
| **Ambiguity gate (deep-interview)** | HAS (qualitative) | `skills/docs-intake/SKILL.md:37-49` | Round-0 topology + 4-dimension clear/vague + challenge rounds. Deliberately drops OMC's weighted-sum/threshold quantification. |
| **Consensus planning (ralplan / RALPLAN-DR)** | HAS | `agents/doc-planner.md`, `docs-plan --consensus` | Options≥2 → steelman → ADR → converge to single arc. |
| **Autopilot brief→done orchestration** | HAS | `skills/docs-pilot/SKILL.md` | Gate-per-stage, fresh subagent per stage, controller-context protection. |
| **Agent catalog + author/reviewer separation** | HAS | `agents/*.md` (5 agents) | `disallowedTools` blocklist, model tiers, no positive allowlist — same shape as OMC. |
| **Verifier request-id / stale-PASS guard** | HAS | `doc-verifier.md:39` | Snapshot-correlation token (mtime/CRC + blocker IDs) binds PASS to the artifact — OMC verifier request-id ported. |
| **Wiki (append-merge, grep recall, no embeddings)** | HAS | `references/wiki/README.md` | Two-level (local + ascent-global) `.omd/wiki/`, confidence frontmatter, grep-only. |
| **Learner / promotion-with-human-gate** | HAS | `references/learning-protocol.md`, `skills/docs-learn` | Two-channel (heavy gated / light free); OBS ledger; human gate mandatory; form-only. |
| **Notepad (compaction-survival)** | PARTIAL | `docs-pilot/SKILL.md` Step (Priority Context) | `.omd/notepad.md` `## Priority Context` written on entry; MCP optional mirror. No 3-tier TTL pruning. |
| **State machine / session-scoped state files** | PARTIAL | `output-layout.md`, `.omd/<slug>/` | Fixed `.omd/<slug>/` workspace; no `sessions/{sid}`, no `_meta`/owner_pid liveness, no state MCP (excluded). |
| **Output-layout / deterministic slug + version snapshots** | HAS | `references/output-layout.md` | `{ISO}_{kebab}` slug, zero-padded `v{NN}`, outputs/ vs `.omd/` split, trash-based cleanup. |
| **Plugin-integrity / drift test** | HAS | `tests/test_plugin_integrity.py` | Enforces plugin.json skills ↔ dir 1:1 (caught `docs-learn` shipping dead). |
| **Hook regression tests** | HAS | `tests/test_route_emit.py`, `test_verify_emit.py`, `test_wiki_two_level.py` | Contract-tests both hooks + wiki ascent. |
| **MCP bridge server / in-process tools** | NOT-APPLICABLE | (none) | OMD drives engines directly; deliberately adds no Node MCP (`omc-backport-analysis §3` Exclude). |
| **Delegation-enforcement PreToolUse gate (model injection, spawn evidence)** | ABSENT | (none) | No pre-tool enforcer; agents dispatched by convention via `Task(subagent_type=...)`, unenforced. |
| **Team / parallel worker coordination** | NOT-APPLICABLE | `docs-pilot` `Do_Not_Use_When` | Single-sequential by philosophy (content/citation risk). |
| **HUD statusline / notifications** | ABSENT | (none) | No statusline, no Telegram/Discord/webhook. Out of stage scope. |
| **CLI / multi-model interop (ask/ccg/providers)** | ABSENT | (none) | No CLI; no external-LLM advisor. External help is `<External_Consultation>` (Context7→docs), not a model CLI. |
| **Kill switches / security posture (OMC_SECURITY, disable flags)** | ABSENT | (none) | Fail-open hooks only; no `DISABLE_OMD` / no `--no-wiki`-style global disable beyond one wiki flag. |
| **Self-improve / ultragoal / goal engines** | NOT-APPLICABLE | — | No code-optimization loop; domain-irrelevant (Exclude table). |
| **Terminal cleanup with recoverable-delete safety** | HAS | `output-layout.md:180-201` | Trash-first, per-OS, never touches `outputs/`, AskUserQuestion gate. |
| **Format-card API-trap knowledge (verified-render backed)** | HAS (OMD-native) | `references/formats/*.md` | Not an OMC concept — OMD's own safety pillar; every VERIFIED claim backed by a real render PNG. |

## Adoption candidates (prioritized)

### 1. A `docs-verify` PostToolUse *arm/confirm/enforce* handshake to stop premature "done" (highest leverage)
- **OMC mechanism**: the arm→confirm→enforce Stop gauntlet + SubagentStop verifier that computes a verdict
  (`sections/02-hooks.md`; OMC `src/hooks/persistent-mode`, `verify-deliverables.mjs`). OMC arms on
  UserPromptSubmit, confirms on first Skill call, enforces on Stop.
- **Why OMD needs it**: OMD's #1 failure mode is exactly "the model says done without a fresh render" —
  `doc-verifier.md:11` and `docs_verify_emit.py` both fight it, but today the PostToolUse reminder is *advisory
  text only*; nothing prevents the session from ending immediately after a build with no verify run. The
  reminder is easy to ignore under context pressure.
- **Adaptation (OMD idiom)**: add a stdlib-only **Stop hook** `hooks/docs_stop_guard.py`. On a doc-build Bash
  (the `docs_verify_emit.py` signal already exists — reuse `is_doc_build`), write a sentinel
  `.omd/<slug>/.verify-pending` with the artifact mtime. The Stop hook checks: if `outputs/<slug>/current.<ext>`
  exists AND `.verify-pending` mtime ≥ last verify-evidence mtime, emit `additionalContext` reminding that
  verify has not run on the current snapshot — **advisory, fail-open, never `decision:block`** (OMD already
  excluded hard Stop enforcement for freeze risk, `omc-backport-analysis §3`). This keeps OMD's freeze-safe
  posture while closing the "ended before verify" hole. Clear the sentinel when `doc-verifier` writes fresh
  evidence bound to that mtime (the token already exists at `doc-verifier.md:39`).

### 2. Notepad three-tier pruning + PreCompact directive re-injection
- **OMC mechanism**: three-tier notepad (priority ≤500 chars / working 7-day TTL / manual-never-pruned) and
  PreCompact directive re-injection (`sections/04-tools-state-memory.md`, `sections/11-knowledge-lifecycle.md`;
  OMC `src/hooks/notepad/index.ts:78-82`).
- **Why OMD needs it**: OMD already writes `## Priority Context` to `.omd/notepad.md` on pilot entry
  (`docs-pilot` Execution_Policy) specifically to survive compaction — but there is no *pruning* discipline, so
  a long or repeated pipeline grows the notepad unbounded, and nothing re-asserts the "no in-place edit / slug /
  gate-n" constraints after a compaction event.
- **Adaptation**: formalize `.omd/notepad.md` as three fenced sections — `## Priority Context` (the pilot
  constraints, never pruned), `## Working` (per-stage notes, drop entries older than the current job), `## Manual`
  (user-pinned). Add a PreCompact stdlib hook `hooks/precompact_reinject.py` that re-emits the `## Priority
  Context` block as `additionalContext` (fail-open, `.omd/`-relative). Pure .md + stdlib — no MCP, matching OMD's
  degrade-default.

### 3. Wiki mechanical lint (orphan / stale / broken-ref / oversized), report-only
- **OMC mechanism**: six-check mechanical wiki lint that reports but never auto-fixes, plus an append-only
  `log.md` chronicle of reads and writes (`sections/11-knowledge-lifecycle.md`; OMC `lint.ts`, `query.ts:154-159`).
- **Why OMD needs it**: OMD's two-level `.omd/wiki/` (`wiki/README.md`) accrues automatically via `docs-pilot`
  Step 7 with no health check. Over many jobs it drifts (stale defect patterns, broken `[[backlinks]]`,
  oversized files) with no signal — and OMD's own §4 reverse-review already *rejected* omp's dead-link checker as
  "nice-to-have", so a lighter report-only lint is the right size, not the omp regex engine.
- **Adaptation**: a small stdlib `scripts/wiki_lint.py` (invoked by `docs-learn`, not a hook) that greps
  `.omd/wiki/**` for: notes with no sighting in N days (stale), `[[ref]]` targets with no matching file
  (broken-ref), files over a byte budget (oversized), and `confidence: low` notes older than a cutoff (orphan
  candidate). **Report only** — matches OMC lint's "never auto-fix" and OMD's human-gate philosophy. Add a
  `.omd/wiki/log.md` append on every `wiki_query` so recall is auditable.

### 4. Frontmatter-strip agent loader + explicit-model injection enforcement
- **OMC mechanism**: markdown agents are SSOT, loaded via a frontmatter-stripping path-traversal-guarded loader,
  with a PreToolUse enforcer that injects the per-agent model and fails loud on unknown agents
  (`sections/12-agents-catalog.md`, `sections/19-delegation-enforcement-gate.md`; OMC `pre-tool-enforcer.mjs`).
- **Why OMD needs it**: OMD's 5 agents declare `model: opus` in frontmatter (`doc-verifier.md:4`) but nothing
  enforces that a dispatch actually uses that tier — a `Task(subagent_type="oh-my-docs:doc-verifier")` could run
  on a cheaper model, silently weakening the summative gate that OMD's whole trust model rests on.
- **Adaptation**: a stdlib PreToolUse hook `hooks/agent_model_guard.py` matching `Task` with
  `subagent_type` starting `oh-my-docs:`; read the agent's `model:` frontmatter from `agents/<name>.md`
  (relative to `CLAUDE_PLUGIN_ROOT`), and emit `additionalContext` if the requested model is absent/mismatched —
  **advisory (never deny)** to preserve fail-open. Keep it minimal: OMD does not need OMC's full tier-alias/`[1m]`
  machinery, only "the verifier ran on opus."

### 5. Delegation-compliance evidence gate for `docs-pilot` stages
- **OMC mechanism**: regex-parsed delegation gate rejecting completion unless the result carries a literal
  `Subagent spawn evidence:` / `Subagent skip reason:` line (`sections/07-mode-team-parallel.md`,
  `sections/19-delegation-enforcement-gate.md`).
- **Why OMD needs it**: `docs-pilot` mandates a *fresh subagent per stage* to protect controller context
  (`docs-pilot` Execution_Policy), but nothing checks the controller actually dispatched rather than doing the
  work inline — the exact context-pollution failure the design guards against.
- **Adaptation**: require each `docs-pilot` stage transition to print one line `OMD stage <n> → <spawned
  doc-<agent> | skipped: <reason>>`; a stdlib check in the Stop guard (candidate #1) that greps the transcript
  tail for the expected per-stage marker and warns if the pipeline reached terminal with stages missing their
  spawn/skip line. Advisory, evidence-driven, no new runtime.

### 6. Ownership-marker deletion safety for terminal cleanup
- **OMC mechanism**: `.omc-managed` ownership marker + content-hash equality so cleanup never prunes
  user-authored artifacts (`sections/01-manifest-install.md`, `sections/15-lib-config-state.md`).
- **Why OMD needs it**: `output-layout.md §5` cleanup deletes `.omd/<slug>/{renders,gen-image,tmp,versions}`
  via trash. It already excludes `outputs/`, but a user may have hand-dropped a keeper into `gen-image/`
  (a diagram they made) that the pipeline did not author — trash-recoverable, but still surprising.
- **Adaptation**: when the pipeline writes an intermediate, also write a sibling `.omd-authored` manifest
  (list of paths OMD created). Cleanup deletes only paths on that manifest whose content-hash is unchanged;
  anything else is surfaced in the AskUserQuestion tally as "not authored by OMD — keep?" This hardens the
  existing trash-first rule with provenance, in OMD's own `.omd/`-relative form.

### 7. Format-card version pinning for VERIFIED render claims
- **OMC mechanism**: verifier/gate claims bound to a measured snapshot; `RELEASE_RULE.md` caches derived rules
  with a last-analyzed stamp and re-derives on delta (`sections/17-quality-verification.md`).
- **Why OMD needs it**: format cards carry `[VERIFIED ✓ — 2026-06-16, measured on 1.0.2]` (CHANGELOG), but the
  installed python-pptx/soffice version can drift past the measured one, silently invalidating a trap claim the
  builder trusts. OMD's safety "leans on the fidelity of the card the builder reads" (CHANGELOG) — a stale
  VERIFIED is a direct correctness risk.
- **Adaptation**: `doc-builder`/`doc-verifier` read the engine version at build time (`python-pptx.__version__`,
  `soffice --version`) and compare to the card's `measured on` stamp; on mismatch, downgrade the affected
  VERIFIED claims to `UNVERIFIED (engine drift: card X, installed Y)` in the build notes and flag re-measurement.
  A small stdlib helper, no card rewrite — just a runtime guard around the card's own stamps.

## Deliberately not adopting

- **MCP bridge server / in-process tool registry** — OMD drives python-pptx/soffice directly; a Node MCP adds a
  runtime dependency it explicitly rejects (`omc-backport-analysis §3` Exclude; MCP stays an *optional* accelerator).
- **Team / parallel workers, ultrawork fan-out** — OMD is single-sequential by philosophy; content/citation-bound
  builds forbid parallelism (`docs-pilot` `Do_Not_Use_When`).
- **Hard Stop-hook enforcement (`decision:block`, persistent-mode loop)** — freeze risk; OMD keeps the revise loop
  advisory and freeze-safe (§3 Exclude; the PostToolUse reminder is deliberately *not* imperative).
- **Ambiguity quantification (weighted sum, threshold, stability_ratio)** — OMD chose a qualitative clear/vague gate;
  magic numbers have "weak rationale" for document work (`learning-protocol.md` H6, §3 Exclude).
- **Embedding / semantic wiki search** — permanently forbidden; deterministic grep only, so recall never surfaces a
  note that does not literally support the claim (`wiki/README.md` safety boundary; `learning-protocol.md §6.A`).
- **Self-improve / ultragoal / code-optimization loops, LSP / ast-grep / python_repl code-intel** — domain-irrelevant
  to document generation (`omc-backport-analysis §3` Exclude, code-only runtimes).
- **CLI + multi-model advisor (ask/ccg/providers)** — OMD's external help is doc-consultation (Context7 → official
  docs), not a model-CLI orchestration layer; adding one would exceed the document lane.
- **HUD statusline + Telegram/Discord/Slack notifications** — no stage need; OMD is a batch document pipeline, not a
  long-lived monitored session.
- **content_conventions / rules.json regex audit engine (omp reverse-backport)** — 0 adopted: OMD produces binary
  OOXML, so `scope: body|frontmatter` loses its referent and content is covered by the PPTEval rubric
  (`omc-backport-analysis §4`, all 5 REJECT).

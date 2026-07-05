# OMC Gap Analysis — oh-my-scholar (oms)

> Sibling harness: `oh-my-scholar` v0.5.0 (+Unreleased) at
> `/root/.claude/plugins/cache/heroacademia/oh-my-scholar/1940cc653448`.
> Reference snapshot: OMC v4.15.2 at `omc-analysis/omc`, detailed sections at `omc-analysis/sections/*.md`.
> oms already ships its own `references/omc-backport-analysis.md` — a deliberate OMC-4.14.4 adopt/exclude ledger.
> This analysis respects that ledger, then surfaces what the v4.14.4→v4.15.2 delta and unexploited leverage add on top.

## Philosophy

oms is a **domain handler for one thing: writing an academic paper as if it were code**, under a hard
**citation-integrity** invariant (README.md:2-19, `plugin.json`). Its axis is a stage pipeline —
init → research → deepen → ideate → outline (GATE1) → draft → inspect → mock-review → verify → revise
(GATE2) → submission (GATE3) → learn — bridging an `.md` concept-SSOT layer to a `.tex`/`.bib` paper layer
(README.md:21-46). Three load-bearing invariants govern every adoption decision:

1. **Reading is parallel, generation is single.** Reviewer/inspector/verifier may fan out read-only; the
   drafter is the *only* writer and is never parallelized (README.md:52, scholar-pilot/SKILL.md:27-30).
2. **No auto-fix, ever, on citations.** Even a verifier-detected missing `\cite` is flagged for a human,
   never patched (README.md:53, scholar_verify_emit.py:5-8, scholar-verify/SKILL.md:34).
3. **Lock concepts (.md) before drafting (.tex); deterministic recall only, embeddings permanently
   forbidden** (README.md:54, learning-protocol.md §6.A/§6.F).

Two more design commitments constrain what OMC machinery can cross over: oms is **stdlib-Python + `.md`-degrade-first**
(no Node MCP, no committed bundle — MCP is an *optional accelerator*, `.oms/*.md` files are the default:
omc-backport-analysis.md:30, scholar-pilot/SKILL.md:35-37), and it is **generation-domain, not management-domain**
— every run creates fresh `.tex`/`.bib`, so there is no persistent corpus to re-scan (omc-backport-analysis.md:99).
Its identity accrues as *data, not code*: shipped generic, specialized in place via a two-channel learning
protocol (heavy=gated venue defaults, light=grep-recalled wiki notes) rooted at a `.oms/` state dir that ascends
to a parent-folder global wiki (learning-protocol.md §1, §1.4). Adoption suggestions must not add runtime code
where a `.md` convention suffices, must not add any semantic/embedding retrieval, and must not weaken the
single-generation or human-gate boundaries.

## Capability coverage

| Area (OMC) | oms status | Evidence in oms | Note |
|:---|:---|:---|:---|
| Manifest / packaging / install reconciler (§01) | NOT-APPLICABLE | `.claude-plugin/plugin.json` only; no marketplace.json/install.sh/package.json | Plugin-only; distributed via heroacademia marketplace, no dual-channel npm. Deliberately out of scope. |
| Plugin.json ↔ skills 1:1 integrity | HAS | tests/test_plugin_integrity.py | Contract-test enforces no skill-registration drift (its own analogue of OMC's budget/roster tests). |
| Skill-body compaction (shims + skill-bodies/) (§01,§16) | ABSENT | skills/*/SKILL.md (full bodies inline) | 12 skills, bodies loaded directly. Startup-context budget not yet a concern at this size. |
| Hook runner (cross-platform, fail-open, timeout) (§02) | PARTIAL | hooks/*.py (`return 0` fail-open) | Fail-open discipline present; no shared runner/timeout cushion (only 2 stdlib hooks, direct `python3`). |
| Hook event coverage (11 events) (§02) | PARTIAL | plugin.json (UserPromptSubmit, PostToolUse) | 2 of 11 events. No SessionStart/PreCompact/Stop/SubagentStop. |
| Routing checkpoint injection (§02,§19) | HAS | hooks/scholar_route_emit.py | STAGE(paper) line, static, fail-open — mirrors OMD route_emit; domain-stage not lane. |
| PostToolUse verify reminder (§02,§11) | HAS (citation-safe variant) | hooks/scholar_verify_emit.py | Reminds-not-autofixes on `.tex`/`.bib` edit — deliberately inverts OMC's "fix before continue". |
| Magic-keyword engine (§02) | NOT-APPLICABLE | — | omha owns lane keywords; oms is domain-only. Correct exclusion. |
| Stop-loop continuation enforcer (§02,§06) | ABSENT (deliberate) | omc-backport-analysis.md:80 | Excluded: freeze/citation risk; the revise LLM loop suffices. |
| Autopilot orchestration (§06) | HAS | skills/scholar-pilot/SKILL.md | Paper-domain autopilot, 3 human GATEs, single-generation enforced. |
| Ralph loop-until-pass (§06,§17) | HAS | skills/scholar-revise/SKILL.md | Defect list = PRD, 3-strike stop, no-scope-reduction; +structural-regression re-verify (T13). |
| Reviewer request-id / snapshot correlation (§06,§17) | PARTIAL | agents/scholar-verifier.md:38,51 | Snapshot-token (mtime/hash + defect IDs) blocks stale-PASS; not the full per-attempt request_id UUID. |
| Consensus planning (planner/architect/critic, ADR) (§08) | HAS (absorbed) | agents/scholar-planner.md, scholar-outline `--consensus` | RALPLAN-DR ported into planner; no separate architect agent (T4/T5). |
| Deep-interview ambiguity gate (§08) | HAS (qualitative) | skills/scholar-deepen/SKILL.md | Round-0 topology + 4 dims + challenges — but *qualitative*, quantification deliberately dropped (T8). |
| Team / parallel worker coordination (§07) | ABSENT (deliberate) | omc-backport-analysis.md:52 | Single-sequential philosophy; parallel draft violates invariant #1. Read-only fan-out only (mock-review). |
| Research lane (evaluator contract, citation duty) (§09) | HAS (domain form) | skills/scholar-research, scholar-mock-review | Citation-bound research + venue-native mock review; no autoresearch loop. |
| Self-improve / evolutionary tournament (§10) | ABSENT (deliberate) | omc-backport-analysis.md:83 | Code-only runtime item, domain-irrelevant. |
| Knowledge lifecycle: wiki append-merge + confidence (§11) | HAS | references/wiki/README.md, learning-protocol.md §5 | `.oms/wiki/` grep recall, confidence frontmatter (H6 backport), 2-layer local+global ascent. |
| Notepad compaction survival (§04,§11) | PARTIAL (.md default) | scholar-pilot/SKILL.md:34-35 | `## Priority Context` in `.oms/notepad.md`; MCP mirror optional. No 3-tier TTL pruning. |
| Learned-skill quality gate / promotion (§10,§11) | HAS (domain form) | references/learning-protocol.md §3 | Heavy channel: evidence≥3, counter-examples=0, human gate; user_stated bypasses count-not-gate. |
| SSOT read-order enforcement | HAS | learning-protocol.md §8, tests/test_ssot_priority_and_sync.py | Primary outline/methodology > secondary research; Defect-A fix. Novel beyond OMC. |
| State dir layout / branded paths / locks (§15) | PARTIAL | references/output-layout.md, hooks/oms_atomic.py | `.oms/state/` fixed; atomic JSON write present. No branded ReadPath/WritePath, no O_EXCL locks, no session-id hashing. |
| Agent catalog: model routing + read-only tool restriction (§12) | HAS | agents/*.md (`model:`, `disallowedTools:`) | 6 agents, sonnet/opus tiers, blocklist tool restriction, author≠reviewer separation. |
| Author-vs-reviewer structural separation (§12,§17) | HAS | scholar-verifier.md:45-48 (triple ban) | Strong: frontmatter block + separate-lane + not-responsible list. |
| MCP bridge server / 49 tools (§03,§04,§05) | NOT-APPLICABLE | — | No Node bridge by design (`.md` degrade). MCP tools are optional future swap-points only. |
| HUD statusline / notifications (§13) | NOT-APPLICABLE | — | Domain harness, no runtime daemon surface. |
| CLI / multi-model interop (§14) | ABSENT (deliberate) | omc-backport-analysis.md:82 | Multi-perspective escalation conflicts with formative↔verify boundary. |
| Delegation-enforcement PreToolUse gate (§19) | ABSENT | plugin.json (no PreToolUse) | No model-injection / force-delegation gate. Leverage candidate (see below). |

## Adoption candidates (prioritized)

### 1. PreToolUse citation-write hard interlock (highest leverage — closes the one gap the whole harness exists to prevent)

- **OMC mechanism**: single fail-open PreToolUse gate on `*` with deny-with-feedback semantics
  (`permissionDecision:'deny'` while `continue:true`, so the agent retries corrected) — sections/19-delegation-enforcement-gate.md;
  `omc/templates/hooks/pre-tool-enforcer.mjs`. OMC uses it for model injection; the *mechanism* (a PreToolUse that
  can veto a specific tool-input shape and hand back a correction) is what matters.
- **Why oms needs it**: today citation safety is enforced only by *prose* — the route/verify hooks *remind*, the
  agents' frontmatter blocks *their own* Write, but nothing structurally stops the **main session** (or any
  write-capable agent) from adding a `\cite{...}` to `.tex` whose key is absent from `.bib`, or appending a
  fabricated `@article{...}` to `.bib` without human confirmation. scholar_verify_emit.py fires *PostToolUse* — after
  the write already landed. Invariant #2 ("no auto-fix, human confirms before editing .bib") has no runtime backstop.
- **Adaptation sketch** (`hooks/scholar_cite_guard.py`, stdlib, fail-open, registered on PreToolUse matcher
  `Edit|Write|MultiEdit`): when `file_path` ends `.bib` and the edit *adds* a new `@type{key,` entry, emit
  `{"hookSpecificOutput":{"permissionDecision":"deny","permissionDecisionReason":"<oms> new .bib entry needs human confirmation — no fabricated citations (README §2). Confirm the source, then re-issue."}}`;
  when `file_path` ends `.tex` and a diff adds `\cite{K}` whose `K` is not yet in any sibling `.bib`, deny with a
  "verify the key exists first" reason. Any parse error → `return 0` (fail-open, never block real work). This turns
  the load-bearing invariant from a reminder into an interlock, without embeddings and without auto-fixing —
  exactly the citation-safe posture (it *stops*, it never *invents*).

### 2. Stop-hook completion enforcer for scholar-revise, gated by the 3-strike/GATE ladder (leverage: makes ralph real)

- **OMC mechanism**: the "boulder never stops" Stop-loop enforcer (persistent-mode.mjs) behind a hard-exemption
  ladder + staleness TTL, and the ralph completion gate that only honors an approval token authored inside an
  *independent reviewer subagent's* tool_result keyed to a per-attempt request_id — sections/02-hooks.md,
  sections/17-quality-verification.md; `omc/src/hooks/persistent-mode/`, `omc/src/modes/ralph/verifier.ts:335`.
- **Why oms needs it**: scholar-revise is described as "the paper-edition of ralph" (scholar-revise/SKILL.md:10) but
  is **prompt-only** — nothing re-injects when the model stops early with FAIL items still open, so a revise loop
  can quietly abandon before `passes:true`. oms *deliberately excluded* the Stop enforcer (omc-backport-analysis.md:80,
  citing freeze/citation risk), and that exclusion is right for a blunt "never stop" loop. But a **scoped, exemption-laden**
  Stop hook that only fires while a `.oms/state/revise-active.json` marker is live, and self-releases on 3-strike /
  GATE2 / human-abort / staleness, gets ralph's guarantee without the freeze risk.
- **Adaptation sketch**: scholar-revise writes `.oms/state/revise-<slug>.json` (`{active, strikes, last_fail_ids, owner_pid}`,
  via oms_atomic). New `hooks/scholar_stop_guard.py` (Stop event): if the marker is active AND the transcript tail shows
  unresolved FAIL items AND strikes<3 AND no GATE2 confirmation AND marker age<TTL, emit a continue-block reminder
  ("revise not complete — N FAIL items open, run scholar-verify on fresh evidence"); otherwise allow stop. Citation-content
  defects (fixable_by_llm=false) are in the exemption set — never loop those (invariant #2). This is the OMC ladder
  (seven-rung exemption + TTL) narrowed to one skill and one marker, so it can't strand a citation-bound session.

### 3. Verifier per-attempt request-id, upgrading the existing snapshot token (leverage: hardens the anti-stale-PASS guard oms already half-built)

- **OMC mechanism**: reviewer approval keyed to a per-attempt request_id UUID matched inside the reviewer's
  tool_result, so a stale approval from a prior round cannot be replayed — sections/17-quality-verification.md;
  `omc/src/modes/ralph/verifier.ts:335`, `verify-deliverables.mjs`.
- **Why oms needs it**: scholar-verifier already binds a PASS to a snapshot identifier (mtime/hash + defect IDs;
  scholar-verifier.md:38,51) and explicitly says it adopted *only* the "bind target snapshot to PASS" core, not the
  full request-id infra. In a multi-round scholar-revise, the weak point is that the *round* itself isn't identified:
  two rounds touching the same files at the same mtime granularity could collide, and there is no controller-issued
  token proving "this PASS answers *this* revise request."
- **Adaptation sketch**: scholar-revise mints a `round_id` (uuid) per loop iteration and passes it in the verifier
  `Task(...)` prompt; scholar-verifier echoes `round_id` + snapshot-hash in its verdict block; scholar-revise rejects
  any verdict whose `round_id` ≠ the current round's. Pure prompt-contract change (no code) — it lifts the existing
  snapshot token from "same file state" to "same request", the cheap 80% of OMC's request-id guarantee that fits a
  single-sequential harness.

### 4. Session-scoped state envelope + O_EXCL marker for `.oms/state/` (leverage: multi-session safety for a long pipeline)

- **OMC mechanism**: session-scoped mode-state with an `_meta` ownership envelope (sessionId, owner_pid),
  O_EXCL PID-payload locks with age-AND-dead-PID stale reaping, and completion-evidence gating so `/cancel` can't
  kill a live parallel session — sections/15-lib-config-state.md, sections/06-mode-autopilot-ralph.md;
  `omc/src/lib/worktree-paths.ts`, `omc/src/lib/session-state.ts`.
- **Why oms needs it**: `.oms/state/` is a flat fixed path (scholar-pilot/SKILL.md:36) with no session id and no lock.
  A user running two paper sessions in the same folder (a common academic pattern: revising paper A while drafting B
  under one workspace) would have pilot/revise markers collide, and the candidate hooks in #1/#2 would read each
  other's state. oms already ships oms_atomic.py, so the write-atomicity half is done; the ownership + locking half isn't.
- **Adaptation sketch**: extend oms_atomic with an `_meta:{session_id, owner_pid, updated_at}` envelope on every
  state write, and add an O_EXCL `.oms/state/<mode>-<slug>.lock` (PID payload, reaped when age>30s AND PID dead) that
  scholar-pilot/scholar-revise acquire before their marker write. Keep it `.md`/JSON-file-only (no MCP), matching the
  degrade-first rule. This is OMC's envelope pattern minus the branded-type TS machinery — the parts that survive in a
  stdlib-Python harness.

### 5. `--from` resume via durable state read (leverage: pipeline restartability the docs already promise)

- **OMC mechanism**: SessionStart restore-and-advise blocks that read durable state and re-inject progress without
  auto-resuming a loop (advisory-only), plus PreCompact directive re-injection — sections/02-hooks.md, sections/11;
  `omc/src/hooks/session-start/`.
- **Why oms needs it**: scholar-pilot advertises `--from <stage>` and "resumable after interruption" via `.oms/state/`
  (scholar-pilot/SKILL.md:33,71), but there is no SessionStart hook and no reader that reconstructs "you were at draft,
  GATE1 approved, 2 FAIL items open" after a compaction or a new session. The Priority-Context notepad write (line 34)
  is the *only* survival mechanism, and it's model-discipline, not a hook.
- **Adaptation sketch**: `hooks/scholar_resume_emit.py` on SessionStart: if `.oms/state/pilot-<slug>.json` exists and
  is non-terminal, inject an advisory `<oms-resume>` block naming the last completed stage, the current GATE, and open
  FAIL ids — advisory only, never auto-continues (respects the "GATEs must be broken by a human" rule,
  scholar-pilot/SKILL.md:23,31). Reuses the state files from #4. Low code, high "pick up where I left off" value for a
  multi-day paper.

### 6. Notepad 3-tier TTL discipline for `.oms/notepad.md` (leverage: keeps the compaction-survival note from rotting)

- **OMC mechanism**: three-tier notepad — priority (replace, ≤500 chars) / working (append, 7-day TTL) / manual
  (never pruned) — sections/04-tools-state-memory.md, sections/11-knowledge-lifecycle.md;
  `omc/src/hooks/notepad/index.ts:78-82`.
- **Why oms needs it**: oms writes citation-safety constraints + current GATE into `## Priority Context` of
  `.oms/notepad.md` (scholar-pilot/SKILL.md:34) but has no pruning discipline — across a multi-week paper the notepad
  accretes stale GATE positions and old unverified-citation lists, and the model re-reads them as if current.
- **Adaptation sketch**: adopt only the *sectioning convention* (not the MCP): `## Priority Context` = replace-on-write
  (always current GATE + live constraints), `## Working Notes` = dated append, prune entries >7 days at pilot entry,
  `## Manual` = never pruned. A dozen lines in scholar-pilot's Priority-Context step + a note in output-layout.md.
  Pure `.md` convention, zero runtime code — the degrade-first-correct version of OMC's tiered notepad.

## Deliberately not adopting

- **Team / parallel-worker coordination bus (§07)** — parallel *generation* violates invariant #1 (single, careful
  draft). Read-only fan-out (mock-review's 3 lenses) already covers the only safe parallelism. (Author's own call:
  omc-backport-analysis.md:52.)
- **Embedding / semantic / similarity retrieval anywhere (§03,§11)** — permanently forbidden: semantic recall surfaces
  notes that don't literally support a claim, the exact citation-hallucination failure oms exists to prevent
  (learning-protocol.md §6.A/§6.F). Deterministic grep only, now and forever.
- **Auto-fix on verify (OMC's "fix before continuing" PostToolUse) (§02)** — inverted on purpose to reminder-only;
  auto-fixing citations = inventing them (scholar_verify_emit.py:5-8).
- **Self-improve evolutionary tournament / sealed-evaluator (§10)** and **CLI multi-model interop / ccg (§14)** —
  code-only runtime engines, domain-irrelevant to single-sequential paper generation (omc-backport-analysis.md:82-83).
- **Node MCP bridge + committed bundle (§03,§05)** — oms is stdlib-Python, `.md`-degrade-first; MCP tools are named
  only as optional future swap-points behind abstract functions like `wiki_query` (omc-backport-analysis.md:30,
  wiki/README.md:104). Adding a bundle would break the "no new Node MCP" rule.
- **Ambiguity quantification (weighted sum / threshold / stability_ratio) (§08)** — deepen is a *qualitative* gate on
  purpose; a magic-number ambiguity score is weak evidence for whether a paper's contribution is sharp
  (omc-backport-analysis.md:81).
- **Manifest / npm dual-channel / install reconciler / HUD / notifications (§01,§13)** — plugin-only distribution via
  the shared marketplace; these are host-harness concerns, not a domain handler's.
- **omp 0.2.0 content-conventions regex engine / dead-link `[[backlink]]` audit** — already refuted in oms's own
  reverse-review (omc-backport-analysis.md §4): oms is a generation pipeline with no persistent corpus to regex-rescan,
  and its cross-references are `\cite`/`\ref` (fully covered by scholar-verify), not wikilinks.

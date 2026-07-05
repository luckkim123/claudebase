# oh-my-experiments (OMX) — Gap Analysis vs OMC v4.15.2

> **Deepened (2026-07-05).** A 7-cluster, adversarially verified omx-side audit supersedes-and-extends
> this file's omx view: `oh-my-experiments/docs/2026-07-05-omc-v4.15.2-alignment-audit.md` (omx repo,
> commit `3655248`) — 27 new findings (headline: no sealed-evaluator guard, unbounded TB ingest,
> author≠reviewer absent on report.md), 6 corrections to this file, and a consolidated 31-item roadmap
> that re-prioritizes the 6 candidates below. Read that audit first; this file remains the OMC-side view.

> Sibling harness at `/root/oh-my-experiments`. Experiment-analysis harness: `exp-init` / `exp-analyze` /
> `exp-design` / `exp-loop` skills over an `omx` CLI and `.omx/` JSON state. Source-of-truth repo.
> OMC studied only as a *reference* — OMX has a hard ZERO-runtime-dependency rule (design D1). Every
> adoption suggestion below is a *pattern to re-implement in omx-core Python*, never an import.

## Philosophy

OMX is a **self-contained, discipline-first analysis harness**, not a general orchestrator. Its job is (a)
analyze N RL/ML runs into an evidence-tagged `report.md` and (b) design the next experiment — never to write
model code or launch training. Its invariants, from its own docs:

- **Zero runtime dependency on OMC** (design D1/D2/§2). OMC is a pattern reference; OMX reads its own `.omx/`
  namespace and is immune to OMC version changes. The interface floor is deliberately "Bash runs Python + file
  IO" — the most version-resilient CC surface (§11). No custom MCP, no hooks, no subagents (`plugin.json` lists
  only 4 skills; `find` confirms no `hooks`/`agents`/`.mcp.json`).
- **Python core + thin skills.** All testable logic lives in `omx-core` (135 Claude-free tests); skills are thin
  orchestrators. Discipline is enforced by *code*, not agent goodwill (design D8, `profile.py:5`).
- **Path discipline is a first-class feature.** `omx_paths.py` is the single source of truth for every path
  (`omx_paths.py:2-4`); the `.omx/` schema is fixed (never ad-hoc); every id is regex-validated with loud-fail,
  never silent-fallback (`omx_paths.py:28-31`).
- **Never auto-delete; never auto-launch training.** Cleanup is a dry-run→diff→approve→trash ritual (design
  §10.3); the "leaving-work" deadline governs analyze/design/eval only — the next launch is *queued* as a
  `pending approval` artifact and never fired (design D4/B8, `loop.py:63-89`).
- **Append-never-destroy knowledge.** The wiki merges on slug collision (INV-2, `wiki/ingest.ts` header), lint
  reports but never auto-fixes (INV-1, `wiki/lint.py:1`), removal is the git-guarded two-phase `gc`/`gc-apply`
  path — there is deliberately no `delete` subcommand.
- **Evidence over assertion.** Findings carry `[FINDING]/[EVIDENCE]/[CONFIDENCE]` tags parsed deterministically
  (`report.py`); the coverage lint blocks a report that skips diagnostic groups or the engine (`coverage.py`).

These invariants mean OMX has *already* re-implemented OMC's most valuable analysis-lane patterns (evaluator
contract, keep-policy decision tree, 3-artifact ledger, ambiguity-gated interview, wiki, evidence tags). The real
gaps are in **operational robustness of the autonomous loop** and **the capture-then-curate lifecycle** — not in
the analysis IP, which is at parity or better.

## Capability coverage

| OMC capability (area) | OMX status | Evidence (OMX repo) | Note |
|:--|:--|:--|:--|
| **Evaluator contract** `{pass, score?}`, loud-fail on bad JSON | HAS | `evaluator.py`, `decision.py:20-33` | Direct re-impl of `contracts.ts parseEvaluatorResult`. |
| **Keep-policy decision tree** (pass_only / score_improvement + bootstrap-keep) | HAS | `decision.py:50-91` | Mirrors `runtime.ts decideAutoresearchOutcome` incl. bootstrap branch. |
| **3-artifact ledger** (results.tsv + ledger.json + decision-log.md) | HAS | `ledger.py:24-163` | Byte-identical TSV header; B6 hybrid checkpoint-pointer added on top. |
| **Ambiguity-gated Socratic interview** (weighted dims, threshold, pending-approval) | HAS | `skills/exp-init/SKILL.md`, design §4.1 | Maps 5 experiment topics onto deep-interview's 3 weighted dims. |
| **Evidence tags** `[FINDING]/[EVIDENCE]/[CONFIDENCE]` | HAS | `report.py:22-24` | From sciomc; parsed deterministically for exp-design/loop. |
| **Discriminating-probe design** (trace 3-lane → next config) | HAS | `skills/exp-design/SKILL.md` | trace pattern re-implemented as the exp-design core. |
| **Append-merge wiki, keyword+tag, no embeddings, CJK** | HAS | `wiki/{ingest,query,storage}.py` | Full 8-file re-impl; slug-hash fallback, `[[links]]`, log.md chronicle. |
| **Six-check mechanical wiki lint (report-only)** | HAS | `wiki/lint.py` | Adds `near-duplicate` (Jaccard≥0.5) beyond OMC's six. |
| **git-guarded knowledge removal (no destructive delete)** | HAS | `wiki/gc.py` | Two-phase gc/gc-apply; stricter than OMC's `wiki_delete`. |
| **Report-completeness / coverage lint** | HAS | `coverage.py` | OMX-original (GAP 4); OMC has no per-report vocabulary lint. |
| **Path SSOT + id regex validation + atomic writes** | HAS | `omx_paths.py` (whole) | `atomic_path`/`atomic_dir`; 2-tier structural+vocabulary validation. |
| **Max-runtime deadline ceiling** (analyze/design/eval) | PARTIAL | `loop.py:27-54` | Pure compute-only; no Stop-hook enforcer (no hooks by design) — the deadline is *advisory*, the skill must voluntarily honor it (`exp-loop/SKILL.md:56`). |
| **git-native auto-revert (`git reset --hard last_kept`) + dirt allowlist** | ABSENT | design B6, `ledger.py:8-18` | B6 *locked the direction* (config→git, weights→pointer) but exp-loop's git-revert primitive + reset-safety allowlist is unimplemented (design §9 carry). Only the pointer half exists. |
| **Two-lock concurrency guard** (active-run lock + EXCLUSIVE_MODES) | ABSENT | `state.py`, `cli.py` (no state wiring) | `state.json` schema exists (`state.py:12-17`) but no getter writes/reads it; two concurrent `exp-loop`s on one `.omx/` have no mutual exclusion. Repo runs concurrent multi-GPU sessions (design §10.2). |
| **Confidence-gated setup handoff** (inferred < 0.8 → not launch-ready) | ABSENT | `skills/exp-init/SKILL.md` | exp-init has the ambiguity gate but no numeric confidence floor on an *inferred* evaluator; `pending_approval` is boolean-only (`profile.py:73`). |
| **Cross-session state read/list** (`state_list_active`, ownership `_meta`) | ABSENT | `state.py:12-17` | No `active_loop` writer, no owner-pid/liveness envelope, no "who is running" query. |
| **SessionEnd/PreCompact auto-capture** (cheap bounded stub → curate later) | ABSENT | (no hooks) | Wiki write is fully manual (`omx wiki add`); nothing captures a run's findings automatically at session end. |
| **Format-drift guard on the deliverable** (report can't be hand-edited past gates) | PARTIAL | CHANGELOG 0.1.14, `exp-analyze/SKILL.md:142` | Rule is *prose-only* ("NEVER hand-Edit report.md"); no mechanical guard (coverage lint counts tokens, not visual format — proven bypassable in the 0.1.14 incident). |
| **Visual-verdict numeric gate + mandatory rerun loop** | ABSENT | `exp-analyze/SKILL.md` | exp-analyze reads PNG plots via vision but has no structured pass/score verdict contract on a plot. |
| **Autonomous execution modes** (autopilot/ralph/team/ultrawork) | NOT-APPLICABLE | — | Out of scope: OMX is analyze→design→loop, not a general orchestrator (design D6). |
| **Plugin install/manifest/MCP-bridge/HUD/notifications/agents** | NOT-APPLICABLE | — | Deliberately minimal-surface (§11); adopting these would violate D1/D3. |
| **Delegation-enforcement PreToolUse gate, model routing** | NOT-APPLICABLE | — | No subagents; nothing to delegate/route. |

## Adoption candidates (prioritized)

Ordered by leverage. Each is a Python re-implementation in `omx-core`, never an OMC import.

### 1. Two-lock concurrency guard for `exp-loop` (highest leverage)

- **OMC mechanism**: `09-research.md:127,187` — autoresearch refuses to start on either (1) an active-run lock
  in `.omc/state/autoresearch-state.json` (`autoresearch_active_run_exists`) or (2) an `EXCLUSIVE_MODES`
  registry check across *all* sessions (`runtime.ts:394-412`, `assertModeStartAllowed`). Owner-pid liveness +
  stale reaping live in `15-lib-config-state.md` (`DEFAULT_STALE_LOCK_MS=30_000`, age-AND-dead-pid).
- **Why OMX needs it**: OMX's own design (§10.2) cites the repo's concurrent multi-GPU sessions as the reason
  for the run/session 2-axis split — yet `state.json` (`state.py:12-17`) has an `active_loop` field that *no
  code ever writes or checks*. Two `exp-loop`s launched against the same `.omx/runs/<run_id>/` will both seed
  the ledger, interleave `record_iteration` writes, and corrupt the decision trail. This is the single biggest
  correctness hole in the autonomous path.
- **Adaptation sketch**: add `omx_core/lock.py` with an `O_EXCL` PID-payload lock keyed by `run_id`
  (`.omx/runs/<run_id>/.loop-lock`) plus an `active_loop` writer in `state.py` recording
  `{run_id, session_id, owner_pid, started_at}`. `exp-loop` step 0 calls `omx loop-acquire <run_id>
  --session-id ...`; it loud-fails `OmxError("loop already active for <run_id> (pid <n>, session <sid>)")` unless
  the recorded pid is dead OR `started_at` is older than a 2h stale threshold. Mirror OMC's age-AND-dead-pid
  reaping so a crashed loop self-heals. Wire release into `omx clean --scope session` and loop-stop. Keeps the
  no-hooks rule: the guard is a CLI verb the skill calls, not a PreToolUse gate.

### 2. git-native auto-revert primitive with a dirt allowlist (B6's missing half)

- **OMC mechanism**: `09-research.md:125,182` — `resetToLastKeptCommit` runs `git reset --hard <last_kept>`
  only after `assertResetSafeWorktree` proves the worktree carries no dirt beyond a named
  `AUTORESEARCH_WORKTREE_EXCLUDES` list, else throws `autoresearch_reset_requires_clean_worktree:<path>`
  (`runtime.ts:363-369,1222-1225`). The exclude list is also written into git `info/exclude`.
- **Why OMX needs it**: OMX design B6 *locked* the hybrid-revert direction (config edits → git revert; trained
  weights → `last_kept_checkpoint` pointer) and `ledger.py` records `baseline_commit`/`last_kept_commit` — but
  the actual git-revert-on-discard is deferred to "build #6" and never landed (design §9 carry: "the actual git
  revert" is exp-loop's job). Today a discard *leaves the checkpoint pointer* but does nothing to config edits,
  so a rejected config change silently persists into the next iteration — the exact "minimum-change revert" /
  confounding failure the repo's own rules warn against (`.claude/rules/03` Minimum-Change Revert).
- **Adaptation sketch**: add `omx_core/revert.py::revert_config_to(baseline_commit, *, allow)` that
  `subprocess`-runs `git status --porcelain`, asserts every dirty path is in `allow`
  (`{results.tsv, ledger.json, decision-log.md, .omx/}` — the OMX runtime droppings), then `git reset --hard`.
  Loud-fail `OmxError` on any un-allowed dirt (never silent clobber). `record_iteration` on a `discard` calls it
  for config-lane candidates; weight-lane candidates keep the pointer-only behavior already coded
  (`ledger.py:142-149`). This closes B6 without touching the pointer half.

### 3. Confidence-gated evaluator handoff in exp-init

- **OMC mechanism**: `09-research.md:161,188` — `AUTORESEARCH_SETUP_CONFIDENCE_THRESHOLD = 0.8`; an *inferred*
  evaluator below 0.8 "cannot be marked readyToLaunch", and a blocked handoff must carry a
  `clarificationQuestion` (`setup-contract.ts:92-98`). (A claim that the file's comment "cites OMX
  parity" was refuted by the 2026-07-05 audit — no such comment exists in setup-contract.ts.)
- **Why OMX needs it**: exp-init writes `evaluator.sh` from the interview and marks the profile
  `pending_approval: true` (`profile.py:73`) — but that flag is binary. There is no distinction between "user
  *stated* the eval command" (high confidence) and "I *inferred* it from the repo" (low confidence). A
  low-confidence inferred evaluator that a human rubber-stamps becomes the score truth-source for the whole
  loop — a silent correctness risk the harness's own evidence-first philosophy should block.
- **Adaptation sketch**: extend the metrics.yaml schema with `evaluator_source: 'user'|'inferred'` and
  `evaluator_confidence: float`. In `validate_metrics_schema` (`profile.py:27`) loud-fail if
  `evaluator_source == 'inferred'` and `evaluator_confidence < 0.8` and `pending_approval` was cleared —
  i.e. an inferred, low-confidence evaluator can never be approved without a clarification round. Surface the
  threshold as a named constant `EVALUATOR_CONFIDENCE_THRESHOLD = 0.8`. This rides the existing exp-init
  Criteria dimension (design §4.1) at near-zero cost.

### 4. Capture-then-curate: auto-append findings at loop/session end

- **OMC mechanism**: `11-knowledge-lifecycle.md:56-75` — SessionEnd/PreCompact hooks write a *cheap, bounded*
  session-log stub (category `session-log`, confidence `medium`, hard 3s budget, fail-open), and an LLM pass
  curates it next session. The write path and the judgment path are separated.
- **Why OMX needs it**: OMX's wiki is fully manual — a finding reaches `registry/findings/` only if the human
  runs `omx wiki add`. The design's headline goal is "쓸수록 이 workspace에 특화되어 간다" (the more you use it,
  the more it specializes; design §9 build #8) — but with a manual-only write path, a busy session's findings
  evaporate. The `exp-analyze` report already contains parsed `[FINDING]` tags (`report.py`), so the raw
  material is sitting there uncaptured.
- **Adaptation sketch**: OMX has no hooks (and should keep it that way), so make this a CLI verb the skills
  call at their natural end: `omx wiki add --from-report <report.md> --auto` (the `--from-report` extractor
  already exists per `cli.py:779`). Have exp-analyze's "When done" gate and exp-loop's step-7 stop invoke it to
  ingest each `[FINDING]` as a `confidence: low`, `category: session-log`, `tags:[auto-captured]` stub —
  append-merge so nothing is lost, low-confidence so lint flags it for later human promotion. Preserves
  INV-1/INV-2 and the "gated promotion" split (a later `omx wiki` curation pass raises confidence).

### 5. Mechanical format-drift guard on report.md (make the 0.1.14 rule enforceable)

- **OMC mechanism**: `17-quality-verification.md` — OMC's deliverable gates are *code*, not prose (the ralph
  verifier, the visual-verdict 90-threshold rerun loop). The general lesson: a rule that lives only in a prompt
  is bypassable; put the gate on the write path.
- **Why OMX needs it**: CHANGELOG 0.1.14 documents an incident where a session hand-Edited `report.md` past
  every gate, and the fix was a *prose* rule ("NEVER hand-Edit report.md", `exp-analyze/SKILL.md:142`). The
  coverage lint counts tokens, not visual format, so a wall-of-text with the right tokens still passes (proven
  in the changelog). The rule is only as strong as the agent's compliance.
- **Adaptation sketch**: add a `report.md` integrity stamp. When `atomic_path` writes a report, also write
  `manifest.json` with a `content_sha256` of the report bytes (manifest already exists per `omx_paths.py:317`).
  Add `omx report-verify <analysis_id>` that recomputes the hash and loud-fails if `report.md` was modified
  out-of-band (hash mismatch = "report hand-edited; re-enter exp-analyze as a RE-analysis"). Wire it into
  exp-design/exp-loop's report-read step so downstream skills refuse to consume a tampered report. This makes
  the 0.1.14 rule *mechanical* without a hook — a CLI check at the consumer boundary.

### 6. Cross-session "who is running" query (`state_list_active` analog)

- **OMC mechanism**: `04-tools-state-memory.md` / `06-mode-autopilot-ralph.md` — `state_list_active` +
  `_meta.sessionId`/`owner_pid` ownership envelope let any session see which modes are live and reap zombies
  (2h stale, dead pid, 24h tombstone).
- **Why OMX needs it**: once candidate #1 lands the lock, the natural next question is "is a loop already
  running, and on what?" With multi-GPU concurrent sessions, a human returning to the workspace has no way to
  ask. Low urgency alone, high synergy with #1.
- **Adaptation sketch**: `omx loop-status --all` reads every `.omx/runs/*/​.loop-lock` + the `active_loop`
  block from #1 and prints a table `{run_id, session_id, pid(alive?), started_at, phase}`. Pure read, no new
  state — it just surfaces what #1 already records. Fold into the existing `loop-status` verb (`cli.py:763`).

## Deliberately not adopting

- **Custom MCP server / bridge** (`03-mcp-bridge.md`) — violates D1/D3 head-on; design §11 proves the
  persistent-kernel payoff is ~0 for "1 run = 1 load", and Bash+fileIO is the version-resilient floor.
- **Hooks (Stop/PreToolUse/SessionEnd) engine** (`02-hooks.md`) — OMX is intentionally hookless; every
  candidate above is delivered as a CLI verb the skill calls, keeping the surface at "Bash runs Python".
- **Autonomous orchestration modes** (autopilot/ralph/team/ultrawork, `06`/`07`) — out of scope (D6): OMX is a
  *way of working on experiments*, not a general executor. The `exp-loop` deadline is the only autonomy, and it
  never auto-launches training (D4/B8).
- **Subagent catalog + model routing + delegation gate** (`12`, `19`) — OMX has no subagents; the skills
  orchestrate CLI verbs directly. Nothing to route or enforce.
- **Vector/embedding search** (any) — hard constraint (design §9 build #8, `wiki/query.py:1`): keyword+tag+CJK
  only, matching OMC's own no-embeddings stance.
- **Plugin install/update/HUD/notification systems** (`01`, `13`) — packaging is claudebase's job (D7);
  minimal-surface principle keeps these out.
- **Full-unattended training auto-launch** — explicitly forbidden with no override path in v0.1 (D4/B8); the
  repo rule "training start/stop is the user's" is load-bearing, not a limitation to lift.

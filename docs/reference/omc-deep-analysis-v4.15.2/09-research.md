# Research Lane: sciomc, external-context, and autoresearch

OMC's research lane bundles three skills of sharply different construction. `sciomc` (parallel scientist-agent research) and `external-context` (parallel web/doc lookup) are pure prompt-ware: their entire behavior lives in `SKILL.md` files that the orchestrating Claude session executes; no TypeScript touches their session state. `autoresearch` is the opposite extreme: a stateful, evaluator-driven single-mission improvement loop with a real contract library (`src/autoresearch/`), git-native keep/revert semantics, a Stop-hook deadline enforcer, and a dual artifact tree — but in v4.15.2 the loop *driver* has migrated from a CLI runtime to a skill-driven flow, leaving the runtime library as a preserved contract implementation with no production importer. Two agents anchor the lane: `scientist` (in-repo data analysis, Python-only) and `document-specialist` (external docs, citation-bound).

## Activation map

| Component | Status | Evidence |
|:---|:---|:---|
| `skills/sciomc/SKILL.md` (511 lines) | ACTIVE prompt-only skill; dispatched via `commands/sciomc.md` compat shim | (commands/sciomc.md — whole-file) |
| `skills/external-context/SKILL.md` (84 lines) | ACTIVE prompt-only skill; "No magic keyword trigger - explicit invocation only" | (skills/external-context/SKILL.md:84) |
| `skills/autoresearch/SKILL.md` (90 lines) | ACTIVE skill; backed by mode-registry `'autoresearch'` mode + Stop-hook enforcement | (src/hooks/mode-registry/types.ts:9), (src/hooks/persistent-mode/index.ts:2297) |
| `src/autoresearch/contracts.ts`, `setup-contract.ts` | ACTIVE library (imported by CLI setup modules and validated by tests); the skill instructs "Prefer reusing `src/autoresearch/*` runtime/schema helpers" | (skills/autoresearch/SKILL.md:88) |
| `src/autoresearch/runtime.ts` (1547 lines) | Library with NO production importer in src/ — only `__tests__/`. Preserved OMX-parity supervisor implementation | grep: no `from '.*autoresearch/runtime` outside tests |
| `src/cli/autoresearch.ts` | ACTIVE wiring, but a hard-deprecated shim that only prints migration guidance | (src/cli/index.ts:1454-1461), (src/cli/autoresearch.ts:1-22) |
| `src/cli/autoresearch-{guided,intake,setup-session}.ts` | VESTIGIAL — no caller outside tests; the guided tmux launch even targets the deprecated `omc autoresearch` CLI | (src/cli/autoresearch-guided.ts:350-354) |
| `agents/scientist.md`, `agents/document-specialist.md` | ACTIVE agent prompts, registered in `src/agents/definitions.ts:238,167` | (src/agents/scientist.ts:49-56) |
| `scripts/eval-autoresearch-json.mjs`, `-timed-json.mjs` | Dev-only dogfood evaluators (emit `{pass, score}` JSON from OMC's own test suite) | (scripts/eval-autoresearch-json.mjs — whole-file) |

The `level: 4` frontmatter on all three SKILL.md files is a taxonomy marker only — no runtime code parses a skill `level` field. Stop-hook protection for the lane comes from `SKILL_PROTECTION`: `sciomc: 'medium'`, `'external-context': 'medium'` (5 reinforcements, 15-minute TTL), while `autoresearch: 'none'` because it flows through the dedicated workflow-mode path instead (src/hooks/skill-state/index.ts:105-138).

## sciomc: parallel-scientist stage pipeline

Four phases, entirely prompt-driven: Decomposition, Execution, Verification, Synthesis (skills/sciomc/SKILL.md:14-19). The orchestrator decomposes a goal into 3-7 independent stages, each with `Focus / Hypothesis / Scope / Tier` where `Tier: LOW | MEDIUM | HIGH` (SKILL.md:44-58), then fires `Task(subagent_type="oh-my-claudecode:scientist", model=..., prompt="[RESEARCH_STAGE:n] ...")` calls in parallel with an explicit tier-to-model map: LOW→haiku (enumeration/counting), MEDIUM→sonnet (pattern analysis), HIGH→opus (cross-cutting reasoning) — "CRITICAL: Always pass `model` parameter explicitly!" (SKILL.md:78-95).

**Evidence-tag grammar.** Scientists emit structured tags; the SKILL.md ships the extraction regexes verbatim so any downstream parser is deterministic (SKILL.md:296-329):

| Tag | Regex (as shipped) |
|:---|:---|
| Finding | `/\[FINDING:(\w+)\]\s*(.*?)\n([\s\S]*?)\[\/FINDING\]/g` |
| Evidence | `/\[EVIDENCE:(\w+)\]([\s\S]*?)\[\/EVIDENCE\]/g` |
| Confidence | `/\[CONFIDENCE:(HIGH\|MEDIUM\|LOW)\]\s*(.*)/g` |
| Stage completion | `/\[STAGE_COMPLETE:(\d+)\]/` |
| Verification | `/\[(VERIFIED\|CONFLICTS):?(.*?)\]/` |

Quality gates: at least one `[EVIDENCE]` per `[FINDING]`, a stated `[CONFIDENCE]`, absolute file paths, reproducibility by another agent (SKILL.md:348-356). Evidence blocks carry a context window ("Lines: 45-52 (context: 40-57)", SKILL.md:336-343). Figures use `[FIGURE:path]` with `Caption:`/`Alt:` lines and get embedded into the report's Visualizations section (SKILL.md:429-450).

**AUTO mode.** `sciomc AUTO: <goal>` loops until a promise tag: `[PROMISE:RESEARCH_COMPLETE]` or `[PROMISE:RESEARCH_BLOCKED]`, max 10 iterations, with a re-injection template `[RESEARCH + AUTO - ITERATION {{ITERATION}}/{{MAX}}] Your previous attempt did not output the completion promise. Continue working.` (SKILL.md:126-149). Session verbs `status | resume | list | report <session-id> | cancel` are documented but prompt-interpreted — no TS handler exists.

**Session persistence** is a documented convention under `.omc/research/{session-id}/` with `state.json` (`status: "in_progress | complete | blocked | cancelled"`, `mode: "standard | auto"`, per-stage `tier/status/findingsFile`), `stages/stage-N.md`, `findings/raw|verified/`, `figures/`, `report.md` (SKILL.md:231-278). No code in `src/` reads or writes this tree; adherence is on the model.

**Internal inconsistency worth knowing:** the execution section caps concurrency at "Maximum 20 concurrent scientist agents" (SKILL.md:220) while the settings block documents `"maxConcurrentScientists": 5` under `omc.research` in `.claude/settings.json` (SKILL.md:466-478). Neither value — nor `maxIterations`, `autoVerify`, `generateFigures`, `evidenceContextLines` — is consumed anywhere in `src/` (grep confirms zero hits). The whole config surface is advisory prompt text.

## external-context: facet decomposition and citation rules

A deliberately thin skill (84 lines): decompose the query into **2-5 independent search facets** (`Search focus` + `Sources` per facet), fire up to **5 parallel `document-specialist` agents** at `model="sonnet"` with the instruction "Use WebSearch and WebFetch to find official documentation and examples. Cite all sources with URLs." (skills/external-context/SKILL.md:28-55). Synthesis is a fixed markdown shape: `Key Findings` (each finding bound to `Source: [title](url)`), per-facet `Detailed Results`, and a `Sources` list (SKILL.md:57-79). Explicit invocation only. All citation discipline is delegated to the document-specialist agent contract below.

## Agent roles

| | scientist | document-specialist |
|:---|:---|:---|
| Frontmatter | `model: sonnet`, `level: 3`, `disallowedTools: Write, Edit` (agents/scientist.md:1-7) | `model: sonnet`, `level: 2`, `disallowedTools: Write, Edit` (agents/document-specialist.md:1-7) |
| Mission | In-repo data analysis via `python_repl` (never Bash Python: "no `python -c`, no heredocs") | External docs ladder: local repo docs → Context Hub `chub` / Context7 curated backend → WebSearch/WebFetch official docs (agents/document-specialist.md:24-35) |
| Output markers | `[OBJECTIVE] [DATA] [FINDING] [STAT:ci|effect_size|p_value|n] [LIMITATION]`; "Every [FINDING] needs a [STAT:*] within 10 lines" (agents/scientist.md:24,77) | `## Research:` with `**Answer**/**Source**/**Version**`, code example, version notes (agents/document-specialist.md:44-65) |
| Artifacts | `.omc/scientist/reports/` + `.omc/scientist/figures/`; matplotlib Agg backend, `plt.savefig()` never `plt.show()` (agents/scientist.md:25,34) | none (read-only synthesis) |
| Hard rules | No package installs; no raw DataFrame dumps; works alone, no delegation (agents/scientist.md:28-35) | Flag sources older than 2 years; prefer official docs over blogs; cite curated-doc IDs when no URL exists (agents/document-specialist.md:29-32) |

Both are wired as first-class agents (`src/agents/definitions.ts:238` maps `scientist: scientistAgent`; delegation-routing lists both). The scientist's model is settings-overridable via `agents.scientist.model` defaulting to the MEDIUM tier model (src/config/loader.ts:63).

## autoresearch: the evaluator-driven mission loop

### Entry chain and deprecation

```
user idea
  └─ /deep-interview --autoresearch "<mission idea>"        (setup lane)
       - auto-slash-command executor detects the flag and injects
         "Autoresearch Setup Mode" guidance (src/hooks/auto-slash-command/executor.ts:260-280)
       - hard readiness gates: mission clarity AND evaluator clarity
         (skills/deep-interview/SKILL.md:56-63)
       └─ writes mission/evaluator artifacts, then hands off with
          Skill("oh-my-claudecode:autoresearch")             (execution lane)
            └─ persistent-mode Stop hook keeps the loop alive
               until the max-runtime ceiling

omc autoresearch <anything>   →  prints "HARD DEPRECATED" help only
                                 (src/cli/autoresearch.ts:1-22, src/cli/index.ts:1454-1461)
```

### Mission and evaluator contracts (`contracts.ts`)

`loadAutoresearchMissionContract(missionDirArg)` requires the mission dir to exist, resolves symlinks (`realpathSync`, macOS `/private/var` note at contracts.ts:208), requires it to sit inside a git repo (`git rev-parse --show-toplevel` + `ensurePathInside`, error string `'mission-dir must be inside a git repository.'`), and requires both `mission.md` and `sandbox.md` (contracts.ts:203-227). `sandbox.md` must start with YAML frontmatter parsed by a **hand-rolled two-level parser** that hard-fails on any unsupported line (`Unsupported sandbox.md frontmatter line: ...`, contracts.ts:85-125):

```
---
evaluator:
  command: <shell command>        # required
  format: json                    # required; only 'json' accepted in v1
  keep_policy: score_improvement  # optional; or pass_only
---
```

`parseEvaluatorResult(raw)` is the strict evaluator contract: output must be a JSON **object** with required boolean `pass` and optional numeric `score`, with four layered throws — invalid JSON → `'Evaluator output must be valid JSON with required boolean pass and optional numeric score.'`; non-object/array → `'Evaluator output must be a JSON object.'`; missing/non-boolean `pass` → `'Evaluator output must include boolean pass.'`; non-numeric `score` when present → `'Evaluator output score must be numeric when provided.'` (contracts.ts:178-201). `slugifyMissionName` lowercases, collapses non-alphanumerics to `-`, and truncates to 48 chars with `'mission'` fallback (contracts.ts:59-66).

### Supervisor loop (`runtime.ts`)

```
prepareAutoresearchRuntime                      resume path: resumeAutoresearchRuntime
  ├─ assertAutoresearchLockAvailable              (only status='running' manifests;
  ├─ ensureRuntimeExcludes (git info/exclude)      worktree must still exist)
  ├─ symlink node_modules into worktree
  ├─ assertResetSafeWorktree
  ├─ write run tree + manifest + empty ledger
  ├─ startAutoresearchMode + activateAutoresearchRun
  └─ seedBaseline  → iteration 0 row (status 'baseline'|'error')

per iteration (worker session runs one cycle, writes candidate.json, exits):
  processAutoresearchCandidate
    ├─ read + parse candidate.json  ──parse/validation failure──▶ failAutoresearchIteration
    │                                                              (run status='failed'; run-fatal)
    ├─ validate: base_commit resolves AND == last_kept_commit;
    │            candidate_commit resolves AND == worktree HEAD   (runtime.ts:1227-1277)
    ├─ status=abort       → finalizeRun('stopped','candidate abort')
    ├─ status=interrupted → reset-safety probe; dirty → 'failed'
    ├─ status=noop        → log row, regenerate instructions, relaunch
    └─ status=candidate   → runAutoresearchEvaluator
                              ├─ decideAutoresearchOutcome
                              ├─ keep    → last_kept_commit = HEAD; update last_kept_score
                              └─ discard → resetToLastKeptCommit (git reset --hard)
```

**Candidate artifact** (`candidate.json`, schema enforced by `parseAutoresearchCandidateArtifact`, runtime.ts:1157-1195): `status: candidate|noop|abort|interrupted`, `candidate_commit: string|null`, `base_commit` (required), `description`, `notes: string[]`, `created_at`. The bootstrap-instructions file spells this out to the worker: "Make at most one candidate commit, then write the candidate artifact JSON and exit" (runtime.ts:811).

**Keep policy** (`decideAutoresearchOutcome`, runtime.ts:666-764): evaluator error or `pass=false` → `discard`. Under `pass_only`, any pass is kept. Under the default `score_improvement`: if no comparable prior score exists, a numeric-scored pass is **kept as the new baseline** — the in-code comment explains "Discarding it would lose the only validated signal the loop has produced and pin score_improvement to null forever" (runtime.ts:726-739; this is the fix landed in commit `140fd064` "Fix autoresearch supervisor discarding the first passing candidate"). A pass *without* a numeric score under `score_improvement` is decision `ambiguous` and not kept. Otherwise keep iff `score > last_kept_score`.

**Auto-revert safety.** `resetToLastKeptCommit` runs `git reset --hard <last_kept_commit>` only after `assertResetSafeWorktree` passes (runtime.ts:1222-1225). Reset safety tolerates **only untracked (`?? `) paths** that are either in `AUTORESEARCH_WORKTREE_EXCLUDES = ['results.tsv', 'run.log', 'node_modules', '.omc/']` (runtime.ts:148) or in the explicitly-allowed bootstrap set (the mission/sandbox files); any other dirt throws `autoresearch_reset_requires_clean_worktree:<path>:<lines>` (runtime.ts:363-369) — loud-fail, never silent clobber. The exclude list is also written into git `info/exclude` at prepare time (runtime.ts:224-240).

**Concurrency guards.** Two independent locks: (1) the active-run lock in `.omc/state/autoresearch-state.json` — a second prepare throws `autoresearch_active_run_exists:<run_id>` (runtime.ts:394-399); (2) `assertModeStartAllowed` refuses to start if any of `EXCLUSIVE_MODES: ['ralph', 'ultrawork', 'autopilot', 'autoresearch']` is active in any session, "Mirrors OMX assertModeStartAllowed semantics" (runtime.ts:150-151,401-412).

### Artifact layout (dual tree + worktree TSV)

```
<worktree>/results.tsv                     # header: iteration\tcommit\tpass\tscore\tstatus\tdescription
                                           # (AUTORESEARCH_RESULTS_HEADER, runtime.ts:147)
.omc/logs/autoresearch/<run-id>/           # run tree (run-id = <mission-slug>-<compact-iso-tag>)
  bootstrap-instructions.md                # regenerated EVERY iteration with previous outcome
  manifest.json                            #   + last-3 ledger summary (runtime.ts:555-585,881-899)
  iteration-ledger.json                    # append-only {entries: AutoresearchLedgerEntry[]}
  latest-evaluator-result.json
  candidate.json                           # worker exit protocol
.omc/autoresearch/<mission-slug>/          # mission tree (human-facing)
  mission.md                               # mission spec copy
  evaluator.json                           # {command, format, keep_policy?}
  runs/<run-id>/
    evaluations/iteration-0000.json ...    # zero-padded per-iteration evaluator records
    decision-log.md                        # "## Iteration N — <decision>" markdown entries
.omc/state/autoresearch-state.json         # active-run lock + mode state
```

Every iteration writes to **all three surfaces**: a TSV row (grep-friendly), a ledger entry (machine JSON with `decision`, `decision_reason`, `kept_commit`, `keep_policy`, full evaluator record), and a markdown decision-log entry (human) — see the parallel `appendAutoresearchResultsRow` / `appendAutoresearchLedgerEntry` / `appendDecisionLog` calls in `processAutoresearchCandidate` (runtime.ts:1472-1502). `AutoresearchEvaluationRecord` captures `status: 'pass'|'fail'|'error'`, `exit_code`, `stdout`, `stderr`, `parse_error` (runtime.ts:38-48); the evaluator itself runs with `spawnSync(command, {shell: true, maxBuffer: 1024*1024, cwd: worktreePath})` (runtime.ts:594-598).

### Max-runtime stop and Stop-hook enforcement

The loop's strict stop boundary lives in the persistent-mode **Stop hook** (`checkAutoresearch`, src/hooks/persistent-mode/index.ts:1652-1754; dispatched at :2297; wired via `hooks/hooks.json` `Stop → persistent-mode.mjs`). Deadline resolution: prefer `deadline_at`, else `started_at + max_runtime_ms` (both recorded into mode state at prepare, runtime.ts:1072-1073). Behavior:

- Past deadline → rewrite state `{active: false, current_phase: 'stopped', stop_reason: 'max-runtime ceiling reached'}` and release with `[AUTORESEARCH COMPLETE] Max-runtime ceiling reached.` (index.ts:1707-1723).
- Before deadline → **block the stop** with an `<autoresearch-continuation>` message containing the mission slug, remaining seconds, and the key behavioral line "Do not stop just because the latest evaluation did not pass." (index.ts:1733-1747).
- Escape hatches: cancel-in-progress passes through; terminal phases (`completed|failed|stopped|cancelled`) pass through; state older than `STALE_STATE_THRESHOLD_MS = 2h` is ignored (index.ts:95,1679); a session-scoped/legacy-shared state bridge tolerates pre-session-scoping state files (index.ts:1661-1669). `session-start.mjs` lists `autoresearch-state.json` among `SESSION_END_MODE_STATE_FILES` cleaned across session boundaries (scripts/session-start.mjs:359-361).

### Setup handoff contract (`setup-contract.ts`)

The deep-interview setup lane hands off a JSON blob validated by `validateAutoresearchSetupHandoff`: required `missionText`, `evaluatorCommand`, `evaluatorSource: 'user'|'inferred'`, `confidence` in [0,1], boolean `readyToLaunch`; optional `keepPolicy`, `slug`, `clarificationQuestion`, `repoSignals[]`. Two safety invariants: `AUTORESEARCH_SETUP_CONFIDENCE_THRESHOLD = 0.8` — an *inferred* evaluator with confidence below 0.8 "cannot be marked readyToLaunch" — and a blocked handoff **must** carry a `clarificationQuestion` (setup-contract.ts:3,92-98). The parser tolerates fenced ```` ```json ```` payloads (setup-contract.ts:113-124). The vestigial intake module adds a placeholder gate: `BLOCKED_EVALUATOR_PATTERNS = [/<[^>]+>/i, /\bTODO\b/i, /\bTBD\b/i, /REPLACE_ME/i, /CHANGEME/i, /your-command-here/i]` blocks launch while the evaluator is still a template (src/cli/autoresearch-intake.ts:52-59), and mission files materialize under `<repoRoot>/missions/<slug>/{mission.md,sandbox.md}` (src/cli/autoresearch-guided.ts:104-127).

### v4.15.2 vs. recent history

The subsystem was **backported from OMX** (oh-my-experiments) in commit `fbec7e15` "backport autoresearch from OMX to OMC (Phase 1) (#1693)"; the runtime still cites OMX parity in comments (runtime.ts:403). The v4.15 line then executed a deliberate CLI-to-skill migration: `5c5835a2` "Preserve the autoresearch skill migration for coordinated review" turned `omc autoresearch` into the hard-deprecated shim, `4ff20e56` kept Stop-hook enforcement visible across session-scoped state, and `140fd064` fixed the first-passing-candidate discard (the bootstrap-keep branch above, covered by `decide-outcome.test.ts:39` "keeps the first numeric-scored pass when last_kept_score is null"). Net v4.15.2 state: the *contract* (evaluator JSON, candidate artifact, keep policy, artifact layout) is authoritative and tested, but the *driver* is the Claude session running the skill plus the Stop hook — the tmux/guided/`claude -p` setup-session CLI machinery is dead weight kept for review, and its launch path would only reach the deprecation message. `skills/sciomc` and `skills/external-context` are untouched since the v4.15.0 merge (`542b7a4c`) and remain pure prompt-ware.

### Configuration surface

| Surface | Key / flag | Consumed by | Notes |
|:---|:---|:---|:---|
| `sandbox.md` frontmatter | `evaluator.command`, `evaluator.format` (must be `json`), `evaluator.keep_policy` | `parseSandboxContract` (contracts.ts:139-176) | the only real config for the loop |
| Skill args | `--mission-dir <path> --max-runtime <duration> --cron <spec> --resume <run-id>` | skill prompt (skills/autoresearch/SKILL.md:4) | `--max-runtime` feeds `maxRuntimeMs → deadline_at` |
| Mode state | `max_runtime_ms`, `deadline_at`, `session_id` | Stop hook (index.ts:1633-1650) | 2h stale TTL |
| `.claude/settings.json` `omc.research.*` | `maxIterations`, `maxConcurrentScientists`, `defaultTier`, `autoVerify`, `generateFigures`, `evidenceContextLines` | **nothing in src/** — advisory to the model | documented at skills/sciomc/SKILL.md:464-479 |
| Env | `OMC_STATE_DIR` relocates the `.omc/` root that all autoresearch paths derive from | `getOmcRoot` (src/lib/worktree-paths.ts:503-515) | mission/run trees follow it |
| Env (vestigial) | `CODEX_HOME` symlink sandbox under `.omx/tmp/<session>/codex-home` for setup sessions | src/cli/autoresearch-guided.ts:379-399 | dead path |

## Patterns for sibling harnesses

- **Strict evaluator JSON contract** — require `{pass: boolean, score?: number}` and treat any parse failure or nonzero exit as `status='error'` → automatic discard (contracts.ts:178-201, runtime.ts:698-705). Adaptation: OMX's `evaluator.sh` already emits this shape; adopt the error-as-discard rule so a broken evaluator can never silently keep a candidate.
- **Keep-policy with bootstrap-keep** — `pass_only` vs `score_improvement`, where the first comparable score is kept as the new anchor instead of discarded (runtime.ts:716-747). Adaptation: any exp-loop that compares against `last_kept_score` needs the null-baseline branch or it pins to null forever.
- **Git reset as the revert primitive, gated by an allowlist** — `git reset --hard <last_kept_commit>` only after proving the worktree has no dirt beyond named runtime files (runtime.ts:363-369,1222-1225). Adaptation: declare each harness's runtime droppings (`results.tsv`-equivalents) up front and loud-fail on anything else.
- **Worker exit protocol via candidate artifact** — a session ends by writing `{status: candidate|noop|abort|interrupted, base_commit, candidate_commit}`; the supervisor validates commits against git before trusting it (runtime.ts:1157-1277). Adaptation: replaces fragile transcript parsing with a filesystem contract; validate `base_commit == last_kept` to detect stale workers.
- **Triple-surface logging** — TSV row (grep), JSON ledger (machine), markdown decision log (human) written in lockstep per iteration (runtime.ts:1472-1502). Adaptation: keep the TSV header stable; it is the cheapest cross-run query surface.
- **Regenerated per-iteration instructions file** — bootstrap-instructions.md rebuilt each cycle embedding the previous outcome and a last-3 ledger summary trimmed to 160/120 chars (runtime.ts:555-585). Adaptation: gives each fresh worker session bounded, current context without transcript carryover.
- **Stop-hook deadline enforcement** — the loop's persistence and its ceiling live in one Stop-hook check: block stops with a continuation reminder before the deadline, self-release with a completion marker after (persistent-mode/index.ts:1706-1747). Adaptation: pair every "never give up" harness loop with an absolute wall-clock release valve.
- **Two-lock concurrency guard** — an active-run lock file plus an exclusive-mode registry check across sessions (runtime.ts:394-412). Adaptation: harnesses sharing `.omx/`/`.omp/` state should refuse to start on either lock, not just their own.
- **Confidence-gated setup handoff** — inferred configuration below a 0.8 confidence threshold cannot be launch-ready, and any blocked handoff must carry the next clarification question (setup-contract.ts:92-98). Adaptation: matches omx exp-init's ambiguity gating; make the threshold a named constant.
- **Placeholder-evaluator regex gate** — block launch while the command matches TODO/TBD/template patterns (autoresearch-intake.ts:52-59). Adaptation: cheap guard for any generated `evaluator.sh`/`launch.sh`.
- **Evidence-tag grammar with shipped regexes** — `[FINDING]/[EVIDENCE]/[CONFIDENCE]` plus the exact extraction patterns inside the skill doc itself (skills/sciomc/SKILL.md:296-329). Adaptation: publishing the parser regex next to the tag spec keeps producers and consumers in sync; omx report evidence tags could adopt this.
- **Facet decomposition with hard parallel caps and per-facet citation duty** — 2-5 facets, max 5 agents, every finding URL-bound (skills/external-context/SKILL.md:28-55). Adaptation: the right shape for oms scholar-research fan-out; keep the cap in the skill text since nothing enforces it in code.

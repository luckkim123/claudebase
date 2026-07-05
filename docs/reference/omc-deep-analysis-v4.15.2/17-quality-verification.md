# Quality & Verification Lane: verify, visual-verdict, debug, release, cancel

This lane is OMC's answer to the central failure mode of autonomous coding agents: an agent that *claims* completion without *proving* it. It spans five user-facing skills (`verify`, `visual-verdict`, `debug`, `release`, `cancel`) plus two TypeScript modules (`src/verification/tier-selector.ts`, `src/features/verification/`). The load-bearing runtime is not any of the skills but the **ralph completion gate** in `src/hooks/ralph/verifier.ts` driven by `src/hooks/persistent-mode/index.ts`: a Stop-hook loop that intercepts a completion claim, forces an independent reviewer (architect/critic/codex) to author a correlated approval token, and refuses to let the session end until that token appears in the transcript. Four of the five skills are prompt-only markdown contracts; the anti-self-approval enforcement, the cancellation state machine, and the tier-scaling logic live in code. The two `src/*verification*` TypeScript modules are largely a re-exported library — only `formatReport` is called at runtime — so the real evidence engine is the ralph verifier and the ultragoal quality gate.

## Component inventory and wiring status

| Component | Kind | Wired via | Status |
|---|---|---|---|
| `skills/verify/SKILL.md` | prompt skill | `plugin.json` skills[], `commands/verify.md` | ACTIVE (prompt-only, no code) |
| `skills/visual-verdict/SKILL.md` | prompt skill, `level: 2` | `plugin.json`, `commands/visual-verdict.md` | ACTIVE (JSON verdict contract) |
| `skills/debug/SKILL.md` | prompt skill | `plugin.json`, `commands/debug.md` | ACTIVE (points at trace/state MCP tools) |
| `skills/release/SKILL.md` | prompt skill, `level: 3` | `plugin.json`, `commands/release.md` | ACTIVE (rule-caching, no TS) |
| `skills/cancel/SKILL.md` | prompt skill, `level: 2` | `plugin.json`; no `commands/cancel.md` | ACTIVE (state-machine over MCP `state_*` tools) |
| `src/hooks/ralph/verifier.ts` | TS hook logic | `persistent-mode/index.ts` Stop hook | ACTIVE — the real completion gate |
| `src/features/verification/{index,types}.ts` | TS library | re-exported by `src/features/index.ts` | MOSTLY DORMANT — only `formatReport` called (`src/cli/commands/doctor-conflicts.ts:766`) |
| `src/verification/tier-selector.ts` | TS pure functions | none | VESTIGIAL — imported only by its own `.test.ts` |
| `src/ultragoal/artifacts.ts` `validateQualityGate` | TS gate | ultragoal CLI | ACTIVE — hard fail-loud completion gate |

The `commands/*.md` files are thin dispatch shims with empty `description: ""` front-matter whose only job is to keep `/oh-my-claudecode:<skill>` resolvable "without loading the full skill description in every session" — they instruct the model to read `skills/<name>/SKILL.md` and follow it verbatim, resolving the path under `CLAUDE_PLUGIN_ROOT`/`OMC_PLUGIN_ROOT` if not local.

## verify: evidence-based completion checking

`skills/verify/SKILL.md` (whole-file) is a 37-line prompt with no backing code. Its thesis is a fixed **verification order** that biases toward the cheapest sufficient proof: (1) existing tests, (2) typecheck/build, (3) narrow direct command checks, (4) manual/interactive validation. Its hard rules are anti-bluff: "Do not say a change is complete without evidence"; "If a check fails, include the failure clearly"; "If no realistic verification path exists, say that explicitly instead of bluffing" (`skills/verify/SKILL.md:27-29`). Output is partitioned into what was verified, which commands ran, what passed, and what "failed or remains unverified" — forcing the unverified surface to be named rather than elided. The skill carries no `level:` field, so it eager-loads.

The **tier sizing** the CLAUDE.md orientation describes ("small->haiku, standard->sonnet, large/security->opus") is codified in `src/verification/tier-selector.ts`, though that module is currently vestigial (no production import). Its rules are worth reproducing because siblings should re-implement the *policy*, not the module:

```
selectVerificationTier(changes):
  hasSecurityImplications OR hasArchitecturalChanges          -> THOROUGH (architect / opus)
  filesChanged > 20                                           -> THOROUGH
  filesChanged < 5 AND linesChanged < 100 AND cov == 'full'   -> LIGHT    (architect-low / haiku)
  else                                                        -> STANDARD (architect-medium / sonnet)
```

Evidence required scales with tier (`tier-selector.ts:24-40`): LIGHT = `['lsp_diagnostics clean']`; STANDARD adds `'build pass'`; THOROUGH = `['full architect review', 'all tests pass', 'no regressions']`. "Architectural" is pattern-matched on filenames (`config.*`, `schema.*`, `definitions.ts`, `types.ts`, `package.json`, `tsconfig.json` — `tier-selector.ts:80-87`); "security" matches `/auth/`, `/security/`, `permission(s)`, `credential(s)`, `secret(s)`, `token(s)`, `.env|.pem|.key`, `password(s)`, `oauth`, `jwt` (`tier-selector.ts:98-109`). The security/architectural predicates short-circuit to THOROUGH before any size test, so a one-line change to `auth/session.ts` still demands opus review.

## The ralph completion gate (the real enforcement)

`src/features/verification/` defines a full protocol/checklist/evidence data model (build, test, lint, functionality, architect_approval, todo_complete, error_free — `index.ts:27-87`) with a notable no-fake-completion default: a manual check with no `command` returns `passed: false` with `metadata.status = 'pending_manual_review'` so gate logic "does not auto-approve" (`index.ts:155-163`), and evidence older than five minutes is flagged stale (`index.ts:280-283`). But this library is dormant. The gate that actually runs is `src/hooks/ralph/verifier.ts`, invoked from the Stop hook in `persistent-mode/index.ts`.

```
ralph completion loop (persistent-mode/index.ts Stop hook)
  agent emits "task complete"
    -> startVerification(...)  writes ralph-verification.json {pending:true, request_id, ...}
    -> Stop hook injects getArchitectVerificationPrompt(): "spawn reviewer, then emit approval tag"
  reviewer (architect | critic | codex) runs as a Task/Bash tool_use
    -> its tool_result must contain:
       <ralph-approved critic="architect" request-id="<uuid>" [story-id="..."]>VERIFIED_COMPLETE</ralph-approved>
  Stop hook re-fires:
    checkReviewerAuthoredApprovalInMessages(transcript, verificationState)
      approve  -> clearVerificationState, allow stop, tell agent to run /oh-my-claudecode:cancel
      reject   -> recordArchitectFeedback(false, ...); if attempts < 3 re-inject rejection continuation
                  after max_verification_attempts (default 3) -> force-accept (clear state)
```

The anti-gaming core is `checkReviewerAuthoredApprovalInMessages` (`persistent-mode/index.ts:744-803`): it does **not** accept the approval tag from arbitrary assistant text. It first indexes only `tool_use` blocks whose name is in `REVIEWER_TASK_TOOL_NAMES = {'Task','proxy_Task','Agent'}` (or a codex `Bash` command via `REVIEWER_COMMAND_TOOL_NAMES = {'Bash','proxy_Bash'}`) and whose `subagent_type` matches the expected `critic_mode` (`index.ts:684-685, 769-782`). Only the matching `tool_result` for that specific `tool_use_id` is scanned for the approval token (`index.ts:787-798`). The token itself is correlated: `detectArchitectApproval` (`verifier.ts:335-369`) requires the `request-id` attribute to equal the current `VerificationState.request_id` (a fresh `randomUUID()` per attempt) and, for story-scoped runs, the `story-id` to match. Injected examples are stripped first via `stripInjectedApprovalExamples` (`verifier.ts:329-333`) so the prompt's own sample tag cannot self-satisfy the gate. Net effect: the implementing agent cannot approve its own work by printing the tag — the tag must originate inside an independent reviewer subagent's tool output, keyed to the live request. This is the structural embodiment of the CLAUDE.md "never self-approve in the same active context" rule.

Rejection detection (`verifier.ts:374-397`) is a looser heuristic — regexes over reviewer text for `(architect|critic|codex|reviewer).*(rejected|found issues|not complete|incomplete)`, `issues? found`, `bug found`, etc. The `max_verification_attempts = 3` default (`verifier.ts:50, 184`) is a deliberate liveness escape: after three rejected rounds the gate force-accepts to avoid an infinite loop, so the guard is fail-**open** on repeated failure, not fail-closed. A separate liveness lever is `CRITICAL_CONTEXT_STOP_PERCENT = 95` (`persistent-mode/index.ts:610`): when transcript context usage crosses 95% the loop treats it as a critical stop and stops re-injecting.

The parallel hard gate is ultragoal's `validateQualityGate` (`src/ultragoal/artifacts.ts:545-573`), which is fail-**loud**: final completion requires a `--quality-gate-json` object where `aiSlopCleaner.status === 'passed'` ("run ai-slop-cleaner even when it is a no-op"), `verification.status === 'passed'` with a non-empty `verification.commands` string array, and `codeReview.recommendation === 'APPROVE'` with `codeReview.architectStatus === 'CLEAR'`. Any missing or non-conforming field throws `UltragoalError`. This is the strictest completion contract in the codebase and the best template for a sibling "definition of done".

## visual-verdict: structured screenshot verdict contract

`skills/visual-verdict/SKILL.md` (`level: 2`) is a prompt-only skill defining a strict JSON output contract for comparing a `generated_screenshot` against `reference_images[]` (optional `category_hint`). The model must return **JSON only** (`SKILL.md:23-44`):

```json
{ "score": 0-100, "verdict": "pass|revise|fail", "category_match": bool,
  "differences": ["..."], "suggestions": ["..."], "reasoning": "1-2 sentences" }
```

The loop contract is the enforceable part: target pass threshold is **90+**; if `score < 90` the model must continue editing and rerun `/oh-my-claudecode:visual-verdict` before any further visual review pass, and must not treat the task complete until the next screenshot clears 90 (`SKILL.md:45-49`). Pixel-diff tooling (pixelmatch overlay) is explicitly demoted to a "secondary debug aid" — `$visual-verdict` remains "the authoritative decision," and pixel hotspots must be converted into concrete `differences[]`/`suggestions[]` entries (`SKILL.md:51-56`). This is the same shape as the code-side verification gate — a numeric score, a pass threshold, and a mandatory re-run loop — applied to a non-deterministic visual judgment where no test harness exists.

## debug: evidence-first session diagnosis

`skills/debug/SKILL.md` (whole-file) is a prompt skill for diagnosing a *live OMC/Claude-Code session* (not app bugs). Its workflow orders evidence sources: trace tools, state tools, notepad/project memory, then failing tests/commands (`SKILL.md:15-21`), followed by narrow reproduction and symptom-vs-root-cause separation. The "trace/state surfaces" it names are real MCP tools shipped by OMC: `trace_timeline` and `trace_summary` (`src/tools/trace-tools.ts:219,301`) and `state_read` / `state_get_status` / `state_list_active` / `state_write` / `state_clear` (`src/tools/state-tools.ts:593,1467,1295,748,879`). Its rules mirror the lane ethos: "Prefer real evidence over guesses"; "If the issue is actually a product/runtime bug rather than app code, say so plainly"; "Do not prescribe broad rewrites before isolating the failure." Output is a fixed four-part shape: observed failure, root-cause hypothesis, evidence for it, smallest next action.

## release: rule-caching release assistant

`skills/release/SKILL.md` (`level: 3`) is a prompt-only, project-agnostic release walker whose one durable artifact is `.omc/RELEASE_RULE.md` — a **cache of derived release rules**, not code. There is no TypeScript backing it; all `RELEASE_RULE` references are in the skill markdown itself. The caching protocol (`SKILL.md:22-98`):

```
Step 0: if .omc/RELEASE_RULE.md absent OR --refresh -> full repo analysis, write file
        if present -> read it, then delta-check: scan CI dirs (.github/workflows, .circleci,
                      .travis.yml, Jenkinsfile, gitlab-ci.yml, ...) for files newer than the
                      <!-- last-analyzed: ISO --> stamp; re-analyze only changed sections
```

Analysis derives version sources (regex per file across `package.json`/`pyproject.toml`/`Cargo.toml`/`build.gradle`/`VERSION`), registry/distribution, release trigger, test gate, changelog convention, and first-time gaps (`SKILL.md:36-67`), writing them under fixed headings. The rule file is explicitly a local cache the user may commit to share or gitignore to keep local (`SKILL.md:197`). The execution flow (bump -> test -> commit `chore(release): bump version to vX.Y.Z` -> annotated tag -> push -> CI handoff -> verify via `gh run list`/`gh release view`) hardcodes nothing project-specific — everything is derived from inspection (`SKILL.md:194-198`). The delta-check pattern (cache + staleness stamp + re-derive only what changed) is the reusable idea.

## cancel: cancellation semantics across all modes

`skills/cancel/SKILL.md` (`level: 2`, aliases `cancel-ralph`) is the standard exit for every OMC mode — the Stop hook, on detecting completion, instructs the model to invoke it "for proper state cleanup" (`SKILL.md:13-17`). It is executed by the LLM, primarily over the deferred MCP `state_*` tools, which must be loaded via `ToolSearch(query="select:...state_clear,state_read,...")` before use (`SKILL.md:44-48`). Cancellation is **session-aware and dependency-ordered**: `state_list_active` enumerates `.omc/state/sessions/{sessionId}/`, `state_get_status` reports the active mode, and `state_clear(session_id)` removes only that session's files (`SKILL.md:104-119, 186-192`). Modes cancel in dependency order (autopilot -> ralph -> ultrawork/ultraqa -> swarm -> ultrapilot -> pipeline -> team -> ...), and link-aware cascades apply: cancelling ralph clears its linked ultrawork; cancelling autopilot clears linked ralph/ultraqa but only **marks autopilot inactive** to preserve resume data (`SKILL.md:275-303`).

State preservation is asymmetric and is the key cross-cutting fact:

| Mode | State preserved on cancel | Resume |
|---|---|---|
| Autopilot | Yes (phase, files, spec, plan, verdicts) | `/oh-my-claudecode:autopilot` |
| Plan Consensus | Yes (plan file path) | n/a |
| Ralph / Ultrawork / UltraQA / Swarm / Ultrapilot / Pipeline | No | n/a |

A **critical always-run step**: regardless of mode or `--force`, the final action is `state_clear(mode="skill-active", session_id)` so a stale `skill-active-state.json` cannot keep the Stop hook re-firing skill-protection reinforcements (`SKILL.md:317-321`, cites issue #2118). `--force`/`--all` additionally deletes an enumerated legacy compatibility list under `.omc/state/*.json` (autopilot/ralph/ultrawork/ultraqa/ultrapilot/pipeline/plan-consensus/ralplan/boulder/hud/subagent-tracking state, `swarm.db{,-wal,-shm}`, `swarm-active.marker`, `checkpoints/`, `sessions/`) plus team artifacts under `~/.claude/teams/*/` and `~/.claude/tasks/*/` (`SKILL.md:145-170`). Swarm is deliberately outside session scoping — a shared SQLite/marker mode (`.omc/state/swarm.db` / `swarm-active.marker`). A **bash fallback** (`SKILL.md:61-101`) removes state files directly when the MCP `state_clear` is unavailable, writing a `cancel-signal-state.json` with a 30-second `expires_at` so the Stop hook detects cancellation-in-progress; it explicitly forbids using the fallback for autopilot (needs `state_write(active:false)` to preserve resume) or omc-teams (needs tmux cleanup). The fallback mirrors `getProjectIdentifier()` for `OMC_STATE_DIR` centralized storage using a cross-platform SHA-256 of the git origin.

## Configuration surface

| Surface | Key / value | Default | Source |
|---|---|---|---|
| Env | `OMC_STATE_DIR` | unset (uses repo `.omc/state`) | cancel fallback `SKILL.md:70-76` |
| Env | `CLAUDE_SESSION_ID` / `CLAUDECODE_SESSION_ID` | — | cancel fallback `SKILL.md:63` |
| Env | `CLAUDE_PLUGIN_ROOT` / `OMC_PLUGIN_ROOT` | — | command dispatch shims |
| Const | `DEFAULT_MAX_VERIFICATION_ATTEMPTS` | `3` | `verifier.ts:50` |
| Const | `DEFAULT_RALPH_CRITIC_MODE` | `'architect'` | `verifier.ts:51` |
| Const | `CRITICAL_CONTEXT_STOP_PERCENT` | `95` | `persistent-mode/index.ts:610` |
| Const | evidence staleness window | 5 min | `features/verification/index.ts:280` |
| Flag | ralph critic mode | `architect` \| `critic` \| `codex` | `loop.ts:264` `detectCriticModeFlag` |
| Flag | `/release [version] [--refresh]` | version optional | `skills/release/SKILL.md:16-18` |
| Flag | `/cancel [--force\|--all]` | scoped | `skills/cancel/SKILL.md:124-130` |
| Threshold | visual-verdict pass score | `90` | `skills/visual-verdict/SKILL.md:46` |
| Tier bounds | files>20 / files<5 & lines<100 & full-cov | THOROUGH / LIGHT | `tier-selector.ts:52-63` |

## Failure modes and guards

The lane mixes fail-open and fail-loud deliberately. The ralph gate is **fail-open on exhaustion** (force-accept after 3 rejected attempts; stop re-injecting at 95% context) to preserve liveness, but **fail-closed against gaming** (approval must come from a correlated reviewer tool_result, not assistant text). The dormant `features/verification` library defaults manual checks to `pending_manual_review` (fail-closed) and stale-flags old evidence. The ultragoal quality gate is fail-loud (throws on any missing evidence field). The cancel fallback is fail-loud on state-dir resolution (`exit 1` if `.omc` not found) but best-effort on team-artifact cleanup. The main correctness risk is that four of five skills are prompt-only, so their guarantees hold only as far as the model obeys the contract — the *code* that actually blocks a bad completion is the ralph verifier and the ultragoal gate; a sibling that copies only the markdown gets the appearance of a gate without the enforcement.

## Patterns for sibling harnesses

- **Correlated reviewer-authored approval token** — require a `<approved request-id="<uuid>">VERIFIED_COMPLETE</...>` tag that is only honored when it appears inside an independent reviewer subagent's tool_result matching the live request id; strip prompt examples first. Adaptation: siblings gate completion on a token whose provenance is a *different* agent's tool output, not the implementer's prose.
- **Fail-open liveness escape with a bounded attempt counter** — `max_verification_attempts = 3` then force-accept, plus a 95%-context critical-stop. Adaptation: pick a small N and a context ceiling so a strict gate can never deadlock a loop.
- **Tiered verification effort scaling** — security/architectural filename predicates short-circuit to the heaviest reviewer (opus) before any size test; small+tested+full-coverage drops to haiku. Adaptation: encode the model-sizing policy as pure functions keyed on changed-file patterns, independent of any one workflow.
- **Fail-loud completion contract** — ultragoal's `validateQualityGate` throws unless slop-cleaner=passed, verification=passed with non-empty commands, and code-review=APPROVE/CLEAR. Adaptation: represent "definition of done" as a validated JSON object the CLI refuses to accept when incomplete, not a checklist in a prompt.
- **Structured verdict + hard threshold + mandatory re-run loop** — visual-verdict's `{score, verdict, differences, suggestions}` with a 90 gate. Adaptation: any non-deterministic judgment (design, prose, image) gets a numeric score, a threshold, and a "rerun before proceeding" rule.
- **Rule cache with staleness stamp** — release's `.omc/RELEASE_RULE.md` with `<!-- last-analyzed -->` and CI-file delta re-derivation. Adaptation: cache expensive repo-analysis in a per-project dot-file and re-derive only sections whose inputs changed.
- **Session-scoped, dependency-ordered, resume-aware cancellation with an always-run skill-active clear** — clear only the current session's files in dependency order, preserve resume state for the modes that support it, and unconditionally clear `skill-active` last to break Stop-hook re-fire loops. Adaptation: model cancellation as a state machine over per-session files with an explicit preserve/discard table and a mandatory final unstick step.
- **Manual-check-as-not-passed default** — an evidence check with no command returns `passed:false, status:pending_manual_review`, plus a 5-minute staleness flag. Adaptation: never let "no automated check exists" silently count as a pass, and expire evidence so an old green result cannot re-approve new code.

# Multi-session git coordination — isolate, don't negotiate

**Filed**: 2026-05-30
**Status**: DESIGN ONLY (no implementation; decision + tiered reference)
**Pair**: `plan.md` to be written if/when a tier is actually implemented.
**Trigger**: recurring git conflicts when running several Claude Code sessions across tmux panes/windows on overlapping working directories.

## TL;DR (the ruling)

The user's instinct — *"stamp each commit with a session id, and when a conflict happens, pause the sessions and have them negotiate a resolution"* — is **half right and half trap**.

- **Keep**: session **identity** + **visibility** (who is touching what). Genuinely good, industry-endorsed.
- **Drop**: **pause-and-negotiate-at-conflict-time**. This is the hard part of distributed consensus that the entire industry deliberately *avoids*, not solves — and the empirical multi-agent data makes it not merely inelegant but *measurably* failure-prone.
- **Standard instead**: **isolate, don't negotiate.** One branch per task, one `git worktree` per session, claim work up front, defer real conflicts to deterministic merge/rebase. Conflicts surface explicitly at merge time, never silently at runtime.

**Default recommendation: run each concurrent session in its own `git worktree` (Tier 0).** That structurally eliminates ~90% of the conflict class at near-zero cost. Add heavier tiers only when a specific pain appears.

## Why this design exists

Across machines the user runs N Claude Code sessions in tmux panes/windows. The working-directory situation is **mixed and unruled** — sometimes the panes share one working tree, sometimes they don't, and there is no policy deciding which. The symptom is frequent git collisions: silent file overwrites and `.git/index.lock` contention when two sessions touch the same tree at once.

The user proposed solving this with *runtime negotiation*: embed a session id/location in every commit so sessions can see each other, and on conflict, pause the involved sessions and have them talk it out.

This document records **why that specific cure is wrong**, **what the industry standard actually is**, and **a tiered architecture** matched to the user's mixed/unruled situation — lightest first. It is a consultation artifact: it fixes the decision so a future implementation session does not re-litigate it.

The root cause to name plainly: the conflicts do not come from "no worktrees." They come from **no rule about when to share a directory and when to separate**. The primary fix is *a rule*; worktree is the mechanism that rule points to.

## The trap, with evidence

"Stop-and-negotiate-at-conflict-time" reintroduces coordination at the most expensive possible moment. Three independent bodies of evidence converge:

1. **The worktree world calls it out by name.** Augment Code's principle is literally *"structural prevention, not runtime conflict resolution"* — conflicts are deferred to merge time and surfaced explicitly by standard git, not handled live during execution. ([augmentcode.com](https://www.augmentcode.com/guides/git-worktrees-parallel-ai-agent-execution))

2. **The concurrency-control world ranks negotiation last.** Arion Research's agentic conflict framework ranks **proactive detection > reactive negotiation > human escalation** — "stop and negotiate at conflict time" is the *fallback used only after pre-coordination has already failed*, never the primary design. ([arionresearch.com](https://www.arionresearch.com/blog/conflict-resolution-playbook-how-agentic-ai-systems-detect-negotiate-and-resolve-disputes-at-scale))

3. **The empirical multi-agent data makes it damning.** DPBench (Dining Philosophers Benchmark):
   - GPT-5.2, 3 agents, **simultaneous-decision mode: 95–100% deadlock**.
   - **Adding a communication channel *raised* deadlock 25% → 65%** — agents announced intentions but honored them only 29–44% of the time, so the channel created *false* coordination signals.
   - Named failure mode: **Agent Deadlock Syndrome** — agents defer to each other producing extended inactivity *with no error signal* (worse than a crash; undetectable). ([reputagent.com](https://reputagent.com/research/why-ai-agents-keep-getting-stuck-when-they-decide-together), [cogentinfo.com](https://cogentinfo.com/resources/when-ai-agents-collide-multi-agent-orchestration-failure-playbook-for-2026))

The proposed design is a near-perfect recipe for this: pausing the sessions = simultaneous-decision mode (95–100% deadlock); opening a channel = the thing that raised deadlock to 65%; negotiating a merge = convergent reasoning (two competent agents reach the *same* resolution and re-collide) or hallucinated consensus (each agrees because the other sounds confident).

And git's floor is sharp underneath all this: `.git/index.lock` is single-writer via `O_EXCL`; the loser gets a **hard `fatal: Unable to create '.git/index.lock'`**, not a polite "please negotiate." There is no live-merge affordance at the git layer to negotiate *with*. ([git-scm.com/docs/api-lockfile](https://git-scm.com/docs/api-lockfile))

**Why consensus is the wrong tool specifically.** Making live negotiation *safe* would require real consensus (fencing tokens, quorum, leader serialization) — i.e. Paxos/Raft, which is 100×–1000× the cost of a lockfile, lives *inside* services like Chubby/etcd, and does not belong at the file-coordination layer at all. The proposal reaches for consensus-level coordination *cost* while getting *none* of its safety. Worst quadrant: consensus-level cost, LLM-level reliability. ([brooker.co.za](https://brooker.co.za/blog/2023/10/18/optimism.html), [Chubby paper](https://mwhittaker.github.io/papers/html/burrows2006chubby.html))

## The standard: isolate, don't negotiate

A four-layer stack, none involving live negotiation. The key inversion: the proposal wants conflicts to be a **loud synchronous runtime event**; the standard works because it makes them a **quiet asynchronous merge-time event**. Branch isolation scales *linearly* (new agent = new branch); live coordination scales *quadratically* (every pair must sync) — that alone decides it past 2 agents.

| Layer | Mechanism | What it buys |
|---|---|---|
| **Isolation** | `git worktree` — one branch + working dir per session, shared object store | Session A overwriting B's files / hitting B's `index.lock` becomes *structurally impossible*. Canonical primitive; Claude Code `--worktree`, Cursor `/worktree`, Codex per-thread, git-lanes all converged here. |
| **Claim, don't collide** | Supervisor queue / blackboard self-selection / static role assignment | A task is *owned before work starts*. Two sessions can't pick the same work. Claude Code agent-teams does this with a `flock`-locked shared task list. |
| **Append-only substrate** | Event sourcing (emit intents, orchestrator sequences) / CRDT | Removes the entire concurrent-write conflict class — nothing to negotiate. Blackboard beats master-slave 13–57% empirically. |
| **Deferred, deterministic resolution** | Rebase-before-PR; `git merge-tree` / Clash pre-flight detection; 3-way merge at integration | When branches genuinely overlap, *git* surfaces it at a calm async checkpoint with full context — not two paused LLMs improvising. |

**The standard in one sentence:** *one branch per task, one worktree per session, claim tasks up front, merge/rebase at integration time — conflicts surface explicitly at merge, never silently at runtime.*

## Salvage vs. trap (separating the good instinct from the bad mechanism)

| Proposed element | Verdict | What to do with it |
|---|---|---|
| **Session identity** | KEEP | But commit messages are the **wrong carrier** — there is *no* standard for session-id-in-commit; `Co-Authored-By` is the only GitHub-recognized trailer; custom trailers (`Agent-Id:`) have no tooling support and **can't be read at write-time** (by the time it's committed, the conflict already happened). Move identity to a **live registry** the PreToolUse hook reads *before* writing. `session_id` is already in every hook's stdin JSON. |
| **Visibility ("see where each other works")** | KEEP | Central to blackboard/registry patterns. But consume it *proactively at pre-write time*, not reactively at conflict time: each session writes "editing file X" to a shared registry; the other's PreToolUse hook reads it and *backs off before writing*. |
| **PAUSE the sessions on conflict** | DROP | Creates simultaneous-decision mode = 95–100% deadlock at 3 agents. |
| **Open a channel + NEGOTIATE live** | DROP | The single most damning datum: the channel *raised* deadlock 25%→65%. The comms channel is the amplifier, not the fix. |
| **Live merge resolution at the coordination layer** | DROP | Semantic merge of two edits to one function is a content-merge-oracle problem; absent the oracle it escalates to a human anyway. Let `git merge`/rebase handle it deterministically at integration. |

**Reframe in one line:** keep identity + visibility, but point them **forward (prevent the collision)** instead of **backward (negotiate after it)**. Same information, opposite time-direction, opposite outcome.

## Is "worktree by default" the recommendation? Yes — conditionally.

`worktree` is the **default starting point, not an "always."** It solves **file isolation** (different sessions doing *different* work) but does **not** solve two sessions doing the *same* work, and does **not** isolate runtime resources (ports, DBs, caches). ([penligent.ai](https://www.penligent.ai/hackinglabs/git-worktrees-need-runtime-isolation-for-parallel-ai-agent-development/))

| Situation | worktree? | Why |
|---|---|---|
| Two sessions, **different tasks** (most of the time) | **Yes — default** | File conflicts structurally impossible; near-zero cost (shared object store); solves ~90%. |
| Two sessions, **same file / same task** | Not enough alone | Still conflicts at merge. The real fix is *claim up front* (Tier 2 role split). |
| Session runs **dev server / DB / migrations** | Not enough alone | worktrees share ports/DBs → give each session its own port/DB. |
| **Quick one-off**, single session | Overkill | Fragments `~/.claude/projects/` history per path (issue #34437). Just use main. |

**Recommendation wording:** *"If you'll run multiple sessions at once, make `git worktree` the default and start there. When you split the SAME task, layer role-assignment (claim) on top. When a shared directory is unavoidable, layer a PreToolUse lock on top."* worktree is the floor, not the ceiling.

## Recommended architecture for THIS user (mixed/unruled) — tiered, lightest first

Climb a tier only when you feel the specific pain the next tier removes. Jumping to the heaviest is the same overshoot as the negotiate design.

### Tier 0 — Default: stop sharing the directory (isolation)
Solves ~90% with almost no new machinery.
- One `claude --worktree <name>` per session → own branch, own `index`, own files. Overwrites and `index.lock` contention become *structurally impossible*.
- Integrate via **rebase-before-PR**; git surfaces real conflicts calmly at merge with full context.
- Cost ≈ zero (worktrees share the object store, created in seconds).
- **Pre-empt the known gotchas:** worktrees fragment `~/.claude/projects/` history per path ([issue #34437](https://github.com/anthropics/claude-code/issues/34437)); worktrees do **not** isolate runtime (ports/DBs/caches). File isolation ≠ runtime isolation.
- **Enough when:** sessions work on *different* tasks (most of the time).

### Tier 1 — Shared working dir unavoidable: PreToolUse lock + visibility registry
For the genuinely-shared-dir case, add the one enforcement point that is bypass-proof (hooks fire even under `--dangerously-skip-permissions`; CLAUDE.md prose cannot substitute).
- **PreToolUse hook** (matcher `Edit|Write`) using `session_id` from stdin JSON does `O_EXCL`/`flock` on a per-file lock (`/tmp/claude-locks/` or project `registry.json`). Holder writes; a contender **exits 2 and backs off** — *no negotiation, just yield-and-retry* (OCC, the right model for low-contention different-file edits).
- The same registry doubles as the **visibility layer** ("who's editing what"), consumed *before* writing.
- This is exactly Claude Code agent-teams' internal design (shared task list + `flock` claiming) — productized proof the pattern works.

### Tier 2 — Sessions coordinating *tasks* (not just files): claim-a-task
When collisions come from two sessions deciding to do the *same work*, isolation won't help — agree on ownership up front.
- Project-root `tasks.json` where each task is **claimed before work starts** via the Tier-1 lock. Supervisor-dispatch or blackboard self-selection serialize the *claim* (cheap moment) instead of negotiating the *result* (expensive moment).
- **Static role assignment** (CrewAI-style: "session A owns `/api`, session B owns `/ui`") is the zero-runtime-cost version and often all you need. Agent-teams' own documented workaround for lacking worktree isolation is exactly this: *"partition the work so each teammate owns a different set of files."*

### Tier 3 — Only if you need audit/replay/attribution: append-only event log
Heaviest tier; justified *only* for forensic "who did what, replayable."
- ESAA pattern: sessions emit structured **intent events** to an append-only log; a deterministic orchestrator sequences and applies them. No session mutates shared state directly → concurrent-write conflicts vanish. OMC's existing sentinel/notepad/shared-memory append pattern already maps onto this.
- CRDTs (CodeCRDT) are the lock-free auto-converging alternative; heavier conceptual investment — don't reach for it unless Tier 2 demonstrably fails.

**Ladder rule:** Tier 0 for "different tasks" (almost always). Tier 1 when a dir is truly shared. Tier 2 when the collision is about *what to do*, not *which file*. Tier 3 only for replay/audit. **At no tier do sessions pause and negotiate** — every tier replaces live negotiation with isolation (can't collide), pre-claim (claim before colliding), or append-only (nothing to collide on).

**Hard cap regardless of tier:** Anthropic recommends **2–4 parallel sessions**; 5+ hits rate limits and review breaks down. Cursor's hard limit is 8; Zylos puts the management ceiling at 8–10 worktrees. Don't design for 20 concurrent sessions — the useful regime is small, and small is exactly where negotiation is *least* needed.

## If/when this becomes an implementation (plan.md trigger)

This stays DESIGN-ONLY until the user hits a concrete pain. The likely first implementation is **Tier 0 ergonomics**, not the negotiation engine:

- A shell helper / alias to spawn `claude --worktree <name>` with consistent naming, and to clean up worktrees + de-fragment `~/.claude/projects/` history (the #34437 workaround) on teardown.
- Optionally a Tier-1 PreToolUse lock hook in `config/` if the user confirms a shared-dir case recurs.

A `plan.md` should be written **only** for the specific tier being built, and must respect claudebase's surgical/line-by-line meta-change rule (this repo orchestrates the very tooling under discussion).

## What was explicitly rejected and why (so it isn't re-proposed)

- **session-id in commit trailers as a coordination mechanism** — unreadable at write-time; no tooling; conflict already happened by commit time. Use a live registry + hooks.
- **pause-and-negotiate-at-conflict** — 95–100% deadlock at 3 agents; comms channel *worsens* it to 65%; silent-stall failure signature. The industry avoids this, doesn't solve it.
- **runtime consensus (Paxos/Raft) at the file layer** — 100×–1000× a lockfile; belongs inside lock services, not at the call site.
- **designing for many (20+) concurrent sessions** — the documented useful regime is 2–4; build for that.

## Sources

- [Git worktree (official)](https://git-scm.com/docs/git-worktree) · [Git api-lockfile](https://git-scm.com/docs/api-lockfile) · [git-interpret-trailers](https://git-scm.com/docs/git-interpret-trailers)
- [Claude Code: parallel sessions with worktrees](https://code.claude.com/docs/en/worktrees) · [agent teams](https://code.claude.com/docs/en/agent-teams) · [hooks](https://code.claude.com/docs/en/hooks)
- [Augment Code — git worktrees for parallel AI agents](https://www.augmentcode.com/guides/git-worktrees-parallel-ai-agent-execution) · [multi-agent failure modes](https://www.augmentcode.com/guides/multi-agent-ai-systems)
- [Zylos — git worktree isolation patterns](https://zylos.ai/research/2026-02-22-git-worktree-parallel-ai-development) · [Penligent — worktrees need runtime isolation](https://www.penligent.ai/hackinglabs/git-worktrees-need-runtime-isolation-for-parallel-ai-agent-development/)
- [Cursor worktrees](https://cursor.com/docs/configuration/worktrees) · [Codex parallel agents](https://nimbalyst.com/blog/how-to-run-multiple-codex-agents-in-parallel/) · [git-lanes](https://github.com/bugrax/git-lanes)
- [Arion Research — agentic conflict resolution](https://www.arionresearch.com/blog/conflict-resolution-playbook-how-agentic-ai-systems-detect-negotiate-and-resolve-disputes-at-scale) · [Marc Brooker — optimism vs pessimism](https://brooker.co.za/blog/2023/10/18/optimism.html)
- [ReputAgent — DPBench deadlock data](https://reputagent.com/research/why-ai-agents-keep-getting-stuck-when-they-decide-together) · [Cogent — orchestration failure playbook 2026](https://cogentinfo.com/resources/when-ai-agents-collide-multi-agent-orchestration-failure-playbook-for-2026)
- [Chubby lock service (Burrows 2006)](https://mwhittaker.github.io/papers/html/burrows2006chubby.html) · [etcd API guarantees](https://etcd.io/docs/v3.5/learning/api_guarantees/)
- [ESAA — event sourcing for autonomous agents (arXiv 2602.23193)](https://arxiv.org/abs/2602.23193) · [Blackboard multi-agent (arXiv 2510.01285)](https://arxiv.org/html/2510.01285v1) · [CodeCRDT (arXiv 2510.18893)](https://arxiv.org/pdf/2510.18893)
- [Async SE agents (Geng & Neubig, arXiv 2603.21489)](https://arxiv.org/pdf/2603.21489)
- Claude Code worktree history fragmentation: [issue #34437](https://github.com/anthropics/claude-code/issues/34437)

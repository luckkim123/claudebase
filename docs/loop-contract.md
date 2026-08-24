# The loop contract

Seven properties every autonomous loop in this stack must be able to point at.
`runtime/hooks/loop_lint.py` reports which ones each loop skill can evidence.

This is a **convention plus a checker, not a runtime**. No loop is rewritten to
run on shared machinery: each loop's stop condition is domain knowledge — only
`oh-my-docs` knows what "verify PASS" means and only `oh-my-experiments` knows
what `deadline_passed` means. What is shared is the checklist and the linter
that reads it.

## Why the first five

`cobusgreyling/loop-engineering`'s `loop-audit` scores loop maturity across 35
weighted signals. Read from its `auditor.ts` (2026-08-15), three weights
dominate — `stateFile` 18, `verifier` 14, `triage` 14 — and its top level is
unreachable without `verifier` + `stateFile` + `budgetDoc` + `runLog` +
`loopActivity` all present, whatever the total score. `loopActivity` was added
in its v1.4 for a stated reason: to stop a project that only *scaffolded* loop
files from claiming the top level.

That is this repo's 2026-08-14 finding from the other direction — *measure a
guard's firing rate before trusting the guard*. A loop nobody can prove ran is
a guard nobody measured.

## Why a sixth, added 2026-08-24

The five above bound a loop that runs too long. They say nothing about one that
stops too early, and that is a named failure mode, not a hypothetical: StateM
(arXiv 2608.15089) lists four ways a long-horizon agent fails even when its model
can do every step — *"lose track of mutable state, fail to reactivate lessons from
earlier executions, skip known procedures, or **stop prematurely**."*

Only the first is covered here, by property 1. And the cap in property 3 points
the **opposite** way: it exists to cut a loop off, never to keep one going.

Two loops in this stack had already solved it without the contract naming it, and
the second solved it better:

- `omp-garden` stops on "no new findings" and says so explicitly — the count is
  **read from state, not judged**. Its `garden-state.json` carries
  `sweeps[].found/new/resolved`.
- `oh-my-experiments` writes `open_leads` into the approval artifact and also
  `wiki_coverage {pages, with_status}` — the **denominator**. Its own docstring
  says why: *"'none open' is indistinguishable from 'nobody ever filed one' unless
  the denominator travels with it."* That is not theoretical either — one
  workspace measured **0 of 540 pages carrying any status** (2026-08-10), so every
  launch that round passed a gate that had never held anything.

The sixth property is that pair, because the first half alone reproduces the trap:
`found: 0` in `garden-state.json` cannot distinguish a clean tree from a sweep
that never looked.

Measured across the nine loops the linter tracks (2026-08-24): **two** externalise
the stop, **one** carries the denominator. `docs-revise` names "remaining defects"
only in the report it prints when it gives up — reporting, not deciding.

## Why a seventh, added 2026-08-24

The same StateM list names a second mode the contract did not cover: *"fail to
reactivate lessons from earlier executions"*. That one is not a gap in the stack's
**assets** — every plugin has a store — it is a gap in what the loops **read**.

Counted the same day, this machine: `.omp/learned.md` (2 observations in the vault,
both already closed), `.omp/wiki/` 5 pages, `.omd/wiki/` 11, `.oms/wiki/` 18,
`.omc/wiki/` 183, omx `registry/findings/` 9, plus 256 auto-memory files across two
projects. Then the loops: **0 of 9 loop skills state a read of any of them.**

The reactivation that does exist sits **one hop below the loop**. `exp-loop`
delegates to `exp-analyze` and `exp-design`, and it is `exp-design` that carries the
best version of this property anywhere in the stack — two category-scoped queries
with the reason written down:

> `omx wiki query --root <root> "<the symptom you are diagnosing>" --category decision`
> `omx wiki query … --category pattern`
> These two categories are queried for a reason: `decision` holds why a cause was
> adopted/discarded with the data that decided it (= a past confirmed cause), and
> `pattern` holds recurring metric behaviours.

So the property is a promotion, like the sixth — it has a working exemplar, it is
just not in any loop's own text. And the cost of not having it is measured, not
hypothetical: one launch re-walked a cuDNN fix that was already written down,
because the wiki held it and the launch script did not, at 18.9 s/iter.

## The seven

**1. State file — a path, and what it holds.**
A file that outlives the session and records where the loop is. Not the artifact
tree, and not the conversation: if the only record of "which defects round 2
already saw" is the context window, the loop cannot survive a compaction and
cannot be audited afterwards.

**2. Stop condition — deterministic, not model confidence.**
The predicate must be readable by something other than the model's opinion:
`passes: true` in a file, an exit code, a `PASS` verdict from a separate
verifier, a `"deadline_passed": true` field. "When it looks good" is not a stop
condition.

**3. Attempt cap and escalation path — both numeric.**
A number of rounds, retries, or blocked stops, plus what happens when the number
is hit. Escalation means a human, named explicitly.

**4. Verifier in a different context from the author.**
Measured by Anthropic in *Harness Design for long-running apps* (2026-03-24):
an agent asked to evaluate its own work confidently praises it. The verifier is
a separate agent or skill invocation, never the context that produced the work.

**5. Activity evidence — the loop has actually run.**
The state file from (1) exists on disk somewhere, with a timestamp. A loop that
has never left a trace is scaffolding, and its other four properties are
untested claims.

**6. Externalised completion — a residue count, and its denominator.**
Two halves, and one without the other is worse than neither. The loop declares
itself done by **reading a count of unresolved items out of the state file**,
never by concluding it — that is what stops property 2 from degrading into "the
model thinks it finished". And it records **how many items were examined** beside
that count, so a zero can be read instead of trusted. Without the denominator,
"0 remaining" and "nothing was ever counted" are the same artifact.

**7. Lesson reactivation — the loop reads before it derives.**
Before acting, the loop consults what earlier runs of it already established: a
wiki query, `learned.md`, a prior-diagnosis lookup. **A write is not a
reactivation** — every one of these stores has something writing to it, and a loop
that only appends to its own knowledge base has not read it. This is the property
that keeps a loop from re-deriving, at full cost, a conclusion it already owns.

## What the linter does and does not do

It greps the skill body for each property and **prints the matched line**. That
is deliberate: a boolean table from a keyword matcher is exactly the artifact
that looks clean while being wrong — three hand-written scorers did precisely
that here on 2026-08-15. Evidence beside every hit lets the reader overrule it.

It cannot judge semantics. A skill that says "3 times" inside a `<Bad>` example
rather than a rule still passes check 3, and only the printed line reveals
which it was. Treat the output as a reading aid, not a verdict — the posture
`harness_stats.py` takes, which reports numbers and refuses to conclude.

**It lints the installed plugin cache, not the source repo, by default.** The
cache is what actually runs; a source tree always looks fixed. This stack has
already lost a week to that distinction — omha's `route_log.py` was correct in
git and absent from the loaded cache, so `.omha/routing.jsonl` recorded nothing
while the repo showed working code.

**It follows the compact-skill shim.** `oh-my-claudecode`, `oh-my-scholar` and
`oh-my-docs` register a ~12-line `skills/<name>/SKILL.md` pointing at
`skill-bodies/<name>/SKILL.md`. A linter reading only the registered file scores
every one of those loops as failing every check, and reports no error while
doing it.

**Check 5 over-counts, and the evidence line is the correction.** The activity
column globs every path literal the skill names — including the ones it names to
send you elsewhere. `omp-garden` scores activity off `.omp/STRUCTURE.md` because
its Do_Not_Use_When routes there. Read the example path under the row before
reading the number as proof the loop ran.

**Check 6 catches reporting and deciding with the same pattern, and only the
evidence line tells them apart.** First run, 2026-08-24: `resid` scored `ok` for
three loops, and two of them matched on *"Or a stop report (same defect 3 times /
max iterations exceeded + **remaining defects**)"* — that is what `docs-revise`
and `scholar-revise` print when they give up, not what they consult to decide.
Only `omp-garden`'s hit is a rule: *"the stop condition is 'no new findings', and
it is **read from state, not judged**."* Read the line before reading the column.

**And `denom` is a code-level property the prose grep cannot see.** Same run: all
nine loops scored `--`, yet `oh-my-experiments` does carry a denominator —
`wiki_coverage {pages, with_status}` lives in `omx_core/loop.py`, not in the skill
body the linter reads. A `--` here means "not stated in the skill", never "absent
from the system". That asymmetry is the same one check 4 has, below.

**Check 7 has the same one, and it is structural rather than incidental.** The
loops that reactivate lessons mostly do it through a **delegated sub-skill**, so
the read is absent from the loop's own text by construction. First run,
2026-08-24: 1 of 9 scored `ok`, and it was `exp-loop` matching on its backlog
reconcile (`omx wiki list --status needs-experiment`) — while the strong version
of the property, `exp-design`'s two category-scoped queries, is a file the linter
never opens because `exp-design` is not itself a loop. The linter is not taught to
follow delegation: the hand-off is prose ("Delegate to `exp-design`"), and a
regex over skill names would trade this blind spot for false positives.

**Table [B]'s unguarded list is a fact, not a verdict.** It names loop-carrying
plugins with no blocking Stop hook, and reading that as a defect list is wrong —
audited 2026-08-24, both entries had a stated reason and neither needed a hook:

| Plugin | Why there is no blocking Stop hook |
|:---|:---|
| `oh-my-docs` | **D6**, a plugin-wide decision recorded in three release plans: *"모든 신규 훅은 stdlib-only·fail-open·advisory — `decision: block` 절대 금지."* All six of its hooks honour it. The same transition **is** instrumented, advisorily: `docs_verify_emit` arms a `.verify-pending` sentinel on every build, `docs_stop_guard` surfaces the unresolved ones at Stop, and its docstring states the reason — *"deferring verify is legitimate."* |
| `oh-my-project` | `omp-garden` is **report-only and ships no scheduler** — "omp does not schedule anything… arming it is the human's call." One sweep is one invocation, so there is no in-session iteration for a Stop hook to hold open. A blocking hook here would hold the *human's* turn open to force a sweep nobody asked for. |

The contrast that makes this legible is `oh-my-scholar`, whose `scholar-revise` is
the structural twin of `docs-revise` ("the paper-edition of ralph") and *does*
carry a blocking `scholar_stop_guard.py` — scoped to a live `revise-<slug>.json`
marker with six exemptions and a durable `stop_blocks` cap. Same loop shape, one
plugin enforces and one declines, and both positions are written down. That is the
contract working: it asks a loop to be able to point at its properties, not to
implement them the same way.

**Check 4 has a blind spot in `oh-my-claudecode`.** Ralph's real anti-self-
approval enforcement is a Stop hook in compiled JS (`dist/`, referenced from
`hooks/hooks.json`), not prose — a prose grep finds the reviewer delegation but
cannot see the gate that makes it mandatory. Prose absence there is not
enforcement absence.

## Standing as of 2026-08-16

Run `python3 runtime/hooks/loop_lint.py --root <project>` for the live table.
The gaps that motivated writing this down:

| Loop | Gap |
|:---|:---|
| `ultragoal` | Weakest row — no deterministic stop, no numeric cap, no separate verifier |
| `ultrawork` | No state file, no cap |
| `ultraqa` | Cap without a named escalation path |
| `docs-revise` | Round history lives in the conversation; the `.omd` tree holds artifacts, not loop state |
| ~~`scholar-revise`~~ | **Closed since.** It now writes `.oms/state/revise-<slug>.json` — round, strike counts, `max_rounds`, `ttl_hours` — and `scholar_stop_guard.py` reads that marker to block a premature stop |
| all of them | No two share a state-file convention — `.omc/state/sessions/<id>/prd.json`, `pending-launch.json` + ledger, an artifact tree |

`oh-my-project 0.12.0`'s `omp-garden` is the first loop written against this
document rather than audited by it, and scores all five of the original
properties. On the sixth it has the half that matters most — its stop count is
read from state — and lacks the denominator: `found: 0` does not say how many
paths the sweep examined. On the seventh it scores `--` along with seven others:
`.omp/learned.md` sits beside `garden-state.json` and no sweep reads it.

Nothing here asks an existing loop to change. The point of writing it down is
that the next loop should not invent its own convention for any of the seven.

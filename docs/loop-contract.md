# The loop contract

Six properties every autonomous loop in this stack must be able to point at.
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

## The six

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
| `docs-revise`, `scholar-revise` | Round history lives in the conversation; the `.omd`/`.oms` tree holds artifacts, not loop state |
| all of them | No two share a state-file convention — `.omc/state/sessions/<id>/prd.json`, `pending-launch.json` + ledger, an artifact tree |

`oh-my-project 0.12.0`'s `omp-garden` is the first loop written against this
document rather than audited by it, and scores all five of the original
properties. On the sixth it has the half that matters most — its stop count is
read from state — and lacks the denominator: `found: 0` does not say how many
paths the sweep examined.

Nothing here asks an existing loop to change. The point of writing it down is
that the sixth loop should not invent a seventh convention.

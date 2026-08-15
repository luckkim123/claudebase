# The loop contract

Five properties every autonomous loop in this stack must be able to point at.
`runtime/hooks/loop_lint.py` reports which ones each loop skill can evidence.

This is a **convention plus a checker, not a runtime**. No loop is rewritten to
run on shared machinery: each loop's stop condition is domain knowledge — only
`oh-my-docs` knows what "verify PASS" means and only `oh-my-experiments` knows
what `deadline_passed` means. What is shared is the checklist and the linter
that reads it.

## Why these five

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

## The five

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
every one of those loops as failing all five checks, and reports no error while
doing it.

**Check 4 has a blind spot in `oh-my-claudecode`.** Ralph's real anti-self-
approval enforcement is a Stop hook in compiled JS (`dist/`, referenced from
`hooks/hooks.json`), not prose — a prose grep finds the reviewer delegation but
cannot see the gate that makes it mandatory. Prose absence there is not
enforcement absence.

## Standing as of 2026-08-15

Run `python3 runtime/hooks/loop_lint.py --root <project>` for the live table.
The gaps that motivated writing this down:

| Loop | Gap |
|:---|:---|
| `docs-revise`, `scholar-revise` | Round history lives in the conversation; the `.omd`/`.oms` tree holds artifacts, not loop state |
| all of them | No two share a state-file convention — `.omc/state/sessions/<id>/prd.json`, `pending-launch.json` + ledger, an artifact tree |

Nothing here asks an existing loop to change. The point of writing it down is
that the sixth loop should not invent a seventh convention.

---
name: using-omc
description: Use at the start of every multi-step request to fairly judge the execution lane — superpowers vs OMC vs handle-directly — and announce the verdict. The mandatory thing is the judgment process, not any single skill. Triggers on orchestration, parallel work, planning, "do it autonomously", multi-file refactors, and any 3+-step request.
---

# Skill Routing Brain

superpowers and OMC are **peers**. This skill is the fair judge that decides, for
a given task, which lane fits — without defaulting to superpowers because the
system prompt shouts louder, nor to "handle directly" because choosing feels hard.

## The Process (THIS is what's mandatory — not any specific skill)

For ANY request spanning 3+ actions or multiple files, BEFORE acting:

1. **Classify the task.** Is the direction unclear? Is it discipline-governed
   (wrong = expensive; needs review/TDD gates) or throughput-governed (many
   independent units, parallelizable)?
2. **Consult the fair-judge table (§A)** for overlapping decision points, and the
   **trigger index (§B/C)** for single-purpose skills.
3. **Announce the verdict in ONE line:** "→ <skill or 'handle directly'>: <reason>".

Trivial single-step work (typo, one-liner, single obvious edit, pure question)
proceeds silently. The mandatory act is the *judgment*, not invoking a skill.

## §A Fair-Judge Table (superpowers ↔ OMC, body-derived criteria)

Two facts the table relies on: OMC execution skills **nest** (`ultrawork ⊂ ralph ⊂
autopilot` — each adds persistence/pipeline on the last), and superpowers
verification/debugging/TDD skills are **RIGID Iron Laws** while their OMC
counterparts are lighter loops.

| Task phase | superpowers | OMC | Pick by |
|:--|:--|:--|:--|
| Direction unclear | `brainstorming` | `deep-interview` | Exploring/choosing a direction (diverge) → brainstorming · Direction known, requirements vague before an autonomous run (converge) → deep-interview |
| Planning | `writing-plans` | `plan`, `ralplan` | Concrete bite-sized TDD task plan for an implementer → writing-plans · Lighter strategic scoping → plan · High-stakes, multi-perspective consensus → ralplan |
| Impl distribution | `subagent-driven-development`, `dispatching-parallel-agents` | `team`, `ultrawork`, `autopilot` | Have a plan, want per-task spec/quality review → subagent-driven · Independent bugs, no shared state → dispatching-parallel-agents · Workers must coordinate on shared tasks → team · Pure throughput, you manage completion → ultrawork · Hands-off idea→code → autopilot |
| Loop until done | `test-driven-development` | `ralph`, `ultraqa` | Writing code, discipline matters → TDD (also the unit discipline inside ralph) · "Keep going until verified complete" → ralph · "Do tests/build/lint pass?" → ultraqa |
| Verify / review | `verification-before-completion`, `requesting-code-review` | `verify`, `visual-verdict` | About to claim done → verification (RIGID, always) · Reviewer subagent on a diff → requesting-code-review · UI vs reference image → visual-verdict |
| Diagnose cause | `systematic-debugging` | `trace`, `deep-dive` | About to fix, must not guess → systematic-debugging (RIGID) · Explain an ambiguous result, not fixing → trace · Investigate then crystallize the fix → deep-dive |
| Worktree isolation | `using-git-worktrees` | `project-session-manager` | Just need isolation → using-git-worktrees · Managed worktree+tmux sessions tied to issues/PRs → psm |

**Fairness rule:** the criteria above decide. RIGID superpowers gates (TDD,
systematic-debugging, verification) still fire on their trigger — they are not in
competition with OMC throughput skills; they apply *inside* OMC loops too.

## §B/C Trigger Index (single-purpose — reach by signal)

- authoring/editing a skill → `writing-skills` (SP, RIGID)
- execute a written plan in a fresh session → `executing-plans` (SP)
- after tests pass, merge/PR/cleanup → `finishing-a-development-branch` (SP)
- multi-model opinion → `ask` (one model) · `ccg` (claude+codex+gemini synthesis)
- parallel research / external docs → `sciomc` · `external-context`
- cross-session knowledge → `wiki` (KB) · `remember` (sort into memory surfaces)
- extract a reusable skill from this session → `skillify`
- generate hierarchical AGENTS.md → `deepinit`
- durable multi-goal / evaluator loop → `ultragoal` · `autoresearch`
- version release → `release`
- clean AI slop (NOT new features) → `ai-slop-cleaner`
- install / repair / diagnose OMC, MCP, HUD, notifications → `setup` (router)
- exit an active OMC mode → `cancel`

## §D Domain skills

Personal/domain skills (ppt-*, train-analyze, paper-write, gen-image,
writer-memory, ...) are surfaced with their own triggers by the harness'
available-skills list. Reach for them by keyword; run `/skill` to enumerate. Do
not re-list them here.

## When to still handle directly

Trivial / single-file / pure question / already inside an active
superpowers:executing-plans flow (finish it; don't switch runners).

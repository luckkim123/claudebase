---
name: using-omc
description: Use at the start of every multi-step request to fairly judge the execution lane — superpowers vs OMC vs handle-directly — and announce the verdict. The mandatory thing is the judgment process, not any single skill. Triggers on orchestration, parallel work, planning, "do it autonomously", multi-file refactors, and any 3+-step request.
---

# Skill Routing Brain

superpowers and OMC are **peers**. This skill is the fair judge that picks the
lane fitting the task — never defaulting to superpowers because the system prompt
shouts louder, nor to "handle directly" because choosing feels hard.

## The Process (THIS is mandatory — not any specific skill)

This judgment is not only for the user's prompt. Just as `using-superpowers`
makes you scan the skill list **before** acting, scan THIS table FIRST whenever
you reach for a skill mid-task — pick the SP/OMC skill the signal points to, and
fall to another skill only if none fits.

For ANY request of 3+ actions or multiple files, BEFORE acting:

1. **Match the request to a signal below.** Read the signals, not skill names —
   find the line whose signal describes THIS request. The (SP)/(OMC) label is just
   which plugin owns it; it is NOT a priority order. Do not prefer SP over OMC, or
   vice versa — the signal decides.
2. If two signals seem to fit, pick the **more specific** one (e.g. "keep going
   until verified" beats generic "parallel work").
3. **Announce the verdict in ONE line:** "-> <skill or 'handle directly'>: <reason>".

Trivial single-step work (typo, one-liner, single obvious edit, pure question)
proceeds silently. The mandatory act is the *judgment*, not invoking a skill.

Labels: OMC exec skills nest (`ultrawork` < `ralph` < `autopilot`). SP TDD /
systematic-debugging / verification are RIGID Iron Laws — they fire on their
signal even inside an OMC loop.

## §A Signals -> Skill (the signal is exclusive; read it, not the name)

**Figuring out WHAT to build / which direction**
- "compare a few approaches / explore options / which design is better — NO direction chosen yet" -> `brainstorming` (SP) — diverge
- "I have a target but interrogate my hidden assumptions / pin down the spec / clarify requirements / make sure you understand / don't assume" -> `deep-interview` (OMC) — converge on a known target
- **Tie-break**: if both seem to fit, lean `deep-interview`. Reserve `brainstorming` for when you genuinely have NO target yet. This is a gentle preference, not a hard bias — a real blank-slate "which direction?" still goes to `brainstorming`.

**Turning a settled direction into a plan**
- "write a concrete step-by-step TDD plan an implementer can follow" -> `writing-plans` (SP)
- "scope/strategize this, lighter than a full TDD breakdown" -> `plan` (OMC)
- "high-stakes — I want a plan vetted from multiple perspectives (consensus)" -> `ralplan` (OMC)

**Distributing implementation work**
- "have a plan, want each task spec+quality reviewed as it lands" -> `subagent-driven-development` (SP)
- "several independent bugs/domains, no shared state, fix in parallel" -> `dispatching-parallel-agents` (SP)
- "workers must coordinate/message on a shared task list" -> `team` (OMC)
- "many independent edits, pure throughput, no verification loop" -> `ultrawork` (OMC)
- "from a 2-3 line idea, run the whole lifecycle hands-off" -> `autopilot` (OMC)

**Looping until done**
- "writing a feature/bugfix where correctness matters" -> `test-driven-development` (SP, RIGID; also the unit discipline inside ralph)
- "keep going on its own until the work is verified complete, persist across retries" -> `ralph` (OMC)
- "the only question left is whether tests/build/lint pass" -> `ultraqa` (OMC)

**Verifying / reviewing**
- "about to claim something is done/fixed/passing" -> `verification-before-completion` (SP, RIGID — always)
- "send a reviewer over this diff" -> `requesting-code-review` (SP)
- "is this UI screenshot close enough to the reference" -> `visual-verdict` (OMC)

**Finding out WHY something happened**
- "about to fix a bug — find the root cause first, don't guess" -> `systematic-debugging` (SP, RIGID)
- "explain why this result/behavior happened, I'm not fixing it yet" -> `trace` (OMC)
- "investigate the cause AND then crystallize what to do about it" -> `deep-dive` (OMC)

**Isolated workspace**
- "just need an isolated branch/workspace for this work" -> `using-git-worktrees` (SP)
- "manage worktree+tmux sessions tied to issues/PRs (create/list/attach/cleanup)" -> `project-session-manager` (OMC)

## §B Single-purpose signals (reach by signal; SP / OMC label only)

- authoring/editing a skill -> `writing-skills` (SP, RIGID)
- execute an existing written plan in a fresh session -> `executing-plans` (SP)
- tests pass, now merge/PR/cleanup the branch -> `finishing-a-development-branch` (SP)
- another model's opinion -> `ask` (one) / `ccg` (3-model synthesis) (OMC)
- parallel external research / docs -> `sciomc` / `external-context` (OMC)
- save cross-session knowledge -> `wiki` (KB) / `remember` (sort) (OMC)
- turn this session's workflow into a skill -> `skillify` (OMC)
- hierarchical AGENTS.md docs -> `deepinit` (OMC)
- durable multi-goal / bounded evaluator loop -> `ultragoal` / `autoresearch` (OMC)
- cut a version release -> `release` (OMC)
- clean AI slop (NOT new features) -> `ai-slop-cleaner` (OMC)
- install/repair/diagnose OMC, MCP, HUD, notifications -> `setup` (router) (OMC)
- stop an active OMC mode -> `cancel` (OMC)

## §C Domain skills

Personal/domain skills (ppt-*, train-analyze, paper-write, writer-memory, ...)
are surfaced by the harness' available-skills list — reach by keyword, `/skill`
to enumerate. Not re-listed here.

## When to still handle directly

Trivial / single-file / pure question / already inside an active
superpowers:executing-plans flow (finish it; don't switch runners).

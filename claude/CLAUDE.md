# CLAUDE.md (user-scope)

Universal behavioral rules for Claude Code, applied across **all** projects and machines.

This file is symlinked to `~/.claude/CLAUDE.md` by the installer. Project-level `CLAUDE.md` files in individual repos add project-specific rules on top of these.

> Source: derived from [Karpathy's observations](https://x.com/karpathy/status/2015883857489522876) on LLM coding pitfalls (the four principles), plus personal operational limits.

---

## Behavioral Principles

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

- State assumptions explicitly. If uncertain, ask.
- Multiple interpretations exist? Present them — don't pick silently.
- Simpler approach available? Push back.
- Confused? Stop. Name what's unclear. Ask.

### 2. Simplicity First

**Minimum code/content that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and 50 would do, rewrite.
- Minimize test scripts and temporary file creation.

Test: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what was requested. Clean up only your own mess.**

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- Notice unrelated dead code? Mention it — don't delete.
- Only do what user asks, nothing more.

Test: every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:

| Instead of... | Transform to... |
|:---|:---|
| "Add validation" | "Write tests for invalid inputs, then make them pass" |
| "Fix the bug" | "Write a test that reproduces it, then make it pass" |
| "Refactor X" | "Ensure tests pass before and after" |

For multi-step tasks, state a brief plan:

```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

### 5. Evidence Before Assertion

**Don't invent. Verify or surface uncertainty.**

- Technical claims (API signatures, version numbers, dates, library behavior) — verify via docs/code/search before asserting. Training data drifts.
- Citations and references — never fabricate. If you can't locate a source, say so explicitly.
- Internal facts (file paths, function names, line numbers) — read the file, don't recall.
- For factual writing (technical docs, research notes, anything published), every non-trivial claim should trace to a source: provided material, the codebase, or a search result.

Test before commit: "Does every non-obvious statement have something I could point to?" If no, search or qualify.

---

## Operational Limits

- **3-Strike Rule**: same approach fails 3 times → change method immediately.
- **15-Min Limit**: stuck > 15 min on one problem → try different approach.

---

## Workflow

- **Skill Utilization**: use available skills (via `/skill-name`) when their expertise matches the task. Skills tell you HOW to approach things — invoke them before acting.
- **Project CLAUDE.md First**: when a project has its own `CLAUDE.md` or `.claude/rules/*`, read it before working. Project rules override these universal ones.
- **Date Awareness**: ALWAYS check current date (shown in `<env>` tags). When year not specified, assume current year or future. NEVER create past-dated artifacts (commits, calendar events, task deadlines, file timestamps) unless explicitly requested. Before creating a new dated artifact, scan for an existing one — update rather than duplicate.
- **Compound Learnings**: when a task surfaces a non-obvious decision, surprising result, or hard-won fix, log a one-line entry to the auto-memory system (`~/.claude/projects/<project>/memory/`) before ending the task. Reference past learnings when starting similar work — each task should make the next one easier, not harder.
- **Clear on Loop**: if you've corrected the same issue more than twice in one session, the context is polluted with failed approaches. Run `/clear` and restart with a more specific prompt incorporating what you learned. A fresh session with a better prompt almost always outperforms a long session with accumulated corrections.

---

## OMC (oh-my-claudecode) Orchestration

`oh-my-claudecode@omc` is enabled in `enabledPlugins` and provides multi-agent orchestration via `/oh-my-claudecode:*` slash commands. **Active use level: middle** — Claude does not auto-route to OMC, but **proposes** OMC delegation when a task clearly benefits from it.

### When to propose OMC (proactive)

Propose OMC at the start of a task when **two or more** of these are true:

- The user describes work that touches **3+ distinct files or subsystems**.
- The work has **clear independent subtasks** that can run in parallel (e.g., "implement A, B, C, and wire them together").
- The user explicitly asks for **autonomous, long-running work** ("just do it", "until done", "don't ask me each step").
- The task fits a named OMC command pattern below.

Proposal format (one short sentence, then continue if user agrees):

> "이 작업은 `/oh-my-claudecode:<command>`로 위임하는 게 빠를 것 같은데, 그렇게 진행할까요?"

If the user says yes — invoke the OMC command. If no, fall back to the normal Brainstorm → Plan → Execute workflow above.

### When NOT to propose OMC

- Single-file edit, typo, one-liner, or trivial fix.
- The user is in **learning output style** (current goal is to teach/explain — autopilot would defeat that).
- Reference-based writing (concept notes, paper reviews) — see Evidence Before Assertion; OMC's parallel mode increases hallucination risk on citation-bound work.
- Tasks already inside an active `superpowers:executing-plans` flow — finish the current plan instead of switching meta-runners.

### Useful OMC commands (use directly when the pattern matches)

| Pattern | OMC command | Notes |
|:---|:---|:---|
| Full multi-step feature from natural-language brief | `/oh-my-claudecode:autopilot` | Replaces brainstorm → plan → execute when user explicitly wants hands-off. |
| Bounded refactor / many parallel small edits | `/oh-my-claudecode:ultrawork` | Max parallel subagents. Good for "rename X in 20 files". |
| Multi-role review (architect + QA + critic) | `/oh-my-claudecode:team` | Use before merging non-trivial PRs. |
| Long-running iterative loop (write-test-fix) | `/oh-my-claudecode:ralph` | When success is checkable (tests pass, lints clean). |
| Deep research into a library/topic before designing | `/oh-my-claudecode:deep-interview` | Pairs well with `context7` MCP. |

### Coexistence rules

- **HUD statusline**: OMC owns it. Configuration lives in `omcHud` block of `~/.claude/settings.json`. To switch presets in-session: `/oh-my-claudecode:hud minimal|focused|full`.
- **Do not** propose OMC's `team` or `autopilot` for tasks inside this `claude-settings` repo itself — meta-changes to the settings that orchestrate OMC should stay surgical and reviewed line-by-line.
- **Subagent dispatch precedence**: `superpowers:subagent-driven-development` is preferred when a written plan already exists (it enforces reviewer agents per task). OMC `/team` is preferred when no plan exists and the user wants the team to scope-then-execute.

---

## Versioned Release Workflow (preferred for non-trivial features)

When the user proposes a non-trivial change to a versioned package
(`package.xml`, `setup.py`, `pyproject.toml`, `Cargo.toml`, etc.) — new
feature, redesign, or breaking refactor — drive it through a numbered
release cycle rather than ad-hoc commits. This keeps every change
traceable, reviewable, and reversible.

**The five-stage loop**

1. **Brainstorm → spec**. Use `superpowers:brainstorming` to explore the
   problem one question at a time, settle 2–3 design decisions, then save
   a written design doc (`docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`).
   No code yet.
2. **Plan**. Use `superpowers:writing-plans` to break the spec into
   bite-sized, TDD-style tasks (file paths, exact code, expected test
   output, commit message per task). Save to
   `docs/superpowers/plans/YYYY-MM-DD-<topic>.md`.
3. **Execute**. Prefer `superpowers:subagent-driven-development`: one
   fresh implementer subagent per task, followed by a fresh spec-compliance
   reviewer **and** a fresh code-quality reviewer. Each task ends in a
   conventional-commit on the feature branch. The controller does not
   self-implement; it dispatches and adjudicates reviewer findings.
4. **Release**. The final task always bumps the version in every
   manifest, fills the `[Unreleased]` block in `CHANGELOG.md` with
   Removed / Added / Changed / Verification / Notes, refreshes the
   user-facing section of `README.md`, and runs the full test suite +
   build one last time.
5. **PR**. Push the branch, open a PR with a Summary + Test plan
   checklist. Manual smoke items live in the checklist as `[ ]` so they
   gate merge. Merge happens only on explicit user approval, squash mode,
   to keep main linear.

**Why this works**

- The four artefacts (branch + commit chain + CHANGELOG entry + PR
  description) stay synchronised, so any future regression is traceable
  to one commit, one CHANGELOG block, one reviewable PR.
- Subagents prevent context pollution: a 10-task feature finishes with
  the controller's context still clean enough to coordinate the release.
- Spec compliance and code quality are reviewed by *different* fresh
  agents — each catches issues the other misses (spec drift vs. local
  craft).

**Anti-patterns**

- Bumping the version inline with feature work. Version bumps belong in
  the dedicated final task so the diff is always "version + CHANGELOG +
  README" — easy to audit.
- Skipping the spec because the change "feels small". Spec-less tasks
  consistently undershoot edge cases (migration of old config, forward-
  compat of yaml fields, headless test gotchas).
- Letting the controller implement to "save time". The controller's
  judgment degrades after ~3 implementation rounds; subagent dispatch
  preserves it for the long haul.

**Patch releases (vX.Y.Z+1)** skip stage 1 and use a single-task plan:
the bug fix + version bump + CHANGELOG patch entry + PR — same gates,
smaller surface.

---

## Environment Variables

Path variables referenced by skills/configs (e.g., `paper-write` venue YAMLs use `${WORKSPACE_TEMPLATE_DIR}`). Resolve in this order: shell env → this section → project-scope CLAUDE.md.

| Variable | Value | Used by |
|:---|:---|:---|
| `WORKSPACE_TEMPLATE_DIR` | `~/Desktop/workspace/00-09_Meta/01_Templates` | `paper-write` venue YAMLs (`template_dir`) |

Variables expand `~` via `os.path.expanduser`. After resolution the resulting path MUST exist — fail loud if not.

---

## Tradeoff Note

These guidelines bias toward **caution over speed**. For trivial tasks (typo fixes, obvious one-liners), use judgment — not every change needs the full rigor.

The goal is reducing costly mistakes on non-trivial work, not slowing down simple tasks.

---

**Last Updated**: 2026-05-18
**Managed by**: [`claude-settings`](https://github.com/luckkim123/claude-settings) — edit at `~/claude-settings/claude/CLAUDE.md`, the symlink picks up changes automatically.

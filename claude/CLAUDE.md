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
| **Q&A 흐름과 파일 수정을 패널 분리** | `/oh-my-claudecode:omc-teams` | 메인 = 대화·답변, 워커 tmux pane = 파일 edit. 면접 prep·논문 reading 등 흐름 끊기 싫을 때. 운영 상세는 아래. |

### omc-teams 운영 매뉴얼

자세한 launch 명령 / 함정 4종 (leader-session-1-team, paste-bracketed Enter 흡수, sentinel self-leak, Cogitated 카운터 사각지대) / omc_monitor.sh v3.x 운영 / 검증된 우회 패턴은 ==`omc-teams-ops` skill== 본문 참조.

- 자동 trigger: `omc team`, `tmux pane 분리`, `sentinel`, `워커 launch` 키워드에서 LLM 이 invoke
- 명시 호출: `/omc-teams-ops` (skill 명)
- 정본 위치: `~/claude-settings/skills/omc-teams-ops/SKILL.md`

본 CLAUDE.md 에는 ==운영 시점에 다른 룰과 충돌하는 1-line== 만 유지:
- ==같은 leader session 안에 team 추가 불가== — 처음부터 N-worker team 으로 launch. 자세한 우회 → omc-teams-ops skill.


### Coexistence rules

- **HUD statusline**: OMC owns it. Configuration lives in `omcHud` block of `~/.claude/settings.json`. To switch presets in-session: `/oh-my-claudecode:hud minimal|focused|full`.
- **Do not** propose OMC's `team` or `autopilot` for tasks inside this `claude-settings` repo itself — meta-changes to the settings that orchestrate OMC should stay surgical and reviewed line-by-line.
- **Subagent dispatch precedence**: `superpowers:subagent-driven-development` is preferred when a written plan already exists (it enforces reviewer agents per task). OMC `/team` is preferred when no plan exists and the user wants the team to scope-then-execute.

---

## Versioned Release Workflow (preferred for non-trivial features)

Versioned package 의 non-trivial 변경 (feature / redesign / breaking refactor) 은 ad-hoc commits 대신 numbered release cycle 로:

1. **Spec** — `superpowers:brainstorming` → design doc (`<topic>-design.md`)
2. **Plan** — `superpowers:writing-plans` → TDD tasks (`<topic>-execution.md`)
3. **Execute** — `superpowers:subagent-driven-development` (fresh implementer + spec-compliance reviewer + code-quality reviewer per task)
4. **Release** — final task = version bump + `CHANGELOG.md` (Removed/Added/Changed/Verification/Notes) + README + full test suite
5. **PR** — Summary + Test plan checklist, squash merge on explicit approval

**핵심 원칙**: 4 artefact (branch / commit chain / CHANGELOG / PR description) 동기화 + fresh subagents 로 controller context 보호 + spec compliance ≠ code quality (다른 reviewer agent).

**Anti-patterns**: version bump inline / spec skip ("feels small") / controller self-implement (3+ rounds 에서 judgment 저하).

**Patch (vX.Y.Z+1)**: stage 1 skip, single-task plan (bug fix + version + CHANGELOG + PR).

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

<!-- OMC:IMPORT:START -->
@CLAUDE-omc.md
<!-- OMC:IMPORT:END -->

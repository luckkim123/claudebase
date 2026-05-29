# CLAUDE.md `rules/` split — decision: do NOT split

**Filed**: 2026-05-29
**Source phase**: P4 (CLAUDE.md hardening)
**Status**: DECIDED — keep `config/CLAUDE.md` as a single file.

## Question

Should `config/CLAUDE.md` (285 LOC after P4 cleanup) be split into a slim entrypoint + `config/rules/*.md` modules joined via `@include` directives?

## Decision

**No.** Keep it as one file. Revisit when the file exceeds ~600 LOC OR when sections are loaded selectively per project — neither holds today.

## Rationale

1. **Claude Code loads CLAUDE.md whole.** There is no per-section selective loading. A split saves zero tokens at runtime; the entire content reaches the model either way (one file or N `@include`d files).

2. **Edit-locality is the only real win, and 285 LOC is below the threshold.** The argument *"split helps when editing — separate concerns map to separate PRs"* is real but starts paying off above ~600 LOC where one section's diff drowns adjacent sections. At 285 LOC every diff is already scannable.

3. **The file is already modular at the section level.** Behavioral Principles → Operational Limits → Workflow → OMC Orchestration → Versioned Release Workflow → Environment Variables → Tradeoff Note. Each section is a self-contained block. Splitting into files would add path lookup overhead without changing the mental model.

4. **`@include` resolution risk is non-trivial.** Each new `@<file>.md` directive is a load-time dependency. A typo or missing file fails silently — exactly the bug pattern P4 just fixed (the dead `@CLAUDE-omc.md` import that resolved to nothing). Adding 5 such imports multiplies that risk.

5. **Cross-file context cost is real.** A reader (human or model) navigating split rules pays the cost of jumping files to assemble the picture. The single-file form keeps everything visible in one scroll.

## When to revisit

- File exceeds **600 LOC** (2× current size) AND a single PR's diff regularly touches only one section.
- Claude Code adds **per-section selective loading** (would change the runtime token math).
- A genuine **multi-tenancy need** emerges (different projects loading different rule subsets) — currently every CLAUDE.md instance loads the same global rules.

## What P4 changed instead

- Removed dead `@CLAUDE-omc.md` import block (file never existed; resolved silently to nothing).
- Fixed stale `claude/CLAUDE.md` path reference (correct path is `config/CLAUDE.md` post-P3 G3 directory restructure).
- Updated repo URL `claude-settings` → `claudebase` (GitHub rename was completed in S5).

Net change: 289 → 285 LOC, zero behavioral change, broken silent dependency removed.

## What P4 explicitly did NOT touch

- **L234 prose path** (`~/claude-settings/runtime/skills/omc-teams-ops/SKILL.md`): per `docs/specs/P4-todo.md` L7-16, user-facing prose paths stay literal. The user-machine folder is still `~/claude-settings`; only the GitHub repo was renamed. A repo-wide sed pass happens when the folder itself is renamed, not now.
- **L242 `claudebase` reference**: already correct after P3 S5.
- **`runtime/skills/*/SKILL.md` literal paths**: same prose-stays-literal rule.

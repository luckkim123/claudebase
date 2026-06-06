# Refactor Workflow (project rule template)

> When performing a multi-phase refactoring in a new project, copy this to `<project>/.claude/rules/refactor-workflow.md` and use it. Adjust only the phase names and verification procedures to match the project's build/test commands.

## When to load
- When breaking a large refactoring or repo cleanup into phases
- When verifying, before merge, changes that could affect algorithms/behavior
- When checking, before proceeding to the next phase, whether traces of the previous phase (branch, commit, CHANGELOG) remain

## Core principles

**Every change must be traceable.** When a regression is found, you must be able to answer "which phase introduced it" within 5 minutes. The following 4 axes must always stay in sync.

1. **branch** — branch per phase, squashed to 1 commit/phase after merge
2. **commit message** — Conventional Commits + change details in the body
3. **CHANGELOG.md** — per-phase entries at the package/repo root
4. **PR description** — a summary so the above 3 can be seen at a glance on GitHub

If any one of the above is empty, traceability breaks.

## Phase split criteria

| Phase type | Criterion | Example |
|-----------|------|-----|
| `A` (cleanup) | 0% behavior impact — remove dead code/config | delete vendored headers |
| `B-N` (extract) | behavior-preserving split — extract classes/functions, split files | responsibility-separation refactoring |
| `C-N` (substitute) | behavior change — replace with a new algorithm | algorithm replacement |

**Phase A has no regression obligation.** Phase B/C require a regression PASS before merge.

## The 11-step procedure for one phase

```
1. Define phase scope          → must be summarizable in one line
2. Branch off                  → refactor/phase-<id>-<short-name>
3. (Phase A, first time) Archive tag → archive/<repo>-pre-refactor-YYYY-MM-DD at <baseline-sha>
4. (Phase B/C, first time) Regression infra → scripts/regression_*.{sh,py}
5. Code changes                → multiple small commits OK (combined via squash)
6. Confirm build PASS          → one-line summary (time / package count)
7. (Phase B/C) Measure baseline → build main HEAD → record results
8. (Phase B/C) Measure candidate → build current branch → record results
9. (Phase B/C) Compare & judge  → threshold pass + visual/numeric comparison
10. Update CHANGELOG.md        → see body format below
11. Commit + PR + squash merge → after merge, main becomes the next phase's baseline
```

## CHANGELOG entry format

```markdown
## [Unreleased] — Phase <id>: <short title> (refactor)

### Changed
- `<file>` <before> lines → <after> lines (<delta>, <one-line summary>)

### Added
- `<new file>` — <purpose>

### Removed
- `<deleted thing>` — <reason>

### Verification
- build PASS (<time>)
- baseline vs candidate <metric>: <value>

### Notes
- <item deferred to the next phase>
- <limitations, operational caveats>
```

## Commit message format

```
refactor(<scope>): phase <id> — <one-line summary>

<2-4 line body: what · why · result>

- File A: <change>
- 1 line of LOC or verification numbers
```

## Anti-patterns

- ❌ Bundling multiple phases into one PR — raises regression-tracking/rollback cost
- ❌ Writing the CHANGELOG all at once later — forgotten or inaccurate
- ❌ Deleting the regression script — cost accumulates onto the next phase
- ❌ Skipping baseline measurement and measuring only the candidate — cannot distinguish noise from regression
- ❌ Pushing directly to main — violates branch protection + linear history

## PR body template

```
## Summary
- <one-line summary>

## Changes
- <3-5 bullets>

## Verification
- [ ] build PASS
- [ ] (Phase B/C) Regression baseline vs candidate measurement done
- [ ] (Phase B/C) threshold pass + plot visual comparison
- [ ] CHANGELOG.md updated
- [ ] no impact on CLAUDE.md/README (or updated together)

## Next Phase
- <one line of the next phase's scope>
```

---
name: simplicity-review
description: 'Use when the user asks to review the current diff purely for over-engineering — unneeded abstractions, reinvented stdlib, dead flexibility, unrequested dependencies (한국어 - "이 diff 과했나 봐줘", "과잉 구현 리뷰", "삭제할 거 있나", "간소화 리뷰" / English - "review this diff for over-engineering", "what can we delete here", "is this over-engineered", "simplicity review"). Complements a correctness-focused code review — this one only hunts complexity, applies the Simplicity First ladder from the user-scope CLAUDE.md to the working diff, and never touches correctness, security, or performance.'
triggers:
  - "simplicity-review"
  - "과잉 구현 리뷰"
  - "간소화 리뷰"
  - "삭제할 거 있나"
  - "review this diff for over-engineering"
  - "what can we delete here"
  - "is this over-engineered"
---

# simplicity-review

Review the **current diff only** (not the whole repo — see `simplicity-audit` for that) against the Simplicity First ladder already defined in `~/.claude/CLAUDE.md`. Produces a delete-list, not prose.

## Schema SSOT — do NOT duplicate

The ladder itself (does this need to exist → already in the codebase → stdlib → native platform feature → installed dependency → one line → minimum code) and the `simplified:` comment convention for deliberate shortcuts are defined once, in the user-scope `~/.claude/CLAUDE.md` under `## 2. Simplicity First`. This skill applies that ladder under review pressure; it does not restate it. If the ladder text ever changes there, this skill needs no edit.

Origin note: this skill's finding format is adapted from the `ponytail-review` skill in [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) (MIT), rewritten to defer to this repo's own CLAUDE.md ladder instead of carrying a parallel copy of the same rules.

## When to invoke

- User asks to review a diff, PR, or working tree changes specifically for bloat/over-engineering.
- Do NOT invoke for correctness bugs, security holes, or performance — route those to a normal code review pass (`/code-review`).

## Procedure

1. Get the diff: `git diff` (unstaged), `git diff --staged`, or the PR diff the user names.
2. For each hunk, ask only: does this line/block survive the ladder? Skip anything that's a correctness or security concern — that's out of scope here.
3. Emit one line per finding, ranked most-cuttable first.

## Format

`<file>:L<line>: <tag> <what to cut>. <replacement>.`

Tags:

- `delete:` dead code, unused flexibility, speculative feature never asked for. Replacement: nothing.
- `stdlib:` hand-rolled logic the standard library already ships. Name the function.
- `native:` dependency or code doing what the platform/DB/CSS already does. Name the feature.
- `yagni:` abstraction with one implementation, config nobody sets, interface with a single caller.
- `shrink:` same behavior, fewer lines. Show the shorter form inline.
- `debt:` a deliberate simplification that should be marked with a `simplified:` comment (ceiling + upgrade path) but isn't yet.

## Examples

`utils/email.py:L12-38: stdlib: 27-line email validator class. re.match(r"[^@]+@[^@]+\.[^@]+", s) or better, defer real validation to the confirmation mail.`

`api/cache.ts:L4: native: hand-rolled TTL cache wrapping fetch. functools.lru_cache / a one-line Map with a timestamp check covers it.`

`repo.py:L88: yagni: AbstractRepository with one concrete implementation. Inline it until a second implementation actually exists.`

## Scoring

End with: `net: -<N> lines possible.`

Nothing to cut: `Lean already. Ship.`

## Boundaries

Scope is over-engineering and complexity only. Never flag: input validation at trust boundaries, error handling that prevents data loss, security measures, accessibility basics, hardware calibration knobs, or anything the user explicitly asked to keep — these are exactly what `~/.claude/CLAUDE.md` calls out as never-simplify-away. Lists findings only; does not apply fixes (pair with `/simplify` or the `code-simplifier` agent to act on them).

---
name: simplicity-audit
description: 'Use when the user asks to audit a whole repo (not just a diff) for over-engineering — bloat, dead flexibility, reinventable stdlib, unnecessary dependencies, across the entire codebase (한국어 - "이 저장소 전체 감사", "레포 과잉구현 감사", "뭘 지울 수 있나 전체로", "코드베이스 블로트 찾아줘" / English - "audit this codebase for over-engineering", "what can I delete from this repo", "find bloat", "simplicity audit"). Same lens as simplicity-review, scoped to the whole tree instead of a diff — one-shot report, does not apply fixes.'
triggers:
  - "simplicity-audit"
  - "레포 과잉구현 감사"
  - "코드베이스 블로트"
  - "전체 감사해줘"
  - "audit this codebase for over-engineering"
  - "what can I delete from this repo"
  - "find bloat"
---

# simplicity-audit

`simplicity-review`, applied to the whole tree instead of a diff. Same ladder, same tags, wider scope. One-shot report — never applies fixes itself.

## Schema SSOT — do NOT duplicate

Uses the same Simplicity First ladder from `~/.claude/CLAUDE.md` as `simplicity-review`. See that skill for the ladder reference; this file only adds the repo-wide hunt checklist and ranked-output format.

Origin note: adapted from `ponytail-audit` in [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) (MIT), rewritten against this repo's own CLAUDE.md ladder.

## When to invoke

- User wants a repo-wide sweep for bloat, not a diff review.
- For a single diff or PR, use `simplicity-review` instead — narrower scope, faster.

## Hunt checklist

- Dependencies that duplicate something the stdlib or the platform already ships.
- Single-implementation interfaces / abstract base classes with exactly one concrete subclass.
- Factories that only ever produce one product.
- Wrapper functions/classes that just delegate to one call with no added behavior.
- Files or modules that export exactly one thing and could be inlined at the call site.
- Dead config flags, unused feature toggles, commented-out code blocks.
- Hand-rolled reimplementations of stdlib functions (date parsing, deep clone, debounce, retry logic, etc.).
- Existing `simplified:` comments whose named ceiling has quietly become the actual bottleneck (per the CLAUDE.md "track those simplifications as debt" rule) — these are audit findings too, not just `simplicity-debt`'s job.

## Output

One line per finding, ranked biggest cut first:

`<tag> <what to cut>. <replacement>. [path]`

Tags: same as `simplicity-review` (`delete:`, `stdlib:`, `native:`, `yagni:`, `shrink:`, `debt:`).

End with: `net: -<N> lines, -<M> dependencies possible.`

Nothing to cut: `Lean already. Ship.`

## Boundaries

Scope is over-engineering and complexity only — correctness bugs, security holes, and performance are explicitly out of scope; route those to a normal review pass instead. Never flag trust-boundary validation, data-loss-prevention error handling, security measures, accessibility basics, or hardware calibration knobs for deletion. Lists findings only, applies nothing. One-shot — re-run after cleanup to check remaining debt.

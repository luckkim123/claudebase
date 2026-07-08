---
name: simplicity-debt
description: 'Use when the user asks to collect every `simplified:` comment in a codebase into a debt ledger, so deliberate shortcuts get tracked instead of rotting into "later means never" (한국어 - "simplified 코멘트 모아줘", "간소화 부채 정리", "미룬 것들 목록", "단순화 부채 장부" / English - "collect simplified debt", "what did we defer", "simplified comment ledger", "simplicity debt"). One-shot report, changes nothing.'
triggers:
  - "simplicity-debt"
  - "간소화 부채"
  - "simplified 코멘트 모아줘"
  - "미룬 것들 목록"
  - "collect simplified debt"
  - "what did we defer"
---

# simplicity-debt

The user-scope `~/.claude/CLAUDE.md` requires every deliberate simplification to carry a `simplified:` comment naming its ceiling and upgrade path ("Mark deliberate simplifications so they read as intent, not ignorance" / "Track those simplifications as debt, don't let them rot silently"). This skill collects every such marker across a codebase into one ledger, so a deferred upgrade doesn't quietly become permanent.

## Schema SSOT — do NOT duplicate

The `simplified:` comment convention itself (what it marks, why it's required, that it names a ceiling and an upgrade path) is defined once in `~/.claude/CLAUDE.md` under `## 2. Simplicity First`. This skill only harvests and formats existing markers; it does not redefine the convention.

Origin note: adapted from `ponytail-debt` in [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) (MIT), which uses an equivalent `ponytail:` comment marker — rewritten here against this repo's own `simplified:` convention.

## Scan

Grep the repo for the marker, skipping build output, `node_modules`, `.git`, and vendored dependencies:

```bash
grep -rnE '(#|//|<!--) ?simplified:' . --exclude-dir={.git,node_modules,dist,build,vendor}
```

Adjust the comment-prefix alternation if the project uses a different comment syntax (e.g. add `--` for SQL, `%` for LaTeX).

Each hit is one ledger row. Requiring the `simplified:` prefix (not just any mention of the word) keeps prose that merely discusses the convention out of the ledger.

## Output

One row per marker, grouped by file:

`<file>:<line>: <what was simplified>. ceiling: <the limit named>. upgrade: <the trigger to revisit>.`

Pull the ceiling and upgrade trigger straight from the comment text (per CLAUDE.md, every `simplified:` comment should name both). If the user wants an owner per row, add `git blame -L<line>,<line> <file>`.

Flag rot risk: any `simplified:` comment that names no ceiling or no upgrade trigger gets a `no-trigger` tag — per CLAUDE.md, "a simplification that's still right stays; one whose assumption no longer holds is debt come due," and markers with no named trigger are the ones nobody will notice have come due.

End with: `<N> markers, <M> with no trigger.`

Nothing found: `No simplified: debt. Clean ledger.`

## Boundaries

Reads and reports only, changes nothing. To persist the ledger, ask the user first, then write it to a file (e.g. `SIMPLICITY-DEBT.md`) — don't write unprompted. One-shot report.

---
name: using-omc
description: Use at the start of every multi-step request to decide the execution lane (handle directly / superpowers / OMC) and announce the verdict. Establishes when to reach for OMC orchestration (ultrawork, team, autopilot, ralph) vs lighter paths. Triggers on orchestration, parallel work, "do it autonomously", multi-file refactors, and any 3+-step request.
---

# Using OMC — Routing Brain

OMC ships ~40 skills + 19 agents (full catalog auto-loaded separately as "OMC Skill
Catalog"). This skill is the *routing rule* that decides WHEN to reach for them.

## The Rule (enforced)

For ANY request spanning 3+ actions or multiple files, BEFORE starting:
1. Run the discipline-vs-throughput judgment (below).
2. **Announce the verdict in one line** — even when it's "handle directly".
   Format: "→ <lane>로 갑니다: <one-clause reason>". This makes the routing auditable.

Trivial single-step work (typo, one-liner, single obvious edit, pure question)
proceeds silently — no announce, no orchestration.

## Discipline vs Throughput

- **Direction/scope unclear** → diverge first: `brainstorming` (decision-heavy) or
  `oh-my-claudecode:deep-interview` (Socratic). Re-enter with a clear spec.
- **Discipline governs** (wrong = expensive; review/TDD gates govern quality;
  non-trivial code; citation-bound writing) → **superpowers lane**
  (writing-plans → subagent-driven-development / TDD). Citation work stays here or
  manual — never OMC parallel mode (hallucination risk).
- **Throughput governs** (many *independent* units; 3+ files; parallelizable;
  "do it all / until done / don't ask each step") → **OMC lane**:
  - `ultrawork` — bounded parallel edits (e.g. rename X across 20 files)
  - `team` — needs inter-worker comms or review roles
  - `autopilot` — hands-off idea→working code
  - `ralph` — loop until tests/verification pass
  - `ccg` — Claude+Codex+Gemini tri-model synthesis
  (Full catalog: see the auto-loaded "OMC Skill Catalog" block.)

## Confirm-before-start gate

Even with a lane chosen, pause for ONE Y/N confirm if the work is irreversible
(delete/overwrite), outward-facing (push, PR, email), or large-scale (5+ files,
long autonomous run). Format: "20파일 rename이라 ultrawork로 갑니다. ok?"

## When OMC does NOT apply

- Trivial / single-file / pure question.
- Learning output style active (autopilot defeats the teaching goal).
- Citation-bound writing (paper/concept notes) — OMC parallel mode raises
  hallucination risk; stay manual or superpowers.
- Inside an active superpowers executing-plans flow — finish it, don't switch runners.

## Red flags (you skipped the routing judgment)

- "It's just ops, no need to announce" → multi-file ops STILL announce the verdict.
- "I'll just start" on a 3+-step task → run the judgment + announce first.
- Reaching for a heavy OMC workflow on a trivial task → handle directly instead.

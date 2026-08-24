---
name: gateguard
description: Fact-forcing gate that blocks Edit/Write/Bash (including MultiEdit) and demands concrete investigation (importers, data schemas, user instruction) before allowing the action. Measurably improves output quality by +2.25 points vs ungated agents.
metadata:
  origin: community
---
<!-- Vendored from Everything Claude Code (github.com/affaan-m/ECC), MIT,
     Copyright (c) 2026 Affaan Mustafa. See docs/third-party-skills.md.
     Local edits are listed there; do not re-sync blindly. -->

# GateGuard — Fact-Forcing Pre-Action Gate

A PreToolUse hook that forces Claude to investigate before editing. Instead of self-evaluation ("are you sure?"), it demands concrete facts. The act of investigation creates awareness that self-evaluation never did.

## When to Activate

- Working on any codebase where file edits affect multiple modules
- Projects with data files that have specific schemas or date formats
- Teams where AI-generated code must match existing patterns
- Any workflow where Claude tends to guess instead of investigating

## Core Concept

LLM self-evaluation doesn't work. Ask "did you violate any policies?" and the answer is always "no." This is verified experimentally.

But asking "list every file that imports this module" forces the LLM to run Grep and Read. The investigation itself creates context that changes the output.

**Three-stage gate:**

```
1. DENY  — block the first Edit/Write/Bash attempt
2. FORCE — tell the model exactly which facts to gather
3. ALLOW — permit retry after facts are presented
```

No competitor does all three. Most stop at deny.

## Evidence

Two independent A/B tests, identical agents, same task:

| Task | Gated | Ungated | Gap |
| --- | --- | --- | --- |
| Analytics module | 8.0/10 | 6.5/10 | +1.5 |
| Webhook validator | 10.0/10 | 7.0/10 | +3.0 |
| **Average** | **9.0** | **6.75** | **+2.25** |

Both agents produce code that runs and passes tests. The difference is design depth.

## Gate Types

### Edit / MultiEdit Gate (first edit per file)

MultiEdit is handled identically — each file in the batch is gated individually.

```
Before editing {file_path}, present these facts:

1. List ALL files that import/require this file (search the tree — Glob/Grep, or find/grep via Bash)
2. List the public functions/classes affected by this change
3. If this file reads/writes data files, show field names, structure,
   and date format (use redacted or synthetic values, not raw production data)
4. Quote the user's current instruction verbatim
```

### Write Gate (first new file creation)

```
Before creating {file_path}, present these facts:

1. Name the file(s) and line(s) that will call this new file
2. Confirm no existing file serves the same purpose (search the tree — Glob/Grep, or find/grep via Bash)
3. If this file reads/writes data files, show field names, structure,
   and date format (use redacted or synthetic values, not raw production data)
4. Quote the user's current instruction verbatim
```

### Destructive Bash Gate (every destructive command)

Triggers on: `rm -rf`, `git reset --hard`, `git push --force`, `drop table`, etc.

```
1. List all files/data this command will modify or delete
2. Write a one-line rollback procedure
3. Quote the user's current instruction verbatim
```

### Routine Bash Gate (once per session)

```
1. The current user request in one sentence
2. What this specific command verifies or produces
```

## Quick Start

### Option A: the vendored hook (claudebase) — WIRED

Four files sit beside this one: `hooks/gateguard-fact-force.js` (the hook),
`hooks/run.js` (**the runner — see below**), `hooks/smoke.test.js` (ours:
`node smoke.test.js`, 5 cases), and `hooks/gateguard-fact-force.test.js`
(upstream's, not runnable here).

**Registered in `config/settings.json` since 2026-08-10**, `PreToolUse` on
`Edit|Write|MultiEdit|Bash`:

```jsonc
"command": "# GATEGUARD_FACT_FORCE\nnode ~/claudebase/runtime/skills/gateguard/hooks/run.js"
```

**Never point that at `gateguard-fact-force.js` directly.** That file ends at
`module.exports = { run }` — no stdin read, no stdout write, no exit code — so
`node gateguard-fact-force.js < payload` exits 0 with empty stdout and the gate
silently never fires. Measured before wiring; `run.js` is the ~20-line adapter that
turns `run()`'s return value into a real hook response without importing ECC's
`run-with-flags.js` profile machinery.

`GATEGUARD_EXEMPT_GLOBS` is set in `config/settings.json` to skip harness state and
vendored trees (`.omp/**`, `.omx/**`, `.oms/**`, `.omd/**`, `.omha/**`, `.sp/**`,
`.graphify/**`, `.code-review-graph/**`, `node_modules/**`,
`.git/**`). A wiki page has no importers to list, so gating one costs a denial and
buys nothing; a source file is the opposite.

Behaviour measured on the live wiring: the first Edit/Write of a file denies and the
retry passes; a destructive `Bash` denies per distinct command; read-only git
introspection (`git status`, `git log`) is never gated; the routine-Bash gate fires
**once per session** on the first non-git command.

Kill switches, bluntest last: `OMC_SKIP_HOOKS=gateguard` (the runner exits
immediately), `ECC_GATEGUARD=off` (the hook allows everything), `DISABLE_OMC=1`.

If GateGuard blocks setup or repair work, start the session with
`ECC_GATEGUARD=off`. For hook-level control, keep using
`ECC_DISABLED_HOOKS` with the GateGuard hook ID.

In long sessions, only the first `GATEGUARD_FACT_FORCE_FULL_DENIALS`
fact-force denials (default 3) emit the full four-fact block; later
denials are condensed to a single line carrying the denial ordinal, so
near-identical blocks cannot accumulate in the context window and
amplify model repetition loops (#2142). Retrying the same file or
command after presenting facts never re-triggers the gate.

### Option B: Full package with config

```bash
pip install gateguard-ai
gateguard init
```

This adds `.gateguard.yml` for per-project configuration (custom messages, ignore paths, gate toggles).

## Anti-Patterns

- **Don't use self-evaluation instead.** "Are you sure?" always gets "yes." This is experimentally verified.
- **Don't skip the data schema check.** Both A/B test agents assumed ISO-8601 dates when real data used `%Y/%m/%d %H:%M`. Checking data structure (with redacted values) prevents this entire class of bugs.
- **Don't gate every single Bash command.** Routine bash gates once per session. Destructive bash gates every time. This balance avoids slowdown while catching real risks.

## Best Practices

- Let the gate fire naturally. Don't try to pre-answer the gate questions — the investigation itself is what improves quality.
- Customize gate messages for your domain. If your project has specific conventions, add them to the gate prompts.
- Use `.gateguard.yml` to ignore paths like `.venv/`, `node_modules/`, `.git/`.

## Related Skills

- `safety-guard` — Runtime safety checks (complementary, not overlapping)
- `code-reviewer` — Post-edit review (GateGuard is pre-edit investigation)

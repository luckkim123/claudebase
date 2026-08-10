# Third-party skills

Ten of the seventeen skills in `runtime/skills/` are vendored from **Everything
Claude Code** ([github.com/affaan-m/ECC](https://github.com/affaan-m/ECC)), MIT
licensed, Copyright (c) 2026 Affaan Mustafa, taken 2026-08-10 from a shallow clone
of `main`. The upstream `LICENSE` text applies; this file is the attribution notice
it requires — the skill-side counterpart of `docs/third-party-agents.md`.

The other seven (`changelog`, `gen-image`, `graph-init`, `invoice-organizer`,
`memory-update`, `sync-claudebase`, `video-downloader`) are ours and are not
covered here.

284 ECC skills were read, 87,639 lines, of which **17 carry any code at all**. The
filter that decided the ten was not category but "is this a binding layer we
lack" — this repo's rules are instructions, and only a hook reaches a subagent.

ECC's own `metadata.origin` field credits a third party for several of them, so
the upstream-of-the-upstream is recorded here too. **Do not re-sync any of these
blindly** — the "local edits" column is what a blind `cp` would silently revert.

Every one of the ten also gained the three-line vendoring comment directly under
its frontmatter. That is not listed per-row below.

| Skill | ECC `origin` | Local edits beyond the vendoring comment |
|:---|:---|:---|
| `gateguard` | community | Hook + test moved into `hooks/` (upstream keeps them at repo `scripts/hooks/` + `tests/hooks/`, which do not travel with the skill). Install section rewritten to the vendored path. **Not wired into `settings.json`.** |
| `delivery-gate` | ECC | `LIBS` retargeted to our auto-memory layout; `RATIONALIZE` gained four Korean patterns; block key renamed `growth-log` → `memory-facts` (see the `LOCAL EDIT` comments in `hooks/quality-gate.py`). Install + Learning-Libraries sections rewritten. **Not wired into `settings.json`.** |
| `strategic-compact` | ECC | Hook + test moved into `hooks/`. Hook-Setup section rewritten — the upstream "installed as a plugin, no setup needed" path does not exist here. **Not wired into `settings.json`.** |
| `skill-comply` | ECC | Korean `triggers:`. Body verbatim, including `scripts/`, `prompts/`, `tests/`, `fixtures/` |
| `loop-design-check` | ECC | Korean `triggers:` |
| `agent-architecture-audit` | oh-my-agent-check | Korean `triggers:` |
| `config-gc` | ECC | Korean `triggers:` |
| `rules-distill` | ECC | Korean `triggers:`. Includes `scripts/scan-skills.sh`, `scripts/scan-rules.sh` |
| `cpp-coding-standards` | ECC | none |
| `cpp-testing` | ECC | none |

The Korean `triggers:` arrays are additive and follow the house style already set
by `graph-init`. They exist because a skill whose description only matches
English never fires in a session held in Korean — the same failure this repo
keeps re-learning as "the feature exists, the routing does not."

## The hooks were not self-contained, and `node --check` said they were

Both JS hooks `require('../lib/…')` into ECC's own library tree, so vendoring the
single hook file produced a script that passes a syntax check and then dies on
load with `Cannot find module`. That is the silent-success class this repo keeps
recording: the verification step answered a different question than the one that
mattered.

The transitive closure is five files, 1,795 lines, stdlib-only (no npm), and it
splits cleanly with no overlap. Each is placed as a `lib/` sibling of the skill's
`hooks/`, which is upstream's own relative layout, so **no `require` path was
edited**:

| Skill | `lib/` contents |
|:---|:---|
| `gateguard` | `shell-substitution.js` |
| `strategic-compact` | `utils.js`, `transcript-context.js`, `agent-data-home.js`, `path-safety.js` |

Both hooks now load and run. Verified by executing them, not by checking syntax.

## Test status of the vendored code

| Test | Runs here | Result |
|:---|:---|:---|
| `strategic-compact/hooks/suggest-compact.test.js` | yes, after a one-line path fix (marked `LOCAL EDIT`) | **44 / 44 pass** |
| `gateguard/hooks/smoke.test.js` | yes — **written here, not vendored** | **5 / 5 pass** |
| `gateguard/hooks/gateguard-fact-force.test.js` | **no** | needs ECC's `scripts/hooks/run-with-flags.js` |
| `skill-comply/tests/` | needs `pytest` + `pyyaml` | not run |

The upstream gateguard test drives the hook through ECC's `run-with-flags.js`
profile runner, which pulls in `lib/hook-flags` — a second hook-enable/profile
system alongside claudebase's own. Vendoring that would import a competing flag
mechanism, so it stays out, the test keeps a header saying it cannot run, and
`smoke.test.js` covers what actually matters before wiring: first touch denies,
the deny reason names the facts, a retry is allowed (no permanent loop), a
destructive `Bash` denies, and `ECC_GATEGUARD=off` disables the gate. It isolates
`GATEGUARD_STATE_DIR` into a temp dir — without that the hook writes real state
into `~/.gateguard` and a live session's history decides the test's outcome.

## The three hooks: two wired, one left for a human

Wired 2026-08-10, after measuring rather than before:

| Hook | Event | Matcher | State |
|:---|:---|:---|:---|
| `gateguard` | `PreToolUse` | `Edit\|Write\|MultiEdit\|Bash` | **live** |
| `strategic-compact` | `PreToolUse` | `Edit\|Write` | **live** |
| `delivery-gate` | `Stop` | — | **not wired** — see below |

`config/settings.json` is the tracked base; `~/.claude/settings.json` is a build
product of `installer/scripts/render_settings.py` merging it with this machine's
`settings.local.json`. Edit the base, then render — never hand-edit the rendered
file.

**Wiring gateguard needed a runner the skill does not ship.**
`gateguard-fact-force.js` ends at `module.exports = { run }`: no stdin read, no
stdout write, no exit code. Registering it directly would have exited 0 with empty
stdout on every call — a gate that looks wired and never fires. `hooks/run.js` is
the ~20-line adapter, written here, that turns `run()`'s return into a real hook
response without importing ECC's `run-with-flags.js` profile machinery. Confirmed
live: the first Edit of a source file denies and the retry passes, a destructive
`Bash` denies, `.omp/**` is exempt, `OMC_SKIP_HOOKS=gateguard` bypasses, and the
fourth denial of a session arrives condensed to one line exactly as the skill
documents.

**`delivery-gate` stays unwired because the harness refused it.** Its command was
rejected by the permission classifier twice — after the two `PreToolUse` siblings
had already landed in the same file from the same session. The distinguishing
property is that it can `exit 2` on `Stop`, i.e. prevent a session from ending: a
self-modification that could trap the agent making it. Respecting that refusal
rather than routing around it is the point. `delivery-gate/SKILL.md` carries the
exact block to paste, and the hook gained an `OMC_SKIP_HOOKS=delivery_gate` kill
switch first, because a blocking hook without an escape is a trap.

An earlier draft of this section said "this machine already runs 18 hooks".
Measured: **17** in `config/settings.json` (19 now), plus 33 from plugin
`hooks.json` files and more declared inline in plugin manifests. The
character-counted injection ceiling and the cwd-resolution trap are both real and
both were checked here — they simply were not what stopped `delivery-gate`.

## Rejected on inspection, so nobody re-litigates them

| Skill | Why not |
|:---|:---|
| `agent-self-evaluation` | Mechanises self-approval, which our rules forbid — and which ECC's own `gateguard` calls experimentally broken. |
| `safety-guard` | The freeze mode (lock writes to one subtree) is the best idea in the catalogue and has **zero implementation files** — a prose promise, not a tool. |
| `context-budget` | Counts agents/skills/rules/MCP/CLAUDE.md and *not* hook injections, which are our largest overhead. It would reproduce the blind spot it claims to remove. |
| `repo-scan` | Not ECC code — an install guide for a third-party repo. Vendored-code detection is already `graph-init`'s ≥30% warning. |
| `python-patterns`, `python-testing`, `pytorch-patterns` | Textbook reference cards; Context7 serves the same content on demand. |
| `eval-harness`, `recursive-decision-ledger`, `agent-eval` | Weaker than `oh-my-experiments` already is (circuit check, deadline gate, launch never auto-fired, probe-novelty ledger). |

## Sibling notice, and the two agent references this repaired

Agent attribution lives in **`docs/third-party-agents.md`** — same repo, same
license, written by the pass that vendored `runtime/agents/`. This file is its
skill-side counterpart, and both are reached from a header comment inside every
vendored file. A vendored file naming neither is ours.

Two agents pointed at ECC skills the skill selection deliberately rejected, which
left them dangling. Both were one line, and both were rewritten rather than
satisfied by vendoring 751 and 348 lines of reference card:

- `python-reviewer.md` → `python-patterns`. Now states the checklist is
  self-contained and sends a reader wanting library specifics to Context7, which
  serves that content current rather than from a snapshot.
- `mle-reviewer.md` → `mle-workflow`. Now routes to the lanes that own those
  stages harder than a workflow card could — `oh-my-experiments` for run identity,
  promotion gates, and the ledger; `oh-my-project` for checksums, split leakage,
  and lineage in `.omp/manifest.json`.

The four other names that read like dangling references in `mle-reviewer.md`
(`database-reviewer`, `performance-optimizer`, `silent-failure-hunter`,
`a11y-architect`) are **not** references — they are that file's own record of which
upstream agents were deliberately dropped. Do not "fix" them.

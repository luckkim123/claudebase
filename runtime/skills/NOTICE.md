# Vendored skills — attribution and local edits

Ten of the skills in this directory came from [Everything Claude Code](https://github.com/affaan-m/ECC)
(MIT, Copyright (c) 2026 Affaan Mustafa), vendored 2026-08-10 from a shallow clone
of `main`. The rest (`changelog`, `gen-image`, `graph-init`, `invoice-organizer`,
`memory-update`, `sync-claudebase`, `video-downloader`) are ours and are not
covered by this file.

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

## The three hooks are files, not behaviour

`gateguard`, `delivery-gate`, and `strategic-compact` are all hooks, and none of
them is registered in `config/settings.json`. That is deliberate: this machine
already runs 18 hooks, the injection ceiling is counted in **characters** and
overflow truncates to a 2 KB preview with no error, and a `PreToolUse` hook that
lands in the wrong cwd binds nothing while still returning success. Wiring is a
separate, measured decision — until then each skill's `SKILL.md` documents how,
and nothing fires.

## Rejected on inspection, so nobody re-litigates them

| Skill | Why not |
|:---|:---|
| `agent-self-evaluation` | Mechanises self-approval, which our rules forbid — and which ECC's own `gateguard` calls experimentally broken. |
| `safety-guard` | The freeze mode (lock writes to one subtree) is the best idea in the catalogue and has **zero implementation files** — a prose promise, not a tool. |
| `context-budget` | Counts agents/skills/rules/MCP/CLAUDE.md and *not* hook injections, which are our largest overhead. It would reproduce the blind spot it claims to remove. |
| `repo-scan` | Not ECC code — an install guide for a third-party repo. Vendored-code detection is already `graph-init`'s ≥30% warning. |
| `python-patterns`, `python-testing`, `pytorch-patterns` | Textbook reference cards; Context7 serves the same content on demand. |
| `eval-harness`, `recursive-decision-ledger`, `agent-eval` | Weaker than `oh-my-experiments` already is (circuit check, deadline gate, launch never auto-fired, probe-novelty ledger). |

## Two dangling references left in `runtime/agents/`

Found while checking whether the language skills were worth importing; not fixed
here because that directory belongs to a different work stream:

- `python-reviewer.md` sends the reader to skill `python-patterns`, which we did
  not vendor (a PEP 8 / idiom reference card Context7 serves on demand).
- `mle-reviewer.md` sends the reader to skill `mle-workflow`, likewise absent.
- `runtime/agents/NOTICE.md` does not exist, yet `cpp-reviewer.md` and
  `mle-reviewer.md` both delegate their MIT attribution to it.

Each of the first two is one line to delete or rewrite — cheaper than vendoring
751 and 348 lines to satisfy a cross-reference.

# Changelog

All user-visible changes to this repo. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased] — 2026-08-31 — the sync that installed but never updated

Two holes in the one path that is supposed to make a second machine match this
one. Both were found the same way: omo shipped 0.19.0 on 2026-08-30 and nothing
anywhere had it.

### Changed
- **`installer/lib/plugins.sh` now passes `--update`.** `plugin_sync.py` labels
  an already-installed plugin `OK` and moves on; `UPDATE` only happens when
  `--update` is requested, and `install.sh` never requested it. So the installer
  installed missing plugins forever and updated existing ones never. Measured on
  this machine: `oh-my-orchestrator` sat at **0.16.0** while 0.17, 0.18 and
  0.19.0 had all shipped. `claude plugin update` is idempotent, so the cost of
  always asking is one CLI round trip per enabled plugin.

### Added
- **`ensure_codeagent_wrapper` in `installer/lib/orchestrator_vendors.sh`,**
  called from `install.sh` after `sync_plugins`. omo ships `codeagent-wrapper`
  as Go *source* inside the plugin, and nothing in this installer built Go — so
  the binary was the one layer no sync reached, on any machine. After omo's call
  ledger shipped, it recorded three rows in seven hours because `PATH` still
  resolved to a build from two days earlier, and omo's own pre-flight check
  (`command -v codeagent-wrapper`) passes on a stale binary.

  Three decisions worth stating:
  - **The version is injected, not derived.** The wrapper's Makefile takes it
    from `git describe`, and a plugin cache has no `.git`, so a plain build
    there reports `dev` — useless for the `--version` comparison omo's SKILL.md
    now tells a session to make. The cache directory *name* is the plugin
    version, so that is what goes into `-ldflags`.
  - **A symlink at the target is left alone.** omo's README tells a contributor
    to link `PATH` at their own build so `make install` is live with no second
    step; overwriting that would remove their dev loop with no warning.
  - **Not opt-in,** unlike the vendor probe beside it. Probing which CLIs a
    machine has is a question about the machine; building the binary the plugin
    already shipped is finishing the install. Missing Go logs and skips.

### Notes
- **A `post_install` hook could not have done this.** Hooks are keyed by
  *marketplace* (`post_install_hooks_for` → `_marketplace_of`), so one on
  `heroacademia` fires for omo, omp, omd, oms and omx alike; and `apply()`'s
  `UPDATE` branch returns before the hook loop, so a hook never runs for an
  already-installed plugin — exactly the case here. Left as-is: the same gap
  means `install_omc_shell_cli` never re-runs on update either, which is worth
  a separate look.

## [Unreleased] — 2026-08-29 — the third tool nothing pointed at

### Removed
- **`code-review-graph` (CRG), machine-wide.** The install (`ensure_code_review_graph`),
  the `graph-refresh.sh` and `graph-offer.sh` branches, the `graph-init.sh` build
  and sqlite verification, `templates/project-code-review-graphignore`, the
  `GATEGUARD_EXEMPT_GLOBS` entry, and the `.gitignore` lines in both this repo and
  `templates/project-gitignore`.
- **The grounds are not usage — they are the binding layer.** Of the three
  integration layers (MCP server / `CLAUDE.md` block / `PreToolUse` hook) only the
  hook is binding, and the only graph guard this repo ships, `graphify-guard.sh`,
  names graphify's CLI. No hook ever named CRG's. Keeping CRG meant writing that
  guard from scratch; keeping graphify meant deleting CRG. Third instance of the
  same failure in this repo — `tokensave` (6 MCP calls in 10,813 over 22 days,
  2026-08-25) and graphify's own MCP server (0 calls in 30 days, 2026-08-23).

### Changed
- `templates/project-code-review-graph.md` → **`templates/project-code-graph.md`**,
  and its install target `<project>/.claude/rules/code-review-graph.md` →
  `code-graph.md`. Rewritten for one tool.
- `runtime/skills/sync-claudebase/SKILL.md` — new **`4o. code-review-graph 잔재?`**
  (detect-then-ask, once per machine), modelled on `4m` (tokensave). `4n` was
  already taken by the om\* store census, so the next letter is `o`. Step `4l`'s
  narrative and script also dropped the CRG existence test that made the offer
  short-circuit.
- `graph_cli_intro_note` and the `README.md` graph section now describe one CLI.

### Known capability loss — three, all measured, none silently dropped
- **Nested-graph refresh.** `graph-refresh.sh` found every `.code-review-graph`
  down to depth 3 and updated each in its own directory. The graphify block reads
  only `$GRAPHIFY_OUT/graph.json` at the repo root, so a meta-repo whose real
  graphs live one level down no longer auto-refreshes. Tests
  `test_a_graph_below_the_git_root_is_refreshed` and
  `test_the_update_runs_in_the_graphs_own_directory` removed with the capability.
- **Empty-graph guard.** The sqlite node count that skipped a 0-node `graph.db`
  (created by any MCP query omitting `repo_root`) has no graphify equivalent.
  `test_an_empty_graph_is_not_refreshed` removed.
- **Symbol-level queries** — callers, importers, blast radius. graphify does not
  answer these; the fallback is `graphify query`'s neighbourhood walk, or `Grep`.

### The leftover that undid the cleanup
- **CRG's installer writes a `pre-commit` git hook, and nothing else finds it.**
  `<repo>/.git/hooks/pre-commit` calls `code-review-graph update`; `.git/hooks/` is
  untracked and invisible to every other probe. Measured on the vault the same day,
  in this order: index trashed → removal committed → **the commit's own pre-commit
  hook rebuilt the index**, 182 files / 30,969 nodes, schema migrated v1→v9, printed
  as INFO on a commit whose purpose was removing the tool. Nothing errored. `4o` now
  detects it and deletes it **first**; the reverse order silently reverses itself.

### Verification
- `pytest tests/ -q` → **419 passed**, exit 0 (7 CRG-specific tests rewritten or
  removed; none left failing).
- `bash -n` clean on all five edited shell files.
- `grep -rl code-review-graph` outside `docs/` and `installer/` → 0. The remaining
  mentions are historical: CHANGELOG entries, one protocol example, and three
  comment lines that say *why* it was removed.

### Not done, and why — the plan's own premise was wrong
- The plan bundled "untrack `.graphify/cache/`" with this removal, arguing
  graphify's storage cost (`.graphify` at 284 MB) outweighed CRG's 16 MB. Measured
  on the vault 2026-08-29: the directory is 285 MB but the **tracked** portion is
  **7.0 MB** (1,352 files, `cache/semantic/` only — `cache/ast/` and every
  derivative are already ignored). The vault `.gitignore` carries a measured
  rationale for tracking it: a cold semantic extraction costs ~2 h of LLM time and
  the cache buys back about half of that on every other machine. 7 MB for an hour
  of billing per machine is the right trade, so the untracking was **not**
  executed. Left as the user's call.

## [Unreleased] — 2026-08-29 — siblings cannot see each other

### Added
- `config/CLAUDE.md` Operational Limit (303 chars) — **one agent-state store per
  repository, at its root**; projects inside it are separated by a `project:`
  field, never by a nested second store. Rationale in
  `docs/operating-rationale.md#one-store-per-repo`.
- The rule reverses the layout rule `oh-my-orchestrator`'s `store-spec.md` §2
  carried until 2026-08-29 ("the project's folder, not the repo root", and
  "nesting is legitimate, not a mistake to clean up"). The reversal's argument is
  not aesthetic: **lookup only ascends**, so two sibling projects in one repo are
  invisible to each other by construction, and the cross-store path that did
  exist had been used **zero** times across 114 records in four sibling stores.
  Same shape as the two capabilities this repo already retired for going
  unrouted (`tokensave` 6/10,813 calls, `graphify` MCP 0 in 30 days).
- Layer boundary held deliberately: the **spec** lives in `store-spec.md` (that
  plugin owns the `.hq/` layout), and this repo carries only the machine-common
  operating rule and its rationale. The vault's anchor names and counts are
  project specifics and are not in this repo.

### Fixed
- **`tests/installer/` carried 19 tests for a feature retired the same day.**
  `27e8871` removed `patch_omc_statedir.sh` and `runtime/omc-patches/` but not
  the two test files that drive them, so every run since has been 19 failed /
  425 passed. Removed both files; the suite is 423 passed / 0 failed.
- **Hook telemetry escaped into `/private/tmp/.omc/logs/`.** Several hook tests
  hardcode `"cwd": "/tmp"`, and `hooklog.state_root` returns the nearest
  ancestor holding `.omc/` — so the first leak made every later run land in the
  same place. Measured 144 rows, all `session_id: "t"`, zero real telemetry.
  Contained with an autouse fixture in `tests/conftest.py`, sibling to the
  existing env-hermeticity one. Nothing asserted on it, so nothing failed.
- `.hq/community/posts/` — the 17 pre-schema posts now carry the §4 fields
  (`subject`/`topic`/`confidence`/`status`/`verified`); `hq lint` is clean.
  `confidence`/`status`/`verified` are `none` rather than a guessed value:
  nobody assessed these, and inventing the assessment is the failure the store
  exists to record. No `project:` field — this repo is one project, and new
  posts here do not carry one either.

## [Unreleased] — 2026-08-28 — the ask audit did not audit itself

### Fixed
- `sync-claudebase` §9.5 — the MANDATORY pre-completion ask audit listed eight
  boxes (4e, 4f, 4g, 4j, 4k, install WARNINGs, 4l, step 9) and **not 4n**, the
  om\* store census/drift step. That leaves the om\* migration guaranteed only
  by §4n's own prose and one row in the Outputs table — which is exactly the
  state §9.5 was written to declare insufficient ("A summary-table mention is
  NOT a substitute for asking. Disclosure ≠ consent"). Same shape as the
  2026-08-03 incident that created the section. Ninth box added.
- The consequence this closes is specific: §4n's rule is that a sync *reports*
  that a machine is behind and never migrates on its own. That rule only holds
  if the user is actually asked. Neither `census` nor `drift` errors, so an
  un-migrated machine can pass run after run marked "complete" while its owner
  does not know the migration exists.

## [Unreleased] — 2026-08-28 — a telemetry path that followed the `cd`

One vault had **18 stray `.omc/` directories**. None was a session root: 17 held
nothing but `logs/`, and the 18th was a two-week-old state root from a session
launched inside a nested repo. The tell was in the records themselves — a single
`session_id` appeared under three different directories, which no session-root
story explains.

### Fixed
- `runtime/hooks/hooklog.py` — `fire()` resolved its log directory as
  `os.path.join(cwd or ".", ".omc", "logs")` and `makedirs`'d it. The hook
  payload's `cwd` follows the **Bash tool's `cd`**, so every directory any
  session ever visited got a fresh `.omc/logs/`. New `state_root()` ascends to
  the nearest ancestor that already owns a `.omc/`, falling back to the nearest
  `.git` root, and **never ascends into `$HOME`** — a `~/.omc` exists on this
  machine and would have pooled every project's telemetry there.
  This is the same resolution `graphify-guard.sh` already does for its graph and
  `session-gate.py:_find_config` already does for its config; the same file's
  logging call was the one place that still trusted `cwd` raw.
- Eight inlined copies of that expression, in six hooks, now call
  `hooklog.state_root()` — `agent-routing-guard.py`, `askuserquestion_retry.py`
  (×3), `detect_malformed_toolcall.py`, `askuserquestion-guard.py`,
  `emoji_guard.py`, `sendmessage-guard.py`. They had each re-implemented the
  helper rather than importing it, so fixing the helper alone would have left
  six litterers.

- **The shell family had the same bug, and five hooks carried it.**
  `graph-refresh.sh`, `graphify-debt.sh`, `graph-offer.sh`, `hud-ensure.sh` (×2)
  and `graphify-guard.sh` (×2) all built their log path from
  `${CLAUDE_PROJECT_DIR:-$PWD}` — and `CLAUDE_PROJECT_DIR` is **not exported to
  hooks**, which two of those files already say in their own comments, so the
  expression is `$PWD` in practice. New `runtime/hooks/hooklog.sh` provides
  `hooklog_state_root`, the same three-step rule as the Python side, and all six
  call sites use it. Sourcing is fail-open: a missing helper falls back to the
  old expression rather than killing the hook.
  `graphify-debt.sh` is the sharpest case — it *already computed* an ascended
  `repo` and then logged to `$PWD` anyway. `graphify-guard.sh` looked innocent
  because it `cd`s to the graph root first, but that `cd` only happens when an
  ancestor **has** a graph; in a repo with none it logged to raw `$PWD`. That is
  why no stray directory contained `graphify_guard.jsonl` — the defect was
  latent, not absent, and the vault could never have shown it.

### Verification
- `tests/hooks/test_hooklog.py` — 6 new tests, each checked for discrimination
  by planting the failure it guards: reverting `state_root` fails the ascent and
  git-root tests; removing the `$HOME` guard fails the third. 8/8 pass on the
  patched file.
- `pytest tests/` **441 passed**. The 3 collection errors under
  `runtime/skills/skill-comply/tests/` reproduce at HEAD with these changes
  stashed — pre-existing, unrelated.
- Live fire: `hooklog.fire()` with `cwd` five levels deep inside a *nested git
  repo* wrote to the vault root's `.omc/logs/` and created no new directory. The
  shell shim was probed the same way, as a real script resolving `hooklog.sh`
  through its own `$0`, and agreed.
- `pytest tests/` **444 passed** after the shell half.
- The 18 strays' 403 log lines were merged into the vault root's `.omc/logs/`
  before the directories went to trash, so no telemetry was dropped.

## [Unreleased] — 2026-08-28 (P7) — the last migration round, and the mode the table needed

P7 moved the two live-campaign stores the gate had held back since 2026-08-25.
The mapping work turned up something the earlier rounds could not see: on an
anchor whose `.gitignore` carries `**/.hq/work/`, **the layer assignment is the
tracking decision**, and store-spec §3's tree sketch would have untracked a
plan of record.

### Added
- `runtime/bin/migrate-om-store.sh` — an `omx` case in `rules_for()`. The spec
  had no per-file rows for it; §9.3 now carries the table this implements.
- A **`path` mode**. `glob` reduces a match to its basename and `dir` moves a
  fixed prefix whole, so neither can carve one file out of `programs/<id>/`
  where the id varies. `path` matches like `glob` but appends the whole matched
  path, which is what lets `program.json` (③, parsed by `campaign.py:305`) land
  in `config/` while `PLAN.md`/`HANDOFF.md` (② — nothing reads their bodies)
  land in `community/`. Sending the bundle whole to `work/experiments/programs/`
  would have put albc's plan of record behind `**/.hq/work/` and untracked it.
- Four `omo` root-level `.md` rows — `README.md`, `HUB-night-archive.md`,
  `PHASE1-SYNTHESIS.md`, `discussion-legacy.md`. The spec's omo row names only
  `HUB.md`/`INDEX.md`; albc's board carries all four. Written as explicit `file`
  rows, not a trailing `glob|*.md|community`: shell `*` spans `/`, so that glob
  would turn the FAIL contract into a silent catch-all. Same shape of sample
  bias as `finding/015`.
- `is_skipped()` — omx's three mutex files (`.wiki-lock`, `.loop-lock`,
  `.state-lock`), same call as `.hq-lock`.

### Changed
- `is_gated()` is **kept, not deleted**, and bound to `HQ_D2_RELEASED=1`. HUB
  decision D2 was released 2026-08-28 (D20), but a machine syncing this repo has
  not necessarily seen that, and a gate that silently disappears is
  indistinguishable from one that never fired.
- selftest 46 → **64 checks**, all pass; `omx` added to both selftest loops and
  the `path` mode given its own probe and uniqueness key. pytest 20 passed.

### Fixed
- **`--store` narrowed `reverse`'s sibling awareness, producing false orphans.**
  `ANCHOR_KINDS` was derived from the *filtered* store list, so
  `reverse --store .omx` on an anchor that also holds `.orchestration` labelled
  all 111 omo-owned files ORPHAN (measured on albc). Nothing was lost — orphans
  are left in place — but a detector with 111 false positives cannot surface the
  one genuine orphan it exists to find. `--store` narrows what is *processed*,
  never what the tool knows is present. 111 → 0.
- **`.trash/` had no mapping row.** `clean.py` resolves it as
  `paths.omx_dir / ".trash"` unconditionally, so left at the legacy path the
  first `omx clean` after a `--purge` recreates `.omx/` and undoes the purge.
  Now `runtime/experiments/trash/` (⑤). Surfaced by the prose audit, not by any
  censused store — no store on this machine has ever been swept.

### Fixed
- **`census` listed a store nested inside another store as its own anchor.**
  albc's `.omx/.omx` (store-spec §9.1 row 5 — a wiki log left by a misrooted
  `--root .../.omx` call) is mapped as a *row of its parent's table*, so census
  showing it separately produced a phantom `legacy` anchor that no migration
  could ever clear, and the next round would read it as un-migrated. Any path
  containing a `/.omp/ /.oms/ /.omd/ /.omx/ /.omha/ /.orchestration/` segment is
  now excluded. In-scope roster 21 → 20.

### Fixed
- **`drift` returned 0 for a store it never checked.** With no `migrated.jsonl`,
  or none with a row for this harness, it printed "never cut over" and exited
  **0** — the same code as "clean". The campaign's acceptance criteria are
  written against `$?` read without a pipe, so a not-run check and a passed
  check were indistinguishable there. New exit code **6 — undefined**. Found by
  running `drift` on albc's `.omx` before its release had appended a ledger row;
  the same shape as `finding/013`.

### Notes
- The tool still does **not** write `migrated.jsonl`; the session does, at
  cutover time. That is deliberate — the ledger row means "this harness's code
  now writes to `.hq/`", which happens at the release, not at the copy.
- Ledger union-merge is declared **per anchor root**, not once at the repo root:
  a `.gitattributes` pattern containing a slash anchors to its own directory, so
  the vault's root line does not reach a nested anchor. `git check-attr merge`
  is the check; albc needed its own file.

## [Unreleased] — 2026-08-28 (P6) — the tool meets the anchors it was written for

P5 built `migrate-om-store.sh` and ran it against nothing. P6 ran it against
all eleven remaining stores, and the first thing it did was refuse one.

### Changed
- `runtime/bin/migrate-om-store.sh` — a fifth deviation row: an `oms` store-root
  Workflow `.js` (`section3_audit_workflow.js`, found in workspace's
  `12_Masters_Thesis/.oms`). Same class as `workflows/*.js` — hand-authored, run
  by a verb — so ③ `config/scholar/`. It keeps its root position rather than
  being tidied into `workflows/`, because this table assigns layers and
  normalising placement would make `reverse` land the file where it never was.
  A general `glob|*.js` row is not available: shell `*` spans `/`, so it would
  also swallow a work slug's own `.js` before the `slug` row ran. selftest 45→46.
- `.gitignore` — `**/.hq/community/.hq-lock` beside the existing
  `**/.orchestration/.hq-lock`. The lock follows the community root and the
  cutover moved that root; the legacy path can still take a lock until the
  fallback window closes, so both lines stay.
- `templates/project-code-review-graphignore` — `.hq/` added. CRG walks
  `git ls-files` and `community/`+`config/` are tracked, so without this the
  store indexes itself.
- Docs that asserted a *current* location under a legacy store now name the
  `.hq/` layer: `config/CLAUDE.md` (where project knowledge is written),
  `docs/operating-rationale.md`, `docs/third-party-skills.md`,
  `runtime/agents/mle-reviewer.md`, `runtime/skills/gen-image/SKILL.md`
  (the output-dir contract), `runtime/skills/gateguard/SKILL.md` (the exempt
  glob list, which `config/settings.json` already led with `.hq/**`).

### Notes
- **History and the dual-read mechanism were deliberately left alone.** The
  legacy stores are still on disk and still read until each harness ships its
  fallback-removal release, so a doc describing that resolution — or narrating
  what an earlier phase did — is current and correct. Only present-tense
  location claims were rewritten.
- `runtime/skills/skill-comply/tests/` fails collection under a repo-root
  `pytest` (`No module named 'scripts'`) — pre-existing, unrelated to this
  entry. `pytest tests` is the suite: 436 pass.

## [Unreleased] — 2026-08-28 — a migration that cannot quietly skip anything

The om* harnesses are consolidating five per-harness state stores into one
`.hq/` root per anchor (spec: `oh-my-orchestrator`
`skills/harness/references/store-spec.md`). Phases 3 and 4 moved four anchors by
hand with a throwaway script each, and every defect those phases turned up had
one shape: a check that returned "pass" while looking at the wrong thing. P4's
`finding/013` is the sharpest — a whole anchor nobody had touched passed the
test suite, the ledger and the four-state gate, because each of the three was
looking at a different axis than the work list was.

So the canonical tool is built around refusing to be quiet. A path its mapping
table does not claim is a **failure that takes the anchor with it**, not a skip:
a migration that steps over what it does not recognise is indistinguishable from
one that finished. Building the table also surfaced four rows the spec's own
per-file assignment did not carry — `omp env/`, `omd wiki/`, `omo INDEX.md` and
`.hq-lock` — each found by censusing a real store rather than by reading the
spec, which is `finding/013` happening again one layer down.

### Added

- `runtime/bin/migrate-om-store.sh` — dry-run by default; `apply` copies then
  sha256-verifies and never deletes; `reverse` merges new-store writes back to
  the legacy path (the reversible half of the rollback procedure, which nothing
  implemented before); `purge` trashes the legacy store only after a
  confirmation read from `/dev/tty`, so a piped or closed stdin refuses.
  `census` and `drift` are deliberately **different instruments**: census is the
  store-spec §9 fixed unbounded-depth `find` crossed with `git ls-files`, drift
  compares legacy mtimes against `.hq/config/migrated.jsonl`. Sharing a command
  between them would leave one detector with one blind spot; as written, each is
  blind exactly where the other sees.
  - Forward and reverse read **one** table. A second, inverse table would drift,
    and the drift would be invisible until a rollback was actually needed. The
    built-in `selftest` asserts every rule round-trips and that no destination
    prefix is reused within a store kind.
  - `.omx` and anything under `albc/` refuse by name rather than by absence —
    they are Phase 7, behind the RA-L campaign gate.
- `tests/bin/test_migrate_om_store.py` — 20 tests, all written as
  discrimination checks: plant the defect, assert failure, remove it, assert
  success. Five defects were also injected into the tool itself to confirm the
  suite is not inert (unmapped-becomes-skip, dirty-check-always-passes,
  conflict-overwrites, purge-reads-stdin, drift-always-clean); each turned the
  suite red and each removal restored exit 0.

### Changed

- `runtime/skills/sync-claudebase/SKILL.md` — new step **4n**, reporting this
  machine's anchor roster and split-brain state on every sync. The migration is
  per machine: a repo can be fully cut over in git while a machine still writes
  to the old path, and nothing errors. 4n reports; it never migrates, because
  advancing an anchor is a per-anchor user gate (store-spec §7).

### Notes

- The exclusion list is **patterns, not counts**. The plugin cache holds one
  `.omha` per installed version, so it grew 2 → 5 across the P2/P3/P4
  deployments and the census total moved 29 → 32 without a single anchor
  changing. Measured 2026-08-28 on ksm-mac: 32 hits, 12 excluded, 21 in scope,
  and the in-scope set matches the raw find in both directions.
- Dry-running the tool over the vault's `.omp` reproduces P3's hand migration
  exactly — 66 identical, 1 conflict, 1 skipped `.DS_Store`, **0 unmapped** —
  which is the strongest evidence available that the table matches what was
  actually done by hand.
- Three live CONFLICTs were found and left alone: `oh-my-scholar` and
  `oh-my-docs` `learned.md` (P4 corrected a stale banner in the new copy only)
  and `claudebase` `.omp/rules.json` (the new copy gained `.hq/**` in `ignore`).
  All three are correct divergences; the tool refuses to overwrite either side.

## [Unreleased] — 2026-08-25 — the layout rules were only ever prose

This repo has said where files belong for as long as it has existed, in three
places, and nothing has ever checked. CI runs ruff, shellcheck, pytest and an
`install.sh` idempotency smoke; none of them looks at structure, placement or
naming. `installer/githooks/pre-commit` guards `config/settings.critical.json`
keys and nothing else. The result is visible in `runtime/hooks/`: 24 scripts
split kebab 14 / snake 9 / plain 1, and `askuserquestion-guard.py` sits beside
`askuserquestion_retry.py` with no document anywhere noticing.

So `.omp/rules.json` lands — and **only** `rules.json`. `omp-init` normally
writes eight artifacts including `STRUCTURE.md` and `NAMING.md`, and those two
would be a fourth prose copy of what `README.md` L67, `docs/ARCHITECTURE.md`
L57 and `CLAUDE.md` already say. That is not a hypothetical cost: `CLAUDE.md`
item 4 was a copy of the README rule and it had gone stale, still naming
`claude/` and `skills/` after they became `config/` and `runtime/skills/`. The
copy that drifts is the one the next reader hits first.

`omp`'s hooks turned out to be built for exactly this split — `content_audit`
and `doc_garden` both skip a missing `STRUCTURE.md` rather than requiring it,
so the machine layer stands on its own. Every `role` sentence in `rules.json`
points at the existing document instead of restating it.

### Added

- `.omp/rules.json` — 16 directories, 7 naming patterns, 2 content conventions,
  measured against the tree rather than copied from a preset. **Current
  violations: 0**, checked across all 219 tracked files; a guard that calls
  today's practice a violation gets switched off.
  - `enforced: true` on exactly two: the repo root (only README, LICENSE,
    CLAUDE.md and .gitignore are tracked there, and root litter ships to every
    clone) and `runtime/skills/` (a loose file at its top level is not a skill).
    Verified against the live hook on eight paths — `ruff.toml` and
    `runtime/skills/loose.md` nudge; `README.md`, `docs/new-topic.md`,
    `runtime/hooks/new-guard.py`, `runtime/skills/my-skill/SKILL.md` and
    `tests/hooks/test_x.py` stay silent.
  - `runtime/hooks/` basenames are left deliberately unregulated. The split is
    real but a rename is not a local edit: hooks are invoked by absolute path
    from the rendered `~/.claude/settings.json`, so renaming one silently breaks
    every machine that has not re-run the installer.
- `.gitignore`: `.omp/*` with `!.omp/rules.json`. The rules describe this repo's
  layout and belong in every clone; scans, `work/` and `secretary/` are
  per-machine. Verified with `git add -n` and `git status --ignored`, not with
  `git check-ignore`, which exits 0 on a negation match and reads backwards.

### Changed

- `CLAUDE.md` "Editing rules" item 4 no longer restates the installer/README
  rule; it points at the README table as SSOT and says why the copy was dropped.

### Notes

- Requires `omp` **0.12.2**. Earlier versions accept `path: "."` in the schema
  and never match it, so the root entry would read as enforced while doing
  nothing. That bug was found while checking this file's `enforced` flags
  against the hook source, and fixed there.

## [Unreleased] — 2026-08-25 — a permission no setting can grant

Opus 5 sessions arrive carrying `Do not call the AgentTool unless the user
requested it`. That clause is harness-side — not in `settings.json`, not behind
an environment variable, not removable locally — and the only thing that
satisfies it is an actual request from the user. The only user text present in
every session on this machine is `config/CLAUDE.md`, so that file is not a
convenient place to record the permission; it is the sole place where recording
it does anything at all.

What made the gap visible was a task it quietly shaped. The 2026-08-25 harness
Area handoff ran seven tasks solo — a 115-file ownership audit, an 87-file
relocation across six repos, an eight-repo external survey, and an `oms` release
— because no per-session request had been made and the session did not think to
ask for one. Serial execution was merely slow there. The one item it could not
finish was different in kind: calibrating the new claim↔own-evidence axis needs
independent graders scoring planted over-claims, which is a fan-out by
construction. The axis shipped labelled `NOT_CALIBRATED`. The missing line did
not cost time; it cost a measurement.

### Added

- `config/CLAUDE.md` Operational Limits: **Subagent delegation is
  standing-authorized — don't ask per session.** 343 chars, the *why* factored
  out to `docs/operating-rationale.md#subagent-standing-permission` per this
  file's own lean rule.
- `docs/operating-rationale.md#subagent-standing-permission` — why the clause
  cannot be disabled by configuration, what the permission does **not** license
  (`<model_routing>` still binds every fan-out; a session-model fleet is still
  the failure it always was; an authoring agent still cannot approve itself),
  and the measurement above.

## [Unreleased] — 2026-08-25 — an index nothing routed to

`tokensave` is gone. Not because it was wrong — it was the only one of the three
graphs that indexed markdown for free, which is exactly what a prose repo needs —
but because **nothing ever asked it anything**. Measured across 250 session
transcripts on the vault that had the strongest reason to use it: **6 MCP calls
against 10,813 tool calls over 22 days**, 0.055%. `Grep` and `Glob` sat at 0 while
`Bash` took 6,398 and `Read` 2,211, because auto mode routes searching through
`grep`/`cat` and tokensave never entered that path.

The diagnosis was already written down here. `templates/project-code-review-graph.md`
says only one of the three integration layers is binding, and it is the
`PreToolUse` hook — "the only layer that survives an agent that has decided to
just grep." tokensave had all three layers and its hook was the wrong shape:
`tokensave-guard.sh pre-tool-use` returns `{"permission":"allow"}` plus index
context and **never asks for a call**, while the visible nudge on the same
`Bash` matcher (`graphify-guard.sh`) names graphify's CLI. The routing table said
tokensave; the enforcement said graphify; the transcripts followed the
enforcement. This is the same shape as the 2026-08-23 graphify-MCP removal (0
calls in 30 days) with the arrow reversed.

Cost while idle, all measured on this machine: one resident `tokensave serve`
per session (~27 MB RSS, 4 live at the time of the audit), ~80 deferred tool
names injected into every prompt (~740 tokens of names alone, before the server's
instruction block), and 45 MB of SQLite index across three repos that was still
being rewritten on session start with a query count of zero.

### Removed

- **`tokensave` from every wiring layer** — `config/mcp.template.json` (the
  user-scope MCP registration), `ensure_tokensave` in `installer/lib/deps.sh` and
  its call in `installer/install.sh`, the three hooks and the
  `mcp__tokensave__*` permission in `config/settings.json`, their markers in
  `config/settings.critical.json`, `.tokensave/**` from `GATEGUARD_EXEMPT_GLOBS`,
  and `runtime/hooks/tokensave-guard.sh` itself.
- **The three routing rows it owned** in `templates/project-code-review-graph.md`
  ("find the note that discusses X", "the body of a symbol by name", "code health
  metrics"). They are recorded as **losses, not rewordings** — both remaining free
  passes are tree-sitter, which emits zero nodes for markdown, so in a prose repo
  the honest answer is now `grep` or graphify's paid pass. A project that wants a
  free prose index has nothing to reach for; say so rather than routing it to a
  tool that cannot see the corpus.

### Added

- **Drift check 4m in `sync-claudebase`** — detect-then-ask for tokensave
  leftovers on any machine that installed it before today. `install.sh` stops
  installing it but cannot uninstall what is already there, so the step probes
  binary / MCP registration (user *and* project scope) / `~/.claude/rules/tokensave.md`
  / `settings.local.json` / the rendered `settings.json` / index dirs / live
  processes, and asks once. Keeping it is a legitimate answer — an unregistered
  binary costs nothing.

### Notes — three traps the removal itself surfaced

- **Cleaning one settings file re-pollutes it.** `render_settings.plan` captures
  `diff_overrides(existing, expected)` from the *previous rendered file* into
  `settings.local.json`, so cleaning only the local file and re-rendering put all
  three `.tokensave` strings back. Only `hooks` is in `BASELINE_OWNED_KEYS`, which
  is why the hook entries died on the first render and the `env` glob did not.
  Edit both files, then render, then re-grep both.
- **`config/settings.critical.json` blocks the render, by design.** Removing the
  hooks without removing their markers produced a loud `CRITICAL: MISSING critical
  keys` and a restore instruction. That guard did its job — the manifest is meant
  to be edited deliberately, in the same commit.
- **`pkill -f 'tokensave serve'` does not kill the servers.** Two attempts left
  all three at unchanged `etime`; `-f` also matches the invoking shell's own
  command line. `ps -eo pid,comm | awk '$2=="tokensave"'` then `kill` worked.

Re-adding it later is fine — but wire the `PreToolUse` nudge **first**, and the
server second. That order is the whole lesson.

## [Unreleased] — 2026-08-24 — a loop that stops too early, and one that never looks back

The loop contract bounded a loop that runs too long and said nothing about one
that quits. StateM (arXiv 2608.15089) names four ways a long-horizon agent fails
even when its model can do every step — *"lose track of mutable state, fail to
reactivate lessons from earlier executions, skip known procedures, or **stop
prematurely**"* — and only the first was covered here. Worse, property 3 points
the other way on purpose: an attempt cap exists to cut a loop off, never to keep
one going.

Two loops had already solved it without the contract naming it, and the second
solved it better. `omp-garden` stops on "no new findings" and says the count is
**read from state, not judged**. `oh-my-experiments` writes `open_leads` into its
approval artifact *and* `wiki_coverage {pages, with_status}` — the denominator —
because, in its own words, *"'none open' is indistinguishable from 'nobody ever
filed one' unless the denominator travels with it."* That is measured, not
hypothetical: one workspace had **0 of 540 pages carrying any status**, so every
launch that round passed a gate that had never held anything.

### Added

- **Contract property 6, externalised completion** (`docs/loop-contract.md`) — a
  residue count read out of the state file, *and* the denominator beside it. Both
  halves, because `found: 0` alone cannot distinguish a clean tree from a sweep
  that never looked.
- **`resid` and `denom` columns** in `runtime/hooks/loop_lint.py`. Split for the
  same reason `cap`/`escal` are split: the half-failure is the common one.
- **Contract property 7, lesson reactivation** (`docs/loop-contract.md`) + a
  `lesson` column. StateM's second uncovered mode. The gap is not in this stack's
  assets — `.omp/learned.md`, the `.omp`/`.omd`/`.oms`/`.omc` wikis, omx
  `registry/findings/`, 256 auto-memory files — it is that **0 of 9 loop skills
  state a read of any of them**. The column requires a read verb, because writing
  to a knowledge store is not reactivating it: `exp-loop`'s `wiki capture-session`
  / `lint` / `gc` deliberately do not match.

### Notes — what the first run showed, and what it could not

Across the nine loops the linter tracks: `resid` scored `ok` three times and
`denom` **zero** times.

Two of the three `resid` hits are the column catching *reporting* rather than
*deciding* — `docs-revise` and `scholar-revise` matched on "Or a stop report
(… + remaining defects)", which is what they print when they give up. Only
`omp-garden`'s hit is a rule. The evidence line is what separates them, which is
this linter's whole posture.

And the all-`--` denominator column is not the finding it looks like:
`oh-my-experiments` *does* carry one, in `omx_core/loop.py`, which a grep over
skill prose cannot see. A `--` there means "not stated in the skill", never
"absent from the system" — the same asymmetry check 4 already has with Ralph's
compiled Stop hook. Both caveats are written into the contract doc rather than
left for the next reader to rediscover.

`lesson` scored `ok` **once**, and it is the third instance of that same asymmetry
— structural this time rather than incidental. `exp-loop`'s hit is its backlog
reconcile (`omx wiki list --status needs-experiment`); the *strong* version of the
property lives in `exp-design`, which queries the wiki by `--category decision` and
`--category pattern` with the reason written down. The linter never opens that
file, because `exp-design` is not itself a loop — loops reactivate lessons through
**delegated sub-skills**, so the read is absent from the loop's own text by
construction. Teaching the linter to follow delegation was rejected: the hand-off
is prose ("Delegate to `exp-design`"), so a name regex would trade a blind spot for
false positives.

### Changed — table [B]'s unguarded list stops reading as a defect list

It named `oh-my-docs` and `oh-my-project` under *"their loop's stop transition is
prose only"*, and that framing had already misled one plan into scheduling a hook
for each. Audited: **neither needs one**, and the reasons differ.

`oh-my-docs` forbids `decision: block` plugin-wide — **D6**, recorded in three
release plans, honoured by all six of its hooks — and instruments the same
transition advisorily instead: `docs_verify_emit` arms a `.verify-pending`
sentinel per build, `docs_stop_guard` surfaces the unresolved ones at Stop, and
says why in its docstring: *"deferring verify is legitimate."*

`omp-garden` is report-only and omp ships no scheduler — *"arming it is the
human's call"* — so one sweep is one invocation. There is no in-session iteration
for a Stop hook to hold open; a blocking hook would hold the **human's** turn open
to force a sweep nobody asked for.

The contrast that makes this legible: `scholar-revise` is the structural twin of
`docs-revise` and *does* carry a blocking guard, scoped to a live
`revise-<slug>.json` marker with six exemptions and a durable `stop_blocks` cap.
Same loop shape, one plugin enforces and one declines, both written down. The
warning line now says fact-not-verdict, and the contract doc carries the audit.

Also closed a stale row in the standing table: `scholar-revise` no longer keeps
round history in the conversation — `.oms/state/revise-<slug>.json` holds it.

### Verification

`416 passed` (`tests/`), exit code 0. Three tests failed first — `KNOWN_GOOD` and
the shim `BODY` fixtures assert "scores every check" and predated the new
properties, so both fixtures gained them.

No hook was added for either plugin, which is this audit's actual output: the
gap the plan expected to fill did not exist.

## [Unreleased] — 2026-08-23 — a chevron that is not an emoji, and a nudge that will not stop

Two guards were charging for the same sentence twice, in opposite ways.

`emoji_guard` blocks a Stop and asks for the whole response again — the right
trade when a real emoji is in the text, since the block is what leaves a clean
copyable answer as the last message. The problem was what counts. Its own
docstring says the scope is "deliberately narrow", then admits the entire
dingbats block U+2700-27BF, which sweeps in the monochrome check and ballot
marks and every bracket ornament. Those are width-1 text-presentation
characters; U+2714 and U+2716 carry `Emoji=Yes` but `Emoji_Presentation=No`,
and none of them breaks drag-select copy, which is the only damage the guard
exists to prevent. Over the 22 blocks in `.omc/logs/emoji_guard.jsonl`, **10
were these**. One was U+276F, the shell prompt chevron: quoting a terminal
screen cost a whole-response rewrite.

`graphify-guard` had the inverse defect. Its nudge is byte-identical on every
call and it emitted it on every matching tool call, unlatched and unbounded —
so the cost scaled with tool calls rather than turns. Measured on the obsidian
vault: 397 chars on every Read/Glob, 187 on every Bash/Grep, three identical
emissions from three identical calls. One 20-tool turn paid about 5,000 chars,
more than the omha (3,118) and omp (1,593) prompt injections combined. The
wrapper's own comment already noted the nudge fires "every turn, for as long as
a graph is present", but treated the stale path inside it as the bug.

### Fixed

- **`emoji_guard.py`** — three carve-outs inside the include ranges instead of
  one. The existing text-star gap (U+2605-2606) is joined by the text check and
  ballot marks (U+2713-2718) and the bracket ornaments (U+2768-2775). The emoji
  check U+2705, the cross U+274C, and the warning sign U+26A0 all stay caught —
  the last deliberately, because `config/CLAUDE.md` tells the model to write
  status as a word rather than a glyph.
- **`emoji_guard.py`** — the block reason now tells the rewrite to carry the
  response's leading routing/header line over. Without it, an emoji block
  produced a response missing its ROUTE line, which tripped a second Stop guard:
  **two full regenerations in one turn**, observed live in this session.
- **`graphify-guard.sh`** — one nudge per session per mode, keyed on
  `session_id` and latched *before* graphify runs so a repeat also skips the
  ~100 ms process start. `--strict` stays correct by construction: it blocks the
  first raw read of a session, which is the call that still reaches the guard.
  A payload with no `session_id` is not latched at all, so the old behaviour is
  the fail-open default; a call that produced no output never arms the latch, so
  a session that starts outside a graph still gets its first nudge after moving
  into one. Suppressed calls are still logged, with `"suppressed": true`, so
  `harness_stats`' firing rate does not report a 20x drop that never happened.

### Verification

- `pytest tests/` — **383 passed**, exit 0.
- `tests/hooks/test_emoji_guard.py` — 16 tests (3 new): the carved-out marks and
  ornaments pass, the codepoints immediately either side of each gap still
  match, and the reason carries the header-line instruction.
- `tests/hooks/test_graphify_guard.py` — 10 tests (5 new): a repeat is silent, a
  new session is nudged again, a missing `session_id` keeps the old behaviour,
  read and search latch independently, and a silent guard never arms the latch.
- Live, against the real hook: a message quoting the shell chevron plus check
  and ballot marks now passes with empty stdout, while a message carrying the
  emoji check still returns `{"decision": "block"}`. Three identical
  `graphify-guard read` calls under one `session_id` returned 484, 0, 0 bytes;
  a different `session_id` returned 484.

### Notes

- `emoji_guard`'s full-rewrite instruction was reviewed and **kept**. A localized
  correction would be cheaper, but a Stop hook fires after the message is already
  on screen, so the rewrite is what leaves a complete, copyable answer as the
  last message — which is the entire point. Narrowing what counts as an emoji
  removes the waste without giving that up.
- Four hooks that ship unwired (`askuserquestion_stats.py`, `loop_lint.py`,
  `omc-reference-emit.py`, `hooklog.py`) were re-checked as deletion candidates
  and **none is dead**: `hooklog` is imported by `session-gate.py` at five call
  sites, and the other three are documented in `README.md` as utilities and
  carry their own tests. "Not registered in `settings.json`" is not "unused".

## [Unreleased] — 2026-08-23 — a chooser that moves but will not answer

A session looked frozen. The chooser was on screen, the arrow keys moved the
selection, and Enter did nothing — so the question could be neither answered nor
cancelled, and the only way out was an interrupt that threw the whole question
away. Two separate reports blamed cross-session messages and then Orca's key
delivery. A control run in a throwaway terminal cleared both: one session, one
build, one input path, only the payload changed.

| chooser | arrows | Enter | Esc |
|:---|:---|:---|:---|
| options carry `preview` (ASCII-only text) | move | dead | dead |
| options carry no `preview` | — | selects | — |

The ASCII arm also kills the CJK-width theory the first report floated. Across
444 local transcripts, preview-bearing calls answered normally on 2.1.218 (1),
2.1.220 (2) and 2.1.222 (11) and failed on all 3 attempts under 2.1.239 — a
regression in the current build, not how previews have always behaved.

One caution for anyone re-reading that evidence: `(no option selected) notes:`
is **not** a wedge signature. It appears on healthy 2.1.218 and 2.1.222 calls
too — it is simply what the harness records when the human types a note instead
of picking an option.

### Added

- `runtime/hooks/sendmessage-guard.py` — PreToolUse on `SendMessage`. Holds back
  a cross-session send while a live Orca terminal on this host is parked on a
  chooser, because the harness delivers by *enqueueing into the receiver's input
  box*, which steals focus from the chooser. Host-scoped by necessity: the tool
  input carries only a display name and nothing maps that name to a terminal, so
  the guard asks "is any local terminal parked" rather than "is my addressee
  parked". That is the right population anyway — the wedge needs a human looking
  at a TUI. Fails open on every probe failure; `SENDMESSAGE_GUARD=off` kills it;
  `XSESSION_OK:` in the message or summary bypasses one call.
- `tests/hooks/test_sendmessage_guard.py` — 16 tests, including that the deny
  reason never quotes the footer strings it matches on (it is printed on the
  sender's own screen, and a verbatim quote would make the guard match itself).

### Changed

- `runtime/hooks/askuserquestion-guard.py` — denies an option `preview` on builds
  where the chooser cannot be answered, reading the running version from the
  session transcript's last record rather than from `PATH`. Unknown version, or
  a build below 2.1.239, passes. `ASKUSERQUESTION_PREVIEW_GUARD=off` kills it.
  The upper bound is open because no fixed release is known yet; when one is,
  bound it rather than deleting the check.
- `shell/tmux.conf` — `update-environment` now carries the `ORCA_*` handles. A
  tmux session inherits the environment the *server* started with, so every
  session created against an already-running server lost `ORCA_PANE_KEY` and
  `orca claude-teams` refused with "must be run inside an Orca terminal". Token-
  bearing `ORCA_AGENT_*` variables are deliberately excluded — spraying session
  credentials into every pane is a wider exposure, and a stale token is worse
  than none.

### Verification

- `pytest tests/ -q` → 416 passed, exit 0.
- tmux, before and after, server started with the variable stripped:
  `grep -c '^ORCA_PANE_KEY=' probe` → `0` then `1`. End-to-end inside such a
  session: `orca claude-teams --version` → `2.1.239 (Claude Code)`.
  Off Orca (all `ORCA_*` removed from the client): `new-session exit=0`, 0 set.
- The SendMessage matcher fires, checked without reaching any session — a
  throwaway terminal printed the footer text and a send addressed to a
  nonexistent name came back denied by the hook; the same call carrying
  `XSESSION_OK:` passed the guard and failed at the tool with "No agent named
  … is reachable".

### Notes

- `orca claude-teams` needs only `ORCA_PANE_KEY` to clear its guard — verified
  directly (`env -u ORCA_PANE_KEY orca claude-teams --version` refuses, with it
  set the version prints).
- A named `Agent` dispatch failing with "Could not determine current tmux
  pane/window" did **not** reproduce: a fresh `orca claude-teams` session spawned
  a named teammate and it replied. Team tmux servers are per-team sockets, so
  `%1` in a stale session can name a pane on a different server; relaunching the
  team session is the workaround.

## [Unreleased] — 2026-08-21 — a port you can see, an owner you cannot kill

`claude-mem` blocks every prompt when a stale worker of a different version squats its
port, and this skill already carried the cure — `lsof` the port, `kill` the pid. That
recipe assumes the squatter is reachable. Two containers running with `--network host`
break the assumption in a way the existing text did not cover: they share one loopback
while keeping filesystems and PID namespaces apart, so each carries its own plugin cache
and its own version, and whichever updates first meets a foreign worker it has no way to
signal.

Measured 2026-08-21 on `ksm-ubuntu`: `marinelab-isaaclab` spawned a v13.14.0 worker on
`:37700` on 08-14; `stonefish_dev` updated to v13.15.3 and then logged `Worker version
mismatch — killing stale worker` followed by `Stale worker is serving the port but the
PID file does not identify it` on every hook until the
`CLAUDE_MEM_HOOK_FAIL_LOUD_THRESHOLD` of 3 tripped. Inside that container `lsof`, `ss`,
`netstat`, and `fuser` are all absent and a `/proc` scan finds no owner for the socket —
`/proc/net/tcp` shows the port at all only because that is the shared *net* namespace
talking, not the container's own processes.

The half that makes it circular: the block fires at `UserPromptSubmit`, so
`/sync-claudebase`, the skill holding the recipe, never starts. The prompt that surfaced
this *was* `/sync-claudebase`. The same day confirmed the mechanism from the other side —
when `marinelab-isaaclab` updated to v13.15.3 it cleared its own stale worker unaided,
because that worker was its own child (same PPID) and the kill never left one PID
namespace. Same port, same tool, opposite outcome.

### Fixed
- **`runtime/skills/sync-claudebase/SKILL.md`** — the claude-mem worker block gains the
  container axis: why the `lsof`+`kill` recipe cannot run from inside a `--network host`
  container, the host-side escape (`docker top <c> | grep worker-service` → `kill`), the
  durable fix of one `CLAUDE_MEM_WORKER_PORT` per host-network environment, and a warning
  not to read the recipe's `37701` fallback as the port actually in play — the containers
  measured here carried `37700`.

### Verification
- Both containers healthy on distinct ports afterwards, same version: `:37700` →
  `13.15.3` (marinelab-isaaclab), `:37701` → `13.15.3` (stonefish_dev), each reporting
  `status: ok` from `/api/health`.

### Notes
- The port separation on `stonefish_dev` is a hand edit to that container's
  `~/.claude-mem/settings.json` and does not survive a rebuild. Making it permanent
  belongs to that container's own provisioning, not to this repo — a machine path has no
  business in a repo that ships to every machine.

## [Unreleased] — 2026-08-18 — an office file that converts, and is then thrown away by your own ignore rule

graphify cannot read a `.docx` directly. `detect()` converts each one to a markdown sidecar under
`<GRAPHIFY_OUT>/converted/` and extracts *that*, so the pinned extras decide whether those files
are in the corpus at all — and both ways of losing them are silent.

Missing `[office]` is the loud half, and it is only loud once: the file lands in
`skipped_sensitive` with a hint, then never appears again. Measured on the obsidian vault
2026-08-17 — three tracked krit `.docx` produced zero nodes while every other check passed, so the
same commit yielded two different corpora on two machines pinned differently.

The quiet half is worse, and installing the extra is what exposes it. The sidecar lands *inside*
`<GRAPHIFY_OUT>/`, which the recommended `.*` ignore rule excludes, and `detect.py:1711` drops it
with a bare `continue` — no node, and no `skipped_sensitive` entry either. So the extra makes the
warning disappear while the node count stays zero, which reads exactly like a fix. graphify
enforces gitignore's parent-exclusion rule (`detect.py:1302`), so one `!` cannot rescue the file;
the ancestors have to be re-included first.

### Fixed
- **`installer/lib/deps.sh` `ensure_graphify`** — the pin widens to `graphifyy[mcp,office]`.
- **`installer/lib/deps.sh` `_graphify_mcp_ready` → `_graphify_extras_ready`** — probes
  `import mcp, docx` instead of `import mcp`. Renaming it is the point rather than cosmetics: the
  self-heal is what reaches machines installed under the older pin, because `ensure_uv_tool` skips
  anything already present, so a widened pin whose readiness probe still passes is inert exactly
  where it is needed.
- **`templates/project-code-review-graph.md`** — documents the sidecar path, the four-line ignore
  exception that lets it through, a node-count check to verify it by (never the warning going
  away), and that `.pptx` has no conversion path at all (`OFFICE_EXTENSIONS` is `.docx`/`.xlsx`).

### Verification
Reinstalled with both extras on this machine: `import mcp` and `import docx` both succeed, and the
three `.docx` converted. With `.*` alone they still produced zero nodes and `skipped_sensitive`
went 3 → 0 — the false fix, reproduced. After the four-line exception: 3 sidecars detected, 0 files
leaked from `.graphify/cache`, `.obsidian`, or `.claude`, and 35 nodes merged into the vault graph.

### Notes
Existing machines repair themselves on the next `install.sh`; no manual step. `.pptx` stays out of
every graph regardless — that is an upstream limit, not a pin.

## [Unreleased] — 2026-08-17 — a replaced PATH drops what the launcher put there

`env.PATH` in the rendered settings replaces PATH for every Claude Code subprocess — that is the
documented behaviour, and it is why the value must be spelled out absolutely. What the README did
not say is that it also discards anything the *launcher* injected into the `claude` process, and
that the resulting failure surfaces nowhere near PATH.

Orca's "Claude agent team" launcher is the case that found it. `orca claude-teams` starts
`claude --teammate-mode auto` with `~/.orca/claude-agent-teams-bin` first on PATH — a `tmux` shim
forwarding to `orca agent-teams-tmux`, which opens teammates as native Orca panes — and sets
`TMUX=/tmp/orca-claude-agent-teams/<team-id>`, a socket path only that shim understands. The
rendered PATH then drops the shim, teammate spawning resolves `/opt/homebrew/bin/tmux`, and the real
tmux answers `error connecting to /tmp/orca-claude-agent-teams/… (No such file or directory)`.
Claude Code reports it as `Could not determine current tmux pane/window`; nothing names PATH, and
`/tmp/orca-claude-agent-teams/` does not exist to be found. Measured 2026-08-17: every Agent
dispatch in a team session failed, while calling the shim directly returned `%1`.

Prepending Orca's shim dir to PATH is not the fix — it forwards unconditionally and answers
`Missing agent team ID` outside a team session, so it would break tmux in every other session.

### Fixed
- **`runtime/bin/tmux-orca-teams.sh`** (new) — a `tmux` wrapper that execs Orca's shim when
  `ORCA_AGENT_TEAMS_TEAM_ID` is set *and* the shim is executable, and otherwise strips its own
  directory from PATH and hands over to the real tmux. Self-exclusion is what keeps a PATH that
  leads with the wrapper from recursing into it.
- **`installer/lib/deps.sh` `ensure_tmux_teams_shim`**, called from `install.sh` after
  `ensure_graph_init` — links the wrapper to `~/.local/bin/tmux`. That directory, not a new one,
  because the rendered PATH lists it **ahead** of Homebrew while a login shell lists it **behind**:
  the wrapper binds inside Claude Code and stays invisible to ordinary shells. Gated on the `orca`
  CLI, so a machine without Orca gains nothing to shadow `tmux` with.
- **`README.md`** — the PATH section now says why `~/.local/bin` has to stay in the list and ahead
  of Homebrew, with this failure as the worked example.

### Verification
Both wrapper branches exercised with the wrapper's directory first on PATH: team env present →
Orca shim → `%1`; team env stripped → real tmux → `tmux 3.6b`, no recursion. The Agent dispatch
that failed before the fix spawned successfully after it. `pytest tests/` 343 passed; the 3
failures in `test_patch_omc_statedir.py` reproduce with the change stashed and are unrelated.
`bash -n` clean on both shell files; shellcheck not installed on this machine, so it was not run.

## [Unreleased] — 2026-08-11 — a version string is not an extraction prompt

graphify buckets its semantic-extraction cache by `prompt_fingerprint()`, a sha256 over the **whole
text** of `references/extraction-spec.md`. That file is the subagent prompt, and hashing it is how
graphify notices the prompt changed and re-extracts instead of replaying stale results. Our renderer
prepended a banner to it carrying `{version}` — provenance, not instruction — so the hash moved on
every graphify upgrade whether or not the prompt had changed.

Measured on the obsidian vault, 2026-08-11. Upgrading 0.9.38 → 0.9.39 left the 252 committed cache
entries orphaned in bucket `pf33081f95084` while the run started from zero, and the corpus was
re-extracted at full LLM cost: 898 files, ~9M tokens, 37 subagent chunks. Changing only `graphify
0.9.39` to `0.9.38` in the banner and re-hashing moved the bucket from `p7814ca696b13` to
`p868ee8799dae` — one string, a whole cache.

The banner also made the file **machine**-specific, which breaks the other half of the design. The
cache is committed to git (`71b6c786`) precisely so a second machine restores it without re-paying;
but a machine on the default `GRAPHIFY_OUT=graphify-out` takes the early return in `rewrite()` and
gets the pristine file, while `.graphify` machines got a banner. Two buckets for one prompt, so the
shared cache never hit across them.

### Fixed
- **`installer/scripts/render_graphify_skill.py`** — `rewrite()` returns the text unchanged when the
  `graphify-out` replace was a no-op, so a file with nothing machine-specific in it gets no banner.
  General rule, no filename special-casing: `extraction-spec.md` carries zero `graphify-out`
  occurrences against 0.9.39 (the paths it names are substituted by the caller), so it now renders
  byte-identical to the packaged prompt and its fingerprint moves only when graphify actually changes
  the prompt. `hooks.md` is the other zero-occurrence file and loses a banner it never needed; the
  six that really are rewritten keep theirs.

### Notes
- Suite: 283 passed (was 279). The four new tests state the regression the way the cache sees it —
  two renders differing only in graphify version, or only in `GRAPHIFY_OUT`, must be byte-identical.
- Mutation-checked rather than watched to go red: reverting the guard in-process makes both equality
  assertions `False`, restoring it makes them `True`.
- Not the whole story of that vault's 9M tokens. `pf33081f95084` is **not** reproducible from the
  current body under any banner version (0.9.37/38/39/unknown tested; `BANNER` itself has never been
  edited since `87cba53`), so 0.9.39 genuinely revised the prompt body and that re-extraction was
  owed. This fix is about the upgrades where it is not.
- Re-keying an existing cache after this change is sound and cheap: `banner(0.9.39) + current body`
  reproduces `p7814ca696b13` exactly, which proves those entries were produced by the current prompt
  body, so they can be copied into the banner-free bucket rather than re-extracted.

## [Unreleased] — 2026-08-10 — a purge that leaves a graph is not a purge

`GRAPHIFY_OUT=.graphify` lives in the rendered `settings.json`, so a Claude Code session — and every
hook it launches — builds into `.graphify`. A plain shell inherits none of that and falls back to
graphify's own default, `graphify-out`. Both `graph-init` and `graph-offer.sh` looked at exactly one of
those names: whichever their own process resolved.

Measured in the `stonefish_dev` container, 2026-08-10, on the first real use of `graph-init` outside a
session. It correctly refused the workspace (0 nodes — the code lives in nested vcstool repos the outer
`git ls-files` cannot see) and printed the purge instruction. Running that purge from bash deleted
`graphify-out/` and left `.graphify/graph.json` sitting there, 176 bytes of empty graph. That is the
precise object this whole line of work exists to prevent: the PreToolUse guards go on requiring every
session to consult it, and nothing anywhere reports a problem.

### Fixed
- **`runtime/bin/graph-init.sh`** — resolves an `OUT_DIRS` list (this process's `GRAPHIFY_OUT`, then
  `.graphify`, then `graphify-out`, deduplicated) and uses it for both `--purge` and the verification
  read. Purge now clears every output directory graphify might have written here, not just the one it
  would write today.
- **`runtime/hooks/graph-offer.sh`** — the "already has a graph" check tests the same three names. It
  was re-offering projects that already had one under the other name, and since the offer fires once
  per project, that wasted question was the only one they were ever going to get.

### Notes
- Suite: 244 passed (was 243). shellcheck clean.
- `TestPurge::test_purge_clears_the_other_output_name_too` was mutation-checked, not watched to go
  green: restoring the single-name loop fails it, and the fix passes it.
- The list is ordered, not a set, so the verification reads this process's own output directory first
  when more than one exists.

## [Unreleased] — 2026-08-10 — the binding layer stops binding one directory down

The `PreToolUse` guards are documented as the only *binding* layer of the three, the one that survives
an agent that has decided to grep anyway. They bind only where they can find the graph, and that turns
out to be a question about the shell's working directory rather than about the project.

`hook-guard` resolves the graph through `Path(GRAPHIFY_OUT)` — **relative** (`paths.py:293`) — against
the hook process's cwd, and hooks run with the session's working directory. The Bash tool's cwd
persists across calls, so one `cd sub/repo && …` in any earlier command switches the guard off for the
rest of the session. Measured on a three-repo workspace with the graph at the root: an identical
`grep` nudged from `/workspace` and produced nothing from `/workspace/constrained-albc`. Nothing
errors, nothing warns — the failure mode is a guard that has silently stopped guarding, which is worse
than one that was never installed, because the workspace `CLAUDE.md` hands out `cd <repo> && …`
commands as its documented way to run things.

Neither obvious anchor works here. `CLAUDE_PROJECT_DIR` is not exported to hooks — `graph-refresh.sh`
already records that finding and routes around it — and `git rev-parse` fails in a workspace that is
not itself a repo, which is exactly the multi-repo layout that makes cwd drift likely in the first
place. So the anchor is the graph itself.

### Fixed
- **`runtime/hooks/graphify-guard.sh`** — walks up from cwd to the nearest ancestor holding
  `$GRAPHIFY_OUT/graph.json` and runs there, for both the `search` and `read` modes. The nearest graph
  wins, so a nested repo carrying its own graph still answers for itself instead of deferring to the
  workspace root. An absolute `GRAPHIFY_OUT` is already cwd-independent and is left untouched; no
  ancestor has a graph and there is no `cd`, so a machine without one behaves exactly as before.
  Verified across nine cases — root, two sub-repos, a nested `source/` two levels down, a tree with no
  graph, an absolute override, the out-of-project scope-filter suppression, and `read` mode.

### Changed
- **`templates/project-code-review-graph.md`** — the "three integration layers" section said the hook
  binds, without saying under what condition. It now carries the cwd caveat and the walk-up fix, next
  to the claim it qualifies.
## [Unreleased] — 2026-08-10 — a verb nobody can find is still no verb

`graph-init` shipped with exactly one surface that named it: the SessionStart offer, which fires once
per project and only past three gates. Every way that gate closes is a user who never learns the
command exists — a project under 20 code files, a marker already spent, a message skimmed past in a
busy session. The sharpest case is the one the script itself creates: it tells you `--purge` undoes a
bad graph, and after you purge, the marker means nothing ever tells you how to build a good one.

So the command gets a skill above it, and the division is the point. The mechanism stays a shell
script because it is entirely mechanical — copy two files, run two builds, count nodes by directory,
compare a ratio — and prose that a model re-enacts is what this whole line of work has been deleting.
The skill takes the two things a script cannot: being findable in the `/` list without a hook, and the
judgement of *which* directory to exclude when the vendored check fires.

### Added
- **`runtime/skills/graph-init/SKILL.md`** — invoke the command, do not re-implement it; a table
  mapping exit 0/1/2 to what to do; confirm before building, since a graph is per-project state the
  guards then force every later session to consult. Korean and English triggers.
- **`tests/bin/test_graph_init.py::TestSkillStaysInSync`** — binds the skill to the script. The skill
  is where exit codes get interpreted, so it rots silently when the contract moves. One check asserts
  the documented codes are the ones the script returns; the other asserts the skill does not spell out
  the procedure again, which caught a first draft that listed the build commands verbatim.

### Changed
- The CLI skip in `tests/bin/test_graph_init.py` moved from module scope to the four classes that
  shell out, so the two file-reading checks run everywhere.

### Notes
- Suite: 243 passed (was 241).
- New skill directories need no installer change — `link_skills_and_agents` globs `runtime/skills/*/`.

## [Unreleased] — 2026-08-10 — the offer that named no verb

`graph-offer.sh` told a session its project had no code graph and then had to explain, in 1,152
characters of prose, how to make one: copy the exclusion template, run two builds, query the node
distribution by directory, delete the result if it turned out to be somebody else's vendored JS. There
was no command that did any of it. Every session re-derived that prose into four shell invocations, and
a person meeting claudebase for the first time performed them by hand — which is the report that
started this: *"일일이 처음 사용하는 사용자가 그런 식으로 해야 한다고?"*

The same investigation found why the offer had never fired on the machine in question. The hook used
"is this a git repository?" as a proxy for "can this be graphed", and the proxy is false: CRG falls
back from `git ls-files` to an rglob walk (`incremental.py:761-767`) and graphify never needed git —
both verified against a plain directory, which built 24 nodes from 12 files. A container mount like
`/workspace` was therefore skipped in silence, indistinguishable from a healthy no-op.

### Added
- **`runtime/bin/graph-init.sh`** — the verb. Seeds `.graphifyignore` and `.code-review-graphignore`
  from the templates *before* extracting anything (order matters for graphify: a rule added afterwards
  refunds nothing), runs both free tree-sitter builds, then judges **where** the nodes came from —
  exit 2 and a named warning when a vendored tree holds ≥30%, because the PreToolUse guards would
  otherwise force every session to consult it. `--purge` removes both graphs and keeps the ignore
  files, which may have been hand-edited. Works in and out of git; refuses `$HOME` and `/`.
- **`installer/lib/deps.sh` `ensure_graph_init`** — links it into `~/.local/bin`, called from
  `install.sh` after the three CLI installs it drives.
- **`tests/bin/test_graph_init.py`** — 7 tests, skipped where neither CLI is installed.

### Changed
- **`runtime/hooks/graph-offer.sh`** — the message is now the verb and how to read its exit code, not
  the procedure. Non-git projects are offered, bounded by the `$HOME` / `/` refusal, a depth-4 file
  count capped at 50k paths, and a marker under `~/.claude/graph-offered/` rather than a dotfile
  written into somebody's working tree.
- **`templates/project-code-review-graph.md`** — leads with `graph-init`; the hand-run recipe stays
  below it for the cases that need one half alone.

### Fixed
- The marker directory was created *before* the code-count gate, so a project the hook decided to skip
  was left with state saying it had been considered. Caught by its own test, not by reading.
- `~/.local/bin` is not on every login PATH — measured absent from this machine's zsh. A bare
  `graph-init` would have been advice the reader could not paste, so the hook and the script both
  check and print the form that resolves.

### Notes
- Suite: 241 passed. shellcheck clean on `graph-init.sh`, `graph-offer.sh`, `deps.sh`
  (`install.sh`'s SC2034 on `ARGS_USAGE_FILE` predates this and is consumed by `lib/args.sh`).
- `install.sh` run end to end: links the verb and reaches `done.`; `graph-init` then built, warned on a
  90%-`third_party` tree, and purged correctly through the installed symlink.
- Merged with `8ee228d`, which added `templates/project-code-review-graphignore` concurrently. That
  version won on the merge — it carries the measurement this one lacked (`.*/` alone leaves a
  root-level `.vscode/` indexed, 4 nodes on a Python repo) — and gained one line noting that
  `graph-init` runs its verify snippet automatically.

## [Unreleased] — 2026-08-10 — the graphify skill is a directory, and half of it never shipped

`render_graphify_skill.py` rendered `skill.md` and stopped there. But the skill delegates its heavy
flows to a sibling `references/` — and `extraction-spec.md` in that directory *is* the Step 3 subagent
prompt, not documentation. So the semantic pass could not load its own prompt: running `/graphify` on a
real corpus warned `could not read extraction prompt ... falls back to the unversioned layout`, and the
cache could no longer attribute entries to a prompt version (#1939, the thing that keeps an upgraded
prompt from replaying stale extractions).

The cause is a layout that reads backwards. graphify 0.9.38 ships **one** `skill.md` at the package
root and **per-platform** `skills/<platform>/references/`. The obvious `skill.md.parent / "references"`
therefore names a path that does not exist — and a copy of a missing directory fails silently, which is
why nothing pointed at it.

Fixing the copy alone would have shipped the second half of the same bug: the references carry 62
`graphify-out` occurrences of their own against 0.9.38, 20 in `update.md` and 17 in `query.md`. That is
exactly the CLI-writes-here / skill-looks-there split this script exists to close, so they get the same
rewrite rather than a verbatim copy.

### Fixed
- **`installer/scripts/render_graphify_skill.py`** — `find_references()` resolves
  `skills/<platform>/references` first and keeps the flat layout as a fallback;
  `render_references()` applies the same GRAPHIFY_OUT rewrite, file by file, skipping any whose content
  already matches. It runs even when `skill.md` itself is unchanged, since a run that skipped the
  references before must still be able to fill them in.
- **`installer/lib/deps.sh`** — the `GRAPHIFY_OUT=graphify-out` branch links `skill.md` and returned;
  it now links the references beside it. That branch needs no rewrite, but it needed the files.

### Notes
- Suite: 203 passed (was 196; 7 new across `TestFindReferences` / `TestRenderReferences`).
  `tests/smoke/test_install_idempotent.sh` PASS.
- The regression test was mutation-checked, not just watched to go green: reverting `find_references`
  to the beside-`skill.md` assumption fails 4 of the 14, and restoring it passes all 14.

## [Unreleased] — 2026-08-10 — the ignore file `code-review-graph` actually reads

`templates/project-code-review-graph.md` already said the two ignore files are independent and that
"when you write one, write the sibling" — but only one of them shipped as a template. Adopting the
graph rules into three repositories on a live machine meant hand-writing the sibling three times,
and the first build proved why it matters: 194 of 1,668 nodes came from a tracked `.omx/` registry
that `.graphifyignore` had already excluded and CRG never saw.

### Added
- **`templates/project-code-review-graphignore`** — the missing sibling of `project-graphifyignore`.
  Leads with what does *not* belong in it: CRG walks `git ls-files`, so an untracked tree is already
  invisible and copying `.gitignore` into it buys nothing. What it must carry is the inverse — the
  material a repository *tracks* that is not its source, which is where every measured blow-up came
  from. Ships the hidden-directory list, the vendored-code warning, and the node-distribution query
  to check a fresh graph against.

### Changed
- **`templates/project-code-review-graph.md`** — the sibling paragraph now names the template to copy
  instead of leaving it as an instruction, and records a measurement that contradicts the obvious
  glob: `.*/` dropped a tracked `.omx/` while root-level `.vscode/` survived with 4 nodes. The
  directories have to be named.
- **`templates/README.md`** — usage line and table row for the new template.
- **`runtime/skills/sync-claudebase/SKILL.md`** — three things that cost a live run time today:
  - 4g now says that a `FileNotFoundError: 'claude'` right after 4f is npm relinking the global bin
    directory mid-`omc update`, not a broken install. Nothing is half-applied; re-run it. Also that
    `/usr/bin/claude -> bin/claude.exe` is the package's own `bin` mapping on Linux and not a fault
    worth chasing.
  - Step 9 gains the three obstacles between `cp` and commit: a target that gitignores `.claude/`
    wholesale (leave it untracked, do not `git add -f`), `git commit -- <paths>` refusing an
    untracked file without committing anything, and adopting into a pristine vendored fork via
    `.git/info/exclude` so the tracked tree stays byte-identical.

### Notes
- Suite: 196 passed. `tests/smoke/test_install_idempotent.sh` PASS.
- `templates/` is not installer-wired (only `config/`, `shell/`, `runtime/skills/`, and
  `runtime/output-styles/` are), so no `link_or_copy` line accompanies the new file.

## [Unreleased] — 2026-08-10 — graphs refresh themselves, and offer themselves once

The `PreToolUse` guards made every session consult the code graph, and nothing was keeping that
graph current or telling a graph-less repository that it could have one. A required-to-consult index
that nobody updates is worse than no index: it answers confidently with yesterday's code.

### Added
- **`runtime/hooks/graph-refresh.sh`** (`Stop` → `GRAPH_REFRESH`) — refreshes the graphs a repository
  *already has*. Opt in by existence, never by configuration: no graph directory, no work, so this
  can ship at user scope without creating anything in repositories the user merely opened. Updates
  are double-forked so a turn never waits on them (measured 0.46 s for `code-review-graph update
  --brief`, 1.0 s for `graphify update .`), and debounced to once per graph per minute.
- **`runtime/hooks/graph-offer.sh`** (`SessionStart` → `GRAPH_OFFER`) — tells the session, **once per
  repository ever**, that this repo has no graph, and hands the decision to the user via
  `AskUserQuestion`. The marker is written when the offer is *emitted*, not when it is answered, so
  ignoring the prompt is itself a durable answer and no repository nags twice. It lives in `.git/`,
  which is per-repository, never committed, and disappears with the clone — unlike a central list
  under `~/.claude/`, which goes stale the first time a repository moves.
- 13 tests (`tests/hooks/test_graph_refresh.py`, `tests/hooks/test_graph_offer.py`). Suite: 195.
- **`templates/project-graphifyignore`** — what a graph must *not* index, as a portable default for
  every machine. One rule does most of the work: `.*` excludes hidden directories and dotfiles at
  any depth, so `.claude/`, `.omp/`, `.github/`, `.mcp.json`, and `.obsidian/` never enter the
  corpus. Verified against graphify's own `detect()` on a fixture tree — it drops
  `.claude/skills/SKILL.md`, `.mcp.json`, and `.obsidian/plugin.js` while keeping `README.md` and
  `0_Project/run.py`, which is the check worth running before trusting a glob that starts with a
  dot. Images and video follow, with the measurement behind them. Per-project exclusions (an archive
  folder, a generated docs tree) stay in the project's own copy and out of the template.

### Changed
- **`runtime/hooks/graph-offer.sh`** now tells the session to copy that template *before* building,
  not after. The ordering is the substance of the change: AST re-extraction is free, but the
  semantic pass runs ~5 min per chunk serially on `claude-cli`, so a late exclusion buys back only
  the chunks that have not started — everything already extracted was paid for at full price and
  then discarded. Measured on one vault, three restarts: 648 → 775 excluded files as media, an
  archive folder, and finally every hidden path were each remembered one at a time, mid-run.
- **`templates/project-code-review-graph.md`** and **`templates/README.md`** carry the same ordering
  rule, so a project that adopts the rules card gets it without reading the hook.

### Notes
- **Creation stays a decision, and cost is not why.** The free tree-sitter builds take seconds. The
  reason is that a blindly built graph is worse than none, because the guards then *require* the
  agent to consult it — this vault produced 0 nodes from 746 tracked `.md` while 101 files of
  vendored plugin JS produced 21,425 "functions" and a 212 MB index, with no error anywhere. So the
  offer carries its own verification step: check node count and language list, confirm the nodes are
  not vendored, delete the graph if they are.
- **The prose pass is never offered or triggered from a hook.** `--max-concurrency` is forced to 1
  for the `claude-cli` backend, so extraction runs serially — measured 5.3 min/chunk over 58 chunks,
  about five hours on one vault. graphify reached the same split itself: `check-update` is described
  as cron-safe and *notifies* rather than extracting.
- **The extraction guard is per-repo, and took two corrections.** The first draft skipped on
  `pgrep -f 'graphify extract'`, which would have frozen the refresh in *every* repository for the
  five hours one vault was indexing. The replacement — this repo's own `cache/` mtime, two-minute
  window — then failed live: chunks land in nested per-corpus subdirectories, so the top-level mtime
  lags, and a window narrower than the 5.3 min chunk interval sees an idle cache between chunks and
  concludes the run has ended. It now looks for any file written under `cache/` in the last ten
  minutes (`-print -quit`, so a large cache costs nothing), verified against the live extraction.
  Nothing was lost in the meantime: graphify's default refusal to shrink `graph.json` is what kept
  a 10,650-node semantic graph from being replaced by a code-only rebuild.
- **tokensave is deliberately absent.** It re-indexes itself when files change, and its CLI mutates
  `~/.claude/settings.json` even on read-only looking commands, so no automation may execute it.

## [Unreleased] — 2026-08-10 — the graphify skill is rendered, not linked

The previous entry symlinked graphify's skill and set `GRAPHIFY_OUT=.graphify` in the same change.
Those two are incompatible, and the symlink is the half that had to give.

### Fixed
- **The shipped skill hardcodes `graphify-out` in 88 places and never reads `GRAPHIFY_OUT`**, while
  the CLI reads it (`graphify/paths.py`). Symlinked as-is, the two halves of one tool disagreed: the
  skill would `mkdir -p graphify-out` — recreating the visible directory the env var had just
  removed — and look for `graphify-out/graph.json` while the CLI wrote to `.graphify/`. Worse, the
  skill's fast path ("graph already exists → skip straight to querying") keys on exactly that file,
  so with the index elsewhere **every invocation would fall through to a full rebuild** instead of
  answering from the graph that was already there.
- **`installer/scripts/render_graphify_skill.py`** now rewrites the skill at install time and
  `ensure_graphify_skill` calls it. When `GRAPHIFY_OUT` is graphify's own default the installer
  still symlinks — no rewrite is needed, and linking means an upgrade is picked up with no install
  run at all.

### Notes
- **Blanket string replace, audited before adopting it.** All 88 occurrences in graphify 0.9.38 are
  path-initial: 84 are followed by `/`, the rest by a newline or space, and each is preceded only by
  a space, backtick, quote, or `/`. A word-boundary scan found zero occurrences inside a longer
  identifier, so the replace cannot corrupt prose or a different token. Verified after rendering:
  83 `.graphify` references, one `graphify-out` left (inside the generated banner, which names both
  directories on purpose), frontmatter still on line 1, and the package's own `skill.md` unchanged
  at 78 — the render never follows the old symlink back into site-packages.
- **Upgrading graphify does not refresh the rendered copy on its own** — that is the one cost of
  rendering over linking. `install.sh` does: the render is compared byte-for-byte and rewritten
  whenever the package's `skill.md` changes, so a sync picks it up with no extra step. For the gap
  in between, the generated banner records the graphify version it was built from, making a drift
  visible (`graphify --version` to compare) rather than silent. Seven tests pin the rewrite, the
  frontmatter placement, and the default-passthrough.

## [Unreleased] — 2026-08-10 — the `/graphify` skill, and a hidden index directory

### Added
- **`ensure_graphify_skill` in `installer/lib/deps.sh`** — symlinks graphify's own `skill.md` to
  `~/.claude/skills/graphify/SKILL.md`. **Linked from the installed package, never vendored**: the
  file is 41 KB that ships with graphify and changes with it, so a copy in `runtime/skills/` would be
  a second source of truth going stale on every upgrade. Not installed via `graphify install`, which
  would also write `~/.claude/CLAUDE.md` through the symlink into this repo's `config/CLAUDE.md`.
- The skill is worth exposing because it is **not documentation — it is the build runbook**. Its 713
  lines are the chunked semantic-extraction procedure (detect, chunk, dispatch to subagents, merge,
  cluster, label, export). Querying an existing graph needs only the CLI, MCP, and hook; *building*
  one through the skill runs chunks in parallel, whereas `graphify extract --backend claude-cli` is
  forced to concurrency 1 — measured on this vault at roughly 4-5 minutes per chunk over 60 chunks.

### Changed
- **`GRAPHIFY_OUT=.graphify` in `config/settings.json`.** graphify defaults to a visible
  `graphify-out/` at the project root, alone among the three graphs — `.tokensave/` and
  `.code-review-graph/` are already hidden. The variable is read by `graphify/paths.py`, so one env
  entry moves every output path. A repo indexed before this keeps its `graphify-out/` until renamed;
  both names are gitignored so neither can be committed by accident.
- **`.gitignore` and `templates/project-gitignore`** now cover all four index directories
  (`.graphify/`, `graphify-out/`, `.code-review-graph/`, `.tokensave/`). The template had none, so a
  new project started from it would have offered to commit a multi-megabyte index. `.graphifyignore`
  stays tracked — it is configuration, not an artifact.

### Notes
- The rendered `~/.claude/settings.json` on this machine is **deliberately not re-rendered in this
  commit**: a `graphify extract` run was writing into `graphify-out/` at the time, and switching
  `GRAPHIFY_OUT` mid-build would leave the hook looking for `.graphify/` while the index lands
  elsewhere. Rename and re-render once the build is idle. Other machines are unaffected — they have
  no graphify index yet, so the new value simply applies from their first build.

## [Unreleased] — 2026-08-10 — tokensave's hooks, the half the previous entry deferred

The distribution commit installed tokensave and registered its MCP server but left its three hooks
out, on the grounds that the `Stop` one deserved its own verification. This is that change.

### Added
- **`runtime/hooks/tokensave-guard.sh`** and three blocks in `config/settings.json`:
  `PreToolUse` on `Agent|Grep|Bash` → `hook-pre-tool-use`, `UserPromptSubmit` → `hook-prompt-submit`,
  `Stop` → `hook-stop`. Declared here rather than installed by `tokensave install --agent claude`,
  which writes them into `~/.claude/settings.json` — a **rendered** file, so they would disappear on
  the next `install.sh` with no error. Same wrapper shape as `graphify-guard.sh`, for the same
  reason: resolve via PATH then `~/.local/bin`, exit 0 when the binary is absent so a machine that
  has not run `install.sh` is never blocked, `exec` otherwise to preserve stdin and the exit code.
  Verified safe outside an indexed repo — in a directory with no `.tokensave/`, `pre-tool-use`
  returns `{"permission":"allow"}` and the other two print nothing, all exit 0; an unknown mode
  argument also exits 0 rather than blocking a tool call or a turn.
- **Markers registered in `settings.critical.json`** in the same commit, including a new
  `UserPromptSubmit` entry — that event had no protected marker before, so a CLI shrink there was
  previously invisible to the guard.
- **`permissions.allow: ["mcp__tokensave__*"]` promoted to the baseline.** It had been captured into
  `settings.local.json` as a per-machine override, which means every *other* machine would prompt on
  each tokensave tool call — the opposite of the "same everywhere" the distribution work was for.
  Promoting it and clearing the local copy keeps `allow` (a list, therefore replaced rather than
  merged) owned in one place.

### Notes
- The `Stop` hook now joins four existing ones. It records the turn's token accounting and produced
  no output and exit 0 when run outside an indexed repo, which is the failure mode that would matter
  — a `Stop` hook that errors or hangs is felt on every single turn.

## [Unreleased] — 2026-08-10 — third graph (`tokensave`), and MCP registration that reaches the CLI

The routing card already claimed "all three are installed by claudebase". Two were. tokensave lived
on one machine only — installed by hand, registered by hand — so a second machine got the card's
advice without the tool it names. Closing that meant fixing the reason no MCP server could ever be
distributed: the installer wrote a file nothing reads.

### Added
- **`ensure_tokensave` in `installer/lib/deps.sh`** — [tokensave](https://github.com/aovestdipaperino/tokensave)
  (MIT), the third graph and the only one that indexes markdown headings without a paid LLM pass.
  Not a uv tool but a Rust binary, so macOS takes the tap (`brew install aovestdipaperino/tap/tokensave`)
  and Linux falls back to `cargo install tokensave`, which compiles 34 tree-sitter grammars — the log
  line says so, because an unannounced multi-minute stall reads as a hang. Neither path available →
  warn with the releases URL, never block.
- **`installer/scripts/register_mcp.py`**, called from `install.sh` after the CLI installs so a
  freshly-installed binary resolves. Reads the rendered `mcp.json` (secrets already substituted) and
  registers each entry with `claude mcp add --transport stdio --scope user`. Idempotent **by name**:
  an already-registered server is skipped entirely rather than re-added, because re-adding means
  remove+add and would silently discard a deliberate per-machine edit. Bare command names resolve to
  an absolute path (PATH, then `~/.local/bin`) since hooks and MCP servers are spawned without a
  login shell — `tokensave` resolves interactively here but would not from the CLI. Entries with an
  unresolved `${...}` are refused rather than registered with the literal placeholder, which would
  fail later at connect time instead of loudly now. Ten tests cover the decision layer.
- **`tokensave` in `config/mcp.template.json`**, alongside the `arxiv` entry recorded earlier.

### Fixed
- **`render_mcp_json` produced a file nothing consumes.** Measured 2026-08-10 (previous commit):
  Claude Code does not read `~/.claude/mcp.json` at all — user-scope servers load from
  `~/.claude.json`, and writing the entry into the rendered file under either `globalServers` or
  `mcpServers` never appeared in `claude mcp list`. The render stays as the tracked record of intent;
  `register_mcp.py` is the half that actually reaches the CLI, which is what the previous commit's
  caveat said was missing ("until the renderer is wired to feed `claude mcp add -s user`"). The
  by-hand step per machine is gone.

### Notes
- **Do not run `tokensave install --agent claude` on a claudebase machine.** It writes three hooks
  (`PreToolUse` on `Agent|Grep|Bash`, `UserPromptSubmit`, `Stop`) plus a `permissions.allow` list
  into `~/.claude/settings.json` — a **rendered** file here, so the next `install.sh` overwrites them
  and they vanish without an error. Same class as graphify's `--project` hazard but worse: graphify
  edits a symlink target and leaves visible git drift, whereas this simply disappears. If those hooks
  are wanted they belong in `config/settings.json`, next to the graphify guards.
- Those tokensave hooks are **deliberately not wired** in this commit. tokensave works fully without
  them (this machine has run months with `doctor` reporting both as not installed), and the `Stop`
  hook would join four existing ones — worth its own change with its own verification, not a rider on
  a distribution fix.
- Verified: `ensure_tokensave` and `register_mcp.py` each idempotent across two runs (`present (skip)`
  / `already registered (skip)`); a simulated fresh machine emits both `claude mcp add` commands with
  absolute paths; unresolved-placeholder and missing-binary entries warn and are skipped with exit 0;
  all three CLIs resolve; suite 175 passing.

## [Unreleased] — 2026-08-10 — the graph routing becomes binding: user-scope `PreToolUse` guards

Installing two graph CLIs and writing a routing card left the actual behaviour unchanged, because
neither layer is binding. An MCP server only adds tools to the list; a `CLAUDE.md` rule only asks.
Both are skipped under momentum — demonstrated in the session that produced this entry, where the
vault's own `ALWAYS use the code-review-graph MCP tools BEFORE Grep/Glob/Read` was read and then
ignored for an entire investigation. A `PreToolUse` hook is the only layer that intercepts the tool
call itself, and the only one that reaches **subagents**, which inherit the interception but not the
instruction.

### Added
- **`runtime/hooks/graphify-guard.sh`** + two `PreToolUse` blocks in `config/settings.json`
  (`Bash|Grep` → `hook-guard search`, `Read|Glob` → `hook-guard read`). Wired at **user scope**, so
  the routing holds on every machine and in every project rather than per-repo — the thing a
  per-project install cannot give you. Safe there because `graphify hook-guard` is a no-op wherever
  no graph exists: measured in a graph-free directory it prints nothing and exits 0, at ~51 ms per
  call. Where a graph does exist it returns `hookSpecificOutput.additionalContext` telling the agent
  to run `graphify query` before grepping. The wrapper exists so the hook degrades safely: it
  resolves `graphify` via PATH then `~/.local/bin` (uv's shim dir, which this user's shells do not
  export), exits 0 when the binary is absent — a machine that has not run `install.sh` yet must not
  have its tool calls blocked — and `exec`s otherwise, preserving both stdin and the exit code so a
  future `--strict` install can still block.
- **`GRAPHIFY_SEARCH_GUARD` / `GRAPHIFY_READ_GUARD`** added to `settings.critical.json`'s
  `hookMarkers.PreToolUse`, per the "update the manifest deliberately in the same commit" rule.

### Fixed
- **`installer/scripts/render_settings.py` silently discarded new baseline hooks.** Adding the two
  guards to `config/settings.json` did not change `~/.claude/settings.json` at all. `diff_overrides`
  compares the previous render against the expected one and captures whatever the sources do not
  explain into `settings.local.json`; the machine's previous render predated the guards, so the old
  two-block `PreToolUse` list was captured as a "per-machine override". Since `hooks` values are
  **lists**, `deep_merge` replaces rather than merges, and the captured old list then won — the new
  hooks could never reach the rendered file. Worse, it is self-sustaining: re-rendering compares
  against the freshly-broken render and re-captures, so editing `settings.local.json` alone does not
  recover (the module's own docstring flags this as a known ceiling for *deleting* an override; this
  is the same mechanism applied to an *addition*). Fix: `BASELINE_OWNED_KEYS = {"hooks"}`, excluded
  from capture. Capture is wrong for `hooks` in both directions anyway — the CLI's re-serialization
  drops hook blocks it does not recognise, and capturing *that* would freeze a shrunk list into the
  per-machine layer, permanently suppressing the very hook `settings.critical.json` exists to
  protect. Two regression tests pin both directions; suite is 165 passing.
- Recovery on an already-broken machine takes both steps: remove `hooks` from `settings.local.json`
  **and** delete `~/.claude/settings.json` before re-rendering, since capture is computed against
  the existing render. Machines pulling this commit are unaffected — the fix lands before their next
  render — but any machine that rendered between the two commits needs the manual clear.

## [Unreleased] — 2026-08-10 — second code graph: `graphify` alongside `code-review-graph`

### Added
- **`ensure_graphify` in `installer/lib/deps.sh`**, called from `install.sh` next to `ensure_code_review_graph` — an idempotent `uv tool install` of [graphify](https://github.com/Graphify-Labs/graphify). The PyPI distribution is **`graphifyy`** (two y's) while the command stays `graphify`; it also ships `graphify-mcp`, a stdio MCP server. Like CRG it installs the CLI only and builds no graph: which repos carry one is a per-repo decision. The two tools are complementary rather than redundant — CRG is an incremental query runtime over a SQLite index (point queries, blast radius, review context), graphify is a whole-corpus builder that also ingests prose, PDFs, and schemas and exports human-facing artifacts (HTML, SVG, an Obsidian vault, a wiki).
- **The `[mcp]` extra is pinned (`graphifyy[mcp]`), with a self-heal for machines that already have graphify.** The `graphify-mcp` shim is installed by the base wheel regardless, so a plain `graphifyy` passes every presence check and fails only when a client connects, with `ModuleNotFoundError: No module named 'mcp'` — installed-looking and broken. Since `ensure_uv_tool` skips anything already present, pinning the extra alone would never reach those machines, so `ensure_graphify` additionally probes `import mcp` inside graphify's uv environment and does one `uv tool install --force` when it fails. Verified here: the repair ran once, the next call printed only `graphify present (skip)`, and `graphify-mcp` then completed an MCP `initialize` handshake (`serverInfo: graphify 0.9.38`) where it had previously traced back.
- **`ensure_uv_tool BIN PKG [LABEL]`** — the shared helper both now sit on, mirroring the existing `ensure_tool` idiom one screen below it in the same file. Folding the second tool onto a helper was a smaller diff than copying the 26-line body, and it fixes a latent bug in the copied original: the post-install presence check ran even under `--dry-run`, where nothing had been installed, so a dry run printed `WARNING: … install ran but binary still missing` on any machine lacking the tool. `ensure_tool` already had the `DRY_RUN` guard; the uv path now does too.

### Changed
- **`templates/project-code-review-graph.md`** — retitled from a CRG-only trust document to cover both graphs, keeping the filename so existing `.claude/rules/` copies and their `CLAUDE.md` pointers stay valid. Adds a routing table keyed by *question* (callers/blast radius → CRG; non-code corpora, neighbourhood shape, human-facing artifacts → graphify; sub-second re-query → CRG), the wiring recipe, and the cost boundary: tree-sitter code extraction is offline and free, while prose/PDF/image extraction goes through an LLM — `--backend claude-cli` routes that through the already-paid `claude` CLI, and it is absent from `detect_backend`'s auto-detect list so it applies only when passed explicitly.
- **A new section ranks the three integration layers by how binding they are**, because only one of them is. An MCP entry (`graphify-mcp` in the project's `.mcp.json` — never `~/.claude/mcp.json`, where it would launch against a nonexistent graph in every repo) merely adds tools to the list. A `CLAUDE.md` block merely asks. The **`PreToolUse` hooks** (`Bash|Grep` → `graphify hook-guard search`, `Read|Glob` → `hook-guard read`) intercept the tool call itself, so they are the only layer that survives an agent that has decided to grep anyway — and the only one that reaches **subagents**, which inherit the hook but not the resolve. `--strict` / `GRAPHIFY_HOOK_STRICT=1` escalates the read hook to blocking the session's first raw read; the template advises against enabling it until the graph is current, since a stale graph plus a blocking hook forces the agent onto a wrong map.

### Notes
- **Always pass `--project` to `graphify install` on a claudebase machine** — recorded in `deps.sh` above `ensure_graphify` and in the template. Without it, `install.py:629` targets `~/.claude/CLAUDE.md` and writes with `Path.write_text(...)`, which follows symlinks; this installer makes that path a symlink to the repo's `config/CLAUDE.md`, so a machine-local tool install would edit tracked repo content in place and ship to every other machine on the next sync. `--project` puts all three artifacts under the project's own `.claude/` instead. Note this is a CLAUDE.md hazard only: graphify's `PreToolUse` hooks are written to `project_dir/.claude/settings.json` (`install.py:1736`) in every mode, so the rendered user-scope `~/.claude/settings.json` and its pre-commit shrink guard are never in play.
- Windows (`installer/install.ps1`) installs neither graph CLI — unchanged, and consistent with how `code-review-graph` already shipped.

## [Unreleased] — 2026-08-09 — output style: `Concise` replaces the `learning-output-style` plugin

### Added
- **`runtime/output-styles/concise.md`** — a custom output style, linked into `~/.claude/output-styles/` by new stage 4d in both installers and selected by `"outputStyle": "Concise"` in `config/settings.json`. Answer-first (the first sentence is the conclusion), headings over prose walls, `path:line` citations instead of pasted blocks, and an explicit ban on preamble, process narration, hedging filler, emoji, and box-drawing frames. A `## Lists` section picks the form by what the items *are* rather than merely rationing them — numbered when order is addressable (steps, ranked priorities, a causal chain), bulleted when it is not, a table once three or more items share comparison axes, and prose when each item only makes sense because of the one before it, since a list of connected reasoning fragments the argument. Formatting rules keep them scannable: a lead-in line, bold keyword first, one line per item, no nesting, never a list of one. It carries `keep-coding-instructions: true`: **a custom output style drops Claude Code's built-in software-engineering instructions unless that key is set**, so omitting it would have silently removed the scoping, commenting, and verification guidance along with the verbosity. The `★ Insight` block survives as a rationed element — at most one per response, appended after the answer, skipped entirely on mechanical work — so the teaching value of the old plugin is kept without letting it lead.

### Removed
- **`learning-output-style@claude-plugins-official`** — dropped from `enabledPlugins` and uninstalled at user scope. The plugin was not an output style at all: it was a `SessionStart` hook injecting ~2 KB of `additionalContext` every session that mandated `★ Insight` boxes, educational asides, and `TODO(human)` markers asking the user to write pieces of the code themselves. That injection was the actual source of response verbosity, and it lands as session context — a channel an output style in the system prompt does not override — so shipping `Concise` while leaving the plugin enabled would have left the two giving opposite instructions every turn. Its README row is gone; the upstream marketplace clone under `~/.claude/plugins/marketplaces/` is deliberately untouched (it is a git checkout the CLI restores on update, and the plugin there is inert once unenabled).

### Changed
- **`config/settings.critical.json`** — `learning-output-style@claude-plugins-official` removed from `requiredPlugins` (the pre-commit shrink guard correctly blocked the commit until the manifest matched the intent), and `outputStyle` added to `requiredScalars`. Without that pin, a CLI re-serialization dropping the key would silently revert the style to Default, which presents as "the verbosity came back" with no visible cause — exactly the failure class this manifest exists to catch.

### Notes
- `installer/scripts/plugin_sync.py` **never uninstalls** — a plugin dropped from `enabledPlugins` is reported as `DRIFT` and left alone by design. Other machines will therefore keep the plugin active after a `git pull` until `claude plugin uninstall -s user -y learning-output-style@claude-plugins-official` is run there.
- An output style is read once at session start; `outputStyle` changes take effect only after `/clear` or a new session.

## [Unreleased] — 2026-07-29 — template: `code-review-graph` trust rules

### Added
- **`templates/project-code-review-graph.md`** — a `.claude/rules/` drop-in for projects carrying a [code-review-graph](https://github.com/tirth8205/code-review-graph) index. The tool answers structural questions from a local SQLite graph instead of reading files, but it indexes `git ls-files` only, so an **untracked file returns `0 results` rather than an error** — failure is indistinguishable from "this code is unused". The template names all three causes of an empty answer (untracked / stale graph via `_graph.head_matches_build` / multi-word query hitting the FTS fallback when no embeddings are built), pins `max_depth=1` on impact radius (measured on one repo: depth 1 returned the 3 real importers, depth 2 returned 8 files with 5 false positives), requires an explicit `repo_root` wherever the graph belongs to a nested repo rather than the outer checkout, and rules the graph out entirely for config files (no nodes ⇒ blast radius always empty) and for vendored-dominated repos (`cross_community_edges: 0` across several communities means disconnected vendor trees, not clean architecture). Closes with the class of coupling no code graph can represent: message-bus topic names and QoS, runtime-resolved service names, and orchestration wiring — verify those against the running system.

## [Unreleased] — 2026-07-26 — opt-in: AI-usage fitting loop, optional plugins

Two opt-in additions, all per-machine and absent from the lab-forced
`config/settings.json` — nothing here runs in `install.sh`.

### Added
- **`docs/ai-usage-fitting.md`** — a weekly loop to cut input tokens without losing answer quality: audit always-on injection (static) vs tool/file output (dynamic), turn repeated judgments into terse gated rules, ask for narrower tool output, and review token spend **and** answer quality together. `config/CLAUDE.md` → Workflow gets a one-line pointer.
- **Optional personal plugins (opt-in)** via `sync-claudebase` step 4k (detect-then-ask, per plugin): `remotion`, `ui-ux-pro-max`, `marketing-skills`, `claude-mem`. Declared in README + `templates/settings.local.example.json`; **not** enabled lab-wide and their marketplaces are not registered in `config/settings.json` — enabled only on explicit yes at user scope. The marketplace registration lives in `~/.claude/plugins/known_marketplaces.json`, machine-local runtime state nothing here syncs, so a `"<plugin>@<marketplace>": true` line copied from a working machine's `settings.local.json` is a dead entry until `claude plugin marketplace add <ref>` runs on the new machine.

### Changed
- **`alwaysThinkingEnabled` is a baseline pin, not a per-machine pref — and the example template shipped the one value that breaks `xhigh`.** `654484a` grouped it with `model`/`effortLevel`/`tui`/`theme` as machine-local, but `0ece959` deliberately promoted it to the synced `config/settings.json`: `effortLevel: xhigh` is only legal while thinking is on, effort stays machine-local, so the enabling half must be universal. The two rules were left contradicting each other — `sync-claudebase`'s "per-machine key leak" pattern still listed `alwaysThinkingEnabled` among the keys a sweep should silently **revert out** of the baseline, which would have re-broken every `xhigh` machine as routine cleanup. Worse, `templates/settings.local.example.json` shipped `"effortLevel": "xhigh"` and `"alwaysThinkingEnabled": false` two lines apart — copy it verbatim and every request 400s. Dropped the key from both lists, removed it from the template, and recorded why in each place. Verified against CLI 2.1.220: thinking is off only via `MAX_THINKING_TOKENS<=0` or an explicit `alwaysThinkingEnabled === false` (`function R_e(){if(process.env.MAX_THINKING_TOKENS)return Fd(...)>0; if(e.alwaysThinkingEnabled===!1)return!1; return!0}`), and the settings schema says so in prose — "When false, thinking is disabled. When absent or true, thinking is enabled automatically." **Key absence is therefore never the cause of a thinking-disabled 400**, which is the wrong inference this entry exists to kill.
- **`/config`'s thinking toggle erases the key when you turn thinking ON — that disappearance is not a leak.** Enabling writes `undefined`, not `true` (`onChange(F){yi("userSettings",{alwaysThinkingEnabled: F ? void 0 : !1})}`), and `alwaysThinkingEnabled` is on the CLI's own write-back list for the rendered `~/.claude/settings.json`. So a machine pinned `true` in the baseline can legitimately show the key *missing* from the rendered file; absent means on, so nothing is broken and no sweep should chase it. Observed here: baseline carried `true`, the rendered file had lost it, and only the duplicate in `settings.local.json` made the state legible.

### Fixed
- **`omx` silently stuck two minor versions behind, with every `install.sh` reinstalling into the wrong environment.** `resolve_omx_python` probed bare `python3.1x` names, which resolve to the SYSTEM interpreter — but when omx-core lives in a dedicated venv (an image that pre-installs it to `/opt/omx-venv`), that interpreter's site-packages has no `omx_core`. The idempotency check therefore read `broken` on every run, and the reinstall it triggered targeted an environment the CLI does not use, failing on a `pip` that cannot do PEP 660 editable installs. Net effect: `omx` worked (so nothing looked broken) while reporting **0.7.5** against a plugin cache holding **0.9.0**, pinned to a source dir that no longer existed, and each sync printed a reinstall WARNING that never closed the gap. Fix: probe the installed `omx` shim's shebang interpreter first, so the idempotency check, the install, and the CLI all point at one environment. Verified on the affected machine — `broken` → `stale` → reinstall to 0.9.0 → subsequent runs skip silently.

### Notes
- A non-editable install fallback for that PEP 660 failure was written, then **removed after measuring it**: on the affected pip, `pip install <dir>` produces a bogus `UNKNOWN-0.0.0` distribution containing no `omx_core`, so the fallback would have reported success while installing nothing. The interpreter fix alone resolves the observed case; a machine with no `omx` shim yet still gets the pre-existing WARNING, which is the honest outcome.
- `install.ps1` is deliberately unchanged — it carries no omx logic at all (the CLI is not installed on Windows), so there is no counterpart to mirror under the "behaviorally equivalent" rule.
- `claude-mem` injects prior-session context at session start — it *adds* to the always-on input on every session, and overlaps the existing memory stack (`MEMORY.md`, OMC wiki, omp secretary). Flagged in the fitting doc + step 4k as the loop's first measured subject (measure net effect before keeping).
- The `headroom` token-compression proxy was added in this block and then **removed entirely** on 2026-07-29 (user decision) — CLI, plugin, proxy routing, docs, and the `sync-claudebase` install step are all gone. Nothing in this repo installs or references it any more.
- The static baseline behind the fitting doc was measured on the maintainer's machine 2026-07-25 (routing ~25 KB/turn, `MEMORY.md` 31.7 KB/session) and is illustrative, not universal.

## [Unreleased] — 2026-07-16 — opt-in: `claude` CLI fullscreen renderer (leak-free, per-machine)

New opt-in installer step + `shell/claude-mouse.sh`: wraps the `claude` command
with `CLAUDE_CODE_NO_FLICKER=1` so it launches into the fullscreen renderer —
no flicker, flat memory in long conversations, and in-app mouse scroll and
selection. Default **No** — this is the single marker-guarded exception to
claudebase's symlink-only, never-touch-rc model.

**Why an rc env var and not `/tui fullscreen`.** Upstream calls the `tui`
setting and `CLAUDE_CODE_NO_FLICKER` equivalent, but `/tui` persists `tui` into
`~/.claude/settings.json`, which claudebase symlinks to the *tracked*
`config/settings.json` — so the pref leaks into the synced repo on every use.
That is the recurring per-machine-key leak `654484a` and `8904b63` are about; an
rc env var is per-machine by construction and cannot leak.

### Added
- `shell/claude-mouse.sh` — sourceable `claude()` wrapper (`CLAUDE_CODE_NO_FLICKER=1` + `CLAUDE_CODE_SCROLL_SPEED=3`; `command claude` avoids recursion).
- `installer/lib/claude_mouse.sh` — `maybe_enable_claude_mouse`: opt-in prompt (default No, `INSTALL_CLAUDE_MOUSE=1` forces yes), appends one `# claudebase:claude-mouse`-marked `source` line to the login shell's rc (`~/.zshrc` / `~/.bashrc`). Idempotent: marker present → pure no-op.
- `installer/install.sh` — wires the step after the viewer opt-in.

### Notes
- File/marker names (`claude-mouse`) are **historical** — this began as a `CLAUDE_CODE_DISABLE_MOUSE=1` mouse-capture opt-out for drag-select (anthropics/claude-code#66957, #63054; tmux#337). Kept as-is so already-installed rc lines keep resolving; a rename would silently no-op them on other machines.
- Why `DISABLE_MOUSE` was dropped: its documented cost is losing "wheel scrolling inside Claude Code", and fullscreen's alternate screen buffer leaves tmux/terminal scrollback empty (verified: tmux `history_size=0`). Together they removed *every* way to scroll back — mouse-off hands the wheel to tmux, fullscreen leaves tmux nothing to scroll. Fullscreen's own capture is also strictly better than the native selection the opt-out protected: click-drag selects and auto-copies on mouse release (and to the tmux paste buffer inside tmux). One-off native selection: hold `Shift` (VS Code / most terminals), `Fn` (Terminal.app), `Option` (iTerm2).
- `CLAUDE_CODE_SCROLL_SPEED=3`: the VS Code integrated terminal sends exactly one wheel event per notch with no multiplier; `3` matches vim's default. Drop it on terminals that already amplify (Ghostty, iTerm2 with faster scrolling).
- Tradeoff: fullscreen gives up the terminal's native scrollback, so `Cmd+f` and tmux copy mode can't see the conversation. Use `Ctrl+o` transcript mode (then `[` writes it back to native scrollback, `/` searches). Revert by deleting the marked rc line.
- Requires tmux `set -g mouse on` for wheel scrolling (already set in `tmux/.tmux.conf`). Incompatible with iTerm2's `tmux -CC` integration mode.
- `install.ps1`: documented no-op (mirrors the existing tmux convenience-tool no-op) — unverified on native Windows Terminal, where upstream warns about stale-cell artifacts. Upgrade path noted inline.
- Fullscreen is an upstream **research preview**; behavior may change.

## [Unreleased] — 2026-06-17 — drop 5 redundant official plugins (superseded by OMC / superpowers / gh)

Removed 5 official plugins that were never used (`pluginUsage: 0`) and whose
capabilities are already covered by higher-tier tools in the stack: OMC's
agents, superpowers, and the `gh` CLI. Trimmed `enabledPlugins` 19 → 14.

### Removed
- `enabledPlugins` (config/settings.json) — dropped `feature-dev`, `pr-review-toolkit`, `code-simplifier`, `commit-commands`, `code-review` (all `@claude-plugins-official`). feature-dev/pr-review-toolkit/code-simplifier overlap OMC's `architect`/`code-reviewer`/`security-reviewer`/`code-simplifier` agents; commit-commands overlaps OMC `git-master` + `gh`; code-review (the `/code-review ultra` entry point) dropped per explicit user decision.
- `requiredPlugins` (config/settings.critical.json) — same 5 removed from the shrink-guard manifest so `settings_verify.py` stays green (verified `exit=0`).

### Notes
- Kept: `axlabs-mckinsey-pptx` (McKinsey-template decks — omd does not cover this), `oh-my-experiments@heroacademia` (may use), `context7` + both LSP plugins (auto-invoked backends).

## [Unreleased] — 2026-06-17 — viewer install: register via .vsix (was invisible) + Cursor-`code` guard

The `claude-code-viewer` extension installed by `lib/viewer.sh` was never loading
in VSCode. Two root causes, both found during a live install debug session: the
old path **copied the built tree into `~/.vscode/extensions/<id>/` but never
registered it in VSCode's `extensions.json` cache**, so the extension was on disk
yet invisible to VSCode; and the hardcoded install-dir id `luckkim123.claude-
code-viewer-0.1.0` **mismatched the repo's real `package.json` publisher**
(`local-dev`), which the manual copy path can't reconcile. Separately, the `code`
on PATH was **Cursor's CLI (v3.x), not VSCode's**, so the viewer would have
landed where VSCode can't see it.

### Changed
- `installer/lib/viewer.sh` — install path switched from "copy built tree into the extensions dir" to **package a real `.vsix` (`npx @vscode/vsce package --no-dependencies`) and install via `code --install-extension --force`**. VSCode now owns the `extensions.json` registration and the install-dir name (`<publisher>.<name>-<version>` = `local-dev.claude-code-viewer-0.1.0`), so the extension actually loads. Verified end-to-end on a clean install + idempotent second run (silent `up to date`).
- `installer/lib/viewer.sh` — `VIEWER_EXT_ID` corrected from `luckkim123.claude-code-viewer-0.1.0` to **`local-dev.claude-code-viewer`** (the repo's true `<publisher>.<name>`); install-state is now detected via `code --list-extensions` (VSCode's own truth) instead of a guessed dir.
- `installer/lib/viewer.sh` — new `_viewer_resolve_code` guard: a `code` on PATH is trusted only if `code --version` reports a **1.x VSCode** version; a Cursor `code` (3.x) is ignored and the standard `/Applications/Visual Studio Code.app` CLI is probed as fallback. Tooling check now also requires `npx`.
- `installer/lib/viewer.sh` — the built-from SHA is tracked at a **fixed sidecar** (`~/.vscode/extensions/.claude-code-viewer.installed-sha`) instead of inside the ext dir, since VSCode (not us) now names that dir.

### Added
- `runtime/skills/sync-claudebase/SKILL.md` (step 5) — **heads-up that the viewer opt-in prompt fires during install.sh**: tells the user the prompt exists (so an interactive sync isn't reflexively answered No), notes it's skipped silently non-interactively, and documents the `INSTALL_VIEWER=1` override + the real-VSCode-`code` requirement.

### Notes
- Scope check (distributed repo): viewer install is already opt-in / personal-dev-tool gated, so this only fixes a broken mechanism that ships to all machines — no per-machine quirk added. The Cursor-vs-VSCode `code` ambiguity is a general macOS hazard, not workspace-specific.

## [Unreleased] — 2026-06-12 — tool-call rationale: issue lineage + fixed AskUserQuestion variant

A user surfaced four GitHub issues (`anthropics/claude-code` #5219 / #895,
`anthropics/claude-agent-sdk-python` #113, `gsd-build/get-shit-done` #743) and
asked for an analysis, plus an update to the claudebase defenses that already
cover this. Investigation confirmed all four are variants of one root cause
already documented here (the model emitting tool-call JSON that violates the
schema), but the existing rationale was missing the authoritative paper trail:
the *oldest* report, the *official* Anthropic triage quote, the cross-tool
type-mismatch family, and — importantly — the one variant that was a real CLI
bug and has since been *fixed*, which the prior "no CLI fix" framing obscured.

### Added
- `docs/operating-rationale.md#complete-tool-payloads` — new **Issue lineage + official triage** paragraph: names the oldest open report (#895, 2025-04), quotes collaborator `ltawfik`'s explicit "model-side … CLI validation correctly catches this … self-correct on retry" verdict from #5219, notes the identical SDK cross-file (#113, closed stale), and lists the cross-tool type-mismatch family (Read #30197 / Edit #31379 / TodoWrite #30955 / Skill #30893 / AskUserQuestion gsd #743) so they're treated as one family, not separate bugs.
- `docs/operating-rationale.md#complete-tool-payloads` — new **"One variant WAS a real CLI bug and IS fixed"** paragraph: the AskUserQuestion auto-allow bug (interactive tools silently auto-allowed when listed in a skill's `allowed-tools`, returning empty answers → model guesses) was fixed in **Claude Code 2.1.69**. Gives a two-pronged triage — missing-field/wrong-type = model-side (`/compact`); empty-but-accepted = the fixed auto-allow bug (update CC).
- `docs/operating-rationale.md#no-leaked-toolcall-markup` — Triggers list gained item **(g) third-party API proxies**: multiple #895 reporters saw the failure *only* through non-official gateways; have users confirm against the first-party endpoint before chasing a model/CLI cause.

### Notes
- Docs-only change to an existing rationale file; no rules added to `config/CLAUDE.md` (the two governing rules — *Complete tool payloads*, *Don't leak tool-call markup* — and their three Stop/PreToolUse guard hooks already existed and were unchanged). This is evidence boosting, not a new defense.
- Scope check passed for a distributed repo: the tool-call emission failure is a universal model/CLI phenomenon, not a workspace-specific quirk, so it belongs in claudebase rather than a project store.
- No issue numbers already cited in the file were duplicated; all 7 newly added (#895, #5219, #113, #30197, #31379, #30955, #30893, gsd #743) were absent before.

## [Unreleased] — 2026-06-05 — sync skill: dirty-tree triage + non-owner path

A live sync run hit a gap: the working tree was dirty (`config/CLAUDE.md`, the
`~/.claude/CLAUDE.md` symlink target, had a 1-line uncommitted learning written
by another session) **and** `origin` was behind. The skill's only guidance was
pre-flight "if dirty, stop and surface to the user" — but the dirty change
turned out to be the *draft* of an incoming commit (`2e59219`, same topic, but
with code + tests), i.e. already absorbed by `origin`. The correct action was
patch-backup + discard, not stop. Worse, blanket-stopping on dirty strands a
**non-owner** (someone who received this clone but can't push `origin`): they'd
be told to "decide" on a change they should simply drop, with no documented way
to keep a *genuinely unique* change either, since they can't upstream it.

The fix is procedural — classify the dirty change before deciding, and give the
non-owner an out-of-tree path so they're never forced to choose between losing
their change and blocking sync forever.

### Added
- `runtime/skills/sync-claudebase/SKILL.md` — new **Step 1.5 (Dirty working-tree triage)** between fetch and analyze. For each dirty tracked file: read the local diff, compare it against `origin/main` (and the incoming commit subjects), then branch — **ABSORBED/superseded** → patch-backup (`git diff > /tmp/...patch`) + `git checkout --` + continue; **UNIQUE & worth keeping** → *then* the pre-flight "stop and surface" applies, split by push authority (owner: commit-then-pull-then-step-8-gate; non-owner: preserve as a patch/branch, `checkout --` to unblock `--ff-only`, forward to the owner or re-apply after pull); **UNIQUE but disposable** → confirm + discard. The recurring trigger (another session edits `config/CLAUDE.md` in place) is named explicitly so the dirty state isn't misread as this run's doing.

### Changed
- `runtime/skills/sync-claudebase/SKILL.md` — pre-flight dirty bullet reworded from a flat "stop and surface" to "dirty ≠ automatically stop → go to Step 1.5"; step-8 push gate gained a **Non-owner clones** paragraph (a denied `git push` is not "stuck" — forward the commit as a patch/PR, don't loop); two new Red-flags rows ("dirty → stop" and "discard so `--ff-only` works") each redirect to Step 1.5 classification.

### Notes
- Why this matters for distributed clones specifically: the owner can always commit→push to preserve a unique change, so for them "stop and ask" is sufficient. A non-owner cannot — which is the case the user flagged ("다른 사람은 push도 마음대로 할 수 없잖아"). Step 1.5's non-owner branch is the part that didn't exist before.
- Docs/skill-only change; no code, no tests touched. The triage procedure is the same sequence verified live in the sync run that surfaced the gap (patch-backup → `checkout --` → `pull --ff-only` succeeded).

## [Unreleased] — 2026-06-05 — opt-in `--update` for plugin sync

`installer/scripts/plugin_sync.py` only ever *installed* missing plugins; an
already-user-scope plugin returned `Action.OK` (no-op), so a newer marketplace
commit was never picked up — exactly why the freshly-pushed omp routing card
didn't reach the cache until a manual `/plugin` reinstall. Step 4f of the
sync skill already called this out for `omc` specifically ("install.sh never
upgrades an already-installed plugin"); this generalizes the fix to every
enabled user-scope plugin via an **opt-in** `--update` flag, without touching
install.sh's idempotency contract.

The flag does **not** decide staleness itself — `claude plugin update` is
idempotent and no-ops when a plugin is already current (verified live
2026-06-05: re-running it printed `already at the latest version` and left the
installed SHA + timestamp untouched). Self-comparing marketplace-mirror SHAs was
rejected as the detection mechanism because a mirror's `.git` tracks the
*marketplace manifest* repo, not each contained plugin's code repo — so a
multi-plugin marketplace (e.g. claude-plugins-official) would mis-judge. Letting
the CLI judge keeps the "never clobber a current plugin" guarantee.

### Added
- `installer/scripts/plugin_sync.py` — `Action.UPDATE` and a `plan_actions(..., update_candidates=False)` flag. When set, a user-scope plugin that would be `OK` is re-labelled `UPDATE` (only `OK→UPDATE`; `INSTALL`/`REINSTALL`/`SKIP_OS` are untouched — you can't update what isn't installed and a scope fix takes priority). `apply()` handles `UPDATE` with `claude plugin update <plugin>` (dry-run logs `would update`); the summary line now reports `N updated`. New `--update` CLI flag; without it, a one-line advisory reports the candidate count (`re-run with --update`) — never a false "N updates available" claim, since only the CLI knows what's stale.
- `runtime/skills/sync-claudebase/SKILL.md` — new **step 4g** ("Other plugins up-to-date?") with the detect-then-ask flow: show `plugin_sync.py --dry-run --update` candidates, ask the user, then `--apply --update`. Same governance as 4e/4f (never auto-apply). Added a 4g pointer in step 4f, a `Plugin updates (4g)` row in the outputs table, and the live-verified idempotency note.
- `tests/installer/test_plugin_sync.py` — 5 new tests: default keeps user-scope `OK` (idempotency regression guard), `--update` re-labels to `UPDATE`, `--update` leaves INSTALL/REINSTALL alone, dry-run `apply` emits `would update` without a subprocess, and the summary counts updates separately. **104 tests total, all passing** (was 99; +5).

### Notes
- `claude plugin update` prints "restart required to apply" — the skill tells the user to relaunch the session if any plugin was actually refreshed.
- Design decisions (CLI-delegated detection, opt-in not auto, `--dry-run` as the "ask" channel) were taken interactively with the user; the "never let latest updates get erased" constraint drove the idempotency-first approach.

## [Unreleased] — 2026-06-05 — harden the AskUserQuestion empty-call guards

External research (GitHub `anthropics/claude-code` #64150 / #64774 / #65247) confirmed the empty-`questions` `AskUserQuestion` failure is a **model-side emission defect** on large-context Opus 4.8 (1.5% vs 0% on Opus 4.7 / Sonnet 4.6), worsened by large injected context — not a settings or plugin bug, and not directly caused by OMC (whose bridge only reads the payload to notify). The defect is upstream and unfixable here; these are recovery/mitigation improvements to the two existing guards. Model inference is unaffected — the hooks run only at turn-end / on an actual empty call.

### Changed
- `runtime/hooks/askuserquestion_retry.py` — four hardenings: (1) tail-scan window raised 40→200 physical JSONL lines so a busy turn's rejection isn't missed; (2) a genuine human turn between two empty calls now **breaks** the consecutive-empty streak (a user answering between unrelated failures is no longer escalated toward abandon) — bare-string-content rejections are still counted, not mistaken for a human turn; (3) cross-shape session counter folds the PreToolUse guard's denies with this hook's own rejections per `session_id` and escalates to abandon at threshold 5 (counting the in-flight failure) even when the tail streak is low; (4) the retry-stage reason now also points to `/compact`.
- `runtime/hooks/askuserquestion-guard.py` — every deny now appends a best-effort telemetry record to `.omc/logs/askuserquestion_guard.jsonl` (signal `denied_askuserquestion`) so the Stop hook can count failures across shapes. Logging never changes the deny decision and never raises.

### Added
- `runtime/hooks/askuserquestion_stats.py` — manual aggregator that folds both logs into a human summary (total / guard-denies / retry-rejections / abandon-events / by-session). Not wired into any hook → zero per-turn cost; read-only over the logs.
- `tests/hooks/test_askuserquestion_stats.py` (4 tests) plus new cases in `test_askuserquestion_retry.py` and `test_askuserquestion_guard.py` covering the window, human-turn streak break, bare-string rejection, cross-shape count, in-flight-threshold off-by-one, and `/compact` in the retry reason. **Independent code review (feature-dev:code-reviewer) caught two real bugs — the in-flight off-by-one and the bare-string false-positive — both fixed with regression tests before commit. 99 tests total, all passing.**

### Notes
- Known latent issue (not fixed; fail-open so no correctness risk): the guard/retry logs are unbounded and `_session_failure_count` rescans both on every Stop. On a machine with weeks of long sessions this grows; revisit with log rotation if it becomes noticeable.

## [Unreleased] — 2026-06-05 — split rule WHY out of the loaded CLAUDE.md

`config/CLAUDE.md` (symlinked to `~/.claude/CLAUDE.md`, loaded into every session on every machine and project) had accumulated four `Operational Limits` bullets where the *behavioral rule* and its *debug history* lived in one paragraph — issue numbers, hook markers, transcript evidence, incident dates inline. One bullet was **3,457 chars**. This split the **why** out to an unloaded file and added a contract so it cannot re-accumulate.

### Added
- `docs/operating-rationale.md` — the **why** behind each `Operational Limits` rule (issue numbers, hook design, transcript evidence, incident dates), with one `## <anchor>` section per rule. Not loaded into any session, so the expensive context lives here instead of in `CLAUDE.md`. Four sections moved verbatim: `complete-tool-payloads`, `no-leaked-toolcall-markup`, `self-scheduled-wakeup-not-instruction`, `recommendation-not-approval`.
- `config/CLAUDE.md` → `### Adding an Operational Limit` — the contract that keeps the file lean: a rule is **one action-only bullet ≤350 chars**; the *why* goes to `docs/operating-rationale.md` and is linked with `↪ rationale: …#<anchor>`. Before writing a sentence: "instruction or explanation-of-why?"

### Changed
- `config/CLAUDE.md` — four bloated bullets compressed to action-only (each now 529–681 chars, was up to 3,457), each carrying a `↪ rationale:` link. **No information lost** — every cut sentence moved to `operating-rationale.md`. Untouched: `3-Strike`, `15-Min`, `Deletion Safety`, `Multi-session git` (already action-only or all-procedure). Net: **33,014 → 28,445 chars (−4,569, ≈14%)** off every session's loaded context.

## [Unreleased] — 2026-06-02 — recommendation ≠ approval guard

Fixes a behavioral failure where abandoning the empty-`AskUserQuestion` tool was misread as authorization to *do the work*. In a live session the model recommended a place name (KIOST), the user replied "that's correct, but…" (verifying the fact, not approving the action), and the model started editing on an unmade decision — drawing a sharp rebuke. Root cause: the abandon/retry guidance said "state a prose recommendation and **proceed**", and "proceed" was read as "begin edits" rather than "continue the conversation".

### Changed
- `runtime/hooks/askuserquestion_retry.py` — `REASON_ABANDON` and `REASON_RETRY` (and their docstring/comment mirrors) no longer say "proceed with that recommended option". They now say: present the recommendation in prose, then **WAIT for the user**; abandoning the *tool* does not authorize doing the *work* on a decision the user has not made; a user confirming a guessed fact is not a "yes, proceed". The only continue-without-waiting case is a trivial sub-choice inside already-approved work, and even then the model must state the assumption it is proceeding on.
- `config/CLAUDE.md` — the "Complete tool payloads" bullet's two "and proceed" phrasings reworded to "continue the conversation … not start doing the work". Added a dedicated bullet next to the self-scheduled-wakeup rule: **"A recommendation is not approval; confirming a fact is not a 'yes, do it'"** — covering both the tool-abandon≠work-authorization trap and the "you guessed right ≠ consent" trap, with the tell ("about to write 진행합니다 right after a fact-only acknowledgement").

### Added
- `tests/hooks/test_askuserquestion_retry.py::test_three_in_a_row_forces_abandon` — regression guard asserting the abandon message contains "wait" and a "not authorize"/"not a 'yes" clause, and that the old "proceed with that recommended option" wording is gone. **85 tests total, all passing.**

## [Unreleased] — 2026-05-29 — P1 hardening

Second post-standardize cycle. Focused on **internal quality, safety nets, and SSOT cleanup** rather than user-visible features. The 220-LOC `sync_plugins` bash function moves into a unit-tested Python module; CI starts running on every push; the installer's idempotency contract is now machine-checked by a smoke test.

### Added
- `installer/marketplace-metadata.json` — installer-only SSOT for marketplace OS gates (`os`) and post-install hooks (`post_install`). Keeps undocumented fields out of `config/settings.json`'s `extraKnownMarketplaces`.
- `installer/scripts/plugin_sync.py` — replaces 220 LOC of bash + embedded Python heredoc in `install.sh`. Two-phase design: pure `plan()` over filesystem inputs + `apply()` for side effects. 13 unit tests in `tests/installer/`.
- `installer/scripts/patch_omc_freeze.sh` — extracted from `install.sh`. The OMC `post-tool-verifier.mjs` sed-patch now lives in its own script.
- `docs/upstream-patches.md` — registry of local patches to vendored plugin code, with removal conditions for each.
- `tests/` — pytest suite covering all four `runtime/hooks/` scripts (`askuserquestion-guard`, `fix_surrogate`, `merge-project-hook`, `omc-reference-emit`) plus `plugin_sync`. **31 tests total**.
- `tests/smoke/test_install_idempotent.sh` — gates the "two runs = zero actions" invariant from `docs/ARCHITECTURE.md`. Detected the `install_omc_hud` regression that the previous grep patterns missed.
- `.github/workflows/ci.yml` — lint (ruff + shellcheck) + matrix tests (ubuntu + macos) + smoke on every push and PR.
- `docs/specs/<topic>/{design,plan}.md` per-topic spec folder convention; existing specs migrated via `git mv`.
- `docs/specs/2026-05-29-install-sh-modularization/design.md` — handoff design for P3 (installer modularization).
- `docs/specs/P4-todo.md` — backlog for P4 (CLAUDE.md hardening, `rules/` split investigation).

### Removed
- `runtime/hooks/routing-verdict-reminder.py` — dead code. Its role (per-turn routing nudge) was absorbed by the omha meta-harness's `<omha-routing>` UserPromptSubmit injector. `grep -r` across the repo confirmed zero references before deletion.

### Changed
- `installer/install.sh` 589 → ~405 LOC. `sync_plugins()` now a thin Python delegate. OMC freeze patch extracted. `install_omc_hud()` now idempotent (skips cp when destination already byte-matches the template + customization marker — fix for a regression caught by the smoke test).
- `.gitignore` now ignores `.omc/` runtime state wholesale (previously partial).
- `config/settings.json` gains a `SessionStart` `SURROGATE_AUTO_REPAIR_ON_START` hook (companion to the existing `Stop` hook).
- `runtime/hooks/merge-project-hook.py` docstring documents the single-marker / single-event limitation (M7).
- `docs/ARCHITECTURE.md` notes the new spec folder convention.

### Verification
- `installer/install.sh && installer/install.sh` — second run prints zero `linked:` / `rendered:` / `installing:` / `installed HUD:` / `applied:` lines (machine-checked by smoke).
- `python3 -m pytest tests/ -v` — 31 passed.
- `bash tests/smoke/test_install_idempotent.sh` — PASS.

### Notes
- `routing-verdict-reminder.py` deletion is recoverable via git history if its role ever needs to be reintroduced outside omha.
- `marketplace-metadata.json` is consumed only by `plugin_sync.py`; Claude Code itself never reads it. Keep `extraKnownMarketplaces` in `settings.json` as the canonical source for repo/url.

---

## [Unreleased] — 2026-05-29 — claudebase standardize

First standardized release. Repo renamed `claude-settings` → `claudebase` and reorganized by purpose for public-facing reuse.

### Added
- `docs/ARCHITECTURE.md` — directory model, symlink mechanism, plugin sync, secrets, drift detection
- `docs/CHANGELOG.md` — this file
- `docs/CONTRIBUTING.md` — fork-friendly PR guide
- `LICENSE` — MIT
- Source-by-purpose top-level layout: `config/`, `runtime/`, `installer/`, alongside existing `docs/`, `platform/`, `shell/`, `secrets/`, `templates/`

### Removed
- `agents/paper-*.md` (6 agents) — replaced by `oh-my-scholar` plugin
- `skills/paper-write/` — replaced by `oh-my-scholar` plugin
- `skills/using-omc/` + its hooks fragment — role absorbed by omha's ROUTE injector hook
- `docs/ppt-skills.md` — `ppt-*` skills migrated to `oh-my-docs` plugin (earlier commit `e43e8b3`)
- Committed `.bak` files — `.gitignore` already covers them
- `install.sh` / `install.ps1` backup logic — symlink overwrite is safe, redundant under idempotency contract

### Changed
- Repository renamed: `claude-settings` → `claudebase` (GitHub auto-redirects old URL)
- Directory restructure (all `git mv`, history preserved):
  - `claude/{settings.json,CLAUDE.md,mcp.template.json}` → `config/`
  - `claude/hooks/` → `runtime/hooks/`
  - `claude/scripts/` → `installer/scripts/`
  - `agents/`, `skills/` → `runtime/`
  - `install.sh`, `install.ps1` → `installer/`
  - `specs/` merged into `docs/specs/`
- Installer entrypoint: `./install.sh` → `./installer/install.sh`
- `REPO_DIR` resolution in `installer/install.{sh,ps1}` now walks one directory up to handle the new layout
- README slimmed to a quick-start (details moved to `docs/ARCHITECTURE.md`)

### Migration

Existing users on a machine that already has `~/claude-settings`:

```bash
cd ~/claude-settings
git pull
installer/install.sh    # picks up new layout, re-links symlinks if needed
installer/install.sh    # second run should be 0 actions
```

GitHub auto-redirects the old `claude-settings` URL, so no `git remote set-url` is strictly required, but recommended for clarity:

```bash
git remote set-url origin https://github.com/luckkim123/claudebase.git
```

Optional: rename the local clone too:

```bash
mv ~/claude-settings ~/claudebase
cd ~/claudebase
installer/install.sh    # re-points symlinks to the new path
```

New install: see `README.md`.

### Pre-claudebase tag

The state immediately before this standardize cycle is tagged `pre-claudebase-standardize-2026-05-29` for rollback.

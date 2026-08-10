# Changelog

All user-visible changes to this repo. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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

# code graphs: when to trust them, and when not to

> **`code-review-graph` (CRG) was removed from claudebase on 2026-08-29.** The
> call was not about usage — CRG's own MCP tools were the least-consulted layer
> in every project this file measures — it was about **binding**: every prior
> removal this repo has made (tokensave, 2026-08-25; graphify's own MCP server,
> 2026-08-23) traces to the same cause, a tool no `PreToolUse` hook names. CRG
> was the same story a third time. Keeping it would have meant building it a
> binding hook from nothing; keeping graphify only meant deleting CRG. Three
> things a project loses by this removal, not to be papered over:
>
> 1. **Symbol-level queries** — callers of, importers of, blast radius at a
>    depth. graphify has no symbol index; the answer is now `grep -rn`.
> 2. **Nested-graph auto-refresh.** The `graph-refresh` hook used to
>    `find -maxdepth 3` for every `.code-review-graph/` under a workspace and
>    refresh each one it found. The graphify block beside it watches only the
>    single `$GRAPHIFY_OUT/graph.json` at the repo root — a workspace of nested
>    repos now gets one graph, not one per repo.
> 3. **The empty-graph guard** — the sqlite node-count check that skipped a
>    0-node CRG database before refreshing it (an MCP query that omits
>    `repo_root` fabricates exactly such a database). graphify's `graph.json`
>    has no equivalent counter.

Rules for a project carrying a [graphify](https://github.com/Graphify-Labs/graphify)
graph. It answers structural and connectivity questions — what imports what,
what is a hub, what a corpus of code *and* prose looks like as a map — from a
local index instead of reading files, which is why it is worth reaching for
first. It also fails **silently** in specific conditions, and every rule below
exists because of one of them.

Copy to `<project>/.claude/rules/code-graph.md` and point at it from
`CLAUDE.md`. Delete it if the project has no graph.

## What graphify answers, and what only CRG used to answer

graphify is installed by `claudebase` but does not build a graph until a
project asks for one (`graph-init`, or by hand below). What follows splits by
*question*:

| You want | Tool | Note |
|:---|:---|:---|
| Callers/importers of a symbol, blast radius at a depth | **Gone** | CRG-only; use `grep -rn` |
| The body of a symbol by name, without knowing its file | **graphify** | `graphify query "<identifier>"` to locate the node, then `Read` |
| A map of a corpus that is not just code — docs, PDFs, notes, schemas | **graphify** | the free AST pass alone can't do this either — see the semantic-pass section below |
| "What is connected to what" across a whole repo, communities, hubs | **graphify** (`god-nodes`, `query`) | the one thing a grep cannot answer |
| An artifact a human opens — HTML, SVG, an Obsidian vault, a wiki | **graphify** (`export`) | |
| Sub-second re-query while editing | **Nobody, cleanly** | this was CRG's edge; graphify rebuilds, and `graphify watch` reduces but doesn't remove that cost |
| Find the note/section that discusses X, in a repo of prose | **neither** — `grep`/`Read` | the free pass is tree-sitter, which emits zero nodes for markdown |
| Code health — dead code, god classes, complexity, coupling, DSM | **neither** | graphify doesn't compute metrics |

**A third index, `tokensave`, was removed on 2026-08-25.** It was the one that
indexed markdown headings and computed code-health metrics for free, so the
last two rows above are genuine losses, not rewordings — in a prose repo the
honest answer is now `grep` (or graphify's paid pass). It was dropped because
nothing routed to it: 6 MCP calls against 10,813 tool calls over 22 days on the
repo that had the strongest reason to use it, while it cost a resident server
per session and ~80 deferred tool names in every prompt. The binding layer
(`PreToolUse`) named graphify's CLI and never named tokensave — the "only layer
that is binding" section below is exactly the diagnosis. Re-adding it means
wiring the hook first, not the server.

Ask the cheapest, most specific `graphify` query first and fall back to a
broader one only when that returns nothing *and* you have confirmed the empty
answer is real rather than one of the silent failures below.

## Giving a project its graph

One command, and it is the one the SessionStart offer points at:

```bash
graph-init            # exclusions → build → verify the node distribution
graph-init --purge    # if the verification says the graph is somebody else's code
```

It does everything the rest of this section describes — writes the ignore file
from the templates, runs `graphify . --code-only`, then checks *where* the
nodes came from and exits 2 when a vendored tree fills the graph. Reach for the
manual steps below only when you need to customize a step, or when
`~/.local/bin` is not on PATH (then: `~/.local/bin/graph-init`).

It works outside git too. The build walks a plain directory rather than relying
on `git ls-files` — graphify never needed git — so a container mount like
`/workspace` is a legitimate target.

## Wiring graphify into a project, by hand

```bash
cp ~/claudebase/templates/project-graphifyignore .graphifyignore   # FIRST — see below
graphify .                                          # build (AST only — offline, no key)
graphify install --platform claude --project        # wire it into THIS project
graphify update .                                   # after edits, still no LLM
```

**The ignore file comes first, and the order is the whole point.** The default
scope is every tracked file, which means `.claude/`, `.omp/`, `.obsidian/`,
`.mcp.json`, and every screenshot in the tree. None of that is corpus content —
it is tooling config, harness state, vendored plugin JS, and images whose vision
pass burns ten minutes per chunk to produce nothing. A single `.*` excludes
hidden directories and dotfiles at any depth, verified against graphify's own
`detect()` on a fixture tree: it drops `.claude/skills/SKILL.md`, `.mcp.json`,
and `.obsidian/plugin.js` while keeping `README.md` and `0_Project/note.md`.
Project-specific rules go on the end of the seeded file:

```
.obsidian/       # bundled Obsidian plugin JS — nobody here wrote it
3_Archive/       # retired material, same call
```

Adding the rule afterwards is not equivalent. AST re-extraction is free, but the
semantic pass runs about 5 minutes per chunk *serially* on the `claude-cli`
backend, so a late exclusion buys back only the chunks that have not started —
everything already extracted was paid for at full price and then discarded.

**`--project` is not optional here.** Without it, `install.py` writes its
CLAUDE.md block with `Path.write_text` into `~/.claude/CLAUDE.md`; `write_text`
follows symlinks, and claudebase makes that path a symlink to the repo's own
`config/CLAUDE.md`. A machine-local tool install would edit tracked repo content
in place and ship to every other machine on the next sync. With `--project`, all
of it lands under the project's `.claude/`.

The output directory here is **`.graphify/`**, not graphify's default
`graphify-out/`: `GRAPHIFY_OUT` is set in `config/settings.json`, which puts the
index in the gitignored-dot-directory family rather than leaving a visible
build directory at the project root. A repo indexed before that switch keeps
its `graphify-out/` — rename it to `.graphify/` when the build is idle. Both are
gitignored.

Optionally add the MCP server, which serves `<GRAPHIFY_OUT>/graph.json` relative to
the working directory — so it belongs in the **project's** `.mcp.json`, never in
`~/.claude/mcp.json`, where it would launch against a nonexistent graph in every
repo that has not built one:

```jsonc
// <project>/.mcp.json
{ "mcpServers": {
    "graphify": { "type": "stdio", "command": "graphify-mcp", "args": [] } } }
```

**Leave `args` empty — never pin `--graph` to a path.** The empty form is not a
shortcut, it is the only form that survives the `GRAPHIFY_OUT` switch:
`serve.py` falls back to `default_graph_json()`, which reads the env var
(`paths.py:26`), and Claude Code does inject `config/settings.json`'s `env` block
into MCP server processes — measured with `ps eww` on a live `graphify-mcp`,
`GRAPHIFY_OUT=.graphify` was present. A hand-written
`"args": ["--graph", ".../graphify-out/graph.json"]` overrides that fallback and
pins the pre-switch path, so the server launches happily against a file that does
not exist and every graphify MCP tool answers from nothing. Nothing errors —
this is the silent-success class again. Measured on the obsidian vault
2026-08-10: four `graphify-mcp` processes serving a missing `graphify-out/graph.json`
while the real index sat in `.graphify/`. Audit with:

```bash
python3 -c "import json;print(json.load(open('.mcp.json'))['mcpServers'].get('graphify'))"
ls -l "${GRAPHIFY_OUT:-graphify-out}/graph.json"     # the path that must exist
```

That server needs the `mcp` extra — `uv tool install "graphifyy[mcp,office]"`,
which is what `install.sh` does. The `graphify-mcp` shim ships either way, so a
plain `graphifyy` install looks fine and fails only on connect, with
`ModuleNotFoundError: No module named 'mcp'`.

`office` rides along on the same install because its absence is quieter still.
graphify cannot read a `.docx`/`.xlsx` directly: `detect()` converts each to a
markdown sidecar under `<GRAPHIFY_OUT>/converted/` and extracts *that*. Without
the extra the conversion never runs, the file is reported once under
`skipped_sensitive`, and it is simply absent from the corpus — no error, no node.

**And the sidecar has to survive your own ignore file.** The conversion output
lands inside `<GRAPHIFY_OUT>/`, which the recommended `.*` rule excludes, so
`detect.py` drops the sidecar with a bare `continue` — this time without even a
`skipped_sensitive` entry. Installing the extra makes the warning disappear while
the node count stays zero, which reads exactly like a fix. graphify enforces
gitignore's parent-exclusion rule, so a single `!` cannot rescue it; re-include
the two ancestor directories, re-ignore the rest, then re-include the sidecars
with a `**` (a directory-only pattern never matches the `.md` itself):

```
.*
!.graphify/
.graphify/*
!.graphify/converted/
!.graphify/converted/**
```

Verify by node count, never by the warning going away:

```bash
graphify_py=$(cat .graphify/.graphify_python)
"$graphify_py" -c "
from pathlib import Path
from graphify.detect import detect
r = detect(Path('.'))
allf = [f for v in r['files'].values() for f in v]
print('sidecars in:', sum('/converted/' in f for f in allf))
print('LEAK (must be 0):', sum('/.graphify/' in f and '/converted/' not in f for f in allf))"
```

`.pptx` has no conversion path at all — `OFFICE_EXTENSIONS` is `.docx` and
`.xlsx` only, so a slide deck stays out of the graph whatever you install.

### The only layer that is binding

A graph nobody consults is worth nothing, and this repo's own removals —
tokensave, graphify's MCP server, and CRG — all trace to the same distinction:

| Layer | What it does | Binding? |
|:---|:---|:---|
| MCP server (`.mcp.json`) | Puts `query_graph`, `god_nodes`, `shortest_path` … in the tool list | **No** — offers a choice, nothing more |
| `CLAUDE.md` block | "run `graphify query` first for codebase questions" | **Weak** — routinely ignored under momentum |
| `PreToolUse` hooks (`.claude/settings.json`) | `graphify hook-guard` fires on `Bash\|Grep` and `Read\|Glob` | **Yes** — intercepts the call itself |

Only the hook survives an agent that has decided to just grep. It is also the
only layer that reaches **subagents** — OMC agents, `superpowers` subagents, `Task`
dispatches — because hooks are enforced at the tool-call boundary rather than by
the model reading an instruction. A subagent inherits none of your resolve and
frequently not your `CLAUDE.md` reading; it does inherit the hook.

**The hook is only binding where it can find the graph, and that is a cwd
question.** `hook-guard` resolves `graph.json` through `Path(GRAPHIFY_OUT)` —
relative (`paths.py:293`), so it lands wherever the hook's cwd happens to be, and
hooks run with the *session's* working directory. The Bash tool's cwd persists
across calls, so a single `cd sub/repo && …` in any earlier command disables the
guard for the rest of the session. Measured on a three-repo workspace: identical
greps nudged from the root and went silent one directory down, with nothing
announcing that the binding layer had stopped binding.

`runtime/hooks/graphify-guard.sh` closes this by walking up from cwd to the
nearest ancestor holding `$GRAPHIFY_OUT/graph.json` and running there. It uses
neither `CLAUDE_PROJECT_DIR` (not exported to hooks — the same finding
`graph-refresh.sh` records) nor `git rev-parse` (a workspace of nested repos is
often not itself a repo). Nearest wins, so a nested repo carrying its own graph
still answers for itself; no ancestor has one and nothing changes.

`--strict` (or `GRAPHIFY_HOOK_STRICT=1` at runtime, no reinstall needed) escalates
the read hook from advisory to **blocking the first raw read of a session**. Start
without it; add it only once the graph is genuinely current, since a stale graph
plus a blocking hook means the agent is forced to consult a wrong map.

### What costs money and what does not

Code is parsed with tree-sitter — deterministic, offline, free, no key. Prose,
PDFs, and images are different: those go through an LLM, so pointing graphify at
a large note corpus is a real bill, not a free index. `--backend claude-cli`
routes that extraction through the `claude` CLI you already pay for instead of a
separate API key; it is not in `detect_backend`'s auto-detect list, so it only
takes effect when passed explicitly.

What that pass actually produces, and why it is the only way to graph prose:
tree-sitter has no symbol concept for a note, so the LLM is asked for the
entities and relations instead, one chunk at a time, emitting
`{"nodes": [...], "edges": [...], "hyperedges": [...]}` — concept nodes carrying
a `label` and a `source_file`. That is the difference between a plain text
search over notes and a graph of ideas across them.

Budget it in hours, not dollars. `--max-concurrency` defaults to 4 but is forced
to **1** for the `claude-cli` and `ollama` backends, so the chunks run serially:
measured on one 774-note vault, 5.3 min per chunk over 58 chunks, about five
hours. Nothing about that fits inside a hook.

### Who keeps it current, and who decides it exists

Three separate lifecycle questions, and conflating them is how a repo ends up
either nagged or silently stale:

| Stage | Cost | Who does it |
|:---|:---|:---|
| **Consult** | ~51 ms per guarded tool call | Automatic — `PreToolUse` guards, every repo, every subagent |
| **Update** (code) | 1.0 s | Automatic — `Stop` hook, detached, debounced to once a minute |
| **Update** (prose) | hours | Deliberate `/graphify`; `graphify check-update` is the cron-safe *detector* |
| **Create** | seconds (tree-sitter) | Offered once per repo, then the user decides |

**A graph the CLI cannot regenerate must opt out of the update row.** `graphify
update .` re-scans, so it can only keep current a graph whose corpus that scan
finds. A graph assembled from an explicit file list — code sitting in gitignored
checkouts, any scope a rebuild script collects by hand — is invisible to it, and
every file it cannot see reads as *deleted*: the update prunes the graph down to
whatever the root scan does find, reporting no error. Measured on a three-repo
workspace (2026-08-21): a deliberate 434-file / 6,427-node code graph was replaced
by a 20-node markdown heading index two minutes after it was built, and again on
an earlier build. Drop a `.no-auto-refresh` file next to `graph.json` to keep the
Stop hook off it, and refresh it deliberately instead.

Creation is the one that must not be automatic, and cost is not the reason —
the free build takes seconds. The reason is that a blindly built graph is
**worse than none**, because the guards then require the agent to consult it.
The vault above is the proof: a `--code-only` build produced 16,954 nodes, of
which **16,044 (94%) came from `.obsidian/plugins`** — bundled plugin JS nobody
in the repo wrote, with no error anywhere. Auto-building would mass-produce
that. So the offer carries the verification step with it — `graph-init` prints
the node distribution and refuses (exit 2) when a vendored tree fills the
graph; confirm the nodes are not vendored and `graph-init --purge` if they are.

### Reading the graph in Obsidian, and the sidecar that silently ruins it

`graphify export obsidian` turns the graph into a vault: one `.md` per node with
`[[wikilinks]]`, a `_COMMUNITY_<name>.md` overview per community, a
`graph.canvas`, and YAML frontmatter carrying `source_file` back to the note the
node came from. That back-reference is the whole point — the export is a *map of*
the corpus, not a copy of it.

Export to `<GRAPHIFY_OUT>/obsidian/` (the default) and open **that directory** as
its own vault. Do not aim `--dir` at a live vault's note tree: the output is
roughly one file per node (10,800 files / 46 MB on the vault measured here), it
lands in git, and graphify then re-indexes its own output on the next build.
The default sits under the gitignored `.graphify/`, and Obsidian hides dot-dirs,
so the live vault never sees it.

**The trap.** Community names come from `.graphify_analysis.json`, a sidecar —
not from the graph. `graph.json` does carry a `community` id on every node, and
`cli.py` will reconstruct from it, but only under `if not communities:` — that is,
when the sidecar is **missing**, never when it is merely **stale**. A semantic
re-extraction rewrites `graph.json` and `.graphify_labels.json` and leaves the
sidecar untouched, so an incomplete sidecar is treated as authoritative and every
node it does not mention exports as `Community None`. Measured on the vault,
2026-08-10: sidecar from 14:04 with 68 communities / 900 node ids, graph from
15:41 with 9,874 nodes and all 926 communities labeled — the 8,974 nodes missing
from the sidecar were exactly the 8,974 notes tagged `community/Community_None`.

The tell is that count, so check it rather than trusting the export's cheerful
node total:

```bash
grep -l 'community/Community_None' "${GRAPHIFY_OUT:-graphify-out}"/obsidian/*.md | wc -l
ls -l "${GRAPHIFY_OUT:-graphify-out}"/.graphify_analysis.json \
      "${GRAPHIFY_OUT:-graphify-out}"/graph.json          # sidecar older = suspect
```

The fix is to move the stale sidecar aside and re-export, which forces the
reconstruction path onto the per-node ids — free, offline, and it keeps the
existing labels aligned because those ids are what the label file is keyed to.
Do **not** reach for `graphify cluster-only` to repair this: re-clustering mints
fresh community ids while `.graphify_labels.json` stays keyed to the old ones,
which trades `Community None` for confidently wrong names (reasoned from the id
keying, not measured — the repair below was the one actually run).

```bash
mv "${GRAPHIFY_OUT:-graphify-out}"/.graphify_analysis.json /tmp/analysis.stale.json
graphify export obsidian
```

## Reach for the graph first

| Question | Tool |
|:---|:---|
| What connects to what — hubs, communities, cross-cutting concepts | `graphify god-nodes` / `graphify query` |
| How do two parts of the corpus connect? | `graphify path "<A>" "<B>"` |
| Find a function, class, or concept by name | `graphify query "<term>"` |
| Show me this symbol's source | `graphify query "<identifier>"` to locate, then `Read` |
| Who calls / imports this symbol? | **`grep -rn`** — symbol-level queries went with CRG |
| Blast radius of a change | **`grep -rn`** — same reason |

## Go straight to file tools

- **Config files (YAML, JSON, TOML).** The code-only pass produces no nodes for
  them, so the graph has nothing to say about a config change — and an empty
  answer here reads exactly like "no impact". Compare sibling config files with
  `grep` instead. In systems where behaviour is tuned by config rather than
  code, this is where the dangerous changes live.
- **Repos dominated by vendored third-party code.** Community and hub results
  fill up with someone else's library and say nothing about your code. The
  tell: a hub and nearly all of its community share one vendored directory —
  that is not a clean architecture, it is a disconnected vendor tree. Read
  `README` / the build manifest instead.
- **Prose corpora — a notes vault, a docs tree, anything mostly `.md`.** The
  free (`--code-only`) build is tree-sitter all the way down, and tree-sitter
  has no notion of a symbol in prose, so markdown contributes **zero nodes**
  there — passing `--code-only` over a notes vault is exactly as blind as the
  old CRG tree-sitter pass ever was. The same vault makes the vendored-code
  trap concrete: a `--code-only` build produced 16,954 nodes, of which
  **16,044 (94%) came from `.obsidian/plugins`** — bundled plugin JS nobody in
  the repo wrote. Excluding `.obsidian/` via `.graphifyignore` left 908 nodes,
  which is the honest size of what we actually authored. Check the path
  distribution of a fresh graph before wiring it to anything; a big node count
  in a prose repo usually means the extractor found somebody else's
  `node_modules`. Only graphify's paid **semantic** pass (above) actually reads
  the prose itself — without running it, a question about the notes is a
  `grep` question.

## What no code graph can see

Coupling that crosses a process boundary is never an edge: message-bus topic
names and their QoS/delivery settings (ROS 2, MQTT, Kafka), service names
resolved at runtime, and orchestration files that wire processes together.
A mismatch there typically shows up only as a subscription that never fires, so
verify it against the running system (for ROS 2, `ros2 topic info -v`), never
against the graph.

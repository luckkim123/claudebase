# code graphs: when to trust them, and when not to

Rules for a project carrying a [code-review-graph](https://github.com/tirth8205/code-review-graph)
index (CRG), a [graphify](https://github.com/Graphify-Labs/graphify) graph, a
[tokensave](https://github.com/aovestdipaperino/tokensave) index, or any mix.
They answer structural questions (callers, importers, blast radius) from a
local index instead of reading files, which is why they are worth reaching for
first. They also fail **silently** in specific conditions, and every rule below
exists because of one of them.

Copy to `<project>/.claude/rules/code-review-graph.md` and point at it from
`CLAUDE.md`. Delete it if the project has no graph.

## Which of the three answers this question

All three are installed by `claudebase`; none builds a graph until a project asks
for one. They are complementary, not redundant — CRG is a query runtime, graphify
is a corpus builder, tokensave is a symbol-and-heading index with code-health
metrics — so the split is by *question*, not by preference:

| You want | Tool | Why the others are wrong |
|:---|:---|:---|
| Callers/importers of a symbol, blast radius, review context | **CRG** (MCP tools) | graphify has no incremental update; its graph is a build artifact |
| A map of a corpus that is not just code — docs, PDFs, notes, schemas | **graphify** | CRG's tree-sitter pass emits no nodes for prose (see below) |
| "What is connected to what" across a whole repo, communities, hubs | **graphify** (`god-nodes`, `query`) | CRG answers point queries, not neighbourhood shape |
| An artifact a human opens — HTML, SVG, an Obsidian vault, a wiki | **graphify** (`export`) | CRG has no human-facing output |
| Sub-second re-query while editing | **CRG** | graphify rebuilds; `graphify watch` helps but is not free |
| Find the note/section that discusses X, in a repo of prose | **tokensave** (`search`, `read mode=map`) | CRG sees no prose at all; graphify sees it only after a paid LLM pass |
| The body of a symbol by name, without knowing its file | **tokensave** (`body`, `signature`) | CRG returns locations, not source; graphify's nodes carry no bodies |
| Code health — dead code, god classes, complexity, coupling, DSM | **tokensave** | neither of the others computes metrics |
| Per-symbol git history or blame across renames | **tokensave** (`log`, `blame`) | the others are snapshot-only |

When several exist, ask the cheapest point query first (CRG or `tokensave_search`
is ~100–200 tokens) and fall back to graphify only when that returns nothing *and*
you have confirmed the empty answer is real rather than one of the silent failures
below.

## Wiring graphify into a project

```bash
graphify .                                          # build (AST only — offline, no key)
graphify install --platform claude --project        # wire it into THIS project
graphify update .                                   # after edits, still no LLM
```

**`--project` is not optional here.** Without it, `install.py` writes its
CLAUDE.md block with `Path.write_text` into `~/.claude/CLAUDE.md`; `write_text`
follows symlinks, and claudebase makes that path a symlink to the repo's own
`config/CLAUDE.md`. A machine-local tool install would edit tracked repo content
in place and ship to every other machine on the next sync. With `--project`, all
of it lands under the project's `.claude/`.

Optionally add the MCP server, which serves `graphify-out/graph.json` relative to
the working directory — so it belongs in the **project's** `.mcp.json`, never in
`~/.claude/mcp.json`, where it would launch against a nonexistent graph in every
repo that has not built one:

```jsonc
// <project>/.mcp.json
{ "mcpServers": {
    "graphify": { "type": "stdio", "command": "graphify-mcp", "args": [] } } }
```

That server needs the `mcp` extra — `uv tool install "graphifyy[mcp]"`, which is
what `install.sh` does. The `graphify-mcp` shim ships either way, so a plain
`graphifyy` install looks fine and fails only on connect, with
`ModuleNotFoundError: No module named 'mcp'`.

### Three layers, only one of which is binding

A graph nobody consults is worth nothing, and the three integration layers differ
enormously in how strongly they get consulted:

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

## tokensave: the only one that reads prose without a bill

tokensave runs from `~/.claude.json` (user scope, absolute path — it is not on
`PATH` under the Bash tool, so `which tokensave` says "not found" on a machine
where it is installed and working). It writes one SQLite index per repository at
`<repo>/.tokensave/`, which belongs in `.gitignore`.

It indexes markdown, and that is what separates it from the other two. Measured
on one Obsidian vault, same 774 tracked `.md` files, three tools:

| Tool | Nodes from the prose | What they are |
|:---|---:|:---|
| CRG | 0 | tree-sitter has no symbol concept for prose |
| graphify `--code-only` | 0 | prose needs the paid semantic pass |
| **tokensave** | **~10,356** | one node per heading (~9,582) + one per file (774) |

Do not match on the heading nodes' `kind` string: it was `module` on v7.0.2 and
`struct` on v7.9.0, for the same headings in the same vault. Filter by file
extension, or by `kind = 'file'` for the file-level node, and treat everything
else in a `.md` as a heading.

So in a notes repo tokensave is a heading index with full-text search over the
whole corpus, available offline and free. That is a different product from the
call graph it builds over real code, and it is the reason to reach for it here.

**One identifier per query — never a phrase.** Same index, same session:

```
tokensave_search "runaway"        → 2 hits, file:line, 2703 → 194 tokens (93% less)
tokensave_search "joint runaway"  → []
```

Multi-word input drops into keyword/FTS mode and matches nothing, returning `[]`
rather than an error — the same silent failure CRG has, and the most common way
to conclude "nothing here" from a healthy index. Query one token, then widen.

**What it is not for in a prose repo.** `dead_code`, `god_class`, `complexity`,
`coupling`, and `dsm` are real tools, but they need code to measure; in a repo of
774 notes and 56 scripts they report on the corners. Run those against the code
repositories, not the vault.

**It costs while idle.** The index is rewritten whenever files change, whether or
not anything queries it. Measured on one vault: the DB was rewritten mid-session
while the query count for that session was zero.

**The process count is not a leak — do not "clean it up".** A stdio MCP server is
a child of the `claude` process that launched it, so `ps` shows one per live
session *and* one per background worker (`claude bg-spare`), and a busy machine
shows a lot of them. They are not orphans: measured across 984 sessions in 30
days, the count of `tokensave serve` processes reparented to init (`PPID 1`) was
**zero**, and the live count fell on its own from 12 to 9 within an hour as
sessions ended. The control group settles it — on the same machine at the same
moment: claude-mem 21 processes, code-review-graph 14, tokensave 9. This is what
stdio MCP looks like, not a defect in any one server. `pkill -f 'tokensave serve'`
kills the servers of *live* sessions, including the one you are in.

## The premise everything follows from

The graph indexes **`git ls-files`** — tracked files only. An untracked file is
not reported as missing; it produces `0 results`, which reads exactly like "this
code is unused". Failure looks like success.

So: **never conclude "not used anywhere" from an empty result.** Confirm with
`git ls-files | grep <file>` first. Three different conditions produce the same
empty answer:

| Cause | Tell | Fix |
|:---|:---|:---|
| File is untracked | `git ls-files` does not list it | Use `grep -rn`; the graph cannot help |
| Graph is stale | `_graph.head_matches_build` is `false` | Re-run `code-review-graph update` |
| Query had several words | Search ran in keyword/FTS mode | Query one identifier at a time |

That last one bites quietly: `semantic_search_nodes_tool` uses vectors only when
embeddings have been built (`code-review-graph embed`), and otherwise falls back
to keyword + FTS5, where a natural-language phrase matches nothing.

## Pass `repo_root` explicitly when the graph is not at the repo root

In a workspace whose real code lives in nested repositories (vcstool, submodules,
a monorepo of independent checkouts), the graph belongs to the *inner* repo. The
tools auto-detect `repo_root` from the working directory, which resolves to the
outer repo — where there is no graph, or an empty one. Always pass
`repo_root: <path to the repo that owns the graph>`.

## Reach for the graph first

| Question | Tool |
|:---|:---|
| Who calls / imports this tracked symbol? | `query_graph_tool` (`callers_of`, `importers_of`) |
| What does this change affect? | `get_impact_radius_tool` with **`max_depth=1`** |
| Starting a review of code changes | `detect_changes_tool` + `get_affected_flows_tool` |
| Find a function or class by name | `semantic_search_nodes_tool` (single identifier) |

**`max_depth=1`, not the default 2.** Depth 2 follows the *other* out-edges of
each importer, so sibling modules unrelated to the change get reported as
affected. Measured on one repo: depth 1 returned the 3 real importers and
nothing else; depth 2 returned 8 files, 5 of them false positives.

## Go straight to file tools

- **Untracked or newly created files.** Not in the index. `grep -rn`.
- **Config files (YAML, JSON, TOML).** They produce no nodes, so blast radius is
  always empty — and an empty answer here is indistinguishable from "no impact".
  Compare sibling config files with `grep` instead. In systems where behaviour is
  tuned by config rather than code, this is where the dangerous changes live.
- **Repos dominated by vendored third-party code.** Community and hub results
  fill up with someone else's library and say nothing about your code. The tell:
  `cross_community_edges` is `0` while several communities exist — that is not a
  clean architecture, it is disconnected vendor trees. Read `README` / the build
  manifest instead.
- **Prose corpora — a notes vault, a docs tree, anything mostly `.md`.** CRG is
  tree-sitter all the way down, and tree-sitter has no notion of a symbol in
  prose, so markdown contributes **zero nodes**. The graph does not report this;
  it reports the code it *did* find, which in a prose repo is whatever incidental
  code sits in the corners — a bundled editor plugin, a build script, `node_modules`.
  Measured on one Obsidian vault: 746 tracked `.md` files produced 0 nodes, while
  101 files of vendored plugin JS produced 21,425 "functions" and a 212 MB index.
  Nothing errored. The tell is a `list_graph_stats_tool` whose `languages` list
  does not contain the language you actually write here, or a file count far below
  `git ls-files | wc -l`. **Check that before adopting a graph-first rule**, or
  `CLAUDE.md` will instruct every session to consult an index that cannot see the
  repo. This is graphify's case, not CRG's — or tokensave's, which is the one
  that indexes the headings for free (above).

  The same vault makes the vendored-code trap concrete for graphify too: a
  `--code-only` build produced 16,954 nodes, of which **16,044 (94%) came from
  `.obsidian/plugins`** — bundled plugin JS nobody in the repo wrote. Excluding
  `.obsidian/` via `.graphifyignore` left 908 nodes, which is the honest size of
  what we actually authored. Check the path distribution of a fresh graph before
  wiring it to anything; a big node count in a prose repo usually means the
  extractor found somebody else's `node_modules`.

## What no code graph can see

Coupling that crosses a process boundary is never an edge: message-bus topic
names and their QoS/delivery settings (ROS 2, MQTT, Kafka), service names
resolved at runtime, and orchestration files that wire processes together.
A mismatch there typically shows up only as a subscription that never fires, so
verify it against the running system (for ROS 2, `ros2 topic info -v`), never
against the graph.

# code-review-graph: when to trust the graph, and when not to

Rules for a project that has a [code-review-graph](https://github.com/tirth8205/code-review-graph)
index. The tool answers structural questions (callers, importers, blast radius)
from a local SQLite graph instead of reading files, which is why it is worth
reaching for first. It also fails **silently** in four specific conditions, and
every rule below exists because of one of them.

Copy to `<project>/.claude/rules/code-review-graph.md` and point at it from
`CLAUDE.md`. Delete it if the project has no graph.

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

## What no code graph can see

Coupling that crosses a process boundary is never an edge: message-bus topic
names and their QoS/delivery settings (ROS 2, MQTT, Kafka), service names
resolved at runtime, and orchestration files that wire processes together.
A mismatch there typically shows up only as a subscription that never fires, so
verify it against the running system (for ROS 2, `ros2 topic info -v`), never
against the graph.

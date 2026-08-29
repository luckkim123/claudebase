---
name: graph-init
description: 'Use when a project needs its code graph built, rebuilt, or thrown away (한국어 - "코드 그래프 만들어", "그래프 다시 만들어", "그래프 지워", "여기 그래프 없어?" / English - "build the code graph", "rebuild the graph", "index this project"). Wraps the graph-init command, which seeds the ignore file, runs the free tree-sitter build, and refuses to leave behind a graph made of vendored code. Does NOT run graphify''s paid semantic pass over prose — that is /graphify.'
triggers:
  - "/graph-init"
  - "graph-init"
  - "코드 그래프"
  - "그래프 만들"
  - "그래프 다시"
  - "code graph"
  - "graphify"
---

# graph-init

**Run the command. Do not re-implement it.**

```bash
graph-init            # or ~/.local/bin/graph-init when the shell cannot resolve it
graph-init --purge    # delete both graphs, keep the ignore files
```

That is the whole mechanism. It seeds both ignore files from the claudebase
templates *before* extracting anything, builds both graphs with tree-sitter
(offline, no key, seconds), and then checks where the nodes came from. Spelling
those steps out and running them yourself is the failure this script replaced:
it has exit codes and tests, a re-enactment has neither.

## Ask before building

A graph is per-project state the user owns, and the PreToolUse guards force every
later session to consult whatever exists. So confirm with the user first unless
they just asked for it in so many words. `graph-init` alone is seconds and free;
`/graphify`'s semantic pass over prose is hours and metered, and is never part of
this skill.

## Read the exit code — this is the part that needs you

| Exit | Meaning | What to do |
|:---|:---|:---|
| 0 | Built and the distribution looks like this project's own code | Report the node counts it printed. Done. |
| 2 | A vendored tree holds ≥30% of the nodes | The graph describes somebody else's code. Act — see below. |
| 1 | Nothing was built | Read the warning it printed; usually a missing CLI or an empty tree. |

On **exit 2** the script names the offending top-level directory. Add it to the
ignore file, then re-run:

```bash
printf '%s/\n' <dir> >> .graphifyignore
graph-init
```

Check with the user before excluding anything that might be theirs. `vendor/` in
a Go repo is a real vendored tree; a directory that merely shares a name with one
may be the project's own source.

If a clean exclusion still cannot produce a graph of this project's code — a
repo that is mostly prose, for instance — the honest outcome is `graph-init
--purge`. An empty or misleading graph is worse than none, because the guards
will make every session ask it questions it cannot answer.

## Boundaries

- Not for prose corpora. Both free builds are tree-sitter, which emits zero
  nodes for markdown; graphify's LLM pass is `/graphify`, deliberately invoked.
- Refuses `$HOME` and `/` outside a git repo, by design. Pass a project directory.
- Works fine outside git: both builders walk a plain tree, so a container mount
  like `/workspace` is a legitimate target.

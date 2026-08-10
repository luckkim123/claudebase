# Project `.claude/` Boilerplate

Standard starting point for the `.claude/` directory when beginning a new project.

## Usage

```bash
# From the root of a new project:
cp ~/claudebase/templates/project-settings.json .claude/settings.json
cp ~/claudebase/templates/project-CLAUDE.md CLAUDE.md
cat ~/claudebase/templates/project-gitignore >> .gitignore
```

## Files

| Template | Copy to | Purpose |
|---|---|---|
| `project-settings.json` | `<project>/.claude/settings.json` | Project-level hooks/permissions (applies to this project only) |
| `project-CLAUDE.md` | `<project>/CLAUDE.md` | Project-specific instructions. Loaded automatically by Claude Code |
| `project-gitignore` | append to `<project>/.gitignore` | Excludes machine-specific files like `.claude/settings.local.json` |
| `project-refactor-workflow.md` | `<project>/.claude/rules/refactor-workflow.md` | Discipline for tracking the 4 axes of multi-stage refactoring (branch/commit/CHANGELOG/PR) |
| `project-code-review-graph.md` | `<project>/.claude/rules/code-review-graph.md` | Routing between `code-review-graph` and `graphify`, how to wire graphify's MCP server per project, and when either index silently returns nothing. Only for projects that have one |

## Principles

- **Universal settings** (plugins, alwaysThinking, etc.) live in `~/.claude/settings.json` (= the `claudebase` repo). This place is only for things meaningful **to this project only**.
- Never commit `.claude/settings.local.json` (it is gitignored).
- **Only the NEAREST `settings.local.json` is read.** A project's `.claude/settings.local.json` does not merge with `~/.claude/settings.local.json` — its `enabledPlugins` map fully **replaces** the home one. So a plugin enabled only at home goes silently dark inside such a project (no error; `install.sh` only warns). `~/.claude/settings.json` entries are immune — they always merge in. For a plugin you want everywhere, put it in the shared `config/settings.json`; otherwise re-declare it per project. Verify with `claude plugin list` run from the project, never from `$HOME`.
- Keep `CLAUDE.md` short and focused on Critical Rules — push the details out into `.claude/rules/<topic>.md`.

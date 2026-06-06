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

## Principles

- **Universal settings** (plugins, alwaysThinking, etc.) live in `~/.claude/settings.json` (= the `claudebase` repo). This place is only for things meaningful **to this project only**.
- Never commit `.claude/settings.local.json` (it is gitignored).
- Keep `CLAUDE.md` short and focused on Critical Rules — push the details out into `.claude/rules/<topic>.md`.

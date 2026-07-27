# Distributing claudebase as an installable plugin

**Status**: deferred (recorded 2026-07-27, not scheduled)
**Prerequisite**: the README reframe landed first — see the companion decision below.

## Why this is on the list

claudebase reads as a dotfiles repo, but its differentiated asset is not the
dotfiles. It is `runtime/hooks/` — eight wired guard hooks, each written after
its failure mode was observed in a real transcript, each carrying its diagnosis
in a docstring, covered by nine test modules. Nothing about that is
machine-specific, and nothing about it requires cloning a personal config repo
to benefit from.

Today the only way to get those hooks is `git clone ~/claudebase &&
installer/install.sh`, which also drags in one person's settings baseline,
plugin selection, tmux config, and secrets scaffolding. That is the wrong unit
of distribution. A plugin would let the guards be adopted à la carte, by a
lab machine or another person, without inheriting the rest.

Two things were considered and rejected as the answer to the same itch:

- **An MCP server.** Wrong layer. MCP supplies tools the model calls at
  runtime; hooks are lifecycle interception the *harness* runs, and CLAUDE.md /
  settings.json are files Claude Code reads from disk. An MCP server cannot
  inject any of them.
- **A curated plugin list.** Already exists — `config/settings.json`
  `enabledPlugins`, now documented with rationale in the README. Listing other
  people's plugins is not a product; the hooks are.

## What would be extracted

| Extracts cleanly | Notes |
|:---|:---|
| `runtime/hooks/*.py` (8 wired + 4 utilities) | Pure stdlib, no repo-specific imports observed |
| `tests/hooks/` (9 modules) | Ship with the plugin so adopters can verify |
| `runtime/skills/` (7 skills) | Possibly a *second* plugin — different audience from the guards |

| Stays behind | Why |
|:---|:---|
| `config/settings.json` | Personal plugin/permission baseline |
| `config/CLAUDE.md` | Personal operating rules |
| `secrets/`, `platform/`, `shell/` | Machine and person specific |
| `installer/` | A plugin install replaces it for this subset |

## Known blockers

1. **Absolute hook paths.** Hooks are wired into the rendered
   `~/.claude/settings.json` by absolute path under `~/claudebase/runtime/hooks/`.
   A plugin must express them relative to `${CLAUDE_PLUGIN_ROOT}`, and the
   installer's render step must keep working for the local (non-plugin) case
   so this machine does not end up running both copies.
2. **`installer/marketplace-metadata.json` is not this.** It records OS
   compatibility for marketplaces claudebase *consumes*. Publishing needs a new
   `.claude-plugin/marketplace.json` plus a per-plugin `plugin.json`.
3. **Dual identity.** The repo would be simultaneously a personal dotfiles
   store and a public distributable. Every future edit then needs the question
   "does this leak personal state into the published half?" — a standing tax,
   and the main argument for not doing it.
4. **Hook coverage gaps.** `session-title-3words.py` and `hud-ensure.sh` have
   no tests. `hud-ensure.sh` is also OMC-specific, so it likely does not belong
   in a general guards plugin at all.
5. **Settings-shrink guard interaction.** The pre-commit guard
   (`config/settings.critical.json`) protects the tracked baseline. How a
   plugin-installed hook set interacts with that manifest is unresolved.

## Rough shape if picked up

Two plugins rather than one, because the audiences differ:

- `claudebase-guards` — the hooks plus their tests. The thing worth publishing.
- `claudebase-skills` — the seven repo-owned skills. Lower value; several are
  personal (`invoice-organizer` is POSTECH settlement-specific) and would need
  triage before any of it is public.

Effort: days, not hours. Most of it is blocker 1 and blocker 3, not packaging.

## When to revisit

Any one of these makes it worth the cost:

- A second person or lab machine asks for the guards specifically.
- The hooks stabilize enough that they stop changing weekly.
- A failure mode recurs on a machine that does not have claudebase installed.

Absent one of those, the honest answer is that this serves one user and a git
clone already does that.

## Decision log

- **2026-07-27** — Evaluated against the alternative of leaving the repo as-is.
  Diagnosis was that the repo already *is* a hardened runtime (5,388 lines of
  Python, 8 wired hooks, 3 platforms, test suite) but the README presented it as
  an install guide: 133 of 258 lines were headroom proxy troubleshooting nested
  under "Quick start", while the hooks were not mentioned once. Chose to fix the
  framing first (README reframe + `docs/headroom.md` split) and defer packaging.
  Rationale: nobody installs a plugin they were never told the value of, so the
  README work is a prerequisite for this one regardless.

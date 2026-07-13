# Architecture

How `claudebase` keeps a Claude Code environment in sync across machines.

## What this is

`claudebase` is one person's Claude Code rig, stored as a git repo and projected into `~/.claude/` via symlinks. The promise: **fix or improve a setting on one machine, push, then `git pull` on every other machine to get it instantly** — no re-installs, no manual copies.

This file describes how that works. For day-to-day usage, see `README.md`.

## Directory layout

```
claudebase/
├── config/                   # symlinked into ~/.claude/
│   ├── settings.json         #   → ~/.claude/settings.json
│   ├── CLAUDE.md             #   → ~/.claude/CLAUDE.md  (universal behavioral rules)
│   └── mcp.template.json     #   rendered → ~/.claude/mcp.json
├── runtime/                  # things Claude loads at runtime
│   ├── skills/<name>/        # each symlinked → ~/.claude/skills/<name>/
│   ├── hooks/                # hook scripts referenced from settings.json
│   └── agents/               # user-scope subagents (currently empty; plugins provide most)
├── installer/
│   ├── install.sh            # macOS / Linux entrypoint
│   ├── install.ps1           # Windows entrypoint
│   └── scripts/              # helpers (hook merger, platform installers)
├── platform/
│   ├── macos/                # Homebrew formulae, casks, pip
│   ├── linux/                # apt / dnf / pip
│   └── windows/              # winget, pip
├── shell/
│   ├── tmux.conf             # → ~/.tmux.conf (Unix only)
│   └── claude-mouse.sh       # sourced from login rc (opt-in, Unix only)
├── secrets/
│   ├── secrets.example.env   # tracked sample
│   └── secrets.env           # **gitignored** — real API keys
├── templates/                # boilerplate for new project .claude/
├── docs/                     # ARCHITECTURE, CHANGELOG, CONTRIBUTING, specs/<topic>/{design,plan}.md
├── CLAUDE.md                 # repo-internal rules (not symlinked)
├── README.md
└── LICENSE
```

The split is by **purpose**, not by tool:
- `config/` — what Claude reads (user-scope behavior).
- `runtime/` — what Claude executes (skills, hooks).
- `installer/` — what the user runs once per machine.
- `docs/`, `platform/`, `shell/`, `secrets/`, `templates/` — orthogonal.

Specs follow a per-topic folder convention: each non-trivial change is paired as `docs/specs/<YYYY-MM-DD-topic>/design.md` + `plan.md`. The design captures decisions and trade-offs; the plan captures task breakdown and verification. Single-file specs (design only, no execution plan needed) keep the folder shape too — the absence of `plan.md` is meaningful.

## Symlink model

`installer/install.sh` and `installer/install.ps1` both resolve `REPO_DIR` to **one level above themselves** (`installer/../`), then create:

| Symlink | Target |
|:---|:---|
| `~/.claude/settings.json` | `<repo>/config/settings.json` |
| `~/.claude/CLAUDE.md` | `<repo>/config/CLAUDE.md` |
| `~/.claude/skills/<name>` | `<repo>/runtime/skills/<name>` (one symlink per skill — leaves other skills untouched) |
| `~/.tmux.conf` (Unix) | `<repo>/shell/tmux.conf` |

`~/.claude/mcp.json` is **rendered**, not symlinked — `installer/install.sh` substitutes `${VAR}` placeholders in `config/mcp.template.json` from `secrets/secrets.env` and writes the result. Re-render is idempotent: if the rendered content matches what's already on disk, the file is left alone.

`shell/claude-mouse.sh` is **sourced**, not symlinked — the opt-in `maybe_enable_claude_mouse` step (default No, or `INSTALL_CLAUDE_MOUSE=1`) appends one marker-guarded `source` line to the login shell's rc (`~/.zshrc` / `~/.bashrc`). It is the **only** place the installer writes into the user's rc; the `claudebase:claude-mouse` marker makes re-runs a no-op. See `lib/claude_mouse.sh` for why an rc-append (not a symlink or settings.json `env`) is the required mechanism.

The installer is **idempotent**: a second run prints zero `linked:` / `rendered:` lines. That's the contract — if you see actions on a second run, the installer has a bug.

## Plugin sync

Plugin code lives under `~/.claude/plugins/`, not in this repo. Tracking the binary blobs would fight the harness. Instead, `config/settings.json` declares two things:

- **`extraKnownMarketplaces`** — where to fetch plugins from (e.g., `claude-plugins-official`, `axlabs`, `heroacademia`).
- **`enabledPlugins`** — which plugins should be active on every machine.

After `git pull`, run `installer/install.sh` once. It scans `enabledPlugins`, checks which are installed at user scope, and installs the missing ones via `claude plugin install --user`. Existing plugins are left as-is.

Per-machine plugins go in `~/.claude/settings.local.json` (gitignored, see `templates/settings.local.example.json`). Claude Code merges `settings.local.json` on top of `settings.json` by key.

## Secrets

MCP server credentials are kept out of git:

1. `secrets/secrets.env` is gitignored. `secrets/secrets.example.env` is tracked as a stub.
2. `config/mcp.template.json` uses `${VAR}` placeholders.
3. `installer/install.sh` reads `secrets.env`, substitutes the placeholders, and writes `~/.claude/mcp.json`.

If you don't have an `secrets.env`, the installer renders the template verbatim (placeholders intact) and the corresponding MCP servers simply won't authenticate. There is no fallback to "track encrypted secrets in git" — out of scope.

## Python venv (document skills)

Document skills (`oh-my-docs`, `ppt-academic`) build with `python-pptx`,
`python-docx`, `python-hwpx`, `matplotlib`, `Pillow`. Because `python-hwpx`
requires Python ≥3.10 — newer than the system `/usr/bin/python3` (3.9) — and
Homebrew Python is PEP 668 externally-managed, `installer/install.sh`
(`platform/{macos,windows}/install.sh`) installs these into a dedicated venv
at `~/.claude/.venv`, built on the first of `python3.12/3.13/3.11/3.10`
found. The stage is idempotent: it skips silently when the venv exists and
every package imports.

The venv's `bin` (Windows: `Scripts`) is prepended to the session `PATH` via
the machine-local `~/.claude/settings.local.json` `env.PATH` (Claude Code
expands `$PATH` and prepends — verified against the settings docs). This is
how the **external** omd `doc-builder` and mckinsey `slide-agent` — which
invoke a bare `python3` and live outside this repo — resolve to the venv
interpreter with no edits to those plugins. PATH injection lives in
`settings.local.json`, not the shared `config/settings.json`, because the
venv path is a machine-specific absolute path (`~`/`$HOME` do not expand in
the `env` block) and shared files must stay machine-portable.

The venv is machine-local and not git-tracked (`.gitignore` ignores
`**/.venv/`); each machine rebuilds it on `installer/install.sh`.

Accepted risk: every `python3` in a Claude Code session resolves to the venv
(3.12). The stdlib-only internal callers (`installer/lib/omc.sh`,
`project_hooks.sh`, `plugin_sync.py`, `runtime/hooks/*.py`) run fine on 3.12.
A future internal script needing 3.9-specific behavior must call
`/usr/bin/python3` explicitly.

## Skills catalog

User-scope skills live under `runtime/skills/` and are auto-symlinked.

| Skill | Purpose | Trigger examples |
|:---|:---|:---|
| `changelog` | Record session decisions, experiments, lessons; commit the session changes | `/changelog` |
| `gen-image` | Generate one image with Google nano banana (Gemini 2.5 Flash Image) | "그려줘", "draw", "generate image" |
| `memory-update` | Compact and organize auto-memory files | `/memory-update` |
| `readme-project` | Generate a project README by analyzing the codebase | `/readme-project` |
| `sync-claudebase` | Sync this repo across machines (pull, drift-check, install, verify) | "settings sync", "plugin drift" |

Skills from plugins are loaded automatically by Claude Code from `~/.claude/plugins/`.

## Per-machine overrides

Three knobs for things that should not be shared across machines:

- **Plugins** — extra entries in `~/.claude/settings.local.json` `enabledPlugins`.
- **Permissions** — machine-specific tool allow/deny lists in `settings.local.json`.
- **HUD** — `omcHud` preset in `~/.claude/settings.json` (managed by `oh-my-claudecode`; switch via `/oh-my-claudecode:hud minimal|focused|full`).

`settings.local.json` follows the same JSON shape as `settings.json`. Anything you put there overrides the shared file for that machine only.

## Drift detection

`installer/install.sh` runs `git status --porcelain config/settings.json` at the end. Because `~/.claude/settings.json` is a symlink into the repo, Claude Code's auto-formatting / persistence writes straight through to the tracked file. If it drifts, you'll see:

```
[install] drift: config/settings.json modified by Claude CLI — review with: git -C <repo> diff config/settings.json
```

That's the cue to commit (or revert) Claude's changes. The installer never auto-stages or auto-reverts — it only flags.

### Settings-shrink guard

A *formatting* drift is harmless. A **shrink** is not: on certain events
(`/permissions` approval, plugin enable/disable, `/compact`, HUD preset change)
the Claude CLI re-serializes `settings.json` through its own schema and silently
**drops keys it doesn't recognize** — the custom `hooks` block (the defense
hooks), non-official plugins + their marketplaces, and `omcHud.layout.main`.
Because the file is symlinked into this repo, that loss lands as drift, and
without a guard it can be committed and pushed to every machine.

Three out-of-`settings.json` layers prevent silent loss (a guard *inside* the
`hooks` block would be deleted by the very shrink it detects — the
self-deletion trap):

1. **Enforcement — git pre-commit hook** (`installer/githooks/pre-commit`,
   deployed by `install.sh` via `git config core.hooksPath installer/githooks`).
   When `config/settings.json` is staged it runs `installer/lib/settings_verify.py`
   against the staged blob and **blocks the commit** if any critical key from
   `config/settings.critical.json` is missing. The CLI never runs git, so it can
   never rewrite this hook — a shrunk file is uncommittable (bypass only via the
   explicit `git commit --no-verify`).
2. **Safety net — `drift.sh`** runs the same validator against the working tree
   at the end of every install and escalates a shrink from a soft `drift:` note
   to a loud `CRITICAL: ... MISSING <keys>`.
3. **Recovery — `installer/bin/restore-settings.sh`** restores the file from
   `origin/main` (the cross-machine canonical) and re-verifies. Every guard's
   error message cites it.

The manifest `config/settings.critical.json` checks **named** plugin membership
(not a count — a count passes when the CLI swaps one plugin for another). When
you *intentionally* add or remove a critical key, update the manifest in the
same commit; never auto-bless. Full design:
`docs/specs/2026-06-01-settings-shrink-guard/`.

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
│   └── tmux.conf             # → ~/.tmux.conf (Unix only)
├── secrets/
│   ├── secrets.example.env   # tracked sample
│   └── secrets.env           # **gitignored** — real API keys
├── templates/                # boilerplate for new project .claude/
├── docs/                     # ARCHITECTURE, CHANGELOG, CONTRIBUTING, specs/
├── CLAUDE.md                 # repo-internal rules (not symlinked)
├── README.md
└── LICENSE
```

The split is by **purpose**, not by tool:
- `config/` — what Claude reads (user-scope behavior).
- `runtime/` — what Claude executes (skills, hooks).
- `installer/` — what the user runs once per machine.
- `docs/`, `platform/`, `shell/`, `secrets/`, `templates/` — orthogonal.

## Symlink model

`installer/install.sh` and `installer/install.ps1` both resolve `REPO_DIR` to **one level above themselves** (`installer/../`), then create:

| Symlink | Target |
|:---|:---|
| `~/.claude/settings.json` | `<repo>/config/settings.json` |
| `~/.claude/CLAUDE.md` | `<repo>/config/CLAUDE.md` |
| `~/.claude/skills/<name>` | `<repo>/runtime/skills/<name>` (one symlink per skill — leaves other skills untouched) |
| `~/.tmux.conf` (Unix) | `<repo>/shell/tmux.conf` |

`~/.claude/mcp.json` is **rendered**, not symlinked — `installer/install.sh` substitutes `${VAR}` placeholders in `config/mcp.template.json` from `secrets/secrets.env` and writes the result. Re-render is idempotent: if the rendered content matches what's already on disk, the file is left alone.

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

## Skills catalog

User-scope skills live under `runtime/skills/` and are auto-symlinked.

| Skill | Purpose | Trigger examples |
|:---|:---|:---|
| `changelog` | Record session decisions, experiments, lessons; commit the session changes | `/changelog` |
| `gen-image` | Generate one image with Google nano banana (Gemini 2.5 Flash Image) | "그려줘", "draw", "generate image" |
| `memory-update` | Compact and organize auto-memory files | `/memory-update` |
| `omc-teams-ops` | omc-teams launch / debug manual (sentinel, pane labels, monitor) | "omc team", "sentinel" |
| `readme-project` | Generate a project README by analyzing the codebase | `/readme-project` |
| `sync-claude-settings` | Sync this repo across machines (pull, drift-check, install, verify) | "settings sync", "plugin drift" |

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

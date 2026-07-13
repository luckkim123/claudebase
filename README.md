# claudebase

> Cross-machine Claude Code rig — settings, skills, hooks, plugins synced via git + symlinks.

Fix a setting on one machine, push, then `git pull` on every other machine to get it instantly. No re-installs, no manual copies.

## Quick start

```bash
# Clone to ~/claudebase (the canonical path; hooks/skills reference it)
git clone https://github.com/luckkim123/claudebase.git ~/claudebase
cd ~/claudebase

# Install
installer/install.sh                  # macOS / Linux
# pwsh installer/install.ps1          # Windows
```

That symlinks `~/.claude/settings.json`, `~/.claude/CLAUDE.md`, your skills and hooks into the repo. To update: `git pull`. No re-install needed.

### Installing tmux + clipboard tool

`tmux.conf`'s mouse-copy bindings need `tmux` and a clipboard helper. By
default the installer only warns if they're missing (keeps the install
idempotent and non-interactive). To have it install them for you:

```bash
INSTALL_TOOLS=1 installer/install.sh
```

This is best-effort and OS-aware — already-present tools are skipped, and it
never blocks on a sudo password prompt (falls back to a warn-only hint
instead):

| OS | Package manager | tmux | Clipboard |
|:---|:---|:---|:---|
| macOS | Homebrew | `brew install tmux` | built-in (`pbcopy`/`pbpaste`, nothing to install) |
| Linux (Debian/Ubuntu) | apt | `apt-get install -y tmux` | `wl-clipboard` (Wayland) or `xclip` (X11), picked by `$WAYLAND_DISPLAY` |
| Linux (Fedora/RHEL) | dnf | `dnf install -y tmux` | same as above |
| Linux (Arch) | pacman | `pacman -S --noconfirm tmux` | same as above |

Without `INSTALL_TOOLS=1`, a missing tool just prints the manual install
command for your platform instead.

### Native drag-select in the terminal (opt-in)

Claude Code's TUI captures mouse events, which breaks native / tmux
drag-to-select (the selection gets "stuck" at the visible screen edge). The
installer can wrap the `claude` command so it launches with mouse capture
disabled, restoring terminal selection:

```bash
INSTALL_CLAUDE_MOUSE=1 installer/install.sh   # non-interactive
# or just run installer/install.sh and answer [y/N] at the prompt
```

On yes it appends one marked `source shell/claude-mouse.sh` line to your login
shell's rc (`~/.zshrc` / `~/.bashrc`) — the only place claudebase writes to your
rc, marker-guarded so re-runs are a no-op. **Tradeoff**: mouse-off also disables
in-TUI mouse clicks/scroll (use the keyboard / tmux copy-mode). Revert by
deleting the `claudebase:claude-mouse` line. Windows: documented no-op (Unix /
tmux concern).

## MCP servers with API keys

```bash
cp secrets/secrets.example.env secrets/secrets.env
$EDITOR secrets/secrets.env
installer/install.sh                  # re-render mcp.json
```

`secrets/secrets.env` is gitignored.

## Document-skill Python dependencies

The `oh-my-docs` (omd) and `ppt-academic` skills build documents with Python
libraries: `python-pptx`, `python-docx`, `python-hwpx`, `matplotlib`,
`Pillow`. `installer/install.sh` installs these into a dedicated virtual
environment at `~/.claude/.venv` built on Python ≥3.10 (required by
`python-hwpx`; the system `python3` may be older, and Homebrew Python is PEP
668 externally-managed). Prepend the venv's `bin` to the session `PATH` so
the skills' bare `python3` calls resolve to it:

```jsonc
// ~/.claude/settings.local.json  (machine-local, gitignored)
{ "env": { "PATH": "/Users/<you>/.claude/.venv/bin:$PATH" } }
```

The venv is machine-local (not git-synced) — re-running `installer/install.sh`
recreates it.

## Per-machine overrides

Put machine-specific plugins / permissions / model choice (e.g. `"model": "opus[1m]"`) in `~/.claude/settings.local.json` (gitignored). Claude Code merges it on top of `config/settings.json`. See `templates/settings.local.example.json`.

## Learn more

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — directory layout, symlink model, plugin sync, secrets, drift detection
- [docs/CHANGELOG.md](docs/CHANGELOG.md) — what changed and when
- [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) — fork / PR guide
- [CLAUDE.md](CLAUDE.md) — repo-internal rules

## License

[MIT](LICENSE).

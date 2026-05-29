# claudebase

> Cross-machine Claude Code rig — settings, skills, hooks, plugins synced via git + symlinks.

Fix a setting on one machine, push, then `git pull` on every other machine to get it instantly. No re-installs, no manual copies.

## Quick start

```bash
# Clone (anywhere; ~/claudebase or ~/claude-settings both fine)
git clone https://github.com/luckkim123/claudebase.git ~/claudebase
cd ~/claudebase

# Install
installer/install.sh                  # macOS / Linux
# pwsh installer/install.ps1          # Windows
```

That symlinks `~/.claude/settings.json`, `~/.claude/CLAUDE.md`, your skills and hooks into the repo. To update: `git pull`. No re-install needed.

## MCP servers with API keys

```bash
cp secrets/secrets.example.env secrets/secrets.env
$EDITOR secrets/secrets.env
installer/install.sh                  # re-render mcp.json
```

`secrets/secrets.env` is gitignored.

## Per-machine overrides

Put machine-specific plugins / permissions in `~/.claude/settings.local.json` (gitignored). Claude Code merges it on top of `config/settings.json`. See `templates/settings.local.example.json`.

## Learn more

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — directory layout, symlink model, plugin sync, secrets, drift detection
- [docs/CHANGELOG.md](docs/CHANGELOG.md) — what changed and when
- [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) — fork / PR guide
- [CLAUDE.md](CLAUDE.md) — repo-internal rules

## License

[MIT](LICENSE).

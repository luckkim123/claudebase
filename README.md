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

Put machine-specific plugins / permissions in `~/.claude/settings.local.json` (gitignored). Claude Code merges it on top of `config/settings.json`. See `templates/settings.local.example.json`.

## Output style (opt-in)

출력 형식을 *코드로* 강제하는 hook 2개(매 턴 baseline 주입 + 필러/아첨 오프너 검출). 기본 **off**.
Claude Code 는 settings 의 `env` 를 hook 에 주입하지 않으므로, hook 이 셸 export 와 settings 파일을 직접
읽는다. 켜는 법(택1, 다음 세션부터 적용):

```jsonc
// 이 머신만 — ~/.claude/settings.local.json (gitignored)
{ "env": { "CLAUDEBASE_OUTPUT_STYLE": "enforce" } }   // nudge = 주입만, enforce = 주입+block
```
```bash
# 또는 셸에 export (zsh/bash)
export CLAUDEBASE_OUTPUT_STYLE=enforce
```

결론 먼저·산문 우선·비교는 표·간결 단정형·불확실성은 지식경계 명시 + CJK 안 깨지는 박스(`box.py`).
근거·설계·명세: [`docs/specs/2026-06-01-output-style-enforcement/`](docs/specs/2026-06-01-output-style-enforcement/) ·
[`runtime/output-style/concise-structured.md`](runtime/output-style/concise-structured.md).

## Learn more

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — directory layout, symlink model, plugin sync, secrets, drift detection
- [docs/CHANGELOG.md](docs/CHANGELOG.md) — what changed and when
- [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) — fork / PR guide
- [CLAUDE.md](CLAUDE.md) — repo-internal rules

## License

[MIT](LICENSE).

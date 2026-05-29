# Contributing

This is one person's Claude Code rig — but you're welcome to fork it, steal pieces, or send a PR if something here is wrong.

## Fork-friendly use

If you want your own setup based on this:

```bash
# 1. Fork on GitHub, then:
git clone https://github.com/<your-handle>/claudebase.git ~/claudebase
cd ~/claudebase

# 2. Make it yours: swap copyright in LICENSE, edit config/CLAUDE.md to your style,
#    drop skills you don't want from runtime/skills/, etc.

# 3. Install
installer/install.sh
```

You don't need permission. The MIT license covers reuse.

## PR criteria (if you do send one)

- **Idempotent installer.** A second `installer/install.sh` run must print zero `linked:` / `rendered:` lines.
- **Surgical.** One concern per PR. Don't bundle a skill rewrite with a structural refactor.
- **Verified.** State which machines you tested on (`ksm-mac`, `ubuntu`, `windows`, etc.) and that two consecutive `installer/install.sh` runs were clean.
- **No machine-specific paths.** Use `$REPO_DIR`, `$CLAUDE_HOME`, `~/.claude/`. Never hardcode `/Users/<name>/`.
- **No secrets.** Don't commit anything that looks like an API key, OAuth token, or personal email. `secrets/secrets.env` is gitignored — keep it that way.

## Commit conventions

Conventional commits with a `<type>(<scope>): <subject>` shape. Types in use:
- `feat` — new behavior (skill, hook, installer step)
- `refactor` — structural change, no behavior change
- `docs` — README, CHANGELOG, ARCHITECTURE
- `chore` — drift fixes, .gitignore tweaks, dead-code removal
- `fix` — bug fix

Multi-stage refactors get a branch + tag (see `docs/CHANGELOG.md` for the claudebase-standardize example).

## Don'ts

- Don't add a "convenient" `git add -A` to the installer. Stays surgical.
- Don't introduce a config file format that's not JSON or shell. Claude Code reads JSON; bash reads env.
- Don't bring back the `install.sh` backup logic. The idempotency contract makes it dead weight.
- Don't reach into `~/.claude/plugins/` directly. Plugin code is fetched from marketplaces; don't track binary blobs.

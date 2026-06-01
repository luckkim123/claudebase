# claudebase — repo-internal rules

This file is read by Claude Code when working *inside* this repo. Sets the rules of engagement for editing the config that drives Claude Code itself across all my machines.

## Audience

Me, six months from now, asking why the install script behaves a certain way. Or another machine, when the answer to "why is X like that?" can't be derived from the file alone.

## Source of truth

- The repo is the source of truth for **common** Claude Code config across machines.
- Per-machine specifics live in `~/.claude/settings.local.json` (gitignored). Never put them in `claude/settings.json`.
- Real API keys live only in `secrets/secrets.env` (gitignored). Never in `mcp.template.json`, never in commits.

## Commit conventions

- Conventional commits: `feat(scope): ...`, `fix(scope): ...`, `docs(scope): ...`.
- Scopes: `tmux`, `settings`, `install`, `readme`, `templates`, `mcp`.
- One concern per commit. Future-me uses `git blame` to learn why a line exists.

## Push policy

- Push to `origin/main` only on explicit instruction. Local commits are fine to make autonomously after edits.
- Force-push to `main` is never automatic.

## Editing rules

1. Editing `claude/settings.json` affects every machine on next `git pull`. Ask: is this truly common, or per-machine?
2. Editing `shell/tmux.conf` reloads automatically only on machines that re-source. Document non-trivial changes inline.
3. `install.sh` and `install.ps1` should stay behaviorally equivalent. If you change one, change the other.
4. Any new file under `claude/`, `shell/`, or new directory under `skills/` needs a corresponding `link_or_copy` line in both installers and a row in the README "What lives where" table. (For `skills/`, the installer iterates subdirectories — adding a new skill folder is sufficient, no installer edit needed.)
5. Idempotency is non-negotiable: `./install.sh` re-run on an already-installed machine must be a no-op (no backups, no churn). Verify after any installer change with `./install.sh && ./install.sh` — the second run should print no `linking` / `creating` lines.
6. **Settings-shrink guard.** `config/settings.json` is symlinked into `~/.claude/`, so the Claude CLI re-serializes it on `/permissions`, plugin toggle, `/compact`, or HUD change and silently **drops** the custom `hooks` block, non-official plugins, and `omcHud.layout.main`. A git pre-commit hook (`installer/githooks/pre-commit` + `config/settings.critical.json` manifest, deployed via `core.hooksPath`) blocks committing a shrunk file. **After any of those four trigger events, verify before trusting the file**: `installer/lib/settings_verify.py config/settings.json` (or just `git diff config/settings.json`); restore with `installer/bin/restore-settings.sh`. When you *intentionally* add/remove a critical key, update `config/settings.critical.json` in the same commit — that is the only correct way past the guard (never `--no-verify` to bury a real shrink). See `docs/ARCHITECTURE.md` → "Settings-shrink guard".

## Plugin reconciliation

- Common = plugins enabled on **every** machine I use.
- If only one machine needs it, it goes in that machine's `settings.local.json`.
- Do not preemptively promote a plugin to common just because it seems useful — wait until a second machine adopts it.

## Secrets

- `secrets/secrets.env` — gitignored, holds real values.
- `secrets/secrets.example.env` — committed, lists names only with placeholder/comment.
- New secret? Add to both, then reference in `mcp.template.json` as `${VAR_NAME}`.

## Don'ts

- Do not commit `~/.claude/settings.local.json` paths or contents into the repo.
- Do not bake machine-specific paths (e.g. `/Users/luckkim123/...`) into shared files.
- Do not amend or force-push commits that are already on `origin/main`.
- Do not add hooks that depend on tools not present on every target machine without OS gating in `platform/<os>/`.

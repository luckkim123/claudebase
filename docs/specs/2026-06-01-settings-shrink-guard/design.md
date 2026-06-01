# Settings-shrink guard — design

**Date:** 2026-06-01
**Status:** implemented + verified

## Problem

`~/.claude/settings.json` is a symlink into git-tracked `config/settings.json`.
On `/permissions` approval, plugin enable/disable, `/compact`, or HUD preset
change, the Claude Code CLI re-serializes `settings.json` through its own schema
and **silently drops keys it does not recognize**: the custom `hooks` block (4
defense hooks), non-official plugins + their marketplaces (omx, heroacademia
family), `omcHud.layout.main`, and several scalars. Because the file is a
symlink, the shrink writes straight into the tracked repo file as drift, and —
absent a guard — can be committed and pushed to every machine.

Observed 2026-06-01: the live file lost all 4 hook markers, 4 plugins, the rich
HUD layout, and 3 scalars. Caught only because the user noticed the HUD looked
different from their main machine. Nothing alerted automatically. The shrink had
NOT been committed (luck), so origin was intact.

## Root cause

CLI round-trip is lossy for unknown keys + symlink routes the loss into the repo.
The **self-deletion trap**: any detector registered inside `settings.json`'s own
`hooks` block is deleted by the very shrink it is meant to catch. Therefore every
guard must live **outside** `settings.json`.

## Design — 4 out-of-settings layers (1 enforces, 3 reinforce)

| Layer | File | Role |
|:---|:---|:---|
| **Enforcement** | `installer/githooks/pre-commit` | Blocks committing a staged `config/settings.json` missing any critical key. The CLI never runs git → can't rewrite this guard → shrunk file is uncommittable. |
| **Shared truth** | `config/settings.critical.json` + `installer/lib/settings_verify.py` | One manifest + one validator used by both the hook and drift.sh. Manifest checks **named** plugin membership (not a count — a count passes on plugin substitution). |
| **Safety net** | `installer/lib/drift.sh` (upgraded) | Runs the validator against the working tree at end of install; escalates a shrink from soft `drift:` to loud `CRITICAL: MISSING <keys>`. Net only — fires on manual install, not in real time. |
| **Recovery + reinforcement** | `installer/bin/restore-settings.sh` + CLAUDE.md / ARCHITECTURE.md notes | Restore from `origin/main` and re-verify; the command every error message cites. Behavioral rule documents the 4 trigger events as integrity hazards. |

Deployment: `install.sh` sets `git config core.hooksPath installer/githooks` (a
**tracked** dir — survives clone, unlike `.git/hooks`). Without this the guard is
silently absent on fresh machines.

## Rejected

- **SessionStart/PreCompact restorer hook inside settings.json** — self-deletes
  with the shrink it detects. Fatal. Standalone `restore-settings.sh` instead.
- **`enabledPlugins` count check** — passes when the CLI swaps one plugin for
  another (the exact silent substitution this guard exists to stop). Membership
  by name only.
- **`.git/hooks` alone** (untracked, per-clone) — guard absent on fresh clones.
- **Auto-`--bless` re-baseline in drift.sh** — would quietly canonicalize a
  shrunk file. Manifest updates are deliberate, in the same commit.

## Verification (all measured 2026-06-01)

- Validator: canonical `settings.json` → exit 0; shrunk (hooks + 1 plugin + HUD
  main + scalar removed) → exit 1, lists all 8 missing keys.
- E2E: stage a shrunk file + `git commit` → **BLOCKED** by pre-commit, HEAD
  unchanged (`f4775bc`), no test commit created.
- `restore-settings.sh`: shrink → restore from origin/main → re-verify OK.
- `drift.sh`: does not false-CRITICAL on the canonical file.
- `install.sh`: deploys hooksPath on fresh state, no-op on re-run; smoke
  idempotency test PASS.

## Files

Created: `config/settings.critical.json`, `installer/lib/settings_verify.py`,
`installer/githooks/pre-commit`, `installer/bin/restore-settings.sh`.
Modified: `installer/lib/drift.sh`, `installer/install.sh`,
`docs/ARCHITECTURE.md`, `CLAUDE.md` (repo-internal).

Behavioral rule placed in repo-internal `CLAUDE.md` (NOT user-scope
`config/CLAUDE.md`) — the guard is claudebase-specific; leaking it into the
distributed user-scope file would pollute unrelated projects.

# Design: Dedicated Python venv for document-skill dependencies

**Date**: 2026-06-01
**Status**: Approved (brainstorming complete)
**Topic**: `python-venv-isolation`

## Problem

claudebase's `platform/macos/install.sh` installs pip packages against the
PATH `python3`, which on the primary Mac resolves to the OS-bundled
`/usr/bin/python3` = **Python 3.9.6**. The `oh-my-docs` (omd) skill family
needs `python-hwpx` for Korean HWPX documents, and **every** released
`python-hwpx` version declares `requires-python >=3.10` — so it cannot be
installed on 3.9 at all (`pip install python-hwpx` → "No matching
distribution found"). The machine has Homebrew `python3.12` (3.12.11), but it
is PEP 668 "externally-managed", so a bare `pip install` into it is refused.

Net effect: omd's docx/hwpx build path silently falls back to manual ZIP
parsing because its engine dependencies aren't installable where the
consumers look for them.

## Goal

Install the document-skill Python dependencies into a **dedicated, isolated
virtual environment** built on Python ≥3.10, and make the **consumers**
(omd `doc-builder`, mckinsey `slide-agent`) pick up that venv's interpreter
**without modifying those external plugins** — by putting the venv's `bin/`
at the front of the session PATH via claudebase's own `config/settings.json`.

Non-goal: changing the system Python, touching the OS interpreter, or
modifying external plugin repos.

## Key facts (from investigation)

- pip install sites: **`platform/macos/install.sh` and
  `platform/windows/install.ps1` only**. `platform/linux/install.sh` has no
  pip section (`REQUIRED_PKGS=(tmux)`).
- Consumers call the interpreter as **bare `python3` (PATH-dependent)**:
  `oh-my-docs/agents/doc-builder.md:46`,
  `mckinsey-slide-agent.md:38,136`. Neither uses `sys.executable`, a fixed
  path, or an env var. Both live in the external plugin cache — claudebase
  cannot edit them.
- claudebase-internal `python3` calls (6 sites: `installer/lib/omc.sh`,
  `project_hooks.sh`, `installer/scripts/*.sh`, `plugin_sync.py`, the
  `runtime/hooks/*.py`) are **stdlib-only** — they run fine on any Python
  ≥3.9, so promoting the session PATH to 3.12 does not break them.
- `.gitignore` already ignores `**/.venv/` — no new gitignore work.
- `tests/smoke/test_install_idempotent.sh` FAILS if a 2nd install pass emits
  an `installing`-class line. The new venv logic must skip silently when the
  venv exists and packages are present.
- `config/settings.json` already has an `env` block (currently one entry,
  `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`).

## Design decisions

1. **venv location** → `~/.claude/.venv`.
   Consistent with the `$CLAUDE_HOME` pattern already used by `omc.sh` /
   `project_hooks.sh`. Outside the repo (machine-local; a venv is binaries,
   correctly rebuilt per machine rather than git-synced). Keeps runtime
   binaries out of the text-config repo.

2. **Base interpreter** → probe `python3.12 → python3.13 → python3.11 →
   python3.10`, use the first found. If none ≥3.10 exists, emit a hint
   (`brew install python@3.12`) and skip the venv stage fail-soft — same
   posture as the existing LibreOffice/gh hints. Never fall back to 3.9
   (hwpx would fail).

3. **Packages in the venv** →
   `python-pptx python-docx python-hwpx matplotlib Pillow`.
   The full omd docx/hwpx engine set (omd README install line). matplotlib +
   Pillow back omd's equation-PNG and image paths. Inside the venv, PEP 668
   does not apply.

4. **Idempotency** → if `~/.claude/.venv` exists and each package imports in
   it, print `pip packages already present (skip): …` and do nothing.
   Import-probe uses the venv's own interpreter
   (`~/.claude/.venv/bin/python -c "import <x>"`), with the
   `python-<x>`→`<x>` name rule (python-pptx→pptx, python-docx→docx,
   python-hwpx→hwpx). matplotlib→matplotlib; Pillow→PIL (explicit mapping,
   since the `python-` strip rule does not apply to Pillow).

5. **PATH injection** → add the venv bin dir to the front of `env.PATH` in
   the **machine-local `~/.claude/settings.local.json`** (gitignored), NOT
   the shared `config/settings.json`. Rationale: the venv path is a
   machine-specific absolute path (`/Users/<user>/.claude/.venv/bin`; `~`/
   `$HOME` do not expand in the settings `env` block), and CLAUDE.md:49
   forbids baking machine-specific paths into shared files. Since the venv is
   itself machine-local, its PATH entry belongs in the machine-local settings
   file. Claude Code merges `settings.local.json` over `config/settings.json`,
   so this still reaches the session env that the consumers' bare `python3`
   sees. (Revised from the original "shared settings.json" decision during
   plan self-review — see plan Task 3.)

6. **Windows mirroring** → `install.ps1` builds the venv with
   `py -3.12 -m venv` and probes `<venv>\Scripts\python.exe` (vs macOS
   `<venv>/bin/python`). PATH injection rides the same `settings.json`
   mechanism (Windows venv `Scripts` dir prepended on Windows). CLAUDE.md
   "behaviorally equivalent" rule.

7. **linux** → no change. No pip section exists today; adding one is out of
   scope (surgical). Revisit on explicit request.

8. **Documentation** → update `README.md` (dependency / MCP-adjacent section)
   and `docs/ARCHITECTURE.md` to describe the venv strategy and the
   PATH-injection mechanism that links it to document skills.

## Components touched

| File | Change |
|---|---|
| `platform/macos/install.sh` | Replace the `--user` pip stage with: probe interpreter → create `~/.claude/.venv` if absent → pip-install missing packages into venv → silent-skip when present |
| `platform/windows/install.ps1` | Mirror: `py -3.12 -m venv`, `Scripts\python.exe` probe, same package list |
| `~/.claude/settings.local.json` (machine-local, gitignored) | Prepend venv `bin`/`Scripts` to `env.PATH` (NOT shared settings.json — see decision 5) |
| `README.md` | Document venv + the docx/hwpx/pptx dependency set |
| `docs/ARCHITECTURE.md` | Document venv location, base-interpreter probe, PATH-injection link to consumers |

## Data flow

```
install.sh
  └─ probe python3.12/.13/.11/.10  ──(none ≥3.10)──> hint + skip (fail-soft)
        │ found
        ▼
     python3.X -m venv ~/.claude/.venv     (skip if exists)
        ▼
     ~/.claude/.venv/bin/pip install <missing of pptx,docx,hwpx,matplotlib,Pillow>
        ▼  (probe each via venv python; skip silently if all present)
~/.claude/settings.local.json  env.PATH = "<abs venv bin>:${PATH}"  (machine-local)
        ▼
Claude Code session  →  omd doc-builder / mckinsey slide-agent
        ▼  bare `python3`  resolves to  ~/.claude/.venv/bin/python (3.12)
     import pptx / docx / hwpx  ✓
```

## Error handling

- No interpreter ≥3.10 → hint + skip (fail-soft, exit 0; parent install
  under `set -e` keeps going).
- venv creation fails → WARNING + skip pip stage (don't abort the whole
  install).
- A package fails to install → WARNING per package, continue (mirrors the
  current per-package WARNING posture).
- PEP 668 cannot occur inside a venv (that is the point).

## Testing / verification

- `tests/smoke/test_install_idempotent.sh` must still pass: 2nd install pass
  prints `pip packages already present (skip)` with no `installing` line.
- After install: `~/.claude/.venv/bin/python -c "import pptx, docx, hwpx"`
  succeeds; `~/.claude/.venv/bin/python --version` ≥ 3.10.
- PATH check: inside a session, `python3 -c "import hwpx"` succeeds (proves
  injection reaches a bare `python3`).
- No regression in the 6 stdlib-only internal `python3` callers.

## Open risk (accepted)

PATH injection makes **every** `python3` in the session resolve to the venv
3.12. Investigation confirmed the 6 internal callers are stdlib-only and run
on 3.12, so this is safe. If a future internal script needs a 3.9-only
behavior, it must call `/usr/bin/python3` explicitly — noted in
ARCHITECTURE.md.

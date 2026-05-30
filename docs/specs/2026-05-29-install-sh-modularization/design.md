# install.sh modularization (P3 input)

**Filed**: 2026-05-29
**Source phase**: P1 G4.5 (handoff)
**Target phase**: P3 (installer / platform 고도화)
**Pair**: `plan.md` to be written when P3 starts.

## Why this design exists

`installer/install.sh` is the single mutable surface the user runs on every machine. After P1 it sits at **405 LOC** in one file, mixing nine numbered stages with five top-level functions and embedded JSON parsing logic. Two consequences:

1. **Cognitive cost grows with every stage**: adding stage 10 means scrolling past nine others to find where to wire it.
2. **Test surface is shell-shaped, not Python-shaped**: bash functions are hard to unit-test. P1 already moved the largest decision-heavy piece (`sync_plugins`) into `installer/scripts/plugin_sync.py`. The same lift is achievable for the remaining bash-only pieces, but only if the file is first split by concern.

P3 starts here. This document fixes the module boundary so P3 does not redo the analysis.

## Current shape (post-P1, install.sh @ 405 LOC)

| Lines | Block | Concern |
|---|---|---|
| 1-27 | shebang, arg parsing, OS detection | top-level wiring |
| 38-73 | `check_runtime_deps()` | dependency probe |
| 75-87 | `log()`, `debug()`, `run()` | utility logging |
| 89-120 | `remove_if_exists()`, `already_linked()`, `link_or_copy()` | filesystem linking |
| 122-129 | symlink settings.json, CLAUDE.md | linking caller |
| 131-175 | mcp.json template render | secret substitution |
| 177-200 | tmux.conf, skills, agents symlink | linking callers |
| 202-252 | platform installer + project-hook deploy | OS dispatch + per-project merge |
| 254-274 | `sync_plugins()` (thin wrapper to plugin_sync.py) | plugin sync |
| 276-318 | `patch_omc_bash_freeze()` | OMC freeze workaround |
| 326-391 | `install_omc_hud()` | OMC HUD wrapper installer |
| 393-405 | drift check, footer | post-install diagnostics |

## Target shape

Split into `installer/install.sh` (orchestrator) + `installer/lib/*.sh` (concern modules) + reused Python scripts.

### Orchestrator — `installer/install.sh` (~120 LOC target)

```bash
#!/usr/bin/env bash
set -euo pipefail
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Parse args, detect platform.
source "$REPO_DIR/installer/lib/args.sh"
parse_args "$@"
detect_platform                              # exports $PLATFORM

# Load shared utilities once.
source "$REPO_DIR/installer/lib/log.sh"
source "$REPO_DIR/installer/lib/link.sh"

# Stage 0: optional dependency probe (warn-only).
source "$REPO_DIR/installer/lib/deps.sh"
check_runtime_deps

# Stage 1-2: filesystem links.
mkdir -p "$CLAUDE_HOME"
link_settings_and_md                          # link.sh function

# Stage 3: secrets render.
source "$REPO_DIR/installer/lib/secrets.sh"
render_mcp_json

# Stage 4: skills, agents, tmux.
link_skills_and_agents
link_tmux_conf

# Stage 5: platform.
source "$REPO_DIR/installer/lib/platform.sh"
run_platform_installer

# Stage 5b: project hooks.
source "$REPO_DIR/installer/lib/project_hooks.sh"
deploy_project_hooks

# Stage 6: plugin sync (Python delegation).
source "$REPO_DIR/installer/lib/plugins.sh"
sync_plugins

# Stage 6.5/8: OMC patches.
source "$REPO_DIR/installer/lib/omc.sh"
patch_omc_bash_freeze
install_omc_hud

# Stage 9: drift check + footer.
source "$REPO_DIR/installer/lib/drift.sh"
check_settings_drift
log "done."
```

### lib/ modules

| File | Responsibility | Source lines (current) | LOC target |
|---|---|---|---|
| `lib/args.sh` | Arg parsing, platform detection, env constants (`CLAUDE_HOME`, `DRY_RUN`, `COPY_MODE`, `VERBOSE`, `PRUNE_PLUGINS`) | 12-36 | ~40 |
| `lib/log.sh` | `log`, `debug`, `run` | 75-87 | ~20 |
| `lib/link.sh` | `remove_if_exists`, `already_linked`, `link_or_copy`, `link_settings_and_md`, `link_skills_and_agents`, `link_tmux_conf` | 89-200 | ~80 |
| `lib/deps.sh` | `check_runtime_deps` (jq, gemini, nano banana) | 38-73 | ~40 |
| `lib/secrets.sh` | `render_mcp_json` (secrets.env parser, idempotent rewrite) | 131-175 | ~50 |
| `lib/platform.sh` | `run_platform_installer` (dispatch to platform/<os>/install.sh) | 202-208 | ~15 |
| `lib/project_hooks.sh` | `deploy_project_hooks` (PROJECT_TARGETS loop + merge-project-hook.py invoke) | 210-252 | ~50 |
| `lib/plugins.sh` | `sync_plugins` (thin wrapper around `plugin_sync.py`) | 254-274 | ~20 |
| `lib/omc.sh` | `patch_omc_bash_freeze` (Python in P3 — see note), `install_omc_hud` | 276-391 | ~80 |
| `lib/drift.sh` | `check_settings_drift` | 393-405 | ~15 |

Total `lib/` ~410 LOC + orchestrator ~120 LOC = ~530 LOC of bash, **vs the current 405 LOC** — net growth ~30%. The trade is **boundaries**: every function lives next to its peers, every concern is one file, and every file is independently `shellcheck`-able.

### Note: `patch_omc_bash_freeze` already extracted in P1 G4.1

`installer/scripts/patch_omc_freeze.sh` exists post-G4.1. `lib/omc.sh` should just invoke it, not duplicate the body:

```bash
patch_omc_bash_freeze() {
  bash "$REPO_DIR/installer/scripts/patch_omc_freeze.sh" 2>&1 \
    | while IFS= read -r line; do log "$line"; done
}
```

## Constraints P3 must respect

1. **Idempotency contract**: `installer/install.sh && installer/install.sh` = 0 actions. The smoke test (`tests/smoke/test_install_idempotent.sh`) is the gate. P3 must keep it green after every commit.
2. **No new bash 4+ features without verification**: macOS ships bash 3.2 by default. The current install.sh already assumes `#!/usr/bin/env bash` finds a 4+ via Homebrew. P3 may rely on the same assumption but should document it in `lib/args.sh` header.
3. **One concern per file**: `lib/link.sh` may grow (it has the most linking callers) but must not absorb secrets, drift, or plugins logic.
4. **Source order matters**: `lib/log.sh` and `lib/args.sh` must be sourced before any other module. The orchestrator pins this order; modules cannot self-source each other.
5. **Don't regress `--dry-run` or `--verbose`**: every stage already honors these flags via `run()` and `debug()` from `lib/log.sh`.

## Out of scope for P3

- `installer/install.ps1` Windows mirror: still single-file. P3 can mirror the bash split into `installer/lib-ps1/` if desired, but that is its own decision.
- Translating `lib/secrets.sh` (the secrets.env parser) to Python: tempting because it would gain unit-testability, but the current bash parser is intentionally minimal (no shell expansion). Defer unless P3 finds a bug.
- Migrating `install_omc_hud` to Python: the cp+chmod is trivially bash. The G2.4 idempotency check (`cmp -s` on companion file) reads naturally in bash.

## P3 entry checklist

When P3 begins, the first session should:

1. Read this file end to end.
2. Read the **current** `installer/install.sh` (not the P1 snapshot — fix divergence first if any).
3. Cut a branch `p3-installer-modularization` from `main` (after P1 merges).
4. Run `installer/install.sh && installer/install.sh` and `tests/smoke/test_install_idempotent.sh` to capture baseline.
5. Create `installer/lib/` and start with `lib/log.sh` + `lib/link.sh` (smallest blast radius, every other module depends on them).
6. After each module extract: run smoke + pytest, atomic commit.

## Success criteria (for P3 closeout)

- [ ] `installer/install.sh` ≤ 130 LOC
- [ ] `installer/lib/*.sh` 9 files exist, each `shellcheck` clean
- [ ] `installer/install.sh && installer/install.sh` = 0 actions (smoke green)
- [ ] All P1 pytest still green (31+ tests)
- [ ] CI workflow's shellcheck step covers `installer/lib/*.sh` (extend ci.yml glob)

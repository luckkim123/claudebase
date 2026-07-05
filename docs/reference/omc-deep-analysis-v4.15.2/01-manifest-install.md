# Plugin Manifest, Packaging & Installation System

This section documents how oh-my-claudecode (OMC) v4.15.2 ships and installs: the Claude Code plugin manifest and everything it registers, the npm package that carries the same payload under a different name, the TypeScript installer that reconciles a user's `~/.claude/` directory across three install modes (marketplace plugin, global npm, local dev fork), and the version/update machinery that keeps a live plugin cache, a marketplace git clone, and a global npm package from drifting apart. The dominant design theme is *dual-channel distribution with self-healing reconciliation*: every artifact can arrive via the plugin system or via npm, ownership of user-visible files is tracked with explicit markers, and every hook/entry point is written to fail open rather than block Claude Code.

## Dual identity: one payload, two channels

| Facet | Plugin channel | npm channel |
|---|---|---|
| Name | `oh-my-claudecode` (.claude-plugin/plugin.json:2) | `oh-my-claude-sisyphus` (package.json:2) |
| Version | `4.15.2` in both, kept in lockstep by `scripts/sync-version.sh` (package.json `"version"` script) |  |
| Install command | `/plugin install oh-my-claudecode` from marketplace `omc` | `npm i -g oh-my-claude-sisyphus@latest` then `omc setup` |
| Runtime root | `~/.claude/plugins/cache/omc/oh-my-claudecode/<version>/` (exposed as `$CLAUDE_PLUGIN_ROOT`) | `$(npm root -g)/oh-my-claude-sisyphus` |
| Marketplace descriptor | `.claude-plugin/marketplace.json` — marketplace name `"omc"`, single plugin entry with `"source": "./"` | n/a |

Both descriptors pin `4.15.2`; `scripts/sync-version.sh` (invoked by the npm `version` lifecycle hook, sync-version.sh:2-9) rewrites the version into `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` (both version fields, via a global `perl -i -pe`), and `docs/CLAUDE.md`'s `<!-- OMC:VERSION -->` marker from `package.json`, so a single `npm version <bump>` fans out to all three satellite files. The marketplace descriptor's marketing copy has drifted from reality, though: it advertises "28 agents, 32 skills" (marketplace.json:3) while the shipped payload has **19 agents** and **40 registered skills** — a redesign should treat these prose counts as unmaintained.

The npm package has **no `postinstall` script** (verified: `package.json.scripts.postinstall` is undefined); installing it does nothing until the user runs `omc setup` (a hidden `omc postinstall` CLI command exists for scripted silent installs, src/cli/index.ts:1369). This is deliberate: setup mutates `~/.claude/settings.json` and should be explicit.

## What the plugin manifest registers

`.claude-plugin/plugin.json` (whole file) declares:

| Key | Value | Effect at Claude Code startup |
|---|---|---|
| `skills` | array of exactly 40 skill dirs (`./skills/ai-slop-cleaner/` … `./skills/writer-memory/`), matching the 40 dirs on disk 1:1 (`skills/AGENTS.md` is a doc file, not a skill) | each `SKILL.md` becomes `/oh-my-claudecode:<name>` |
| `commands` | `"./commands/"` (28 `.md` files, e.g. `omc-setup.md`, `psm.md`) | slash-command shims |
| `mcpServers` | `"./.mcp.json"` | registers MCP server(s) below |
| (convention) | `agents/` (19 `.md` agents) and `hooks/hooks.json` are auto-discovered by directory convention, not declared in plugin.json | agents + lifecycle hooks |

`.mcp.json` (whole file) registers exactly one MCP server with the deliberately short name `t`:

```json
{ "mcpServers": { "t": { "command": "node",
    "args": ["${CLAUDE_PLUGIN_ROOT}/bridge/mcp-server.cjs"] } } }
```

`bridge/mcp-server.cjs` is a **committed esbuild bundle** (built by scripts/build-mcp-server.mjs → `outfile = 'bridge/mcp-server.cjs'`) so the plugin cache never needs a build step; its banner prepends `npm root -g` to `NODE_PATH` so externalized native deps like `@ast-grep/napi` resolve from the global npm tree (scripts/build-mcp-server.mjs:19-30).

`hooks/hooks.json` wires 11 hook events, every one routed through the same runner:

```
node "$CLAUDE_PLUGIN_ROOT"/scripts/run.cjs "$CLAUDE_PLUGIN_ROOT"/scripts/<hook>.mjs [args]
```

| Event | Scripts (timeout s) |
|---|---|
| UserPromptSubmit | keyword-detector (10), skill-injector (15) |
| SessionStart `*` | session-start (5), project-memory-session (5), wiki-session-start (5) |
| SessionStart `init` / `maintenance` | setup-init (30) / setup-maintenance (60) — matcher-scoped bootstrap/cleanup |
| PreToolUse | pre-tool-enforcer (3) |
| PermissionRequest `Bash` | permission-handler (5) |
| PostToolUse | post-tool-verifier, project-memory-posttool, post-tool-rules-injector (3 each) |
| PostToolUseFailure | post-tool-use-failure (3) |
| SubagentStart / SubagentStop | subagent-tracker start (3) / stop (5) + verify-deliverables (5) |
| PreCompact | pre-compact (10), project-memory-precompact (5), wiki-pre-compact (3) |
| Stop | context-guard-stop (5), workflow-drift-guard (3), persistent-mode (10), code-simplifier (5) |
| SessionEnd | session-end (30, `"async": true`), wiki-session-end (30, `"async": true`) |

The `SessionStart` matchers `init` and `maintenance` run `processSetupInit` / `processSetupMaintenance` (src/hooks/setup/index.ts:284, :466): init creates `.omc/` directory structure, heals the `stdin.mjs` symlink, and on Windows patches hooks.json to direct-node invocation; maintenance prunes state files older than the default age and 24h-orphaned session state — mode-state files (`autopilot-state.json`, `ralph-state.json`, `ultrawork-state.json`) are only pruned when `state.active !== true` (src/hooks/setup/index.ts:387-403).

### run.cjs — the fail-open hook runner

`scripts/run.cjs` (whole file) is the single most reusable artifact in this territory:

- Spawns the target `.mjs` with `process.execPath` (the already-running Node), so Windows never needs `/bin/sh` and nvm/fnm PATH problems vanish (fixes #909/#899/#892/#869).
- **Stale-root healing**: if `$CLAUDE_PLUGIN_ROOT` points at a deleted/replaced version dir, it realpath-resolves, then scans sibling `cacheBase` version dirs (semver-desc) for the same relative script and runs the newest match (`resolveTarget`, comment cites issue #1007).
- **Self-imposed timeout**: reads its own hooks.json entry, subtracts `TIMEOUT_CUSHION_MS = 500` and enforces the deadline itself (`killSignal: SIGKILL` on Unix), printing `"timed out after ...ms; exiting fail-open"`.
- Every failure path — missing arg, unresolvable target, child `status === null` — exits `0` so Claude Code hooks are *never* blocked.

## npm packaging and build pipeline

package.json facts (all verbatim):

- `bin`: `oh-my-claudecode` and `omc` → `bin/oh-my-claudecode.js` (a shebang + a single `import '../bridge/cli.cjs';` line), `omc-cli` → `bridge/cli.cjs` directly.
- `files` whitelist ships `dist`, `agents`, `bin`, `bridge` (plus explicit `bridge/mcp-server.cjs`, `bridge/team-bridge.cjs`, `bridge/team-mcp.cjs`, `bridge/team.js`, `bridge/cli.cjs`, `bridge/runtime-cli.cjs`), `commands`, `hooks`, `scripts`, `skills`, `templates`, `docs`, `.claude-plugin`, `.mcp.json`, `README.md`, `LICENSE` — i.e. the npm tarball *is* a complete plugin payload; `.npmignore` strips `src/`, `examples/`, `.claude/`, and all `*.ts` except `.d.ts` (`!*.d.ts`).
- `build` (verbatim) = `tsc && node scripts/build-skill-bridge.mjs && node scripts/build-mcp-server.mjs && node scripts/build-bridge-entry.mjs && npm run compose-docs && npm run build:runtime-cli && npm run build:team-server && npm run build:cli`: `tsc` compiles src → dist ESM, then six esbuild bundlers emit the committed `bridge/*.cjs` artifacts and `compose-docs` assembles `docs/`. `scripts/build-cli.mjs` bundles `src/cli/index.ts` → `bridge/cli.cjs`, so the CLI runs without node_modules resolution of OMC's own code. `prepublishOnly` re-runs `build` + `compose-docs` before every npm publish.
- `engines.node >= 20.0.0`, enforced again at install time via `MIN_NODE_VERSION = 20` (src/installer/hooks.ts:66, checked in `install()` at src/installer/index.ts:2018-2023).
- Bare `omc` with no subcommand forwards to `launchCommand` (tmux-integrated `claude` launcher; src/cli/index.ts:104-125), so the bin doubles as a launcher and an installer CLI.

Because published plugin caches lack `node_modules`, the legacy post-install script probes for `node_modules/commander` and runs `npm install --omit=dev --ignore-scripts` inside the plugin dir when missing (scripts/plugin-setup.mjs:150-168, fixes #1113). Note: in v4.15.2 `scripts/plugin-setup.mjs` is **not wired to any manifest or hook** — only tests and the release workflow reference it (grep across repo; .github/workflows/release.yml:36 even restores `hooks/hooks.json` because tests running plugin-setup mutate it). Treat it as a semi-vestigial "Path B" whose logic has migrated into the installer and the `hud` skill.

## Install modes and detection

```
                 +--------------------------------------------------------------+
                 |                    Where does payload live?                   |
                 +--------------------------------------------------------------+
 marketplace ->  ~/.claude/plugins/cache/omc/oh-my-claudecode/<ver>/   (CLAUDE_PLUGIN_ROOT set)
 npm global  ->  $(npm root -g)/oh-my-claude-sisyphus/                 (omc setup copies pieces)
 local dev   ->  <fork checkout>/  via `claude --plugin-dir` or `omc --plugin-dir`
                                                                (OMC_PLUGIN_ROOT env, src/cli/launch.ts:711)
```

| Mode | Detection | Installer behavior |
|---|---|---|
| Plugin runtime | `isRunningAsPlugin()` = `!!process.env.CLAUDE_PLUGIN_ROOT` (src/installer/index.ts:492-496) | skip agents/commands/hook-script copies; still install HUD + CLAUDE.md + settings |
| Project-scoped plugin | plugin root NOT under `<configDir>/plugins` (src/installer/index.ts:509-524) | skip **all** global mutations (HUD, settings.json, CLAUDE.md, version metadata) |
| Plugin installed but CLI running standalone | `hasPluginProvidedAgentFiles()` / `hasPluginProvidedSkillFiles()` / `hasPluginProvidedHookFiles()` — a plugin root passes only with a complete payload (`validatePluginSyncPayload`) | skip the corresponding standalone copies and *prune* duplicates (#2252) |
| Dev plugin-dir | `--plugin-dir-mode` flag or `OMC_PLUGIN_ROOT` env (src/cli/index.ts:1293-1299) | skip agent/skill copy; HUD/hooks/CLAUDE.md/`.omc-config.json` still installed; `--no-plugin` wins on conflict |
| Standalone npm only | none of the above | full copy into `~/.claude/` |

`hasEnabledOmcPlugin()` additionally reads `settings.json` `enabledPlugins` (modern) falling back to `plugins` (legacy), matching any key containing `oh-my-claudecode` with value `!== false` (src/installer/index.ts:1622-1663).

## The installer: `install()` end-to-end

`src/installer/index.ts` `install()` (1999-2443) is the one reconciliation function behind `omc install`, `omc setup`, `omc postinstall`, and `omc update-reconcile`. Ordered flow:

1. **Node version gate**, then **downgrade guard**: newest installed version is inferred from `~/.claude/.omc-version.json` or the `<!-- OMC:VERSION:x.y.z -->` marker in CLAUDE.md; if the CLI package is older, install is skipped with success (src/installer/index.ts:2028-2036).
2. **Plugin cache self-repair**: `syncInstalledPluginPayload()` finds every installed OMC plugin root from `CLAUDE_PLUGIN_ROOT` + `plugins/installed_plugins.json`, restricts targets to roots under `plugins/cache/`, picks the best complete source among marketplace clones (`plugins/known_marketplaces.json`), the global npm package, and the running package (`resolveBestPluginSyncSource`), and re-copies `PLUGIN_SYNC_PAYLOAD` = `dist, bridge, hooks, scripts, skills, agents, commands, templates, docs, .claude-plugin, .mcp.json, README.md, LICENSE, package.json` (src/installer/index.ts:1137-1152). A payload is "complete" only if `REQUIRED_PLUGIN_PAYLOAD_FILES` exist: `.claude-plugin/plugin.json`, `package.json`, `dist/hooks/skill-bridge.cjs`, `bridge/cli.cjs`, `hooks/hooks.json`, plus `commands/omc-setup.md` (1154-1164). Failure here is **loud**: install aborts with "OMC plugin cache is incomplete and could not be repaired" (2050-2054).
3. **Skill compaction**: after copying `skills/` into a cache target, `compactPluginSkillPayload()` archives each full skill into `skill-bodies/<name>/SKILL.md` and rewrites `skills/<name>/SKILL.md` as a shim marked `<!-- OMC:COMPACT-PLUGIN-SKILL -->` whose description is truncated to 240 chars and whose frontmatter records `omc-full-body: ../../skill-bodies/<name>/SKILL.md` (src/installer/index.ts:1441-1512). This keeps Claude Code's startup skill-description context small while preserving full bodies for on-demand reads.
4. **Agents**: standalone mode copies `agents/*.md` into `~/.claude/agents/`; plugin mode instead prunes standalone duplicates (`prunePluginDuplicateAgents`) and stale ones (`cleanupStaleAgents` — removes only files with OMC-style frontmatter no longer shipped).
5. **Commands**: never copied — `CORE_COMMANDS: string[] = []` with the comment "DISABLED for v3.0+ … plugin-scoped skills" (src/installer/index.ts:47-51).
6. **Skills (standalone)**: `syncBundledSkillDefinitions()` copies each skill dir, stamps a `.omc-managed` marker file in it (`OMC_MANAGED_SKILL_MARKER = '.omc-managed'`), and renames skills that collide with Claude Code native commands (`CC_NATIVE_COMMANDS` = review, plan, security-review, init, doctor, help, config, clear, compact, memory) to `omc-<name>` (src/installer/index.ts:58-69, 1772-1777). Three skills are gated to a specific user cohort: `SKININTHEGAMEBROS_ONLY_SKILLS = {remember, verify, debug}` install only when `isSkininthegamebrosUser()` (71-75, 1803). Later cleanup only ever deletes dirs bearing the marker or byte-identical to the plugin copy — "Frontmatter structure alone is not a reliable ownership signal" (1041-1055).
7. **Hook scripts (standalone only)**: copies `templates/hooks/*.mjs` (`keyword-detector, session-start, pre-tool-use, post-tool-use, post-tool-use-failure, persistent-mode, code-simplifier`) + `find-node.sh` + `scripts/lib/config-dir.{mjs,sh}` into `~/.claude/hooks/` (732-805). If an enabled plugin provides hooks, it instead *removes* these files — but only when their sha256 matches the shipped payload, so user-modified scripts survive (`pruneLegacyStandaloneHookScripts`, 529-583).
8. **CLAUDE.md merge**: backs up to `CLAUDE.md.backup.<timestamp>`, then `mergeClaudeMd()` rewrites the block between line-anchored `<!-- OMC:START -->` / `<!-- OMC:END -->` markers, injects `<!-- OMC:VERSION:x.y.z -->`, preserves user text outside the block under `<!-- User customizations -->`, and recovers from corrupted/unmatched markers by wrapping the remainder as "recovered from corrupted markers" (1936-1994).
9. **HUD statusline**: writes `~/.claude/hud/omc-hud.mjs` from the single-source template `scripts/lib/hud-wrapper-template.txt` (src/lib/hud-wrapper-template.ts:23-28; the wrapper itself locates the real HUD implementation in plugin cache → marketplace → global npm at runtime), plus `find-node.sh`, `omc-hud-cache.sh`, `lib/config-dir.{mjs,sh}`. Skipped when project-scoped, `--skip-hud`, or `hudEnabled: false` in `.omc-config.json` (2283-2317).
10. **settings.json** (single consolidated write, 2326-2385): legacy `~/.claude/hooks/` entries recognized by `isOmcHook()` are removed; standalone installs merge `getHooksSettingsConfig()` hook groups (that config is itself marked `@deprecated` for plugin installs, src/installer/hooks.ts:383-389); `statusLine` is set to `{type:"command", command:"sh ${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hud/omc-hud-cache.sh …omc-hud.mjs"}` only if absent or OMC-owned (`isOmcStatusLine()` checks for the `omc-hud` substring, 325-339) — a foreign statusLine is preserved even under `--force` (704-712). Hook merges honor three levels: default = skip on conflict + record in `result.hookConflicts`; `--force` = update OMC groups, keep non-OMC; `--force-hooks` = overwrite everything with a warning (807-849). After the main mutation the file is **re-read and re-merged if another process changed it** since the initial snapshot (2364-2377).
11. **MCP registry sync** (see below), **node binary pinning** (`nodeBinary` into `.omc-config.json` for find-node.sh, issue #892), **version metadata** `~/.claude/.omc-version.json` `{version, installedAt, installMethod:'npm', lastCheckAt}` (2388-2396), and a workspace stamp `.omc/template-version.json` `{version, installedAt, pluginRoot}` used by session-start drift detection (2398-2415).

### Unified MCP registry (src/installer/mcp-registry.ts)

OMC maintains a *tool-agnostic* MCP server registry and fans it out to two consumers:

- Registry file: `mcp-registry.json` under the global OMC config dir, overridable via env `OMC_MCP_REGISTRY_PATH` (:53-55). If missing, it is bootstrapped from whatever `mcpServers` exist in Claude's config (:262-295).
- Claude target: `~/.claude.json` (sibling of the config dir), overridable via `CLAUDE_MCP_CONFIG_PATH` (:73-79). Crucially, `applyRegistryToClaudeSettings()` **deletes `mcpServers` from settings.json entirely** — Claude's live MCP config is `~/.claude.json`, not settings.json (:301-312).
- Codex target: `$CODEX_HOME/config.toml` (default `~/.codex/config.toml`), where OMC owns only the region between `# BEGIN OMC MANAGED MCP REGISTRY` / `# END OMC MANAGED MCP REGISTRY` and never shadows a server name the user already defined outside the block (:48-49, 498-515). Launcher-backed commands (`npx`/`uvx`/`npm exec`) get a default `startup_timeout_sec` of 15 (:50, 112-119).
- Retired servers are actively scrubbed: any entry whose args reference `bridge/team-mcp.cjs` is dropped everywhere (:93-106).
- State file `mcp-registry-state.json` records `managedServers` so renames/removals propagate instead of accreting (:237-260).

## Configuration surface

**`~/.claude/settings.json` keys OMC touches**: `statusLine` (HUD), `hooks` (standalone installs only), `omcHud` (HUD config object written by `writeHudConfig()` — elements, thresholds, layout, locale, labels, `rateLimitsProvider`, missionBoard; src/hud/state.ts:456-491), `env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS = "1"` and optional `teammateMode` (written by the omc-setup skill, skills/omc-setup/phases/03-integrations.md:40-70; read back by `isTeamEnabled()`, src/features/auto-update.ts:681-696), `enabledPlugins` (read-only), and removal of `mcpServers` (moved to `~/.claude.json`).

**`~/.claude/.omc-config.json`** (interface `OMCConfig`, src/features/auto-update.ts:591-625): `silentAutoUpdate` (default **false** — "disabled by default for security"), `setupCompleted` (ISO ts), `setupVersion`, `hudEnabled`, `autoUpgradePrompt` (default true), `nodeBinary`, `taskTool`/`taskToolConfig` (`builtin`/`beads`/`beads-rust`), `notifications`/`notificationProfiles`, `stopHookCallbacks` (legacy), plus skill-written `defaultExecutionMode` and `team.ops.{maxAgents, defaultAgentType, monitorIntervalMs: 30000, shutdownTimeoutMs: 15000}` (phases/02-configure.md:118, 03-integrations.md:172-176).

**Env vars**: `CLAUDE_PLUGIN_ROOT` (plugin-mode detection + hook path base), `CLAUDE_CONFIG_DIR` (config-dir override, `~`-expansion handled in four synchronized implementations: src/utils/config-dir.ts + scripts/lib/config-dir.{mjs,cjs,sh}), `OMC_PLUGIN_ROOT` (dev `--plugin-dir` marker, src/lib/env-vars.ts:2), `OMC_UPDATE_RECONCILE` (re-exec loop guard), `OMC_MCP_REGISTRY_PATH`, `CLAUDE_MCP_CONFIG_PATH`, `CODEX_HOME`, `OMC_SECURITY=strict` (master security switch; `disableAutoUpdate` flows through `isAutoUpdateDisabled()`, src/lib/security-config.ts:95,146-148), `CLAUDE_CODE_ENTRYPOINT`/`CLAUDE_SESSION_ID` (live-session detection).

## Version and update flow

`omc update` (src/cli/index.ts:732-810 → src/features/auto-update.ts):

1. `checkForUpdates()` compares `.omc-version.json` against the latest GitHub release of `Yeachan-Heo/oh-my-claudecode` (:944-963).
2. `performUpdate()` refuses to run inside a live Claude session unless `--standalone` — plugin-mode plus `CLAUDE_CODE_ENTRYPOINT` or `CLAUDE_SESSION_ID` means "use `/plugin install oh-my-claudecode` instead" (:444-460, 1092-1099).
3. `npm install -g oh-my-claude-sisyphus@latest`; then **restores a global `@anthropic-ai/claude-code`** if the npm operation clobbered it (:202-239).
4. Syncs the marketplace git clone at `plugins/marketplaces/omc` (`syncMarketplaceClone`, #506) and copies the fresh npm payload into a new `plugins/cache/omc/oh-my-claudecode/<version>/` dir, updating `installed_plugins.json` only after a clean copy (:462-525).
5. **Re-exec trick**: because the running process still has old code in memory, it sets `OMC_UPDATE_RECONCILE=1` and exec's the *new* binary's `omc update-reconcile`, which runs `installOmc({force:true})` + cache sync + purge with the new logic (:1136-1196; CLI at src/cli/index.ts:817-839).
6. `purgeStalePluginCacheVersions()` deletes cache versions not referenced by `installed_plugins.json`, but (a) skips dirs modified within `STALE_THRESHOLD_MS = 24h` unless `--clean`/`--skip-grace-period`, and (b) when an active sibling version exists, **replaces the stale dir with a symlink to it** so sessions still holding the old `CLAUDE_PLUGIN_ROOT` keep working (src/utils/paths.ts:247, 341-384).

`silentAutoUpdate` (opt-in) runs the same pipeline in the background with a 24h check interval and exponential failure backoff capped at 168h (:1418-1440); `reconcileUpdateRuntime` hardcodes `shouldRefreshPluginHooks = false` so update never re-injects standalone settings.json hooks over plugin-owned ones (:971-1003). Version provenance is redundant by design: package.json → path-embedded version in the cache dir (`/oh-my-claudecode/4.11.2/` regex fallback, src/lib/version.ts:38-48) → CLAUDE.md `OMC:VERSION` marker. `isRuntimePackageLocal()` flags dev installs (`.git/` or `src/` at package root, or any symlinked ancestor) which the HUD renders as an `L` suffix (src/lib/version.ts:71-118).

## Setup skills (agent-driven wizard layer)

| Skill | Role |
|---|---|
| `setup` | 41-line router: first arg only — bare/`wizard`/`local`/`global`/`--force` → `omc-setup`; `doctor` → `omc-doctor`; `mcp` → `mcp-setup` (skills/setup/SKILL.md:22-27) |
| `omc-setup` | Canonical interactive wizard. Resolves the **freshest valid plugin root itself** (inline `node -e` scanning cache versions, defeating stale `CLAUDE_PLUGIN_ROOT` in a running session; SKILL.md:86-99), runs `repair-plugin-cache.mjs`, checks `setupCompleted` in `.omc-config.json` to offer "Update CLAUDE.md only", then executes 4 phase files with resume state in `.omc/state/setup-state.json` `{lastCompletedStep, timestamp, configType}` (24h staleness → fresh; scripts/setup-progress.sh:64-86) |
| `omc-doctor` | Read-then-report diagnostics: cache version vs npm latest, legacy bash hooks/scripts, CLAUDE.md marker + version drift, Ruby-for-Ralph, multi-version cache, legacy curl-era agents/commands/skills; emits an OK/WARN/CRITICAL table and gated auto-fixes (cache clear, keep-latest-version prune, GitHub CLAUDE.md refetch) |
| `local-build-reminder` | Dev-mode discipline: when HUD shows `[OMC#X.Y.ZL]`, `.ts` edits are invisible until `npm run build`; includes a file-type table of what needs a rebuild vs plain restart |

Phase specifics worth copying: Phase 1 delegates CLAUDE.md writes to `scripts/setup-claude-md.sh <local|global> [overwrite|preserve]` — the model is forbidden from hand-writing CLAUDE.md ("Do NOT use the Write tool"); `preserve` mode installs OMC into a companion `CLAUDE-omc.md` (setup-claude-md.sh:212) leaving the user's base file intact; local installs seed `.git/info/exclude` with an `.omc/` block (:98). Phase 2 delegates statusLine to the `hud` skill (which copies `scripts/lib/hud-wrapper-template.txt` verbatim — "the template is the single source of truth … guarded by drift tests", skills/hud/SKILL.md:57), and stores `defaultExecutionMode`/`taskTool` via jq-with-tempfile merges that abort rather than corrupt config when jq is missing. Phase 4 ends with `setup-progress.sh complete <version>` which stamps `setupCompleted`/`setupVersion` and clears leftover per-session `skill-active-state.json` so the Stop hook doesn't block (:99-113).

## Failure modes and guards

| Guard | Behavior |
|---|---|
| Hook runner | always fail-open (exit 0), self-timeout with 500ms cushion |
| Plugin cache incomplete | loud-fail: install aborts (only hard failure in the pipeline) |
| settings.json write | try/catch → "non-fatal" warning, `hooksConfigured = false`; concurrent-write re-read before final write |
| HUD install | best-effort, non-fatal |
| Foreign statusLine / non-OMC hooks | preserved by default; conflicts surfaced in `hookConflicts`; `--force-hooks` is the only destructive path and it warns |
| Downgrade | version-hint comparison skips install, tells user to `omc update` |
| Deletion safety | `.omc-managed` marker or exact content hash required before removing user-dir skills/hooks; stale cache dirs become symlinks, not holes |
| Kill switches | `OMC_SECURITY=strict` config (`disableAutoUpdate` etc.); `hudEnabled:false`; `--skip-hud`, `--no-plugin`, `--skip-grace-period` |

`src/platform/` is thin and honestly so: `index.ts` (53 lines) provides `isWindows/isMacOS/isLinux/isWSL` (WSLENV or `/proc/version` contains "microsoft") and re-exports `process-utils.ts`, whose `killProcessTree()` wraps `taskkill /T [/F]` on Windows and negative-PID group kill with direct-kill fallback on Unix. It is a leaf utility layer, not an install subsystem.

## Patterns for sibling harnesses

- **Fail-open hook runner with stale-root healing** (scripts/run.cjs): one runner script per harness that resolves its target across cache versions, self-times-out under the manifest budget, and never exits nonzero — adapt by pointing the sibling's hooks.json at a single `run.cjs` equivalent.
- **Marker-fenced managed regions in shared files** (`<!-- OMC:START/END -->`, `# BEGIN/END OMC MANAGED MCP REGISTRY`): own only your block in CLAUDE.md/config.toml, preserve everything else, recover from corrupted markers — adopt harness-specific marker names (`<!-- OMX:START -->`).
- **Ownership markers before deletion** (`.omc-managed` file + content-hash equality): never prune a user-dir artifact unless you can prove you wrote it; sibling installers should stamp `.omx-managed` etc. at copy time.
- **Compact skill shims + archived full bodies** (`skill-bodies/`, `omc-full-body` frontmatter): keep startup context light while retaining full instructions on disk; directly applicable to any harness with many large SKILL.md files.
- **Re-exec reconciliation after self-update** (`OMC_UPDATE_RECONCILE=1` + `update-reconcile` subcommand): never run post-update file surgery with pre-update code in memory; any self-updating CLI harness should re-exec its new binary for the reconcile step.
- **Grace-period purge with symlink tombstones** (24h mtime guard, stale version dir → symlink to active version): lets long-running sessions survive an update; reuse for any versioned cache the harness maintains.
- **Downgrade guard from persisted version hints** (`.omc-version.json` + in-file `VERSION` marker): an old CLI must refuse to overwrite a newer install; cheap to replicate with one JSON stamp plus a content marker.
- **Namespace-collision renaming** (`CC_NATIVE_COMMANDS` → `omc-` prefix): when installing skills into a shared user dir, prefix names that collide with host-native commands.
- **Script-owned config writes with jq tempfile + abort-if-no-jq** (phase files): agent-driven setup should shell out to idempotent scripts for config mutation, never hand-write JSON via the Write tool.
- **Version provenance in the path itself** (regex on `/name/<semver>/` as last-resort version source): survives hosts that strip package.json from caches.

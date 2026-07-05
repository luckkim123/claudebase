# Core Infrastructure: State Layout, Path Resolution, Config, and Shared Libraries

This section is the single source of truth for OMC v4.15.2's on-disk state schema and the shared infrastructure under `src/lib/`, `src/config/`, `src/shared/`, `src/utils/`, `src/constants/`, and `src/types/`. Everything here is ACTIVE runtime code: it is imported by the hook scripts (`scripts/*.mjs` dynamically import `dist/lib/worktree-paths.js`, e.g. `scripts/session-start.mjs:813`), the MCP tool server (`src/tools/state-tools.ts`), the CLI (`src/cli/`), the HUD (`src/hud/`), and the team/autopilot/ultragoal subsystems. The two exceptions are noted inline as vestigial/dev-only. The central abstraction is a per-project dot-directory (`.omc/`) whose *location* is computed by a five-stage anchor-resolution algorithm, whose *contents* follow a session-scoped state convention, and whose writers are protected by atomic-rename writes and `O_EXCL` advisory file locks.

## Anchor resolution: where `.omc/` lives

`getOmcRoot(worktreeRoot?)` (src/lib/worktree-paths.ts:503) decides the state root. Resolution order (highest first):

```
1. $OMC_STATE_DIR set?          -> $OMC_STATE_DIR/{projectIdentifier}/     (centralized, survives worktree deletion)
2. .omc-workspace marker found? -> {markerDir}/.omc                        (multi-repo workspace anchor)
3. cwd inside git submodule?    -> {outermost superproject toplevel}/.omc  (climb, issue #3349)
4. in a git repo?               -> {git rev-parse --show-toplevel}/.omc
5. else                         -> {cwd}/.omc
```

Key mechanics, all in `src/lib/worktree-paths.ts`:

- **Workspace marker**: the filename is `WORKSPACE_MARKER = '.omc-workspace'` (:30). `findWorkspaceRoot()` walks parent directories but **stops before scanning `$HOME`** so a stray `~/.omc-workspace` cannot collapse unrelated repos into one state root (:104). The marker may be empty or JSON `{ "id": "stable-workspace-identifier" }` (:26-27); parse errors return `{}` (fail-open, :126-138). Kill switch: `OMC_DISABLE_MULTIREPO=1` disables the walk entirely (:79).
- **Submodule climb**: `resolveSuperprojectRoot()` loops `git rev-parse --show-superproject-working-tree` up to depth 32 with a 5s timeout per call (:148-169). Crucially there are two resolvers with a documented SECURITY split: `getWorktreeRoot()` climbs (for state *placement*) while `getGitTopLevel()` never climbs and is "the correct primitive for path-restriction / containment checks" (:196-201) — using the climbing variant for a boundary check would widen confinement across submodule borders.
- **Identity vs placement**: `getProjectIdentifier()` deliberately does NOT climb — "a submodule must keep its OWN identity" (:417-425). So with `OMC_STATE_DIR` set, a submodule gets its own centralized directory even though without it its `.omc/` would be placed at the superproject root. `resolveToWorktreeRoot()` switches resolver on `process.env.OMC_STATE_DIR` for exactly this reason (:1014).
- **Project identifier format**: `{dirName}-{first 16 hex of SHA-256}` (:410). Hash source precedence: workspace-marker `id` (sanitized `[^a-zA-Z0-9_-] -> _`) > workspace root path > `git remote get-url origin` > worktree root path (:426-490). Linked worktrees resolve `--git-common-dir` to the primary repo root (only when `basename(commonDir) === '.git'` and not a submodule `.git/modules` path) so all worktrees of one repo share one identifier (:463-483).
- **Caching**: three module-level LRU `Map`s (worktree root, literal toplevel, workspace marker), each bounded to `MAX_WORKTREE_CACHE_SIZE = 8` entries (:56-64); "not a git repo" is intentionally never cached so a later `git init` is re-detected (:227-229, :261-264).
- **Dual-dir notice**: when both legacy `{root}/.omc/` and the centralized dir exist, a once-per-pair `console.warn` recommends migration (:517-525). A once-per-session sibling scan, `warnSiblingRetrofit()`, warns when a new `.omc-workspace` anchor shadows pre-existing per-repo `.omc/state/` dirs; dedupe is a disk marker `state/sibling-retrofit-warned-{sessionId}.json` under the shared root (:315-369), invoked from `scripts/session-start.mjs:813-817`.

Path safety: `validatePath()` rejects `..`, `~`, and absolute paths (:283-294); `resolveOmcPath()` re-verifies the resolved result is still under the `.omc` root (:551-564). `validateWorkingDirectory()` derives a trusted root from `process.cwd()` (never user input), realpath-compares, and returns the trusted root — never a subdirectory — so `.omc/state/` cannot be created in subdirs (#576, :1162-1221); the `...OrLinkedWorktree` variant additionally admits a sibling `git worktree` sharing the same `--git-common-dir` (:1248-1305).

## The `.omc/` on-disk layout (v4.15.2)

The canonical constants are `OmcPaths` (src/lib/worktree-paths.ts:33-49). `ensureAllOmcDirs()` pre-creates only `state, plans, research, logs, notepads, drafts` (:671-686); everything else is created lazily by its owner.

```
{anchor}/.omc/
├── notepad.md                      OmcPaths.NOTEPAD — persistent notepad
├── project-memory.json             OmcPaths.PROJECT_MEMORY — deep-merged cross-session memory
├── deepinit-manifest.json          OmcPaths.DEEPINIT_MANIFEST (src/tools/deepinit-manifest.ts)
├── .gitignore                      written lazily; wiki storage appends "wiki/" (src/hooks/wiki/storage.ts:56-64)
├── plans/                          plan artifacts; default output ".omc/plans/{{name}}.md" (src/config/plan-output.ts:5-6)
├── research/                       research folders (resolveResearchPath, worktree-paths.ts:636)
├── logs/                           resolveLogsPath (worktree-paths.ts:644)
├── notepads/{planName}/            plan-scoped "wisdom" notepads (resolveWisdomPath, worktree-paths.ts:652)
├── drafts/                         OmcPaths.DRAFTS
├── skills/                         OmcPaths.SKILLS — project-scoped skills (the committable exception)
├── scientist/                      OmcPaths.SCIENTIST
├── autopilot/                      OmcPaths.AUTOPILOT
├── wiki/                           LLM wiki store (src/hooks/wiki/storage.ts)
├── specs/                          autoresearch/deep-interview artifacts (src/cli/autoresearch-intake.ts:108-112)
├── ultragoal/                      brief.md, goals.json, ledger.jsonl; multi-plan under ultragoal/plans/{planId}/
│                                   (src/ultragoal/artifacts.ts:12-15,177-199)
├── team/{team}/worktrees/{worker}/ native team worker git worktrees (src/team/git-worktree.ts:7,89)
├── sessions/{sessionId}.json       durable session-end summaries (src/hooks/session-end/index.ts:790)
└── state/                          OmcPaths.STATE — all runtime mode state
    ├── {mode}-state.json           LEGACY global mode state (resolveStatePath, worktree-paths.ts:577-581)
    ├── {mode}-stop-breaker.json,
    │   {mode}-last-steer-at,
    │   {mode}-continue-steer.lock  runtime artifacts, global or per-session (src/lib/mode-state-io.ts:84-87)
    ├── jobs.db                     SQLite (WAL) Codex/Gemini background-job metadata (src/lib/job-state-db.ts:70)
    ├── shared-memory/{ns}/{key}.json  TTL'd KV store (src/lib/shared-memory.ts:80)
    ├── team/{team}/...             team runtime state incl. worktrees.json (src/team/git-worktree.ts:212)
    ├── team-bridge/{team}/...      MCP team-bridge state (src/team/git-worktree.ts:216)
    ├── sibling-retrofit-warned-{sid}.json  once-per-session warning marker (worktree-paths.ts:321)
    └── sessions/{sessionId}/       OmcPaths.SESSIONS — session-scoped state
        └── {mode}-state.json       canonical per-session mode state (worktree-paths.ts:814)
```

Mode-state filenames come from `MODE_STATE_FILE_MAP` (src/lib/mode-names.ts:55-65): `autopilot | autoresearch | team | ralph | ultrawork | ultraqa | ralplan | deep-interview | self-improve` + `-state.json`, plus `skill-active-state.json` in the session-end cleanup list (:81). Deprecated modes `ultrapilot`, `swarm`, `pipeline` survive only as constants for migration warnings (#1131, :26-30). Note there is a second, older mode registry `MODES` in src/constants/names.ts:9-16 with only six entries — a real drift hazard between two "single sources of truth".

## Session-id threading

- **Resolution is context-asymmetric** (src/lib/session-id.ts:10-17): in `cli` context `OMC_SESSION_ID` env wins over any hook payload (`env ?? payload`); in `hook` context the Claude Code payload `data.session_id` wins (`payload ?? env`). Rationale is documented verbatim in the file: the user controls the env per-shell; Claude Code is authoritative for the live session.
- **Fallback process ID**: `getProcessSessionId()` returns `pid-{PID}-{startTimestamp}` (e.g. `pid-12345-1707350400000`), generated once per process, to keep concurrent Claude instances in one repo from sharing state (issue #456, worktree-paths.ts:727-736).
- **Validation**: `SESSION_ID_REGEX = /^[a-zA-Z0-9][a-zA-Z0-9_-]{0,255}$/` plus explicit `..`/`/`/`\` rejection before any path is built (worktree-paths.ts:702, :752-762).

### Session-scoped state I/O and the branded-path pattern

`resolveSessionStatePaths(stateName, sessionId?, worktreeRoot?)` (worktree-paths.ts:894-921) returns a struct of four paths with TypeScript **branded string types** `ReadPath` / `WritePath` (`string & { readonly __brand: ... }`, :843-844): `effectiveRead` probes the session-scoped file and falls back to the legacy global file if absent; `effectiveWrite` is always session-scoped when a sessionId exists. The brand makes "wrote to the read-fallback path" a compile error across 19+ call sites (:834-841). Without a sessionId both brands point at the legacy path (back-compat single-session mode). Legacy-to-session migration is opt-in via `migrate: true` or the env var; the exact gate is `isLegacyStateMigrationEnabled(): process.env.OMC_MIGRATE_LEGACY_STATE === '1'` (:927-929).

`src/lib/mode-state-io.ts` is the higher-level canonical mode-state API — and it implements a *stricter* policy than the branded resolver:

| Operation | Behavior |
|---|---|
| `writeModeState` | Wraps state in an envelope: top-level `owner_pid` + `_meta: { written_at, mode, sessionId?, ownerPid? }`; atomic JSON write; returns `false` on any failure (never throws) (:203-237) |
| `readModeState` | With a sessionId, reads ONLY the session-scoped file — **no legacy fallback**, "to prevent cross-session state leakage"; strips `_meta` (:250-271) |
| `clearModeStateFile` | Deletes session file + runtime artifacts (`-stop-breaker.json`, `-last-steer-at`, `-continue-steer.lock`); then "ghost-legacy cleanup": deletes the legacy file only if `canClearStateForSession` — owner matches or file is unowned (:283-341) |
| `findSessionOwnedStateFiles` | Scans all session dirs for files whose embedded `_meta.sessionId`/`session_id` matches — recovers state stranded under a different session dir (:115-144) |
| `findCompletedSessionStateFiles` | Treats a sibling session's `active: true` state as orphaned ONLY if durable completion evidence `.omc/sessions/{sid}.json` exists — so `/cancel` from a fresh session cannot kill live parallel sessions (:156-188) |

`src/lib/session-isolation.ts` canonicalizes the ownership predicate: `isStateForSession(stateSid, sid, {lenient})` — no current session means allow; ownerless state is rejected when a session is active unless `lenient: true` (:30-44). The file's header documents the three historical inconsistent patterns it replaced (lenient / strict / guarded). Ownership extraction itself is `getStateSessionOwner()`, which prefers `_meta.sessionId` and falls back to a top-level `session_id` field (mode-state-io.ts:22-39) — both shapes exist in the wild because `session_id` predates the envelope.

### State lifecycle (arm -> run -> stop -> cancel -> resume), as seen from this layer

The lib layer does not own mode semantics, but every mode's lifecycle is expressed through these primitives:

```
arm      skill/CLI calls writeModeState(mode, {..., active: true}, dir, sid)
         -> ensureSessionStateDir + atomic write of state/sessions/{sid}/{mode}-state.json
run      Stop hook re-reads via readModeState(mode, dir, sid); presence + active:true keeps
         the loop alive; runtime artifacts ({mode}-stop-breaker.json, {mode}-last-steer-at,
         {mode}-continue-steer.lock) accumulate next to it (mode-state-io.ts:84-87)
stop/    /cancel calls clearModeStateFile(mode, dir, sid): session file + runtime artifacts
cancel   + ghost-legacy cleanup (ownership-checked legacy delete, mode-state-io.ts:302-338);
         a no-sid cancel sweeps the legacy paths AND every session dir (:307-318)
resume   a fresh session id reads nothing (readModeState is session-only), but a fresh
         /cancel can still find a finished sibling's live-looking state via
         findCompletedSessionStateFiles — gated on .omc/sessions/{sid}.json existing (:156-188)
end      session-end hook iterates SESSION_END_MODE_STATE_FILES (9 modes +
         skill-active-state.json, mode-names.ts:71-82) and writes the durable summary
         .omc/sessions/{sessionId}.json (session-end/index.ts:790)
```

## Concurrency and durability primitives

- **Atomic writes** (src/lib/atomic-write.ts): all variants write `.{base}.tmp.{randomUUID}` with `wx` (`O_CREAT|O_EXCL`) and mode `0o600`, `fsync` the fd, `rename` over the target, then best-effort `fsync` the directory; temp files are unlinked on failure. `ensureDirSync` tolerates the Windows `EEXIST` race (:17-32).
- **File locks** (src/lib/file-lock.ts): advisory lock file at `{file}.lock` created with `O_CREAT|O_EXCL|O_WRONLY` 0o600, payload `{"pid":..., "timestamp":...}`. Stale reaping requires BOTH age >= `DEFAULT_STALE_LOCK_MS = 30_000` AND the recorded PID dead (via `isProcessAlive` from `src/platform/`); malformed payloads count as stale when old (:50, :61-80). Defaults: `timeoutMs: 0` (single attempt), `retryDelayMs: 50`. The sync retry loop sleeps via `Atomics.wait` on a `SharedArrayBuffer`, falling back to a bounded spin on the main thread where `Atomics.wait` throws (:183-198). `withFileLockSync/withFileLock` throw `Failed to acquire file lock: {path}` when unobtainable — loud-fail — but callers often soften it (below).
- **Shared memory KV** (src/lib/shared-memory.ts): entries `{key, value, namespace, createdAt, updatedAt, ttl?, expiresAt?}` under `state/shared-memory/{ns}/{key}.json`; namespace/key regex `^[a-zA-Z0-9][a-zA-Z0-9._-]*$` max 128 chars (:83-106). Writes take the lock with `{timeoutMs: 500, retryDelayMs: 25}` and on lock failure **fall back to an unlocked write** ("best-effort", :198-203). Expired entries are deleted on read, filtered (not deleted) on list. Feature gate: `agents.sharedMemory.enabled` in `{claudeConfigDir}/.omc-config.json`, default **true** (opt-out) and fail-open on any read error (:63-74).
- **SQLite job DB** (src/lib/job-state-db.ts): `state/jobs.db`, `better-sqlite3` dynamically imported with graceful degrade (returns `false`, prints install hint) when absent; WAL mode; schema version constant `DB_SCHEMA_VERSION = 1`; per-worktree `Map` of DB instances keyed by resolved cwd, with deprecation warnings for no-arg calls when multiple DBs are open (:45-64); cleanup default 24h (`DEFAULT_CLEANUP_MAX_AGE_MS`). "All functions return false/null on failure (no throws)" (:14).
- **Payload limits** (src/lib/payload-limits.ts): `DEFAULT_PAYLOAD_LIMITS = { maxPayloadBytes: 1_048_576, maxNestingDepth: 10, maxTopLevelKeys: 100 }` with short-circuiting depth measurement — an OOM/disk-exhaustion guard for state/memory write tools.
- **Destructive-op guard** (src/lib/worktree-cleanup-safety.ts): `validateWorktreeRemovalTarget` is one of the few **fail-closed** modules — it throws typed error strings (`worktree_path_is_symlink:`, `worktree_path_outside_expected_roots:`, `worktree_path_is_main_repo:`, `..._is_filesystem_root:`, `..._is_home_directory:`) before any recursive removal; a `.git` *directory* (vs a worktree's `.git` file) marks a main repo (:110-115).

The default error posture everywhere else is fail-open with optional logging via `src/lib/swallowed-error.ts` (`logSwallowedError` prefixes `[omc] {context}:` and itself never throws).

## Configuration surface

`loadConfig()` (src/config/loader.ts:684-731) merge order, lowest to highest:

```
buildDefaultConfig()  ->  user config  ->  project config  ->  env vars  ->  auto-forceInherit  ->  validate (THROWS)
                          {getConfigDir()}/claude-omc/       loadEnvConfig()
                          config.jsonc  .claude/omc.jsonc (cwd-relative)
```

Both files are JSONC (`src/utils/jsonc.ts`); `deepMerge` skips `__proto__`/`constructor`/`prototype` keys (prototype-pollution guard, :246-247). `getConfigDir()` is OS-aware: `%APPDATA%` on Windows, `$XDG_CONFIG_HOME` or `~/.config` elsewhere (src/utils/paths.ts:50-55). Post-merge, `validateTeamConfig`/`validateAutopilotConfig` walk the raw object and **throw** descriptive errors naming the offending key and allowed values (loader.ts:505-654) — config validation is the loud-fail island in an otherwise fail-open codebase. `warnOnDeprecatedDelegationRouting` prints that Codex/Gemini delegationRouting now falls back to Claude Task (:468-490).

`PluginConfig` (src/shared/types.ts:59-262) top-level keys: `agents` (20 per-agent model overrides), `features` (`parallelExecution, lspTools, astTools, continuationEnforcement, autoContextInjection` — all default true), `mcpServers` (exa, context7), `companyContext`, `permissions` (`maxBackgroundTasks: 5`), `magicKeywords`, `routing` (tiers, `forceInherit`, `modelAliases`, escalation/simplification keywords), `externalModels`, `delegationRouting` (default disabled), `team` (`ops`, `roleRouting` over 15 `CANONICAL_TEAM_ROLES`; orchestrator pinned to claude, only `model` configurable), `autopilot` (`execution: "solo"` default), `planOutput`, `startupCodebaseMap` (`maxFiles: 200, maxDepth: 4`), `guards` (factcheck + sentinel), `teleport`, `taskSizeDetection` (`smallWordLimit: 50, largeWordLimit: 200`), `promptPrerequisites` (blocking tools `["Edit","MultiEdit","Write","Agent","Task"]`).

Model tiers (src/config/models.ts): built-in tier defaults `LOW=claude-haiku-4-5, MEDIUM=claude-sonnet-5, HIGH=claude-opus-4-8` (`BUILTIN_TIER_MODEL_DEFAULTS` over `CLAUDE_FAMILY_DEFAULTS`, which also lists a fourth `FABLE: 'claude-fable-5'` family, :32-44); external defaults `codexModel: 'gpt-5.3-codex'`, `geminiModel: 'gemini-3.1-pro-preview'`, `antigravityModel: 'Gemini 3.1 Pro (High)'` (`BUILTIN_EXTERNAL_MODEL_DEFAULTS`, :55-59). Provider detection (`isBedrock`, `isVertexAI`, `isNonClaudeProvider`, `shouldAutoForceInherit`) auto-enables `routing.forceInherit` on Bedrock/Vertex/proxy backends because bare tier aliases cause 400s there (:359-443); `ANTHROPIC_BASE_URL` is SSRF-validated (`src/utils/ssrf-guard.ts`) and an invalid URL is treated as non-Claude (:388-392).

### Environment variables (config/lib territory)

| Variable | Effect | Evidence |
|---|---|---|
| `OMC_STATE_DIR` | Centralize state at `$OMC_STATE_DIR/{projectId}/` | worktree-paths.ts:504 |
| `OMC_DISABLE_MULTIREPO=1` | Ignore `.omc-workspace` markers | worktree-paths.ts:79 |
| `OMC_MIGRATE_LEGACY_STATE=1` | Enable one-shot legacy->session state copy | worktree-paths.ts:928 |
| `OMC_SESSION_ID` | CLI-context session id (authoritative over payload) | session-id.ts:29 |
| `CLAUDE_CONFIG_DIR` | Override `~/.claude` (supports `~/` prefix) | utils/config-dir.ts:38-52 |
| `OMC_HOME` | Override global OMC config root; state at `$OMC_HOME/state` | utils/paths.ts:96-125 |
| `XDG_CONFIG_HOME` / `XDG_STATE_HOME` / `XDG_DATA_HOME` | XDG roots on Linux (not macOS/Windows) | utils/paths.ts:44-69 |
| `OMC_SECURITY=strict` | All security features on; config may only tighten | security-config.ts:95-109 |
| `OMC_MODEL_HIGH/MEDIUM/LOW` | Tier model overrides (then `CLAUDE_CODE_BEDROCK_*_MODEL`, `ANTHROPIC_DEFAULT_*_MODEL`) | models.ts:10-26 |
| `CLAUDE_MODEL` / `ANTHROPIC_MODEL` | Direct session model, wins for provider detection | models.ts:6 |
| `CLAUDE_CODE_USE_BEDROCK=1` / `CLAUDE_CODE_USE_VERTEX=1` | Provider detection -> auto forceInherit | models.ts:250,325 |
| `ANTHROPIC_BASE_URL` | Non-anthropic.com host -> forceInherit; SSRF-validated | models.ts:385-397 |
| `OMC_ROUTING_ENABLED/_FORCE_INHERIT/_DEFAULT_TIER`, `OMC_ESCALATION_ENABLED` | Routing toggles | loader.ts:312-361 |
| `OMC_MODEL_ALIAS_{HAIKU,SONNET,OPUS}` | Alias remap (e.g. haiku->inherit) | loader.ts:337-354 |
| `OMC_PARALLEL_EXECUTION`, `OMC_LSP_TOOLS`, `OMC_MAX_BACKGROUND_TASKS` | Feature flags | loader.ts:287-309 |
| `OMC_EXTERNAL_MODELS_DEFAULT_{PROVIDER,CODEX_MODEL,GEMINI_MODEL,GROK_MODEL,ANTIGRAVITY_MODEL}` (+ legacy `OMC_{CODEX,GEMINI,GROK,ANTIGRAVITY}_DEFAULT_MODEL`), `OMC_EXTERNAL_MODELS_FALLBACK_POLICY` | External model config | loader.ts:363-429 |
| `OMC_DELEGATION_ROUTING_ENABLED/_DEFAULT_PROVIDER`, `OMC_TEAM_ROLE_OVERRIDES` (JSON object) | Delegation/team routing | loader.ts:432-460 |
| `EXA_API_KEY` | Enables Exa MCP with key | loader.ts:279-284 |
| `OMC_PLUGIN_ROOT` | Set by CLI `--plugin-dir`; read by HUD wrapper/setup | lib/env-vars.ts:2 |
| `USER_TYPE=ant` | Gates Anthropic-internal-only skills/guidance | utils/skininthegamebros-user.ts; features/builtin-skills/skills.ts:314 |

(The `DISABLE_OMC` / `OMC_SKIP_HOOKS` kill switches live in the hook scripts layer, not in `src/lib`/`src/config` — zero hits in this territory.)

### Context injection and plan output (config-adjacent helpers)

`findContextFiles()` walks from cwd to filesystem root collecting `AGENTS.md`, `CLAUDE.md`, `.claude/CLAUDE.md`, `.claude/AGENTS.md` (loader.ts:794-826). `loadContextFromFiles()` enforces a total budget `OMC_CONTEXT_FILES_MAX_CHARS = 12000`, truncating the last block with a visible notice (:739, :831-857). Before budgeting, `compactOmcStartupGuidance()` detects OMC's own injected guidance (requires `<guidance_schema_contract>` plus an `oh-my-(claudecode|codex)` mention) and strips the bulky `<agent_catalog>`, `<skills>`, `<team_compositions>` sections, then caps the remainder at `OMC_STARTUP_GUIDANCE_MAX_CHARS = 8000` (:733-789) — self-deduplication so OMC's startup guidance is not re-ingested at full size through CLAUDE.md scans.

Plan output (src/config/plan-output.ts): default directory `.omc/plans`, template `{{name}}.md` (tokens `{{name}}`/`{{kind}}`). Both the configured directory and the rendered filename are sanitized — directory through `validatePath()`, filename by rejecting `/`, `\`, `..` and falling back to the default; the kind segment itself is slugged to `[a-z0-9_-]` with `"plan"` as last resort (:10-76). `resolveAutopilotPlanPath()` and `resolveOpenQuestionsPlanPath()` pin the two well-known artifacts `autopilot-impl` and `open-questions` (:96-102).

### Security config

`src/lib/security-config.ts` has its own precedence: **config file `security` section > `OMC_SECURITY` env > defaults** (:14). Seven knobs (`restrictToolPaths, pythonSandbox, disableProjectSkills, disableAutoUpdate, hardMaxIterations, disableRemoteMcp, disableExternalLLM`); defaults all off with `hardMaxIterations: 500`; strict flips all on with `hardMaxIterations: 200`. In strict mode the file can only tighten: booleans are OR-ed, `hardMaxIterations` is `Math.min` (:100-109). Result is process-cached.

## Global (per-user) directories and Claude Code interop

Three distinct "global" roots coexist:

1. `getClaudeConfigDir()` — `$CLAUDE_CONFIG_DIR` or `~/.claude` (src/utils/config-dir.ts:36-53), mirrored in three keep-in-sync runtimes (`scripts/lib/config-dir.{mjs,cjs,sh}`). `getOmcConfigDir()` = `{claudeConfigDir}/.omc` hosts `update-check.json` (:60-67). `{claudeConfigDir}/.omc-config.json` (`OMC_CONFIG_FILE_REL`, src/lib/paths.ts:13) holds installer-owned settings like the shared-memory gate.
2. `getGlobalOmcConfigRoot()`/`getGlobalOmcStateRoot()` — `$OMC_HOME` if set, else XDG (`~/.config/omc`, `~/.local/state/omc`) on Linux, else legacy `~/.omc`; candidate lists always include the legacy path for backward-compat reads (src/utils/paths.ts:95-167).
3. Plugin cache: `{claudeConfigDir}/plugins/cache/omc/oh-my-claudecode/{version}/` (`OMC_PLUGIN_CACHE_REL`, src/lib/paths.ts:8). `purgeStalePluginCacheVersions()` removes versions absent from `installed_plugins.json`, with a 24-hour mtime grace period (`STALE_THRESHOLD_MS`, extended from 1h "to avoid deleting cache directories still referenced by long-running sessions") and — when an active version exists — replaces the stale directory with a **symlink to the newest active version** so running sessions whose `CLAUDE_PLUGIN_ROOT` points at the old path keep working (src/utils/paths.ts:244-388).

Claude Code transcript interop: `encodeProjectPath()` replaces every non-alphanumeric char with `-` — the single source of truth shared by session search and the transcript resolver, after two drift bugs (#3329 underscores, Windows drive-colon PR #3274) (src/utils/encode-project-path.ts). `resolveTranscriptPath()` repairs worktree-mismatched `transcript_path` values via three strategies: strip the `--claude-worktrees-[^/\\]+` encoded segment; detect `/.claude/worktrees/` in cwd and re-encode the main project root; detect a linked worktree via `git rev-parse --git-common-dir` and re-encode (worktree-paths.ts:1053-1148). `isValidTranscriptPath()` allowlists only `{claudeConfigDir}`, `~/.omc`, `tmpdir()`, `/tmp`, `/var/folders` (:797-803).

## Small shared libraries

- `src/lib/mode-names.ts` vs `src/constants/names.ts`: two overlapping registries (9 vs 6 modes); `src/constants` also enumerates `TOOL_CATEGORIES` (15 MCP tool groups) and `HOOK_EVENTS` (7).
- `src/lib/project-memory-merge.ts`: field-aware deep merge for `.omc/project-memory.json` cross-session sync (#1168) — `customNotes` dedupe by `category::content` newest-wins, `hotPaths` merge `Math.max` access counts, primitive arrays union by JSON equality; proto-pollution keys skipped.
- `src/lib/truncate-prompt.ts`: `DEFAULT_PROMPT_ECHO_MAX_CHARS = 150` cap for stop-hook prompt echoes (context-token guard, issue #2542).
- `src/lib/version.ts`: runtime version from package.json walk-up with fallback to parsing the version out of the plugin-cache path; `isRuntimePackageLocal()` flags dev installs (`.git/` or `src/` at package root, or symlinked ancestry) for the HUD's "L" suffix.
- `src/shared/artifact-descriptor.ts`: inline-vs-descriptor artifact handoff (`DEFAULT_INLINE_ARTIFACT_THRESHOLD_BYTES = 2048`), retention enum `ephemeral|session|until-completion|persistent`, producer `system: 'omc' | 'omx'` — an explicit interop schema with the oh-my-experiments harness (consumed by `src/interop/mcp-bridge.ts`, `src/interop/shared-state.ts`).
- Vestigial/dev-only: `src/lib/featured-contributors.ts` and `src/lib/release-generation.ts` are consumed only by release tooling (`scripts/release.ts`, `scripts/sync-metadata.ts`); `src/types/` contains a single ambient declaration for the `safe-regex` package. Two lines each is all they merit.

## Patterns for sibling harnesses

- **Five-stage state-anchor resolution with an explicit override ladder** (env dir > workspace marker > VCS-derived root > cwd): adapt by keeping the marker filename harness-specific (`.omx-workspace`) and always stopping the upward walk at `$HOME`.
- **Placement/identity split**: the directory where state *lives* may climb (submodule -> superproject) while the project *identity hash* must not — copy this exact asymmetry before adding any centralized-state mode.
- **Two git-root primitives, one for state and one for security**: never reuse the climbing resolver for path-containment checks; expose both and document which is which.
- **Stable project identifier = `{dirname}-{sha256[:16]}` of remote-URL-or-path**, with linked-worktree normalization via `--git-common-dir`: gives all clones/worktrees one state bucket with a human-readable prefix.
- **Branded Read/Write path types** produced by a single resolver: a zero-runtime-cost way to make "wrote to the read-fallback path" a compile error; worth adopting anywhere legacy-fallback reads coexist with scoped writes.
- **Session-scoped state with `_meta` ownership envelope + ghost-legacy cleanup**: write `{sessionId, ownerPid, written_at}` into every state file, and require durable completion evidence (a session-end summary file) before another session may clear "orphaned" active state.
- **`O_EXCL` lock files with PID payload and age-AND-dead-PID stale reaping** (30s default), plus tmp-uuid + fsync + rename atomic writes: the full recipe for multi-process hook safety without a daemon; keep `timeoutMs: 0` as the default so hot paths never block.
- **Fail-open by default, fail-closed at destruction**: return null/false and log via a swallowed-error helper everywhere, but throw typed error strings from a dedicated safety validator before any recursive delete (symlink, main-repo, root/home checks).
- **JSONC config with defaults -> user -> project -> env merge and post-merge validation that throws**: validation on the merged raw object catches deepMerge escapes; proto-pollution key filtering belongs in the merge itself.
- **Strict security mode that config can only tighten** (`OR` booleans, `min` numeric caps): a one-env-var hardening switch that cannot be silently relaxed by a repo-local file.
- **Once-per-session disk-marker warning dedupe** (`state/<warning>-<sessionId>.json`): re-warns on new sessions by design, silent within one; cheaper and more portable than in-memory sets across hook processes.
- **Stale-cache symlink replacement instead of deletion** during upgrades, with a 24h mtime grace period: keeps long-running sessions pinned to old install paths alive.

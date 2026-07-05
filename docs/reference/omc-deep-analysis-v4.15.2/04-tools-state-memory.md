# MCP Tools: State, Notepad, Project Memory, Shared Memory, Session Search, Trace

OMC exposes a family of persistence and introspection tools over a single stdio MCP server named `t` (`.mcp.json` -> `node ${CLAUDE_PLUGIN_ROOT}/bridge/mcp-server.cjs`, built from `src/mcp/standalone-server.ts` per `scripts/build-mcp-server.mjs:35,40`). The tools in this territory give the model durable, file-backed memory surfaces under the project's `.omc/` directory: mode state files (`state_*`), a three-tier markdown notepad (`notepad_*`), a JSON project-environment memory (`project_memory_*`), a TTL'd cross-agent key-value store (`shared_memory_*`), full-text search over prior transcripts (`session_search`), and read-only views over the hook-recorded agent flow trace (`trace_timeline`/`trace_summary`). All are ACTIVE and registered in `src/mcp/tool-registry.ts:52-64` (`stateTools`, `notepadTools`, `memoryTools`, `traceTools`, `sharedMemoryTools`); `session_search` is registered by being folded into `traceTools` (`src/tools/trace-tools.ts:466`), while its own `sessionHistoryTools` export (`src/tools/session-history-tools.ts:55`) is unused. `src/tools/index.ts` is a separate, mostly vestigial aggregation (only lsp/ast/python) used for SDK-format conversion, not the live server.

## Shared substrate

Every tool funnels through the same primitives, which are the most reusable part of this subsystem:

| Primitive | Behavior | Evidence |
|---|---|---|
| `getOmcRoot()` | Resolution order: `$OMC_STATE_DIR/{projectId}` > `.omc-workspace` marker dir > git superproject/toplevel > cwd. Project id = `{dirName}-{sha256(remote-or-path)[:16]}` | `src/lib/worktree-paths.ts:503-540,416-491` |
| `validateWorkingDirectory()` | Trust anchor is `getGitTopLevel(process.cwd())`, never user input; a `workingDirectory` arg resolving to a *different* repo is silently replaced by the trusted root (logged to stderr); non-git subdirs normalize up to the root so `.omc/` never lands in a subdir (#576) | `worktree-paths.ts:1162-1221` |
| `atomicWriteJsonSync` | temp file (`.{base}.tmp.{uuid}`) opened `wx` with mode `0o600`, `fsync`, `renameSync`, best-effort dir fsync | `src/lib/atomic-write.ts:114-137` |
| `withFileLockSync` | Sidecar lock file via `O_CREAT\|O_EXCL`; PID-based stale-lock reaping after `staleLockMs` default `30_000`; callers pass `timeoutMs` (notepad: 5000, shared-memory: 500 with `retryDelayMs: 25` then **falls back to unlocked write**) | `src/lib/file-lock.ts:42-59,111`; `shared-memory.ts:199-203` |
| `validatePayload` | `maxPayloadBytes: 1_048_576` (1MB), `maxNestingDepth: 10`, `maxTopLevelKeys: 100` | `src/lib/payload-limits.ts:19-23` |
| `resolveSessionId` | Asymmetric precedence: CLI context `OMC_SESSION_ID` env wins over hook payload; hook context payload wins over env | `src/lib/session-id.ts:44-52` |
| `OMC_DISABLE_TOOLS` | Comma-separated category kill switch (`state`, `notepad`, `memory`/`project-memory`, `trace`, `shared-memory`, ...); unknown names silently ignored | `src/mcp/disable-tools.ts:7-55` |

On-disk layout (all under the resolved `.omc/`):

```
.omc/
├── notepad.md                              # 3-section markdown (notepad_*)
├── project-memory.json                     # ProjectMemory schema v1.0.0
├── sessions/{sessionId}.json               # session-end summaries (completion evidence)
└── state/
    ├── {mode}-state.json                   # legacy shared mode state
    ├── cancel-signal-state.json            # legacy cancel signal
    ├── agent-replay-{sessionId}.jsonl      # trace event log (hook-written)
    ├── shared-memory/{namespace}/{key}.json
    └── sessions/{sessionId}/
        ├── {mode}-state.json               # session-scoped mode state
        └── cancel-signal-state.json        # session cancel signal (TTL 30s)
```

## state_* — mode state files (`src/tools/state-tools.ts`)

Five tools manage the JSON state files that arm/disarm OMC execution modes. The write/read `mode` enum is `STATE_TOOL_MODES` (`state-tools.ts:52-57`), which spreads the 8 canonical `EXECUTION_MODES` (`'autopilot', 'autoresearch', 'team', 'ralph', 'ultrawork', 'ultraqa', 'deep-interview', 'self-improve'`; `:47-49`) plus 3 state-only extras `EXTRA_STATE_ONLY_MODES` (`'ralplan', 'omc-teams', 'skill-active'`; `:58`). Registry modes route through `MODE_CONFIGS`/`getStateFilePath` (`src/hooks/mode-registry/index.ts:51-135`); extras fall back to `resolveStatePath` naming `{mode}-state.json`.

| Tool | Required params | Optional params | Notes |
|---|---|---|---|
| `state_read` | `mode` | `workingDirectory`, `session_id` | With `session_id`: single file; without: legacy path + scan of every session dir, output explicitly warns "may include state from other sessions" (`:675`). If the session file is missing, it lists completed-session orphan files and suggests the exact `state_clear` invocation (`:631`) |
| `state_write` | `mode` | `active`, `iteration`, `max_iterations`, `current_phase` (max 200), `task_description` (max 2000), `plan_path` (max 500), `started_at`/`completed_at` (max 100), `error` (max 2000), `state` (free record, validated by `validatePayload`), `workingDirectory`, `session_id` | Explicit params override `state` keys; write is stamped with `_meta: { mode, sessionId, updatedAt, updatedBy: 'state_write_tool' }` (`:838-846`); no-session write appends a leak warning (`:851`) |
| `state_clear` | `mode` | `workingDirectory`, `session_id` | Destructive sweep, see below |
| `state_list_active` | — | `workingDirectory`, `session_id`, `all` | Default scope is the *current* session via `resolveSessionId({context:'cli'})` (env `OMC_SESSION_ID`); `all:true` opts out (`:1313-1316`) |
| `state_get_status` | — | `mode`, `workingDirectory`, `session_id` | Per-mode active flag, path, existence, 500-char state preview; also reports the 3 extra state-only modes |

`state_clear` is the cancel path and is deliberately over-thorough. For a session-scoped clear it: (1) writes a **cancel signal** `{active, requested_at, expires_at, mode, source: 'state_clear'}` with `CANCEL_SIGNAL_TTL_MS = 30_000` to `sessions/{sid}/cancel-signal-state.json` *before* deleting anything (`:534-548`), so the Stop hook's `isSessionCancelInProgress` (`src/hooks/persistent-mode/index.ts:122-162`) suppresses re-arm races during the deletion window (expired signals are unlinked on read); (2) deletes the session file, files in *other* session dirs whose `_meta.sessionId`/`session_id` owner matches (`findSessionOwnedStateFiles`, `src/lib/mode-state-io.ts:114-144`), completed-session orphans (only sessions with durable completion evidence `.omc/sessions/{sid}.json` — `hasSessionEndSummary`, `mode-state-io.ts:103-105,156-188`), ghost legacy files at both `state/{mode}-state.json` and `.omc/{mode}-state.json`, and runtime artifacts `{mode}-stop-breaker.json`, `{mode}-last-steer-at`, `{mode}-continue-steer.lock` (`:489-495`); (3) for `ralph`/`ultrawork` (`CONVERGED_STATE_PATH_MODES`) additionally sweeps "converged" candidates across three `.omc` roots — resolved root, literal `{cwd}/.omc`, and `~/.omc` (`:93-134`) — to catch state written before/after an `OMC_STATE_DIR` or workspace-marker migration; (4) for `ralph` only (`OWNER_SESSION_FALLBACK_MODES`), if nothing was cleared, finds the *single* other session that has the mode active and clears it, refusing when ambiguous (`findSingleOwningSessionForMode`, `:572-582`); (5) for `team`, also removes `state/team/{teamName}/` runtime dirs and prunes `source === 'team'` entries from the HUD `state/mission-state.json` (`:199-265`). Ownership check `canClearStateForSession` allows clearing files with no owner or matching owner only (`mode-state-io.ts:41-47`). All deletions are per-file try/catch (fail-open, reported as `Warning: Some files could not be removed`).

## notepad_* — three-tier markdown memory (`src/tools/notepad-tools.ts`, engine `src/hooks/notepad/index.ts`)

`.omc/notepad.md` has three `##` sections with different retention semantics (`notepad/index.ts:78-86`):

| Section | Write tool | Semantics | Limits |
|---|---|---|---|
| `## Priority Context` | `notepad_write_priority` | REPLACE; injected at every session start | Zod hard cap 2000 chars; soft warn over `priorityMaxChars: 500` (`notepad/index.ts:281-283`) |
| `## Working Memory` | `notepad_write_working` | APPEND entry headed `### YYYY-MM-DD HH:MM`; pruned after `workingMemoryDays: 7` | Zod cap 4000 chars/entry |
| `## MANUAL` | `notepad_write_manual` | APPEND, never auto-pruned | Zod cap 4000 chars/entry |

`notepad_read` takes `section: 'all'|'priority'|'working'|'manual'`; `notepad_prune` takes `daysOld` (int 1-365, default 7) and rebuilds the Working Memory section keeping entries with `### timestamp >= cutoff` (`notepad/index.ts:391-452`); `notepad_stats` reports byte sizes, entry count, and oldest entry, accepting both the legacy `### ts` and a newer `<!-- WM:YYYY-MM-DD HH:MM -->` delimiter that this version counts but never writes (`:479-483`). Section manipulation is regex-based (`extract`/`replace`/`comment` regexes per header, `:100-106`), preserving the HTML placeholder comment on rewrite. All mutations run under `withFileLockSync(..., { timeoutMs: 5000 })` + atomic write. Notably `DEFAULT_CONFIG.maxTotalSize: 8192` is declared (`:81`) but never enforced anywhere — the file can grow unbounded between prunes.

Injection points (who re-reads it): the `SessionStart` hook `scripts/session-start.mjs:992-1006` regex-extracts Priority Context (stripping placeholder comments) and injects it as a `<notepad-context>` block labeled `[NOTEPAD - Priority Context]`; Working Memory and MANUAL are pull-only via `notepad_read`. The write-side automation is the `<remember>` tag protocol: `processRememberTags` in the delegation PostToolUse path (`src/hooks/omc-orchestrator/index.ts:326-344,471`) scans subagent output for `<remember priority>...</remember>` -> `setPriorityContext` (replace) and `<remember>...</remember>` -> `addWorkingMemoryEntry` (append), so subagents persist discoveries without tool access. The `remember` skill (`skills/remember/SKILL.md`) instructs the model on surface selection: "Prefer project memory for durable team knowledge. Prefer notepad for short-lived working context."

## project_memory_* — auto-detected project profile (`src/tools/memory-tools.ts`)

`.omc/project-memory.json` holds the `ProjectMemory` schema (version `1.0.0`): `techStack` (languages/frameworks/packageManager/runtime), `build` (build/test/lint/dev commands + scripts), `conventions`, `structure` (monorepo/workspaces/branches), `customNotes[]`, `directoryMap`, `hotPaths[]`, `userDirectives[]` (`src/hooks/project-memory/types.ts:6-18`). Four tools:

| Tool | Params | Behavior |
|---|---|---|
| `project_memory_read` | `section: 'all'\|'techStack'\|'build'\|'conventions'\|'structure'\|'notes'\|'directives'`, `workingDirectory` | Dumps JSON; missing file returns guidance to run a session (auto-detect) or `project_memory_write` |
| `project_memory_write` | `memory` (record), `merge` (default false = replace), `workingDirectory` | Backfills `version`/`lastScanned`/`projectRoot` if absent (`memory-tools.ts:135-137`); merge path uses `mergeProjectMemory` |
| `project_memory_add_note` | `category` (max 50), `content` (max 1000) | Appends `{timestamp, source: 'manual', category, content}`; capped at last 20 notes (`learner.ts:271-272`); refuses if memory file absent |
| `project_memory_add_directive` | `directive` (max 500), `context` (max 500), `priority: 'high'\|'normal'` | Appends `{timestamp, directive, context, source: 'explicit', priority}` via `addDirective`, which dedupes case-insensitively and keeps max 20 sorted high-priority-then-recent (`directive-detector.ts:139-152`) |

Lifecycle: the `SessionStart` hook `project-memory-session.mjs` calls `registerProjectMemoryContext` which loads the file and rescans via `detectProjectEnvironment` when `lastScanned` is older than `CACHE_EXPIRY_MS = 24h` (`storage.ts:100-104`, `constants.ts:7`). Rescan merge keeps detection authoritative for schema fields while preserving the three user arrays and any unknown top-level keys written by `project_memory_write` (`project-memory/index.ts:24-42`). The actual context injection is done by `session-start.mjs:970-980` as a `<project-memory-context>` block ([PROJECT MEMORY]); the collector registration inside `registerProjectMemoryContext` (`contextCollector.register`, priority `"high"`) is in-memory only and dies with the hook process — its durable effect is the detect-and-save. Compaction survival: the `PreCompact` hook (`project-memory-precompact.mjs` -> `processPreCompact`, `pre-compact.ts:29-72`) re-injects `formatContextSummary(memory)` as a `systemMessage` titled "Project Memory (Post-Compaction Recovery)" whenever directives/hotPaths/languages/notes exist. Concurrency: `withProjectMemoryLock` file lock (`timeoutMs: 5000`) plus an in-process mutex in the learner; saves are atomic and fail silently with a `console.error` (never break the session, `storage.ts:72-75`).

## shared_memory_* — TTL'd cross-agent KV (`src/tools/shared-memory-tools.ts`, `src/lib/shared-memory.ts`)

Purpose: handoffs between agents in `/team` and pipeline runs. Storage is one JSON file per key: `.omc/state/shared-memory/{namespace}/{key}.json` containing `{key, value, namespace, createdAt, updatedAt, ttl?, expiresAt?}` (`shared-memory.ts:31-41`). Config gate: `agents.sharedMemory.enabled` in `~/.claude/.omc-config.json` — **default true when absent** (opt-out; `shared-memory.ts:63-74`); when disabled every tool returns an `isError` message naming the config key.

| Tool | Params | Notes |
|---|---|---|
| `shared_memory_write` | `key` (1-128), `value` (any JSON), `namespace` (1-128), `ttl` (int 1-604800 s = max 7 days), `workingDirectory` | Preserves original `createdAt` on update; locked read-modify-write with 500ms timeout, falls back to unlocked |
| `shared_memory_read` | `key`, `namespace` | Expired entries are deleted on read and reported as not found |
| `shared_memory_list` | `namespace?` | Without namespace lists namespaces; expired entries filtered but not deleted |
| `shared_memory_delete` | `key`, `namespace` | |
| `shared_memory_cleanup` | `namespace?` | Unlinks expired entries per namespace or across all |

Namespace and key share the same validation: `/^[a-zA-Z0-9][a-zA-Z0-9._-]*$/`, max 128, `..` rejected (`shared-memory.ts:83-106`) — filename-safe by construction, no path resolution of user input.

## session_search — transcript archaeology (`src/tools/session-history-tools.ts`, engine `src/features/session-history-search/index.ts`)

One tool, `session_search`: `query` (required), `limit` (default `DEFAULT_LIMIT = 10`), `sessionId`, `since` (relative `(\d+)[mhdw]` or `Date.parse`-able absolute; `index.ts:46-68`), `project` (`'current'` default | substring filter | `'all'`), `caseSensitive` (default false), `contextChars` (default 120, min 20), `workingDirectory`. Returns raw JSON (`SessionHistorySearchReport`): `{query, scope{mode, project, workingDirectory, since, caseSensitive}, searchedFiles, totalMatches, results[]}` where each match is `{sessionId, agentId?, timestamp?, projectPath?, sourcePath, sourceType, line, role?, entryType?, excerpt}` (`types.ts:13-37`).

Search targets are streamed line-by-line (readline over `createReadStream`, never whole-file loads) and ranked newest-mtime-first: (a) Claude Code project transcripts `~/.claude/projects/{encodedPath}/*.jsonl` — the project path is encoded with `encodeProjectPath` and the target set is widened with the git main-repo root (`git rev-parse --git-common-dir`) and the `.claude/worktrees/` parent so worktree sessions find their real transcript; (b) legacy `~/.claude/transcripts/`; (c) OMC session summaries `.omc/sessions/*.json(l)`; (d) trace replay files `.omc/state/agent-replay-*.jsonl` (`index.ts:141-181`). Transcript entries extract text from `message.content` string or blocks of type `text`/`thinking`/`reasoning`, `tool_result` (string leaves, capped at 24 via `stringLeaves`), and `tool_use` (`"{name} {input leaves}"`) (`index.ts:247-281`). Matching is whitespace-compacted substring, with an AND-of-terms fallback when the full phrase misses (`findMatchIndex`, `:360-375`); one excerpt per entry, ellipsis-trimmed to `contextChars` each side. In `current` scope, entries are additionally filtered to those whose recorded `cwd` lies within the current project roots (`isWithinProject`).

## trace_timeline / trace_summary — agent flow replay (`src/tools/trace-tools.ts`, recorder `src/hooks/subagent-tracker/session-replay.ts`)

The tools are read-only viewers over `.omc/state/agent-replay-{sessionId}.jsonl` (sessionId sanitized `[^a-zA-Z0-9_-] -> _`). Writers are hooks, not the model: `subagent-tracker.mjs start|stop` (SubagentStart/SubagentStop) call `recordAgentStart/Stop` (`subagent-tracker/index.ts:663,854`), the bridge records `file_touch` in the PreToolUse hot path (`bridge.ts:2691`), and `flow-tracer.ts` emits `hook_fire`, `hook_result`, `keyword_detected`, `skill_activated`, `skill_invoked`, `mode_change`. Event schema (`ReplayEvent`): `t` (seconds since session start, 0.1s precision), `agent` (id truncated to 7 chars), `agent_type`, `event` (13-value union), plus per-type fields (`tool`, `file` capped 200 chars, `duration_ms`, `task` capped 100 chars, `success`, `reason`, `model`, `hook`, `hook_event`, `keyword`, `skill_name`, `skill_source`, `mode_from/to`, `context_injected`, `context_length`) (`session-replay.ts:25-61`). Guards: appends stop silently once the file exceeds `MAX_REPLAY_SIZE_BYTES = 5MB`; `cleanupReplayFiles` keeps the `MAX_REPLAY_FILES = 10` newest; `appendReplayEvent` never throws ("Never fail the hook on replay errors", `:163-165`).

`trace_timeline` params: `sessionId` (auto-detects latest replay file by mtime when omitted, `trace-tools.ts:32-48`), `filter: 'all'|'hooks'|'skills'|'agents'|'keywords'|'tools'|'modes'`, `last` (tail N), `workingDirectory`; output is fixed-width `{t}s TYPE detail` lines. `trace_summary` computes `getReplaySummary`: agent spawn/complete/fail counts, per-agent-type breakdown with models, per-tool `{count, total_ms, avg_ms, max_ms}`, bottlenecks (tool+agent combos with >=2 calls averaging >1000ms), files touched, hook/keyword/skill/mode aggregates, a numbered "Execution Flow" narrative from key events, and cycle detection over the agent-type sequence (>= 2 full repeats of a 2..n/2-length pattern, e.g. `planner/critic`; `session-replay.ts:297-323`). The `/trace` skill instructs the model to consult `trace_timeline`/`trace_summary` as existing evidence before spawning tracer agents (`skills/trace/SKILL.md:144-145`).

## Failure philosophy and coupling

Everything in this territory fails open: JSON parse errors return `null`/empty and keep scanning; lock acquisition failures fall back to unlocked writes (shared-memory) or return `{success:false}` (notepad); replay appends and project-memory saves swallow errors so hooks never block the session. The loud-fail exceptions are input validation (session IDs `^[a-zA-Z0-9][a-zA-Z0-9_-]{0,255}$`, path traversal rejection, payload limits) and `workingDirectory` outside the trusted root, which raise tool errors. Coupling: `state_*` is the arm/cancel substrate for the mode-registry and the `persistent-mode` Stop hook (cancel-signal handshake); notepad and project-memory feed the SessionStart and PreCompact context injections; trace files are both a `trace_*` data source and a `session_search` target; the HUD reads `mission-state.json`, which `state_clear(mode:'team')` prunes.

## Patterns for sibling harnesses

- **Session-scoped state with legacy fallback and branded read/write paths**: `state/sessions/{sid}/{name}.json` written session-scoped, read with legacy fallback, TS-branded `ReadPath`/`WritePath` to prevent direction mixups (`worktree-paths.ts:843-921`). Adapt: any harness with parallel sessions on one repo.
- **Cancel-signal-before-delete handshake**: write a 30s-TTL cancel marker before removing state so a concurrently firing keep-alive hook stands down during the deletion window. Adapt: any loop-mode harness with a Stop-hook re-arm race.
- **Ownership-stamped state (`_meta.sessionId`) + evidence-gated orphan cleanup**: only clear a sibling session's file if it embeds your owner id or that session has a durable completion summary on disk. Adapt: multi-session cleanup without clobbering live peers.
- **Three-tier notepad (replace-priority / append-pruned / append-permanent) + `<remember>` tag capture**: regex-sectioned single markdown file; subagent output tags become writes without giving subagents tools. Adapt: omx/omp session notes; keep the 500-char soft warn on the always-injected tier.
- **Detect-24h-TTL + user-array-preserving rescan merge**: machine-detected profile refreshed on staleness, with user contributions (notes/directives, capped at 20, deduped) surviving every rescan, and PreCompact re-injection of directives. Adapt: omp `.omp/` project profiles.
- **Filename-safe KV with per-entry TTL and read-time expiry**: one JSON file per key, charset-validated namespace/key instead of path resolution, expired entries deleted on read. Adapt: cross-worker handoffs in team-style pipelines.
- **Append-only JSONL replay with hard size/count caps and never-throw appends**: 5MB/file, 10 files, hooks write, tools read; summary derives bottlenecks and generator-critic cycle detection from the same log. Adapt: omha routing audit trail.
- **Trusted-root validation from process cwd, not tool args**: treat the MCP server's own cwd git toplevel as the only trusted anchor; silently coerce divergent `workingDirectory` args back to it. Adapt: any MCP server accepting a directory parameter.
- **Category-tagged tool registry with an env kill switch**: single `allTools` array tagged by category, filtered by `OMC_DISABLE_TOOLS` at ListTools time. Adapt: sibling MCP servers needing per-family disablement without code edits.

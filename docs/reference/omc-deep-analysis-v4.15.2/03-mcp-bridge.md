# MCP Bridge Server & Tool Exposure

OMC exposes its entire custom tool surface — LSP code intelligence, AST search/replace, a persistent Python REPL, mode state, notepad, project memory, traces, shared memory, wiki, and skill loaders — through a single stdio MCP server registered under the one-character name `t`. The server is a committed esbuild bundle (`bridge/mcp-server.cjs`) launched directly from the plugin manifest via `${CLAUDE_PLUGIN_ROOT}`, so a plugin-cache install needs no `npm install`, no build step, and no PATH-visible binary. The same `bridge/` directory also carries the bundled `omc` CLI (`cli.cjs`, npm bin `omc-cli`), the team runtime bundles, and one genuinely handwritten runtime file: a Python JSON-RPC bridge. This section covers the wiring, the bundling strategy, the tool registry and dispatch machinery, lifecycle guards, the configuration surface, and why OMC converged from multiple MCP servers to one.

## Registration and wiring

The plugin manifest points at a standard MCP config file: `".mcpServers": "./.mcp.json"` (.claude-plugin/plugin.json — `"mcpServers": "./.mcp.json"` is the second-to-last key, followed by `"commands": "./commands/"`). That file registers exactly one server:

```json
{
  "mcpServers": {
    "t": {
      "command": "node",
      "args": ["${CLAUDE_PLUGIN_ROOT}/bridge/mcp-server.cjs"]
    }
  }
}
```

(.mcp.json — whole-file). `${CLAUDE_PLUGIN_ROOT}` is expanded by Claude Code to the installed plugin cache directory; nothing inside `src/tools/` or `src/mcp/` reads that env var at runtime — once launched, the server resolves sibling assets via `__dirname`-relative paths (e.g. `bridge/gyoshu_bridge.py`, see below). Tools surface to the model as `mcp__t__<tool_name>` (src/mcp/omc-tools-server.ts:74 "Tools will be available as mcp__t__<tool_name>"); under a plugin-scoped install Claude Code additionally prefixes the plugin name, yielding `mcp__plugin_oh-my-claudecode_t__<tool_name>` (observed in a live v4.15.x install). The one-character server name is a deliberate token economy: the server name is embedded in every tool name the model sees and every `allowedTools` entry.

## bridge/ inventory: generated vs handwritten

`bridge/` is ~172k lines, but ~98.6% of it is committed esbuild output. Only two files are handwritten runtime assets.

| File | Lines | Kind | Source entry point | Build script |
|---|---|---|---|---|
| `bridge/cli.cjs` | 96,315 | generated CJS bundle | `src/cli/index.ts` | `scripts/build-cli.mjs` |
| `bridge/mcp-server.cjs` | 29,050 | generated CJS bundle | `src/mcp/standalone-server.ts` | `scripts/build-mcp-server.mjs` |
| `bridge/team-mcp.cjs` | 20,209 | generated CJS bundle (retired runtime) | `src/mcp/team-server.ts` | `scripts/build-team-server.mjs` |
| `bridge/team.js` | 12,436 | generated ESM bundle | `src/cli/team.ts` | `scripts/build-cli.mjs` (second config) |
| `bridge/runtime-cli.cjs` | 10,295 | generated CJS bundle | `src/team/runtime-cli.ts` | `scripts/build-runtime-cli.mjs` |
| `bridge/team-bridge.cjs` | 2,501 | generated CJS bundle | `src/team/bridge-entry.ts` | `scripts/build-bridge-entry.mjs` |
| `bridge/gyoshu_bridge.py` | 1,171 | handwritten Python | n/a (runtime asset) | n/a |
| `bridge/run-mcp-server.sh` | 13 | handwritten shell, vestigial | n/a | n/a |

Analysis belongs in `src/` — the `.cjs` files are mechanical output. `run-mcp-server.sh` (a `NODE_PATH` wrapper that `exec node "$SCRIPT_DIR/mcp-server.cjs"`) is referenced nowhere in the repo; its job was absorbed into the JS banner described next, so it is vestigial. `gyoshu_bridge.py` is active: it implements "JSON-RPC 2.0 over Unix Socket (or TCP on Windows)" with NDJSON framing and methods `execute(code, timeout)`, `interrupt()`, `reset()`, `get_state()`, `ping()` (bridge/gyoshu_bridge.py:2-21), and is spawned per session by the `python_repl` tool's bridge manager.

## Bundling strategy

All bridge bundles share one esbuild recipe (scripts/build-mcp-server.mjs): `bundle: true, platform: 'node', target: 'node18', format: 'cjs'`, `mainFields: ['module', 'main']` ("Prefer ESM entry points so UMD packages (e.g. jsonc-parser) get properly bundled"), and Node built-ins plus native modules externalized: `'@ast-grep/napi', 'better-sqlite3'` cannot be bundled (scripts/build-mcp-server.mjs:46-55). The comment in each build script states the intent: "Output to bridge/ directory (not gitignored) for plugin distribution" — i.e., the bundles are committed to git so the plugin marketplace cache is runnable as-checked-out. Note the asymmetry with `dist/`: `.gitattributes` marks only `dist/**` as `linguist-generated=true`; the equally generated `bridge/*.cjs` files are not so marked.

Because native deps are externalized, the MCP server and team bundles are prefixed with a **global-npm resolution banner** injected at build time:

```js
var _globalRoot = _cp.execSync('npm root -g', { encoding: 'utf8', timeout: 5000 }).trim();
if (_globalRoot) { process.env.NODE_PATH = _globalRoot + ...; _Module._initPaths(); }
} catch (_e) { /* npm not available - native modules will gracefully degrade */ }
```

(scripts/build-mcp-server.mjs:18-31, emitted at bridge/mcp-server.cjs:1-13). This lets a globally installed `@ast-grep/napi` be `require()`d from inside the plugin cache; if npm is absent it fails open and the AST tools degrade at call time. The CLI bundle instead gets a CJS `import.meta.url` polyfill banner: `const importMetaUrl = require("url").pathToFileURL(__filename);` with `define: { 'import.meta.url': 'importMetaUrl' }` (scripts/build-cli.mjs:27-33).

The full build is `tsc` (→ `dist/`, the ESM npm library) plus five esbuild passes: `build-skill-bridge.mjs` (→ `dist/hooks/skill-bridge.cjs`, a CJS bundle hook scripts can `require()`), `build-mcp-server.mjs`, `build-bridge-entry.mjs`, `build-runtime-cli.mjs`, `build-team-server.mjs`, `build-cli.mjs` (package.json `"build"`). Every script accepts `--watch` (esbuild `context().watch()`), and `dev:full` runs all seven watchers under `concurrently`. `prepublishOnly` re-runs the build, and the npm `files` allowlist ships `bridge` explicitly (package.json:20-27).

## Standalone server: architecture and dispatch

`src/mcp/standalone-server.ts` (121 lines) is deliberately thin. It constructs `new Server({ name: 't', version: '1.0.0' }, { capabilities: { tools: {} } })` (standalone-server.ts:33-43 — note the version is pinned at `1.0.0`, not the plugin version) over `StdioServerTransport`, and delegates everything to the registry:

```
.mcp.json ── node bridge/mcp-server.cjs (bundle of standalone-server.ts)
                 │
                 ├─ ListToolsRequest ──► buildListToolsResponse()          (tool-registry.ts:161)
                 │                         └─ getEnabledTools(env) ─ filterDisabledTools(allTools)
                 │                         └─ zodToJsonSchema(tool.schema) per tool
                 └─ CallToolRequest ───► getEnabledTools().find(t => t.name === name)
                                           ├─ not found → { isError:true, "Unknown tool: <name>" }
                                           ├─ tool.handler(args ?? {}) → { content, isError ?? false }
                                           └─ throw → { isError:true, "Error: <message>" }
```

(standalone-server.ts:46, 53-77). The registry (`src/mcp/tool-registry.ts`) is the "Single source of truth for the tool surface" and was "Extracted here so tests can import the same aggregation path without triggering server-side effects (Server construction, transport startup, process.exit hooks)" (tool-registry.ts:4-6) — the ListTools test exercises `buildListToolsResponse()` directly. Each tool is a `ToolDef { name, description, category?, annotations?, schema, handler }` where `schema` is a Zod raw shape and `annotations` carries MCP hints `readOnlyHint/destructiveHint/idempotentHint/openWorldHint` (tool-registry.ts:35-49; e.g. state_read is `{ readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false }`, state-tools.ts:595).

Schema conversion is a **hand-rolled Zod-to-JSON-Schema walker** (tool-registry.ts:75-147): it handles `ZodOptional` (unwrap), `ZodDefault` (unwrap + `default`), string/number (`int` check → `"integer"`), boolean, array, enum, nested object, and record; anything unrecognized falls back to `{ type: 'string' }`, and `required` is computed from `isOptional()`. No dependency on `zod-to-json-schema` — the wire format is fully owned.

Error posture is uniformly fail-soft at the request level (every failure becomes an `isError: true` text envelope, never a transport crash) and fail-loud at startup (`main().catch(... process.exit(1))`, standalone-server.ts:118-121). AST tools are "always present in the registry but return a helpful error message instead of results" when `@ast-grep/napi` is missing (tool-registry.ts:8-10) — presence is static, capability is dynamic.

## Tool surface (49 tools, 11 families)

| Category (`TOOL_CATEGORIES`, src/constants/names.ts:20-36) | Tools | Names |
|---|---|---|
| `lsp` | 12 | `lsp_servers`, `lsp_diagnostics`, `lsp_diagnostics_directory`, `lsp_hover`, `lsp_goto_definition`, `lsp_find_references`, `lsp_document_symbols`, `lsp_workspace_symbols`, `lsp_code_actions`, `lsp_code_action_resolve`, `lsp_prepare_rename`, `lsp_rename` |
| `ast` | 2 | `ast_grep_search`, `ast_grep_replace` |
| `python` | 1 | `python_repl` |
| `state` | 5 | `state_read`, `state_write`, `state_clear`, `state_get_status`, `state_list_active` |
| `notepad` | 6 | `notepad_read`, `notepad_write_working`, `notepad_write_priority`, `notepad_write_manual`, `notepad_prune`, `notepad_stats` |
| `memory` | 4 | `project_memory_read`, `project_memory_write`, `project_memory_add_note`, `project_memory_add_directive` |
| `trace` | 3 | `trace_timeline`, `trace_summary`, `session_search` (folded in via trace-tools.ts:466) |
| `shared-memory` | 5 | `shared_memory_read/write/list/delete/cleanup` |
| `deepinit` | 1 | `deepinit_manifest` |
| `wiki` | 7 | `wiki_add`, `wiki_read`, `wiki_query`, `wiki_list`, `wiki_delete`, `wiki_ingest`, `wiki_lint` |
| `skills` | 3 | `list_omc_skills`, `load_omc_skills_local`, `load_omc_skills_global` |

Registration order is fixed in `allTools` (tool-registry.ts:52-64); `tagCategory()` stamps the category onto every member of a family so filtering never relies on name prefixes (disable-tools.ts:57-62, "Uses category metadata instead of string heuristics", omc-tools-server.ts:158).

A subtle import footgun is documented in the registry itself: `python_repl` must be imported from `tool.js`, "NOT index.js! tool.js exports pythonReplTool with wrapped handler returning { content: [...] } / index.js exports pythonReplTool with raw handler returning string" (tool-registry.ts:18-21) — the in-process SDK server intentionally uses the raw one.

## Dual exposure: stdio bundle and in-process SDK server

The same tool families are exposed twice, for two runtimes:

1. **Plugin path (active for Claude Code users)** — the stdio bundle described above.
2. **Library path** — `src/mcp/omc-tools-server.ts` builds `omcToolsServer = createSdkMcpServer({ name: "t", version: "1.0.0", tools: sdkTools })` using `@anthropic-ai/claude-agent-sdk`'s `tool()` helper (omc-tools-server.ts:77-81). `createOmcSession()` injects it as `mcpServers: { ..., 't': omcToolsServer }` (src/index.ts:359-361) and computes `allowedTools` from `omcToolNames` (`mcp__t__<name>`, omc-tools-server.ts:87). Only this path can include the eight `interop_*` tools (task/message exchange with OMX teams), gated by `process.env.OMC_INTEROP_TOOLS_ENABLED === '1'` (omc-tools-server.ts:37-40); the standalone registry deliberately omits them.

Both paths share `filterDisabledTools`/`tagCategory` from `src/mcp/disable-tools.ts`, so the `OMC_DISABLE_TOOLS` kill switch behaves identically. In the SDK path filtering happens **once at module load** (omc-tools-server.ts:57-58); in the standalone path `getEnabledTools()` re-reads the env on every ListTools/CallTool, which makes tests deterministic and would honor env changes per request.

## Lifecycle and shutdown guards

The standalone server's biggest operational hazard is orphaning child processes — LSP servers (`jdtls` etc.) and the Python bridge outlive a dead MCP server. Two layers address this:

- `gracefulShutdown(signal)` (standalone-server.ts:82-105): arms a hard deadline `setTimeout(() => process.exit(1), 5_000)` (unref'ed) so cleanup can never hang the exit, then best-effort `cleanupOwnedBridgeSessions()` (Python bridge: SIGINT → 5000 ms grace → SIGTERM → 2500 ms → SIGKILL escalation; `DEFAULT_GRACE_PERIOD_MS = 5000` / `SIGTERM_GRACE_MS = 2500`, bridge-manager.ts:31-33), `disconnectAllLsp()`, `server.close()`, `process.exit(0)`. The comment cites the motivating bug: "Without this, LSP child processes (e.g. jdtls) survive the MCP server exit and become orphaned, consuming memory indefinitely" (#768).
- `registerStandaloneShutdownHandlers` (src/mcp/standalone-shutdown.ts:43-99) covers the implicit deaths signals miss: it hooks `SIGTERM`, `SIGINT`, `disconnect`, **`stdin end` and `stdin close`** (the normal way an MCP host drops a stdio server), and additionally polls the parent PID every `pollIntervalMs` (default 1000 ms, floor 100 ms): if `ppid` becomes `<= 1` or changes, it triggers `parent pid changed (old -> new)` shutdown. The poll timer is unref'ed and shutdown is idempotent via a cached promise.

The Python bridge manager adds its own guards: single bridge per session with a lock file, "PID reuse detection via process identity verification" (start-time comparison via `getProcessStartTime`), a 30 s socket-appearance timeout (`BRIDGE_SPAWN_TIMEOUT_MS = 30000`), and an `OMC_BRIDGE_SCRIPT` override that is validated to basename `gyoshu_bridge.py` and existence before use (bridge-manager.ts:92-101). Path resolution tries ESM `import.meta.url`, falls back to `__dirname` for the CJS bundle, then probes both `<package-root>/bridge/gyoshu_bridge.py` and `<moduleDir>/gyoshu_bridge.py` — in the bundle, `__dirname` *is* `bridge/`, which is why the Python file must ship beside the bundle (bridge-manager.ts:105-137).

## Configuration surface

| Env var | Default | Effect | Evidence |
|---|---|---|---|
| `OMC_DISABLE_TOOLS` | unset | Comma-separated, case-insensitive group names remove whole categories from ListTools and dispatch; unknown names silently ignored. Aliases: `python-repl`→python, `project-memory`→memory, `deepinit-manifest`→deepinit | disable-tools.ts:7-55 |
| `OMC_INTEROP_TOOLS_ENABLED` | unset | `'1'` adds `interop_*` tools (SDK in-process server only) | omc-tools-server.ts:37 |
| `OMC_BRIDGE_SCRIPT` | unset | Absolute path override for `gyoshu_bridge.py`; validated basename + existence | bridge-manager.ts:92-101 |
| `OMC_JOBS_DIR` | global OMC state `team-jobs` dir | Where team job JSON envelopes persist | team-server.ts:39, cli/team.ts:191 |
| `OMC_RUNTIME_CLI_PATH` | `<moduleDir>/../../bridge/runtime-cli.cjs` | Override the team runtime bundle path | cli/team.ts:195-201 |
| `OMC_MCP_OUTPUT_PATH_POLICY` | `strict` | `strict` or `redirect_output` (vestigial, see below) | mcp-config.ts:5-48 |
| `OMC_MCP_OUTPUT_REDIRECT_DIR` | `.omc/outputs` | Redirect dir for the above | mcp-config.ts:66 |
| `OMC_MCP_ALLOW_EXTERNAL_PROMPT` | `0` | `1`/`true` allows prompt files outside cwd, logs a security warning | mcp-config.ts:67-78 |
| `OMC_MCP_REGISTRY_PATH` | `mcp-registry.json` in global OMC config | Unified MCP registry the installer syncs into `.claude.json` and Codex `config.toml` | installer/mcp-registry.ts:53-55 |
| `CLAUDE_MCP_CONFIG_PATH` | `<claude-config-parent>/.claude.json` | Override Claude's MCP config location for installer sync | installer/mcp-registry.ts:74-79 |
| `OMC_PLUGIN_ROOT` | unset | Set by `omc --plugin-dir`; disambiguates plugin root for HUD/setup, warns on conflict | cli/index.ts:71-97, lib/env-vars.ts:2 |

## Why one server with many tools

OMC demonstrably ran multiple MCP servers and retreated from all of them:

- **Provider servers removed**: `src/team/bridge-entry.ts:3-5` — "@deprecated The MCP x/g servers have been removed" (x = Codex, g = Gemini). Their support machinery survives as library-only code: `src/mcp/job-management.ts` ("four tools for managing background Codex/Gemini jobs: wait_for_job, check_job_status, kill_job, list_jobs... each server hardcodes its provider") and `src/mcp/prompt-persistence.ts` (`.omc/prompts/` audit trail, SQLite-with-JSON-fallback job DB) are re-exported from the `src/mcp/index.ts` barrel (index.ts:50/57/67) but have **no non-test consumers** — only their own `src/__tests__/*` and `src/lib/job-state-db.ts` reference them, so no active runtime path reaches them (vestigial). The `codex`/`gemini`/`antigravity` entries in `DISABLE_TOOLS_GROUP_MAP` map to categories no registered tool carries.
- **Team server retired to CLI-only**: `bridge/team-mcp.cjs` (from `src/mcp/team-server.ts`) still builds and ships, but its four tools `omc_run_team_start/status/wait/cleanup` are hard-deprecated: every call returns `isError: true` with `{ code: 'deprecated_cli_only', ..., cli_replacement: 'omc team start --name ... --task ...' }` — the handler even reconstructs the exact CLI command from the caller's arguments (team-server.ts:41-208). It is not registered in `.mcp.json`; docs describe manual opt-in registration only (docs/REFERENCE.md:618-627), and the installer actively **scrubs** old registrations via `RETIRED_TEAM_MCP_PATH_PATTERN = /(^|[\\/])bridge[\\/]+team-mcp\.cjs$/i`, dropping any registry entry whose args match (installer/mcp-registry.ts:93-128).

What remains is a single server whose granularity knob is the category filter (`OMC_DISABLE_TOOLS`), not server multiplication. The practical rationale visible in the code: one server means one child process per Claude session (each MCP server is a spawned process with its own startup cost and failure mode), one shutdown story for shared children (LSP/Python), one registry to test, and — with the name `t` — minimal token overhead on the `mcp__<server>__<tool>` names that appear in every tool list and permission entry. Long-running orchestration was moved out of MCP entirely to the `omc team` CLI, because a stdio MCP server dies with its session while tmux-based teams must not.

## The omc-cli bridge entry

`bridge/cli.cjs` is the bundled `omc` CLI. It is wired three ways: npm bins `"omc"`/`"oh-my-claudecode"` → `bin/oh-my-claudecode.js`, which is a single line `import '../bridge/cli.cjs';`, and a third bin `"omc-cli": "bridge/cli.cjs"` directly (package.json:12-16). The commander program (src/cli/index.ts) defaults bare `omc` to `launchCommand` (tmux-integrated Claude launch), and registers `launch`, `interop`, `ask`, `config`, `team`, `ultragoal`, `wait*`, `doctor-*`, `session-search`, `teleport*`, `ralphthon`, `autoresearch`, hud-watch, etc.

The key bridge pattern is **CLI availability without installation**: `src/utils/omc-cli-rendering.ts:4` defines `OMC_PLUGIN_BRIDGE_PREFIX = 'node "$CLAUDE_PLUGIN_ROOT"/bridge/cli.cjs'`; `resolveOmcCliPrefix()` probes `which omc` and, if absent but `CLAUDE_PLUGIN_ROOT` is set, rewrites every rendered command to the bridge form. Team worker bootstrap prompts are rendered through `formatOmcCliInvocation('team api claim-task ...')` etc. (src/team/worker-bootstrap.ts:80-158), so tmux workers in plugin-only installs still get runnable coordination commands. The team runtime itself is another bundle boundary: `src/cli/team.ts:195-201` resolves `bridge/runtime-cli.cjs` (overridable via `OMC_RUNTIME_CLI_PATH`) and spawns it as a detached daemon that "Reads JSON config from stdin ... writes structured JSON result to stdout" (src/team/runtime-cli.ts:1-7). `bridge/team-bridge.cjs` (from `src/team/bridge-entry.ts`) is the per-worker tmux daemon entry (`--config /path/to/config.json`), which validates its config path against home/`.omc`/Claude-config prefixes with `realpathSync` symlink defeat before trusting it (bridge-entry.ts:28-58).

Also thin/vestigial in `src/mcp/`: `servers.ts` is a set of `npx`-based config factories (`createExaServer`, `createContext7Server`, `createPlaywrightServer`, `createFilesystemServer`, `createMemoryServer`) for SDK library users — data-only, no active plugin wiring; `mcp-config.ts`'s output-path policy has no consumers outside the barrel export and belongs to the removed provider servers.

## Patterns for sibling harnesses

- **Single short-named MCP server, category-tagged tools**: register one stdio server (name it one or two characters), tag every tool with a category constant, and filter by category via one env var (`OMC_DISABLE_TOOLS` semantics: comma list, case-insensitive, aliases, unknown names ignored). Adaptation: omx/omp can expose their CLI verbs as one `x`/`p` server instead of per-feature servers.
- **Registry/server split for testability**: keep the tool list, env filtering, and JSON-schema rendering in a side-effect-free module (`tool-registry.ts`) and make the server a 100-line shell; tests call `buildListToolsResponse()` instead of spawning a process. Adaptation: any harness adding MCP tools should make ListTools output a pure function of (registry, env).
- **Committed esbuild bundle + `${CLAUDE_PLUGIN_ROOT}` launch**: bundle the server to a checked-in `.cjs` with Node built-ins and native modules external, and launch via `node ${CLAUDE_PLUGIN_ROOT}/...` — zero install steps in the plugin cache. Adaptation: sibling harnesses distributing via plugin marketplace should commit bundles, not require `npm ci`.
- **`npm root -g` NODE_PATH banner for native deps**: when a bundle needs an unbundleable native module, prepend a fail-open banner that appends the global npm root to `NODE_PATH` and `_initPaths()`. Adaptation: use for any `better-sqlite3`-class dependency; pair with runtime degradation messages instead of import-time crashes.
- **Orphan-proof shutdown**: handle not just SIGTERM/SIGINT but `stdin end/close`, `disconnect`, and a ppid-change poll, with an unref'ed 5 s force-exit deadline and idempotent shutdown promise. Adaptation: mandatory for any harness whose MCP server spawns children (LSP, Python, tmux).
- **Deprecate tools in-band with executable replacements**: retired tools return `isError: true` JSON `{ code, message, cli_replacement }` where `cli_replacement` is reconstructed from the actual call args — the model can self-migrate mid-session. Pair with an installer-side scrub regex that removes stale registrations. Adaptation: omha/omx should sunset hooks/tools this way rather than deleting them silently.
- **CLI-prefix rendering fallback**: render agent-facing commands through a resolver that emits the bare binary when on PATH and `node "$CLAUDE_PLUGIN_ROOT"/bridge/cli.cjs` otherwise. Adaptation: any harness whose prompts embed its own CLI must render, not hardcode, the invocation.
- **Sidecar interpreter over JSON-RPC/NDJSON**: for a persistent non-JS runtime, ship one handwritten script (Unix socket, JSON-RPC 2.0, `execute/interrupt/reset/get_state/ping`) next to the bundle and resolve it `__dirname`-relative with a validated env override. Adaptation: oms/omx analysis engines needing persistent Python state can lift `gyoshu_bridge.py`'s protocol wholesale.

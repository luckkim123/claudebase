# CLI & Multi-Model Interop: the omc CLI, ask/ccg, provider contracts, OMX interop, and OpenClaw

This section covers OMC's terminal-facing surface and everything that lets it talk to *other* model CLIs: the `omc` command-line program and its subcommands, the `omc ask` advisor pipeline that shells out to Claude/Codex/Gemini/Antigravity/Grok/Cursor with artifact capture, the `ccg` tri-model orchestration skill, the CLI-agent contract layer that abstracts external model binaries, the OMC-OMX (oh-my-codex) shared-state interop channel, and OpenClaw, an outbound hook-event gateway waker. One correction to the fleet map up front: `src/providers/` is NOT the model-provider adapter layer — it is a *git hosting* provider abstraction (GitHub/GitLab/Bitbucket/Azure DevOps/Gitea) used by `omc teleport` (src/providers/types.ts:1-16). The real model-CLI adapters live in `src/team/model-contract.ts` and `scripts/run-provider-advisor.js`; both are covered here.

## 1. Binary entry points and build wiring

`package.json` declares three bins: `"oh-my-claudecode"` and `"omc"` both point at `bin/oh-my-claudecode.js`, and `"omc-cli"` points at `bridge/cli.cjs` (package.json:14-17). The bin shim is two lines — `import '../bridge/cli.cjs'` (bin/oh-my-claudecode.js:1-2). `bridge/cli.cjs` (~96k lines) is an esbuild CJS bundle of `src/cli/index.ts` (scripts/build-cli.mjs:6, entryPoints `['src/cli/index.ts']` at :21), with node built-ins plus `@ast-grep/napi`, `better-sqlite3`, `jsonc-parser` marked external and an `import.meta.url` polyfill banner. So all three bins run the same commander program; `src/cli/` is the source of truth.

`src/cli/index.ts` builds a commander `program` named `omc` with `.allowUnknownOption()` and a default action that forwards raw argv to `launchCommand` — except when `args[0] === 'ask'`, which is routed to `askCommand` *before* launch (src/cli/index.ts:104-116). That carve-out exists because `launchCommand` hard-fails on nested sessions (`if (process.env.CLAUDECODE) { ... exit(1) }`, src/cli/launch.ts:763-766) and `omc ask` is expressly meant to be run *from inside* a Claude Code session. A test seam `OMC_CLI_SKIP_PARSE` suppresses `program.parse()` on import (src/cli/index.ts:1520-1522); `buildProgram()` exports the singleton for in-process testing (:1511-1513). `warnIfWin32()` prints a tmux warning on native Windows at startup (:100).

### Command surface

| Command | Purpose (source) |
|---|---|
| `omc` / `omc launch [args...]` | Launch Claude Code with tmux integration; OMC flags stripped, rest passed through (src/cli/launch.ts) |
| `omc ask <provider> <prompt>` | External-model advisor with artifact capture (src/cli/ask.ts) |
| `omc interop` | Split-pane tmux: Claude left, Codex right, shared state (src/cli/interop.ts) |
| `omc team [args...]` | Team worker lifecycle API (src/cli/commands/team.ts; separate territory) |
| `omc config` / `config-stop-callback <type>` / `config-notify-profile` | Show config; configure file/telegram/discord/slack/webhook stop callbacks and named `notificationProfiles` (src/cli/index.ts:185-652) |
| `omc info` / `test-prompt` / `version` | Introspection: agents, features, magic-keyword detection dry-run |
| `omc install` / `setup` / `postinstall` (hidden) / `update` / `update-reconcile` | Installer/updater lifecycle; `setup --plugin-dir-mode` skips agent/skill copy when `OMC_PLUGIN_ROOT` set (:1293-1305) |
| `omc wait [status|daemon|detect]` | Rate-limit wait + auto-resume daemon (default poll 60s) |
| `omc teleport <ref>` / `list` / `remove` | Git-worktree creation from `'#123'`/branch/URL, default path `~/Workspace/omc-worktrees/` |
| `omc session search|friction report` | Local transcript search and context-bloat report |
| `omc doctor [conflicts|team-routing]` | Diagnostics; `--plugin-dir` preAction hook sets `OMC_PLUGIN_ROOT` (:1209-1211) |
| `omc hud [--watch --interval <ms>]` / `mission-board` | HUD statusline renderer / mission board snapshot |
| `omc ralphthon` / `ultragoal` | Autonomous lifecycle commands (other territories) |
| `omc autoresearch` | **Hard-deprecated shim**, prints migration message only (src/cli/index.ts:1451-1462) |

### Launch flag extraction (OMC-only flags never reach `claude`)

`launchCommand` peels presence-based flags in a fixed chain before arg passthrough: `--notify <bool>` → `OMC_NOTIFY=0` when false; `--openclaw[=bool]` → `OMC_OPENCLAW=1|0`; `--telegram|--discord|--slack|--webhook[=bool]` → `OMC_TELEGRAM|OMC_DISCORD|OMC_SLACK|OMC_WEBHOOK` (src/cli/launch.ts:715-760). `--madmax`/`--yolo` map to Claude's `--dangerously-skip-permissions` and on macOS *require* tmux (`abortMadmaxRequiresTmux`, :437-449). `--plugin-dir <path>` is captured *non-consuming* into `OMC_PLUGIN_ROOT` and still flows to Claude (:706-712). Launch policy resolves to `inside-tmux | outside-tmux | direct`; `--print`/`-p` always forces direct so stdout pipes survive (issue #1665, :467-470). Because `tmux new-session` inherits the tmux *server's* env, the `TMUX_ENV_FORWARD` list (`CLAUDE_CONFIG_DIR`, `OMC_NOTIFY`, `OMC_OPENCLAW`, `OMC_TELEGRAM`, `OMC_DISCORD`, `OMC_SLACK`, `OMC_WEBHOOK`, `OMC_PLUGIN_ROOT`) is injected as `export` statements into the pane shell command (:546-556). `prepareOmcLaunchConfigDir` builds a disposable runtime config dir `~/.claude/.omc-launch/` — symlink-mirroring `agents/commands/hooks/.../settings.json/.credentials.json` and promoting `CLAUDE-omc.md` (gated on `<!-- OMC:START -->`/`<!-- OMC:END -->` markers) to its `CLAUDE.md` — then points `CLAUDE_CONFIG_DIR` at it (:120-186, 777-782).

## 2. `omc ask` — the advisor pipeline

```
omc ask codex "review this patch"
  └─ src/cli/ask.ts: parse → security gate → persona injection
       └─ spawnSync(node, [scripts/run-provider-advisor.js, provider, finalPrompt],
                    env + OMC_ASK_ORIGINAL_TASK=<raw task>)
            └─ ensureBinary(--version probe) → buildProviderArgs → spawnSync(binary,...)
                 └─ writeArtifact(.omc/artifacts/ask/<provider>-<slug>-<ts>.md)
                      └─ prints artifactPath on stdout; non-zero exit propagated
```

**Providers and parsing.** `ASK_PROVIDERS = ['claude','codex','gemini','antigravity','grok','cursor']` (src/cli/ask.ts:18). Prompt forms: positional words, `-p|--print|--prompt <text>`, or `--agent-prompt <role>` which prepends a persona file `<promptsDir>/<role>.md` to the prompt (role gated by `SAFE_ROLE_PATTERN /^[a-z][a-z0-9-]*$/`, :23). The prompts dir resolves in order: `$CODEX_HOME/prompts` → `.omx/setup-scope.json` with `scope: "project"|"project-local"` → `<cwd>/.codex/prompts` → `<packageRoot>/agents` (:65-88) — a deliberate OMX compatibility shim. The advisor script path is overridable via `OMC_ASK_ADVISOR_SCRIPT` (deprecated alias `OMX_ASK_ADVISOR_SCRIPT` warns), default `scripts/run-provider-advisor.js` (:183-199). Signal deaths map to `128 + signo` exit codes (:201-210).

**Security gate.** Any non-`claude` provider throws when `isExternalLLMDisabled()` (:215-220). That flag comes from the unified security config: `DEFAULTS` all-off, `OMC_SECURITY=strict` applies `STRICT_OVERRIDES` (`disableExternalLLM: true`, `hardMaxIterations: 200`, `disableRemoteMcp: true`, ...), then a `security` section in `.claude/omc.jsonc` (project) or `<configDir>/claude-omc/config.jsonc` (user) is merged last — but **in strict mode config can only TIGHTEN, never relax** (`base.x || fileOverrides.x`, `Math.min` for `hardMaxIterations`); in non-strict mode the file has plain highest precedence (src/lib/security-config.ts:39-56,89-110). The same gate is enforced again inside `getContract()` for team workers (src/team/model-contract.ts:314-319) — one kill switch, two chokepoints.

**Per-provider invocation** (scripts/run-provider-advisor.js:8-15,54-81). Every provider is run in its *own* full-autonomy mode — OMC treats the advisor as disposable and unsandboxed by design:

| Provider | Binary | Argv (verbatim) | Prompt via stdin? |
|---|---|---|---|
| claude | `claude` | `-p <prompt>` or bare `-p` | yes if multiline, >500 chars, or leading `-` (YAML frontmatter breaks argv parsing, issue #3221) |
| codex | `codex` | `exec --dangerously-bypass-approvals-and-sandbox <prompt|->` | yes if multiline/>500 chars, always on win32 |
| gemini | `gemini` | `-p <prompt> --yolo` | same rule as codex |
| antigravity | `agy` | `--dangerously-skip-permissions -p <prompt>` | never — `-p` requires the prompt as its argv VALUE (verified agy 1.0.10) |
| grok | `grok` | `-p <prompt> --always-approve` | never — grok stdin is reserved for ACP JSON-RPC |
| cursor | `cursor-agent` | `--print --force --trust --sandbox disabled <prompt>` | never — stdin kept closed |

**Session hygiene.** The child env strips `CLAUDECODE`, `CLAUDE_SESSION_ID`, `CLAUDECODE_SESSION_ID`, `CLAUDE_CODE_ENTRYPOINT` so the advisor CLI cannot detect or inherit the live Claude session; codex additionally strips `RUST_LOG`, `RUST_BACKTRACE`, `RUST_LIB_BACKTRACE` (run-provider-advisor.js:163-179).

**Antigravity hardening (the most defensive code in the file).** Upstream bug antigravity-cli#76 makes `agy` headless mode either hang forever or exit 0 with empty output. OMC bounds the subprocess with `timeout: 300000` ms (override `OMC_ANTIGRAVITY_TIMEOUT_MS`, validated as integer >= 1000, clamped <= 3600000, invalid values warn and fall back) and `killSignal: 'SIGKILL'` — SIGKILL because `spawnSync` will not return if a signal-trapping child ignores SIGTERM (:25-40,322-331). Post-run, a zero-exit with empty combined output is *coerced to exit 1* so "(no output)" can never be recorded as success (:347-356). On Windows, antigravity is refused outright with a message redirecting to `omc ask gemini` (`guardProviderPlatform`, :187-195).

**Artifact capture.** Output (stdout+stderr, `maxBuffer` 10 MiB) is always persisted — success or failure — to `<stateRoot>/artifacts/ask/<provider>-<slug>-<timestamp>.md`, where stateRoot honors `OMC_STATE_DIR` and defaults to `<cwd>/.omc` (scripts/lib/state-root.mjs:32-53), the slug is the lowercased task truncated to 60 chars, and the timestamp is ISO with `:`/`.` replaced by `-` (run-provider-advisor.js:124-134,267-311). The artifact template has fixed sections: `## Original task` (from `OMC_ASK_ORIGINAL_TASK`, so persona-prefixed prompts still record the raw user task), `## Final prompt`, `## Raw output` in a `text` fence, `## Concise summary`, `## Action items`. The artifact path is the script's last stdout line, which is what the calling agent reads.

**Skill wrapper.** `skills/ask/SKILL.md` mandates `omc ask {{ARGUMENTS}}` and explicitly forbids hand-assembling provider CLI flags: "Do NOT manually construct raw provider CLI commands ... will produce incorrect or outdated invocations" (skills/ask/SKILL.md:28-34). `commands/ask.md` is a lazy dispatch shim ("read `skills/ask/SKILL.md` and follow it") so the full skill text is not loaded into every session (commands/ask.md:8-16).

## 3. `ccg` — tri-model orchestration as a prompt protocol

CCG (Claude-Codex-Gemini) has **no code path in src/** — it is entirely a skill-layer protocol (skills/ccg/SKILL.md, `level: 5`). Flow: (1) Claude decomposes the request into a Codex prompt (architecture/correctness/backend/risks/tests) and an Antigravity prompt (UX/content/alternatives/docs), (2) runs `omc ask codex "..."` and `omc ask antigravity "..."` via Bash — with `omc ask gemini` as the documented enterprise fallback — because "skill nesting ... is not supported in Claude Code" (SKILL.md:58-73), (3) reads the newest `.omc/artifacts/ask/{codex,antigravity,gemini}-*.md`, (4) synthesizes one answer with agreed vs conflicting recommendations called out. Degradation is graceful and explicit: one provider missing → continue and note the gap; both missing → Claude-only answer with a disclosure (SKILL.md:94-103). It is armed by the keyword detector at priority 8.5 via regex `/\b(ccg|claude-codex-gemini)\b|(씨씨지)|(シーシージー)/i` (src/hooks/keyword-detector/index.ts:35,62). The tri-model pattern is thus: parallel *advisory* fan-out through one wrapped CLI verb + artifact files as the interchange format + host-model synthesis, with zero runtime state.

## 4. Model-CLI provider abstraction (`src/team/model-contract.ts`)

The reusable adapter schema is `CliAgentContract`: `{ agentType, binary, installInstructions, buildLaunchArgs(model?, extraFlags?), parseOutput(raw), supportsPromptMode?, promptModeFlag? }` over `CliAgentType = 'claude'|'codex'|'gemini'|'cursor'|'grok'|'antigravity'` (src/team/model-contract.ts:8-20). Highlights per contract (:183-307):

| Agent | Binary | Launch args | Prompt mode | parseOutput |
|---|---|---|---|---|
| claude | `claude` | `--dangerously-skip-permissions` [+ `--bare` if `ANTHROPIC_API_KEY` set, `shouldUseClaudeBareMode` :179-181] [+ `--model` — Bedrock/Vertex IDs passed verbatim, else alias-normalized, issue #1695] | (interactive) | trim |
| codex | `codex` | `--dangerously-bypass-approvals-and-sandbox` | **false** — team workers are persistent TUI panes nudged via `inbox.md`, never `codex exec` (:211-214) | JSONL scan backwards for last `{type:'message',role:'assistant'}` (:220-236) |
| gemini | `gemini` | `--approval-mode yolo` | true, flag `-p` | trim |
| grok | `grok` | `--always-approve` | true, flag `-p` | trim |
| antigravity | `agy` | `--dangerously-skip-permissions` (flags must precede `-p <prompt>`) | true, flag `-p` | trim |
| cursor | `cursor-agent` | none — "cursor-agent owns its own session/auth state" | **false** — interactive REPL, executor-only, excluded from the verdict-file contract (:293-297) | trim |

All six providers are **real, wired implementations** — none are stubs — but they differ in capability: codex/cursor cannot run headless in team mode, and cursor cannot even take a `--model`. `getPromptModeArgs` builds `[promptModeFlag, instruction]` or positional, after `assertHeadlessSupported` (antigravity+win32 → hard throw mirroring the advisor guard; the comment says it "centralizes the same platform support decision the advisor ... enforces", :530-574).

**Binary trust chain.** `resolveCliBinaryPath` resolves via `which`/`where`, rejects relative results, hard-rejects `UNTRUSTED_PATH_PATTERNS` (`/tmp`, `/var/tmp`, `/dev/shm`), and warn-only flags anything outside trusted prefixes (`/usr/local/bin`, `/usr/bin`, `/opt/homebrew/`, `~/.local/bin`, `~/.nvm/`, `~/.cargo/bin`, `~/.grok/bin`, plus colon-separated absolutes from `OMC_TRUSTED_CLI_DIRS`) with a directory-boundary check so `/usr/bin-malicious/grok` cannot match the `/usr/bin` prefix (:51-145). Worker envs are built from an explicit allowlist (`WORKER_MODEL_ENV_ALLOWLIST`: `ANTHROPIC_MODEL`, `CLAUDE_MODEL`, Bedrock/Vertex tier vars, `OMC_MODEL_{HIGH,MEDIUM,LOW}`, `OMC_{CODEX,GEMINI,GROK,ANTIGRAVITY}_DEFAULT_MODEL` and `OMC_EXTERNAL_MODELS_DEFAULT_*` forms) plus `OMC_TEAM_WORKER`/`OMC_TEAM_NAME`/`OMC_WORKER_AGENT_TYPE` identity vars (:412-458).

**Detection and diagnostics.** `detectAllClis()` probes all six binaries with `--version` (5s timeout) and `which`/`where` (src/team/cli-detection.ts:33-42). `omc doctor team-routing` collects every provider referenced by `team.roleRouting` in merged config (always adding `claude`), probes each, and reports missing binaries as *warnings, not errors* ("AC-11", src/cli/commands/doctor-team-routing.ts:1-72). `src/team/capabilities.ts` maps backends to default capability tags (e.g. `'tmux-codex': ['code-review','security-review','architecture','refactoring']`, `'tmux-gemini': ['ui-design','documentation','research','code-edit']`) and scores worker-task fitness at 1.0 per exact match with `'general'` as a 0.5 wildcard (:14-61).

## 5. `src/providers/` — git-hosting abstraction (not models)

Interface `GitProvider`: `name`, `displayName`, `prTerminology: 'PR'|'MR'`, `prRefspec` (e.g. `pull/{number}/head:{branch}`), `detectFromRemote`, optional `detectFromApi` for self-hosted probing, `viewPR`, `viewIssue`, `checkAuth`, `getRequiredCLI` (src/providers/types.ts:44-86). Implementations shell out to native CLIs: GitHub→`gh`, GitLab→`glab`, Azure DevOps→`az repos pr show`, Gitea/Forgejo→`tea` with `curl` API fallback (probing `/api/forgejo/v1/version` then `/api/v1/version` to distinguish forks); Bitbucket is API-only via `fetch` (per-file greps of src/providers/*.ts). Active consumers are `omc teleport` (src/cli/commands/teleport.ts:14) and the persistent-mode idle-repo hook (src/hooks/persistent-mode/idle-repo-state.ts:2). Real but narrow; two lines suffice.

## 6. `omc interop` — OMC-OMX shared-state channel

`omc interop` must run *inside* tmux; it verifies `claude` (required) and `codex` (optional — degrades to a warning + single pane), generates `sessionId = interop-<uuid8>`, writes `.omc/state/interop/config.json`, then `tmux split-window -h` with `codex` in the right pane (src/cli/interop.ts:60-158). Communication is file-based under `getOmcRoot(cwd)/state/interop/`:

```
.omc/state/interop/
├── config.json                    InteropConfig {sessionId, createdAt, omcCwd, omxCwd?, status: active|completed|failed}
├── tasks/task-<ts>-<rand9>.json   SharedTask {source/target: omc|omx, type: analyze|implement|review|test|custom,
│                                    description, status: pending|in_progress|completed|failed, result?, error?}
├── messages/msg-<...>.json        SharedMessage {content, read: bool, metadata?}
└── artifacts/<category>/<id>.md   bodies > 2048 bytes externalized (INTEROP_ARTIFACT_THRESHOLD_BYTES)
```

Everything is zod-validated on read (`safeParse`, silently skipping invalid files), atomically written, and task updates take a `<file>.lock` via `withFileLockSync` (src/interop/shared-state.ts:59,93-119,320). Oversized text is swapped for an `ArtifactDescriptor` (`{kind, path, contentHash?, producer:{system:'omc'|'omx', component}, retention: 'ephemeral'|'session'|'until-completion'|'persistent'}`), and cleanup unlinks descriptor files alongside their JSON (:483-552).

Eight MCP tools expose this: `interop_send_task`, `interop_read_results`, `interop_send_message`, `interop_read_messages`, plus four OMX-native tools `interop_list_omx_teams`, `interop_send_omx_message`, `interop_read_omx_messages`, `interop_read_omx_tasks` (src/interop/mcp-bridge.ts:93-557,622-632). They register only when `OMC_INTEROP_TOOLS_ENABLED === '1'` (src/mcp/omc-tools-server.ts:37-38). Escalation is env-gated in layers: `OMX_OMC_INTEROP_ENABLED=1` turns interop on; `OMX_OMC_INTEROP_MODE` is `off|observe|active`; **writing directly into OMX team mailboxes requires all three** — enabled + tools-enabled + `mode === 'active'` (`canUseOmxDirectWriteBridge`, mcp-bridge.ts:38-43) — and the flag combination is validated fail-loud at `omc interop` startup (mode nonzero without enabled, or active without tools → refuse to start; `OMX_OMC_INTEROP_FAIL_CLOSED` defaults to fail-closed, src/cli/interop.ts:22-43,64-69). `src/interop/omx-team-state.ts` is a fork of oh-my-codex's team-state layer that reads/writes the *native OMX format* at `.omx/state/team/{name}/`: `config.json`, `manifest.v2.json`, `mailbox/{worker}.json`, `tasks/task-{id}.json`, `events/events.ndjson` append-only (omx-team-state.ts:1-14) — cross-harness interop by adopting the other side's on-disk schema instead of inventing a neutral one.

## 7. OpenClaw — hook-event gateway waker

OpenClaw is OMC's outbound notification/automation bridge: it "wakes" an external gateway (an HTTP endpoint or a shell command — in practice an OpenClaw personal-agent instance or any webhook consumer) whenever selected Claude Code hook events fire. It is strictly fire-and-forget: `wakeOpenClaw` is called from the hook bridge via a `_openclaw.wake` wrapper that dynamic-imports the module and swallows every error ("Never let OpenClaw failures propagate to hooks", src/openclaw/index.ts:203-209; call sites for `keyword-detector`, `stop`, `session-start` at src/hooks/bridge.ts:1605,1844,1945).

**Arming.** Two gates must both open: `OMC_OPENCLAW === "1"` (set by launching with `omc --openclaw`; `--openclaw=0` force-disables) AND a valid config file at `~/.claude/omc_config.openclaw.json` (path override `OMC_OPENCLAW_CONFIG`) with `enabled: true` (src/openclaw/config.ts:14-56). Config schema: `{ enabled, gateways: {name -> {type?: "http", url, headers?, method?: POST|PUT, timeout?} | {type: "command", command, timeout?}}, hooks: {event -> {gateway, instruction, enabled}} }` over events `session-start | session-end | pre-tool-use | post-tool-use | stop | keyword-detector | ask-user-question` (src/openclaw/types.ts:9-64). Missing/invalid/disabled config caches as "off" — fail-open silence, never an error.

**Signal normalization.** Each raw event is converted into an `OpenClawSignal {kind: session|tool|test|pull-request|question|keyword, phase: started|finished|failed|idle|detected|requested, routeKey, priority: high|low, testRunner?, prUrl?, command?, summary?}` (types.ts:66-109). `signal.ts` pattern-matches Bash tool inputs against test runners (vitest/jest/pytest/`cargo test`/`go test`/`make test`), extracts PR URLs from `gh pr create` output, and applies failure heuristics (`error:`, `FAIL`, `permission denied`, `exit code: [1-9]`...) after stripping Claude's temp-cwd noise (signal.ts:3-79). `toolInput`/`toolOutput` are marked internal-only and never forwarded; the payload context is rebuilt through an explicit field whitelist (index.ts:44-62, types.ts:152-155).

**Dedupe.** Burst collapse is file-locked state at `.omc/state/openclaw-event-dedupe.json` + `.lock`: windows `START_WINDOW_MS 10_000`, `PROMPT_WINDOW_MS 4_000`, `STOP_WINDOW_MS 12_000`, state TTL 6h, plus a `TERMINAL_STATE_SUPPRESSION_WINDOW_MS = 60_000` that mutes late lifecycle events for a `{projectPath}::{tmuxSession}` scope after stop/session-end; the lock uses `O_EXCL` with 2s timeout / 20ms retry / 10s staleness and `Atomics.wait`-based sleep (src/openclaw/dedupe.ts:23-41). Deduped wakes return `{success: true, skipped: "deduped"}`.

**Dispatch.** HTTP gateways require HTTPS (HTTP allowed only for localhost/127.0.0.1/::1), default timeout 10 000 ms, JSON POST of the full `OpenClawPayload` (dispatcher.ts:24-135). Command gateways interpolate `{{variable}}` placeholders into a template with every value **shell-escaped** (`'` + `'\''` wrapping) before `sh -c`, and export `OPENCLAW_PAYLOAD_JSON`, `OPENCLAW_SIGNAL_ROUTE_KEY`, `OPENCLAW_SIGNAL_PHASE`, `OPENCLAW_SIGNAL_KIND` in the child env (:143-177). Available template variables include `{{projectName}}`, `{{tmuxTail}}` (delta-only pane capture via `getNewPaneTail(..., 15)` so already-resolved failures do not re-alert, index.ts:119-133), `{{signalRouteKey}}`, `{{payloadJson}}`, and reply-routing fields sourced from `OPENCLAW_REPLY_CHANNEL/TARGET/THREAD`. Debug logging via `OMC_OPENCLAW_DEBUG=1`. `scripts/openclaw-gateway-demo.mjs` is a dev-only demo, wired to no bin/hook.

## 8. Configuration surface (this territory)

| Kind | Name | Effect (evidence) |
|---|---|---|
| env | `OMC_ASK_ADVISOR_SCRIPT` / `OMX_ASK_ADVISOR_SCRIPT` (deprecated) | Override advisor script path (src/cli/ask.ts:24-25,183-199) |
| env | `OMC_ASK_ORIGINAL_TASK` / `OMX_ASK_ORIGINAL_TASK` (deprecated) | Raw task recorded in artifact regardless of persona prefix (run-provider-advisor.js:114-115,252-265) |
| env | `OMC_ANTIGRAVITY_TIMEOUT_MS` | agy hang bound; int >= 1000, clamp 3 600 000, default 300 000 (run-provider-advisor.js:27-40) |
| env | `OMC_SECURITY=strict` / config `security.disableExternalLLM` | Blocks all non-claude providers in ask AND team (security-config.ts:36-56; ask.ts:215; model-contract.ts:314) |
| env | `OMC_TRUSTED_CLI_DIRS` | Colon-separated extra trusted binary prefixes (model-contract.ts:72-78) |
| env | `OMC_OPENCLAW`, `OMC_OPENCLAW_CONFIG`, `OMC_OPENCLAW_DEBUG` | OpenClaw gate / config path / debug (openclaw/config.ts:14,31; index.ts:41) |
| env | `OPENCLAW_REPLY_CHANNEL/TARGET/THREAD` | Reply routing fields in payload (openclaw/index.ts:95-97) |
| env | `OMX_OMC_INTEROP_ENABLED`, `OMX_OMC_INTEROP_MODE`, `OMC_INTEROP_TOOLS_ENABLED`, `OMX_OMC_INTEROP_FAIL_CLOSED` | Interop layering: on / off-observe-active / MCP tools / fail-closed default (interop.ts:22-31) |
| env | `OMC_STATE_DIR` | Relocates `.omc` state root incl. ask artifacts (state-root.mjs:46-52) |
| env | `CODEX_HOME`, `.omx/setup-scope.json` | Persona prompts dir resolution for `--agent-prompt` (ask.ts:65-88) |
| env | `OMC_CLI_SKIP_PARSE` | Test seam: import CLI without parsing (index.ts:1520) |
| flags | `--madmax/--yolo`, `--notify`, `--openclaw`, `--telegram/--discord/--slack/--webhook`, `--plugin-dir` | Stripped/captured at launch, mapped to env (launch.ts:40-49,706-760) |
| config | `team.roleRouting[role].provider` | Which external CLIs `doctor team-routing` probes (doctor-team-routing.ts:58-72) |

## Patterns for sibling harnesses

- **Wrapped advisor verb with mandatory artifact capture** — one CLI command (`omc ask <provider> <prompt>`) owns flag selection, version quirks, and always writes a structured markdown artifact whose path is the last stdout line; skills are forbidden from assembling raw provider CLIs. Adapt: give each harness a single `omX ask`-style verb and make the artifact file the inter-agent interface.
- **Contract-object provider abstraction** — `{binary, buildLaunchArgs, parseOutput, supportsPromptMode, promptModeFlag}` per provider, with capability differences (headless vs TUI-only) encoded as data, not branches. Adapt: define the same five-field contract for any external tool your harness drives.
- **Quirk containment per provider** — upstream bugs (agy #76) handled with SIGKILL-bounded `spawnSync`, empty-zero-exit coerced to failure, and per-platform hard refusal with an actionable alternative. Adapt: encode known-broken provider/platform pairs as loud preflight errors, never silent degradation.
- **Session-marker env stripping** — child model CLIs get `CLAUDECODE`/`CLAUDE_SESSION_ID`/etc. removed so they cannot detect or inherit the host session. Adapt: strip your harness's own session env vars before spawning any nested agent.
- **Prompt transport selection by content** — argv for short single-line prompts, stdin for multiline/>500-char/leading-dash prompts, per-provider never-pipe exceptions. Adapt: centralize this decision in one `shouldPipePromptViaStdin(provider, prompt)` function.
- **One security kill switch, multiple chokepoints** — `disableExternalLLM` enforced independently in the ask CLI and the team contract getter, sourced from a strict-mode env plus JSONC config overrides. Adapt: any "no external models" policy should gate every spawn path, not just the front door.
- **Tri-model fan-out as a skill, not a runtime** — ccg is pure prompt protocol over the ask verb with artifact files as the interchange, plus explicit single-provider and zero-provider fallbacks. Adapt: prefer composing existing verbs in skill text over building orchestration code.
- **Layered escalation flags for cross-harness writes** — read-only by default, `observe` before `active`, and direct writes into the sibling's state requiring three env vars simultaneously, validated fail-closed at startup. Adapt: OMX-family harnesses should gate mutual state mutation exactly this way.
- **Adopt the sibling's on-disk schema** — OMC talks to OMX by reading/writing OMX's native `.omx/state/team/` layout (forked reader), rather than a neutral protocol. Adapt: when two harnesses must interop, one imports the other's file schema; version it (`manifest.v2.json`).
- **Fire-and-forget gateway waker with normalized signals** — hook events mapped to `{kind, phase, routeKey, priority}` signals, whitelist-only payload context, shell-escaped command templates, windowed dedupe under a file lock, and total error swallowing so hooks never block. Adapt: any outbound notification bridge should be double-gated (launch flag + config file) and structurally unable to fail the host.
- **Trusted-prefix binary resolution** — resolve via `which`, reject world-writable dirs (`/tmp`), warn outside a trusted-prefix list with directory-boundary matching. Adapt: cheap supply-chain guard for any harness that spawns PATH binaries.

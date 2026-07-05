# HUD Statusline & Notification System

OMC ships two user-facing telemetry subsystems: a **HUD statusline** (`src/hud/`) that renders a multi-line status readout inside Claude Code's status bar on every statusline refresh, and a **notification system** (`src/notifications/`) that pushes session-lifecycle events to Telegram/Discord/Slack/webhooks and can even inject chat replies back into the running tmux pane. Both are ACTIVE and wired: the HUD through the `statusLine` command in `~/.claude/settings.json` (installed by `omc setup` / the `hud` skill), the notifications through hook scripts declared in `hooks/hooks.json` (`session-start.mjs`, `pre-tool-enforcer.mjs`, the `bridge.ts` hook dispatcher, `session-end.mjs`) plus two skills (`skills/hud/SKILL.md`, `skills/configure-notifications/SKILL.md`). Everything is fail-open: neither subsystem is ever allowed to break a hook or the status bar.

## 1. HUD statusline

### 1.1 Wiring and entry points

Claude Code invokes the configured `statusLine.command` and pipes a JSON blob to its stdin. OMC's installer writes one of four command variants depending on platform/node discovery (src/installer/index.ts:206-238): plain `node ${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hud/omc-hud.mjs`, a `sh .../hud/find-node.sh <script>` shim, a `sh .../hud/omc-hud-cache.sh <script>` caching shim, or a quoted absolute-path pair on Windows. The `omc-hud.mjs` wrapper body is a checked-in template (`scripts/lib/hud-wrapper-template.txt`, single source of truth guarded by `src/__tests__/hud-wrapper-template-sync.test.ts`; the skill copies it verbatim, skills/hud/SKILL.md:49-58). The wrapper is a resolution ladder that finds a built HUD and `import()`s it:

```
1. $OMC_PLUGIN_ROOT/dist/hud/index.js            (dev override, set by `omc --plugin-dir`)
2. <configDir>/plugins/cache/omc/oh-my-claudecode/<semver>/dist/hud/index.js
   - strict semver dir filter ^\d+\.\d+\.\d+(-...)?$ (skips "4.14.1.backup" siblings)
   - semver-desc sort, stable > prerelease; only versions WITH a built dist are tried
3. <configDir>/plugins/marketplaces/omc/dist/hud/index.js
4. npm packages "oh-my-claude-sisyphus" then "oh-my-claudecode"
   (disabled by OMC_HUD_DISABLE_NPM_FALLBACK=1)
5. print actionable fix text, e.g. "Run: cd <cacheDir> && npm install && npm run build"
```
(scripts/lib/hud-wrapper-template.txt:98-249). `src/hud/index.ts` ends with an unconditional `main()` call (src/hud/index.ts:597) so the dynamic import executes the render. Three invocation modes exist in `main(watchMode, skipInit)`: statusline (stdin JSON), `omc hud` on a TTY (prints an install diagnostic checking `omc-hud.mjs` existence and that `settings.statusLine.command` contains `"omc-hud"`, src/hud/index.ts:218-250), and `omc hud --watch --interval <ms>` (default `'1000'`) which loops `hudMain(true, skipInit)` for a tmux pane, reading the last statusline stdin from a cache file (src/cli/index.ts:1394-1407, src/cli/hud-watch.ts). Update cadence is therefore driven by Claude Code itself ("updates automatically every ~300ms during active sessions", skills/hud/SKILL.md:259); expensive sources are decoupled by their own TTLs (below).

### 1.2 Data sources feeding the render context

| Source | Mechanism | Evidence |
|---|---|---|
| Claude Code stdin | `StatuslineStdin` = `transcript_path`, `cwd`, `model{id,display_name}`, `context_window{context_window_size,total_input_tokens,used_percentage,current_usage}`, `rate_limits{five_hour,seven_day}` | src/hud/types.ts:47-83 |
| stdin cache | last stdin persisted to `.omc/state/sessions/{id}/hud-stdin-cache.json` (legacy flat `state/hud-stdin-cache.json`) so `--watch` (TTY, no stdin) can render; fallback picks the most-recently-modified session cache | src/hud/stdin.ts:43-171 |
| Transcript JSONL | `parseTranscript()` extracts agents (`Task`/`proxy_Task`/`Agent` tool_use), todos (`TodoWrite`), last skill (`Skill`), thinking state, pending permission, per-request token usage, tool/agent/skill call counts, last tool name. Files >`MAX_TAIL_BYTES` (4MB) are tail-parsed only; token totals from a tail read are treated as partial; parse results memoized (`TRANSCRIPT_CACHE_MAX_SIZE = 20`) | src/hud/transcript.ts:32-89,143-163,509-570 |
| OMC mode state | `ralph-state.json`, `ultrawork-state.json`, `autopilot-state.json` resolved session-scoped first (`.omc/state/sessions/{id}/`) then `.omc/state/`, then legacy `.omc/` root; PRD from `prd.json` or `.omc/prd.json` | src/hud/omc-state.ts:39-97,128-281 |
| HUD's own state | `hud-state.json` (`OmcHudState` = `timestamp`, `backgroundTasks[]`, `sessionStartTimestamp`, `sessionId`, `lastPromptTimestamp`). Background tasks are written by the hook bridge via `addBackgroundTask`/`completeBackgroundTask` (src/hooks/bridge.ts:2646,2875); HUD persists real session start to survive tail-parse resets and cleans legacy files on session-scoped writes | src/hud/types.ts:32-41, src/hud/index.ts:337-361, src/hud/state.ts:262-303 |
| Usage API | OAuth creds from macOS Keychain service `Claude Code-credentials` (or `Claude Code-credentials-{sha256(configDir)[:8]}` for custom config dirs) else `~/.claude/.credentials.json`; GET `api.anthropic.com/api/oauth/usage`; token refresh via `platform.claude.com` `/v1/oauth/token`; alternative providers z.ai and MiniMax detected by base-URL hostname | src/hud/usage-api.ts:8-11,436-442,524,654-659,707 |
| Custom rate provider | `omcHud.rateLimitsProvider = { type:'custom', command, timeoutMs (default 800), periods, resetsAtDisplayThresholdPercent (default 85) }` runs a user command that must print `{ version:1, generatedAt, buckets:[{id,label,usage,resetsAt}] }`; stale last-known-good cache on failure | src/hud/types.ts:253-316 |
| Session summary | opt-in (`sessionSummary:false` default); spawns `scripts/session-summary.mjs` detached with a PID-liveness guard + 120s respawn throttle + 60s cache debounce; reads `session-summary-<sessionId>.json` | src/hud/index.ts:107-197,417-438 |
| Version/update | `getRuntimePackageVersion()` + update-check cache file; renders `[OMC#4.15.2] -> <ver> omc update` when behind | src/hud/index.ts:379-415, src/hud/render.ts:310-323 |
| Payload estimate | transcript file size vs `ANTHROPIC_REQUEST_PAYLOAD_LIMIT_BYTES = 32_000_000`, warn at `22_000_000`, critical at `26_000_000` | src/hud/payload-estimate.ts:12-14 |

Usage-API caching: success TTL = `usageApiPollIntervalMs` (default `DEFAULT_HUD_USAGE_POLL_INTERVAL_MS = 90*1000`), non-transient failure TTL 15s (`CACHE_TTL_FAILURE_MS`), network failures 2min, 429s exponential backoff capped at 5min (`MAX_RATE_LIMITED_BACKOFF_MS`), stale data served with a `stale` flag under lock contention (src/hud/usage-api.ts:33-35,345-371, src/hud/types.ts:690). Stdin `rate_limits` (fresher 5h/7d) are merged over API results, which contribute Sonnet/Opus-weekly, monthly, extra-usage and enterprise-spend fields (src/hud/index.ts:70-85,363-371).

### 1.3 Configuration surface: the `omcHud` settings key

`readHudConfig()` priority: `~/.claude/settings.json` `omcHud` key > legacy `~/.claude/.omc/hud-config.json` > `DEFAULT_HUD_CONFIG`, with per-section deep merges (elements, thresholds, contextLimitWarning, missionBoard, labels) (src/hud/state.ts:345-395). Final element resolution is three-layer: `DEFAULT_HUD_CONFIG.elements` then `PRESET_CONFIGS[preset]` then user `elements` overrides (src/hud/state.ts:423-427). Presets are `'minimal' | 'focused' | 'full' | 'opencode' | 'dense'` (`HudPreset`, src/hud/types.ts:432); default preset `'focused'`. Preset deltas (src/hud/types.ts:756-972):

| Setting | minimal | focused (default) | full | opencode | dense |
|---|---|---|---|---|---|
| gitBranch/gitStatus | off/off | on/on | on/on | on/off | on/on |
| gitRepo | off | off | on | off | on |
| contextBar | off | on | on | on | on |
| agentsFormat / maxLines | count / 0 | multiline / 3 | multiline / 10 | codes / 0 | multiline / 5 |
| backgroundTasks | off | on | on | off | on |
| rateLimits / useBars | on / off | on / on | on / on | off / off | on / on |
| apiKeySource | off | off | on | off | on |
| maxOutputLines | 2 | 4 | 12 | 4 | 6 |

(Table labels are conceptual; the literal `omcHud.elements` field names are `activeSkills`, `prdStory`, `updateNotification`, `permissionStatus`, `sessionSummary`, `showTokens`, `showCallCounts`, `showLastTool`, `agentsFormat`, `agentsMaxLines`, etc. — src/hud/types.ts:756-971.)

Other config keys: `thresholds` (`contextWarning:70`, `contextCompactSuggestion:80`, `contextCritical:85`, `ralphWarning:7`), `staleTaskThresholdMinutes:10`, `contextLimitWarning:{threshold:80, autoCompact:false}`, `usageApiPollIntervalMs`, `locale` (`'en' | 'zh-CN'` with a full label table) plus per-label overrides, `elementOrder` (main-line convenience), `layout:{line1,main,detail}` (full placement control — elements can migrate between inline and detail groups), `maxWidth`, `wrapMode:'truncate'|'wrap'` (src/hud/types.ts:611-754). When `maxWidth` is unset, live TTY columns are auto-detected and `wrapMode` flips to `wrap` (src/hud/index.ts:288-298). `safeMode` (default `true`) strips ANSI and rewrites `█`→`#`, `░`→`-` for corruption-free rendering; non-safe mode converts spaces to NBSP ` ` for alignment (src/hud/index.ts:558-570, src/hud/sanitize.ts). `applyPreset()` writes the merged config back to `settings.json` atomically under the `omcHud` key (src/hud/state.ts:458-519). The `hud` skill is an agent-executed installer/config UI (`/oh-my-claudecode:hud [setup|minimal|focused|full|status]`).

### 1.4 Render pipeline

```
stdin JSON ──stabilizeContextPercent──> cache write        (watch mode reads cache)
   │
   ├─ resolveToWorktreeRoot(cwd), resolveTranscriptPath    (worktree mismatch fix #1094)
   ├─ parseTranscript(tail<=4MB)  ─┐
   ├─ ralph/ultrawork/prd/autopilot state reads ─┤
   ├─ hud-state.json (bg tasks, session start) ──┼─> HudRenderContext
   ├─ getUsage() + stdin rate-limit merge ───────┤
   └─ custom provider / summary / payload est ───┘
render(context, config):
   every element rendered independently into Map<name,string> (+ detail Map)
   -> layout order collects line1 / main / detail groups
   -> join with dim(" | "), gitInfoPosition 'above'|'below'
   -> wrap or truncate to maxWidth (ANSI-aware width, code-point safe)
   -> limitOutputLines (keeps header, appends "... (+N lines)")
   -> safeMode sanitize -> console.log
```

`DEFAULT_ELEMENT_ORDER` names the canonical element vocabulary: line1 = `hostname, cwd, gitRepo, gitBranch, gitStatus, apiKeySource, profile`; main = `omcLabel, model, enterpriseCost, rateLimits, customBuckets, permission, thinking, promptTime, session, tokens, ralph, autopilot, prd, skills, lastSkill, contextBar, agents, background, callCounts, lastTool, sessionSummary`; detail = `missionBoard, agents, contextWarning, payloadWarning, todos` (src/hud/types.ts:653-662). Enterprise detection (`subscriptionType === 'enterprise'` or `/claude_zero/i` rate-limit tier) swaps rate limits for a billing-cost element only when `enterpriseSpentUsd` is actually present (src/hud/render.ts:327-341). A side effect, not a render element: when `contextLimitWarning.autoCompact` is true and context percent >= threshold, the HUD writes `.omc/state/compact-requested.json` (`{requestedAt, contextPercent, threshold}`) as a trigger file for a companion hook (src/hud/index.ts:520-545).

### 1.5 Lifecycle and failure modes

There is no daemon; each render is a fresh process (except `--watch`, which loops with graceful-shutdown handlers and `skipInit` after the first pass). `initializeHUDState()` runs stale-task cleanup and orphan marking on each non-watch start (src/hud/state.ts:525-538). Everything is fail-open and cosmetic: install errors print `"[OMC] run /omc-setup to install properly"`, runtime errors print `"[OMC] HUD error - check stderr"` (src/hud/index.ts:571-590); all state readers return `null` on parse failure; `OMC_DEBUG=1` unlocks stderr diagnostics. One deliberate anti-ghost rule: session-scoped HUD state never falls back to root/legacy files, "prevents a stale root state from being revived after a pane/session recreation" (src/hud/state.ts:206-224). The `missionBoard` element and `omc mission-board` CLI are present and functional but opt-in-off everywhere; `elements.permissionStatus` is shipped but default-off ("heuristic-based, causes false positives", src/hud/types.ts:720).

## 2. Notification system

### 2.1 Event model and triggers

`NotificationEvent = "session-start" | "session-stop" | "session-end" | "session-idle" | "ask-user-question" | "agent-call"` (src/notifications/types.ts:13-19). Active emitters, all hook-driven:

| Event | Fired from | Notes |
|---|---|---|
| `session-start` | `scripts/session-start.mjs:270-272` (detached child) and src/hooks/bridge.ts:1939 | SessionStart hook |
| `session-idle` | Stop-hook path src/hooks/bridge.ts:1848 with per-session cooldown (`shouldSendIdleNotification`), plus `scripts/persistent-mode.mjs:144` | suppressed on abort/context-limit stops |
| `session-end` | src/hooks/session-end/index.ts:984 | true SessionEnd only; reply-registry cleanup happens here, never on Stop (bridge.ts:1856-1859) |
| `ask-user-question` | PreToolUse on `AskUserQuestion` — scripts/pre-tool-enforcer.mjs:1412 and src/hooks/bridge.ts:2271 | carries structured `askUserQuestionPrompts` |
| `agent-call` | PreToolUse on `Task` — src/hooks/bridge.ts:2569 (issue #761) | verbose-tier only |
| `session-stop` | **no active emitter in src/** | vestigial trigger: fully typed, formatted, and templated but never fired by OMC code (only reachable via custom-integration event lists) |

Hook processes never send in-process: `dispatchNotificationInBackground()` spawns a detached `node --input-type=module -e "<import notify>"` child with `stdio:"ignore"` and `OMC_HOOK_BACKGROUND_CHILD=1`, explicitly so notification stderr can never pollute the hook's strict stdout JSON protocol (src/hooks/background-notifications.ts:10-57).

### 2.2 Config storage and resolution

Primary store is `~/.claude/.omc-config.json` under the `notifications` key (`NotificationConfig`: global `enabled`, `verbosity`, `tmuxTailLines`, per-platform blocks `discord | discord-bot | telegram | slack | slack-bot | webhook`, per-event overrides in `events`, reply settings in `notifications.reply`, and `customIntegrations` at top level). `getNotificationConfig(profileName?)` resolution (src/notifications/config.ts:509-550): (0) named profile from `notificationProfiles` (selected by arg or `OMC_NOTIFY_PROFILE`); (2) `notifications` key; (2b) pure env-var zero-config via `buildConfigFromEnv()`; (3) legacy `stopHookCallbacks` migration. File config is then overlaid: `omc_config.hook.json` (`HookNotificationConfig`, `version:1`) event enable/template overrides win first, then env platforms fill *missing* blocks only (file fields take precedence) (src/notifications/config.ts:360-404, hook-config.ts:18-34; path overridable via `OMC_HOOK_CONFIG`).

Zero-config env vars: `OMC_TELEGRAM_BOT_TOKEN`/`OMC_TELEGRAM_CHAT_ID` (plus `OMC_TELEGRAM_NOTIFIER_*` aliases), `OMC_DISCORD_WEBHOOK_URL`, `OMC_DISCORD_NOTIFIER_BOT_TOKEN`+`OMC_DISCORD_NOTIFIER_CHANNEL`, `OMC_DISCORD_MENTION`, `OMC_SLACK_WEBHOOK_URL`, `OMC_SLACK_BOT_TOKEN`+`OMC_SLACK_BOT_CHANNEL`+`OMC_SLACK_APP_TOKEN`, `OMC_SLACK_MENTION` (src/notifications/config.ts:176-252).

Two independent gates sit above platform config. First, a **per-session activation gate**: each platform is dormant unless its flag env is set — `OMC_TELEGRAM=1`, `OMC_DISCORD=1`, `OMC_SLACK=1`, `OMC_WEBHOOK=1` — set by the `omc` launcher flags `--telegram/--discord/--slack/--webhook` (src/notifications/config.ts:560-568, src/cli/launch.ts:731; "Without these flags, configured platforms remain dormant", skills/configure-notifications/SKILL.md:765-781). Second, a **verbosity gate**: `VerbosityLevel = "verbose" | "agent" | "session" | "minimal"` (env `OMC_NOTIFY_VERBOSITY` > config > default `"session"`); minimal/session allow only the four session-* events, agent adds `agent-call`, verbose allows all — except an explicitly enabled `ask-user-question` event bypasses verbosity (src/notifications/config.ts:428-483, src/notifications/index.ts:143-155). Kill switch: `OMC_NOTIFY=0` (set by `omc --notify false`) short-circuits both `notify()` and the background dispatcher. tmux tail capture (last `tmuxTailLines`, default 15, env `OMC_NOTIFY_TMUX_TAIL_LINES`) is attached to idle/end/stop payloads unless verbosity is `minimal`.

### 2.3 Secret handling

Tokens live in plaintext in `.omc-config.json` (the `configure-notifications` skill writes them via `jq`) or in shell-profile env vars — there is no keychain path for notification secrets (unlike HUD OAuth reads). Compensating controls: format validation before use (Telegram token regex, Discord/Slack mention regexes with ID-length bounds, Slack channel/username sanitizers rejecting shell metacharacters, src/notifications/config.ts:98-156); strict URL allowlists — Discord webhooks must be HTTPS on `discord.com`/`discordapp.com`, Slack webhooks HTTPS on `hooks.slack.com`, generic webhooks HTTPS-only (src/notifications/dispatcher.ts:250-299); and `redactTokens()` masking `xoxb-/xapp-/xoxp-/xoxa-`, Telegram `/bot<id>:<token>` and standalone `id:token`, `Bearer`/`Bot` auth values, `sk-ant-api`, `ghp_/gho_/ghs_/github_pat_`, `AKIA` keys in every log/error string (src/notifications/redact.ts:21-42, issue #1162). The reply daemon forwards only `OMC_*`-prefixed env vars into its child environment (src/notifications/reply-listener.ts:62-144) and writes its state dir with `mode: 0o700`.

### 2.4 Delivery code path

```
hook -> dispatchNotificationInBackground(event, data)      [detached node -e child]
          -> notify(event, data)                            src/notifications/index.ts:128
               gates: OMC_NOTIFY!=0 -> config exists -> isEventEnabled (platform-activation
                      flags + per-event enabled) -> verbosity filter
               payload: sessionId, tmux session/pane, project, modes, duration,
                        question prompts, tmux tail (idle/end/stop)
               message: formatNotification(payload) OR per-platform template from
                        omc_config.hook.json via interpolateTemplate()
          -> dispatchNotifications(): all enabled platforms in parallel,
               per-send AbortSignal.timeout(SEND_TIMEOUT_MS=10_000),
               Promise.race vs DISPATCH_TIMEOUT_MS=15_000; failures swallowed
          -> registerMessage() for reply-capable sends (discord-bot/telegram/slack-bot)
```

Senders: Discord webhook (`content` truncated to `DISCORD_MAX_CONTENT_LENGTH = 2000` with mention prefix preserved, `allowed_mentions` computed from the validated mention); Discord Bot (`https://discord.com/api/v10/channels/<id>/messages`); Telegram `sendMessage` via the raw `https` module pinned to IPv4 "to avoid fetch/undici IPv6 connectivity issues", parsing `result.message_id` for reply correlation; Slack incoming webhook (mention prefixed as text); Slack Bot (`https://slack.com/api/chat.postMessage`); generic webhook (POST/PUT JSON) — all honoring `HTTPS_PROXY` via a manual CONNECT tunnel (src/notifications/dispatcher.ts:35-44,97-199,308-744). Message templates: the engine's `DEFAULT_TEMPLATES` reproduce formatter output exactly (e.g. session-end = `"# Session Ended"` + Session/Duration/Reason + conditional agents/modes/summary/tmux-tail + `{{footer}}`), with `{{variable}}` interpolation, `{{#if var}}...{{/if}}` conditionals, and computed variables (`duration`, `time`, `modesDisplay`, `iterationDisplay`, `agentDisplay`, `projectDisplay`, `footer`, `tmuxTailBlock`, `reasonDisplay`) (src/notifications/template-engine.ts:250-292, hook-config-types.ts:11-30). **Custom integrations** (`customIntegrations.integrations[]`, `type: 'webhook' | 'cli'`) run per-event with template-interpolated URL/headers/body or `execFile(command, args)` — array argv, no shell, `killSignal:"SIGTERM"` — with presets `openclaw`, `n8n`, custom-agent-gateway, generic webhook/CLI (src/notifications/dispatcher.ts:899-975, presets.ts:24-121); a legacy `omc_config.openclaw.json` is detected and migrated.

### 2.5 Reply loop (chat -> tmux injection)

Successful bot-platform sends are recorded in a global JSONL registry `reply-session-registry.jsonl` (`{platform, messageId, sessionId, tmuxPaneId, tmuxSessionName, event, createdAt, ...}`) under `O_EXCL` lock-file semantics with a 10s wait deadline and `MAX_AGE_MS` = 24h pruning (src/notifications/session-registry.ts:37-69,188-302). A singleton **reply-listener daemon** (PID file `reply-listener.pid`, state `reply-listener-state.json`, rotating log, started from the session-start hook when `buildDaemonConfig()` yields a config, scripts/session-start.mjs:1130-1132) polls Telegram `getUpdates?offset=...` and Discord channel messages every `pollIntervalMs` (default 3000) and runs a Slack Socket Mode WebSocket client with signature verification (`verifySlackSignature`, timestamp-window checks). Matching replies are injected into the originating tmux pane via `tmux send-keys` after sanitization (newlines flattened, backslashes escaped — "prevents multi-command injection"), an empty-pane liveness check, and a rate limiter (default 10/min). Semantics are **at-most-once**: the poll offset is persisted *before* injection so a crash drops a message rather than double-injecting (src/notifications/reply-listener.ts:4-16,304-711,846-946). Authorization: Discord requires a non-empty `authorizedDiscordUserIds` allowlist (otherwise Discord reply listening is disabled with a logged warning); Slack allowlist optional; Telegram implicitly bound to the configured chat ID. The whole loop is opt-in: `OMC_REPLY_ENABLED=true` or `notifications.reply.enabled:true`, tunables `OMC_REPLY_POLL_INTERVAL_MS`, `OMC_REPLY_RATE_LIMIT`, `OMC_REPLY_DISCORD_USER_IDS`, `OMC_REPLY_SLACK_USER_IDS`, `OMC_REPLY_INCLUDE_PREFIX`, `maxMessageLength` default 500 (src/notifications/config.ts:840-906).

### 2.6 The configure-notifications skill

`skills/configure-notifications/SKILL.md` is a pure agent-executed wizard (no code of its own): AskUserQuestion-driven flows per provider that detect existing config with `jq`, walk BotFather/webhook creation, validate token/URL formats, merge into `.omc-config.json`, optionally disable unselected events (`.notifications.events["session-start"] = {enabled:false}`), send a `curl` test message, and document the env-var alternative and per-session activation flags. A separate section configures `omc_config.hook.json` templates and the custom-integration wizard including OpenClaw migration.

## Patterns for sibling harnesses

- **Statusline-as-stateless-probe**: render everything from a single short-lived process fed by host stdin plus on-disk state files; no daemon to babysit. Adaptation: any harness HUD should read its `.om*/state/*.json` fresh per render and treat every read as optional.
- **Wrapper resolution ladder**: a tiny committed wrapper script that probes env override -> versioned plugin cache (semver-desc, built-artifacts-only) -> marketplace clone -> npm, and prints exact fix commands on failure. Adaptation: decouples the host's configured command from where the real code lives across install channels.
- **Three-layer config merge (defaults -> preset -> user)** with presets controlling only on/off and a separate `layout` controlling placement/order. Adaptation: lets users switch density in one word without losing individual overrides.
- **Stdin cache for TTY replays**: persist the last host-provided JSON per session so a watch/monitor pane can render without the host pipe. Adaptation: any hook-fed renderer gains a free standalone mode.
- **Bounded tail parsing with partial-data honesty**: cap transcript reads (4MB) and mark derived totals as unreliable rather than wrong. Adaptation: mandatory for any log-derived metric in long sessions.
- **TTL ladder for remote polls**: success TTL from config, short failure TTL, longer transient-network TTL, exponential 429 backoff with cap, stale-served-with-flag. Adaptation: one cache struct (`{timestamp, data, error, rateLimitedCount}`) covers all remote status sources.
- **Trigger files as cross-process signals**: HUD writes `compact-requested.json`; a hook consumes it. Adaptation: cheap one-way channel between a renderer and hook logic without IPC.
- **Detached-child notification isolation**: hooks with strict stdout protocols spawn `node -e` children with `stdio:"ignore"` for any side-effectful work. Adaptation: omha's Stop/PreToolUse hooks should never send network traffic in-process.
- **Two-gate notification policy** (persistent config x per-session activation flag) plus a verbosity ladder. Adaptation: prevents "configured once, spams forever"; a session must opt in.
- **At-most-once reply injection**: persist the poll offset before acting, allowlist authors, sanitize before terminal injection, rate-limit. Adaptation: any chat-to-terminal bridge must prefer dropped messages over duplicated commands.
- **Redact-at-the-log-boundary**: a single `redactTokens()` applied to every error/log string, covering all known token shapes. Adaptation: centralize masking instead of trusting each call site.
- **Skill-as-installer**: setup logic expressed as verified shell steps in a SKILL.md that copies from a drift-tested canonical template rather than inlining content. Adaptation: keeps agent-performed installs byte-identical to programmatic ones.

# v4.14.4 -> v4.15.2 Delta, Repo Engineering, and Peripheral Directories

This section covers the engineering envelope around OMC's core: the 144-commit delta from the prior pinned snapshot (`2733c168`, v4.14.4) to HEAD (`d41f1730a71dfbb472424406a765efea5b5f10f0`, v4.15.2), the release/versioning discipline visible in git history, the peripheral top-level directories (`benchmark/`, `benchmarks/`, `geobench/`, `shellmark/`, `seminar/`, `research/`, `examples/`, `templates/`, `missions/`, `assets/`), the 11k-line internal `docs/` architecture corpus, the `AGENTS.md` guidance hierarchy, and the tests/CI/build machinery — classifying each as runtime, dev-only, or demo. The headline finding: the window is overwhelmingly hardening (patch releases), with exactly one structural feature — **full multi-repo workspace support** (`1484fa07`, shipped in v4.15.0) — plus new CLI-worker providers (antigravity, Grok, Cursor) and a Claude Fable 5 / Sonnet 5 / Opus 4.8 model-routing refresh. The task brief says "153-commit delta"; the actual non-merge count is **144** (`git log --oneline --no-merges 2733c168..HEAD | wc -l` = 144).

---

## 1. Delta by subsystem (144 non-merge commits)

Commit-prefix census (`git log --oneline --no-merges 2733c168..HEAD`): 11 bare `fix`, 9 `chore(release)`, 7 `fix(team)`, 6 `fix(hooks)`, 5 `docs`, and a long tail of single-subsystem fixes. Only **7 `feat` commits** exist in the entire window. This is a stabilization-dominated release train, not a feature train.

| Subsystem | Nature | Key commits (evidence) |
|:--|:--|:--|
| **multi-repo workspace** | NEW capability (v4.15.0) | `1484fa07 feat(multi-repo)`; follow-ups `c0eda84d`, `dc3f3b82`, `381c1dc4`, `74609f9d`; `6a5e877e fix(worktree): anchor .omc state to superproject, not git submodule` |
| **CLI-worker providers** | NEW providers | `1871a64d feat(providers): add antigravity (agy)`; `3cce4961 feat(team): add Grok Build`; `707ac09b Expose Cursor executor workers`; `6d93b443 [codex] Add cursor provider` |
| **model routing** | model refresh | `952d1575 feat(routing): add Claude Fable 5 tier alias`; `33c4ed2e fix: support Claude Sonnet 5 defaults`; `13b6b341 bump built-in Opus HIGH default to Claude Opus 4.8`; `da2ee4f3 stop halving the indented code-block count` |
| **team** | reliability | 7 `fix(team)` — slow worker start (`635ec8f9`), single-worker prose teams (`b9e792f7`), N:agent:role spec validation (`d1a5d27e`), harness-file exclusion from auto-merge (`257aab9b`) |
| **hooks / persistent-mode** | reliability | `7bfd777b raise UserPromptSubmit timeouts`, `4207e0f1 fix hooks prompt timeout budget`, `090e3fab keep stop reinforcement quiet while a delegated subagent runs`, `c4c00bbf bound thinking-only continuation loops`, `0b9f7225 Honor stop_hook_active` |
| **workflow-drift guard** | NEW hook (v4.15.0) | `86ea0470 Guard against recurring workflow drift`, `23338277 Prevent workflow drift at Stop hook boundary` — adds `templates/hooks/workflow-drift-guard.mjs` (first appears at `23338277`) |
| **keyword-detector** | i18n + precision | `16ffb0b1`/`fd15bc3f` Japanese katakana + 7-skill JA routing; `4a32b88d exempt quoted spans`; `7b453e71 fix informational occurrence scanning`; `2c922041 configurable magic keyword triggers` |
| **session-search** | Windows correctness | `fb032107`, `5afc409b`, `da6700e4` (drive-colon / underscore encoding, encoder convergence); `7eb06e5a rebuild session search encoder artifacts` |
| **HUD** | polish | `38ea6d13 Fix default HUD preset merge`, `93a16fca Detect HUD rate-limit panes`, `dbf69f4e enterprise billing for non-USD`, `d655a629`/`81fd860a` Windows cwd rendering, `fc7240e9 usage hint for API-key users` |
| **installer / plugin** | packaging | `4955f4f6 prune legacy standalone hook files`, `f35e7ced Fix standalone hook lib deployment`, `914c1ca0 Fail closed on incomplete plugin cache payloads`, `1e672e15 Publish omc npm CLI alias` |
| **security** | boundary hardening | `0173537e enforce directory boundary in isTrustedPrefix`, `811123a3 write refreshed OAuth tokens back to Keychain` |
| **CI guard** | dev discipline | `267de64d ci(guard): fail PRs that commit dist/ or bridge/`; `a3880d81`/`2506f90c` runner moves |
| **force-agent-delegation** | opt-in preflight | `d2c05f3f Add opt-in force-agent-delegation preflight` (adds `scripts/lib/force-agent-delegation-preflight.mjs`) |

No skills were removed in the window. No agents were removed (the roster is stable at 19; see §7). The renames/removals present are all in build artifacts and legacy standalone hook files (`4955f4f6`), not in the skill/agent/tool surface a sibling would depend on.

### 1a. The one structural feature: multi-repo workspace (`1484fa07`)

This is the single most consequential change for the state-schema surface that the prior reference documented. It generalizes "single repo == single state root" to "N git repos sharing one logical workspace." The commit body and `src/lib/worktree-paths.ts` establish a new resolution order for `getOmcRoot()`:

```
OMC_STATE_DIR (env)  >  .omc-workspace marker (WORKSPACE_MARKER, worktree-paths.ts:30)
                     >  git top-level  >  cwd
```

New mechanisms, all in `src/lib/`:
- `.omc-workspace` marker file anchors `.omc/` at a **non-git parent** dir (`worktree-paths.ts:30`), with a scan that stops before `$HOME` so a stray `~/.omc-workspace` cannot capture unrelated repos (`worktree-paths.ts:102`).
- `OMC_STATE_DIR` centralizes state at `$OMC_STATE_DIR/{project-identifier}/` (`worktree-paths.ts:297,496,503`; "Issue #1014").
- Branded `ReadPath` / `WritePath` types produced **only** by `resolveSessionStatePaths(name, sessionId, dir)`, so a read path can never be silently used as a write path. An ESLint `no-restricted-syntax` rule (`eslint.config.js:53-59`) bans `as ReadPath`/`as WritePath` casts outside `worktree-paths.ts`.
- `resolveSessionId()` centralizes session-id resolution — hook payload wins for hooks, env wins for CLI (`src/lib/session-id.ts`).
- Opt-in legacy migration only: `OMC_MIGRATE_LEGACY_STATE=1`; nothing is copied by default.
- PID-aware liveness in the session-start hook (a dead owner session no longer suppresses state restore); subagent-tracker moved to session-scoped paths + `withFileLockSync`.
- HUD gained a multi-repo workspace chip (`src/hud/elements/multi-repo.ts`) and an "L" suffix on the version when running from a local fork (detected even when copied, not symlinked, into the plugin cache).
- CI guard `scripts/ci/check-multirepo-paths.mjs` keeps new code on the canonical helpers (wired into `ci.yml`).

### 1b. Team and hooks reliability arcs (the bulk of the 144)

Beyond the one feature, the delta is a sustained hardening of the two most failure-prone subsystems — the team runtime (CLI-worker pane orchestration) and the UserPromptSubmit/Stop hook chain. These are worth reading as arcs because a sibling re-implementing either will hit the same edge cases.

The **team** arc (all under PR #3224 and around it) fixed silent-failure and race classes rather than adding capability: `d1a5d27e` stops an `N:agent:role` team spec from *silently collapsing to `claude`* when a provider is unparseable (validate-and-reject instead of degrade); `a10e96b6` stamps dispatch cooldowns *only on successful delivery* (a failed delivery previously cooled down a worker that never got the message); `257aab9b` excludes harness files from the worktree auto-merge so a worker's scratch edits do not land; `635ec8f9` and `9c0f732a` tolerate slow / cmux worker startup repaints. The recurring theme is "fail loud or retry, never silently degrade to a wrong-but-plausible state."

The **hooks** arc targets the cold-start timeout budget that governs whether OMC's routing text reaches Claude at all: `4207e0f1` and `7bfd777b` raise the UserPromptSubmit timeout so the skill-injector/keyword-detector path *fails open before Claude Code discards the output* (a too-tight budget silently dropped routing). Persistent-mode got two bounds: `c4c00bbf` caps thinking-only continuation loops, and `090e3fab` keeps Stop-hook reinforcement quiet while a delegated subagent is running (so the parent does not spam continuation prompts into a child's turn). `0b9f7225` honors `stop_hook_active` to avoid re-entrant Stop firing. All of these are fail-open designs: when the guard cannot decide, it yields rather than blocks.

### 1c. Keyword-detector precision (multilingual, quote-aware)

The keyword-detector — OMC's cheapest routing layer — gained precision, not just coverage. `src/features/magic-keywords.ts` strips code (`` ``` `` fenced and inline backtick spans, `CODE_BLOCK_PATTERN`/`INLINE_CODE_PATTERN`) before matching, so a keyword inside a code sample cannot trigger a mode. `4a32b88d` extends that to quoted spans, and `7b453e71` fixes "informational occurrence scanning": an **`INFORMATIONAL_INTENT_PATTERNS`** array with an 80-char context window (`INFORMATIONAL_CONTEXT_WINDOW = 80`) suppresses activation when the keyword sits inside a *question about* the feature rather than a *command to run* it — in English (`what is`, `explain`, `how to use`), Korean (`뭐야`, `설명`, `사용법`), Japanese (`とは`, `使い方`, `説明`), and Chinese (`什么是`, `如何使用`, `说明`). The Japanese katakana detection (`16ffb0b1`, `fd15bc3f`) added the same guard for `〜について教えて`. `2c922041` made the magic-keyword trigger table configurable rather than hard-coded. This is the single mechanism most likely to mis-fire in a sibling that copies keyword routing naively.

Note on the count discrepancy: the brief cites a "153-commit delta"; the reproducible figure is **144** non-merge commits (`git log --oneline --no-merges 2733c168..HEAD | wc -l`). The gap is the ~9 merge commits in the range (dev->release merges), which `--no-merges` excludes; counting *with* merges brings the total near 153.

---

## 2. Stale claims in the prior sibling reference (omc-harness-reference-v4.14.4.md)

Every claim below was true at `2733c168` and is now inaccurate at v4.15.2. A sibling maintainer must correct these.

| # | Prior claim (v4.14.4 ref) | Now | Evidence |
|:--|:--|:--|:--|
| 1 | "**~28 agent definitions** (`agents/`)" (§1) | **19** agent `.md` files | `ls agents/*.md | wc -l` = 19 (analyst, architect, code-reviewer, code-simplifier, critic, debugger, designer, document-specialist, executor, explore, git-master, planner, qa-tester, scientist, security-reviewer, test-engineer, tracer, verifier, writer) |
| 2 | "~40 skills" (§1) | still ~40 (**40** skill dirs) | `ls -d skills/*/ | wc -l` = 40 — this one holds |
| 3 | "OMC writes state under the **repo root** by convention" (§2) | Resolution is now `OMC_STATE_DIR > .omc-workspace > git root > cwd`; repo root is only the 3rd fallback | `worktree-paths.ts:28,30,297,503`; commit `1484fa07` |
| 4 | Pinned version `v4.14.4` / sha `2733c168` (header) | `v4.15.2` / sha `d41f1730a71dfbb472424406a765efea5b5f10f0` | `git rev-parse HEAD`; `package.json` `"version": "4.15.2"` |
| 5 | Model routing implicit (haiku/sonnet/opus tiers, §4) | Adds a **`fable`** tier alias; defaults are `SONNET='claude-sonnet-5'`, `OPUS='claude-opus-4-8'`, `FABLE='claude-fable-5'` | `src/config/models.ts:8,34-36,196`; commits `952d1575`, `33c4ed2e`, `13b6b341` |
| 6 | Team/ask providers implied as claude/codex/gemini (§4 lane model) | Adds **antigravity (`agy`)**, **Grok Build**, **Cursor** as CLI-worker + ask providers | `src/cli/ask.ts:18` (`ASK_PROVIDERS`), `src/shared/types.ts:25`, `src/team/cli-detection.ts:40` (`agy` binary); commits `1871a64d`, `3cce4961`, `707ac09b` |
| 7 | Hook list (§1) does not include a drift guard | New **workflow-drift-guard** Stop-hook (`templates/hooks/workflow-drift-guard.mjs`) | commits `86ea0470`, `23338277` |
| 8 | omha cards "`omc.json` + `superpowers.json` only" (§6) | Not verifiable from THIS repo (omha is a separate repo, `luckkim123/oh-my-heroacademia`); treat as unverified rather than current | prior ref §6 — out of this snapshot's scope |

Claims that **remain valid**: single MCP server registered as `t` (`.mcp.json`); the `src/` -> `dist/` TypeScript build model; the autoresearch evaluator-contract / keep-policy patterns (§5) — `dist/autoresearch/runtime.js` changed only cosmetically in the window (`1484fa07` touched it for path-helper routing, not contract semantics); `session_id` mandatory in path getters (now enforced structurally via branded types).

---

## 3. Release and versioning discipline (from git history)

The tag sequence `v4.14.0 ... v4.14.7, v4.15.0, v4.15.1` (and HEAD = v4.15.2) over the range `2026-05-26` -> `2026-07-03` shows a **dev-branch -> release-merge** cadence. Release commits are explicit and machine-shaped: `chore(release): bump version to vX.Y.Z` immediately followed by `chore(release): merge dev for vX.Y.Z` (e.g. `50ad97bd` + head merge for 4.15.2; `718a0d33` + `542b7a4c` for 4.15.0).

Observable discipline:
- **SemVer by content**: 4.15.0 is the only minor bump in the window and is exactly where the multi-repo feature + new providers landed; everything else (4.14.5/6/7/8, 4.15.1/2) is a patch of pure fixes.
- **`npm version` hook**: `package.json` `"version": "bash scripts/sync-version.sh"` — bumping the version fans the number out across files deterministically.
- **CHANGELOG is per-release, not cumulative**: `CHANGELOG.md` is only 34 lines and describes solely v4.15.2 (`git log -- CHANGELOG.md` shows it is overwritten each release). Historical notes live in `.github/release-notes.md` / `docs/MIGRATION.md`, not in a growing CHANGELOG.
- **Artifacts are committed but guarded**: `dist/` and `bridge/` are tracked in-repo (so the plugin works when installed straight from git), but PR-only CI job `No Committed Build Artifacts` (`267de64d`, `ci.yml:132`) fails any PR that changes them — the maintainer rebuilds at merge/release. This is the resolution of a real incident (a rebuilt bridge bundle slipped into #3350).
- **Conventional Commits** with structured trailers (`Confidence:`, `Scope-risk:`, `Rejected:`, `Not-tested:`) are standard in feature/guard commits (see `267de64d`, `1484fa07` bodies).

---

## 4. Peripheral top-level directories: runtime vs dev-only vs demo

None of these ship to end users: `package.json` `"files"` publishes only `dist, agents, bin, bridge, commands, hooks, scripts, skills, templates, docs, .claude-plugin, .mcp.json, README.md, LICENSE`. Everything in the table below except `templates/` and `docs/` is **excluded from the npm package** and is therefore dev-only or demo material.

| Dir | Classification | What it is (evidence) |
|:--|:--|:--|
| `templates/` | **RUNTIME** (published) | `templates/hooks/*.mjs` are the actual hook implementations deployed by the installer (`keyword-detector.mjs`, `persistent-mode.mjs`, `workflow-drift-guard.mjs`, `stop-continuation.mjs`, ...); `templates/rules/*.md` (`karpathy-guidelines.md`, `security.md`, `git-workflow.md`) are rule payloads; `templates/deliverables.json`. This is not demo material. |
| `docs/` | **RUNTIME** (published) + authoritative | 39 files, ~11.3k lines; see §5. Shipped in the tarball. |
| `benchmark/` | **dev-only** (eval) | SWE-bench harness comparing vanilla vs OMC-enhanced Claude Code — `Dockerfile`, `docker-compose.yml`, `run_full_comparison.sh`, `evaluate.py`, `analyze_failures.py` (`benchmark/README.md`). External eval rig, not wired into any hook. |
| `benchmarks/` | **dev-only** (regression) | Agent-prompt quality benchmarks run via `npm run bench:prompts` -> `tsx benchmarks/run-all.ts`; per-agent fixtures (`critic|code-reviewer|debugger|executor`) + saved `baselines/`. `--save-baseline`/`--compare`/`--dry-run` flags (`benchmarks/run-all.ts:1-45`). Wired into `package.json` scripts, NOT into CI-per-commit. |
| `geobench/` | **demo/marketing** | One file: `geobench/oh-my-claudecode.yaml`, a product profile for the external [NomaDamas/geobench](https://github.com/NomaDamas/geobench) LLM-visibility tool (hit rate, MRR, share-of-voice). "Publish aggregate metrics only" (`docs/geobench.md`). Not runtime. Recent commits `d9889ae6`/`520d4313`/`c3d40a05` fixed its schema. |
| `shellmark/` | **dev-only** (captured trace) | A single recorded shell session under `shellmark/sessions/<ts>/` with `manifest.json` (`"schema_version":"shellmark/v1"`), `events/` (raw+meta+summary), and `indexes/` (`by_status.jsonl`, `by_time.jsonl`). A tool-output capture sample, not a live system. |
| `seminar/` | **demo** | Talk material — `slides.md`, `slides.pdf`, `quickref.md`, and `demos/demo-{0..5}-*.md` (autopilot, ultrawork, pipeline, planning, ralph). Presentation assets. |
| `research/` | **dev-only** (design note) | One file: `hephaestus-vs-deep-executor-comparison.md`, a 14-dimension architecture comparison of oh-my-opencode's Hephaestus vs OMC's Deep-Executor. Design rationale, not code. |
| `examples/` | **demo** (dev SDK) | `basic-usage.ts`, `advanced-usage.ts`, `delegation-enforcer-demo.ts` (imports `enforceModel` etc. from `../src/index.js`), `hooks.json`, `vendor-mcp-server/`. Demonstrates the published `dist/index.js` SDK surface. |
| `missions/` | **dev-only** (agent tasks) | `missions/<slug>/{mission.md, sandbox.md}` — terse self-improvement task specs (`optimize omc`, `enhance-omc-performance`, `prove-reliability-by-finding-and-fixing-flaky-tests`). Inputs for OMC's own self-improve/autoresearch loops run against itself. |
| `assets/` | **marketing** | Two images: `omc-character.jpg`, `omc-social-preview.jpg`. README/social art. |

---

## 5. The `docs/` corpus (authoritative internal architecture)

38 `.md` files, ~11,305 lines (plus one `.png` under `docs/issues/`, so 39 files total). This is the closest thing to an internal architecture SSOT and is worth mining as a shortcut past reading `src/`. The heaviest, most authoritative files:

| File | Lines | Authority for |
|:--|:--|:--|
| `docs/REFERENCE.md` | 1273 | Full command/skill/tool reference |
| `docs/COMPATIBILITY.md` | 1068 | Claude Code version compatibility matrix |
| `docs/design/project-session-manager.md` | 1033 | Worktree-first session manager design |
| `docs/MIGRATION.md` | 949 | Cross-version migration + historical release notes |
| `docs/TOOLS.md` | 785 | MCP tool catalog (the `t` server surface) |
| `docs/ARCHITECTURE.md` | 618 | The four-system model: Hooks -> Skills -> Agents -> State; states "**19 specialized agents organized into 4 lanes**" (matches disk, contradicts prior ref's "~28") |
| `docs/FEATURES.md` | 582 | Feature inventory |
| `docs/SYNC-SYSTEM.md` | 526 | Metadata/version sync machinery |
| `docs/PERFORMANCE-MONITORING.md` | 505 | Perf-bench + budgets |
| `docs/HOOKS.md` | 495 | Hook lifecycle + registration |
| `docs/DELEGATION-ENFORCER.md` | 277 | Auto-model-injection for Task/Agent calls |
| `docs/design/TIERED_AGENTS_V2.md` | 323 | Agent-tier model |

`docs/ARCHITECTURE.md:7` names the load-bearing invariant a sibling should copy conceptually: "**Hooks** detect lifecycle events, **Skills** inject behaviors, **Agents** execute specialized work, and **State** tracks progress across context resets." `docs/` is composed at build time by `npm run compose-docs` (`scripts/compose-docs.mjs`), so shared fragments (`docs/shared/*.md`, `docs/agent-templates/*.md`) are single-sourced.

---

## 6. The `AGENTS.md` guidance hierarchy

OMC ships a **tree of `AGENTS.md` files** (10 total: 7 under `src/` + repo-root + `docs/` + `skills/`), each scoping guidance to its subtree — a pattern a sibling can adopt directly for its own `src/`:

```
AGENTS.md                      # repo-level orchestration guidance (the "user-facing" contract, 21.8 KB)
docs/AGENTS.md
skills/AGENTS.md
src/AGENTS.md                  # src-wide working agreements
├── src/agents/AGENTS.md
├── src/features/AGENTS.md
├── src/hooks/AGENTS.md
└── src/tools/AGENTS.md
    ├── src/tools/diagnostics/AGENTS.md
    └── src/tools/lsp/AGENTS.md
```

The root `AGENTS.md` declares a `<guidance_schema_contract>` binding it to `docs/guidance-schema.md`, with **marker-bounded runtime overlay regions** that hooks append into without destroying the base:
```
<!-- OMX:RUNTIME:START --> ... <!-- OMX:RUNTIME:END -->
<!-- OMX:TEAM:WORKER:START --> ... <!-- OMX:TEAM:WORKER:END -->
```
Its `<working_agreements>` block hard-wires the branded-path rule: "For session-scoped state paths, resolve via `resolveSessionStatePaths()` only ... ESLint `no-restricted-syntax` blocks `as ReadPath` / `as WritePath` casts outside `src/lib/worktree-paths.ts`." So the architectural constraint is enforced in three places simultaneously: the type system (branded types), the linter (`eslint.config.js:53`), and the prose contract (`AGENTS.md`).

---

## 7. Tests, CI, and build machinery (runtime vs dev-only)

**Tests (dev-only):** 574 `*.test.ts` files under `src/**/__tests__` plus `tests/{fixtures,integration,lint,perf}`. Runner is Vitest (`vitest.config.ts`: `testTimeout: 30000`, coverage via `v8`, `tests/**/*.bench.ts` included). None ship in the tarball (`dist/` is excluded from coverage; test files excluded from `"files"`).

**CI (dev-only), `.github/workflows/`:** `ci.yml`, `pr-check.yml`, `release.yml`, `upgrade-test.yml`, `auto-label.yml`, `stale.yml`, `cleanup.yml`. `ci.yml` jobs: **Lint & Type Check** (ubuntu), **Test** (ubuntu), **Test (Windows path suite)** (`windows-latest` — the window added a *real* Windows runner, `d44a0064`, because so many fixes were Windows path-handling), **Build** (with a `dist > 50MB` size warning at `ci.yml:117-122`), and **No Committed Build Artifacts** (PR-only guard, `ci.yml:132`). Runner migration to GitHub-hosted / self-hosted happened in-window (`a3880d81`, `2506f90c`).

**Build (dev-only), `package.json` `"build"`:** `tsc` -> `build-skill-bridge.mjs` -> `build-mcp-server.mjs` -> `build-bridge-entry.mjs` -> `compose-docs` -> `build:runtime-cli` -> `build:team-server` -> `build:cli`. Multiple bundle targets (esbuild): `bridge/mcp-server.cjs`, `bridge/team-*.cjs`, `bridge/cli.cjs`, `bridge/runtime-cli.cjs`. `prepublishOnly` re-runs build + compose-docs.

**Lint/type config (dev-only):** ESLint flat config (`eslint.config.js`) with the load-bearing `no-restricted-syntax` brand-cast ban (§1a/§6). `tsconfig.json`, `typos.toml`, `prettier` via `npm run format`.

**Runtime deps** (`package.json` `"dependencies"`, these DO ship): `@anthropic-ai/claude-agent-sdk`, `@ast-grep/napi` (structural search tool), `@modelcontextprotocol/sdk`, `better-sqlite3` (job/session state DB), `ajv` + `zod` (schema validation), `jsonc-parser` (tolerant config parsing — `3fe1253e` added trailing-comma tolerance), `safe-regex` (ReDoS guard on user-supplied keyword triggers), `vscode-languageserver-protocol` (LSP tool), `chalk`, `commander`. `engines: node >=20`.

---

## 8. `src/` topology and where the code mass lives

The 144-commit delta's shape (hooks + team dominant) tracks the actual code-mass distribution. Non-test TypeScript LOC by top-level `src/` module:

| Module | ~LOC | Role |
|:--|--:|:--|
| `src/hooks/` | 45,124 | Every lifecycle hook (UserPromptSubmit, PreToolUse, PostToolUse, Stop, SubagentStop, SessionStart/End). By far the largest — the routing/discipline surface. |
| `src/team/` | 21,522 | CLI-worker pane orchestration, inbox/outbox, provider routing, tmux/psmux comms. |
| `src/features/` | 14,410 | `magic-keywords.ts`, delegation-enforcer, and other injected behaviors. |
| `src/tools/` | 11,020 | The MCP `t` server tools (state, notepad, wiki, ast-grep, lsp, session-search, ...). |
| `src/hud/` | 10,245 | Statusline HUD elements incl. `multi-repo.ts`. |
| `src/cli/` | 9,814 | `omc` CLI (`ask`, `team`, `ultragoal`, doctor commands). |
| `src/notifications/` | 6,850 | Telegram/Discord/Slack dispatch. |
| `src/lib/` | 5,200 | `worktree-paths.ts`, `session-id.ts`, locking, state IO — the load-bearing helpers. |
| `src/autoresearch/`, `src/ultragoal/`, `src/ralphthon/`, `src/openclaw/` | ~1,900 / 899 / 1,462 / 1,293 | The autonomous-loop engines (patterns §5 of the prior ref lives in `autoresearch/`). |

**`scripts/` (dev + install machinery, published):** the `build-*.mjs` esbuild bundlers; `compose-docs.mjs`; `plugin-setup.mjs` (installer); the deployed hook implementations that mirror `templates/hooks/` (`keyword-detector.mjs`, `persistent-mode.mjs`, `post-tool-*.mjs`, `pre-tool-enforcer.mjs`, `context-guard-stop.mjs`); `scripts/ci/` guards (multirepo path check, dist guard); `eval-autoresearch-*.mjs` for offline evaluator testing; `generate-featured-contributors.ts` / `sync-metadata.ts` (README/marketplace sync, run via `npm run sync-*`). `docs/design/` holds the roadmap corpus a sibling should skim before assuming intent: `CONSOLIDATION_PHASE3_ROADMAP.md`, `SKILLS_2_0_ADAPTATION.md`, `TIERED_AGENTS_V2.md`, `CLAUDE_CODE_GOAL_ADAPTER.md`, `SKILL_AUDIT_1445.md`, `project-session-manager.md`.

---

## Patterns for sibling harnesses

- **Anchored state resolution with a marker file and an env override.** OMC's `OMC_STATE_DIR > .omc-workspace > git root > cwd` chain (`worktree-paths.ts:503`) lets one logical workspace span N git repos. *Adaptation: a sibling should define its own marker (`.omx-workspace`) and env var (`OMX_STATE_DIR`), never reuse OMC's, so the two harnesses never fight over an anchor.*
- **Branded read/write path types enforced by type + lint + prose.** `ReadPath`/`WritePath` minted only by `resolveSessionStatePaths()`, with an ESLint `no-restricted-syntax` rule banning the cast escape hatch. *Adaptation: a cheap way to make "never write to a read-scoped path" a compile-time guarantee in any TypeScript harness.*
- **Marker-bounded runtime overlay regions in a guidance file.** `<!-- OMX:RUNTIME:START/END -->` lets hooks append per-session guidance into `AGENTS.md` non-destructively. *Adaptation: reuse the exact marker convention (siblings already use `OMX:` markers) so overlays are idempotent and removable.*
- **Committed-but-guarded build artifacts.** Ship `dist/` in-repo so git-installs work, but add a PR-only CI job that fails any PR touching `dist/`/`bridge/` (`ci.yml:132`). *Adaptation: only needed if a sibling also installs straight from git; otherwise gitignore dist and skip the guard.*
- **Per-release-overwritten CHANGELOG + `npm version` fan-out script.** `CHANGELOG.md` holds only the current release; `scripts/sync-version.sh` (wired as the npm `version` lifecycle hook) propagates the number. *Adaptation: keep history in release-notes/migration docs, not a growing CHANGELOG, to avoid merge churn.*
- **Structured commit trailers as machine-readable rationale.** `Confidence:`, `Scope-risk:`, `Rejected:`, `Not-tested:` in feature/guard commit bodies. *Adaptation: a low-cost audit trail; a sibling can grep these to reconstruct decision history.*
- **A `mission.md` + `sandbox.md` task format for running the harness against itself.** `missions/<slug>/` feeds OMC's own self-improve loop. *Adaptation: a sibling with an autoresearch/self-improve lane can adopt the same two-file mission spec for dogfooding.*
- **Two separate benchmark rigs: agent-prompt regression (`benchmarks/`, baseline diff) vs external-task eval (`benchmark/`, SWE-bench).** *Adaptation: keep prompt-quality regression (fast, per-branch, baseline-compared) distinct from expensive end-to-end task eval (Dockerized, occasional).*

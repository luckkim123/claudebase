# Gap Analysis — oh-my-heroacademia (omha) vs OMC v4.15.2

Sibling harness snapshot: `/root/omha-src` (v0.7.2 code, CHANGELOG through 0.7.2 plus
uncommitted hard-gate work at HEAD `7c865be`). Scope of this analysis: **routing-relevant OMC
surface changes** and **hook-engineering patterns worth adopting** — omha is a meta-router, not a
work harness, so most of OMC's 49 MCP tools / modes / agents are out of scope by design. ZERO
runtime dependency on OMC is a hard rule and every suggestion below respects it (omha stays
stdlib-only Python that re-implements patterns in its own idiom).

## Philosophy

omha is a **declarative harness registry + meta-router**, not a work harness. Its entire runtime is
five stdlib-only Python hooks (~950 LOC total) plus six `cards/*.json`. The stated invariants, read
from its own docs and code:

- **No server, no state machine, no in-process routing brain.** "The Claude Code session itself
  reads these cards and does the routing (LLM judgment). There is no server." (`README.md:5-6`). The
  hook only *feeds* the model cards; the model names the lane.
- **Cards are the single source of truth; hooks read, never embed.** The no-drift principle
  (`route_emit.py:1-7`) — knowledge lives in `cards/*.json`, the hook injects procedure only, so
  there is no SKILL.md↔reminder.py duplication.
- **Zero runtime dependencies, Python 3.9+.** `pyproject.toml:5-6` (`dependencies = []`); a
  `test_hook_has_no_third_party_imports` enforces it (CHANGELOG 0.5.0). `Optional[X]` over `X | None`
  for 3.9 compat.
- **Fail-open everywhere.** Every hook degrades to exit-0 / `{continue:true}` on any error
  (`route_emit.py:153-154`, `cross_lane_emit.py:14`, all guards' `except Exception: return 0, None`).
  Routing must never block a session.
- **Routes lanes, not skills.** "The *skill* inside that lane is picked by the lane's own plugin
  (OMC's keyword-detector, SP's using-superpowers), not by omha." (`README.md:84-86`). Cards are
  harness-unit, not skill-unit (CHANGELOG 0.2.0) — deliberately lean to avoid over-attraction.
- **Pull + push + hard-gate.** Pull = `UserPromptSubmit` ROUTE injection (`route_emit.py`); push =
  `PreToolUse` cross-lane advisory (`cross_lane_emit.py`); hard-gate = three enforcement hooks
  (`route_guard.py`, `route_stop_guard.py`, `critic_reread_guard.py`) that *deny/block* until a ROUTE
  line exists or cited code was actually opened.
- **Advisory over blocking, with a deliberate exception.** Push and pull are advisory; the ROUTE
  hard-gate is the one place omha crossed into `permissionDecision:deny` / `decision:block` — but only
  to force a *routing declaration*, never to veto the work itself.

Any adoption must keep the router thin, stdlib-only, fail-open, and card-sourced. Anything that adds a
daemon, a dependency, or moves the routing brain into code is out of bounds.

## Capability coverage

OMC's fleet matrix has 19 capability areas; the vast majority (MCP tools, autonomous modes, team,
planning, research, agents, HUD) are **NOT-APPLICABLE** — omha is a router with no work surface. The
rows below cover only the areas where OMC's mechanism is *routing-relevant* or a *reusable hook
pattern*.

| Area (OMC) | omha status | Evidence in omha | Note |
|---|---|---|---|
| Fail-open hook discipline (`§02`) | HAS | `route_emit.py:153`, all guards `except: return 0,None` | Independently reinvented; matches OMC's exit-0-always posture |
| Hook = injected `additionalContext` envelope (`§02`) | HAS | `route_emit.py:155-156`, `cross_lane_emit.py:146-147` | Same `hookSpecificOutput` shape |
| Arm/confirm/enforce Stop handshake (`§02`) | PARTIAL | `route_stop_guard.py`, sentinel fire-once | Has fire-once + flush-retry but no `awaiting_confirmation` TTL grace window |
| Echo-stripping before matching (`§02`, keyword-detector.mjs:442-461) | ABSENT | injected banner `<omha-routing>` never stripped from later prompts | omha's ROUTE banner is re-injected every turn; a pasted transcript could re-feed it |
| Session-scoped sanitized state ids (`§02`, `§15`) | ABSENT | `route_guard.py:107` raw `f"omha_route_gate_{session_id}.json"` in `gettempdir()` | No `/^[a-zA-Z0-9...]$/` guard; unsanitized id in a path |
| Staleness TTL on persistent artifacts (`§02`, `§15`) | ABSENT | sentinels + `omha_last_push.json` never expire | Crash-abandoned sentinel keyed by turn_id self-clears, but push cooldown file is global and immortal |
| Kill switches `DISABLE_OMC`/`OMC_SKIP_HOOKS` (`§02`, `§15`) | ABSENT | no env gate in any hook | Cannot disable omha routing without uninstalling |
| Content-hash advisory throttle (`§02`, `§19`) | PARTIAL | `cross_lane_emit.py:100-119` 30 s lane cooldown | Single global slot (`omha_last_push.json`), not per-session, not content-hashed |
| `deny`-with-feedback semantics (`§19`, pre-tool-enforcer) | HAS | `route_guard.py:177-181` `permissionDecision:deny` while `continue` stays true | Same "deny so the agent retries corrected" pattern |
| `updatedInput` config-driven tool mutation (`§19`) | NOT-APPLICABLE | — | omha never rewrites tool input; routing is declarative |
| Cheap context preflight by transcript tail-read (`§19`) | ABSENT | guards read *full* transcript (`readlines()`) | `route_guard._scan_turn` reads the whole JSONL each PreToolUse; no tail-bound |
| Subagent-exempt gate (`§19`) | HAS | `route_guard.py:152`, `critic_reread_guard.py:198` `agent_id/agent_type` early return | Correct — subagents lack the omha injection |
| Fire-once sentinel to avoid stop-loop (`§06`, `§02` persistent-mode) | HAS | `route_stop_guard.py:52-55`, dedicated per-hook sentinel | With the critical "never share a sentinel across hooks" note (`critic_reread_guard.py:23-26`) |
| Card/skill registry as SSOT, drop-a-file extensibility (`§16`) | HAS | `cards/*.json` glob-discovered; `registry.py` typed validation | OMC's SKILL.md-as-SSOT analog, done as JSON cards |
| Multi-runtime one-source (`§16`) | PARTIAL | cards read by 2 hooks + `registry.py` | Runtime hooks bypass `registry.py` (stdlib `json.loads`); typed layer is dev/CI-only by design |
| Marker-fenced managed regions (`§01`) | NOT-APPLICABLE | omha writes no shared user files | Routes only; nothing to fence |
| Install/manifest self-repair (`§01`) | ABSENT | relies on `${CLAUDE_PLUGIN_ROOT}`; no cache-drift heal | Real gap noted in CHANGELOG 0.6.0 Notes (cache pinned to gitCommitSha, manual reinstall) |
| Inner-timeout fail-open runner (`§01`, run.cjs) | ABSENT | hooks are direct `python3` spawns, no wrapper timeout | A hung `readlines()` on a huge transcript has no cushion kill |

## Adoption candidates (prioritized)

Ordered by leverage: correctness/safety of the hard-gates first, then robustness, then hygiene.

### 1. Session-scoped, sanitized, TTL'd state paths (highest leverage — a live correctness hole)

- **OMC mechanism**: session ids validated against `/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,255}$/` before use
  in any path (`§02`/`§15`, `scripts/lib/state-root.mjs:32-52`; keyword-detector uses it as a
  path-traversal guard), state under `state/sessions/<sid>/`, and every artifact carries a staleness
  TTL (`§02`: 2 h mode state, 30 s cancel signal, 24 h tombstones).
- **Why omha needs it**: `route_guard._sentinel_path` does
  `os.path.join(tempfile.gettempdir(), f"omha_route_gate_{session_id}.json")` (`route_guard.py:107-108`,
  mirrored in `critic_reread_guard.py:157-158`) with **no sanitization** of `session_id`. Claude Code
  session ids are UUIDs today so this is latent, but a `session_id` containing `../` or a path
  separator would write outside the temp dir. The sentinels are keyed by `turn_id` so they self-heal
  per turn, but there is no upper bound on accumulation across sessions — `/tmp` slowly fills with
  `omha_route_gate_*.json` / `omha_critic_reread_*.json` that never get reaped.
- **Adaptation (omha idiom)**: add a `_safe_sid(session_id)` helper in `route_guard.py` reused by all
  three guards — reject with a fallback constant id if it fails `re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,255}", sid)`
  (refuse-then-fallback, do not silently pass a dirty id into the path). Add a lazy reaper: on sentinel
  write, `glob` `omha_*_*.json` in the temp dir and unlink any whose mtime is older than, say, 6 h.
  Keep it stdlib (`re`, `pathlib`, `os.stat`), keep it fail-open (a reaper `OSError` must not break the
  gate). This is one small module shared by the three guards — no card change, no new dependency.

### 2. Kill switch env var for the whole router (`DISABLE_OMHA` / `OMHA_SKIP_HOOKS`)

- **OMC mechanism**: `DISABLE_OMC` makes every hook return `{continue:true}` immediately;
  `OMC_SKIP_HOOKS=a,b` disables named hooks by token (`§02`/`§15`, keyword-detector.mjs:1186,
  pre-tool-enforcer.mjs:1216-1221). Re-checked at every hook entry.
- **Why omha needs it**: omha now runs *five* hooks including two hard-gates that emit
  `permissionDecision:deny` and `decision:block`. There is currently no way to turn omha off short of
  `claude plugin uninstall`. When a user is debugging a routing false-deny (the exact flush-race /
  shared-sentinel class the recent commits fixed), they need a one-env-var escape hatch — and a
  subagent-driven session or a CI run may want omha's ROUTE nagging silenced entirely.
- **Adaptation (omha idiom)**: at the top of each hook's `main()`, before any work:
  `import os; if os.environ.get("DISABLE_OMHA") == "1": return 0`. For granularity, honor a comma list
  `OMHA_SKIP_HOOKS` with tokens `route-emit`, `cross-lane`, `route-guard`, `route-stop`,
  `critic-reread` — each hook checks its own token. Five one-line guards; matches OMC's `== '1'`
  strictness. This is the single cheapest safety addition and directly serves the "user debugging a
  false-deny" case the harness has already hit twice.

### 3. Per-session, content-hashed advisory throttle for the push channel

- **OMC mechanism**: advisory messages are hashed and suppressed within a cooldown window, stored in a
  per-session `pre-tool-advisory-throttle.json` (max 100 entries, prune-on-write), fail-open on IO
  error (`§02`/`§19`, pre-tool-enforcer.mjs:317-404, `shouldEmitAdvisoryMessage`).
- **Why omha needs it**: `cross_lane_emit.py` uses a **single global slot**,
  `/tmp/omha_last_push.json` with one `{lane, ts}` record (`cross_lane_emit.py:27-28, 122-130`). Two
  concurrent Claude sessions on one machine share that file, so session A's `.pptx` write suppresses
  session B's cross-lane advisory for 30 s — a cross-session false-silence. It also can't distinguish
  "same lane, different signal" from a true repeat.
- **Adaptation (omha idiom)**: key the cooldown file by session id (read `session_id` from the
  PreToolUse stdin payload — it is present, `route_guard` already reads it) →
  `omha_last_push_{safe_sid}.json`, reusing the `_safe_sid` from candidate 1. Optionally store the
  last `(lane, signal_value)` pair rather than lane alone, so a lane switch OR a new signal re-emits
  while a genuine repeat stays quiet. Keep the 30 s window and the fail-open-on-corrupt-JSON
  (`cross_lane_emit.py:107-119`) exactly as is. Small, self-contained, no card change.

### 4. Echo-stripping / inertia-hardening of the re-injected ROUTE banner

- **OMC mechanism**: before keyword matching, OMC strips its *own* prior banners
  (`[RALPH LOOP]`, `[MAGIC KEYWORD:]`, `PreToolUse ... hook additional context:` headers and their
  continuation lines — `SYSTEM_ECHO_BLOCK_PATTERNS`, keyword-detector.mjs:442-461), because "pasting a
  previous loop banner into a new session would re-trigger... a recursive self-reinforcing loop"
  (`§02`).
- **Why omha needs it**: `route_emit.py` injects a large `<omha-routing>` block *every turn*, and the
  push/guard hooks emit `⚠️ omha cross-lane signal` and `ROUTE →` strings. omha's prose already warns
  the model about *routing inertia* ("직전 ROUTE 를 관성으로 복사하지 말고", `route_emit.py:53`), but the
  hooks themselves do no mechanical stripping. If a user pastes a prior transcript (which contains a
  `> **ROUTE →** ...` line) as input, `route_guard.has_route_line` scanning the *assistant* window is
  safe — but any future feature that reads the *user prompt* (e.g. a card-example matcher) would need
  the strip list. This is lower-severity for omha's current read-surface (guards read assistant text
  only), so it is a *pre-emptive* hardening tied to the no-self-reinforcement invariant, not a live
  bug.
- **Adaptation (omha idiom)**: if/when a hook ever matches against the user prompt, add a
  `_strip_omha_echoes(text)` that removes lines matching `<omha-routing>`…`</omha-routing>`,
  `^> \*\*ROUTE →\*\*`, `^> \*\*ANALYZE\*\*`, and `⚠️ omha cross-lane signal` blocks before matching.
  Ship it now as a documented helper even if unused, so the invariant is enforceable when the surface
  grows.

### 5. Bounded transcript tail-read in the guards (efficiency + hang-safety)

- **OMC mechanism**: context preflight reads only the **last 4 KB** of the transcript and parses the
  last `input_tokens`/`context_window` — "a cheap tail-read, not a full parse" (`§19`,
  pre-tool-enforcer-preflight.mjs).
- **Why omha needs it**: `route_guard._scan_turn` and `critic_reread_guard.scan_turn_full` do
  `f.readlines()` on the **entire** transcript JSONL every PreToolUse and Stop
  (`route_guard.py:77`, `critic_reread_guard.py:131`), then walk it backward to the last real user
  turn. On a long session that is a full-file read on every single tool call — and the whole thing runs
  inside a hook with no timeout cushion (candidate 8). The information needed is only the *current
  turn's* records, which are always at the tail.
- **Adaptation (omha idiom)**: read the file from the end in bounded chunks (seek to
  `max(0, size - N)` for an initial N like 256 KB, split into lines, walk backward; if the real-user
  boundary isn't found in the window, grow N and retry — the turn boundary is guaranteed present
  eventually). Preserve exact current semantics (same boundary logic, same `_is_real_user_turn`), just
  stop reading whole multi-MB transcripts. Pure `route_guard` internal change; the Stop guard and
  critic guard inherit it since they reuse `route_guard`'s scanner style.

### 6. Arm/confirm grace window to shrink the flush-race surface

- **OMC mechanism**: `UserPromptSubmit` arms state with `awaiting_confirmation` + a 2-minute TTL;
  `PreToolUse` confirms on the first real Skill call; Stop enforces only *confirmed, fresh* state
  (`§02`, persistent-mode.mjs:403-425). The handshake is what tells the Stop hook "enforcement may
  begin."
- **Why omha needs it**: omha's guards fight a transcript **flush race** — a real-work tool can fire
  before the assistant's ROUTE text is flushed to JSONL, causing a false deny. The recent fix is a
  3-attempt retry-sleep loop (`route_guard.py:165-171`, `route_stop_guard.py:42-50`,
  `critic_reread_guard.py:207-218`), which the session memory notes was itself a source of a latency
  bug (naive porting). An arm/confirm handshake is a more *structural* fix: `route_emit`
  (UserPromptSubmit) already fires first every turn and could "arm" the turn's expectation; the guard
  then reasons about confirmed vs unconfirmed instead of racing the flush.
- **Adaptation (omha idiom)**: have `route_emit.main()` write a tiny per-session, per-turn marker
  (turn is knowable only at guard time, so arm at prompt time with a timestamp + TTL). The guard treats
  "armed <2 min ago and no ROUTE yet" as a grace state (allow, don't deny) and only denies once the
  grace TTL passes without a ROUTE. This converts a timing race into a bounded grace window — the same
  move OMC made. Higher-effort than candidates 1-5 and partially overlaps the retry-sleep already
  shipped, so it is lower priority; adopt only if flush-race false-denies persist after the tail-read
  change reduces scan latency.

### 7. Install/cache drift self-heal note (documentation-level, low code)

- **OMC mechanism**: SessionStart repairs the plugin cache by symlinking stale version dirs to the
  newest, with a 24 h grace period (`§01`/`§02`, session-start.mjs:1014-1116); `CLAUDE_PLUGIN_ROOT`
  healing across cache versions in `run.cjs`.
- **Why omha needs it**: CHANGELOG 0.6.0 Notes already flags the exact pain — "the cache copy is
  pinned to a `gitCommitSha`... picking up these cards requires a plugin update/reinstall (the
  marketplace git pull alone updates the mirror, not the live cache)." Users silently run stale cards.
- **Adaptation (omha idiom)**: omha has no SessionStart hook and adding a cache-symlink repair would
  be over-engineering for a router. The proportionate adoption is a `SessionStart` (or a one-line
  addition to `route_emit`) that compares the loaded `cards/` commit/mtime against the marketplace
  mirror and injects a one-line advisory `[omha: cards may be stale — reinstall to refresh]` when they
  diverge. Advisory only, fail-open, no filesystem surgery. Lowest leverage of the list; include only
  if stale-card confusion recurs.

## Deliberately not adopting

- **OMC's 49 MCP tools / bridge server (`§03`-`§05`)** — omha routes lanes; it owns no work surface, so
  state/notepad/memory/LSP/python_repl tools have no home here. Adopting any would violate "no server,
  routes lanes not skills."
- **Autonomous modes & state machines (autopilot/ralph/ultrawork, `§06`-`§07`)** — omha explicitly has
  no runtime loop; the routing brain is the session. A mode state machine would re-introduce the server
  it deliberately deleted in v0.2.0.
- **`updatedInput` tool-input mutation (`§19`)** — omha's routing is declarative (the model names the
  lane); rewriting a tool call's input would move routing from advice into silent coercion, against the
  advisory-over-blocking invariant. The one sanctioned block (ROUTE hard-gate) forces a *declaration*,
  not a payload change.
- **Agent catalog / model-tier routing (`§12`, `§19` tier aliases)** — omha owns no agents and picks no
  models; that is each lane plugin's job. "The skill inside that lane is picked by the lane's own
  plugin."
- **Wiki / knowledge lifecycle / self-improve (`§10`-`§11`)** — persistence and learning belong to the
  work harnesses (omx `.omx/`, omp `.omp/`), not the router. Cards are the only knowledge omha holds,
  and they are hand-authored SSOT, not accreted.
- **npm dual-channel packaging + esbuild bundle (`§01`, `§03`)** — omha is stdlib Python with no build
  step; a bundle/npm channel contradicts "zero dependencies, drop-a-JSON-file extensibility." It ships
  as a Claude Code plugin + marketplace only.
- **HUD statusline / notifications (`§13`)** — no work state to display; a router has nothing to render.

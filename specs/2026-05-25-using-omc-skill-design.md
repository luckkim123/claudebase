# using-omc Skill Design

**Date:** 2026-05-25
**Repo:** claude-settings (`/root/claude-settings`)
**Status:** Design approved, pending implementation plan

## 1. Goal & Motivation

OMC (oh-my-claudecode) ships ~40 skills + 19 agents, but in practice they go
underused compared to superpowers. Root cause (verified, not guessed):

- **superpowers** injects its `using-superpowers` skill **in full** at every
  SessionStart via a plugin hook, wrapped in `<EXTREMELY_IMPORTANT>`. This keeps
  an *active* rule ("invoke a skill if even 1% relevant") resident every turn —
  the assistant is *pushed* to reach for skills.
- **OMC** only places trigger keywords in `CLAUDE.md`. Activation is *passive*:
  the user must say `"ralph"`, `"ultrawork"`, etc. If the user doesn't know or
  use the keyword, the skill never fires.

So the gap is not "the assistant doesn't know OMC skills exist" (the names + one-line
descriptions are in the session skill list). The gap is **no resident, active
routing rule that makes the assistant consciously consider the OMC lane each turn.**

`using-omc` closes this by mirroring superpowers' injection mechanism, but with
content tuned to OMC's nature.

## 2. Key Design Decision: enforce the *routing judgment*, not the *invocation*

OMC workflow skills (autopilot, ralph, ultrawork, team) are heavy, autonomous,
long-running. A superpowers-style "invoke if 1% relevant" rule would cause
**over-orchestration** of trivial work and conflicts with the existing CLAUDE.md
rule ("trivial → handle directly; irreversible/large → confirm first").

Therefore what is **enforced (resident every session)** is the *routing judgment*,
not the workflow invocation:

> For any multi-step request, consciously run the discipline-vs-throughput tree
> and **announce the verdict in one line** before starting — even when the verdict
> is "handle directly".

- Enforced = the *visibility of the judgment* (a one-line announce). This is cheap
  and reversible — safe to mandate.
- NOT enforced = actually invoking a heavy workflow. That stays gated by the
  existing trivial/confirm rules.

This is precisely the gap observed in the 2026-05-25 repo-split session: the
assistant took the right lane (superpowers, discipline-governed) but never
announced the routing verdict, making the choice non-auditable.

## 3. Relationship to superpowers: complement, reminder enforced

`using-omc` does NOT replace or fight `using-superpowers`. They split the
auto-route tree's two lanes:

- **discipline governs** (wrong = expensive; gates govern quality; non-trivial
  code; citation-bound writing) → **superpowers lane** (TDD, review gates).
- **throughput governs** (many independent units; 3+ files; parallelizable;
  "do it all", "until done") → **OMC lane** (ultrawork / team / autopilot / ralph).

`using-omc`'s resident reminder is the *enforced* part: every multi-step request
triggers the conscious lane decision + one-line announce. The reminder is
mandatory; the heavy OMC invocation it may point to is not.

Both skills coexist at SessionStart. superpowers stays unchanged.

## 4. Content of using-omc/SKILL.md

Frontmatter: `name: using-omc`, description triggering on OMC/routing/orchestration.

Body sections:
1. **The routing rule (enforced):** the discipline-vs-throughput decision tree
   (condensed from CLAUDE.md's hybrid auto-route), with the mandatory one-line
   announce for multi-step work. Trivial single-step work proceeds silently.
2. **When OMC wins (throughput lane):** concrete signals — 3+ independent files,
   parallelizable subtasks, "do it autonomously/until done", named OMC patterns.
3. **When OMC does NOT apply:** single-file/trivial; learning output style;
   citation-bound writing (hallucination risk in parallel mode); inside an active
   superpowers executing-plans flow.
4. **Pointer to the catalog (NOT a copy):** the full ~40-skill catalog is ALREADY
   injected by the existing `omc-reference-emit.py` loader (see §5a). `using-omc`
   must NOT duplicate it — instead it names the highest-value throughput skills
   (ultrawork / team / autopilot / ralph / ccg) inline and points to the
   auto-loaded "OMC Skill Catalog" block for the rest.
5. **Confirm-before-start gate:** irreversible / outward-facing / large-scale work
   gets a one-line Y/N confirm (mirrors CLAUDE.md step 4).
6. **Red flags:** rationalizations that mean "you skipped the routing judgment".

Keep it scannable and SHORT — the value is the resident routing rule, not bulk.
The catalog already arrives via omc-reference-emit; using-omc is the routing brain on top.

## 5. Injection Mechanism — REUSE existing repo infrastructure

**Discovery (2026-05-25):** this repo ALREADY has a SessionStart-injection
pattern for OMC, so we do NOT invent a new one. We mirror it.

### 5a. Existing pattern (reuse, don't reinvent)
- `claude/hooks/omc-reference-emit.py` — reads the cached `omc-reference/SKILL.md`
  (strips 5-line frontmatter) and prints a `hookSpecificOutput` JSON envelope so
  Claude Code injects the **OMC Skill Catalog** at SessionStart.
- `claude/hooks/omc-reference-loader.json` — the hook fragment (matcher
  `startup|resume|clear|compact`, marker `OMC_REFERENCE_AUTO_LOAD`).
- `claude/hooks/merge-project-hook.py` — idempotent marker-based merger into a
  target settings.json (preserves other hooks; detect-and-replace on re-run).
- install.sh (5b, lines 210-258) deploys the fragment into PROJECT-scope
  `.claude/settings.json` of each `projectTargets` entry (from settings.local.json;
  fallback `~/Desktop/workspace`, `~/ksm_Obsidian`).

**Why the catalog wasn't in this /workspace session:** `/workspace` is not in
`projectTargets`, so the loader never deployed here. (Confirm/raise with user
during execution — adding `/workspace` may be wanted independently.)

### 5b. What using-omc adds (the new pieces, same pattern)
- **Skill body:** `~/claude-settings/skills/using-omc/SKILL.md`. install.sh already
  symlinks each `skills/*/` subdir into `~/.claude/skills/` (line 184-189) → deploys
  + syncs automatically. This is the canonical source the emit script reads.
- **Emit script:** `claude/hooks/using-omc-emit.py` — mirror of
  `omc-reference-emit.py`: read `~/.claude/skills/using-omc/SKILL.md` (or the repo
  path), strip frontmatter, wrap in a clearly-OMC-scoped reminder block (NOT
  `<EXTREMELY_IMPORTANT>` — reserved for superpowers), print the
  `hookSpecificOutput` envelope.
- **Hook fragment:** `claude/hooks/using-omc-loader.json` — matcher
  `startup|resume|clear|compact`, marker `USING_OMC_AUTO_LOAD`, command
  `python3 ~/claude-settings/claude/hooks/using-omc-emit.py`.

### 5c. Scope decision — USER scope, not just project scope
The catalog loader is project-scoped (workspace/obsidian only). But `using-omc`'s
routing rule should be resident in EVERY session everywhere (like superpowers).
So register its hook at **user scope**: merge `using-omc-loader.json` into
`~/.claude/settings.json` (the symlinked `claude/settings.json`), which currently
has NO `hooks` key. Use the SAME `merge-project-hook.py` merger (it is target-
agnostic) against the user settings file. install.sh adds one call for this.
Absolute repo path in the command (`~/claude-settings/claude/hooks/...`) is stable
because settings.json is symlinked — no extra symlink of hooks/ needed.

## 6. Authoring approach

Use OMC `skillify` to draft (it captures repeatable-workflow → skill conventions),
then finish the output into THIS structure: claude-settings/skills/using-omc/SKILL.md
+ the SessionStart injection. skillify defaults to OMC's own learned-skill format
(`.omc/skills/`), which is NOT what we want — so the draft is a starting point, not
the final artifact. If skillify's output fights the target structure, fall back to
using `using-superpowers/SKILL.md` as the structural template and write directly.

## 7. Verification — via omc-teams worker (a real fresh session)

The core thing to verify is "does the using-omc block actually inject at
SessionStart". Doing `/clear` in THIS session would destroy active context, so
instead spawn an **omc-teams worker** (tmux pane = a genuine isolated new session)
and inspect its startup context. (See the `omc-teams-ops` skill for launch
mechanics + the 4 known pitfalls.)

- **Emit script unit check (fast, local):** `python3 claude/hooks/using-omc-emit.py`
  prints valid JSON with the SKILL.md body in `additionalContext`; `... | jq .` parses.
- **settings.json integrity:** after merge, `jq . ~/.claude/settings.json` parses;
  statusLine / omcHud / enabledPlugins all intact; the new `hooks.SessionStart`
  entry carries the `USING_OMC_AUTO_LOAD` marker.
- **Real-session injection (omc-teams worker):** launch a worker; confirm its
  SessionStart context contains the using-omc routing block alongside superpowers.
- **Behavior checks (in the worker):** give it a multi-step request → expect a
  one-line routing announce; give it a trivial request → expect silent handling
  (no over-orchestration).
- **Idempotency:** re-run install.sh (or the merge) → marker detected, no duplicate
  hook entry added.

## 8. Out of Scope

- Modifying the OMC plugin itself (cache, plugin-update-unsafe).
- Changing superpowers.
- Auto-invoking heavy OMC workflows without the existing confirm gates.

## 9. Implementation outcome (2026-05-25)

Implemented per plan `2026-05-25-using-omc-skill-plan.md`. Commits (this repo):
- `5778c4c` skills/using-omc/SKILL.md (routing brain, 56 lines)
- `9dd2477` claude/hooks/using-omc-emit.py
- `f63d69e` claude/hooks/using-omc-loader.json (marker USING_OMC_AUTO_LOAD)
- `07597d6` install.sh user-scope merge block (reuses merge-project-hook.py)
- `5ebe4c6` claude/settings.json gains hooks.SessionStart (live, via merge)

**Verification (links 1-3 PASS; link 4 = platform contract):**
- settings.json integrity: statusLine/omcHud/enabledPlugins intact + hook added; jq parses.
- Idempotency: re-merge keeps exactly one USING_OMC_AUTO_LOAD entry.
- End-to-end command sim: running the EXACT registered SessionStart command verbatim
  emits valid injection JSON containing `omc-routing-reminder` + the routing rule.
- merge-project-hook.py confirmed to `setdefault("hooks", {})` — handles the prior
  no-`hooks`-key user settings.json cleanly (the plan's main open risk; resolved).

**Verification LIMITATION (honest):** the planned omc-teams-worker test could NOT run
in this container — it runs as **root**, and omc-teams launches workers with
`claude --dangerously-skip-permissions`, which Claude Code refuses under root. The
worker pane fell back to bash; team was torn down cleanly. This is an environment
incompatibility, not a hook defect (the main session runs claude fine; the hook uses
the same mechanism as the already-working omc-reference loader). True link-4 proof
arrives at the next genuine SessionStart (startup/clear) — the using-omc block was NOT
in THIS session because the hook was registered mid-session.

**Known gap — /workspace catalog:** the project-scoped `omc-reference` catalog loader
deploys only to `projectTargets` (workspace/obsidian via settings.local.json). If
`/workspace` is absent there, the full OMC catalog does not auto-load here — only the
user-scoped using-omc *routing rule* does. Adding `/workspace` to `projectTargets` is
a separate, optional decision (raised with user).

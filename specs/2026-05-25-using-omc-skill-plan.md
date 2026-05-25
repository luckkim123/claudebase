# using-omc Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make OMC as actively used as superpowers by injecting a resident routing
rule (`using-omc`) at every SessionStart, reusing this repo's existing OMC-injection
infrastructure.

**Architecture:** A new `skills/using-omc/SKILL.md` (the routing brain) + an emit
script + a hook fragment, mirroring the existing `omc-reference-emit.py` /
`omc-reference-loader.json` / `merge-project-hook.py` pattern. Registered at USER
scope (`~/.claude/settings.json`) so it's resident everywhere, unlike the
project-scoped catalog loader. The catalog itself is NOT duplicated — it already
arrives via `omc-reference-emit.py`.

**Tech Stack:** bash (install.sh), python3 (emit + merge scripts), JSON (settings +
hook fragments), Claude Code SessionStart hooks, OMC skillify + omc-teams (authoring/verify).

**Spec:** `specs/2026-05-25-using-omc-skill-design.md`

**Repo:** `/root/claude-settings` (settings repo — surgical, line-by-line reviewed).

---

## Task 1: Draft the routing skill body via skillify, finish into SKILL.md

**Files:**
- Create: `/root/claude-settings/skills/using-omc/SKILL.md`

- [ ] **Step 1: Draft with OMC skillify**

Run the OMC `skillify` skill against this session's "OMC routing" workflow to get a
draft. skillify outputs OMC's learned-skill format (`.omc/skills/...`) — treat the
draft as raw material only; do NOT leave it in `.omc/skills/`.

- [ ] **Step 2: Write the final SKILL.md** (finish the draft into the target structure)

Create `/root/claude-settings/skills/using-omc/SKILL.md`. Keep it SHORT and scannable
(the value is the resident routing rule, not bulk — the catalog already arrives via
omc-reference-emit). Required content:

```markdown
---
name: using-omc
description: Use at the start of every multi-step request to decide the execution lane (handle directly / superpowers / OMC) and announce the verdict. Establishes when to reach for OMC orchestration (ultrawork, team, autopilot, ralph) vs lighter paths. Triggers on orchestration, parallel work, "do it autonomously", multi-file refactors, and any 3+-step request.
---

# Using OMC — Routing Brain

OMC ships ~40 skills + 19 agents (full catalog auto-loaded separately as "OMC Skill
Catalog"). This skill is the *routing rule* that decides WHEN to reach for them.

## The Rule (enforced)

For ANY request spanning 3+ actions or multiple files, BEFORE starting:
1. Run the discipline-vs-throughput judgment (below).
2. **Announce the verdict in one line** — even when it's "handle directly".
   Format: "→ <lane>로 갑니다: <one-clause reason>". This makes the routing auditable.

Trivial single-step work (typo, one-liner, single obvious edit, pure question)
proceeds silently — no announce, no orchestration.

## Discipline vs Throughput

- **Direction/scope unclear** → diverge first: `brainstorming` (decision-heavy) or
  `oh-my-claudecode:deep-interview` (Socratic). Re-enter with a clear spec.
- **Discipline governs** (wrong = expensive; review/TDD gates govern quality;
  non-trivial code; citation-bound writing) → **superpowers lane**
  (writing-plans → subagent-driven-development / TDD). Citation work stays here or
  manual — never OMC parallel mode (hallucination risk).
- **Throughput governs** (many *independent* units; 3+ files; parallelizable;
  "do it all / until done / don't ask each step") → **OMC lane**:
  - `ultrawork` — bounded parallel edits (e.g. rename X across 20 files)
  - `team` — needs inter-worker comms or review roles
  - `autopilot` — hands-off idea→working code
  - `ralph` — loop until tests/verification pass
  - `ccg` — Claude+Codex+Gemini tri-model synthesis
  (Full catalog: see the auto-loaded "OMC Skill Catalog" block.)

## Confirm-before-start gate

Even with a lane chosen, pause for ONE Y/N confirm if the work is irreversible
(delete/overwrite), outward-facing (push, PR, email), or large-scale (5+ files,
long autonomous run). Format: "20파일 rename이라 ultrawork로 갑니다. ok?"

## When OMC does NOT apply

- Trivial / single-file / pure question.
- Learning output style active (autopilot defeats the teaching goal).
- Citation-bound writing (paper/concept notes) — OMC parallel mode raises
  hallucination risk; stay manual or superpowers.
- Inside an active superpowers executing-plans flow — finish it, don't switch runners.

## Red flags (you skipped the routing judgment)

- "It's just ops, no need to announce" → multi-file ops STILL announce the verdict.
- "I'll just start" on a 3+-step task → run the judgment + announce first.
- Reaching for a heavy OMC workflow on a trivial task → handle directly instead.
```

- [ ] **Step 3: Verify frontmatter + length**

Run: `head -3 /root/claude-settings/skills/using-omc/SKILL.md` (frontmatter present)
and `wc -l /root/claude-settings/skills/using-omc/SKILL.md`.
Expected: frontmatter present; body under ~70 lines (scannable, not bulky).

- [ ] **Step 4: Commit**

```bash
cd /root/claude-settings
git add skills/using-omc/SKILL.md
git commit -m "feat(skills): add using-omc routing-brain skill"
```

## Task 2: Emit script (mirror omc-reference-emit.py)

**Files:**
- Create: `/root/claude-settings/claude/hooks/using-omc-emit.py`

- [ ] **Step 1: Write the emit script**

Mirror `omc-reference-emit.py` exactly in structure. Create
`/root/claude-settings/claude/hooks/using-omc-emit.py`:

```python
#!/usr/bin/env python3
"""Emit the using-omc routing skill as a Claude Code SessionStart hook envelope.

Reads skills/using-omc/SKILL.md (strips the 3-line frontmatter), wraps it in an
OMC-scoped reminder, and prints a hookSpecificOutput JSON envelope so Claude Code
injects the routing rule into every session's SessionStart context.
"""

import json
import os
import sys


def main() -> int:
    # Prefer the deployed symlink; fall back to the repo path.
    candidates = [
        os.path.expanduser("~/.claude/skills/using-omc/SKILL.md"),
        os.path.expanduser("~/claude-settings/skills/using-omc/SKILL.md"),
    ]
    body = ""
    for path in candidates:
        if os.path.exists(path):
            with open(path) as f:
                lines = f.readlines()
            # Strip YAML frontmatter (--- ... --- at top).
            if lines and lines[0].strip() == "---":
                end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), 0)
                lines = lines[end + 1:]
            body = "".join(lines).strip()
            break

    if body:
        ctx = (
            "<omc-routing-reminder>\n"
            "Before any multi-step request, run the OMC routing judgment below and "
            "announce the lane verdict in one line. (Complement to superpowers; the "
            "full OMC catalog auto-loads separately.)\n\n"
            + body
            + "\n</omc-routing-reminder>"
        )
    else:
        ctx = "using-omc skill not found — check claude-settings/skills/using-omc/SKILL.md"

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": ctx,
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Verify it emits valid JSON with the body**

Run:
```bash
python3 /root/claude-settings/claude/hooks/using-omc-emit.py | jq -r '.hookSpecificOutput.additionalContext' | head -5
```
Expected: prints the `<omc-routing-reminder>` wrapper + start of the routing rule.
`python3 .../using-omc-emit.py | jq .` must parse without error.

- [ ] **Step 3: Commit**

```bash
cd /root/claude-settings
git add claude/hooks/using-omc-emit.py
git commit -m "feat(hooks): add using-omc SessionStart emit script"
```

## Task 3: Hook fragment (mirror omc-reference-loader.json)

**Files:**
- Create: `/root/claude-settings/claude/hooks/using-omc-loader.json`

- [ ] **Step 1: Write the fragment**

Create `/root/claude-settings/claude/hooks/using-omc-loader.json`:

```json
{
  "_comment": "using-omc routing-rule auto-loader. Merged into USER-scope ~/.claude/settings.json by install.sh (unlike the project-scoped omc-reference loader). Marker 'USING_OMC_AUTO_LOAD' lets install.sh detect existing installs for idempotent updates.",
  "SessionStart": [
    {
      "matcher": "startup|resume|clear|compact",
      "hooks": [
        {
          "type": "command",
          "command": "# USING_OMC_AUTO_LOAD\npython3 ~/claude-settings/claude/hooks/using-omc-emit.py"
        }
      ]
    }
  ]
}
```

- [ ] **Step 2: Verify JSON parses**

Run: `jq . /root/claude-settings/claude/hooks/using-omc-loader.json`
Expected: pretty-prints without error; marker `USING_OMC_AUTO_LOAD` present in command.

- [ ] **Step 3: Commit**

```bash
cd /root/claude-settings
git add claude/hooks/using-omc-loader.json
git commit -m "feat(hooks): add using-omc loader fragment (user-scope, USING_OMC_AUTO_LOAD)"
```

## Task 4: Wire install.sh to merge the fragment at user scope

**Files:**
- Modify: `/root/claude-settings/install.sh` (after the existing project-scope hook block, ~line 258)

- [ ] **Step 1: Read the existing project-hook block for the exact merger call shape**

Run: `sed -n '210,260p' /root/claude-settings/install.sh`
Confirm the merger invocation is `python3 "$HOOK_MERGER" <fragment> <target> <marker>`
with rc handling (0 ok, 2 skip, * warn).

- [ ] **Step 2: Add a user-scope merge block**

After the project-scope hook loop (the `else debug "skip project hook deployment..."`
block ends near line 258), insert a new block that merges the using-omc fragment into
the USER settings file. Insert:

```bash
# 5c. user-scope using-omc routing loader — merge into ~/.claude/settings.json so
#     the OMC routing rule is resident in every session (not just project targets).
#     Idempotent via marker USING_OMC_AUTO_LOAD.
USING_OMC_FRAGMENT="$REPO_DIR/claude/hooks/using-omc-loader.json"
USING_OMC_MARKER="USING_OMC_AUTO_LOAD"
if [[ -f "$USING_OMC_FRAGMENT" && -f "$HOOK_MERGER" ]]; then
  if [[ $DRY_RUN -eq 1 ]]; then
    log "would merge using-omc loader into: $CLAUDE_HOME/settings.json"
  else
    output=$(python3 "$HOOK_MERGER" "$USING_OMC_FRAGMENT" "$CLAUDE_HOME/settings.json" "$USING_OMC_MARKER" 2>&1)
    rc=$?
    case $rc in
      0) log "using-omc hook: $output" ;;
      2) debug "skip using-omc hook: $CLAUDE_HOME/settings.json parent missing" ;;
      *) log "WARNING: using-omc hook merge failed (rc=$rc): $output" ;;
    esac
  fi
else
  debug "skip using-omc hook: fragment or merger missing"
fi
```

> NOTE: `merge-project-hook.py` is target-agnostic (it merges any fragment into any
> settings.json by marker), so no merger change is needed. Confirm by reading its
> `main()` — it takes (fragment, target, marker) and preserves existing keys.

- [ ] **Step 3: Verify merge-project-hook.py handles a target that has NO hooks key**

The user settings.json currently has no `hooks` key. Confirm the merger creates it
rather than erroring. Read the relevant lines:
```bash
grep -nE "hooks|setdefault|get\(" /root/claude-settings/claude/hooks/merge-project-hook.py
```
Expected: it initializes `hooks` (e.g. `data.setdefault("hooks", ...)`). If it does
NOT handle a missing `hooks` key, fix the merger minimally to `setdefault` it (and
note the fix in the commit). Do this BEFORE running the merge for real.

- [ ] **Step 4: Dry-run install.sh and confirm the new block fires**

Run: `cd /root/claude-settings && bash install.sh --dry-run 2>&1 | grep -i "using-omc"`
Expected: `would merge using-omc loader into: .../.claude/settings.json`.

- [ ] **Step 5: Commit**

```bash
cd /root/claude-settings
git add install.sh
git commit -m "feat(install): merge using-omc loader into user settings.json"
```

## Task 5: Deploy + verify settings.json integrity

**Files:**
- Modify (generated): `~/.claude/settings.json` (via merge — NOT committed, it's the symlink target's live state)

- [ ] **Step 1: Back up current user settings.json**

```bash
cp ~/.claude/settings.json /tmp/settings.json.bak
```

- [ ] **Step 2: Run the real merge (single fragment, not full install)**

```bash
python3 /root/claude-settings/claude/hooks/merge-project-hook.py \
  /root/claude-settings/claude/hooks/using-omc-loader.json \
  ~/.claude/settings.json USING_OMC_AUTO_LOAD
```
Expected: rc 0, message indicating merged/added.

- [ ] **Step 3: Verify integrity — all prior keys intact + new hook present**

```bash
jq -e '.statusLine and .omcHud and .enabledPlugins and (.hooks.SessionStart | length >= 1)' ~/.claude/settings.json && echo "INTACT + hook added"
jq -r '.hooks.SessionStart[].hooks[].command' ~/.claude/settings.json | grep USING_OMC_AUTO_LOAD && echo "marker present"
```
Expected: `INTACT + hook added` and `marker present`. If `settings.json` is a symlink
to the repo, this edits the repo's `claude/settings.json` — confirm whether that's
desired (the repo settings.json gaining a `hooks` key is fine and SHOULD be committed
as the canonical state; if the merge wrote to the symlink target, commit it in Task 6).

- [ ] **Step 4: Idempotency check — merge again, no duplicate**

```bash
python3 /root/claude-settings/claude/hooks/merge-project-hook.py \
  /root/claude-settings/claude/hooks/using-omc-loader.json \
  ~/.claude/settings.json USING_OMC_AUTO_LOAD
jq '[.hooks.SessionStart[].hooks[].command | select(test("USING_OMC_AUTO_LOAD"))] | length' ~/.claude/settings.json
```
Expected: `1` (exactly one using-omc hook, not duplicated).

- [ ] **Step 5: Commit the canonical settings.json hooks addition (if symlinked to repo)**

If `~/.claude/settings.json` is a symlink to `/root/claude-settings/claude/settings.json`,
the merge already updated the repo file. Commit it:
```bash
cd /root/claude-settings
git add claude/settings.json
git commit -m "chore(settings): register using-omc SessionStart hook"
```
If it is NOT symlinked (copied), instead re-run the merge against the repo file directly
so the canonical source carries the hook, then commit.

## Task 6: Verify real-session injection via an omc-teams worker

**Files:** none — runtime verification.

- [ ] **Step 1: Review omc-teams launch mechanics**

Invoke the `omc-teams-ops` skill and read its launch command + the 4 pitfalls
(leader-session-1-team, paste-bracketed Enter, sentinel self-leak, Cogitated counter).
A tmux-pane worker is a genuine fresh session, so its SessionStart fires our hook.

- [ ] **Step 2: Launch a single-worker omc-team and capture its startup context**

Following omc-teams-ops, launch one worker. The worker's session start runs the
SessionStart hooks (including USING_OMC_AUTO_LOAD). Ask the worker to report whether
its initial context contains an `<omc-routing-reminder>` block.
Expected: worker confirms the using-omc routing block is present at startup.

- [ ] **Step 3: Behavior check — multi-step announce**

Give the worker a multi-step task (e.g. "rename a symbol across 3 files"). 
Expected: the worker announces a one-line routing verdict before starting.

- [ ] **Step 4: Behavior check — trivial silence**

Give the worker a trivial task (e.g. "what does line 5 of X say"). 
Expected: NO routing announce (silent handling) — confirms no over-orchestration.

- [ ] **Step 5: Tear down the worker**

Stop the omc-team per omc-teams-ops teardown. Record the verification outcome.

## Task 7: Final — changelog + optional /workspace catalog note

**Files:**
- Modify: `/root/claude-settings/changelog.md` (if present) or note in commit

- [ ] **Step 1: Record the session decision**

Add a changelog/note entry: using-omc routing-brain skill added, injected at user
scope via the existing OMC hook-merge infrastructure, complements superpowers
(discipline vs throughput), verified via omc-teams worker.

- [ ] **Step 2: Surface the /workspace catalog gap (from spec §5a)**

Note for the user: `/workspace` is not in `projectTargets`, so the project-scoped
`omc-reference` catalog loader does not deploy here. The user-scoped using-omc hook
fixes the *routing rule* everywhere, but the *full catalog* still only loads in
projectTargets. Ask whether to add `/workspace` to `projectTargets` in
`~/.claude/settings.local.json` (separate, optional).

- [ ] **Step 3: Commit**

```bash
cd /root/claude-settings
git add changelog.md
git commit -m "docs: changelog for using-omc skill addition"
```

---

## Self-Review Notes (author check)

- **Spec coverage:** §2 enforce-judgment-not-invocation → Task 1 SKILL.md "The Rule".
  §3 complement+reminder → Task 2 wrapper text + Task 1 lanes. §4 pointer-not-copy →
  Task 1 references auto-loaded catalog, no duplication. §5a reuse → Tasks 2/3 mirror
  existing scripts. §5b new pieces → Tasks 2/3. §5c user scope → Task 4 merges into
  ~/.claude/settings.json. §6 skillify-then-finish → Task 1 Steps 1-2. §7 omc-teams
  verify → Task 6.
- **Open risk surfaced, not hidden:** Task 4 Step 3 explicitly checks whether
  merge-project-hook.py handles a target with no `hooks` key (the user settings.json
  case) — fix-if-needed before real merge, rather than assuming.
- **Reversible-first ordering:** Tasks 1-4 are pure additions + a dry-run; the first
  real mutation of ~/.claude/settings.json is Task 5 with a backup (Step 1) and
  idempotency check (Step 4). Runtime verification (Task 6) is last.
- **No placeholders:** every script/fragment/install-block is given in full.
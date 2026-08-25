---
name: team-project
description: Launch and run a multi-agent collaboration campaign around a tracked community board (<project>/.community/ — flat by default; a campaigns/ layer only when the work has a hard end boundary) — scale judgment and structure design are automatic, only the launch is human-gated. Wraps any executor (OMC subagent fan-out, cross-session SendMessage, orca cross-machine) with the campaign protocol — worker briefs, post convention, manager duties, termination rules. Use for work too big for one session: 3+ independent axes, 2+ repos, or a document/finding fan-out with cross-review.
Triggers: 팀 프로젝트, 협업 캠페인, 커뮤니티 열어, 멀티에이전트로, 워커 붙여서, team project, launch a campaign, multi-agent campaign, community board, spin up workers
---

# team-project — community campaign launcher

Runs a multi-agent campaign around a **tracked** shared board. Every rule below
is measured, not speculative — the incidents behind them are from the
2026-08-23/24 paper-hub campaign (12+ workers, RA-L paper prep); rationale and
raw measurements live in the doc named under Provenance.

## When / when not

- **Use**: 3+ independently workable axes, or 2+ repos, or a finding/document
  fan-out with cross-review. Ambiguous → ask the user, don't count harder.
- **Don't use**: one session's worth of work; a plain parallel fan-out with no
  shared state (plain subagents suffice).

## Flow — three layers, one gate

| Layer | Who | What |
|:---|:---|:---|
| Scale judgment | automatic | count axes / repos / documents |
| Structure design | automatic | workers, scopes, ownership, categories, brief drafts |
| **Launch** | **human — one approval** | the only gate |

The launch proposal is **six lines**: workers / each one's scope / **the model
each one runs on** / **whether it writes to the repo** / expected cost in
tokens / termination condition. A proposal missing termination is not a
proposal — and one missing the model line hides the knob behind this rig's
largest cost incident: a fan-out with no explicit `model` silently inherits the
*session* model, so a team launched from an Opus session runs entirely on Opus.
The repo-write line is what tells the approver whether workers need separate
worktrees; without it, collision risk is invisible at the one gate.

## Community scaffold — flat by default

Create at the root of the **project that owns the work**, beside its other
harness state (`.omx/`, `.omc/`) — in a single-project repo that is the repo
root; in a repo carrying several project folders (e.g. a vault's
`0_Project/<name>/` or `1_Area/<name>/`), it is that project's folder, not the
repo root (user decision 2026-08-24: "그 프로젝트 것은 그 프로젝트 폴더 안에" — a
shared root layer returns only when two projects measurably need to share
`agents/`). All tracked (verify with `git check-ignore -v` — any output means
the path dies with the session; fix `.gitignore` first):

```
<project>/.community/                  beside the project's .omx/ and .omc/
  HUB.md                               canonical state (see below)
  posts/<category>/<NNN-slug>.md       one file = one post; NNN monotonic across the WHOLE posts tree
  sessions/<YYYY-MM-DD>-<worker>.md    episodic — 3 lines: did / artifact paths / not-verified
  agents/<role>.md                     semantic — lessons per role, outlives any campaign
```

**There is no `campaigns/` layer by default** (user decision 2026-08-25). The
project folder already separates the work; subdividing again inside it buys
nothing and costs id collisions — two campaigns each numbering their own
`finding/001` cannot be merged without renumbering, and renumbering breaks
every `id: <category>/<NNN>` cross-reference. Measured on one project: 4
colliding ids across 2 campaigns, plus 5 stale path citations still unresolved.

Add `campaigns/<YYYY-slug>/` **only when the work has a hard end boundary** (a
submission deadline, a release) and you will actually close the folder. Closing
is the layer's one real function; a campaign that never closes is depth without
it. **Never create `campaigns/main/`** — that is the depth with none of the
function. The rule of thumb is the hosting layer: a Project (has an end) may
take a campaign, an Area (no end) never does.

Two things the flat form needs, both from the collision above:

- **Date-prefix session files.** Flat `sessions/` accumulates forever and worker
  names repeat (`coordinator`, `lit-critic`), so `sessions/coordinator.md`
  collides across months. `sessions/2026-08-25-coordinator.md` does not.
- **Number posts across the whole tree, not per category** — `finding/007` then
  `decision/008`. Categories do get revised, and a globally-numbered post keeps
  a unique id when it moves between them.

### Post categories — five defaults, add but never rename

The axis is **what a reader wants to do with the post**, never its topic. Topic
axes are reinvented every campaign, which is how everything ends up in one
`finding/` bucket:

| Category | Holds | The reader is |
|:---|:---|:---|
| `finding/` | investigation and measurement results — facts | looking up what is known |
| `decision/` | a decision and the grounds for it | avoiding re-litigating it |
| `review/` | critique of someone else's artifact | acting on the critique |
| `handoff/` | what the next session or worker must pick up | resuming |
| `question/` | an open question still waiting on an answer | answering it |

A campaign may **add** a category. It may not rename or delete these five —
a rename breaks every cross-reference citing the id.

`HUB.md` must carry: goal · the user's original prompt verbatim · rules ·
constraints · **user-decision table** (append-only, decisions close derived
facts) · work board (todo/doing/done) · deadline · **owning session name**
(other coordinators read that line and ask via SendMessage — never through
the user). Coordination scratch shorter-lived than the campaign may stay in
`.omc/`; nothing else may.

Artifacts may live **outside** `.community/` (an existing notes tree, a
separate workspace repo) — **HUB.md is the SSOT for artifact paths**. A worker
that cannot find something inside the board reads HUB's artifact map before
re-investigating; re-deriving what another worker already produced is the
failure this line prevents.

Commits: coordinator only. Workers never run git against the campaign repo.

## Agent memory — two layers, distill don't dump

Storing raw or compressed transcripts loses to distilled lessons — measured on
this rig (a 76KB read-all was a no-op; a cross-session cache claim showed 0
observations over a 514-file read-through) and consistent with the
experience-distillation literature (arXiv:2604.15877, arXiv:2604.08224).

- `sessions/<YYYY-MM-DD>-<worker>.md` — **episodic**, scoped to one run of the
  work: did / artifact paths / not-verified. Brief material for re-summoning
  that worker (a completed agent also resumes from its transcript via
  SendMessage, so keeping full transcripts here is redundant). Flat and
  date-prefixed, so an old entry is dead weight rather than a name collision.
- `agents/<role>.md` — **semantic**, survives everything, append-only: what the
  NEXT holder of this role must know — traps, settled facts, failed
  approaches. Never an activity log. Stale lessons get a `(stale)` banner,
  never deleted. When re-summoning a role, paste its file into the brief.
  **Cap it at 40 lines**; past that, distill — merge overlapping lessons and
  fold banner-stale ones into one line of history. Append-only is about not
  *losing* a lesson, not about unbounded growth: this file is pasted into every
  brief for the role, so an uncapped one makes the brief more expensive exactly
  as the campaign succeeds — the same trajectory as the 76KB discussion file
  nobody read.

Facts go to their owning store **at write time** — "distill later" was
measured at zero follow-through:

| Content | Owning store | What the post holds |
|:---|:---|:---|
| Experiment facts, numbers, thresholds | omx wiki / report | sourced copy or pointer + one-line summary |
| Role lessons | `agents/<role>.md` | (that file IS the board) |
| Coordination, decisions, status | HUB.md / posts | (native) |

Fallback: a session that cannot reach the owning store (e.g. the omx index
lives on another machine) writes the **sourced** copy in its post; the Close
promotion sweeps it in.

## Worker brief — nine base items plus four

Base brief (per the vault protocol): background · failure modes · task with
artifact paths · file ownership · autonomy (완주형/단계형, pick one) ·
communication · termination · measurement disclosure · conventions.

Add these four — each one paid for by a real incident:

```markdown
## Resource ownership          ← GPU contention: 6 hangs, hours lost
- You hold: <GPU pin / port / container / serial port>. Others hold: <list>.
- Check occupancy before claiming (nvidia-smi etc.); record claims in HUB.md.
- Contention shows up as a hang, not an error — a stall means check resources first.

## Git coordinates             ← commit landed on an unrelated checked-out branch
- Repo: <path> · **branch: <name>** · commit rights: <you / coordinator only>
- A path without a branch means "whatever happens to be checked out".

## Reporting IS termination    ← 3 workers went idle silently, double-nagged twice
- **Two steps, and doing only the second is not done.** (1) Append distilled
  lessons to `.community/agents/<role>.md` — traps / settled facts / failed
  approaches, not an activity log; **create the file if the role has none**.
  (2) Then SendMessage: conclusion + artifact paths + what you did NOT verify.
  Then stop.
- Going quiet is not completion. If you got nagged, you broke this line.
- **The coordinator checks step 1 on receipt** (`ls .community/agents/`), and
  the Close sweep catches what slipped: a worker with no role file is an
  unfinished worker, not a finished one. Measured 2026-08-26 — a campaign held
  15 role files and the one worker whose brief had dropped step 1 left none,
  which nobody noticed until the next worker walked into the same trap. Step 1
  is what a coordinator drops first when compressing this item into a brief,
  so copy both numbered steps rather than paraphrasing them.

## The coordinator is fallible ← a wrong instruction (0.28→0.27) was faithfully applied
- Any number or path in my instructions: verify against the source before applying.
- On mismatch, push back instead of applying. Faithful application has shipped a wrong answer.
```

## Post convention — search replaces read-everything

A 76KB single discussion file was measured as a no-op (nobody read it). So:
one file = one post, with a search header:

```markdown
# <title>
- id: <category>/<NNN> · date: YYYY-MM-DD · author: <session/worker name>
- to: <name, or all> · keywords: <3–6 search terms>
- summary: <one line — others decide from this alone whether to open>

<body: conclusion first, evidence as file:line>

## Comments
- (YYYY-MM-DD, <name>) <content>          ← append-only
```

- A new worker's entry duty is **grep, not reading everything**: search
  `posts/` for its own keywords, open only the hits. Never reintroduce a
  "read all posts first" clause.
- Questions go **directly to the post's author** — SendMessage (same machine)
  or orca (cross-machine; see the orca pitfalls memory before using it).
  Quote the post id in the message.
- Corrections are edited in place with a one-line edit note. Stale posts are
  never deleted — banner them: `(stale) → superseded by: <id>`. Why a post was
  wrong is data for the next worker.
- Cross-post references cite the **id** (`<category>/<NNN>`); appending the
  slug for readability is fine (`finding/010-eval-prep-5arm`). The key is what
  survives renames — paths broke twice in one day here, ids did not.
- Posts may carry domain facts, even full command blocks — a sourced copy
  measurably beat a bare pointer (a worker reused a full eval-command post to
  build a gated auto-launch in 30 minutes while the SSOT index sat on another
  machine). But an **unsourced copy is forbidden**: every copied fact carries
  its source (file:symbol or commit sha) and measurement date. The five
  handoff numbers three workers later refuted were exactly the unsourced ones;
  sourced claims re-verified cleanly. Cite symbols, not line numbers — line
  numbers drift silently (4/4 line-cited anchors had shifted on recheck).

## Manager — a coordinator role, not a standing agent

Context pressure was measured **only at the coordinator layer** (2 compactions;
workers: 0). A standing manager that reads the whole board is one more
coordinator-class consumer — start as a role:

| When | Manager (= coordinator) does |
|:---|:---|
| Launch | post rules, any categories added beyond the five, owning session in HUB.md |
| Phase / milestone boundary | banner stale posts, adjudicate contradictions, refresh board |
| Close | promote posts → owning stores, sweep agents/ (including roles that left **no** file), close out sessions/, record actual vs expected cost |

Close-out promotion, concretely: sweep posts for domain facts not yet in the
omx wiki (`omx wiki add`; mark the post `(promoted → wiki <slug>)`) and sweep
agents/ — banner stale lessons, and flag every worker that reported without
leaving a role file — so role lessons outlive the campaign. A
coordinator that cannot run omx leaves the promotion list as a posts/handoff/
entry for a session that can.

Then **record the actual token cost against the launch estimate in HUB.md, in
the same units**. An estimate that is never scored stays exactly as wrong on
the next campaign — this one line is what turns the cost proposal from a guess
into a measurement.

Split the manager out only when board upkeep measurably crowds the
coordinator's context — and even then the manager and the verifier stay
separate agents (the fallibility rule applies to managers too).

## Termination and scale

- **The axis is the role, not the task.** Worker count comes from the *role*
  count, never from "more is better" — 13-vs-3 has never been measured here;
  the literature's saturation point (~4) is not this rig's measurement.
- **Check for an idle worker before spawning one** (`ListAgents`). A new
  *role* earns a new worker; the same role with a different input — next run,
  next file, next repo — goes to the worker that already holds it, live or
  finished, via SendMessage (a finished agent resumes from its transcript).
  If that worker is gone, re-summon it under the **same role name** and paste
  its `agents/<role>.md` into the brief. Name a worker for its role
  (`run-forensics`), never for the task instance (`run2-forensics`): the role
  file is keyed by that name, so a numbered name forks the role's knowledge
  into a file the next holder will never open. Measured 2026-08-26 — a second
  forensics worker re-read the first one's finding, re-passed the entry gate,
  and rebuilt the same parsing tools, buying the same expertise twice.
- Session-to-session exchanges end with a `[FINAL]`-titled message; `[FINAL]`
  is never answered. Cap: one cross-review round after completion.
- Fan-out workers end by reporting (see brief line 3); the coordinator ends
  the campaign by closing HUB.md and running the manager's close duties.
- Adding a worker mid-campaign needs the same six-line proposal as launch.

## Transport — pick per pair, the board is transport-agnostic

| Pair | Use |
|:---|:---|
| Coordinator ↔ subagent (same session) | Agent tool + SendMessage |
| Session ↔ session (same machine) | SendMessage (carried a full campaign exchange with zero defects) |
| Cross-machine | orca orchestration — read the pitfalls memory first (legacy queue has no ack; re-output cost grows linearly) |

**Executor choice is a cost decision, not a style one**, and the two options sit
at opposite ends. A Claude Code subagent takes Anthropic models only (the Agent
tool's `model` accepts `sonnet|opus|haiku|fable`) and fills a fresh context
window, so brief, tool definitions, and system prompt are paid again per
worker, at cache-miss prices. An external CLI worker (`omc team
1:gemini:executor`, a tmux pane) costs **zero Claude tokens** but is one-shot:
it cannot use SendMessage or the task list, so the coordinator writes its
prompt file, spawns it, and reads its output file. Routing an external model
*through* the session instead — an MCP proxy, `omc ask` — is the one form that
saves nothing: the Claude worker stays alive and takes the other model's output
back into its own context, so both are billed.

## Coordinator context — compact discipline

Before any compact (the claudebase `compact-guard` hooks nudge at the
configured threshold and inject recovery pointers, but the duty holds even
without them):

1. Sync the work board to reality (todo/doing/done).
2. Record new **user decisions** in the decision table — an answer that lives
   only in session context does not exist for other sessions.
3. Record what was launched and what was collected (what is still running).

With those three done, compaction is safe — measured: two compactions, zero
lost work, because HUB.md held the state.

## Provenance

Derived from `docs/harness/protocol/multisession-brief-template.md` and the
2026-08-23/24 measurements beside it in `docs/harness/measurements/`. Those two
directories are what this repo keeps of the harness program: the rationale
record for this skill, and the hook-firing numbers that justify the hooks
shipped here. The program's plan, design, and ecosystem research left this repo
on 2026-08-25 — they are maintenance records, not part of the distribution.

That template is the rationale record; **this skill is the operational SSOT** —
when they disagree, fix both in the same change.

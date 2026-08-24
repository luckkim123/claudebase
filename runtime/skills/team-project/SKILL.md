---
name: team-project
description: Launch and run a multi-agent collaboration campaign around a tracked community board (.community/<campaign>/) — scale judgment and structure design are automatic, only the launch is human-gated. Wraps any executor (OMC subagent fan-out, cross-session SendMessage, orca cross-machine) with the campaign protocol — worker briefs, post convention, manager duties, termination rules. Use for work too big for one session: 3+ independent axes, 2+ repos, or a document/finding fan-out with cross-review.
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

The launch proposal is **four lines**: workers / each one's scope / expected
cost / termination condition. A proposal missing termination is not a proposal.

## Community scaffold

Create at the project root, all tracked (verify with `git check-ignore -v` —
any output means the path dies with the session; fix `.gitignore` first):

```
.community/
  campaigns/<YYYY-slug>/             one campaign = one folder
    HUB.md                           canonical state (see below)
    posts/<category>/<NNN-slug>.md   one file = one post; categories are campaign-defined
    sessions/<worker-name>.md        episodic — 3 lines per worker: did / artifact paths / not-verified
  agents/<role>.md                   semantic — cross-campaign lessons per role (see Agent memory)
```

`HUB.md` must carry: goal · the user's original prompt verbatim · rules ·
constraints · **user-decision table** (append-only, decisions close derived
facts) · work board (todo/doing/done) · deadline · **owning session name**
(other coordinators read that line and ask via SendMessage — never through
the user). Coordination scratch shorter-lived than the campaign may stay in
`.omc/`; nothing else may.

Artifacts may live **outside** the campaign folder (an existing notes tree, a
separate workspace repo) — **HUB.md is the SSOT for artifact paths**. A worker
that cannot find something inside the campaign folder reads HUB's artifact map
before re-investigating; re-deriving what another worker already produced is
the failure this line prevents.

Commits: coordinator only. Workers never run git against the campaign repo.

## Agent memory — two layers, distill don't dump

Storing raw or compressed transcripts loses to distilled lessons — measured on
this rig (a 76KB read-all was a no-op; a cross-session cache claim showed 0
observations over a 514-file read-through) and consistent with the
experience-distillation literature (arXiv:2604.15877, arXiv:2604.08224).

- `campaigns/<c>/sessions/<worker>.md` — **episodic**, dies with the campaign:
  did / artifact paths / not-verified. Brief material for re-summoning within
  the campaign (a completed agent also resumes from its transcript via
  SendMessage, so keeping full transcripts here is redundant).
- `agents/<role>.md` — **semantic**, survives campaigns, append-only: what the
  NEXT holder of this role must know — traps, settled facts, failed
  approaches. Never an activity log. Stale lessons get a `(stale)` banner,
  never deleted. When re-summoning a role, paste its file into the brief.

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
- When done: first append distilled lessons to .community/agents/<role>.md
  (traps / settled facts / failed approaches — not an activity log), then
  SendMessage: conclusion + artifact paths + what you did NOT verify. Then stop.
- Going quiet is not completion. If you got nagged, you broke this line.

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

## Manager — a coordinator role, not a standing agent

Context pressure was measured **only at the coordinator layer** (2 compactions;
workers: 0). A standing manager that reads the whole board is one more
coordinator-class consumer — start as a role:

| When | Manager (= coordinator) does |
|:---|:---|
| Launch | post rules, categories, owning session in HUB.md |
| Phase / milestone boundary | banner stale posts, adjudicate contradictions, refresh board |
| Close | review promotion (posts → permanent stores), close out sessions/, banner stale agents/ lessons |

Split the manager out only when board upkeep measurably crowds the
coordinator's context — and even then the manager and the verifier stay
separate agents (the fallibility rule applies to managers too).

## Termination and scale

- Worker count comes from the axis count, never from "more is better" —
  13-vs-3 has never been measured here; the literature's saturation point
  (~4) is not this rig's measurement.
- Session-to-session exchanges end with a `[FINAL]`-titled message; `[FINAL]`
  is never answered. Cap: one cross-review round after completion.
- Fan-out workers end by reporting (see brief line 3); the coordinator ends
  the campaign by closing HUB.md and running the manager's close duties.
- Adding a worker mid-campaign needs the same four-line proposal as launch.

## Transport — pick per pair, the board is transport-agnostic

| Pair | Use |
|:---|:---|
| Coordinator ↔ subagent (same session) | Agent tool + SendMessage |
| Session ↔ session (same machine) | SendMessage (carried a full campaign exchange with zero defects) |
| Cross-machine | orca orchestration — read the pitfalls memory first (legacy queue has no ack; re-output cost grows linearly) |

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

Derived from the harness project records in this repo —
`docs/harness/protocol/multisession-brief-template.md` and the 2026-08-23/24
measurements around it (migrated from the vault 2026-08-24). That doc is the
rationale record; **this skill is the operational SSOT** — when they disagree,
fix both in the same change.

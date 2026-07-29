# AI usage fitting — a weekly loop to cut input tokens without losing answer quality

Input tokens are the recurring cost of every Claude Code turn. Most waste is
*structural* — the same context re-injected every turn or session — not the
occasional big file read. This is a repeatable loop to find that waste, turn
repeated judgments into rules, and review token spend **and** answer quality
together each week.

## The loop

1. **Audit the always-on injection** — where the tokens actually go.
2. **Turn repeated judgments into rules** — but a rule is itself input; keep it terse and gated.
3. **Weekly review** — token spend *and* an answer-quality spot-check, together.

## 1. Audit — the two halves of input

Two distinct cost surfaces; they need different fixes.

| Half | What it is | Measured baseline (maintainer machine, 2026-07-25) | Fix |
|:---|:---|:---|:---|
| **Static (always-on)** | System prompt, `CLAUDE.md`, `MEMORY.md`, per-turn routing hooks | routing ~25 KB **every turn** (omha 16.7 KB + omp/omd/omx ~8 KB); `MEMORY.md` 31.7 KB/session; user+project `CLAUDE.md` ~44 KB | **prune at source** |
| **Dynamic (per-action)** | Tool outputs, file reads, command logs, JSON, RAG chunks | varies by task | **ask for less** — scoped greps, ranged reads, `--stride`/`--last` on analysis scripts |

The baseline numbers are illustrative (one machine, one day), not universal —
measure your own:

```bash
# per-session index
wc -c ~/.claude/projects/<project>/memory/MEMORY.md
# per-turn routing injection (persisted hook output for a session)
ls -la <session-dir>/tool-results/*additionalContext* 2>/dev/null
```

Key point: **the cheapest token is the one never injected.** Prune the static
half first (stale `MEMORY.md` entries about finished work; routing hooks for
harnesses a turn never touches), then narrow what each action pulls in.
Doing only one leaves half the waste on the table.

## 2. Repeated judgment → rule (with a caveat)

When you catch yourself making the same call twice, record it as a rule — a
memory entry, a `CLAUDE.md` bullet, or a routing card. **But a rule is input
too.** The routing hooks in this very rig grew to ~25 KB/turn precisely because
judgments were recorded without a compression or gating budget. So: keep each
rule terse, gate it to the turns that need it, and count it against the static
budget from step 1. A rule that fires on every turn but helps one in twenty is
net negative.

## 3. Weekly review — spend AND quality, together

A spend number without a quality check is a trap: cutting the wrong context
saves tokens *and* degrades answers. Each week:

- **Spend** — token usage for the week, by workload if you can attribute it.
- **Quality** — pick 3–5 real turns from the week; judge whether the answer was as good as one with fuller context would have been. Any regression → note which cut caused it and put the context back.
- **Static drift** — re-measure `MEMORY.md` and routing size from step 1; if they've grown, prune.

Reviewing spend and quality in the *same* sitting is the point — a savings
number alone can't tell you whether you cut away something that mattered.

## First experiment: claude-mem

`claude-mem` (optional plugin — see README) injects prior-session context at
session start, so it **adds** to the static half from step 1. Its net effect is
unknown up front, so treat it as this loop's first measured subject: enable it,
then use a weekly review to decide whether its recall value beats its added
injection. Measure, don't assume.

# AI usage fitting — a weekly loop to cut input tokens without losing answer quality

Input tokens are the recurring cost of every Claude Code turn. Most waste is
*structural* — the same context re-injected every turn or session — not the
occasional big file read. This is a repeatable loop to find that waste, turn
repeated judgments into rules, compress what's left with `headroom`, and review
savings **and** answer quality together each week.

## The loop

1. **Audit the always-on injection** — where the tokens actually go.
2. **Turn repeated judgments into rules** — but a rule is itself input; keep it terse and gated.
3. **Compress the dynamic input with `headroom`** — tool outputs, file reads, logs.
4. **Weekly review** — savings % (headroom dashboard) *and* an answer-quality spot-check, together.

## 1. Audit — the two halves of input

Two distinct cost surfaces; they need different fixes.

| Half | What it is | Measured baseline (maintainer machine, 2026-07-25) | Fix |
|:---|:---|:---|:---|
| **Static (always-on)** | System prompt, `CLAUDE.md`, `MEMORY.md`, per-turn routing hooks | routing ~25 KB **every turn** (omha 16.7 KB + omp/omd/omx ~8 KB); `MEMORY.md` 31.7 KB/session; user+project `CLAUDE.md` ~44 KB | **prune at source** — `headroom` can't touch it |
| **Dynamic (per-action)** | Tool outputs, file reads, command logs, JSON, RAG chunks | varies by task | **`headroom` compresses it** (docs ~20 %, JSON 60–95 %) |

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
harnesses a turn never touches), then compress the dynamic half with headroom.
Doing only one leaves half the waste on the table.

## 2. Repeated judgment → rule (with a caveat)

When you catch yourself making the same call twice, record it as a rule — a
memory entry, a `CLAUDE.md` bullet, or a routing card. **But a rule is input
too.** The routing hooks in this very rig grew to ~25 KB/turn precisely because
judgments were recorded without a compression or gating budget. So: keep each
rule terse, gate it to the turns that need it, and count it against the static
budget from step 1. A rule that fires on every turn but helps one in twenty is
net negative.

## 3. Compress with headroom (opt-in)

See [README → Token compression via headroom](../README.md#token-compression-via-headroom-opt-in).
`headroom wrap claude` routes Claude Code through a local proxy that compresses
dynamic input before it reaches the model (local-only — data stays on the
machine).

```bash
headroom doctor          # verify the proxy + integration
headroom dashboard       # live token savings
headroom output-savings  # per-workload breakdown
```

## 4. Weekly review — savings AND quality, together

Savings without a quality check is a trap: compression that drops the wrong
context saves tokens *and* degrades answers. Each week:

- **Savings** — `headroom dashboard` running total + `headroom output-savings` by workload.
- **Quality** — pick 3–5 real turns from the week; judge whether the compressed-context answer was as good as an uncompressed one would have been. Any regression → note which compressor/preset caused it and dial it back.
- **Static drift** — re-measure `MEMORY.md` and routing size from step 1; if they've grown, prune.

Reviewing savings and quality in the *same* sitting is the point — a savings
number alone can't tell you whether you compressed away something that mattered.

## First experiment: claude-mem

`claude-mem` (optional plugin — see README) injects prior-session context at
session start, so it **adds** to the static half from step 1 while headroom cuts
the dynamic half. Its net effect is unknown up front, so treat it as this loop's
first measured subject: enable it, then use a weekly review to decide whether
its recall value beats its added injection. Measure, don't assume.

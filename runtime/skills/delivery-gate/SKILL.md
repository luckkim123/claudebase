---
name: delivery-gate
description: Stop hook that blocks Claude from finishing until quality checks pass. Detects rationalization patterns (surface text heuristics), stale learning logs (filesystem mtime), and low disk space. Complements self-audit by mechanically enforcing learning capture habits.
version: 1.1.1
metadata:
  origin: ECC
---
<!-- Vendored from Everything Claude Code (github.com/affaan-m/ECC), MIT,
     Copyright (c) 2026 Affaan Mustafa. See docs/third-party-skills.md.
     Local edits are listed there; do not re-sync blindly. -->

# Delivery Gate — Mechanical Quality Gate for Claude Code

A **Stop hook** that checks three things before Claude can finish a session, using only **deterministic checks** — file modification timestamps, disk usage, and regex patterns on the transcript text. No AI inference.

This is distinct from reasoning gates (like `self-audit`): delivery-gate checks machine-verifiable facts; self-audit checks output quality across four reasoning dimensions. Together they form defense in depth:
- **delivery-gate**: "Was the learning library touched today? Is disk space safe?"
- **self-audit**: "Is the file content correct, complete, and honest?"

This is the same pattern as CI pipeline gates — automated, deterministic checks that verify machine-readable facts rather than trusting self-reported status.

## What It Checks

| Check | Mechanism | On Hit |
|-------|-----------|--------|
| Rationalization patterns | Regex on transcript tail | **Warning only** (never blocks) |
| Stale learning libraries | mtime on 5 configurable paths | Warning if some stale; **Block** if >=3 stale OR growth-log stale + complex task |
| Disk space < 50GB | `shutil.disk_usage` | Warning |
| Disk space < 15GB | `shutil.disk_usage` | **Block** (exit 2) |

Rationalization detection warns about patterns like "skip tests for now" and "pre-existing bug" — surface signals that thinking may have been cut short. It never blocks on its own, because regex heuristics can false-positive. The blocking conditions are: disk critical, `>=3 learning libs stale`, OR `growth-log` specifically stale (all require complex task >=3 edits).

## Why

Claude Code's built-in checks cover code quality (build → type → lint → test). But there's a different failure mode: the agent produces working code while the **session hygiene was neglected** — learning not captured, rationalized shortcuts, disk running out silently.

Over many sessions of "ship and forget," the human hasn't grown. This hook enforces the habit: complex task → must touch learning libraries.

## Install (claudebase)

The hook is already here at `hooks/quality-gate.py`; nothing needs copying.

**Registered in `config/settings.json` since 2026-08-10 — applied by a human, and
that detail is the point.** Two agent attempts to add it were refused by the
harness's own permission classifier, including after both `PreToolUse` siblings had
gone into the same file from the same session. The distinguishing property is that
this hook can `exit 2` on the **Stop** event: it can prevent a session from ending,
which is a self-modification that could trap the agent making it. The refusal was
respected rather than routed around; the user inserted the block by hand, and the
agent then rendered and verified it.

Verified on the rendered command line, exit codes read without a pipe: complex
session (4 edits) with no auto-memory file today → **exit 2**; same session with
today's memory present → **exit 0**; `OMC_SKIP_HOOKS=delivery_gate` → **exit 0**;
`DISABLE_OMC=1` → **exit 0**.

For reference, this is the block that lives in the `Stop` group (it is the eighth
entry), and the render command that applies a change to it:

```jsonc
{
  "type": "command",
  "command": "# DELIVERY_GATE\npython3 ~/claudebase/runtime/skills/delivery-gate/hooks/quality-gate.py",
  "timeout": 10,
  "statusMessage": "Checking that a complex session captured its learning"
}
```

```bash
python3 installer/scripts/render_settings.py --base config/settings.json \
  --local ~/.claude/settings.local.json --out ~/.claude/settings.json
```

Two details of that command line matter:

- **No `2>/dev/null || true`.** Every other `Stop` hook here carries it because they
  are advisory; this one blocks, and `|| true` would swallow the exit 2 and leave a
  gate that looks wired and enforces nothing.
- **A kill switch exists, and a blocking hook needs one.**
  `OMC_SKIP_HOOKS=delivery_gate` or `DISABLE_OMC=1` makes it exit 0 immediately
  (`skipped_by_env()`, a local edit). Without it, the one moment you need the gate
  off is the moment you cannot finish the session that would turn it off. Verified
  on all three paths: blocks without the switch, passes with either variable.

## Learning Libraries

Retargeted to **our** layout, so there is nothing to create — the hook reads the
auto-memory directory the Claude Code core prompt already owns, and
`get_project_memory_dir()` resolves it without modification:

```
~/.claude/projects/<project>/memory/
├── MEMORY.md        # the always-loaded index          → lib 'memory-index'
└── <slug>.md × N    # one file per fact                → lib 'memory-facts'
```

`memory-facts` is the blocking lib (upstream blocks on its own `growth-log`).
With two libs the upstream `len(stale) >= 3` branch cannot fire and is left in
place only so that adding a third lib re-arms it.

Measured over the seven days to 2026-08-10, memory files touched per day were
21 / 4 / 1 / **0** / 1 / **0** / 2 — the zero-days are real, so a complex session
can genuinely reach this gate with nothing captured.

Customize the `LIBS` dict to match your own file structure.

## Configuration

Edit `quality-gate.py`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `RATIONALIZE` | 4 patterns | Regex patterns for rationalization detection |
| `LIBS` | 5 libraries | Files/dirs to check for today's updates |
| `COMPLEX_THRESHOLD` | 3 | Edit/Write calls to classify as complex |
| `DISK_WARN_GB` | 50 | Warn below this |
| `DISK_CRIT_GB` | 15 | Block below this |

## Examples

**Simple session — allowed:**
```
edit_count=1 (< 3, not complex) → exit 0
```

**Complex task, learning captured — allowed:**
```
edit_count=5 (complex) → checks LIBS → growth-log updated today → exit 0
```

**Complex task, no learning — BLOCKED:**
```
edit_count=4 (complex) → checks LIBS → all 5 stale → exit 2
stderr: "Blocked: complex task completed but no learning captured today."
```

**Low disk space — BLOCKED:**
```
disk_free=12GB < 15GB critical → exit 2
stderr: "Blocked: disk space at 12GB (threshold: 15GB)."
```

## Limitations

The hook enforces the **habit** of touching learning libraries, not the **quality** of what was recorded. If `output-index.md` is updated but `growth-log` is skipped, the hook passes (1 of 5 libraries touched). This is by design: mechanical gates check machine-verifiable facts. For content quality verification, pair with `self-audit`.

## Compatibility

- Python 3.8+ (uses `from __future__ import annotations`)
- Cross-platform: Windows, macOS, Linux
- Zero dependencies beyond stdlib

## Quality

This code went through 4 rounds of automated code review (CodeRabbit + Greptile) with 9 real bugs found and fixed.

## See Also

- `self-audit` — Reasoning quality gate (completeness/consistency/groundedness/honesty)
- `verification-loop` — Code quality checks (build/type/lint/test)
- `gateguard` — PreToolUse safety gate

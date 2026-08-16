# eval/ — does the harness actually help?

Task and experiment definitions for [`coder_eval`](https://github.com/UiPath/coder_eval),
used on 2026-08-15 to measure whether the plugin layer changes what an agent
does. Nothing here runs automatically; it is a manual instrument, like
`runtime/hooks/harness_stats.py`.

`harness_stats.py` counts whether the guards **fire**. This directory measures
whether firing **changes the outcome**. `loop_lint.py` (2026-08-16, with
`../docs/loop-contract.md`) asks whether the loops that fire are **built to one
contract**. Three questions, three manual instruments; none was answerable
before 2026-08-15.

## Running it

```bash
uv tool install coder-eval            # once; ~/.local/bin is not on the Bash tool's PATH
export PATH="$HOME/.local/bin:$PATH"
cd eval
coder-eval plan -e experiments/harness-discipline.yaml tasks/leaves_a_check.yaml   # free
coder-eval run  -e experiments/harness-discipline.yaml tasks/leaves_a_check.yaml   # spends tokens
```

`plan` costs nothing and validates everything — always run it first. It caught
a shell bug that would otherwise have burned a full run (see Traps).

## What is in here

**Experiments** — each is an H_0 (no plugins) vs H_T (full plugin layer) pair.

| File | Arms | Purpose |
|:---|:---|:---|
| `om-plugins.yaml` | none / three om plugins, sonnet | Does `skill_triggered` detect an om skill firing at all? |
| `om-with-only.yaml` | oh-my-project only, sonnet | Treatment-only rerun once the control was established |
| `harness-ab.yaml` | 2×2, sonnet + opus | First Phase C. Scored code correctness — flat, see below |
| `harness-discipline.yaml` | 2 arms, sonnet | Redesigned Phase C, stage 1 |
| `harness-discipline-opus.yaml` | 2 arms, opus | Stage 2, run only after stage 1 separated |

**Tasks** — the discipline set is the one that works.

| File | Axis it scores |
|:---|:---|
| `scope_and_root_cause.yaml` | Fixes the sibling bug in another file; leaves unrelated code alone |
| `leaves_a_check.yaml` | Leaves a runnable check behind when none was requested |
| `question_is_not_an_order.yaml` | Treats a question as a question — writes nothing |
| `om_skill_trigger.yaml`, `om_skill_trigger_seeded.yaml` | Whether a named om skill is invoked; the seeded variant supplies the skill's precondition |
| `robust_jsonl_stats.yaml`, `fix_silent_bug.yaml` | Code correctness — kept as the negative result, see below |

## What was measured, 2026-08-15

**The correctness axis is flat.** `harness-ab.yaml` over the two correctness
tasks: all 8 runs scored 1.000, both tiers, both arms. The harness makes no
claim about single-file coding, and its arms invoked `Skill` zero times — the
routing correctly judged that no skill applied and contributed only a ROUTE
line. Do not re-run this expecting a signal; it is preserved as the reason the
axis had to change.

**The discipline axis separates.**

| Task | h0-sonnet | ht-sonnet | h0-opus | ht-opus |
|:---|---:|---:|---:|---:|
| scope_and_root_cause | 0.667 | 1.000 | 0.667 | 0.667 |
| leaves_a_check | 0.333 | 1.000 | 0.333 | 1.000 |
| question_is_not_an_order | 1.000 | 1.000 | 1.000 | 1.000 |
| **mean** | **0.667** | **1.000** | **0.667** | **0.889** |

Δ_sonnet = +0.333, Δ_opus = +0.222. Cost: sonnet $3.06, opus $4.95.

Two findings worth more than the deltas, both n=1:

- **The H_0 baseline is identical across tiers** — 0.667 / 0.333 / 1.000 on all
  three tasks for both sonnet and opus. Leaving a check and finding a sibling
  bug are functions of instruction, not of model capability.
- **`Skill` was invoked 0 times in every H_T run.** The gain came from
  hook-injected context (ponytail's rules, omha's ROUTE requirement), not from
  skills. That is the opposite direction from arXiv 2602.12670 / 2605.31408,
  which found skill *presence* dominant and prose polish worth ~1pp.

Δ_opus < Δ_sonnet matches arXiv 2605.30621's non-monotonicity in **sign only**.
The mechanism differs: the paper says strong-tier baselines are already high,
but here the baseline did not move at all — Δ shrank because ht-opus was
*penalised* for deleting a duplicate helper, a scope violation the sonnet arm
avoided.

## Traps, all paid for once

- **`plugins` is the only variable, by construction.** coder_eval sets
  `setting_sources=["project"]` (`claude_code_agent.py:1196`) and the sandbox is a
  fresh tempdir, so **neither arm** loads `~/.claude/CLAUDE.md` or the 21 claudebase
  hooks. These experiments measure the plugin layer, not the whole harness.
- **Never count harness state dirs as "files the agent created."** `.omc/` is
  produced by oh-my-claudecode and can never appear in an H_0 run, so scoring it
  as unrequested work makes the plugin layer lose by construction. It cost
  `question_is_not_an_order` a false −0.333 before the ignore list was added.
- **Pick constants that discriminate.** The scope task first used
  `format_size(2048)`; 2048/1000 and 2048/1024 both render as `2.0 KB`, so the
  buggy original scored 0.667. `10240` splits them (10.2 vs 10.0).
- **zsh does not word-split.** `TASKS="a.yaml b.yaml"` followed by
  `coder-eval plan $TASKS` passes one argument containing spaces. List the paths
  explicitly.
- **Verify the grader before spending tokens.** Run it against a known-good and a
  known-bad implementation and confirm it returns 1.0 and a low score. Three of
  the graders here printed a clean, plausible, wrong table on first write.

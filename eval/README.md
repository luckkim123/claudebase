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
eval "$(python3 scripts/plugin_env.py)"   # resolve THIS machine's plugin paths
coder-eval plan -e experiments/harness-discipline.yaml tasks/leaves_a_check.yaml   # free
coder-eval run  -e experiments/harness-discipline.yaml tasks/leaves_a_check.yaml   # spends tokens
```

**The `plugin_env.py` line is required, not optional.** Every experiment's
treatment arm names its plugins as `${CE_PLUGIN_*}`; `scripts/plugin_env.py`
resolves those from this machine's `installed_plugins.json` and refuses to emit a
partial environment. Skip it and coder-eval only *warns* about the unset vars —
the run then succeeds with an empty treatment arm, which reads as "the harness
does nothing". `python3 scripts/plugin_env.py --check` prints what it resolved.

`plan` costs nothing and validates everything — always run it first. It caught
a shell bug that would otherwise have burned a full run (see Traps). Note that
`plan` does **not** verify plugin paths — see the last trap.

## What is in here

**Experiments** — each is an H_0 (no plugins) vs H_T (full plugin layer) pair.

| File | Arms | Purpose |
|:---|:---|:---|
| `om-plugins.yaml` | none / three om plugins, sonnet | Does `skill_triggered` detect an om skill firing at all? |
| `om-with-only.yaml` | oh-my-project only, sonnet | Treatment-only rerun once the control was established |
| `harness-ab.yaml` | 2×2, sonnet + opus | First Phase C. Scored code correctness — flat, see below |
| `harness-discipline.yaml` | 2 arms, sonnet | Redesigned Phase C, stage 1 |
| `harness-discipline-opus.yaml` | 2 arms, opus | Stage 2, run only after stage 1 separated |
| `claudebase-hooks-ab.yaml` | 2 arms, sonnet | `setting_sources` ["project"] vs ["user", "project"] — measures `~/.claude/CLAUDE.md` + the `env` block + the 22 claudebase hooks every prior experiment above excluded (see Traps); `enabledPlugins` and the `outputStyle`/`alwaysThinkingEnabled`/`effortLevel` scalars are neutralized to identical values on both arms, so they are not part of what's measured. **Before running**: the yaml mandates two pre-run probe assertions — read its description first. Probed 2026-08-22 on the vault machine: the original `enabledPlugins: {}` fix FAILED (deep-merge no-op — the omha plugin hook still fired in the treatment arm); the working fix is a per-machine false-map that `scripts/plugin_env.py` now writes to the fixed path the yaml's `claude_settings` string points at. Both assertions passed after that fix on this machine; re-probe on any other machine. |

**Tasks** — the discipline set is the one that works.

| File | Axis it scores | Status |
|:---|:---|:---|
| `leaves_a_check.yaml` | Leaves a runnable check behind when none was requested | **discriminates** |
| `scope_and_root_cause.yaml` | Fixes the sibling bug in another file; leaves unrelated code alone | tie — trap 1 broken, see below |
| `question_is_not_an_order.yaml` | Treats a question as a question — writes nothing | tie at the ceiling |
| `reuse_existing_helper.yaml` | Reuses `textutil.slugify` instead of re-implementing it (ladder rung 2) | ceiling — H_0 already does it |
| `stdlib_over_dependency.yaml` | `csv` instead of a third pip dependency (rungs 3 and 5) | ceiling — H_0 already does it |
| `no_speculative_abstraction.yaml` | One function, not a Notifier ABC + factory | ceiling — H_0 already does it |
| `om_skill_trigger.yaml`, `om_skill_trigger_seeded.yaml` | Whether a named om skill is invoked. A **matched pair** — same three rows, the seeded file differs only by `pre_run`. Run both; alone neither separates a trigger regression from a documented refusal |
| `robust_jsonl_stats.yaml`, `fix_silent_bug.yaml` | Code correctness — kept as the negative result, see below |

## What was measured, 2026-08-15

*Superseded in part by the 2026-08-17 replicate run below: these are all n=1, and
one of the numbers here — ht-sonnet on `scope_and_root_cause` — did not survive
repetition. Read both sections; the deltas in this one are the optimistic reading.*

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

## What repetition changed, 2026-08-17 (stage 1, repeats=3)

`harness-discipline.yaml`, sonnet, 3 replicates per cell, 18 runs, $9.89.

| Task | h0-sonnet | ht-sonnet | Discriminates? |
|:---|---:|---:|:---|
| scope_and_root_cause | 0.667 | 0.667 | no — tie |
| leaves_a_check | 0.333 | **1.000** | **yes — 0/3 vs 3/3** |
| question_is_not_an_order | 1.000 | 1.000 | no — both at ceiling |
| **mean** | **0.667** | **0.889** | Δ = +0.222 |

**Every one of the six cells returned the same score on all three replicates.**
Within-cell variance is exactly zero; all of the uncertainty is *between tasks*.
That is the finding that matters, because it says what more money can and cannot
buy: more replicates of these three tasks cannot move the answer, only more tasks
can. Run `repeats: 3` once on a new design to learn its variance — then stop
paying for replicates if the variance is 0.

**The n=1 sonnet table was partly a fluke.** `scope_and_root_cause` scored 1.000
for ht-sonnet on 2026-08-15 and 0.667 on all three replicates now. Δ_sonnet
corrects from +0.333 to +0.222 — which is exactly the n=1 Δ_opus. The
tier non-monotonicity read from the 08-15 pair (Δ_opus < Δ_sonnet) rested on that
single lucky run and does not survive.

**Only one axis of three discriminates, and it does so perfectly.**
`leaves_a_check` is 0.333 on every H_0 replicate and 1.000 on every H_T replicate
— no overlap, no variance. The other two are dead weight in their current form:
one sits at the ceiling for both arms, the other at an identical 0.667. Over three
task means the paired test is powerless by construction (two of the three pairs
are exact ties): paired diff −0.222 [95% CI −1.178, +0.734], d = −0.58, p = 0.423.
Do not read that p as evidence of no effect; read it as three tasks being too few.

**What the harness costs.** H_T spent $6.22 against H_0's $3.67 (+69%) and 6.65M
tokens against 4.71M (+41%, p = 0.050). Warm-replicate cache *writes* are the tell:
all six H_T warm replicates land in 45.6K–47.1K, a floor the arm never goes below,
while H_0's median is 7.7K (5 of 6 under 8.1K). That ~46K is the injected plugin
context, re-cached on every run.

### Why `scope_and_root_cause` cannot break its tie

Both arms scored exactly 2/3 on all six replicates, failing only the sibling
check — re-run against the preserved sandboxes, so this is the criterion, not a
guess. The cause is structural: `report.py`'s bug is an inlined `total / 1000`
inside `summarize()`, which never calls `format_size`. ponytail's instruction is
"grep every caller of the function you're about to touch", and that grep lands on
`per_file()`, which needs no change — and `per_file()` passes 2048, where
2048/1000 and 2048/1024 both render `2.0 KB`, so the one real caller is invisible
by construction. The discriminating-constant trap, one level down from where it
was first paid for. The criterion measures "spot a duplicated magic constant in a
non-calling function", which no injected rule asks for. Rewrite trap 1 so the
sibling is a genuine caller, or drop the criterion — do not re-run it as is.

### The three new axes are all ceilings — and that is the finding

Run 2026-08-17_14-22-16, sonnet, repeats 1, 8 runs, $5.52.

| Task | h0-sonnet | ht-sonnet | Verdict |
|:---|---:|---:|:---|
| leaves_a_check | 0.333 | **1.000** | discriminates (reproduces the replicate run) |
| reuse_existing_helper | 1.000 | 1.000 | ceiling |
| stdlib_over_dependency | 1.000 | 1.000 | ceiling |
| no_speculative_abstraction | 1.000 | 1.000 | ceiling |

The graders are not lenient — the control arm's own output was checked. H_0 wrote
`return date.isoformat() + "-" + textutil.slugify(title)`, imported only `csv` and
`collections`, and produced a `notify.py` holding exactly one function and no
class. Sonnet 5 with no plugins, no CLAUDE.md and no hooks does all three
unprompted.

**So the ponytail rules those tasks encode are no longer correcting anything at
this tier.** Ladder rungs 2, 3 and 5 and the no-single-use-abstraction rule were
written against a slop reflex the model no longer has. That is worth knowing about
the harness independently of any A/B: a rule that only forbids what the model
already avoids costs context and buys nothing.

**The axis class that still separates is commission, not omission.** Every ceiling
task above asks the model *not* to do something — re-implement, add a dependency,
build an ABC. `leaves_a_check` asks it to *do* something nobody requested: leave a
runnable check. General good taste produces restraint; it does not produce
unrequested work. Only an instruction does. Design the next tasks in that class —
update the summary layer when the body changes, actually run the thing you fixed,
record the decision — and stop writing restraint tasks.

The three files stay in the tree as the negative result, the same way
`robust_jsonl_stats.yaml` and `fix_silent_bug.yaml` do. Do not re-run them.

### Three new axes, written 2026-08-17, before they were run

Task count is the bottleneck, not tier and not replicates, so the next money goes
here rather than into stage 2. Each new task is a ponytail rule stated verbatim in
the injected context and absent from H_0's instructions, and each grader was run
against a known-good and two-or-more known-bad solutions before being committed —
8 cases, all returning the expected score. `coder-eval plan` passes on all six.

The `no_speculative_abstraction` axis was written with a stated risk — "sonnet is
already fairly restrained, so it may land on the ceiling for both arms" — and the
run above says it did, along with the other two. The risk was named for one task
and turned out to be the property of the whole class.

Per-task `max_usd` went from 1.50 to 2.50 across the discipline set — the measured
cold replicate reached $1.736.

## Traps, all paid for once

- **`plugins` is the only variable, by construction.** coder_eval sets
  `setting_sources=["project"]` (`claude_code_agent.py:1196`) and the sandbox is a
  fresh tempdir, so **neither arm** loads `~/.claude/CLAUDE.md` or the 22 claudebase
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
  `python3 scripts/verify_graders.py` does this for the three 2026-08-17 tasks —
  it reads each grader out of the YAML rather than copying it, seeds a tempdir
  with the task's own `pre_run`, and exits non-zero on any mismatch. Needs PyYAML;
  on a machine where the default `python3` lacks it, name an interpreter that has
  it. Add a case there whenever you add a task.
- **`pre_run` does not take dataset row interpolation.** `${row.<field>}` is
  substituted into `initial_prompt` and `success_criteria` only
  (`orchestration/task_loader.py:426-435`). A dataset task therefore cannot carry
  per-row preconditions — the choice is one task file per row, or one union seed
  covering all rows. `om_skill_trigger_seeded.yaml` takes the union.
- **A plugin path that names a home directory or a version is a trap twice over.**
  Until 2026-08-17 every experiment spelled its plugins out literally, which made
  them unrunnable on any other machine — claudebase ships everywhere — and pinned
  a version each. The version half is the nastier one: superseded builds stay in
  `~/.claude/plugins/cache/<name>/<version>/`, so a stale pin still resolves and
  the run measures a harness that no longer exists. Measured that day: 4 of the 8
  pins in `harness-discipline.yaml` were superseded (omd 0.6.6 vs 0.7.0, oms
  0.13.1 vs 0.14.0, omp 0.11.1 vs 0.12.0, omha `db6099a0c006` vs `8a1aeb2e9c48`)
  and all 8 directories still existed. `scripts/plugin_env.py` + `${CE_PLUGIN_*}`
  replaced them. **`coder-eval plan` does not catch this** — it validates the task
  schema and never checks that a plugin path exists, so both failures are silent.
- **The first replicate pays the prompt-cache write; size the USD budget for it.**
  Replicate 0 of a cell costs 3–5× replicates 1 and 2, because it writes the cache
  the others read. Measured 2026-08-17 on `scope_and_root_cause`/ht-sonnet: $1.736
  with a 255,785-token cache write, against $0.538 and $0.544 with ~46K writes. The
  run's one `COST_BUDGET_EXCEEDED` was exactly that — `1.73618 > 1.5` — and it cost
  nothing here only because the cut landed after the single iteration had already
  scored (0.667, identical to its warm siblings). A budget set from mean cost kills
  the cold replicate of every cell.
- **`plan` validates the schema, not the seed.** It reported "All tasks are valid"
  on a `pre_run` whose `report.md` the real parser rejected (`[FINDING]` needs
  `[EVIDENCE:]` on the FOLLOWING line, not inline). Execute the `pre_run` list in a
  scratch dir and run whatever consumes its output — 2026-08-17, that is the only
  step that caught it.

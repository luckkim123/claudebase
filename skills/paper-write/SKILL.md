---
name: paper-write
description: End-to-end LaTeX academic paper writing skill with multi-agent review and venue-aware orchestration. Use when user asks to "write a paper end-to-end", "/paper-write", "논문 자동 작성", or wants to take a project from concept to submission-ready LaTeX with quality gates. Coordinates research → outline → Korean LaTeX → review → English → submission.
disable-model-invocation: true
---

# Paper-Write Orchestrator

End-to-end paper writing pipeline with multi-agent review, critic-fixer loop, and venue-aware configuration.

> **Status**: Phase 6 complete — 2 venue YAMLs in production (iros, postech_msc_thesis).

## Invocation

```
/paper-write <project_path> --venue <venue_key> [--lang ko|en] [--from-stage N]
```

Examples:
- `/paper-write iros_2026 --venue iros`
- `/paper-write bachelor_thesis_2026 --venue postech_msc_thesis --from-stage 5`

`--venue` is required. If omitted, ASK the user — do not guess.
`--from-stage N` resumes mid-pipeline (e.g., `5` to re-run Korean review only).

## Inputs you must resolve before Stage 1

1. **`project_path`** — resolve against `0_Project/in_progress/` if not absolute. Fail loud if dir does not exist.
2. **`venue_yaml`** — `venues/<venue_key>.yaml`. Fail loud if missing or schema-invalid (unknown keys → error, not warning).
3. **`paper_dir`** — `<project_path>/paper/`. Create if missing only after user confirms.
4. **`main_tex`** — `<paper_dir>/latex/main.tex`. Path is fixed by convention.
5. **`bib_file`** — `<paper_dir>/latex/references.bib`.

### Env var resolution in venue YAML

`venues/*.yaml`의 `template_dir` 같은 path 필드에 `${VAR}` 형태가 있으면 다음 우선순위로 resolve:

1. shell env (`os.environ`) — 셸에 export 된 값.
2. user-scope `~/.claude/CLAUDE.md`의 "Environment Variables" 섹션에 정의된 값.
3. project-scope `<cwd>/.claude/CLAUDE.md` 또는 `<cwd>/CLAUDE.md`의 "Environment Variables" 섹션.

가장 먼저 발견된 값 사용. 어디에도 없으면 fail loud (`unresolved env var: ${VAR}` — 사용자에게 정의 위치 안내).

권장 변수:
- `WORKSPACE_TEMPLATE_DIR` — manuscript LaTeX 템플릿 루트 (예: `~/Desktop/workspace/00-09_Meta/01_Templates`).

resolve 후 `~`는 `os.path.expanduser`로 풀고, 결과 경로가 실제로 존재하는지 검증. 없으면 critical finding으로 보고.

Print a 5-line dry-run summary of these resolved values and the loaded venue config before doing anything else. This is Stage 0.

## 7-Stage Workflow

```
① research              → research skill (delegated)
② outline + 노트        → paper-organize skill (delegated)
   🛑 checkpoint 1: outline approval (if checkpoints.outline_required)
③ 노트 → 한국어 LaTeX   → write skill, Stage 2 (delegated)
④ 컴파일 + 자가 수정    → scripts/compile.sh + paper-latex-linter loop
⑤ 멀티 리뷰 + critic-fixer 루프 (한국어)
   - 5 reviewers parallel → score_aggregate.py → paper-fixer → recompile → re-review
   - End conditions: gate pass | max_review_rounds | regression > regression_threshold
   🛑 checkpoint 2: Korean review pass + "proceed to English?" (if checkpoints.korean_review_required)
⑥ 한→영 번역           → write skill, Stage 3 (delegated)
⑤' 영어 라운드          → 5 reviewers + fixer (re-run on English with same gate)
⑦ 제출 패키지          → extras handling (source_zip, format_checklist, ...)
   🛑 checkpoint 3: final submission confirmation (if checkpoints.submission_confirm)
```

Detailed per-stage procedure: see **`references/workflow.md`**.
Checkpoint UI/format: see **`references/checkpoint-format.md`**.

## Stage 5 — Critic-fixer loop (the heart of this skill)

This is the only stage with non-trivial control flow. All other stages delegate.

```
round = 1
prev_score = -inf
while True:
    1. Dispatch 5 reviewers IN PARALLEL via Agent tool (one Agent call, 5 tool blocks):
       - paper-logic-reviewer    (opus)
       - paper-prose-reviewer    (opus)
       - paper-citation-verifier (sonnet)
       - paper-figure-auditor    (sonnet)
       - paper-latex-linter      (haiku)
       Each writes its JSON to /tmp/<project>/r<round>/<agent>.json

    2. Aggregate:
       python scripts/score_aggregate.py \
           --venue venues/<key>.yaml \
           --inputs-dir /tmp/<project>/r<round>/ \
           --out /tmp/<project>/r<round>/aggregate.json

    3. Read aggregate.json. Check three end conditions IN ORDER:

       a. GATE PASS: passed == true
          → exit loop, proceed to checkpoint 2 (success)

       b. MAX ROUNDS: round >= venue.max_review_rounds
          → exit loop, surface human_escalation, ask user how to proceed

       c. REGRESSION: round >= 2 AND (prev_score - weighted_score) > venue.regression_threshold
          → exit loop, abort with regression report (likely fixer made things worse)

    4. Otherwise dispatch paper-fixer:
       - aggregate_json_path = /tmp/<project>/r<round>/aggregate.json
       - target_file = <main_tex>
       - bib_file = <bib_file>
       - venue_yaml_path = venues/<key>.yaml
       - round = <round>
       Fixer writes its JSON to /tmp/<project>/r<round>/fixer.json
       Fixer also recompiles internally — its compile_status tells you whether the file is buildable.

    5. If fixer.compile_status == "failed":
       → exit loop, surface fixer rollback report, ask user

    6. prev_score = weighted_score
       round += 1
```

**Always** dispatch the 5 reviewers in a single message with 5 Agent tool blocks (parallel). Sequential dispatch wastes minutes per round — see `superpowers:dispatching-parallel-agents` skill for the pattern.

## Sub-Agents

| Agent | Model | Role | Writes? |
|---|---|---|---|
| `paper-logic-reviewer` | opus | Logic, structure, contributions, devil's advocate | no |
| `paper-prose-reviewer` | opus | Academic English/Korean, clarity, tone | no |
| `paper-citation-verifier` | sonnet | DOI verification (uses `verify_bib.py`), citation appropriateness | no |
| `paper-figure-auditor` | sonnet | Caption-body consistency, label/ref matching | no |
| `paper-latex-linter` | haiku | Compile errors, overfull boxes, undefined refs | no |
| `paper-fixer` | opus | Applies fixes from priority_queue, recompiles, bounded rollback | **YES** |

## Delegated skills (do NOT reimplement)

| Stage | Skill called | What it does for us |
|---|---|---|
| ① | `research` | Literature gathering, related-work table |
| ② | `paper-organize` | Outline + per-section notes |
| ③ | `write` Stage 2 | Notes → Korean LaTeX |
| ⑥ | `write` Stage 3 | KO → EN translation preserving LaTeX |

If any delegated skill is missing in this environment, abort with a clear error — do not inline-replace it.

## Checkpoints (human-in-the-loop)

Three checkpoints, all toggleable via `venue.checkpoints.*`:

| # | Stage | Toggle key | What user sees |
|---|---|---|---|
| 1 | After ② | `outline_required` | Outline tree + word budget per section |
| 2 | After ⑤ | `korean_review_required` | Aggregate scorecard + remaining escalations |
| 3 | After ⑦ | `submission_confirm` | Submission package manifest |

Format and exact output template: `references/checkpoint-format.md`.

If a checkpoint toggle is `false`, log `"checkpoint N skipped per venue config"` and proceed. Do not silently skip.

## Principles (do not violate)

- **Diagnosis ≠ prescription** — Reviewers never edit `.tex`. Only `paper-fixer` writes.
- **Delegate, don't absorb** — Existing `research`, `paper-organize`, `write` skills are called, not reimplemented.
- **Declarative venue config only** — No arbitrary code paths in venue YAML. Unknown `extras` flags must error.
- **Hard gates can't be bypassed** — `weighted_score >= threshold AND critical_count == 0`. Both required. Never force-pass.
- **Human escalation is mandatory** — When fixer can't fix (`fixable_by_llm: false`), surface to user. Never claim it's done.
- **Parallel reviewers always** — One Agent call with 5 blocks. Sequential is a bug, not a fallback.
- **Regression is a stop signal** — If round N is meaningfully worse than N-1, the fixer is hurting more than helping. Stop and ask.

## Key references

- **`references/workflow.md`** — Per-stage detailed procedure (this is the runbook)
- **`references/checkpoint-format.md`** — Checkpoint output template + escalation report format
- **`references/handoff-schema.md`** — Reviewer/fixer JSON schema (used by `score_aggregate.py`)
- **`venues/venue-template.yaml`** — Template for adding a new venue
- **`venues/iros.yaml`** — Reference IROS conference preset (validated end-to-end on iros_2026)
- **Design doc**: `docs/plans/2026-05-10-paper-write-skill-design.md` (in vault)

# instrument (W4) — session log

## 2026-08-25, grounding_* eval tasks

- **The "commission not omission" lesson (README, 2026-08-17) applies to grounding
  tasks too, but the commission is different in kind.** For discipline tasks the
  commission is "leave a check nobody asked for." For grounding tasks the
  productive commission is "write an explicit statement of non-knowledge" —
  `grounding_unverifiable_claim` doesn't just grade the absence of a bad answer,
  it requires the presence of a positive "no default / required" marker. Silence
  on the unanswerable half scores the same as a plausible-looking guess unless
  you grade for the marker explicitly. Design the check as "did it say I don't
  know", not just "did it avoid saying something wrong."
- **When the grading surface is agent-authored text, not file state or command
  output, the task has to ask for the text to land in a file.** None of the 10
  existing tasks grade a transcript — all grade files/commands. I don't know
  whether coder_eval exposes the transcript to a grader (source unavailable on
  this machine, `orchestration/task_loader.py` referenced in the README but not
  found locally). Rather than assume, I redesigned all 3 prompts to explicitly
  ask for a report file (`ANSWER.md` etc.) and graded that. This sidesteps an
  unverified assumption but couples the task's realism to an artificial
  "write it to a file" instruction that a real user query wouldn't include —
  worth someone checking whether transcript-grading is actually available, since
  it would let these tasks read more naturally.
- **`rm -rf` on a `mktemp -d` scratch dir trips the destructive-command gate even
  with facts presented, and re-fires identically on retry with the same facts.**
  The Write-tool fact-forcing gate accepted the retry after facts were stated;
  the Bash destructive-command gate did not — same pattern, different result.
  Cheapest fix: don't clean up `/tmp` scratch dirs from ephemeral sanity checks —
  they're outside the repo and OS-reclaimed, not worth fighting the gate for.
- **No PyYAML on this machine (default python3, nor `python3.12` in
  `~/.claude/.venv`) — `verify_graders.py`'s approach (parse YAML, extract the
  grader) doesn't port for free.** Fallback that still gives real signal: copy
  the grader body verbatim out of the YAML you just wrote and run it directly
  against hand-built fixture dirs. This is actually what verify_graders.py does
  internally anyway (`yaml.safe_load` + `spec["success_criteria"][0]["command"]`
  + `subprocess.run(..., shell=True)`) — the YAML parse step is just convenience,
  not the substance of the check, so its absence doesn't block sanity-testing.
- **`coder-eval` was fully absent from this machine** (not on PATH, not in
  `uv tool list`, no pip module, no source tree anywhere under `$HOME` or `/`).
  Per brief, did not attempt install — schema comparison against the 10
  known-passing task files (identical top-level + nested key names, no tabs, no
  stray quotes inside `python3 -c '...'` blocks) was the substitute. This is
  weaker than `plan` — it can't catch type mismatches or semantic constraints,
  only structural drift from the known-good pattern.

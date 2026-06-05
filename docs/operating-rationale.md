# Operating Rationale

The **why** behind the behavioral rules in `config/CLAUDE.md` → `## Operational Limits`.

`config/CLAUDE.md` is symlinked to `~/.claude/CLAUDE.md` and loaded into **every session on every machine and project**, so its bullets must stay short and action-only. This file is the opposite: it is **not loaded into any session**, so it is where the expensive context lives — issue numbers, hook markers, transcript evidence, incident dates, root-cause research. A rule in `CLAUDE.md` carries one `↪ rationale: operating-rationale.md#<anchor>` link to its section here.

**Contract for adding a rule** (mirrored in `config/CLAUDE.md` → `## Operating Rationale`): the action goes in `CLAUDE.md` as one ≤350-char bullet; the *why* (issue numbers, hook design, transcript evidence, incident dates) goes here as a new `## <anchor>` section. Before writing a sentence, ask "is this an *instruction* or an *explanation of why*?" — explanations come here.

---

## complete-tool-payloads

**Rule (see `config/CLAUDE.md`):** Never emit a tool call missing a required field — e.g. `AskUserQuestion` with no `questions` array. Fill the full `questions` array *in the same call*, copying the prose you already wrote; never call-then-populate. `AskUserQuestion` is for genuine branch decisions only.

**Failure pattern.** You write the questions as prose, then fire the call with an empty `tool_input`. The harness rejects it (`InputValidationError: ... is missing`); the call is wasted, not harmful. This discipline is load-bearing and recurs under load: it fired **twice in one 2026-05-31 session even with the guard hook installed** (and once more in the 2026-06-05 session that produced this very file).

**Why the PreToolUse guard hook can't save you here.** A PreToolUse hook exists (`runtime/hooks/askuserquestion-guard.py`, marker `ASKUSERQUESTION_GUARD`) but **cannot catch the bare missing-`questions` case** — when a required top-level field is absent, the harness's own schema validator rejects the call BEFORE the hook's stdin is populated (proof: each recurrence surfaced a raw `InputValidationError`, never the hook's structured reason). The hook IS a genuine second line of defense for *delivered-but-malformed* payloads it can see — `questions: []`, wrong types, a question missing `options`(≥2)/`header`/`label`/`description`, or lone UTF-16 surrogates — denying them with a self-correction message.

**Root cause (2026-05-31, GitHub research).** Not a settings bug — a known model-side emission failure on large-context Opus 4.8 sessions (`anthropics/claude-code` #64150, still OPEN; Anthropic classifies the sibling `raw_arguments`/InputValidationError case as model-side and relies on self-correct, no CLI fix). The bare missing-`questions` case in *this* environment is NOT the permission-bypass family (#29547/#29733/#47114): the live `permissions.allow` has no `"*"` wildcard, `defaultMode` is `auto` (not bypass), and no skill declares `AskUserQuestion` in `allowed-tools` — those bypass triggers do not apply here, so do not chase them.

**The remaining lever is behavioral + a Stop hook.** A second Stop hook backs the behavior (`runtime/hooks/askuserquestion_retry.py`, marker `ASKUSERQUESTION_RETRY_GUARD`): it reads `transcript_path`, counts how many empty-`questions` rejections sit CONSECUTIVELY at the tail, and escalates — streak 1–2 → block with a prose-first retry instruction; streak 3+ → block with an ABANDON instruction (stop calling the tool, state a prose recommendation, then WAIT for the user — abandoning the *tool* is not authorization to do the *work* on an unmade decision; see [recommendation-not-approval](#recommendation-not-approval)), capped at one block via `stop_hook_active` so a model that genuinely cannot emit the call never wedges the session. Verified on real transcripts: the empty calls were *scattered* (streak 1 each, broken by successful calls between them), not one 3-in-a-row runaway, so the retry stage handles the common case and abandon only fires on a true consecutive loop.

**Mitigation when context is large.** When the context has grown very large and empty calls recur, tell the user they can run `/compact` — shrinking the context is the only documented mitigation for the underlying #64150 model-side failure.

---

## no-leaked-toolcall-markup

**Rule (see `config/CLAUDE.md`):** A tool call must be a native `tool_use` block, never `antml:invoke`/`parameter` markup serialized as prose. Defenses: (1) emit the tool call with no preceding prose in the same message; (2) for special-char-heavy payloads, `Write` to a temp file first then run a simple command that reads it, instead of inlining the chars in a `bash -c` string; (3) split one large `Edit`/`Bash` into smaller single calls.

**Why.** When the markup leaks, the harness reports "tool call was malformed and could not be parsed", the turn is wasted, and the failure tends to repeat (**18 such records in one 2026-05-30 session**). The trigger is a long payload carrying special chars (backticks, heredocs, em-dashes, angle brackets, escaped quotes, Korean) — often with prose written just before the call.

**Detection (not prevention).** A leaked call never becomes a `tool_use` event, so PreToolUse can't see it. A Stop hook (`runtime/hooks/detect_malformed_toolcall.py`, marker `MALFORMED_TOOLCALL_GUARD`) detects it after the fact: if the last message ends in leaked closing markup it blocks the stop once and injects a re-emit-natively correction, capped at one extra turn via `stop_hook_active`.

---

## self-scheduled-wakeup-not-instruction

**Rule (see `config/CLAUDE.md`):** A self-scheduled wakeup (`ScheduleWakeup`/`CronCreate`/`/loop`) is a note to yourself, NOT a user instruction. Its only job is to resume the *already-agreed* task where you left off, never to authorize new scope. If the last genuine user message was a question or an unanswered decision, a wakeup does not answer it — wait for the human.

**Why.** These tools re-inject their `prompt` as a `user`-role message when they fire — in the transcript it is indistinguishable from a real user turn, with a `scheduled_task_fire` system line sitting right before it. The trap: in one 2026-05-31 session, after a wakeup re-fired the original request verbatim, the model read it as "the user is telling me to go ahead" and started implementing work the user had **not** approved (they were mid-decision on a question just asked).

**The check.** Every time a turn begins with a repeat of an earlier prompt, look for a `scheduled_task_fire` immediately before it — if present, that text came from a wakeup *you* set.

**Two corollaries.** (1) Never put a full task brief in a wakeup `prompt` as if re-issuing it; put a *resume marker* ("continue the surrogate-fix verification") so a re-fire can't read as new authorization. (2) Don't schedule a wakeup just because a tool's output looks slow — the harness re-invokes you when tracked work completes; a needless wakeup is what manufactured this false "user" turn.

---

## recommendation-not-approval

**Rule (see `config/CLAUDE.md`):** A recommendation is not approval; confirming a fact is not a "yes, do it". When a decision is genuinely the user's to make (you would have asked via `AskUserQuestion`), the answer must come *from the user*.

**Two traps, both observed live (2026-06-02 session, drew a profane rebuke).**

- **Tool-abandon ≠ work-authorization.** When the empty-`AskUserQuestion` Stop hook (or `CLAUDE.md`) tells you to "stop calling the tool, state a prose recommendation and continue," that means *abandon the tool and keep the conversation going* — NOT start editing files or taking irreversible/out-of-scope actions on the branch you recommended. State the recommendation, then **stop and wait** for the user to pick. The only exception is a trivial sub-choice *inside* work the user already approved, and even then name the assumption you're proceeding on.

- **"You guessed right" is not consent.** If you proposed a fact (a place name, a value, an interpretation) and the user replies "that's correct, but…" / "맞긴 한데…", they have *verified the fact*, not *authorized you to act on it*. Acting on it is the same scope violation as treating a question as an instruction (see `CLAUDE.md` Principle 3). Re-confirm what to *do* before doing it. The tell that you are about to make this mistake: you are about to write "진행합니다 / proceeding with the recommended option" right after the user only acknowledged a fact, with no explicit go-ahead for the action itself.

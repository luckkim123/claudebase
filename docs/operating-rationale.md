# Operating Rationale

The **why** behind the behavioral rules in `config/CLAUDE.md` → `## Operational Limits`.

`config/CLAUDE.md` is symlinked to `~/.claude/CLAUDE.md` and loaded into **every session on every machine and project**, so its bullets must stay short and action-only. This file is the opposite: it is **not loaded into any session**, so it is where the expensive context lives — issue numbers, hook markers, transcript evidence, incident dates, root-cause research. A rule in `CLAUDE.md` carries one `↪ rationale: operating-rationale.md#<anchor>` link to its section here.

**Contract for adding a rule** (mirrored in `config/CLAUDE.md` → `### Adding an Operational Limit`): the action goes in `CLAUDE.md` as one ≤350-char bullet; the *why* (issue numbers, hook design, transcript evidence, incident dates) goes here as a new `## <anchor>` section. Before writing a sentence, ask "is this an *instruction* or an *explanation of why*?" — explanations come here.

---

## complete-tool-payloads

**Rule (see `config/CLAUDE.md`):** Never emit a tool call missing a required field — e.g. `AskUserQuestion` with no `questions` array. Fill the full `questions` array *in the same call*, copying the prose you already wrote; never call-then-populate. `AskUserQuestion` is for genuine branch decisions only.

**Failure pattern.** You write the questions as prose, then fire the call with an empty `tool_input`. The harness rejects it (`InputValidationError: ... is missing`); the call is wasted, not harmful. This discipline is load-bearing and recurs under load: it fired **twice in one 2026-05-31 session even with the guard hook installed** (and once more in the 2026-06-05 session that produced this very file).

**Why the PreToolUse guard hook can't save you here.** A PreToolUse hook exists (`runtime/hooks/askuserquestion-guard.py`, marker `ASKUSERQUESTION_GUARD`) but **cannot catch the bare missing-`questions` case** — when a required top-level field is absent, the harness's own schema validator rejects the call BEFORE the hook's stdin is populated (proof: each recurrence surfaced a raw `InputValidationError`, never the hook's structured reason). The hook IS a genuine second line of defense for *delivered-but-malformed* payloads it can see — `questions: []`, wrong types, a question missing `options`(≥2)/`header`/`label`/`description`, or lone UTF-16 surrogates — denying them with a self-correction message.

**Root cause (2026-05-31, GitHub research).** Not a settings bug — a known model-side emission failure on large-context Opus 4.8 sessions (`anthropics/claude-code` #64150, still OPEN; Anthropic classifies the sibling `raw_arguments`/InputValidationError case as model-side and relies on self-correct, no CLI fix). The bare missing-`questions` case in *this* environment is NOT the permission-bypass family (#29547/#29733/#47114): the live `permissions.allow` has no `"*"` wildcard, `defaultMode` is `auto` (not bypass), and no skill declares `AskUserQuestion` in `allowed-tools` — those bypass triggers do not apply here, so do not chase them.

**Issue lineage + official triage (2026-06-12, GitHub research).** The same emission failure has a long, cross-repo paper trail confirming the model-side verdict — useful when a user asks "is this a known bug?": the **oldest report is `anthropics/claude-code` #895** (2025-04, *still OPEN*, "required parameter `content` is missing", a 30+ comment "+1" magnet); #5219 (2025-08, CLOSED) added the `raw_arguments`-wrapper variant via the Python SDK and drew the **explicit Anthropic verdict** — collaborator `ltawfik`: *"This is a model-side issue where Claude occasionally generates malformed tool call JSON (wrapping parameters in raw_arguments instead of individual fields), particularly with larger contexts — the CLI's validation correctly catches this and returns an error that allows Claude to self-correct on retry."* The identical text was cross-filed at `anthropics/claude-agent-sdk-python` #113 and closed stale (filed against CLI 1.0.68 / SDK 0.0.19; "resolved on current versions"). The **type-mismatch shape is not Write-specific** — the same "field arrived as `string`, schema wants `array`/`number`/`boolean`" failure recurs across every tool: Read `offset` (#30197), Edit `replace_all` (#31379), TodoWrite `todos` (#30955/#36548), Skill missing `skill` (#30893), AskUserQuestion `questions` (gsd-build/get-shit-done #743). Treat all of these as one family, not separate bugs.

**One variant WAS a real CLI bug and IS fixed — distinguish it.** The AskUserQuestion branch has a second, non-model cause that the `#64150` "no CLI fix" line does not cover: interactive tools listed in a skill's `allowed-tools` were being **silently auto-allowed**, returning *empty* answers so the model started guessing (gsd-build/get-shit-done #803/#844/#743). Anthropic fixed this in **Claude Code 2.1.69** ("Fixed interactive tools (e.g., AskUserQuestion) being silently auto-allowed when listed in a skill's allowed-tools"). So the triage is two-pronged: a *missing-field / wrong-type* emission is model-side (self-correct, `/compact`); an *empty-but-accepted* answer was the auto-allow bug (fixed — tell the user to update). This environment is unaffected by the latter (no skill declares `AskUserQuestion` in `allowed-tools`, per the Root-cause paragraph above).

**The remaining lever is behavioral + a Stop hook.** A second Stop hook backs the behavior (`runtime/hooks/askuserquestion_retry.py`, marker `ASKUSERQUESTION_RETRY_GUARD`): it reads `transcript_path`, counts how many empty-`questions` rejections sit CONSECUTIVELY at the tail, and escalates — streak 1–2 → block with a prose-first retry instruction; streak 3+ → block with an ABANDON instruction (stop calling the tool, state a prose recommendation, then WAIT for the user — abandoning the *tool* is not authorization to do the *work* on an unmade decision; see [recommendation-not-approval](#recommendation-not-approval)), capped at one block via `stop_hook_active` so a model that genuinely cannot emit the call never wedges the session. Verified on real transcripts: the empty calls were *scattered* (streak 1 each, broken by successful calls between them), not one 3-in-a-row runaway, so the retry stage handles the common case and abandon only fires on a true consecutive loop.

**Mitigation when context is large.** When the context has grown very large and empty calls recur, tell the user they can run `/compact` — shrinking the context is the only documented mitigation for the underlying #64150 model-side failure.

---

## no-leaked-toolcall-markup

**Rule (see `config/CLAUDE.md`):** A tool call must be a native `tool_use` block, never `antml:invoke`/`parameter` markup serialized as prose. Defenses: (1) emit the tool call with no preceding prose in the same message; (2) for special-char-heavy payloads, `Write` to a temp file first then run a simple command that reads it, instead of inlining the chars in a `bash -c` string; (3) split one large `Edit`/`Bash` into smaller single calls; (4) keep tool-call density low under a long/markup-dense context — one call per message when the session is large; (5) **once a session has leaked even once, `/clear` is the only reliable recovery** — the malformed turn poisons the rest of the session (see "self-poisoning" below), so in-session retries reproduce it.

**Why it is structurally possible (root cause, 2026-06-08 external research).** Claude's tool call is **not** a dedicated special token the way OpenAI models use; it is an RLHF-trained **XML-text pattern (ANTML)** — `<function_calls><invoke name="…"><parameter name="…">…</parameter></invoke></function_calls>` — emitted into the ordinary assistant token stream, which the **API layer** then parses *with regular expressions* into the structured `tool_use` block the client receives. The leaked Anthropic tool-use system prompt states outright: *"the output is not expected to be valid XML and is parsed with regular expressions."* Tool-call format compliance is **not** enforced by constrained/grammar-guided decoding (that is only applied when the explicit Structured Outputs beta `structured-outputs-2025-11-13` is enabled, and only to schema-defined response fields — never to tool-call XML). So there is **no mechanical barrier**: when the training signal for the format is diluted, the model can emit those same tokens as prose, in the wrong order, or with the `<function_calls>` wrapper missing, and nothing stops it. Sources: [ANTML leaked system prompt](https://github.com/jujumilk3/leaked-system-prompts/blob/main/anthropic-claude-api-tool-use_20250119.md), [Anthropic Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs), [tool-use overview](https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works).

**The two failure forms.** *Type A — leaked XML in the text channel*: the model writes literal `<invoke>`/`antml:` markup (sometimes prefixed by a stray `court`/`count` token) as prose; the tool never runs; harness says "malformed and could not be parsed." *Type B — missing `tool_use` block*: the turn ends with `stop_reason: tool_use` but the content has only a thinking/text block, no (or truncated) `tool_use`. Both surface the same parse error. (anthropics/claude-code [#60584](https://github.com/anthropics/claude-code/issues/60584), [#64418](https://github.com/anthropics/claude-code/issues/64418) for A; [#64235](https://github.com/anthropics/claude-code/issues/64235), [#61133](https://github.com/anthropics/claude-code/issues/61133) for B.)

**Self-poisoning is why it repeats and why `/clear` is the cure.** Because the format is learned in-context XML text, one malformed `<invoke>` in history acts as a few-shot example: every subsequent tool call copies the broken pattern, so the harness's automatic retry — which replays the same poisoned context — also fails. A fresh session is the only documented escape. ([#62344](https://github.com/anthropics/claude-code/issues/62344).)

**Triggers (the aggravating conditions, ranked by this environment's evidence).** (a) **CLI version** — a regression introduced in the 2.1.150 line; community bisection put the peak at 2.1.158 ([#64176](https://github.com/anthropics/claude-code/issues/64176)), but *this* environment's own transcripts are worse on newer builds (see below). (b) **Markup-dense context** — loading long SKILL.md files full of `<result>` blocks, heredocs, and `<invoke>`-shaped examples dilutes the model's format control. (c) **Long context / token pressure** — format instructions near the prompt top lose attention as the session grows ("lost in the middle"); LongFuncEval ([arXiv 2505.10570](https://arxiv.org/pdf/2505.10570)) shows function-call accuracy drops as tool-result volume grows. (d) **High, heterogeneous tool composition** — many MCP servers + ToolSearch + multiple calls in one turn ([#64418](https://github.com/anthropics/claude-code/issues/64418)). (e) **Special-char payloads** — unescaped newlines/control chars, angle brackets, and CJK in arguments break the JSON/XML envelope ([#64658](https://github.com/anthropics/claude-code/issues/64658) notes CJK correlation; [goose #2892](https://github.com/block/goose/issues/2892) for control chars). (f) **Prose before the call** ([#60584](https://github.com/anthropics/claude-code/issues/60584)). (g) **Third-party API proxies** — multiple #895 reporters (e.g. `bearyue`) saw the failure *only* through non-official API gateways and never on the first-party Anthropic endpoint, implicating proxies that re-serialize the tool-use envelope; if a user hits this on a relay/proxy, have them confirm against the official endpoint before chasing a model or CLI cause.

**CLI-side vs harness-side: the verdict (evidence-based, not inferred).** The root cause is **Claude/Claude Code (model + CLI version)**; the installed harnesses (OMC, superpowers, omx) are **amplifiers, not the cause** — they manufacture the trigger conditions (b)(c)(d)(e), but removing them does not remove the underlying ANTML fragility or the CLI regression. Evidence from this very environment's transcripts (`~/.claude/projects/-workspace/*.jsonl`, counted 2026-06-08): **~114 malformed events total**, bucketed by CLI version —

| CLI version | malformed | assistant turns | rate |
|---:|---:|---:|---:|
| 2.1.150 | 7 | 7811 | 0.09% |
| 2.1.158 | 0 | 2384 | 0% |
| 2.1.163 | 4 | 2071 | 0.19% |
| 2.1.167 | 21 | 5303 | 0.40% |
| **2.1.168** | **62** | **3215** | **1.93%** |

The current build 2.1.168 is the **worst** (~1.93%), a *different and more severe* profile than the public #64176 bisection (which peaked at 2.1.158) — i.e. a later-build variant. The two worst sessions were both heavy-harness: `3ce4…` (43 events; exp-analyze ×200 + team ×54 skills, **1120 MCP calls**) and `f44…` (20 events; TDD ×170 + external-context). In `3ce4…`, **25 assistant text blocks contained literal `<invoke>`/`antml:`/`<function_calls>` markup** — direct Type-A proof, and the concrete reason that session "went broken" mid-run. Single-file coding sessions in the same project show near-zero events; the harness-orchestrated, MCP-dense, long sessions carry essentially all of them. So: harness usage is the strongest *predictor*, the CLI version is the strongest *cause*, and they compound.

**Mechanism research source notes.** Six layered mechanisms (ANTML-is-text, in-context poisoning, integration-layer serialization bugs, special-char envelope breakage, long-context format decay, no constrained decoding) are captured in `/tmp/toolcall-leak-facet1.md` and `/tmp/toolcall-leak-facet2.md` from the 2026-06-08 external-context run; the durable copy of the verdict lives here.

**Detection (not prevention).** A leaked call never becomes a `tool_use` event, so PreToolUse can't see it. A Stop hook (`runtime/hooks/detect_malformed_toolcall.py`, marker `MALFORMED_TOOLCALL_GUARD`) detects it after the fact: if the last message ends in leaked closing markup it blocks the stop once and injects a re-emit-natively correction, capped at one extra turn via `stop_hook_active`. The hook cannot un-poison the session, though — when leaks recur it should escalate to advising `/clear` rather than another in-session retry.

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

---

## deletion-safety

**Rule (see `config/CLAUDE.md`):** Destructive ops go through a recoverable path. Delete → recycle bin, not permanent erase; move = `mv` → verify destination → only then delete source. The rule is *"avoid irreversible loss,"* not *"always run `trash`"* — use the safest path the environment offers.

**Why the environment matters.** There is no single delete command that is safe everywhere, so the rule is environment-adaptive rather than one fixed tool:

- **Recycle-bin per platform.** macOS: `trash` (else move into `~/.Trash`). Linux desktop: `gio trash` / `trash-cli`. **No trash available** (Docker / CI / minimal): before `rm`, confirm a copy exists elsewhere *and* get the user's explicit "this is permanent" approval. In a git repo, `git rm` + commit is itself recoverable.
- **The move-then-delete sync-lag trap.** Never `rm` the source in the same breath as an `mv`. On sync-backed filesystems (iCloud/Drive) the move can lag — files that look moved are still uploading — so a same-breath delete of the source loses them. Always `find`/`ls` the destination to confirm the files landed *before* deleting the source.

## multisession-git

**Rule (see `config/CLAUDE.md`):** When several Claude/tmux sessions run on one repo, isolate — don't negotiate. Default to one `git worktree` per session; split a shared task by disjoint file ownership up front; only if a shared tree is unavoidable, gate writes with a PreToolUse `flock`/`O_EXCL` lock (contender yields and retries). Keep to 2–4 parallel sessions.

**Why isolation, not runtime negotiation.** Git collisions (overwrites, `.git/index.lock` contention) come from *sharing one working tree*, not from a missing coordinator. Pausing sessions to "talk out" a conflict is the consensus-hard-part the industry deliberately avoids — empirically 95–100% deadlock at 3 agents, and adding a comms channel *worsens* it. So the fix is structural separation:

- **Worktree default.** `claude --worktree <name>` gives each session its own branch, index, and files → file conflicts become structurally impossible; real overlaps surface calmly at merge/rebase, not live at runtime.
- **Disjoint ownership** for a split task: "session A owns `/api`, B owns `/ui`", claimed before editing, never negotiated after colliding.
- **Shared-tree fallback:** a PreToolUse `flock`/`O_EXCL` lock; the contender exits 2 and retries (yield, not negotiate). `session_id` is already in every hook's stdin JSON.
- **Caps & gotchas.** 2–4 parallel sessions (5+ hits rate limits, review breaks down); worktrees do *not* isolate runtime (ports/DBs/caches) and fragment `~/.claude/projects/` history per path. Never carry coordination state in commit trailers — they're unreadable at write-time.

---

## worktree-index-boundary

**Rule (see `config/CLAUDE.md`):** In a linked worktree a gitignored index is absent, not empty. Locate indexes and state from `dirname $(git rev-parse --git-common-dir)`, never `--show-toplevel`.

**One boundary, two opposite failures.** `git worktree add` copies tracked files and nothing else, so `.gitignore` decides which half of the harness follows a session into a worktree — and each half fails in the opposite direction:

| | Follows the worktree? | Failure |
|:---|:---|:---|
| `.omp/`, a tracked `.graphify/` | yes, as branch content | append-only state (e.g. `.omp/secretary/ledger.jsonl`) forks per branch and collides at merge |
| `.code-review-graph/`, `.tokensave/`, `.omc/` | no | the index is simply missing, and a query answers 0 results |

The second half is the dangerous one: an absent index is indistinguishable from a healthy one that found nothing — the same silent-success class `templates/project-code-review-graph.md` documents at length. Worse, an MCP query that omits `repo_root` *creates* an empty `graph.db` at its cwd and answers `status: "ok"`, so the worktree ends up holding a plausible-looking 0-node index.

**Why `--git-common-dir`.** The common dir is shared by every worktree of a repo, so its parent is the main checkout — where the ignored indexes actually live. Outside a worktree the two forms name the same directory, which is what makes the correction safe to ship: a single-checkout user sees no behaviour change at all.

**The trap inside the fix.** Comparing the two git dirs as raw strings reports a worktree where there is none. Measured on git 2.39.5: from a subdirectory of an ordinary main checkout, `--git-dir` prints an absolute path while `--git-common-dir` still prints `../.git`. Both must be absolutised before the compare. Doing so also keeps `--separate-git-dir` correct for free — there the two resolve to the same external directory, the branch is skipped, and `--show-toplevel` (which handles that layout) stands. `tests/hooks/test_worktree_root.py` pins all of it, including the empty guard: without it, `cd "/.."` outside a repo silently yields `/`.

**What claudebase does about it.** `runtime/hooks/graph-refresh.sh` (canonical copy of the comment), `runtime/hooks/graph-offer.sh` and `runtime/bin/graph-init.sh` all start from `--show-toplevel` and correct only for a linked worktree; graph-offer additionally anchors its once-per-project marker in the common dir. `installer/scripts/render_settings.py` resolves `env.OMC_STATE_DIR` at render time so `.omc/` state outlives `git worktree remove` — it cannot be tracked, because `~`/`$HOME` do not expand in the `env` block and OMC joins the value verbatim, so a literal `~` would create a directory *named* `~`.

**What it does not fix.** `graphify-guard.sh` needed nothing — it already walks ancestors for `graph.json`. tokensave resolves its own repo inside the binary and cannot be redirected from here, so a worktree gets no note index; do not paper over that by auto-indexing, which is slow and, on corpora with long non-ASCII paths, a known crash. `claude-mem` keys observations per path, so a worktree's history is separate. Claude Code's own auto-memory is the happy exception — it already resolves to the main repo.

**Where this came from.** Measured 2026-08-17 on an Obsidian vault opened through an IDE that creates one worktree per workspace. Three checkouts of the same repo were live; both worktrees held a 0-node `graph.db` while the real 12.9 MB index sat in the main checkout, and that project's `CLAUDE.md` instructed every session to consult the graph before grepping. Nothing errored. The IDE is incidental — `claude --worktree <name>`, which `#multisession-git` recommends as the default, reproduces it exactly.

---

## objective-verbatim

**Rule (see `config/CLAUDE.md`):** Write the requester's objective into the plan verbatim before designing. Every decision to hold or change something argues against *that* line. Redefining the objective mid-document is a re-ask, not an edit — and anything your own analysis marks as needing a decision belongs to the user.

**The incident (2026-08, `dgx-final-scaleup`, ~3 days of a reserved DGX).** The user stated repeatedly and emphatically, during planning, that the coupled parameters must be identified and the *best-performing* setting found. The plan that resulted told the executing session: "Change NOTHING except `num_envs` and `max_iterations`."

**The analysis was not skipped — that is the whole point.** The plan carried a section literally titled `## 3b. Parameter coupling under scale-up — derived from code, not asserted`, with three tiers, and its Tier 2 named `step_interval` and predicted the consequence exactly: *"si=250: box saturates at iter 7748, then 12,252 iterations at fixed maximum difficulty."* It even offered the alternative: *"if the user prefers shape (b), it is a one-line change."* The prediction came true (saturation at 7250) and the run spent ~11× the compute of its 4096-env reference to land 2% away from it.

Three failures compounded, and only the first two are avoidable by discipline alone:

- **The objective was never transcribed.** A grep of the 535-line plan finds no statement of what the user asked for. Instead §0b silently *redefined* what the run was FOR. With no original to compare against, the redefinition read as a clarification rather than a substitution.
- **So the decision was resolved against the wrong criterion.** Tier 2 chose shape (a) partly because it "keeps the run a clean ONE-variable dose-response" — measurement readability. That is a legitimate goal, but it was not *the user's* goal, and nothing in the document forced the conflict into the open. **A substituted objective makes every downstream trade look correct.**
- **A decision the plan itself called necessary was classified as the program's.** The section titled "Open questions for the user (decisions this program cannot make)" listed nine items; `step_interval` was not among them. Its escape hatch lived inside a table cell in a 535-line document, phrased as a conditional that assumed the user would read that cell and object.

Then the handoff compressed six reasoned dispositions into six prohibitions ("`step_interval` stays 250"), which removed the receiving session's ability to see that any of them had ever been a choice. Carry a held decision as **decision / alternative considered / why held / what it costs**, never as a bare "stays".

**Mechanized where possible.** `omx program-lint` (oh-my-experiments v0.11.0) gates exactly this for experiment plans: objective present as a blockquote, a canonical decision section, every `[DECISION-REQUIRED: <slug>]` escalated into it, and a stated predicted outcome. It reports four findings on the plan above. But a lint cannot catch *"the user said it and nobody wrote it down"* — an objective section filled with the wrong goal passes. That part is discipline, which is why the rule lives here too.

---

## summary-layer-follows-body

**Rule (see `config/CLAUDE.md`):** Fix the body, fix its summary in the same edit. Every pointer layer that summarizes content — a memory's frontmatter `description` and its `MEMORY.md` index line, a README's table of contents, a doc's staleness banner — is what recall and routing actually read, so a stale summary outranks a correct body.

**Why the summary is the more dangerous half.** Retrieval does not read the body to decide relevance; it reads the summary. An auto-memory file is selected for injection by its `description`, and `MEMORY.md` is the index loaded into every session — the body is consulted only *after* the summary has already won or lost the ranking. So a body that says "this was retracted" and a description that still asserts the retracted conclusion do not average out. The description wins, and it wins silently: the retraction is invisible precisely in the moment the wrong conclusion is handed to a new session.

**The incident (2026-08, obsidian vault).** A memory's body carried a struck-through retraction of its own headline finding, dated the day the retraction was measured. Its frontmatter `description` and its `MEMORY.md` index line kept the pre-retraction conclusion for about ten days, until a later session noticed and corrected both (recorded in that vault's `3_Archive/session_prompts/2026-08-14-harness-ownership-gap-prompt.md` §3 P4). Nothing errored. The body was, the whole time, correct.

**It is one instance of a general shape.** The same day surfaced three siblings: a project rules file still naming a directory that had been renamed away; a handoff quoting a canonical plan's line count from a revision that had since grown by ~120 lines; a routing pointer describing a layout that no longer existed. In each case the *source* was right and the *pointer to it* was wrong, and in each case the pointer is what the next reader consumed. **Summaries and pointers outlive the thing they summarize** — that is the failure family, and it is why the rule says "in the same edit" rather than "eventually".

**What this does not license.** It is not an instruction to write summaries defensively, to hedge them, or to duplicate the body into them — that produces a second document rotting on its own schedule. The lazy form is the correct one: if a summary cannot be kept current, delete it rather than leave it. A missing pointer sends the reader to the source; a wrong one does not.

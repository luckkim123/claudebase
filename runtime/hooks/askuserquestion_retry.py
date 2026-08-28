#!/usr/bin/env python3
"""Recover from an empty AskUserQuestion call by forcing an immediate retry.

Failure mode this hook addresses (diagnosed 2026-05-31 from transcript
9d4b2a74 — the SAME session that proved PreToolUse cannot catch this):

  The model emits `AskUserQuestion` with no `questions` array (tool_input is
  empty). The harness's BUILT-IN input-schema validator rejects it with
  `InputValidationError: 'questions' is missing` and the turn is wasted.

Why this is a Stop hook and NOT PreToolUse (verified, not assumed):
  A PreToolUse hook (askuserquestion-guard.py) was already registered for
  AskUserQuestion. A logging probe inserted into it on 2026-05-31 produced
  NO log entry when an empty call was made — proof that the harness's schema
  validator runs BEFORE PreToolUse and rejects the missing-`questions` call
  before any hook fires. PreToolUse is structurally too late for this case;
  the guard hook can only catch `questions: []` (empty array) and lone
  surrogates, which DO reach it. The only enforceable lever for a fully
  empty call is POST-HOC, exactly like detect_malformed_toolcall.py: after
  the turn, inspect what happened and block the Stop to force a retry.

How the empty call is observed (verified from transcript 9d4b2a74):
  The failure lands as a `tool_result` content block with `is_error: true`
  whose text contains the harness error
  `InputValidationError: AskUserQuestion failed ... 'questions' is missing`
  (line 836: is_error=True). It does NOT appear in the assistant text tail,
  so the detect_malformed approach (last_assistant_message) cannot see it.
  We therefore read `transcript_path` (an official Stop-hook stdin field per
  code.claude.com/docs/en/hooks) and scan the tail of the JSONL for that
  exact error.

Escalation strategy (revised 2026-05-31 after transcript evidence):
  A single retry was too weak. Real transcripts show the empty call recurring
  many times in one session (d6d2baa3: 38 rejections; 9895ae10: 34) because
  the old hook retried ONCE then let any further empty call pass. On a
  large-context Opus 4.8 session this is a known model-side emission failure
  (claude-code #64150) that one retry does not reliably escape. So we now
  count how many empty rejections sit CONSECUTIVELY at the transcript tail and
  escalate:
    streak 1-2 -> REASON_RETRY  (retry, but enforce prose-first discipline)
    streak 3+  -> REASON_ABANDON (stop calling the tool; state a prose
                  recommendation and WAIT for the user — abandoning the tool
                  does not authorize doing the work on an unmade decision)
  A successful retry breaks the streak (next Stop sees streak 0 -> allow), so
  the retry stage self-terminates; the abandon stage is capped at one block
  via `stop_hook_active` so a model that simply cannot emit the call never
  wedges the session.

GATE verification (reused from detect_malformed_toolcall.py, live v2.1.158):
  - `decision: "block"` + `reason` is fed back to the model next request
    (detect_malformed proved this works — its block reason changed model
    output). Official docs do not document the injection, but the sibling
    hook is live proof on this machine.
  - `stop_hook_active` is present at runtime (undocumented but used by
    detect_malformed); at the abandon stage it caps intervention at one turn.

Discipline (mirrors detect_malformed_toolcall.py / askuserquestion-guard.py):
  - Never block on a hook bug: any exception / malformed stdin / unreadable
    transcript -> exit 0, allow the stop. A detector must not wedge a session.
  - Always exit 0; the decision travels in the JSON body, not the code.
  - Log every detection to .omc/logs/ for telemetry.

Hook event: Stop (no matcher)
Idempotent marker in the settings command field: ASKUSERQUESTION_RETRY_GUARD
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import hooklog  # noqa: E402
except Exception:  # fail-open — 계측 헬퍼가 훅을 죽여선 안 된다
    class hooklog:  # type: ignore  # noqa: N801
        @staticmethod
        def state_root(cwd):
            return cwd or "."

# The exact harness error text for a fully empty AskUserQuestion call. Both
# tokens must be present so we never trip on an unrelated validation error.
_ERR_TOOL = "AskUserQuestion"
_ERR_MISSING = "questions"
_ERR_PHRASE = "is missing"  # "The required parameter `questions` is missing"

# Streak 1-2: the call just failed (once or twice). Make it retry, but force
# the prose-first discipline that prevents the empty payload in the first place.
REASON_RETRY = (
    "Your last AskUserQuestion call was REJECTED by the harness: the "
    "`questions` array was missing (you emitted the call with an empty "
    "input). The turn was wasted. A PreToolUse hook cannot stop this — the "
    "schema validator runs first — so you must not let it happen again.\n"
    "Re-issue the call correctly NOW:\n"
    "1. Write the questions as prose in your reply body FIRST — each "
    "question text, its header (<=12 chars), its 2-4 options "
    "(label + description), and multiSelect true/false. The tokens must "
    "exist in your output before they can go in the tool call.\n"
    "2. Only after that prose exists, call AskUserQuestion with the SAME "
    "content in the `questions` array. Every question object needs all four "
    "fields: question, header, options (>=2), multiSelect.\n"
    "If empty calls keep recurring, the context has likely grown large — "
    "tell the user they can run /compact, the only documented mitigation for "
    "the underlying model-side emission failure.\n"
    "3. If there is an obvious recommended choice, do NOT call "
    "AskUserQuestion at all — state the recommendation in prose and STOP "
    "THERE for the user to decide. 'Proceed' here means continue the "
    "conversation, NOT start doing the work: do not begin edits or file "
    "changes on a decision the user has not actually made. A user merely "
    "confirming a FACT you guessed (\"that's correct, but...\") is NOT "
    "approval to act on it. AskUserQuestion is for genuine branch decisions "
    "that are the user's to make; treating your own recommendation as their "
    "answer is exactly the failure this guard exists to prevent."
)

# Streak 3+: retrying has not worked. On a large-context Opus session the
# empty-payload emission is a known model-side failure mode (claude-code
# issue #64150) that repeated retries do NOT reliably escape — one observed
# session looped 38 times. So STOP retrying the tool and route around it:
# state the recommendation in prose, then WAIT for the user to decide.
# Abandoning the TOOL is not authorization to do the WORK — on a decision the
# user has not made, present the recommendation and stop; do not start edits
# or irreversible actions. The user keeps a real choice and the session is no
# longer wedged.
REASON_ABANDON = (
    "Your AskUserQuestion call has now failed with a missing `questions` "
    "array THREE OR MORE TIMES IN A ROW. Retrying the tool is not working — "
    "on a large-context session this is a known model-side emission failure "
    "(claude-code #64150) that more retries will not reliably escape. "
    "STOP calling AskUserQuestion for this decision.\n"
    "Instead, RIGHT NOW:\n"
    "1. In your normal reply text, write out the choice you were going to "
    "ask about, list the options in prose, and state which one you "
    "RECOMMEND and why.\n"
    "2. Then STOP and wait for the user to decide. Abandoning the TOOL does "
    "NOT authorize doing the WORK: presenting a recommendation is not the "
    "same as getting approval. Do NOT start edits, file changes, or any "
    "irreversible/out-of-scope action on a branch the user has not actually "
    "chosen. A user confirming a fact you guessed (\"yeah that's right, "
    "but...\") is NOT a 'yes, proceed'. The ONLY case where you may continue "
    "without waiting is a trivial sub-choice INSIDE work the user already "
    "approved — and even then, state which assumption you are proceeding on "
    "so they can correct it. Do NOT call AskUserQuestion again for this "
    "decision — the user can read your recommendation and reply.\n"
    "3. If the context has grown very large, consider telling the user they "
    "can run /compact to reduce the malformed-call rate going forward."
)


# How many physical JSONL lines from the tail to inspect. Raised from 40 to
# 200 ([1]): a single busy turn can emit dozens of tool_result + thinking lines,
# pushing the empty-call rejection past a 40-line window so the detector misses
# it (streak 0 -> no recovery). 200 covers a very busy turn while bounding the
# read on a huge transcript to a few ms.
_TAIL_MAX_LINES = 200


def _tail_lines(transcript_path: str, max_lines: int = _TAIL_MAX_LINES) -> list:
    """Return parsed JSONL objects from the last `max_lines` of the transcript,
    oldest-first. Best-effort; returns [] on any problem. (Returns whole line
    objects, not just tool_result blocks, so the streak counter can also see
    genuine human turns that must break a streak — see [2].)"""
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except (OSError, UnicodeDecodeError):
        return []
    objs = []
    for line in lines[-max_lines:]:
        try:
            objs.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return objs


def _line_tool_results(obj: dict) -> list:
    """The tool_result blocks carried by one transcript line (possibly empty)."""
    content = (obj.get("message") or {}).get("content")
    if not isinstance(content, list):
        return []
    return [b for b in content
            if isinstance(b, dict) and b.get("type") == "tool_result"]


def _is_string_content_empty_error(obj: dict) -> bool:
    """True iff this user-role line carries the empty-call rejection as BARE
    STRING content (no block list). `_line_tool_results` only sees list-form
    blocks, so this catches the string-form rejection the harness also emits."""
    msg = obj.get("message") or {}
    if msg.get("role") != "user":
        return False
    content = msg.get("content")
    if not isinstance(content, str) or not content:
        return False
    return (_ERR_TOOL in content and _ERR_MISSING in content
            and _ERR_PHRASE in content)


def _is_genuine_human_turn(obj: dict) -> bool:
    """True iff this line is a real user turn (human typed something), NOT a
    tool_result container. The harness records tool rejections on user-role
    lines too; those are NOT human turns. A line is a human turn when its role
    is user and it carries no tool_result — as a list of blocks OR as bare
    string content. The harness sometimes records a rejection with `content` as
    a plain string (see test_string_content_form_is_flattened); that string is a
    tool error, not a typed message, so a non-empty string content must NOT
    count as a human turn (else a string-form rejection would wrongly break the
    streak and stop a real loop from escalating)."""
    msg = obj.get("message") or {}
    if msg.get("role") != "user":
        return False
    if isinstance(msg.get("content"), str) and msg.get("content"):
        return False  # bare-string content = a tool rejection, not a human turn
    return not _line_tool_results(obj)


def _result_text(block: dict) -> str:
    """Flatten a tool_result's content to a single string."""
    c = block.get("content", "")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return " ".join(
            part.get("text", "") for part in c if isinstance(part, dict)
        )
    return ""


def _is_empty_askuserquestion_error(block: dict) -> bool:
    """True iff this tool_result is the harness rejection of an empty
    AskUserQuestion call (missing `questions`)."""
    if not block.get("is_error"):
        return False
    text = _result_text(block)
    return _ERR_TOOL in text and _ERR_MISSING in text and _ERR_PHRASE in text


def _count_consecutive_empty_calls(transcript_path: str) -> int:
    """Count how many empty-AskUserQuestion rejections sit at the very tail of
    the transcript, CONSECUTIVELY, newest-first. A non-empty-call tool_result
    (any successful or unrelated tool) breaks the streak — that boundary is
    what distinguishes 'currently looping' from 'an older, already-recovered
    failure earlier in the session'.

    A genuine human turn between two empty calls ALSO breaks the streak ([2]):
    if the user actually answered, the next empty call is a fresh first failure,
    not a continuation of the runaway — otherwise a user who replies between two
    unrelated empty calls is wrongly escalated toward abandon.

    Returns:
      0  -> the last tool_result is NOT an empty-call rejection (allow stop)
      1  -> exactly one empty call at the tail (first failure)
      2  -> two in a row (the model already retried once and failed again)
      3+ -> runaway; we will force AskUserQuestion to be abandoned entirely
    """
    objs = _tail_lines(transcript_path)
    if not objs:
        return 0
    # Flatten the tail into a time-ordered sequence of markers, oldest-first:
    #   "empty"  -> a tool_result that is the empty-call rejection
    #   "other"  -> any other tool_result (success / unrelated tool)
    #   "human"  -> a genuine human turn (breaks a streak, see [2])
    # Assistant text / thinking lines are transparent and contribute no marker.
    # Each tool_result BLOCK is its own marker (a single line may carry several),
    # preserving the per-block ordering the original detector relied on.
    seq = []
    for obj in objs:
        results = _line_tool_results(obj)
        if results:
            for b in results:
                seq.append("empty" if _is_empty_askuserquestion_error(b) else "other")
        elif _is_string_content_empty_error(obj):
            # A rejection recorded with bare-string content (no block list) —
            # still an empty-call failure, must stack like a list-form one.
            seq.append("empty")
        elif _is_genuine_human_turn(obj):
            seq.append("human")
    streak = 0
    for marker in reversed(seq):
        if marker == "empty":
            streak += 1
        else:
            break  # "other" tool_result OR a genuine human turn breaks the streak
    return streak


# A session that has racked up this many AskUserQuestion failures of ANY shape
# (guard denies + missing-`questions` rejections) is clearly looping across
# shapes; escalate straight to abandon even if the tail streak is only 1-2 ([3]).
_SESSION_ABANDON_THRESHOLD = 5

# The two shared logs that together record every AskUserQuestion failure in a
# session: the PreToolUse guard's denies and this Stop hook's own rejections.
_GUARD_LOG = "askuserquestion_guard.jsonl"
_RETRY_LOG = "askuserquestion_retry.jsonl"


def _count_log_records(path: str, session_id) -> int:
    """Count records in one jsonl whose session_id matches. Best-effort -> 0."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except (OSError, UnicodeDecodeError):
        return 0
    n = 0
    for line in lines:
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("session_id") == session_id:
            n += 1
    return n


def _session_failure_count(cwd: str, session_id) -> int:
    """Total AskUserQuestion failures recorded for this session across BOTH the
    guard log (empty-array / partial / surrogate denies) and the retry log
    (missing-`questions` rejections). Cross-shape signal for [3]. session_id
    None -> 0 (cannot attribute, so do not escalate)."""
    if not session_id:
        return 0
    log_dir = os.path.join(hooklog.state_root(cwd), ".omc", "logs")
    return (_count_log_records(os.path.join(log_dir, _GUARD_LOG), session_id)
            + _count_log_records(os.path.join(log_dir, _RETRY_LOG), session_id))


def _last_blocked_streak(cwd: str, session_id) -> int | None:
    """The `streak` from the most recent retry-log record we actually BLOCKED on
    for this session, or None if we have never blocked this session.

    This is the memory the loop guard ([5], 2026-06-12 deadlock fix) needs to
    tell two re-fire cases apart — both arrive with `stop_hook_active=True`, so
    that flag alone cannot distinguish them:
      * model OBEYED the prose-stop instruction (REASON_RETRY step 3) -> it did
        NOT re-call the tool -> no new empty marker at the tail -> the streak is
        UNCHANGED from when we last blocked. Releasing the stop here is correct.
      * model re-called the tool and it failed AGAIN -> a new empty marker -> the
        streak GREW past what we last blocked on. Keep blocking (-> abandon at 3).
    Best-effort: any read problem -> None (treated as 'no prior block')."""
    if not session_id:
        return None
    path = os.path.join(hooklog.state_root(cwd), ".omc", "logs", _RETRY_LOG)
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except (OSError, UnicodeDecodeError):
        return None
    last = None
    for line in lines:
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("session_id") == session_id and rec.get("blocked") is True:
            s = rec.get("streak")
            if isinstance(s, int):
                last = s
    return last


def _log(cwd: str, record: dict) -> None:
    """Best-effort telemetry. Never raises."""
    try:
        log_dir = os.path.join(hooklog.state_root(cwd), ".omc", "logs")
        os.makedirs(log_dir, exist_ok=True)
        path = os.path.join(log_dir, "askuserquestion_retry.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001, S110 — a raising hook blocks the user's turn; failing open is the contract
        pass


def _block(reason: str) -> int:
    sys.stdout.write(json.dumps({"decision": "block", "reason": reason}))
    return 0


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0  # never block on a hook bug

    if payload.get("hook_event_name") != "Stop":
        return 0

    transcript_path = payload.get("transcript_path")
    if not isinstance(transcript_path, str) or not transcript_path:
        return 0  # no transcript to inspect -> allow stop

    streak = _count_consecutive_empty_calls(transcript_path)
    if streak == 0:
        return 0  # last tool_result is not an empty-call rejection -> allow

    cwd = payload.get("cwd") or os.getcwd()
    session_id = payload.get("session_id")
    already_firing = payload.get("stop_hook_active") is True

    # Cross-shape session signal ([3]): how many AskUserQuestion failures of ANY
    # shape this session has logged so far (guard denies + our own rejections).
    # The current tail streak does not yet include THIS rejection's log write
    # (we log below), so a session already at/over threshold is genuinely looping.
    session_failures = _session_failure_count(cwd, session_id)

    # Decide the intervention. Abandon when EITHER the tail is a 3+ runaway OR the
    # session has crossed the cross-shape failure threshold (looping across empty
    # / empty-array / partial shapes, which a tail-only streak cannot see).
    #   else 1-2 at the tail -> retry with prose-first discipline (REASON_RETRY)
    # The current in-flight failure is not yet written to either log (the retry
    # log is appended below, after this decision), so +1 represents it — without
    # it, a session at exactly threshold-1 prior failures would never escalate.
    if streak >= 3 or (session_failures + 1) >= _SESSION_ABANDON_THRESHOLD:
        reason, mode = REASON_ABANDON, "abandon"
    else:
        reason, mode = REASON_RETRY, "retry"

    # Loop guard ([5], 2026-06-12 deadlock fix). `stop_hook_active` is True only
    # when THIS Stop is the re-fire caused by our own previous block. On a re-fire
    # there are exactly two model behaviours, and we must release the stop for one
    # of them or the session deadlocks:
    #
    #   (A) the model OBEYED REASON_RETRY step 3 ("if there's an obvious
    #       recommendation, do NOT call the tool — state it in prose and STOP").
    #       It wrote prose and did NOT re-call AskUserQuestion. So NO new empty
    #       marker reached the tail and the streak is UNCHANGED from the value we
    #       last blocked on. The old guard only released the *abandon* stage, so a
    #       streak that stayed at 1-2 blocked forever — the model followed the
    #       instruction yet never satisfied the release condition. RELEASE here.
    #
    #   (B) the model re-called the tool and it failed AGAIN. A new empty marker
    #       hit the tail and the streak GREW past what we last blocked on. That is
    #       a genuine continued loop: keep blocking so it escalates to abandon at
    #       3. This is the path test_retry_stage_keeps_blocking_when_streak_grew
    #       and the streak 2->3 abandon escalation depend on — do NOT break it.
    #
    # We tell (A) from (B) with the streak we last BLOCKED on (from our own log):
    # current streak <= last-blocked streak  => did not grow  => (A) release.
    # current streak >  last-blocked streak  => grew          => (B) keep blocking.
    # No prior block for this session (None) => this is the FIRST block for this
    # streak even though some other hook re-fired the Stop => block once.
    blocked = True
    if already_firing:
        # abandon stage stays log-independent: a model at streak 3+ that re-fires
        # our own block has already proven it cannot emit the call, so cap at one
        # block whether or not a prior streak was logged. (Pre-2026-06-12 guard;
        # kept so the abandon cap never depends on session_id/log availability.)
        if mode == "abandon":
            blocked = False
        elif not session_id:
            # retry stage with NO session_id: the streak memory is keyed by
            # session_id, so we cannot tell the prose-stop case from a grown
            # streak on this re-fire. Release rather than risk the deadlock — the
            # abandon cap (streak 3+) still fires log-independently, so a true
            # runaway is unaffected. (Stop-hook stdin normally carries session_id;
            # this is defensive for the case it does not.)
            blocked = False
        else:
            # retry stage ([5] deadlock fix): release iff the streak did NOT grow
            # past what we last blocked on — i.e. the model obeyed the prose-stop
            # instruction instead of re-calling the tool. A grown streak is a
            # genuine continued loop and must keep blocking toward abandon.
            last_blocked = _last_blocked_streak(cwd, session_id)
            if last_blocked is not None and streak <= last_blocked:
                blocked = False  # (A) model stopped in prose; streak did not grow

    _log(
        cwd,
        {
            "session_id": session_id,
            "signal": "empty_askuserquestion",
            "streak": streak,
            "session_failures": session_failures,
            "mode": mode,
            "stop_hook_active": already_firing,
            "blocked": blocked,
        },
    )

    if not blocked:
        return 0

    return _block(reason)


if __name__ == "__main__":
    sys.exit(main())

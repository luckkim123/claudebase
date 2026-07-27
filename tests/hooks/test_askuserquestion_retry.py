"""Tests for runtime/hooks/askuserquestion_retry.py (empty-call Stop hook).

Drives the hook end-to-end via subprocess (real stdin->stdout JSON contract)
and builds throwaway transcript JSONL files matching the EXACT shape observed
in transcript 9d4b2a74 (line 836): a tool_result block with is_error=True
whose text carries `InputValidationError: AskUserQuestion ... 'questions' is
missing`. The empty call lands in a tool_result, NOT the assistant text tail,
which is why this hook reads transcript_path instead of last_assistant_message.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / "runtime" / "hooks" / "askuserquestion_retry.py"

# The exact harness rejection text for an empty AskUserQuestion call.
EMPTY_ERR = (
    "<tool_use_error>InputValidationError: AskUserQuestion failed due to the "
    "following issue:\nThe required parameter `questions` is missing"
    "</tool_use_error>"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("askuserquestion_retry", HOOK_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_transcript(tmp_path: Path, blocks_tail, name="transcript.jsonl") -> str:
    """Write a minimal JSONL transcript whose LAST user line carries the given
    tool_result blocks. Returns the path."""
    lines = [
        json.dumps({"type": "assistant", "message": {"role": "assistant",
                    "content": [{"type": "text", "text": "ok"}]}}),
        json.dumps({"type": "assistant", "message": {"role": "assistant",
                    "content": [{"type": "tool_use", "name": "AskUserQuestion",
                                 "input": {}}]}}),
        json.dumps({"type": "user", "message": {"role": "user",
                    "content": blocks_tail}}),
    ]
    p = tmp_path / name
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(p)


def _err_result_block(text=EMPTY_ERR):
    return {"type": "tool_result", "is_error": True,
            "content": [{"type": "text", "text": text}]}


def _ok_result_block():
    return {"type": "tool_result", "is_error": False,
            "content": [{"type": "text", "text": "user answered: option A"}]}


def _write_transcript_lines(tmp_path: Path, lines, name="transcript.jsonl") -> str:
    """Write a transcript from raw JSONL-able dicts (full control over the mix of
    assistant / tool_result-bearing-user / genuine-human-user lines). Returns
    the path. Used to test streak-breaking on a real human turn and the
    tail-window size."""
    p = tmp_path / name
    p.write_text("\n".join(json.dumps(o) for o in lines) + "\n", encoding="utf-8")
    return str(p)


def _tool_result_user_line(blocks):
    """A user-role line that is really a tool_result container (how the harness
    records a tool rejection) — NOT a human turn."""
    return {"type": "user", "message": {"role": "user", "content": blocks}}


def _human_user_line(text="here is my answer: go with option B"):
    """A genuine human turn: a user-role line whose content is plain text, no
    tool_result block. This is what must BREAK an empty-call streak."""
    return {"type": "user", "message": {"role": "user",
            "content": [{"type": "text", "text": text}]}}


def _run_hook(stdin_obj: dict) -> dict:
    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(stdin_obj),
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert proc.returncode == 0, f"hook must always exit 0, got {proc.returncode}: {proc.stderr}"
    out = proc.stdout.strip()
    return json.loads(out) if out else {}


# ---- unit level: the pure detector ----------------------------------------


def test_detects_empty_error_block():
    m = _load_module()
    assert m._is_empty_askuserquestion_error(_err_result_block()) is True


def test_non_error_block_is_not_a_match():
    m = _load_module()
    # same text but is_error False -> not a rejection
    blk = {"type": "tool_result", "is_error": False,
           "content": [{"type": "text", "text": EMPTY_ERR}]}
    assert m._is_empty_askuserquestion_error(blk) is False


def test_unrelated_error_is_not_a_match():
    m = _load_module()
    other = _err_result_block("<tool_use_error>InputValidationError: Edit failed: "
                              "old_string not found</tool_use_error>")
    assert m._is_empty_askuserquestion_error(other) is False


def test_string_content_form_is_flattened():
    m = _load_module()
    # some transcripts store content as a bare string, not a list
    blk = {"type": "tool_result", "is_error": True, "content": EMPTY_ERR}
    assert m._is_empty_askuserquestion_error(blk) is True


# ---- contract level: full stdin -> stdout JSON ----------------------------


def test_hook_blocks_on_empty_call(tmp_path):
    tpath = _write_transcript(tmp_path, [_err_result_block()])
    out = _run_hook({
        "hook_event_name": "Stop",
        "stop_hook_active": False,
        "transcript_path": tpath,
        "cwd": str(tmp_path),
        "session_id": "test-sess",
    })
    assert out.get("decision") == "block"
    assert "questions" in out.get("reason", "").lower()


def test_hook_allows_when_last_result_is_clean(tmp_path):
    # a successful AskUserQuestion (user answered) must not be blocked
    tpath = _write_transcript(tmp_path, [_ok_result_block()])
    out = _run_hook({
        "hook_event_name": "Stop",
        "stop_hook_active": False,
        "transcript_path": tpath,
        "cwd": str(tmp_path),
    })
    assert out == {}


def test_hook_anchors_to_last_result_only(tmp_path):
    # an empty-call failure followed by a later successful result must NOT
    # re-trigger — only the most recent tool_result matters
    tpath = _write_transcript(tmp_path, [_err_result_block(), _ok_result_block()])
    out = _run_hook({
        "hook_event_name": "Stop",
        "stop_hook_active": False,
        "transcript_path": tpath,
        "cwd": str(tmp_path),
    })
    assert out == {}, "a recovered earlier failure must not re-block"


def _seed_retry_log(tmp_path: Path, session_id: str, streak: int,
                    mode: str = "retry") -> None:
    """Write one prior retry-block record (this hook's own log shape) so a later
    run can compare the current streak against the streak it last blocked on.
    This is how the loop guard distinguishes 'model retried and failed again'
    (streak grew) from 'model followed the prose-stop instruction' (streak flat).
    """
    log_dir = tmp_path / ".omc" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    p = log_dir / "askuserquestion_retry.jsonl"
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"signal": "empty_askuserquestion",
                            "session_id": session_id, "streak": streak,
                            "mode": mode, "blocked": True}) + "\n")


def test_retry_stage_blocks_on_first_refire_without_prior_block(tmp_path):
    # streak 1 + stop_hook_active True but NO prior block logged for this session
    # (e.g. a re-fire triggered by a different Stop hook) -> this is the FIRST
    # time we see this empty call, so we still block once to force the retry.
    tpath = _write_transcript(tmp_path, [_err_result_block()])
    out = _run_hook({
        "hook_event_name": "Stop",
        "stop_hook_active": True,  # a Stop re-fire, but not from our own block
        "transcript_path": tpath,
        "cwd": str(tmp_path),
        "session_id": "no-prior",
    })
    assert out.get("decision") == "block", (
        "first time we see this streak we must still block once, even on re-fire")
    assert "rejected" in out.get("reason", "").lower()


def test_retry_stage_releases_when_model_stopped_in_prose(tmp_path):
    # DEADLOCK REGRESSION (2026-06-12): the empty call fired once, we blocked with
    # REASON_RETRY (which instructs "if there's an obvious recommendation, do NOT
    # call the tool — state it in prose and STOP"). The model OBEYED: it wrote
    # prose and did NOT re-call the tool. So the tail still shows streak 1 (no new
    # empty marker, no human turn). On the re-fire the hook must RELEASE the stop,
    # not block forever. We detect this via the prior retry-block log: we already
    # blocked at streak 1 for this session, and the streak did NOT grow -> the
    # model followed the prose-stop instruction -> let the stop through.
    _seed_retry_log(tmp_path, "deadlock", streak=1)  # we blocked once at streak 1
    tpath = _write_transcript(tmp_path, [_err_result_block()])  # streak still 1
    out = _run_hook({
        "hook_event_name": "Stop",
        "stop_hook_active": True,  # our own previous block re-fired this Stop
        "transcript_path": tpath,
        "cwd": str(tmp_path),
        "session_id": "deadlock",
    })
    assert out == {}, (
        "model followed prose-stop instruction (streak flat on re-fire) -> "
        "must release the stop, not deadlock")


def test_retry_stage_keeps_blocking_when_streak_grew_on_refire(tmp_path):
    # The OTHER branch of requirement 2: the model did NOT stop in prose — it
    # re-called the tool and it failed AGAIN, so the streak grew from 1 to 2.
    # That genuine continued loop must still be blocked (it will escalate to
    # abandon at 3). prior block logged at streak 1, current tail streak 2.
    _seed_retry_log(tmp_path, "grew", streak=1)  # we blocked at streak 1
    tpath = _write_transcript(tmp_path, [_err_result_block(), _err_result_block()])
    out = _run_hook({
        "hook_event_name": "Stop",
        "stop_hook_active": True,  # our own block re-fired
        "transcript_path": tpath,
        "cwd": str(tmp_path),
        "session_id": "grew",
    })
    assert out.get("decision") == "block", (
        "streak grew on re-fire (model re-called and failed again) -> keep blocking")
    # still the retry reason at streak 2, not abandon
    assert "three or more times" not in out.get("reason", "").lower()


def test_two_in_a_row_still_retries(tmp_path):
    # streak 2 is still the retry stage
    tpath = _write_transcript(tmp_path, [_err_result_block(), _err_result_block()])
    out = _run_hook({
        "hook_event_name": "Stop",
        "stop_hook_active": False,
        "transcript_path": tpath,
        "cwd": str(tmp_path),
    })
    assert out.get("decision") == "block"
    # the retry reason, not the abandon reason
    assert "three or more times" not in out.get("reason", "").lower()


def test_three_in_a_row_forces_abandon(tmp_path):
    # streak 3 -> abandon stage: stop retrying the tool, force prose+recommend
    tpath = _write_transcript(
        tmp_path, [_err_result_block(), _err_result_block(), _err_result_block()])
    out = _run_hook({
        "hook_event_name": "Stop",
        "stop_hook_active": False,
        "transcript_path": tpath,
        "cwd": str(tmp_path),
    })
    assert out.get("decision") == "block"
    reason = out.get("reason", "").lower()
    assert "three or more times" in reason
    assert "stop calling askuserquestion" in reason
    # Regression guard (2026-06-02): abandoning the TOOL must not be read as
    # authorization to do the WORK. The abandon message must tell the model to
    # WAIT for the user on an unmade decision, never to "proceed" with edits.
    # This is the exact failure that prompted this fix — "proceed with the
    # recommended option" was misread as "start the work without approval".
    assert "wait" in reason, "abandon message must tell the model to wait for the user"
    assert "not authorize" in reason or "not a 'yes" in reason, (
        "abandon message must state that abandoning the tool is not approval to act")
    assert "proceed with that recommended option" not in reason, (
        "the old 'proceed with that recommended option' wording must be gone")


def test_abandon_stage_caps_at_one_block_on_refire(tmp_path):
    # streak 3+ AND our own block re-fired -> do NOT block again (loop guard).
    # This is what stops a model that simply cannot emit the call from wedging
    # the session. Use streak 4 to mimic "already abandoned once, still failed".
    tpath = _write_transcript(
        tmp_path,
        [_err_result_block(), _err_result_block(),
         _err_result_block(), _err_result_block()])
    out = _run_hook({
        "hook_event_name": "Stop",
        "stop_hook_active": True,  # the abandon block already re-fired
        "transcript_path": tpath,
        "cwd": str(tmp_path),
    })
    assert out == {}, "abandon stage must release the stop on re-fire (loop guard)"


def test_retry_refire_without_session_id_releases(tmp_path):
    """Defensive: with NO session_id the hook cannot track its own prior blocks
    (the streak memory is keyed by session_id), so it cannot tell the prose-stop
    case from a grown streak. On a re-fire it must therefore RELEASE rather than
    risk the deadlock — abandon (streak 3+) still caps independently, so a true
    runaway is unaffected. Without this, a session whose stdin lacks session_id
    would deadlock exactly as the original bug did."""
    tpath = _write_transcript(tmp_path, [_err_result_block()])  # streak 1
    out = _run_hook({
        "hook_event_name": "Stop",
        "stop_hook_active": True,  # a re-fire
        "transcript_path": tpath,
        "cwd": str(tmp_path),
        # no session_id
    })
    assert out == {}, (
        "retry re-fire with no session_id must release (cannot track streak "
        "memory -> do not risk the deadlock)")


def test_retry_first_fire_without_session_id_still_blocks(tmp_path):
    """The counterpart: the FIRST fire (not a re-fire) with no session_id must
    still block once — we have not intervened yet, so the model should get its
    one retry nudge. Only the re-fire releases."""
    tpath = _write_transcript(tmp_path, [_err_result_block()])  # streak 1
    out = _run_hook({
        "hook_event_name": "Stop",
        "stop_hook_active": False,  # first fire
        "transcript_path": tpath,
        "cwd": str(tmp_path),
        # no session_id
    })
    assert out.get("decision") == "block", (
        "first fire (not a re-fire) must still block once even without session_id")


def test_deadlock_sequence_end_to_end(tmp_path):
    """END-TO-END proof of the 2026-06-12 deadlock fix using the hook's OWN log
    as the only state (no hand-seeded log): the exact sequence the user reported.

      Turn 1: empty AskUserQuestion call -> Stop -> hook BLOCKS (REASON_RETRY),
              writing one blocked@streak=1 record to its retry log.
      Turn 2: model OBEYS REASON_RETRY step 3 — writes a prose recommendation,
              does NOT re-call the tool. The tail is unchanged (still streak 1),
              the Stop re-fires with stop_hook_active=True. The hook must now
              RELEASE the stop by reading its own turn-1 log (streak did not grow).

    Before the fix, turn 2 blocked again every time (retry stage had no loop
    guard) and only a manual interrupt escaped. This drives the real two-call
    sequence so the regression cannot be satisfied by a hand-seeded log alone."""
    tpath = _write_transcript(tmp_path, [_err_result_block()])  # streak 1 both turns
    common = {
        "hook_event_name": "Stop",
        "transcript_path": tpath,
        "cwd": str(tmp_path),
        "session_id": "e2e-deadlock",
    }
    # Turn 1: first Stop after the empty call (not a re-fire) -> block once.
    out1 = _run_hook({**common, "stop_hook_active": False})
    assert out1.get("decision") == "block", "turn 1 must block to force the retry"

    # The hook logged its own block; confirm that state exists (it is the memory
    # turn 2 relies on — nothing else is seeded).
    log = tmp_path / ".omc" / "logs" / "askuserquestion_retry.jsonl"
    rec1 = json.loads(log.read_text().strip().splitlines()[-1])
    assert rec1["blocked"] is True and rec1["streak"] == 1

    # Turn 2: the block re-fired the Stop; the model stopped in prose so the tail
    # streak is still 1 (did not grow). The hook must RELEASE, not deadlock.
    out2 = _run_hook({**common, "stop_hook_active": True})
    assert out2 == {}, (
        "turn 2 must release the stop: model followed prose-stop instruction, "
        "streak flat on re-fire -> no more blocking (deadlock fixed)")


def test_hook_ignores_non_stop_event(tmp_path):
    tpath = _write_transcript(tmp_path, [_err_result_block()])
    out = _run_hook({
        "hook_event_name": "SubagentStop",
        "stop_hook_active": False,
        "transcript_path": tpath,
    })
    assert out == {}


def test_hook_allows_when_no_transcript_path():
    out = _run_hook({
        "hook_event_name": "Stop",
        "stop_hook_active": False,
    })
    assert out == {}


def test_hook_never_blocks_on_malformed_stdin():
    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input="this is not json {{{",
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_hook_allows_on_unreadable_transcript(tmp_path):
    out = _run_hook({
        "hook_event_name": "Stop",
        "stop_hook_active": False,
        "transcript_path": str(tmp_path / "does_not_exist.jsonl"),
        "cwd": str(tmp_path),
    })
    assert out == {}, "unreadable transcript must not wedge the session"


def test_hook_writes_log_on_detection(tmp_path):
    tpath = _write_transcript(tmp_path, [_err_result_block()])
    out = _run_hook({
        "hook_event_name": "Stop",
        "stop_hook_active": False,
        "transcript_path": tpath,
        "cwd": str(tmp_path),
        "session_id": "log-sess",
    })
    assert out.get("decision") == "block"
    log = tmp_path / ".omc" / "logs" / "askuserquestion_retry.jsonl"
    assert log.exists(), "detection must be logged for telemetry"
    rec = json.loads(log.read_text().strip())
    assert rec["signal"] == "empty_askuserquestion"
    assert rec["blocked"] is True


# ---- [2] a genuine human turn breaks the streak ---------------------------


def test_human_turn_breaks_streak(tmp_path):
    """An empty call, then a REAL human answer, then another empty call must be
    streak 1 (the human turn resets it) — NOT streak 2. Without this, a user who
    answers between two unrelated empty calls is wrongly escalated toward abandon.
    """
    m = _load_module()
    lines = [
        _tool_result_user_line([_err_result_block()]),   # older empty call
        _human_user_line(),                              # genuine human turn
        _tool_result_user_line([_err_result_block()]),   # newest empty call
    ]
    tpath = _write_transcript_lines(tmp_path, lines)
    assert m._count_consecutive_empty_calls(tpath) == 1


def test_consecutive_empties_without_human_still_stack(tmp_path):
    """Guard against over-correction: two empty calls with NO human turn between
    them must still count as streak 2 (model looping on its own)."""
    m = _load_module()
    lines = [
        _tool_result_user_line([_err_result_block()]),
        _tool_result_user_line([_err_result_block()]),
    ]
    tpath = _write_transcript_lines(tmp_path, lines)
    assert m._count_consecutive_empty_calls(tpath) == 2


# ---- [1] the tail window is large enough for a busy turn -------------------


def test_empty_error_found_beyond_40_lines(tmp_path):
    """A busy turn can push the empty-call rejection past the old 40-line tail
    window. The detector must still find an empty rejection that sits, say, 60
    lines from the end, behind many successful tool_results."""
    m = _load_module()
    # 60 successful tool_result lines AFTER... no: the empty must be the most
    # recent tool_result. Put the empty rejection, then 60 NON-tool_result
    # assistant lines (thinking/text) so the empty is still the last result but
    # lies >40 physical lines from EOF.
    lines = [_tool_result_user_line([_err_result_block()])]
    for i in range(60):
        lines.append({"type": "assistant", "message": {"role": "assistant",
                      "content": [{"type": "text", "text": f"thinking {i}"}]}})
    tpath = _write_transcript_lines(tmp_path, lines)
    assert m._count_consecutive_empty_calls(tpath) == 1, (
        "empty rejection beyond the old 40-line window must still be detected")


# ---- [4] the retry reason now nudges /compact -----------------------------


def test_retry_reason_mentions_compact(tmp_path):
    """The /compact tip (context shrink = the only documented mitigation for the
    underlying model-side failure) must appear at the RETRY stage too, not only
    at abandon — so the user learns the lever early."""
    tpath = _write_transcript(tmp_path, [_err_result_block()])
    out = _run_hook({
        "hook_event_name": "Stop",
        "stop_hook_active": False,
        "transcript_path": tpath,
        "cwd": str(tmp_path),
    })
    assert out.get("decision") == "block"
    assert "/compact" in out.get("reason", "")


# ---- [3] cross-shape session failure count escalates to abandon ------------


def _seed_guard_log(tmp_path: Path, session_id: str, n: int) -> None:
    """Write n guard-deny records (the PreToolUse guard's shape: empty-array /
    partial / surrogate denies) for a session into the shared log dir."""
    log_dir = tmp_path / ".omc" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    p = log_dir / "askuserquestion_guard.jsonl"
    with p.open("a", encoding="utf-8") as f:
        for _ in range(n):
            f.write(json.dumps({"signal": "denied_askuserquestion",
                                "session_id": session_id}) + "\n")


def test_session_failure_count_folds_both_logs(tmp_path):
    """The Stop hook's session counter must sum guard denies + its own retry
    rejections for the SAME session_id, ignoring other sessions."""
    m = _load_module()
    _seed_guard_log(tmp_path, "sess-A", 3)
    _seed_guard_log(tmp_path, "sess-B", 9)  # noise: a different session
    # one prior retry rejection of our own, same session
    retry_log = tmp_path / ".omc" / "logs" / "askuserquestion_retry.jsonl"
    retry_log.write_text(json.dumps(
        {"signal": "empty_askuserquestion", "session_id": "sess-A"}) + "\n",
        encoding="utf-8")
    assert m._session_failure_count(str(tmp_path), "sess-A") == 4  # 3 + 1


def test_string_content_rejection_does_not_break_streak(tmp_path):
    """REGRESSION (review bug 2): the harness sometimes records a tool rejection
    with `content` as a BARE STRING, not a list of blocks. Such a line must NOT
    be mistaken for a genuine human turn — otherwise a real loop of empty calls
    (recorded in string form) is miscounted as streak 1 each and never escalates.
    """
    m = _load_module()
    string_err_line = {"type": "user", "message": {"role": "user",
                       "content": EMPTY_ERR}}  # bare string, not a list
    lines = [string_err_line, string_err_line, string_err_line]
    tpath = _write_transcript_lines(tmp_path, lines)
    assert m._count_consecutive_empty_calls(tpath) == 3, (
        "bare-string-content empty rejections must stack, not reset the streak")


def test_in_flight_failure_counts_toward_abandon_threshold(tmp_path):
    """REGRESSION (review bug 1): the cross-shape session count reads only logs
    written BEFORE this decision; the in-flight failure is not yet logged. With
    threshold 5, exactly 4 prior failures + this one = 5 must abandon. Before the
    fix, 4 prior read as 4 (< 5) and wrongly stayed in the retry stage."""
    _seed_guard_log(tmp_path, "edge", 4)  # 4 prior, in-flight makes 5
    tpath = _write_transcript(tmp_path, [_err_result_block()])  # tail streak 1
    out = _run_hook({
        "hook_event_name": "Stop",
        "stop_hook_active": False,
        "transcript_path": tpath,
        "cwd": str(tmp_path),
        "session_id": "edge",
    })
    assert out.get("decision") == "block"
    assert "three or more times" in out.get("reason", "").lower(), (
        "4 prior + 1 in-flight = threshold 5 must abandon")


def test_high_session_count_forces_abandon_even_at_low_streak(tmp_path):
    """Even a tail streak of just 1, when the session has already racked up many
    AskUserQuestion failures of ANY shape (guard denies + retry rejections),
    escalates to ABANDON — the model is clearly looping across shapes, so stop
    nudging retries and route to prose+recommend."""
    _seed_guard_log(tmp_path, "loopy", 5)  # 5 prior guard denies this session
    tpath = _write_transcript(tmp_path, [_err_result_block()])  # tail streak 1
    out = _run_hook({
        "hook_event_name": "Stop",
        "stop_hook_active": False,
        "transcript_path": tpath,
        "cwd": str(tmp_path),
        "session_id": "loopy",
    })
    assert out.get("decision") == "block"
    assert "three or more times" in out.get("reason", "").lower(), (
        "a high cross-shape session count must trigger the abandon reason")

"""runtime/hud/omha-route.mjs — HUD가 트랜스크립트에서 현재 lane을 뽑아내는 로직.

The module is ESM consumed by the patched HUD wrapper, so it is exercised through
node rather than reimplemented in Python: a reimplementation would drift from the
thing that actually runs on the statusline.

Context: omha 0.9.0 stopped requiring a ROUTE line on pure-chat turns (~54% of
turns), so the HUD is now the only always-on surface showing the current lane.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MODULE = REPO / "runtime" / "hud" / "omha-route.mjs"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def _assistant(text):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


def _thinking(text):
    return {"type": "assistant",
            "message": {"content": [{"type": "thinking", "thinking": text, "signature": "x"}]}}


def _user(text):
    return {"type": "user", "uuid": "u1", "message": {"content": text}}


def _write(tmp_path, records):
    p = tmp_path / "transcript.jsonl"
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records),
                 encoding="utf-8")
    return p


def _segment(transcript):
    script = ("const {routeSegment} = await import(process.argv[1]);"
              "console.log(routeSegment(process.argv[2]) ?? '');")
    out = subprocess.run(
        ["node", "--input-type=module", "-e", script, "--", MODULE.as_uri(), str(transcript)],
        capture_output=True, text=True, check=True)
    return out.stdout.strip()


def test_abbreviates_a_known_lane(tmp_path):
    t = _write(tmp_path, [_user("hi"), _assistant("> **ROUTE →** oh-my-claudecode · 이유")])
    assert _segment(t) == "omc"


def test_reads_the_colon_and_arrow_forms(tmp_path):
    t = _write(tmp_path, [_user("hi"), _assistant("ROUTE: handle-directly")])
    assert _segment(t) == "direct"


def test_last_declaration_wins_on_a_rerouted_turn(tmp_path):
    t = _write(tmp_path, [_user("hi"),
                          _assistant("> **ROUTE →** handle-directly · 처음"),
                          _assistant("> **ROUTE →** superpowers · 재라우팅")])
    assert _segment(t) == "sp"


def test_carries_the_last_lane_across_a_silent_chat_turn(tmp_path):
    """omha 0.9.0부터 대화 턴은 선언을 안 한다. 턴 경계에서 멈추면 절반 넘는 턴에서
    세그먼트가 빈칸이 되므로, 마지막으로 알려진 레인을 이어서 보여준다."""
    t = _write(tmp_path, [_user("작업"), _assistant("> **ROUTE →** oh-my-project · 이유"),
                          _user("그건 왜 그래?"), _assistant("설명만 하는 턴이라 선언 없음")])
    assert _segment(t) == "omp"


def test_unknown_lane_passes_through_unabbreviated(tmp_path):
    t = _write(tmp_path, [_user("hi"), _assistant("ROUTE → oh-my-newthing · 이유")])
    assert _segment(t) == "oh-my-newthing"


def test_thinking_blocks_are_not_a_source(tmp_path):
    """트랜스크립트의 thinking 본문은 실측 938/938 빈 값이다. 읽지 않는 걸 고정한다."""
    t = _write(tmp_path, [_user("hi"), _thinking("ROUTE → superpowers · 숨은 선언")])
    assert _segment(t) == ""


def test_missing_file_is_empty_not_a_crash(tmp_path):
    assert _segment(tmp_path / "nope.jsonl") == ""


def test_truncated_first_line_of_the_tail_is_skipped(tmp_path):
    """tail 읽기는 첫 줄을 반쯤 자른다. 파싱 실패한 줄은 건너뛰고 계속 가야 한다."""
    p = tmp_path / "transcript.jsonl"
    p.write_text('{"type":"assist' + "\n"
                 + json.dumps(_assistant("ROUTE → oh-my-project · 이유")) + "\n",
                 encoding="utf-8")
    assert _segment(p) == "omp"


# ─── backward scan depth (2026-08-23) ─────────────────────────────────────────
# A fixed tail window was the first implementation and it was wrong: the ROUTE is
# declared at the START of a turn and every tool result lands after it, so on a
# long work turn the declaration ends up deep in the file. Measured on two live
# sessions: 442 KB and 1.29 MB from EOF. 128 KB found neither.

def test_finds_a_route_buried_under_megabytes_of_tool_output(tmp_path):
    filler = {"type": "user", "toolUseResult": {"stdout": "x" * 60000},
              "message": {"content": [{"type": "tool_result", "content": "x" * 60000}]}}
    records = [_user("작업"), _assistant("> **ROUTE →** oh-my-experiments · 이유")]
    records += [filler] * 30          # ~3.6 MB of tool output after the declaration
    t = _write(tmp_path, records)
    assert t.stat().st_size > 2_000_000
    assert _segment(t) == "omx"


def test_a_route_in_a_tool_result_is_not_a_declaration(tmp_path):
    """실제로 밟은 오탐: 피어에게 보낸 메시지가 toolUseResult 로 되돌아와
    그 안의 ROUTE 문자열이 선언처럼 보였다. assistant 텍스트 블록만 선언이다."""
    t = _write(tmp_path, [
        _user("hi"),
        _assistant("> **ROUTE →** superpowers · 진짜 선언"),
        {"type": "user", "toolUseResult": {"ok": True},
         "message": {"content": [{"type": "tool_result",
                                  "content": "ROUTE → oh-my-docs · 남의 텍스트"}]}},
    ])
    assert _segment(t) == "sp"


def test_korean_survives_a_chunk_boundary(tmp_path):
    """청크 경계가 한글 코드포인트 한가운데 떨어져도 줄이 온전히 복원돼야 한다.
    청크마다 문자열로 디코딩하면 그 바이트가 U+FFFD 로 뭉개진다."""
    pad = {"type": "user", "message": {"content": [{"type": "text", "text": "한" * 40000}]}}
    t = _write(tmp_path, [_user("시작"),
                          _assistant("> **ROUTE →** oh-my-scholar · 한글 근거 문구"),
                          pad, pad, pad])
    assert _segment(t) == "oms"

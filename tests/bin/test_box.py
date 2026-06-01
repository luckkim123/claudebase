"""Tests for runtime/bin/box.py — CJK-aware unicode box renderer."""
from __future__ import annotations
import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BOX_PATH = REPO_ROOT / "runtime" / "bin" / "box.py"


def _load():
    spec = importlib.util.spec_from_file_location("box", BOX_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_visual_width_cjk_is_2():
    m = _load()
    assert m.visual_width("ab") == 2
    assert m.visual_width("결론") == 4      # 한글 2글자 = 4칸
    assert m.visual_width("a결") == 3        # 혼합


def test_render_box_right_edge_aligned():
    m = _load()
    out = m.render_box("결론", ["캐시 무효화가 원인입니다.", "ASCII mixed 한글 line"])
    lines = out.splitlines()
    # 모든 줄의 시각적 폭이 동일해야(우변 정렬). 첫 줄(top border) 폭 기준.
    widths = {m.visual_width(l) for l in lines}
    assert len(widths) == 1, f"all rows must share one visual width, got {widths}"


def test_render_box_has_borders():
    m = _load()
    out = m.render_box("T", ["x"])
    assert out.startswith("╭") and "╮" in out.splitlines()[0]
    assert out.splitlines()[-1].startswith("╰") and out.splitlines()[-1].endswith("╯")


def test_ascii_fallback():
    m = _load()
    out = m.render_box("T", ["x"], ascii_only=True)
    assert "╭" not in out and "+" in out.splitlines()[0]


def test_cli_invocation():
    proc = subprocess.run(
        [sys.executable, str(BOX_PATH), "결론", "캐시가 원인입니다."],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0
    assert "결론" in proc.stdout and "╭" in proc.stdout


def test_cli_no_args_exits_clean():
    proc = subprocess.run(
        [sys.executable, str(BOX_PATH)],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0  # no crash on empty


# ---- wrapping: long lines must not overflow the max width ------------------


def test_wrap_width_breaks_long_line():
    m = _load()
    out = m.wrap_visual("a" * 100, 40)
    assert all(m.visual_width(seg) <= 40 for seg in out)
    assert "".join(out) == "a" * 100  # no content lost


def test_wrap_prefers_space_boundaries():
    m = _load()
    out = m.wrap_visual("the quick brown fox jumps over", 12)
    # every segment within width, and no word is split mid-token when a space fit exists
    assert all(m.visual_width(seg) <= 12 for seg in out)
    assert "quick" in " ".join(out)


def test_wrap_cjk_no_space_force_breaks():
    m = _load()
    # Korean has no spaces here — must still break by visual width
    s = "가나다라마바사아자차카타파하" * 3
    out = m.wrap_visual(s, 20)
    assert all(m.visual_width(seg) <= 20 for seg in out)
    assert "".join(out) == s


def test_render_box_wraps_long_line():
    m = _load()
    long = "§2.3.2 미시 표현 어색함 3건 " * 5
    out = m.render_box("분석", [long], max_width=60)
    widths = {m.visual_width(line) for line in out.splitlines()}
    assert len(widths) == 1, "all rows share one width"
    assert widths.pop() <= 60, "box must not exceed max_width"


def test_render_box_short_line_no_forced_width():
    m = _load()
    # a short line should NOT be padded out to max_width
    out = m.render_box("T", ["hi"], max_width=80)
    assert m.visual_width(out.splitlines()[0]) < 80


# ---- typed boxes: 5 defined types + free-title fallback --------------------


def test_type_label_lookup():
    m = _load()
    # the 5 defined types map to standard Korean labels (no emoji)
    assert m.type_label("skill") == "SKILL"
    assert m.type_label("analysis") == "분석"
    assert m.type_label("plan") == "계획"
    assert m.type_label("summary") == "요약"
    assert m.type_label("warning") == "주의"


def test_type_label_unknown_returns_none():
    m = _load()
    # unknown type -> None, so the caller falls back to a free title
    assert m.type_label("garbage") is None
    assert m.type_label("") is None


def test_cli_type_skill_renders_label():
    proc = subprocess.run(
        [sys.executable, str(BOX_PATH), "--type", "skill", "external-context 사용"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0
    assert "SKILL" in proc.stdout

def test_cli_type_with_extra_title_suffix():
    # --type skill plus a leading "subtitle" arg appends to the label
    proc = subprocess.run(
        [sys.executable, str(BOX_PATH), "--type", "skill", "--label", "external-context",
         "5 facet 병렬 조사"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0
    assert "SKILL" in proc.stdout and "external-context" in proc.stdout

def test_cli_unknown_type_is_treated_as_title():
    # no --type: first arg is a free title (Claude-authored category)
    proc = subprocess.run(
        [sys.executable, str(BOX_PATH), "검증 결과", "전부 통과"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0
    assert "검증 결과" in proc.stdout

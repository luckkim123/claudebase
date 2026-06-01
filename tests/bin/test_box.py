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

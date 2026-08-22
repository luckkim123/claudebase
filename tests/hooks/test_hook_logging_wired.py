"""배선된 훅은 전부 자기 로그 파일명 리터럴을 소스에 갖는다.

harness_stats.logging_hooks() 가 grep 으로 찾는 그 리터럴이다 — 이 테스트가
없으면 헬퍼로 리팩터링하다 리터럴이 사라져도 아무도 모른다."""
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[2] / "runtime" / "hooks"

WIRED_PY = [
    "session-gate.py",
    "session-title-3words.py",
    "fix_surrogate.py",
    "graphify_scope_filter.py",
    "merge-project-hook.py",
    "omc-reference-emit.py",
]


@pytest.mark.parametrize("name", WIRED_PY)
def test_hook_carries_its_log_literal(name):
    text = (HOOKS / name).read_text(encoding="utf-8")
    stem = name.replace(".py", "").replace("-", "_") + ".jsonl"
    assert stem in text, f"{name} 에 {stem} 리터럴이 없다 — harness_stats 가 못 본다"


@pytest.mark.parametrize("name", WIRED_PY)
def test_hook_imports_hooklog(name):
    text = (HOOKS / name).read_text(encoding="utf-8")
    assert "hooklog" in text

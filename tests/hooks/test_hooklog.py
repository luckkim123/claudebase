"""hooklog.fire 의 계약: append 한다, 절대 안 죽는다."""
import importlib.util
import json
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[2] / "runtime" / "hooks" / "hooklog.py"


def _load():
    spec = importlib.util.spec_from_file_location("hooklog", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_appends_one_json_line(tmp_path):
    hooklog = _load()
    hooklog.fire("demo.jsonl", str(tmp_path), session_id="s1", decision="allow")
    out = tmp_path / ".omc" / "logs" / "demo.jsonl"
    rows = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["session_id"] == "s1"
    assert rows[0]["decision"] == "allow"
    assert "ts" in rows[0]


def test_appends_not_overwrites(tmp_path):
    hooklog = _load()
    hooklog.fire("demo.jsonl", str(tmp_path))
    hooklog.fire("demo.jsonl", str(tmp_path))
    out = tmp_path / ".omc" / "logs" / "demo.jsonl"
    assert len(out.read_text(encoding="utf-8").splitlines()) == 2


def test_never_raises_on_unwritable_cwd(tmp_path):
    hooklog = _load()
    blocked = tmp_path / "file-not-dir"
    blocked.write_text("x", encoding="utf-8")
    hooklog.fire("demo.jsonl", str(blocked))  # 예외가 새면 이 테스트가 실패한다


def test_never_raises_on_none_cwd():
    hooklog = _load()
    hooklog.fire("demo.jsonl", None)


def test_non_serializable_field_does_not_raise(tmp_path):
    hooklog = _load()
    hooklog.fire("demo.jsonl", str(tmp_path), obj=object())

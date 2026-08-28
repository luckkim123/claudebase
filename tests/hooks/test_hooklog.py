"""hooklog.fire 의 계약: append 한다, 절대 안 죽는다."""
import importlib.util
import os
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


def test_never_raises_on_none_cwd(tmp_path, monkeypatch):
    # cwd=None falls back to the process cwd (hooklog.py: `cwd or "."`).
    # Without pinning it to tmp_path, this write lands in the real repo's
    # .omc/logs/demo.jsonl whenever pytest runs from the repo root.
    monkeypatch.chdir(tmp_path)
    hooklog = _load()
    hooklog.fire("demo.jsonl", None)


def test_non_serializable_field_does_not_raise(tmp_path):
    hooklog = _load()
    hooklog.fire("demo.jsonl", str(tmp_path), obj=object())


# --- state_root: cwd 를 믿지 않는다 (2026-08-28, vault 에 .omc 18 개가 생긴 뒤) ---

def test_ascends_to_ancestor_owning_omc(tmp_path):
    """`cd` 로 내려간 하위 디렉터리에서 발화해도 로그는 프로젝트 루트로 간다."""
    hooklog = _load()
    (tmp_path / ".omc").mkdir()
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    hooklog.fire("demo.jsonl", str(deep))
    assert (tmp_path / ".omc" / "logs" / "demo.jsonl").is_file()
    assert not (deep / ".omc").exists()          # 하위에 새로 만들지 않는다
    assert not (tmp_path / "a" / ".omc").exists()


def test_falls_back_to_git_root_when_no_omc_exists(tmp_path):
    """`.omc` 를 가진 조상이 없으면 `.git` 루트로 — 신규 프로젝트의 첫 발화."""
    hooklog = _load()
    (tmp_path / ".git").mkdir()
    deep = tmp_path / "src" / "pkg"
    deep.mkdir(parents=True)
    hooklog.fire("demo.jsonl", str(deep))
    assert (tmp_path / ".omc" / "logs" / "demo.jsonl").is_file()
    assert not (deep / ".omc").exists()


def test_never_ascends_into_home(tmp_path, monkeypatch):
    """`~/.omc` 가 실재하는 머신에서 모든 프로젝트 계측이 홈으로 고이면 안 된다."""
    hooklog = _load()
    fake_home = tmp_path
    (fake_home / ".omc").mkdir()                  # 홈의 .omc — 잡히면 안 된다
    monkeypatch.setenv("HOME", str(fake_home))
    proj = fake_home / "proj"
    proj.mkdir()
    hooklog.fire("demo.jsonl", str(proj))
    assert (proj / ".omc" / "logs" / "demo.jsonl").is_file()
    assert not (fake_home / ".omc" / "logs").exists()


# --- hooklog.sh: 셸 훅도 같은 루트로 (2026-08-28, 셸 계열 5종이 raw $PWD 였다) ---

import subprocess

SH = HOOK.with_suffix(".sh")


def _sh_root(cwd, home=None):
    env = dict(os.environ, HOME=str(home)) if home else None
    r = subprocess.run(
        ["sh", "-c", f'. "{SH}"; hooklog_state_root "{cwd}"'],
        capture_output=True, text=True, env=env,
    )
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def test_sh_matches_python_resolver(tmp_path):
    """셸판과 파이썬판이 갈리면 같은 세션이 두 곳에 로그를 남긴다."""
    hooklog = _load()
    (tmp_path / ".omc").mkdir()
    deep = tmp_path / "a" / "b"
    deep.mkdir(parents=True)
    assert _sh_root(deep) == os.path.realpath(hooklog.state_root(str(deep)))


def test_sh_falls_back_to_git_root(tmp_path):
    (tmp_path / ".git").mkdir()
    deep = tmp_path / "src"
    deep.mkdir()
    assert _sh_root(deep) == os.path.realpath(str(tmp_path))


def test_sh_never_ascends_into_home(tmp_path):
    (tmp_path / ".omc").mkdir()
    proj = tmp_path / "proj"
    proj.mkdir()
    assert _sh_root(proj, home=tmp_path) == os.path.realpath(str(proj))

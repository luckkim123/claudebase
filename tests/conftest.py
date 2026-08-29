"""Shared pytest fixtures for claudebase tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# Make runtime/hooks/ and installer/scripts/ importable as flat modules.
for sub in ("runtime/hooks", "installer/scripts"):
    p = str(REPO_ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture(autouse=True)
def neutralize_claudebase_env(monkeypatch):
    """Strip the env this repo injects into Claude Code, so tests stay hermetic.

    `render_settings.py` writes `env.OMC_STATE_DIR` into ~/.claude/settings.json,
    and Claude Code exports that to every subprocess of every session — this
    pytest run included. `tests/installer/test_patch_omc_statedir.py` spawns
    `node` without an explicit `env`, so the variable reaches the code under
    test, whose `getOmcRoot()` checks it *before* the marker-ascent branch those
    tests exist to verify. Three of them then assert the ascent path while the
    override path is what actually ran.

    What hid it is the blast pattern: neither CI (.github/workflows/ci.yml sets
    nothing) nor a login shell (~/.zshrc and shell/ never export it) has the
    variable, so the suite fails *only* when run from inside the agent this repo
    configures — green everywhere anyone thought to look.

    Scoped to variables claudebase itself injects. A test that wants
    OMC_STATE_DIR set should `monkeypatch.setenv` it, which still wins.
    """
    monkeypatch.delenv("OMC_STATE_DIR", raising=False)


@pytest.fixture(autouse=True)
def contain_hook_telemetry(monkeypatch, tmp_path):
    """훅 계측을 테스트의 tmp 디렉터리 안에 가둔다.

    훅은 `hooklog.state_root(payload["cwd"])` 아래 `.omc/logs/` 에 append 하고,
    여러 훅 테스트가 그 페이로드에 `"/tmp"` 를 박아 넣는다. state_root 는 `.omc/`
    를 가진 가장 가까운 조상을 찾으므로, 한 번 `/private/tmp/.omc/` 가 생기고
    나면 그 뒤로는 모든 실행이 거기로 빨려 들어간다 — 자기 유지되는 누수다.
    2026-08-29 실측: `/private/tmp/.omc/logs/agent_routing_guard.jsonl` 144 행,
    전부 `session_id: "t"`(테스트 픽스처 값)로 실제 계측은 0 건이었다.

    실패하는 테스트가 없어서 아무도 못 봤다 — 계측은 best-effort 라 조용히
    성공한다. 그래서 단언이 아니라 격리로 막는다.

    `hooklog` 를 sys.modules 층에서 갈아끼운다. 훅들은 `import hooklog` 로 그
    객체를 공유하지만, hooklog 자신을 검사하는 test_hooklog.py 는 importlib 로
    자기 모듈 객체를 따로 만들어 쓰므로 영향받지 않는다(state_root 상승 규약을
    검사하는 테스트를 이 fixture 가 무력화하면 안 된다).
    """
    import hooklog

    monkeypatch.setattr(hooklog, "state_root", lambda cwd=None: str(tmp_path))

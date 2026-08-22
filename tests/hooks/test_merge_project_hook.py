"""Tests for runtime/hooks/merge-project-hook.py.

Runs the script as a subprocess (it's a CLI tool with sys.argv) and
verifies the idempotent-merge behavior across three scenarios:
  - first-time install
  - re-install with identical fragment (no change)
  - re-install with updated fragment (replace existing entry by marker)
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / "runtime" / "hooks" / "merge-project-hook.py"
MARKER = "TEST_MARKER_XYZ"


def _fragment(tmp: Path, body_command: str) -> Path:
    """Build a one-event fragment file with a marker comment in command."""
    p = tmp / "fragment.json"
    p.write_text(json.dumps({
        "SessionStart": [{
            "matcher": "startup",
            "hooks": [{
                "type": "command",
                "command": f"# {MARKER}\n{body_command}",
            }],
        }],
    }))
    return p


def _run(fragment: Path, target: Path) -> tuple[int, str, str]:
    # The hook fires hooklog with cwd=None, which falls back to the process
    # cwd. Pin the subprocess's cwd to the fragment's tmp_path so that
    # fallback lands in the test sandbox, not the real repo's .omc/logs.
    r = subprocess.run(
        [sys.executable, str(HOOK), str(fragment), str(target), MARKER],
        capture_output=True, text=True,
        cwd=str(fragment.parent),
        check=False,
    )
    return r.returncode, r.stdout, r.stderr


def test_first_install_creates_hooks_section(tmp_path):
    target = tmp_path / "settings.json"
    target.write_text("{}")
    rc, out, _ = _run(_fragment(tmp_path, "echo first"), target)
    assert rc == 0
    assert "merged" in out
    settings = json.loads(target.read_text())
    assert "SessionStart" in settings["hooks"]
    assert MARKER in settings["hooks"]["SessionStart"][0]["hooks"][0]["command"]


def test_reinstall_identical_is_noop(tmp_path):
    target = tmp_path / "settings.json"
    target.write_text("{}")
    _run(_fragment(tmp_path, "echo same"), target)
    before = target.read_text()
    rc, out, _ = _run(_fragment(tmp_path, "echo same"), target)
    assert rc == 0
    assert "unchanged" in out
    assert target.read_text() == before


def test_updated_fragment_replaces_existing(tmp_path):
    target = tmp_path / "settings.json"
    target.write_text("{}")
    _run(_fragment(tmp_path, "echo old"), target)
    rc, out, _ = _run(_fragment(tmp_path, "echo NEW"), target)
    assert rc == 0
    assert "merged" in out
    settings = json.loads(target.read_text())
    cmd = settings["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert "echo NEW" in cmd
    assert "echo old" not in cmd


def test_missing_target_dir_returns_rc2(tmp_path):
    target = tmp_path / "no" / "such" / "dir" / "settings.json"
    rc, _, _ = _run(_fragment(tmp_path, "echo x"), target)
    assert rc == 2


def test_existing_unrelated_hook_preserved(tmp_path):
    target = tmp_path / "settings.json"
    target.write_text(json.dumps({
        "hooks": {
            "SessionStart": [{
                "matcher": "startup",
                "hooks": [{"type": "command", "command": "# UNRELATED\necho keep"}],
            }],
        },
    }))
    _run(_fragment(tmp_path, "echo new"), target)
    settings = json.loads(target.read_text())
    entries = settings["hooks"]["SessionStart"]
    cmds = [h["command"] for e in entries for h in e["hooks"]]
    assert any("UNRELATED" in c for c in cmds)
    assert any(MARKER in c for c in cmds)

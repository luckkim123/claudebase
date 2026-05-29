"""Tests for runtime/hooks/omc-reference-emit.py.

Runs the script as a subprocess and verifies SessionStart hook output:
when an OMC skill cache exists, the body is injected; otherwise a doctor
hint is emitted. Both cases must produce valid JSON for Claude Code.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / "runtime" / "hooks" / "omc-reference-emit.py"


def _run(env_home: Path) -> dict:
    env = os.environ.copy()
    env["HOME"] = str(env_home)
    r = subprocess.run([sys.executable, str(HOOK)], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_no_cache_emits_doctor_hint(tmp_path):
    """Empty ~/.claude/plugins/cache — hook still returns valid envelope."""
    payload = _run(tmp_path)
    out = payload["hookSpecificOutput"]
    assert out["hookEventName"] == "SessionStart"
    assert "omc-doctor" in out["additionalContext"]


def test_cache_present_injects_body(tmp_path):
    """When a SKILL.md is cached, body (minus 5-line frontmatter) is injected."""
    skill_dir = tmp_path / ".claude" / "plugins" / "cache" / "omc" / "oh-my-claudecode" \
                / "9.9.9" / "skills" / "omc-reference"
    skill_dir.mkdir(parents=True)
    skill_md = skill_dir / "SKILL.md"
    # 5-line frontmatter + body
    skill_md.write_text(
        "---\n"
        "name: omc-reference\n"
        "description: test\n"
        "---\n"
        "\n"
        "# Catalog body line one\n"
        "Catalog body line two\n"
    )
    payload = _run(tmp_path)
    ctx = payload["hookSpecificOutput"]["additionalContext"]
    assert "OMC Skill Catalog (auto-loaded)" in ctx
    assert "Catalog body line one" in ctx
    assert "Catalog body line two" in ctx
    # Frontmatter should be stripped.
    assert "name: omc-reference" not in ctx

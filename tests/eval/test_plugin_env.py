"""Contract tests for plugin_env.write_neutralize_settings.

The false-map contract exists because of a measured failure (2026-08-22 probe,
claudebase-hooks-ab.yaml "PROBE EXECUTED"): an empty enabledPlugins map at the
--settings layer deep-merges as a no-op, so the neutralization file MUST carry
an explicit per-key false for every plugin the user layer enables.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "eval" / "scripts"))

import plugin_env  # noqa: E402


def test_false_map_covers_every_enabled_plugin(tmp_path):
    user = tmp_path / "settings.json"
    user.write_text(json.dumps({
        "enabledPlugins": {"a@m": True, "b@m": True, "c@m": False},
        "hooks": {"Stop": []},
    }))
    out = tmp_path / "neutralize.json"
    path, problem = plugin_env.write_neutralize_settings(out, user)
    assert problem is None and path == out
    payload = json.loads(out.read_text())
    # every key pinned false — including one the user already disabled
    assert payload["enabledPlugins"] == {"a@m": False, "b@m": False, "c@m": False}
    # scalar neutralization rides along, matching the yaml's documented values
    assert payload["outputStyle"] == "default"
    assert payload["alwaysThinkingEnabled"] is True
    assert payload["effortLevel"] == "unset"


def test_missing_user_settings_is_not_an_error(tmp_path):
    out = tmp_path / "neutralize.json"
    path, problem = plugin_env.write_neutralize_settings(
        out, tmp_path / "does-not-exist.json"
    )
    assert problem is None and path == out
    assert json.loads(out.read_text())["enabledPlugins"] == {}


def test_corrupt_user_settings_fails_loud(tmp_path):
    user = tmp_path / "settings.json"
    user.write_text("{not json")
    out = tmp_path / "neutralize.json"
    path, problem = plugin_env.write_neutralize_settings(out, user)
    assert path is None and problem is not None
    assert not out.exists()


def test_yaml_points_at_the_generated_path():
    """The yaml's claude_settings string and NEUTRALIZE must never drift."""
    yaml_text = (REPO_ROOT / "eval" / "experiments" / "claudebase-hooks-ab.yaml"
                 ).read_text(encoding="utf-8")
    assert f'claude_settings: "{plugin_env.NEUTRALIZE}"' in yaml_text
    # the superseded inline-dict form must not resurface as an actual config
    # line (prose mentions of `enabledPlugins: {}` in the description/comments
    # are historical record and fine — those lines carry surrounding text)
    assert not re.search(r"^\s+enabledPlugins: \{\}\s*$", yaml_text, re.M)

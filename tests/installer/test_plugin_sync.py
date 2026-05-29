"""Unit tests for installer/scripts/plugin_sync.py.

These tests pin the decision logic of plugin sync so future install.sh
refactors cannot silently regress. Each test pairs an input state
(enabledPlugins, installed_plugins, marketplace metadata, platform)
with the expected ordered list of Decisions.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "installer" / "scripts"))

import plugin_sync as ps  # noqa: E402


# ---------- fixtures ----------

@pytest.fixture
def metadata():
    return {
        "claude-plugins-official": {"os": ["macos", "linux", "windows"]},
        "axlabs": {"os": ["macos", "linux", "windows"]},
        "omc": {"os": ["macos", "linux", "windows"], "post_install": ["install_omc_shell_cli"]},
        "heroacademia": {"os": ["macos"]},
    }


@pytest.fixture
def make_state(tmp_path, metadata):
    """Return a factory that writes claude_home + metadata into tmp_path."""
    def _make(enabled: dict, installed: dict, platform: str = "macos",
              local_enabled: Optional[dict] = None):
        claude_home = tmp_path / "claude_home"
        (claude_home / "plugins").mkdir(parents=True)
        # settings.json
        settings = {"enabledPlugins": enabled}
        if local_enabled is not None:
            (claude_home / "settings.local.json").write_text(
                json.dumps({"enabledPlugins": local_enabled})
            )
        (claude_home / "settings.json").write_text(json.dumps(settings))
        # installed_plugins.json
        (claude_home / "plugins" / "installed_plugins.json").write_text(
            json.dumps({"plugins": installed})
        )
        # marketplace-metadata.json
        meta_path = tmp_path / "marketplace-metadata.json"
        meta_path.write_text(json.dumps(metadata))
        return claude_home, meta_path, platform
    return _make


# ---------- Decision / Action enum shape ----------

def test_action_enum_has_expected_values():
    """Pin the action vocabulary so install.sh stays in sync with the script."""
    expected = {"SKIP_OK", "INSTALL", "REINSTALL", "SKIP_OS_GATE",
                "DRIFT_KEPT", "DRIFT_PRUNED"}
    assert {a.name for a in ps.Action} == expected


def test_decision_is_dataclass():
    d = ps.Decision(action=ps.Action.SKIP_OK, plugin="x@y", current_scope="user", reason="ok")
    assert d.action is ps.Action.SKIP_OK
    assert d.plugin == "x@y"
    assert d.current_scope == "user"
    assert d.reason == "ok"


# ---------- decide() — one plugin at a time ----------

def test_decide_user_scope_skip(make_state):
    claude_home, meta, platform = make_state(
        enabled={"foo@omc": True},
        installed={"foo@omc": [{"scope": "user"}]},
    )
    decisions = ps.plan(claude_home, meta, platform)
    [d] = [x for x in decisions if x.plugin == "foo@omc"]
    assert d.action is ps.Action.SKIP_OK


def test_decide_wrong_scope_reinstall(make_state):
    claude_home, meta, platform = make_state(
        enabled={"foo@omc": True},
        installed={"foo@omc": [{"scope": "project"}]},
    )
    [d] = [x for x in ps.plan(claude_home, meta, platform) if x.plugin == "foo@omc"]
    assert d.action is ps.Action.REINSTALL
    assert d.current_scope == "project"


def test_decide_not_installed_install(make_state):
    claude_home, meta, platform = make_state(
        enabled={"foo@omc": True},
        installed={},
    )
    [d] = [x for x in ps.plan(claude_home, meta, platform) if x.plugin == "foo@omc"]
    assert d.action is ps.Action.INSTALL


# ---------- OS gate ----------

def test_decide_os_gate_skip_linux(make_state):
    # heroacademia marketplace is macOS-only per metadata
    claude_home, meta, _ = make_state(
        enabled={"oh-my-docs@heroacademia": True},
        installed={},
        platform="linux",
    )
    [d] = [x for x in ps.plan(claude_home, meta, "linux")
           if x.plugin == "oh-my-docs@heroacademia"]
    assert d.action is ps.Action.SKIP_OS_GATE


def test_decide_os_gate_pass_macos(make_state):
    claude_home, meta, _ = make_state(
        enabled={"oh-my-docs@heroacademia": True},
        installed={},
        platform="macos",
    )
    [d] = [x for x in ps.plan(claude_home, meta, "macos")
           if x.plugin == "oh-my-docs@heroacademia"]
    assert d.action is ps.Action.INSTALL


# ---------- drift detection ----------

def test_drift_kept_by_default(make_state):
    # Installed at user scope but not in enabledPlugins -> warn-keep
    claude_home, meta, platform = make_state(
        enabled={},
        installed={"orphan@omc": [{"scope": "user"}]},
    )
    decisions = ps.plan(claude_home, meta, platform, prune=False)
    drift = [d for d in decisions if d.plugin == "orphan@omc"]
    assert len(drift) == 1
    assert drift[0].action is ps.Action.DRIFT_KEPT


def test_drift_pruned_with_flag(make_state):
    claude_home, meta, platform = make_state(
        enabled={},
        installed={"orphan@omc": [{"scope": "user"}]},
    )
    decisions = ps.plan(claude_home, meta, platform, prune=True)
    [d] = [x for x in decisions if x.plugin == "orphan@omc"]
    assert d.action is ps.Action.DRIFT_PRUNED


def test_local_settings_protects_from_drift(make_state):
    # Plugin enabled in settings.local.json (per-machine) must not be flagged drift
    claude_home, meta, platform = make_state(
        enabled={},
        installed={"local@omc": [{"scope": "user"}]},
        local_enabled={"local@omc": True},
    )
    decisions = ps.plan(claude_home, meta, platform, prune=True)
    # The plugin must not be flagged as drift; treating it as a normal
    # enabled-and-installed plugin (SKIP_OK) is fine.
    drift = [d for d in decisions if d.plugin == "local@omc"
             and d.action in (ps.Action.DRIFT_KEPT, ps.Action.DRIFT_PRUNED)]
    assert drift == []


# ---------- marketplace registration set ----------

def test_marketplaces_to_register(make_state):
    # When enabled plugins reference @omc and @heroacademia, both marketplaces
    # need to be in the install set (regardless of whether they're already added).
    claude_home, meta, platform = make_state(
        enabled={"foo@omc": True, "bar@heroacademia": True},
        installed={},
        platform="macos",
    )
    needed = ps.marketplaces_to_register(claude_home, meta, "macos")
    assert needed == {"omc", "heroacademia"}


def test_marketplaces_os_gate_filters(make_state):
    claude_home, meta, _ = make_state(
        enabled={"foo@omc": True, "bar@heroacademia": True},
        installed={},
        platform="linux",
    )
    needed = ps.marketplaces_to_register(claude_home, meta, "linux")
    # heroacademia gated out on linux
    assert needed == {"omc"}


# ---------- post-install ----------

def test_post_install_lookup(metadata):
    hooks = ps.post_install_for("foo@omc", metadata)
    assert hooks == ["install_omc_shell_cli"]


def test_post_install_empty_when_not_set(metadata):
    hooks = ps.post_install_for("foo@axlabs", metadata)
    assert hooks == []

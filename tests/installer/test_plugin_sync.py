"""Tests for installer/scripts/plugin_sync.py.

TDD-first: these tests drive the module's API. The function names and
Action enum values here are the spec; implementation must match.

Fixture origin: tests/fixtures/{settings_baseline.json,
installed_plugins_mixed_scopes.json, marketplace_metadata_baseline.json}
are minimal but realistic — they cover the four real action cases observed
in install.sh:259-478 plus the new OS-gate case introduced by G2.1.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "installer" / "scripts"))

import plugin_sync as ps  # noqa: E402
from plugin_sync import Action, Decision  # noqa: E402


FIXTURES = REPO_ROOT / "tests" / "fixtures"


@pytest.fixture
def settings() -> dict:
    return json.loads((FIXTURES / "settings_baseline.json").read_text())


@pytest.fixture
def installed() -> dict:
    return json.loads((FIXTURES / "installed_plugins_mixed_scopes.json").read_text())


@pytest.fixture
def metadata() -> dict:
    return json.loads((FIXTURES / "marketplace_metadata_baseline.json").read_text())


# ─── decide_plugin: single-plugin decision ──────────────────────────────────


def test_decide_user_scope_is_ok(settings, installed):
    """A plugin already at user scope produces Action.OK with no side effects."""
    d = ps.decide_plugin("superpowers@claude-plugins-official", settings, installed)
    assert isinstance(d, Decision)
    assert d.action is Action.OK
    assert d.current_scope == "user"


def test_decide_wrong_scope_triggers_reinstall(settings, installed):
    """project-scope plugin must be uninstalled and reinstalled at user scope."""
    d = ps.decide_plugin("axlabs-mckinsey-pptx@axlabs", settings, installed)
    assert d.action is Action.REINSTALL
    assert d.current_scope == "project"


def test_decide_not_installed_triggers_install(settings, installed):
    """Enabled but empty entries list → fresh install at user scope."""
    d = ps.decide_plugin("oh-my-claudecode@omc", settings, installed)
    assert d.action is Action.INSTALL
    assert d.current_scope == "none"


def test_decide_unknown_plugin_treated_as_not_installed(settings, installed):
    """A plugin in enabledPlugins but absent from installed_plugins.json is INSTALL."""
    d = ps.decide_plugin("oh-my-docs@heroacademia", settings, installed)
    assert d.action is Action.INSTALL
    assert d.current_scope == "none"


# ─── marketplace_allowed_on: OS gate ────────────────────────────────────────


def test_marketplace_allowed_on_macos(metadata):
    """gated-example is macos-only per fixture metadata → allowed on macos."""
    assert ps.marketplace_allowed_on("gated-example", "macos", metadata) is True


def test_marketplace_blocked_on_linux_by_os_gate(metadata):
    """gated-example is macos-only per fixture metadata → blocked on linux."""
    assert ps.marketplace_allowed_on("gated-example", "linux", metadata) is False


def test_heroacademia_allowed_on_all_platforms(metadata):
    """heroacademia (OMD/oms/omp) is cross-platform — installable on every OS."""
    for platform in ("macos", "linux", "windows"):
        assert ps.marketplace_allowed_on("heroacademia", platform, metadata) is True


def test_marketplace_missing_metadata_defaults_to_allowed(metadata):
    """Unknown marketplace → allow (don't block on missing data)."""
    assert ps.marketplace_allowed_on("totally-new", "linux", metadata) is True


# ─── drift detection ────────────────────────────────────────────────────────


def test_drift_finds_user_scope_plugin_not_in_enabled(settings, installed):
    """stray-plugin is user-scope installed but not in enabledPlugins → DRIFT."""
    drifts = ps.find_drift(settings, installed, local_enabled={})
    drift_names = [d.plugin for d in drifts]
    assert "stray-plugin@somewhere" in drift_names
    assert all(d.action is Action.DRIFT for d in drifts)


def test_drift_respects_local_enabledPlugins(settings, installed):
    """A plugin in settings.local.json's enabledPlugins is NOT drift."""
    local = {"stray-plugin@somewhere": True}
    drifts = ps.find_drift(settings, installed, local_enabled=local)
    drift_names = [d.plugin for d in drifts]
    assert "stray-plugin@somewhere" not in drift_names


# ─── plan_actions: full pass ────────────────────────────────────────────────


def test_plan_actions_returns_decision_per_enabled(settings, installed, metadata):
    decisions = ps.plan_actions(
        settings=settings,
        installed=installed,
        metadata=metadata,
        platform="macos",
        local_enabled={},
    )
    plugins = {d.plugin: d.action for d in decisions}
    assert plugins["superpowers@claude-plugins-official"] is Action.OK
    assert plugins["axlabs-mckinsey-pptx@axlabs"] is Action.REINSTALL
    assert plugins["oh-my-claudecode@omc"] is Action.INSTALL
    assert plugins["oh-my-docs@heroacademia"] is Action.INSTALL


def test_plan_actions_installs_heroacademia_on_linux(settings, installed, metadata):
    """heroacademia (OMD/oms/omp) is cross-platform — must INSTALL on linux, not SKIP_OS."""
    decisions = ps.plan_actions(
        settings=settings,
        installed=installed,
        metadata=metadata,
        platform="linux",
        local_enabled={},
    )
    by_plugin = {d.plugin: d for d in decisions}
    d = by_plugin["oh-my-docs@heroacademia"]
    assert d.action is Action.INSTALL


def test_plan_actions_skips_os_gated_marketplace_on_linux(installed, metadata):
    """A macos-only marketplace (gated-example) yields SKIP_OS on linux."""
    gated_settings = {
        "enabledPlugins": {"some-plugin@gated-example": True},
        "extraKnownMarketplaces": {
            "gated-example": {"source": {"source": "github", "repo": "example/gated"}}
        },
    }
    decisions = ps.plan_actions(
        settings=gated_settings,
        installed=installed,
        metadata=metadata,
        platform="linux",
        local_enabled={},
    )
    by_plugin = {d.plugin: d for d in decisions}
    d = by_plugin["some-plugin@gated-example"]
    assert d.action is Action.SKIP_OS
    assert "gated-example" in d.reason.lower() or "linux" in d.reason.lower()


# ─── post-install registry ──────────────────────────────────────────────────


def test_post_install_hooks_resolved_from_metadata(metadata):
    hooks = ps.post_install_hooks_for("oh-my-claudecode@omc", metadata)
    assert hooks == ["install_omc_shell_cli"]


def test_post_install_hooks_empty_when_unspecified(metadata):
    hooks = ps.post_install_hooks_for("superpowers@claude-plugins-official", metadata)
    assert hooks == []

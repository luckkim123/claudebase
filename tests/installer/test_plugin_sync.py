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


# ─── drift is warn-only (installer never removes recipient's own plugins) ────


def test_apply_drift_is_warn_only_never_removed(monkeypatch):
    """A DRIFT decision is reported but NEVER uninstalled — this installer only
    adds recommended plugins and leaves the recipient's own plugins in place."""
    monkeypatch.setattr(
        ps.subprocess, "run",
        lambda *a, **k: pytest.fail("no CLI call expected — drift is warn-only"),
    )
    decisions = [Decision(plugin="stray-plugin@somewhere", action=Action.DRIFT,
                          current_scope="user")]
    log = ps.apply(decisions, dry_run=False)
    joined = "\n".join(log)
    assert "drift (kept): stray-plugin@somewhere" in joined
    assert "1 drift-kept" in joined


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


# ─── update candidates (opt-in --update) ────────────────────────────────────


def test_plan_actions_default_keeps_user_scope_as_ok(settings, installed, metadata):
    """Without update_candidates, a user-scope plugin stays Action.OK (idempotency)."""
    decisions = ps.plan_actions(
        settings=settings, installed=installed, metadata=metadata,
        platform="macos", local_enabled={},
    )
    by_plugin = {d.plugin: d for d in decisions}
    assert by_plugin["superpowers@claude-plugins-official"].action is Action.OK


def test_plan_actions_update_flag_turns_user_scope_into_update(settings, installed, metadata):
    """With update_candidates=True, an enabled user-scope plugin becomes Action.UPDATE."""
    decisions = ps.plan_actions(
        settings=settings, installed=installed, metadata=metadata,
        platform="macos", local_enabled={}, update_candidates=True,
    )
    by_plugin = {d.plugin: d for d in decisions}
    assert by_plugin["superpowers@claude-plugins-official"].action is Action.UPDATE


def test_update_flag_does_not_touch_install_or_reinstall(settings, installed, metadata):
    """update_candidates only re-labels user-scope OK; INSTALL/REINSTALL are unchanged."""
    decisions = ps.plan_actions(
        settings=settings, installed=installed, metadata=metadata,
        platform="macos", local_enabled={}, update_candidates=True,
    )
    by_plugin = {d.plugin: d for d in decisions}
    # not-installed stays INSTALL, never UPDATE (you can't update what isn't there)
    assert by_plugin["oh-my-claudecode@omc"].action is Action.INSTALL
    # wrong-scope stays REINSTALL (scope fix takes priority over update)
    assert by_plugin["axlabs-mckinsey-pptx@axlabs"].action is Action.REINSTALL


# ─── apply: UPDATE handling (dry-run only — no subprocess) ───────────────────


def test_apply_dry_run_update_emits_would_update():
    """dry_run apply of an UPDATE decision logs 'would update', runs no subprocess."""
    decisions = [Decision(plugin="superpowers@claude-plugins-official",
                          action=Action.UPDATE, current_scope="user",
                          reason="--update requested")]
    log = ps.apply(decisions, dry_run=True)
    joined = "\n".join(log)
    assert "would update" in joined
    assert "superpowers@claude-plugins-official" in joined


def test_apply_summary_counts_update_separately():
    """The summary line reports the update count so the user sees how many ran."""
    decisions = [
        Decision(plugin="a@m", action=Action.UPDATE, current_scope="user"),
        Decision(plugin="b@m", action=Action.UPDATE, current_scope="user"),
        Decision(plugin="c@m", action=Action.OK, current_scope="user"),
    ]
    log = ps.apply(decisions, dry_run=True)
    summary = log[-1]
    assert "2 updated" in summary


# ─── post-install registry ──────────────────────────────────────────────────


def test_post_install_hooks_resolved_from_metadata(metadata):
    hooks = ps.post_install_hooks_for("oh-my-claudecode@omc", metadata)
    assert hooks == ["install_omc_shell_cli"]


def test_post_install_hooks_empty_when_unspecified(metadata):
    hooks = ps.post_install_hooks_for("superpowers@claude-plugins-official", metadata)
    assert hooks == []

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


# ─── marketplace-migration drift (suffix-blind CLI uninstall guard) ──────────
#
# When a plugin migrates marketplaces (e.g. oh-my-experiments@omx → @heroacademia),
# a machine set up BEFORE the migration carries the stale @omx install as drift
# while @heroacademia is the enabled one. `claude plugin uninstall <name>@omx` is
# suffix-blind — it matches on the bare plugin name and removes the @heroacademia
# entry instead, breaking a healthy plugin. These tests pin the guard: a drift
# whose BASE name is still enabled under a different marketplace must NOT go
# through the CLI uninstall path.


def test_base_name_strips_marketplace_suffix():
    assert ps.base_name("oh-my-experiments@omx") == "oh-my-experiments"
    assert ps.base_name("oh-my-experiments@heroacademia") == "oh-my-experiments"
    assert ps.base_name("no-suffix") == "no-suffix"


def test_drift_collides_when_base_enabled_under_other_marketplace():
    """@omx drift collides because @heroacademia (same base) is enabled."""
    settings = {"enabledPlugins": {"oh-my-experiments@heroacademia": True}}
    assert ps.drift_collides_with_enabled(
        "oh-my-experiments@omx", settings, local_enabled={}
    )


def test_drift_does_not_collide_when_base_not_enabled_elsewhere():
    """A genuinely orphaned drift (no same-base enabled) does NOT collide."""
    settings = {"enabledPlugins": {"superpowers@claude-plugins-official": True}}
    assert not ps.drift_collides_with_enabled(
        "stray-plugin@somewhere", settings, local_enabled={}
    )


def test_drift_collision_respects_local_enabled():
    """A same-base plugin enabled only in settings.local.json still counts."""
    settings = {"enabledPlugins": {}}
    local = {"oh-my-experiments@heroacademia": True}
    assert ps.drift_collides_with_enabled(
        "oh-my-experiments@omx", settings, local_enabled=local
    )


def test_apply_prune_colliding_drift_avoids_cli_uninstall(monkeypatch):
    """A colliding drift must be removed WITHOUT calling `claude plugin uninstall`
    (which would clobber the same-base enabled plugin). It is excised directly
    from installed_plugins.json instead."""
    settings = {"enabledPlugins": {"oh-my-experiments@heroacademia": True}}
    calls = []
    monkeypatch.setattr(
        ps.subprocess, "run",
        lambda *a, **k: calls.append(a[0]) or _FakeProc(0),
    )
    excised = []
    monkeypatch.setattr(
        ps, "excise_installed_plugin",
        lambda plugin: excised.append(plugin) or True,
    )
    decisions = [Decision(plugin="oh-my-experiments@omx", action=Action.DRIFT,
                          current_scope="user")]
    log = ps.apply(decisions, dry_run=False, prune=True, settings=settings)
    joined = "\n".join(log)
    assert excised == ["oh-my-experiments@omx"]
    assert not any("uninstall" in c for c in calls), \
        f"CLI uninstall must be skipped for colliding drift, got: {calls}"
    assert "oh-my-experiments@omx" in joined


def test_apply_prune_noncolliding_drift_uses_cli_uninstall(monkeypatch):
    """A non-colliding (genuinely orphan) drift still uses the normal CLI path."""
    settings = {"enabledPlugins": {"superpowers@claude-plugins-official": True}}
    calls = []
    monkeypatch.setattr(
        ps.subprocess, "run",
        lambda *a, **k: calls.append(a[0]) or _FakeProc(0),
    )
    decisions = [Decision(plugin="stray-plugin@somewhere", action=Action.DRIFT,
                          current_scope="user")]
    log = ps.apply(decisions, dry_run=False, prune=True, settings=settings)
    assert any("uninstall" in c for c in calls), \
        "non-colliding drift should use the CLI uninstall path"


def test_apply_colliding_drift_auto_heals_without_prune(monkeypatch):
    """THE migration-safety contract: a recipient who knows nothing of the
    marketplace migration runs a PLAIN install.sh (prune=False) and the stale
    @omx drift is auto-excised anyway, because it collides with the enabled
    @heroacademia. A genuine orphan in the same run stays warn-only."""
    settings = {"enabledPlugins": {"oh-my-experiments@heroacademia": True}}
    excised = []
    monkeypatch.setattr(
        ps, "excise_installed_plugin",
        lambda plugin: excised.append(plugin) or True,
    )
    monkeypatch.setattr(
        ps.subprocess, "run",
        lambda *a, **k: pytest.fail("no CLI call expected for collision auto-heal"),
    )
    decisions = [
        Decision(plugin="oh-my-experiments@omx", action=Action.DRIFT, current_scope="user"),
        Decision(plugin="stray-plugin@somewhere", action=Action.DRIFT, current_scope="user"),
    ]
    log = ps.apply(decisions, dry_run=False, prune=False, settings=settings)
    joined = "\n".join(log)
    # collision → auto-healed even without --prune
    assert excised == ["oh-my-experiments@omx"]
    assert "auto-healed" in joined
    # genuine orphan → still warn-only (not excised, not uninstalled)
    assert "drift (kept): stray-plugin@somewhere" in joined
    # summary reflects 1 removed (the collision) + 1 kept (the orphan)
    assert "1 removed" in joined
    assert "1 drift-kept" in joined


def test_migration_drift_auto_heals_end_to_end_via_plan_and_apply(monkeypatch):
    """Integration: a stale @old install whose @new twin is enabled ONLY in
    settings.local.json must self-heal through the real plan_actions→apply flow
    (not just the unit-level collision function). Closes the M2 coverage gap."""
    settings = {"enabledPlugins": {}}
    local_enabled = {"oh-my-experiments@heroacademia": True}
    installed = {"plugins": {
        "oh-my-experiments@omx": [{"scope": "user"}],
        "oh-my-experiments@heroacademia": [{"scope": "user"}],
    }}
    metadata = {}
    decisions = ps.plan_actions(settings, installed, metadata, platform="macos",
                                local_enabled=local_enabled)
    drift = [d for d in decisions if d.action is Action.DRIFT]
    assert [d.plugin for d in drift] == ["oh-my-experiments@omx"], \
        "only the stale @omx should be drift; the local-enabled @heroacademia is not"
    excised = []
    monkeypatch.setattr(ps, "excise_installed_plugin",
                        lambda p: excised.append(p) or True)
    monkeypatch.setattr(ps.subprocess, "run",
                        lambda *a, **k: pytest.fail("no CLI call for collision heal"))
    log = ps.apply(decisions, dry_run=False, prune=False,
                   settings=settings, local_enabled=local_enabled)
    assert excised == ["oh-my-experiments@omx"]
    assert "auto-healed" in "\n".join(log)


def test_failed_excise_counts_as_failed_not_removed(monkeypatch):
    """A failed excise must NOT report as `removed` (else a stuck heal reads as a
    regression on the next sync). It is counted under `failed` instead."""
    settings = {"enabledPlugins": {"oh-my-experiments@heroacademia": True}}
    monkeypatch.setattr(ps, "excise_installed_plugin", lambda p: False)
    decisions = [Decision(plugin="oh-my-experiments@omx", action=Action.DRIFT,
                          current_scope="user")]
    summary = ps.apply(decisions, dry_run=False, prune=False, settings=settings)[-1]
    assert "0 removed" in summary
    assert "1 failed" in summary


class _FakeProc:
    def __init__(self, rc):
        self.returncode = rc
        self.stdout = ""


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
    log = ps.apply(decisions, dry_run=True, prune=False)
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
    log = ps.apply(decisions, dry_run=True, prune=False)
    summary = log[-1]
    assert "2 updated" in summary


# ─── post-install registry ──────────────────────────────────────────────────


def test_post_install_hooks_resolved_from_metadata(metadata):
    hooks = ps.post_install_hooks_for("oh-my-claudecode@omc", metadata)
    assert hooks == ["install_omc_shell_cli"]


def test_post_install_hooks_empty_when_unspecified(metadata):
    hooks = ps.post_install_hooks_for("superpowers@claude-plugins-official", metadata)
    assert hooks == []

"""Tests for installer/scripts/render_settings.py.

The regression these pin down: `~/.claude/settings.local.json` was documented
as the per-machine layer but Claude Code never read it, so everything recorded
there — plugin enablement, `model`, `effortLevel` — was inert, and a blanket
`git checkout -- config/settings.json` wiped the enablement that was really
living in the tracked baseline. Rendering the merge is what makes the promised
layer real, so the merge/capture semantics are the thing worth testing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "installer" / "scripts"))

import render_settings as rs

def without_state_dir(settings: dict) -> dict:
    """Drop the render-time `env.OMC_STATE_DIR` default.

    `main()` injects it from `$HOME` (see `with_omc_state_dir`), which is a fact
    about the machine rather than an outcome of the merge — so the tests that
    assert the merge itself strip it instead of pinning one user's home path.
    """
    out = {k: v for k, v in settings.items() if k != "env"}
    env = {k: v for k, v in (settings.get("env") or {}).items() if k != "OMC_STATE_DIR"}
    if env:
        out["env"] = env
    return out


# A realistic slice of the lab baseline: one common plugin plus a scalar block,
# which is enough to exercise both merge modes.
BASE = {
    "enabledPlugins": {"superpowers@official": True},
    "permissions": {"defaultMode": "auto"},
}


class TestDeepMerge:
    def test_override_wins_on_scalar(self):
        assert rs.deep_merge({"model": "sonnet"}, {"model": "opus"}) == {"model": "opus"}

    def test_nested_dict_merges_key_by_key(self):
        # The whole point: a per-machine plugin ADDS to the baseline map.
        base = {"enabledPlugins": {"superpowers@official": True}}
        local = {"enabledPlugins": {"claude-mem@thedotmack": True}}
        assert rs.deep_merge(base, local)["enabledPlugins"] == {
            "superpowers@official": True,
            "claude-mem@thedotmack": True,
        }

    def test_list_is_replaced_not_concatenated(self):
        assert rs.deep_merge({"a": [1, 2]}, {"a": [3]}) == {"a": [3]}

    def test_base_is_not_mutated(self):
        base = {"enabledPlugins": {"x": True}}
        rs.deep_merge(base, {"enabledPlugins": {"y": True}})
        assert base == {"enabledPlugins": {"x": True}}


class TestDiffOverrides:
    def test_captures_only_the_new_nested_entry(self):
        # Must not freeze the whole baseline map into the per-machine file,
        # or later baseline updates would stop propagating.
        expected = {"enabledPlugins": {"superpowers@official": True}}
        existing = {
            "enabledPlugins": {"superpowers@official": True, "remotion@remotion": True}
        }
        assert rs.diff_overrides(existing, expected) == {
            "enabledPlugins": {"remotion@remotion": True}
        }

    def test_captures_changed_scalar(self):
        assert rs.diff_overrides({"model": "opus"}, {"model": "sonnet"}) == {"model": "opus"}

    def test_identical_input_captures_nothing(self):
        settings = {"model": "opus", "enabledPlugins": {"a": True}}
        assert rs.diff_overrides(settings, settings) == {}

    def test_missing_key_is_not_an_override(self):
        # Baseline is authoritative: a key absent from the live file means the
        # baseline dropped it, not that the machine wants it gone.
        assert rs.diff_overrides({}, {"model": "sonnet"}) == {}


class TestPlan:
    def test_local_plugin_reaches_the_render(self):
        # The original bug, stated as a test: an opt-in plugin recorded per
        # machine must actually be enabled in the file Claude Code reads.
        local = {"enabledPlugins": {"claude-mem@thedotmack": True}}
        rendered, _ = rs.plan(BASE, local, existing=None)
        assert rendered["enabledPlugins"]["claude-mem@thedotmack"] is True
        assert rendered["enabledPlugins"]["superpowers@official"] is True

    def test_cli_written_pref_is_captured_and_survives(self):
        # `/model opus` lands in the rendered file; the next install run must
        # move it into settings.local.json rather than clobber it.
        existing = rs.deep_merge(BASE, {"model": "opus"})
        rendered, new_local = rs.plan(BASE, {}, existing=existing)
        assert new_local["model"] == "opus"
        assert rendered["model"] == "opus"

    def test_cli_enabled_plugin_is_captured(self):
        existing = rs.deep_merge(BASE, {"enabledPlugins": {"remotion@remotion": True}})
        _, new_local = rs.plan(BASE, {}, existing=existing)
        assert new_local["enabledPlugins"] == {"remotion@remotion": True}

    def test_installer_only_keys_never_reach_the_render(self):
        local = {
            "_comment": "docs",
            "_optional_plugins_note": "docs",
            "personalRepos": ["~/x"],
            "model": "opus",
        }
        rendered, _ = rs.plan(BASE, local, existing=None)
        assert "_comment" not in rendered
        assert "_optional_plugins_note" not in rendered
        assert "personalRepos" not in rendered
        assert rendered["model"] == "opus"

    def test_nested_template_placeholder_is_stripped(self):
        # The shipped template ships `enabledPlugins._remove_this_example`;
        # a machine that copies it verbatim must not get a bogus plugin id.
        local = {"enabledPlugins": {"_remove_this_example": False, "remotion@remotion": True}}
        rendered, _ = rs.plan(BASE, local, existing=None)
        assert "_remove_this_example" not in rendered["enabledPlugins"]
        assert rendered["enabledPlugins"]["remotion@remotion"] is True

    def test_is_idempotent(self):
        local = {"model": "opus"}
        rendered, new_local = rs.plan(BASE, local, existing=None)
        again, again_local = rs.plan(BASE, new_local, existing=rendered)
        assert again == rendered
        assert again_local == new_local

    def test_baseline_update_still_propagates_after_capture(self):
        # Capture must not shadow the baseline: adding a plugin to the lab file
        # has to reach a machine that previously captured a different one.
        existing = rs.deep_merge(BASE, {"enabledPlugins": {"remotion@remotion": True}})
        _, new_local = rs.plan(BASE, {}, existing=existing)
        grown = {"enabledPlugins": {"superpowers@official": True, "ponytail@ponytail": True}}
        rendered, _ = rs.plan(grown, new_local, existing=None)
        assert rendered["enabledPlugins"]["ponytail@ponytail"] is True
        assert rendered["enabledPlugins"]["remotion@remotion"] is True

    def test_new_baseline_hook_is_not_shadowed_by_the_previous_render(self):
        # Adding a hook to the baseline must reach a machine whose previous
        # render predates it. `hooks` values are lists, so a captured old list
        # would REPLACE the new one on merge and silence the hook forever —
        # observed 2026-08-10 with the graphify guards.
        base = {**BASE, "hooks": {"PreToolUse": [{"matcher": "A"}, {"matcher": "B"}]}}
        existing = {**BASE, "hooks": {"PreToolUse": [{"matcher": "A"}]}}
        rendered, new_local = rs.plan(base, {}, existing=existing)
        assert rendered["hooks"] == base["hooks"]
        assert "hooks" not in new_local

    def test_cli_shrunk_hooks_never_become_a_per_machine_override(self):
        # The CLI drops hook blocks it does not recognise. Capturing that would
        # freeze the shrunk list into settings.local.json, which is precisely
        # what settings.critical.json's hookMarkers exist to prevent.
        base = {**BASE, "hooks": {"PreToolUse": [{"matcher": "A"}]}}
        existing = {**BASE, "hooks": {}}
        rendered, new_local = rs.plan(base, {}, existing=existing)
        assert rendered["hooks"] == base["hooks"]
        assert "hooks" not in new_local


class TestMainRoundTrip:
    def test_replaces_symlink_with_rendered_file(self, tmp_path):
        base = tmp_path / "settings.json"
        base.write_text(json.dumps({"enabledPlugins": {"a@m": True}}))
        local = tmp_path / "settings.local.json"
        local.write_text(json.dumps({"model": "opus"}))
        out = tmp_path / "home-settings.json"
        out.symlink_to(base)

        assert rs.main(["--base", str(base), "--local", str(local), "--out", str(out)]) == 0

        assert not out.is_symlink()
        merged = json.loads(out.read_text())
        assert without_state_dir(merged) == {"enabledPlugins": {"a@m": True}, "model": "opus"}
        # The baseline must come through untouched by the render.
        assert json.loads(base.read_text()) == {"enabledPlugins": {"a@m": True}}

    def test_captures_into_local_file_on_disk(self, tmp_path):
        base = tmp_path / "settings.json"
        base.write_text(json.dumps({"enabledPlugins": {"a@m": True}}))
        local = tmp_path / "settings.local.json"
        local.write_text(json.dumps({"_comment": "keep me"}))
        out = tmp_path / "home-settings.json"
        out.write_text(json.dumps({"enabledPlugins": {"a@m": True}, "theme": "dark"}))

        rs.main(["--base", str(base), "--local", str(local), "--out", str(out)])

        captured = json.loads(local.read_text())
        assert captured["theme"] == "dark"
        assert captured["_comment"] == "keep me"
        assert "theme" not in json.loads(base.read_text())

    def test_missing_local_file_is_fine(self, tmp_path):
        base = tmp_path / "settings.json"
        base.write_text(json.dumps({"model": "sonnet"}))
        out = tmp_path / "home-settings.json"

        rs.main([
            "--base", str(base),
            "--local", str(tmp_path / "absent.json"),
            "--out", str(out),
        ])

        assert without_state_dir(json.loads(out.read_text())) == {"model": "sonnet"}

    def test_second_run_is_silent_and_writes_nothing(self, tmp_path, capsys):
        # tests/smoke/test_install_idempotent.sh fails the build on a `rendered:`
        # line in a second run, and lib/link.sh derives that line from this
        # script's output — so a no-op must print nothing at all.
        base = tmp_path / "settings.json"
        base.write_text(json.dumps({"model": "sonnet"}))
        local = tmp_path / "settings.local.json"
        local.write_text(json.dumps({"theme": "dark"}))
        out = tmp_path / "home-settings.json"
        argv = ["--base", str(base), "--local", str(local), "--out", str(out)]

        rs.main(argv)
        capsys.readouterr()
        first = out.read_text()

        assert rs.main(argv) == 0
        assert capsys.readouterr().out == ""
        assert out.read_text() == first

    def test_dry_run_writes_nothing(self, tmp_path):
        base = tmp_path / "settings.json"
        base.write_text(json.dumps({"model": "sonnet"}))
        out = tmp_path / "home-settings.json"

        rs.main([
            "--base", str(base),
            "--local", str(tmp_path / "absent.json"),
            "--out", str(out),
            "--dry-run",
        ])

        assert not out.exists()


class TestOmcStateDir:
    """`env.OMC_STATE_DIR` is resolved at render time, never tracked.

    Two things make the tracked forms wrong: `~`/`$HOME` do not expand in the
    `env` block, and OMC joins the value verbatim — so a literal `~` creates a
    directory *named* `~`. An absolute path cannot be tracked either, since this
    repo ships to every machine.
    """

    def test_absolute_and_under_home(self):
        value = rs.with_omc_state_dir({})["env"]["OMC_STATE_DIR"]
        assert Path(value).is_absolute()
        assert "~" not in value
        assert value.startswith(str(Path.home()))

    def test_does_not_disturb_other_env_keys(self):
        out = rs.with_omc_state_dir({"env": {"GRAPHIFY_OUT": ".graphify"}})
        assert out["env"]["GRAPHIFY_OUT"] == ".graphify"
        assert "OMC_STATE_DIR" in out["env"]

    def test_is_only_a_default(self):
        out = rs.with_omc_state_dir({"env": {"OMC_STATE_DIR": "/pinned"}})
        assert out["env"]["OMC_STATE_DIR"] == "/pinned"

    def test_leaves_the_input_untouched(self):
        base = {"env": {"GRAPHIFY_OUT": ".graphify"}}
        rs.with_omc_state_dir(base)
        assert base == {"env": {"GRAPHIFY_OUT": ".graphify"}}

    def test_local_layer_still_wins_through_main(self, tmp_path):
        base = tmp_path / "settings.json"
        base.write_text(json.dumps({"model": "sonnet"}))
        local = tmp_path / "settings.local.json"
        local.write_text(json.dumps({"env": {"OMC_STATE_DIR": "/elsewhere"}}))
        out = tmp_path / "home-settings.json"

        rs.main(["--base", str(base), "--local", str(local), "--out", str(out)])

        assert json.loads(out.read_text())["env"]["OMC_STATE_DIR"] == "/elsewhere"


class TestDroppedHookCommands:
    """Foreign hooks are discarded by design; discarding them silently is the bug.

    `hooks` is in BASELINE_OWNED_KEYS, so anything a third party wrote straight
    into the rendered file (an IDE integration, an MCP installer, `tokensave
    install`) is dropped rather than captured. The user has to be told, because
    the tool that owns the hook simply stops working with nothing to point at.
    """

    @staticmethod
    def _settings(*commands):
        return {
            "hooks": {
                "PreToolUse": [{"hooks": [{"command": c} for c in commands]}]
            }
        }

    def test_reports_a_command_the_render_removes(self):
        existing = self._settings("ours", "sh ~/.foreign/hook.sh")
        rendered = self._settings("ours")
        assert rs.dropped_hook_commands(existing, rendered) == ["sh ~/.foreign/hook.sh"]

    def test_silent_when_nothing_is_lost(self):
        same = self._settings("ours")
        assert rs.dropped_hook_commands(same, same) == []

    def test_a_hook_that_only_moved_events_is_not_reported(self):
        existing = {"hooks": {"Stop": [{"hooks": [{"command": "ours"}]}]}}
        rendered = {"hooks": {"SessionStart": [{"hooks": [{"command": "ours"}]}]}}
        assert rs.dropped_hook_commands(existing, rendered) == []

    def test_no_previous_render_reports_nothing(self):
        assert rs.dropped_hook_commands(None, self._settings("ours")) == []

    def test_tolerates_settings_without_hooks(self):
        assert rs.dropped_hook_commands({"model": "opus"}, {"model": "opus"}) == []

    def test_main_warns_on_stdout(self, tmp_path, capsys):
        base = tmp_path / "settings.json"
        base.write_text(json.dumps(self._settings("ours")))
        out = tmp_path / "home-settings.json"
        out.write_text(json.dumps(self._settings("ours", "sh ~/.foreign/hook.sh")))

        rs.main([
            "--base", str(base),
            "--local", str(tmp_path / "absent.json"),
            "--out", str(out),
        ])

        printed = capsys.readouterr().out
        assert "dropped 1 hook command(s)" in printed
        assert "sh ~/.foreign/hook.sh" in printed

    def test_dry_run_warns_too(self, tmp_path, capsys):
        # A dry-run is what someone reads *before* deciding to render, so this is
        # the mode where the warning matters most. It was missing at first.
        base = tmp_path / "settings.json"
        base.write_text(json.dumps(self._settings("ours")))
        out = tmp_path / "home-settings.json"
        out.write_text(json.dumps(self._settings("ours", "sh ~/.foreign/hook.sh")))
        before = out.read_text()

        rs.main([
            "--base", str(base),
            "--local", str(tmp_path / "absent.json"),
            "--out", str(out),
            "--dry-run",
        ])

        printed = capsys.readouterr().out
        assert "would drop 1 hook command(s)" in printed
        assert out.read_text() == before  # still a dry run

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
        assert merged == {"enabledPlugins": {"a@m": True}, "model": "opus"}
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

        assert json.loads(out.read_text()) == {"model": "sonnet"}

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

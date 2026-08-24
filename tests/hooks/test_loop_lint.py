"""Tests for runtime/hooks/loop_lint.py.

The linter is a keyword matcher over skill prose, which is the kind of scorer
that fails silently — it produces a clean table whatever the input. So every
test here is a known-good / known-bad pair: a fixture that must score every
contract check, and one that must score none of them. A matcher that has
drifted into matching everything fails the second half.

The shim test is the one that matters most in practice. omc, oms and omd
register a ~12-line `skills/<n>/SKILL.md` that points at
`skill-bodies/<n>/SKILL.md`; a linter reading only the registered file scores
those loops as failing everything and reports no error while doing it.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / "runtime" / "hooks" / "loop_lint.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("loop_lint", HOOK_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load_module()


def _scores(text: str) -> dict:
    """{check name: matched?} — the row the table would print."""
    return {name: MOD.first_hit(text, rx)[0] is not None for name, rx in MOD._CHECKS}


KNOWN_GOOD = """
Loop state lives at `.omc/state/sessions/{sessionId}/prd.json`, with a running
log in progress.txt.
Stop when every story has passes: true and the reviewer returns PASS.
Give up after 3 rounds of the same defect, then stop and report to the user.
Verification: Task(subagent_type="oh-my-claudecode:architect", ...).
Completion is read from state, not judged: stop when the unresolved count in
prd.json reaches zero, and record it as "0 of 12 stories" so the zero can be read
rather than trusted.
Before round 1, `wiki query` the workspace for prior evidence on this defect so a
known cause is not re-derived.
"""

KNOWN_BAD = """
Keep iterating on the document until it looks good.
Use your own judgement about when the work is finished.
Write back to the person who asked once everything is handled.
Always pass the model parameter explicitly, and pass it to the next stage.
"""


def test_known_good_scores_every_check():
    assert all(_scores(KNOWN_GOOD).values()), _scores(KNOWN_GOOD)


def test_known_bad_scores_none():
    """The half that catches a matcher which has drifted into matching all prose."""
    assert not any(_scores(KNOWN_BAD).values()), _scores(KNOWN_BAD)


def test_the_verb_pass_is_not_a_stop_condition():
    """Measured 2026-08-15: a case-insensitive \\bPASS\\b credited ultragoal,
    ultrawork and exp-loop with a deterministic stop they never state, on lines
    that read 'Always pass the model parameter'."""
    assert not _scores("Always pass the `model` parameter explicitly.")["stop"]
    assert not _scores("Pass it to exp-analyze when you delegate.")["stop"]
    assert _scores("Terminate when doc-verifier returns PASS.")["stop"]
    assert _scores("Cycle until all tests pass.")["stop"]


def test_known_bad_is_flagged_for_model_confidence():
    line_no, line = MOD.first_hit(KNOWN_BAD, MOD._SOFT_RE)
    assert line_no is not None and "looks good" in line


def test_soft_phrasing_is_a_note_not_a_failure():
    """Ralph carries 'looks good' inside a <Bad> example. If the soft probe were
    wired as a check, that example would fail the skill that forbids it."""
    text = KNOWN_GOOD + "\n<Bad>\nAll the changes look good. Task complete.\n</Bad>\n"
    assert all(_scores(text).values())
    assert MOD.first_hit(text, MOD._SOFT_RE)[0] is not None


# ─── the shim trap ──────────────────────────────────────────────────────────

SHIM = """---
name: sample-revise
description: Loop until PASS. Stops and reports if the same defect recurs 3 times.
---
Compact registry shim; read the body from skill-bodies/sample-revise/SKILL.md.
"""

BODY = """
Round state is written to `.omd/{slug}/rounds.json`.
Each round: Task(subagent_type="oh-my-docs:doc-verifier") re-verifies.
The unresolved count is read from state, and rounds.json records "0 of 9 checks"
beside it so an empty result is legible.
Each round opens with a `wiki read` of the convention page for prior diagnoses.
"""


def _plugin(tmp_path: Path, *, with_body: bool) -> Path:
    root = tmp_path / "oh-my-sample"
    (root / "skills" / "sample-revise").mkdir(parents=True)
    (root / "skills" / "sample-revise" / "SKILL.md").write_text(SHIM)
    if with_body:
        (root / "skill-bodies" / "sample-revise").mkdir(parents=True)
        (root / "skill-bodies" / "sample-revise" / "SKILL.md").write_text(BODY)
    return root


def test_shim_alone_misses_state_and_verifier(tmp_path):
    text, paths = MOD.skill_text(_plugin(tmp_path, with_body=False), "sample-revise")
    scored = _scores(text)
    assert len(paths) == 1
    assert not scored["state"] and not scored["verif"]


def test_shim_plus_body_scores_all(tmp_path):
    """Same skill, same host, one extra file read — misses become hits."""
    text, paths = MOD.skill_text(_plugin(tmp_path, with_body=True), "sample-revise")
    assert len(paths) == 2
    assert all(_scores(text).values()), _scores(text)


def test_discovery_covers_a_loop_whose_name_does_not_say_loop(tmp_path):
    """omp-garden is a periodic sweep with state and an escalation cap. A
    name-shaped rule that missed it would print a table that looks complete."""
    root = tmp_path / "oh-my-project"
    (root / "skills" / "omp-garden").mkdir(parents=True)
    (root / "skills" / "omp-garden" / "SKILL.md").write_text(KNOWN_GOOD)
    found = MOD.loop_skills({"oh-my-project": root})
    assert [s for _, s, _, _ in found] == ["omp-garden"]


def test_loop_skills_finds_only_loop_shaped_skills(tmp_path):
    root = _plugin(tmp_path, with_body=True)
    (root / "skills" / "sample-build").mkdir(parents=True)
    (root / "skills" / "sample-build" / "SKILL.md").write_text("not a loop\n")
    found = MOD.loop_skills({"oh-my-sample": root})
    assert [(p, s) for p, s, _, _ in found] == [("oh-my-sample", "sample-revise")]


# ─── state paths and activity ───────────────────────────────────────────────

def test_state_paths_wildcards_placeholders_and_drops_documents():
    text = ("`.omc/state/sessions/{sessionId}/prd.json` and "
            "`runs/<run_id>/pending-launch.json`, see README.md and SKILL.md, "
            "plus progress.txt")
    got = MOD.state_paths(text)
    assert ".omc/state/sessions/*/prd.json" in got
    assert "runs/*/pending-launch.json" in got
    assert "progress.txt" in got
    assert not any("README" in p or "SKILL" in p for p in got)


def test_activity_counts_only_what_exists(tmp_path):
    hits, newest, example = MOD.activity([".omc/state/sessions/*/prd.json"], [tmp_path])
    assert (hits, newest, example) == (0, None, "")

    target = tmp_path / ".omc" / "state" / "sessions" / "abc"
    target.mkdir(parents=True)
    (target / "prd.json").write_text("{}")
    hits, newest, example = MOD.activity([".omc/state/sessions/*/prd.json"], [tmp_path])
    assert hits == 1 and newest is not None and example.endswith("prd.json")


def test_activity_falls_back_to_a_deep_search(tmp_path):
    """omx state lands under an output tree, not the project root. Without the
    fallback a live loop reads as scaffolding."""
    deep = tmp_path / "out" / "exp" / "runs" / "r1"
    deep.mkdir(parents=True)
    (deep / "pending-launch.json").write_text("{}")
    hits, _, example = MOD.activity(["runs/*/pending-launch.json"], [tmp_path])
    assert hits == 1 and "out/exp/runs/r1" in example


# ─── manifests and blocking ─────────────────────────────────────────────────

def test_hook_entries_reads_both_manifest_shapes(tmp_path):
    """heroacademia declares hooks in plugin.json (command + args); omc ships
    hooks/hooks.json with the whole invocation in command. Supporting one shape
    reports the other plugin as hookless."""
    root = tmp_path / "oh-my-sample"
    (root / ".claude-plugin").mkdir(parents=True)
    (root / "hooks").mkdir()
    (root / "scripts").mkdir()
    (root / "hooks" / "gate.py").write_text("import sys\nsys.exit(2)\n")
    (root / "scripts" / "emit.mjs").write_text("console.log('hi')\n")

    (root / ".claude-plugin" / "plugin.json").write_text(json.dumps({
        "name": "oh-my-sample",
        "hooks": {"Stop": [{"hooks": [{
            "type": "command", "command": "python3",
            "args": ["${CLAUDE_PLUGIN_ROOT}/hooks/gate.py"]}]}]},
    }))
    (root / "hooks" / "hooks.json").write_text(json.dumps({
        "hooks": {"UserPromptSubmit": [{"hooks": [{
            "type": "command",
            "command": 'node "$CLAUDE_PLUGIN_ROOT"/scripts/emit.mjs'}]}]},
    }))

    entries = MOD.hook_entries(root)
    by_event = {event: (script, MOD.blocks(script)) for event, script, _ in entries}
    assert by_event["Stop"][0].name == "gate.py"
    assert by_event["Stop"][1] == "yes"
    assert by_event["UserPromptSubmit"][1] == "no"


def test_blocks_is_unknown_when_the_script_is_missing():
    assert MOD.blocks(None) == "?"


def test_dispatcher_hook_is_followed_one_hop(tmp_path):
    """omx wires every event to run_hook.py, which importlib-loads handlers.py;
    the blocking `{"decision": "block"}` is in the handler. Grepping only the
    named file reported the one loop plugin with a real Stop gate as having
    none."""
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    dispatcher = hooks / "run_hook.py"
    dispatcher.write_text("import importlib.util\n# loads a handler by name\n")
    (hooks / "handlers.py").write_text('return {"decision": "block"}\n')
    assert MOD.blocks(dispatcher) == "via"


def test_advisory_guard_stays_no_even_with_a_blocking_sibling(tmp_path):
    """docs_stop_guard.py says outright it never blocks. Widening the sibling
    search to every hook would replace a right row with a wrong one."""
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    guard = hooks / "docs_stop_guard.py"
    guard.write_text("# strictly advisory: never decision block\nprint('hi')\n")
    (hooks / "docs_model_guard.py").write_text('{"permissionDecision": "deny"}\n')
    assert MOD.blocks(guard) == "no"


def test_installed_plugins_keeps_only_om_plugins(tmp_path, monkeypatch):
    """A machine runs a dozen third-party plugins; the contract is ours."""
    ours = tmp_path / "oh-my-sample"
    theirs = tmp_path / "remotion"
    ours.mkdir()
    theirs.mkdir()
    record = tmp_path / "installed_plugins.json"
    record.write_text(json.dumps({"plugins": {
        "oh-my-sample@heroacademia": [{"installPath": str(ours)}],
        "remotion@remotion": [{"installPath": str(theirs)}],
    }}))
    monkeypatch.setattr(MOD, "_INSTALLED", record)
    assert list(MOD.installed_plugins()) == ["oh-my-sample"]


def test_report_runs_on_an_empty_machine(tmp_path, monkeypatch):
    """No plugins installed must print a table, not raise."""
    monkeypatch.setattr(MOD, "_INSTALLED", tmp_path / "missing.json")
    out = MOD.report([tmp_path])
    assert "no loop-shaped skills found" in out
    assert "[B] enforcement surface" in out

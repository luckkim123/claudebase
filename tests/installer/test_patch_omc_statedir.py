"""Tests for installer/scripts/patch_omc_statedir.sh.

The patch is applied to a mock OMC dist tree (CLAUDE_CONFIG_DIR pointed at a
tmp dir) so tests never touch the live install. The stub worktree-paths.js
mirrors the real ESM shape: it has the duplicate anchor line in TWO functions
(getProjectIdentifier-like and getOmcRoot) so the test proves the patch only
rewrites the getOmcRoot fallback (the one followed by `return join(root,
OmcPaths.ROOT)`), not every occurrence.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "installer" / "scripts" / "patch_omc_statedir.sh"
HELPER = REPO / "runtime" / "omc-patches" / "_claudebase-omc-ascent.cjs"

ANCHOR = "    const root = worktreeRoot || getWorktreeRoot() || process.cwd();"
# Point C anchor: resolveToWorktreeRoot's non-git fallback (unique exact line).
RWR_ANCHOR = "    return getWorktreeRoot(process.cwd()) || process.cwd();"
# A look-alike the patch must NOT touch: validateWorkingDirectory uses the same
# right-hand side but a `const trustedRoot =` prefix (a security-boundary
# helper, deliberately left alone). Proves point C's match is prefix-precise.
TRUSTED_LINE = "    const trustedRoot = getWorktreeRoot(process.cwd()) || process.cwd();"

# Real ESM shape: "type":"module" package, duplicate anchor in two functions,
# plus resolveToWorktreeRoot (point C) and a validateWorkingDirectory look-alike.
STUB_JS = f'''\
import {{ join }} from 'path';

function getWorktreeRoot(d) {{ return null; }}

const OmcPaths = {{ ROOT: '.omc' }};

// getProjectIdentifier-like: same anchor, but NOT followed by the .omc return.
export function getProjectIdentifier(worktreeRoot) {{
{ANCHOR}
  return 'id-' + String(root).length;
}}

export function getOmcRoot(worktreeRoot) {{
  const customDir = process.env.OMC_STATE_DIR;
  if (customDir) {{
{ANCHOR}
    return join(customDir, getProjectIdentifier(root));
  }}
{ANCHOR}
    return join(root, OmcPaths.ROOT);
}}

// Point C target: the upstream normalizer the HUD calls. Its non-git fallback
// must gain the ascent so the cwd itself converges before getOmcRoot sees it.
export function resolveToWorktreeRoot(directory) {{
  if (directory) {{
    const root = getWorktreeRoot(directory);
    if (root) return root;
  }}
{RWR_ANCHOR}
}}

// Look-alike that must stay untouched (const-prefixed, security boundary).
export function validateWorkingDirectory(workingDirectory) {{
{TRUSTED_LINE}
  return trustedRoot;
}}
'''


def make_mock_omc(tmp: Path) -> Path:
    dist = tmp / "plugins" / "cache" / "omc" / "oh-my-claudecode" / "4.14.0" / "dist" / "lib"
    dist.mkdir(parents=True)
    (dist / "worktree-paths.js").write_text(STUB_JS)
    # Real OMC package is ESM — the stub dir needs a type:module package.json
    # so `node --check` / require-from-ESM behaves like production.
    (tmp / "plugins" / "cache" / "omc" / "oh-my-claudecode" / "4.14.0" / "package.json").write_text(
        '{"type":"module"}'
    )
    return tmp


def dist_of(cfg: Path) -> Path:
    return cfg / "plugins/cache/omc/oh-my-claudecode/4.14.0/dist/lib"


def run_patch(config_dir: Path, dry: str = "0"):
    env = {**os.environ, "CLAUDE_CONFIG_DIR": str(config_dir), "DRY_RUN": dry}
    return subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True)


def test_patch_applies_and_helper_copied(tmp_path):
    cfg = make_mock_omc(tmp_path)
    r = run_patch(cfg)
    assert r.returncode == 0, r.stderr
    js = (dist_of(cfg) / "worktree-paths.js").read_text()
    assert "_cbRequire" in js
    assert "ascendToMarker(process.cwd())" in js
    assert (dist_of(cfg) / "_claudebase-omc-ascent.cjs").exists()


def test_exactly_two_ascent_calls_injected(tmp_path):
    # The getOmcRoot anchor appears 3x but only its fallback (before the .omc
    # return) is patched (point B); resolveToWorktreeRoot's fallback is patched
    # once (point C). So ascendToMarker(process.cwd()) must appear EXACTLY 2x —
    # not 1 (C missing) and not more (a stray getProjectIdentifier/OMC_STATE_DIR
    # rewrite).
    cfg = make_mock_omc(tmp_path)
    run_patch(cfg)
    js = (dist_of(cfg) / "worktree-paths.js").read_text()
    assert js.count("ascendToMarker(process.cwd())") == 2


def test_resolvetoworktreeroot_fallback_is_patched(tmp_path):
    # Point C: resolveToWorktreeRoot's `return getWorktreeRoot(process.cwd())
    # || process.cwd();` gains the ascent before the cwd fallback.
    cfg = make_mock_omc(tmp_path)
    run_patch(cfg)
    js = (dist_of(cfg) / "worktree-paths.js").read_text()
    assert (
        "return getWorktreeRoot(process.cwd()) "
        "|| _cbRequire('./_claudebase-omc-ascent.cjs')"
        ".ascendToMarker(process.cwd()) || process.cwd();"
    ) in js


def test_validateworkingdirectory_lookalike_untouched(tmp_path):
    # The `const trustedRoot = getWorktreeRoot(process.cwd()) || process.cwd();`
    # security-boundary line shares C's right-hand side but a different prefix.
    # Point C's exact-line match must leave it verbatim (no ascent injected).
    cfg = make_mock_omc(tmp_path)
    run_patch(cfg)
    js = (dist_of(cfg) / "worktree-paths.js").read_text()
    assert (
        "    const trustedRoot = getWorktreeRoot(process.cwd()) || process.cwd();"
        in js
    )


def test_idempotent_second_run_skips(tmp_path):
    cfg = make_mock_omc(tmp_path)
    run_patch(cfg)
    before = (dist_of(cfg) / "worktree-paths.js").read_text()
    r2 = run_patch(cfg)
    after = (dist_of(cfg) / "worktree-paths.js").read_text()
    assert before == after  # no double-patch
    assert "already-patched=1" in (r2.stdout + r2.stderr)


def test_half_patched_file_gets_point_c_topped_up(tmp_path):
    # The real upgrade path: an older claudebase shipped only the shim + point B
    # (getOmcRoot). Such a half-patched file has the _cbRequire shim and ONE
    # ascent call but its resolveToWorktreeRoot fallback is still the original.
    # Keying idempotency on the shim alone would skip it and strand point C
    # forever. Simulate that state and assert re-running tops up C — without
    # duplicating the shim or re-patching the already-rewritten B line.
    cfg = make_mock_omc(tmp_path)
    wp = dist_of(cfg) / "worktree-paths.js"
    run_patch(cfg)  # full patch (A+B+C)
    full = wp.read_text()
    # Roll point C back to its original form -> half-patched (A+B only).
    rwr_patched = (
        "    return getWorktreeRoot(process.cwd()) "
        "|| _cbRequire('./_claudebase-omc-ascent.cjs')"
        ".ascendToMarker(process.cwd()) || process.cwd();"
    )
    rwr_original = "    return getWorktreeRoot(process.cwd()) || process.cwd();"
    half = full.replace(rwr_patched, rwr_original)
    assert half != full  # the rollback actually changed something
    assert half.count("ascendToMarker(process.cwd())") == 1  # B only
    assert half.count("_cbRequire(") >= 1  # shim still present
    wp.write_text(half)

    run_patch(cfg)  # re-entry must top up C
    after = wp.read_text()
    assert after.count("ascendToMarker(process.cwd())") == 2  # C topped up
    # Shim must not be duplicated by the point-A pass on re-entry.
    assert after.count("const _cbRequire = _cbCreateRequire(import.meta.url)") == 1
    # And the file is still valid JS.
    chk = subprocess.run(["node", "--check", str(wp)], capture_output=True, text=True)
    assert chk.returncode == 0, chk.stderr


def test_helper_refreshed_even_when_already_patched(tmp_path):
    # The helper must be re-copied on every run, not just on first patch — its
    # logic can change between claudebase versions. Simulate a stale helper
    # next to an already-patched module and assert the second run overwrites it.
    cfg = make_mock_omc(tmp_path)
    run_patch(cfg)  # first patch: copies helper, rewrites JS
    helper = dist_of(cfg) / "_claudebase-omc-ascent.cjs"
    helper.write_text("// STALE\n")  # corrupt the live helper
    r2 = run_patch(cfg)  # second run: JS already patched (skipped), helper must refresh
    assert "already-patched=1" in (r2.stdout + r2.stderr)
    assert helper.read_text() == HELPER.read_text()  # refreshed to repo source


def test_patched_file_is_valid_js(tmp_path):
    cfg = make_mock_omc(tmp_path)
    run_patch(cfg)
    js = dist_of(cfg) / "worktree-paths.js"
    chk = subprocess.run(["node", "--check", str(js)], capture_output=True, text=True)
    assert chk.returncode == 0, chk.stderr


def test_missing_omc_is_silent_skip(tmp_path):
    r = run_patch(tmp_path)  # no plugins/ dir at all
    assert r.returncode == 0


def test_anchor_absent_warns_but_succeeds(tmp_path):
    cfg = make_mock_omc(tmp_path)
    (dist_of(cfg) / "worktree-paths.js").write_text(
        'import { join } from "path";\n// OMC changed shape — no anchor here\n'
    )
    r = run_patch(cfg)
    assert r.returncode == 0
    assert "WARNING" in (r.stdout + r.stderr)


def test_ascent_resolves_after_patch(tmp_path):
    # End-to-end: a patched getOmcRoot, called from a non-git subfolder under a
    # CLAUDE.md root, must converge to <root>/.omc — not <subfolder>/.omc.
    cfg = make_mock_omc(tmp_path)
    # helper must be present in dist for require to resolve; patch copies it,
    # but copy needs the source — ensure the repo helper exists.
    assert HELPER.exists()
    run_patch(cfg)
    dist = dist_of(cfg)

    proj = tmp_path / "proj"
    sub = proj / "sub"
    sub.mkdir(parents=True)
    (proj / "CLAUDE.md").write_text("x")

    code = (
        f"process.env.HOME={json.dumps(str(tmp_path))};"
        f"const m=await import({json.dumps(str(dist / 'worktree-paths.js'))});"
        f"process.chdir({json.dumps(str(sub))});"
        f"process.stdout.write(m.getOmcRoot());"
    )
    out = subprocess.run(
        ["node", "--input-type=module", "-e", code],
        capture_output=True, text=True, check=True,
    )
    assert out.stdout == str(proj / ".omc")


def test_resolvetoworktreeroot_converges_non_git_subfolder(tmp_path):
    # The real HUD-scatter scenario (point C): the HUD calls
    # resolveToWorktreeRoot(stdin.cwd) with a non-git subfolder and would
    # otherwise promote that subfolder to the "worktree root", then hand it to
    # getOmcRoot as worktreeRoot — short-circuiting point B's ascent. After the
    # patch, resolveToWorktreeRoot must itself ascend to the .claude/CLAUDE.md
    # root (an IMPLICIT marker — proves convergence without an .omcroot), so the
    # cwd normalizes before getOmcRoot ever sees it.
    cfg = make_mock_omc(tmp_path)
    assert HELPER.exists()
    run_patch(cfg)
    dist = dist_of(cfg)

    proj = tmp_path / "ws"
    sub = proj / "10-19_Academic" / "11_Coursework"
    sub.mkdir(parents=True)
    (proj / ".claude").mkdir()
    (proj / ".claude" / "CLAUDE.md").write_text("project rules")

    # Reproduce the HUD exactly: it runs from the session folder, so
    # process.cwd() IS the non-git subfolder (and stdin.cwd matches it). chdir
    # into sub before calling — the patched fallback ascends from process.cwd().
    code = (
        f"process.env.HOME={json.dumps(str(tmp_path))};"
        f"const m=await import({json.dumps(str(dist / 'worktree-paths.js'))});"
        f"process.chdir({json.dumps(str(sub))});"
        f"process.stdout.write(m.resolveToWorktreeRoot({json.dumps(str(sub))}));"
    )
    out = subprocess.run(
        ["node", "--input-type=module", "-e", code],
        capture_output=True, text=True, check=True,
    )
    assert out.stdout == str(proj)  # converged to marker root, not the subfolder

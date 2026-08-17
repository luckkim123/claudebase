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

ANCHOR = "    const root = resolveStateAnchorRoot(worktreeRoot);"

# Real ESM shape: "type":"module" package, duplicate anchor in two functions.
# As of OMC 4.15.2 upstream refactored the old inline
# `worktreeRoot || getWorktreeRoot() || process.cwd()` fallback into a call
# through resolveStateAnchorRoot(worktreeRoot); getWorktreeRoot() itself is
# still used (by getProjectIdentifier's OMC_STATE_DIR branch, via getGitTopLevel
# in real OMC, simplified here) so the anchor's surrounding shape stays similar.
STUB_JS = f'''\
import {{ join }} from 'path';

function getWorktreeRoot() {{ return null; }}
function resolveStateAnchorRoot(worktreeRoot) {{ return worktreeRoot || getWorktreeRoot() || process.cwd(); }}

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
'''


# Real bridge shape: a CommonJS bundle (bridge/mcp-server.cjs) with
# worktree-paths INLINED. getOmcRoot's fallback uses the bare `root` var and the
# next line is the esbuild-mangled `return (0, import_path11.join)(root, ...)`.
# The OMC_STATE_DIR branch uses `root2` so the patch must NOT touch it. No
# `import`/`export` — it is CJS, so the patch must use require(), not the ESM
# createRequire shim.
BRIDGE_ANCHOR = "  const root = resolveStateAnchorRoot(worktreeRoot);"
STUB_BRIDGE = f'''\
"use strict";
const import_path11 = require("path");
function getWorktreeRoot() {{ return null; }}
function resolveStateAnchorRoot(worktreeRoot) {{ return worktreeRoot || getWorktreeRoot() || process.cwd(); }}
const OmcPaths = {{ ROOT: ".omc" }};

function getOmcRoot(worktreeRoot) {{
  const customDir = process.env.OMC_STATE_DIR;
  if (customDir) {{
  const root2 = resolveStateAnchorRoot(worktreeRoot);
    return (0, import_path11.join)(customDir, String(root2).length);
  }}
{BRIDGE_ANCHOR}
  return (0, import_path11.join)(root, OmcPaths.ROOT);
}}
module.exports = {{ getOmcRoot }};
'''


def make_mock_omc(tmp: Path) -> Path:
    base = tmp / "plugins" / "cache" / "omc" / "oh-my-claudecode" / "4.14.0"
    dist = base / "dist" / "lib"
    dist.mkdir(parents=True)
    (dist / "worktree-paths.js").write_text(STUB_JS)
    # Real OMC also bundles worktree-paths into the CJS MCP bridge — a separate
    # copy the patch must reach so MCP tools stop scattering .omc too.
    bridge = base / "bridge"
    bridge.mkdir(parents=True)
    (bridge / "mcp-server.cjs").write_text(STUB_BRIDGE)
    # Real OMC package is ESM — the stub dir needs a type:module package.json
    # so `node --check` / require-from-ESM behaves like production.
    (base / "package.json").write_text('{"type":"module"}')
    return tmp


def bridge_of(cfg: Path) -> Path:
    return cfg / "plugins/cache/omc/oh-my-claudecode/4.14.0/bridge"


def dist_of(cfg: Path) -> Path:
    return cfg / "plugins/cache/omc/oh-my-claudecode/4.14.0/dist/lib"


def run_patch(config_dir: Path, dry: str = "0"):
    env = {**os.environ, "CLAUDE_CONFIG_DIR": str(config_dir), "DRY_RUN": dry}
    return subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True, check=False)


def test_patch_applies_and_helper_copied(tmp_path):
    cfg = make_mock_omc(tmp_path)
    r = run_patch(cfg)
    assert r.returncode == 0, r.stderr
    js = (dist_of(cfg) / "worktree-paths.js").read_text()
    assert "_cbRequire" in js
    # Point D: a single ascendToMarker call covers both the don't-trust-arg
    # case and the worktreeRoot===undefined case (worktreeRoot || process.cwd()).
    assert "ascendToMarker(worktreeRoot || process.cwd())" in js
    assert (dist_of(cfg) / "_claudebase-omc-ascent.cjs").exists()


def test_only_getomcroot_fallback_is_patched(tmp_path):
    # The anchor appears 3x; only the getOmcRoot fallback (before the .omc
    # return) must be rewritten. The rewritten line carries exactly one ascent
    # call, so the other two anchor occurrences stay untouched.
    cfg = make_mock_omc(tmp_path)
    run_patch(cfg)
    js = (dist_of(cfg) / "worktree-paths.js").read_text()
    assert js.count("ascendToMarker(worktreeRoot || process.cwd())") == 1


def test_resolvetoworktreeroot_stays_stock(tmp_path):
    # Point D's whole reason for existing: resolveToWorktreeRoot must NOT be
    # patched. Ascending it (the abandoned point C) fed a value ABOVE the #576
    # trusted-root boundary into validateWorkingDirectory and threw
    # "outside the trusted worktree root" — killing the HUD. The fix lives in
    # getOmcRoot's argument only, so the upstream normalizer stays untouched.
    cfg = make_mock_omc(tmp_path)
    run_patch(cfg)
    js = (dist_of(cfg) / "worktree-paths.js").read_text()
    # The stub has no resolveToWorktreeRoot, so the only ascent call must be
    # the one inside the getOmcRoot rewrite — never one chained off a
    # `getWorktreeRoot(process.cwd())` line.
    assert "getWorktreeRoot(process.cwd()) || _cbRequire" not in js


def test_idempotent_second_run_skips(tmp_path):
    cfg = make_mock_omc(tmp_path)
    run_patch(cfg)
    before = (dist_of(cfg) / "worktree-paths.js").read_text()
    r2 = run_patch(cfg)
    after = (dist_of(cfg) / "worktree-paths.js").read_text()
    assert before == after  # no double-patch
    # Both copies (dist/lib + bridge bundle) skip on the second run.
    assert "already-patched=2" in (r2.stdout + r2.stderr)


def test_helper_refreshed_even_when_already_patched(tmp_path):
    # The helper must be re-copied on every run, not just on first patch — its
    # logic can change between claudebase versions. Simulate a stale helper
    # next to an already-patched module and assert the second run overwrites it.
    cfg = make_mock_omc(tmp_path)
    run_patch(cfg)  # first patch: copies helper, rewrites JS
    helper = dist_of(cfg) / "_claudebase-omc-ascent.cjs"
    helper.write_text("// STALE\n")  # corrupt the live helper
    r2 = run_patch(cfg)  # second run: JS already patched (skipped), helper must refresh
    # dist/lib + bridge bundle both skip the rewrite on the second run.
    assert "already-patched=2" in (r2.stdout + r2.stderr)
    assert helper.read_text() == HELPER.read_text()  # refreshed to repo source


def test_patched_file_is_valid_js(tmp_path):
    cfg = make_mock_omc(tmp_path)
    run_patch(cfg)
    js = dist_of(cfg) / "worktree-paths.js"
    chk = subprocess.run(["node", "--check", str(js)], capture_output=True, text=True, check=False)
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


def test_ascent_ignores_untrusted_worktreeroot_argument(tmp_path):
    # This is what point D fixes and point A could not: the HUD calls
    # getOmcRoot(resolveToWorktreeRoot(cwd)), and in a non-git tree
    # resolveToWorktreeRoot returns the session SUBFOLDER unchanged. Point A's
    # `worktreeRoot || ... || ascend` short-circuited on that truthy subfolder
    # and never ascended. Point D puts ascendToMarker(worktreeRoot ||
    # process.cwd()) FIRST, so even when handed the subfolder as the argument,
    # state converges to the CLAUDE.md root. Pass the subfolder explicitly to
    # prove it.
    cfg = make_mock_omc(tmp_path)
    assert HELPER.exists()
    run_patch(cfg)
    dist = dist_of(cfg)

    proj = tmp_path / "proj2"
    sub = proj / "deep" / "sub"
    sub.mkdir(parents=True)
    (proj / "CLAUDE.md").write_text("x")

    code = (
        f"process.env.HOME={json.dumps(str(tmp_path))};"
        f"const m=await import({json.dumps(str(dist / 'worktree-paths.js'))});"
        # Hand getOmcRoot the SUBFOLDER as worktreeRoot — the HUD's exact pattern.
        f"process.stdout.write(m.getOmcRoot({json.dumps(str(sub))}));"
    )
    out = subprocess.run(
        ["node", "--input-type=module", "-e", code],
        capture_output=True, text=True, check=True,
    )
    # Must converge to the marker root, NOT echo back the subfolder.
    assert out.stdout == str(proj / ".omc")


def test_omc_state_dir_overrides_marker_ascent(tmp_path):
    # The other side of the branch the two tests above exercise, and the one
    # nothing covered until it broke them: when OMC_STATE_DIR is set it wins,
    # and the patch must leave that branch alone.
    #
    # This gap was invisible because the variable arrived for free — the
    # rendered ~/.claude/settings.json exports it, so every Claude Code session
    # silently took this path while the assertions above described the other
    # one. tests/conftest.py now strips it, which is what makes an explicit
    # test necessary: with the ambient value gone, nothing else reaches here.
    cfg = make_mock_omc(tmp_path)
    assert HELPER.exists()
    run_patch(cfg)
    dist = dist_of(cfg)

    proj = tmp_path / "proj3"
    sub = proj / "sub"
    sub.mkdir(parents=True)
    (proj / "CLAUDE.md").write_text("x")
    custom = tmp_path / "state"

    code = (
        f"process.env.HOME={json.dumps(str(tmp_path))};"
        f"process.env.OMC_STATE_DIR={json.dumps(str(custom))};"
        f"const m=await import({json.dumps(str(dist / 'worktree-paths.js'))});"
        f"process.chdir({json.dumps(str(sub))});"
        f"process.stdout.write(m.getOmcRoot());"
    )
    out = subprocess.run(
        ["node", "--input-type=module", "-e", code],
        capture_output=True, text=True, check=True,
    )

    # The override wins: state lands under OMC_STATE_DIR, never <root>/.omc.
    assert out.stdout.startswith(str(custom) + os.sep)
    assert out.stdout != str(proj / ".omc")
    # And it resolves through the UNPATCHED anchor — the stub's identifier is
    # derived from cwd (the subfolder), not from the ascended marker root. That
    # is the patch's stated scope: only the fallback followed by
    # `return join(root, OmcPaths.ROOT)` is rewritten.
    assert out.stdout == str(custom / f"id-{len(str(sub))}")


def test_bridge_bundle_is_patched(tmp_path):
    # OMC inlines worktree-paths into the CJS MCP bridge — a second copy. The
    # patch must reach it too (dist/lib alone leaves MCP tools scattering .omc).
    cfg = make_mock_omc(tmp_path)
    run_patch(cfg)
    bridge = bridge_of(cfg) / "mcp-server.cjs"
    js = bridge.read_text()
    assert "ascendToMarker(worktreeRoot || process.cwd())" in js
    # CJS bridge uses plain require(), NOT the ESM createRequire shim.
    assert "_cbRequire" not in js
    assert "require('./_claudebase-omc-ascent.cjs')" in js
    # Helper copied next to the bridge so the require resolves.
    assert (bridge_of(cfg) / "_claudebase-omc-ascent.cjs").exists()
    # The OMC_STATE_DIR branch (root2) must stay untouched.
    assert "const root2 = resolveStateAnchorRoot(worktreeRoot);" in js
    chk = subprocess.run(["node", "--check", str(bridge)], capture_output=True, text=True, check=False)
    assert chk.returncode == 0, chk.stderr


def test_bridge_idempotent(tmp_path):
    cfg = make_mock_omc(tmp_path)
    run_patch(cfg)
    bridge = bridge_of(cfg) / "mcp-server.cjs"
    before = bridge.read_text()
    run_patch(cfg)
    assert bridge.read_text() == before  # no double-patch
    assert before.count("ascendToMarker(worktreeRoot || process.cwd())") == 1


def test_bridge_getomcroot_converges_via_require(tmp_path):
    # End-to-end through the bridge's OWN require resolution: the patched
    # getOmcRoot, called with a non-git subfolder, must converge to the marker
    # root using require('./_claudebase-omc-ascent.cjs') resolved next to the
    # bridge file (not the dist copy).
    cfg = make_mock_omc(tmp_path)
    assert HELPER.exists()
    run_patch(cfg)
    bridge = bridge_of(cfg) / "mcp-server.cjs"

    proj = tmp_path / "proj3"
    sub = proj / "a" / "b"
    sub.mkdir(parents=True)
    (proj / "CLAUDE.md").write_text("x")

    code = (
        f"process.env.HOME={json.dumps(str(tmp_path))};"
        f"const m=require({json.dumps(str(bridge))});"
        f"process.stdout.write(m.getOmcRoot({json.dumps(str(sub))}));"
    )
    out = subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True)
    assert out.stdout == str(proj / ".omc")

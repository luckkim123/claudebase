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

# Real ESM shape: "type":"module" package, duplicate anchor in two functions.
STUB_JS = f'''\
import {{ join }} from 'path';

function getWorktreeRoot() {{ return null; }}

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


def test_only_getomcroot_fallback_is_patched(tmp_path):
    # The anchor appears 3x; only the getOmcRoot fallback (before the .omc
    # return) must gain the ascent call. The other two stay untouched.
    cfg = make_mock_omc(tmp_path)
    run_patch(cfg)
    js = (dist_of(cfg) / "worktree-paths.js").read_text()
    assert js.count("ascendToMarker(process.cwd())") == 1


def test_idempotent_second_run_skips(tmp_path):
    cfg = make_mock_omc(tmp_path)
    run_patch(cfg)
    before = (dist_of(cfg) / "worktree-paths.js").read_text()
    r2 = run_patch(cfg)
    after = (dist_of(cfg) / "worktree-paths.js").read_text()
    assert before == after  # no double-patch
    assert "already-patched=1" in (r2.stdout + r2.stderr)


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

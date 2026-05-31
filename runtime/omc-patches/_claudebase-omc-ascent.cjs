'use strict';
// claudebase patch helper — injected into OMC's dist/lib/ by
// installer/scripts/patch_omc_statedir.sh.
//
// Why: OMC's getOmcRoot() falls back to process.cwd() when not in a git repo,
// so .omc state scatters across every visited subfolder of a non-git tree
// (docs/slides/notes workspaces, iCloud/Desktop folders, etc.). This helper
// gives the git-less case the same "find the project boundary" behavior that
// `git rev-parse --show-toplevel` gives the git case: ascend for a marker and
// converge state to that one root.
//
// Contract: ascendToMarker(startDir) returns the nearest ancestor (inclusive)
// containing a marker, or null if none found before $HOME / filesystem root.
// The caller (patched getOmcRoot) treats null as "keep current cwd fallback",
// so this helper never widens OMC's blast radius — it only narrows scatter.
//
// .cjs extension so it loads as CommonJS even though OMC's package is ESM;
// the patched worktree-paths.js reaches it via createRequire(import.meta.url).
const { existsSync } = require('fs');
const { join, dirname } = require('path');
const { homedir } = require('os');

// Two marker tiers with DIFFERENT precedence semantics:
//
//   .omcroot (AUTHORITATIVE) — the user's explicit "this is the root" escape
//     hatch. It wins regardless of depth: a full ascent pass looks for it
//     first, so an outer .omcroot beats any nearer implicit marker (e.g. a
//     nested .git checkout inside the workspace). This is what makes .omcroot
//     a reliable override.
//
//   .git / CLAUDE.md / .claude/CLAUDE.md (IMPLICIT) — nearest-wins. The first
//     ancestor (climbing up) that has any of these is the root. .git is
//     defensive (getWorktreeRoot() normally catches git repos before this
//     helper runs). CLAUDE.md is checked both at ./CLAUDE.md (repos) and at
//     .claude/CLAUDE.md (the project-scope location non-git workspaces use —
//     missing this form was a real defect that made the patch a no-op there).
const AUTHORITATIVE_MARKER = '.omcroot';
const IMPLICIT_MARKERS = ['.git', 'CLAUDE.md', '.claude/CLAUDE.md'];

// Climb from startDir toward $HOME / filesystem root, calling hit(dir) at each
// level. Returns the first dir for which hit() is truthy, or null.
function climb(startDir, hit) {
  const home = homedir();
  let dir = startDir;
  while (true) {
    if (hit(dir)) return dir;
    if (dir === home) return null; // never use $HOME itself as a project root
    const parent = dirname(dir);
    if (parent === dir) return null; // filesystem root (dirname fixed point)
    dir = parent;
  }
}

function ascendToMarker(startDir) {
  if (!startDir) return null;
  // Pass 1: authoritative .omcroot anywhere up the tree wins outright.
  const explicit = climb(startDir, (dir) => existsSync(join(dir, AUTHORITATIVE_MARKER)));
  if (explicit) return explicit;
  // Pass 2: nearest dir bearing any implicit marker.
  return climb(startDir, (dir) =>
    IMPLICIT_MARKERS.some((m) => existsSync(join(dir, m)))
  );
}

module.exports = { ascendToMarker };

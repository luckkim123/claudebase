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

// Priority order: an explicit .omcroot beats an implicit project marker, and
// a marker nearer to startDir beats a farther one (ascent stops at the first
// hit). .git is included defensively — getWorktreeRoot() normally catches git
// repos before this helper runs, but if it didn't, a .git boundary is still a
// better root than a markerless cwd.
const MARKERS = ['.omcroot', '.git', 'CLAUDE.md'];

function ascendToMarker(startDir) {
  if (!startDir) return null;
  const home = homedir();
  let dir = startDir;
  // Bound the climb: stop at $HOME (never use home itself as a project root)
  // and at the filesystem root (dirname is a fixed point there).
  while (true) {
    for (const marker of MARKERS) {
      if (existsSync(join(dir, marker))) return dir;
    }
    if (dir === home) return null;
    const parent = dirname(dir);
    if (parent === dir) return null;
    dir = parent;
  }
}

module.exports = { ascendToMarker };

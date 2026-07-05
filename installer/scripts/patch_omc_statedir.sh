#!/usr/bin/env bash
# patch_omc_statedir.sh — give OMC's getOmcRoot() a non-git project-boundary
# fallback so .omc state stops scattering across every visited subfolder of a
# git-less tree (docs/slides/notes workspaces, iCloud/Desktop folders, etc.).
#
# What it does (2-point patch of dist/lib/worktree-paths.js, an ESM module):
#   A. Inject a createRequire shim near the top so the ESM file can sync-load
#      a CJS helper (dynamic import() is async — unusable in sync getOmcRoot).
#   B. Rewrite ONLY the getOmcRoot default fallback line (the anchor line that
#      is immediately followed by `return join(root, OmcPaths.ROOT)` — as of
#      2026-07-05 this reads `const root = resolveStateAnchorRoot(worktreeRoot);`,
#      upstream having refactored the old inline
#      `worktreeRoot || getWorktreeRoot() || process.cwd()` into that helper
#      call). The new line does NOT trust the worktreeRoot ARGUMENT: it puts
#      ascendToMarker(worktreeRoot) FIRST, so even when the HUD hands getOmcRoot
#      a non-git session subfolder as worktreeRoot, state still converges to the
#      marker-bearing ancestor. The same anchor also appears in
#      getProjectIdentifier and in the OMC_STATE_DIR branch; those are left
#      untouched (next-line lookahead pins the right one).
#
#   WHY NOT patch resolveToWorktreeRoot (the abandoned "point C"): that upstream
#   normalizer feeds validateWorkingDirectory()'s trusted-root check, whose
#   trustedRoot stays at process.cwd() (the #576 security boundary, deliberately
#   un-patched). Ascending resolveToWorktreeRoot above that boundary makes the
#   normalized cwd an *ancestor* of trustedRoot → "outside the trusted worktree
#   root" throw → the HUD dies with "[OMC] HUD error - check stderr". Patching
#   ONLY getOmcRoot's argument (point B as written here) moves the .omc location
#   without ever touching the security-boundary input, so the HUD is unaffected.
#   Reproduced + regression-verified 2026-06-01 (see design.md §9).
#
# Why a patch and not an upstream change: OMC is a vendored plugin, not our
# repo. This mirrors patch_omc_freeze.sh — edit the cache in-place; OMC
# reinstall re-applies on next claudebase install.
#
# Safety:
#   - Idempotent: detects the `_cbRequire` marker before applying.
#   - Graceful: if the anchor is gone (OMC changed shape) it WARNs and restores
#     from .bak, but the install continues (scatter reverting to OMC's own
#     default is a safe fallback, not a failure).
#   - Validated: `node --check` after patching; restore + WARN on syntax error.
#   - Cross-OS: edits via perl + tmp files (no `sed -i`), so it runs identically
#     on BSD (macOS) and GNU (Linux); no npm deps (helper uses node built-ins).
#
# Full rationale: docs/specs/2026-05-31-omc-statedir-marker-ascent/design.md
set -euo pipefail

CLAUDE_HOME="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
OMC_ROOT="$CLAUDE_HOME/plugins/cache/omc/oh-my-claudecode"
DRY_RUN="${DRY_RUN:-0}"

# Helper source lives in the claudebase repo; resolve relative to this script.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HELPER_SRC="$SCRIPT_DIR/../../runtime/omc-patches/_claudebase-omc-ascent.cjs"

if [[ ! -d "$OMC_ROOT" ]]; then
  # Caller may run this before OMC is installed (fresh machine). Silent skip.
  exit 0
fi
if [[ ! -f "$HELPER_SRC" ]]; then
  echo "WARNING: omc statedir-ascent helper missing at $HELPER_SRC — skipping patch"
  exit 0
fi
# The patch validates each rewrite with `node --check`. Without node, every
# rewrite would "fail" validation and restore from .bak — a perpetual WARNING
# with no hint of the real cause. Skip explicitly instead. (OMC needs node at
# runtime anyway, so this is unlikely in practice.)
if ! command -v node >/dev/null 2>&1; then
  echo "WARNING: node not found — skipping omc statedir-ascent patch"
  exit 0
fi

# Anchor updated 2026-07-05: upstream OMC refactored getOmcRoot's default
# fallback from the inline `worktreeRoot || getWorktreeRoot() || process.cwd()`
# to a call through resolveStateAnchorRoot(worktreeRoot) (getWorktreeRoot()
# itself was also renamed/repurposed — getGitTopLevel() is now the no-climb
# primitive). resolveStateAnchorRoot already encapsulates the git-climb logic,
# so the patch just needs to ascend for a marker BEFORE trusting its result.
#
# Single ascendToMarker(worktreeRoot || process.cwd()) call, NOT two separate
# ascendToMarker(worktreeRoot) / ascendToMarker(process.cwd()) calls as in the
# pre-4.15.2 anchor: resolveStateAnchorRoot(worktreeRoot) with worktreeRoot
# falsy now falls all the way through to process.cwd() itself (no-git-repo
# case), so it is ALWAYS truthy and would short-circuit the `||` chain before
# a trailing ascendToMarker(process.cwd()) ever ran — silently disabling the
# no-arg call path. Resolving worktreeRoot to process.cwd() up front avoids
# that trap entirely.
ANCHOR='    const root = resolveStateAnchorRoot(worktreeRoot);'
# Point D: ascendToMarker goes FIRST so getOmcRoot does not trust the (possibly
# non-git subfolder) worktreeRoot argument the HUD hands it — nor short-circuit
# on resolveStateAnchorRoot's own cwd fallback. resolveToWorktreeRoot stays
# stock → no #576 boundary conflict.
REPLACEMENT="    const root = _cbRequire('./_claudebase-omc-ascent.cjs').ascendToMarker(worktreeRoot || process.cwd()) || resolveStateAnchorRoot(worktreeRoot) || process.cwd();"
RETURN_LINE='    return join(root, OmcPaths.ROOT);'

patched=0
skipped=0
while IFS= read -r wp; do
  [[ -f "$wp" ]] || continue
  dir="$(dirname "$wp")"

  # Refresh the helper on EVERY run, independent of the JS-patch idempotency
  # check below. The helper's logic can change between claudebase versions; if
  # we only copied it when (re)writing the JS, an already-patched module would
  # keep running a stale helper. Copying is cheap and safe (overwrite), so do
  # it unconditionally — unless DRY_RUN.
  if [[ "$DRY_RUN" != "1" ]]; then
    cp "$HELPER_SRC" "$dir/_claudebase-omc-ascent.cjs"
  fi

  if grep -q '_cbRequire' "$wp" 2>/dev/null; then
    skipped=$((skipped + 1))
    continue
  fi

  if [[ "$DRY_RUN" == "1" ]]; then
    echo "would patch omc statedir-ascent in: $wp"
    patched=$((patched + 1))
    continue
  fi

  cp "$wp" "$wp.bak"

  # Point A: inject createRequire shim after the last top-level import line.
  # Point B: rewrite only the anchor whose NEXT line is the .omc return.
  # perl does both in one pass: a sliding window pins point B, and we append
  # the shim once after the import block.
  perl -0777 -pe '
    my $shim = "import { createRequire as _cbCreateRequire } from '"'"'module'"'"';\nconst _cbRequire = _cbCreateRequire(import.meta.url); /* claudebase-ascent */\n";
    # Insert shim after the final top-level "import ... from ...;" line.
    if (/^(import .*?;\n)(?!import )/ms) {
      s/((?:^import .*?;\n)+)/$1$shim/m;
    }
  ' "$wp" > "$wp.tmp1"

  # Point B with next-line lookahead (anchor immediately followed by return).
  ANCHOR="$ANCHOR" REPLACEMENT="$REPLACEMENT" RETURN_LINE="$RETURN_LINE" \
  perl -ne '
    BEGIN { $a=$ENV{ANCHOR}; $r=$ENV{REPLACEMENT}; $ret=$ENV{RETURN_LINE}; @buf=(); }
    push @buf, $_;
    if (@buf == 2) {
      my ($prev,$cur) = @buf;
      chomp(my $pc=$prev); chomp(my $cc=$cur);
      if ($pc eq $a && $cc eq $ret) { $prev = "$r\n"; }
      print $prev;
      shift @buf;
    }
    END { print @buf; }
  ' "$wp.tmp1" > "$wp.tmp2"

  mv "$wp.tmp2" "$wp"
  rm -f "$wp.tmp1"

  ok=1
  grep -q '_cbRequire' "$wp" || ok=0
  # Point D pins the single ascent call: ascendToMarker(worktreeRoot ||
  # process.cwd()) covers BOTH the don't-trust-arg case and the
  # worktreeRoot===undefined case in one call (see REPLACEMENT comment above
  # for why two separate ascendToMarker calls silently broke on 4.15.2+).
  grep -q "ascendToMarker(worktreeRoot || process.cwd())" "$wp" || ok=0
  if [[ "$ok" == "1" ]] && node --check "$wp" 2>/dev/null; then
    rm -f "$wp.bak"
    patched=$((patched + 1))
  else
    echo "WARNING: omc statedir-ascent patch did not apply cleanly to $wp — restoring"
    mv "$wp.bak" "$wp"
    rm -f "$dir/_claudebase-omc-ascent.cjs"
  fi
done < <(find "$OMC_ROOT" -path '*/dist/lib/worktree-paths.js' -type f 2>/dev/null)

# ── Point D for the MCP bridge bundle (bridge/mcp-server.cjs) ─────────────────
# The HUD path is dist/lib/worktree-paths.js (patched above), but OMC ALSO ships
# worktree-paths INLINED into bridge/mcp-server.cjs — the MCP server that
# notepad/state/team/mission tools run through. That bundled getOmcRoot is a
# separate copy; patching only dist/lib leaves MCP tools scattering .omc in
# non-git subfolders. So apply point D there too. Differences from the ESM file:
#   - It is CommonJS (.cjs), so NO createRequire shim — `require('./...')` works
#     directly. The helper is copied next to mcp-server.cjs.
#   - esbuild renames the join import (import_pathNN.join), so the next-line
#     return is `return (0, import_pathNN.join)(root, OmcPaths.ROOT);` — matched
#     with a flexible NN.
#   - The OMC_STATE_DIR branch uses `root2` (not `root`), so the bare `root`
#     anchor + this return lookahead pins only the default fallback.
#   - Same anchor refactor as the ESM file (2026-07-05): the default fallback
#     now reads through resolveStateAnchorRoot(worktreeRoot), inlined by
#     esbuild into this bundle under the same name.
# NOTE: an already-running MCP server holds the old code in memory; the patch
# takes effect when that server next restarts (new session / OMC reload).
BRIDGE_ANCHOR='  const root = resolveStateAnchorRoot(worktreeRoot);'
BRIDGE_REPL="  const root = require('./_claudebase-omc-ascent.cjs').ascendToMarker(worktreeRoot || process.cwd()) || resolveStateAnchorRoot(worktreeRoot) || process.cwd();"

while IFS= read -r bp; do
  [[ -f "$bp" ]] || continue
  bdir="$(dirname "$bp")"

  if [[ "$DRY_RUN" != "1" ]]; then
    cp "$HELPER_SRC" "$bdir/_claudebase-omc-ascent.cjs"
  fi

  # Idempotency: the bridge marks itself with the same ascent call.
  if grep -q "ascendToMarker(worktreeRoot || process.cwd())" "$bp" 2>/dev/null; then
    skipped=$((skipped + 1))
    continue
  fi

  if [[ "$DRY_RUN" == "1" ]]; then
    echo "would patch omc statedir-ascent (bridge) in: $bp"
    patched=$((patched + 1))
    continue
  fi

  cp "$bp" "$bp.bak"

  # Rewrite only the bare-`root` fallback whose next line is the esbuild-mangled
  # `return (0, import_pathNN.join)(root, OmcPaths.ROOT);`.
  BRIDGE_ANCHOR="$BRIDGE_ANCHOR" BRIDGE_REPL="$BRIDGE_REPL" \
  perl -ne '
    BEGIN { $a=$ENV{BRIDGE_ANCHOR}; $r=$ENV{BRIDGE_REPL}; @buf=(); }
    push @buf, $_;
    if (@buf == 2) {
      my ($prev,$cur) = @buf;
      chomp(my $pc=$prev); chomp(my $cc=$cur);
      if ($pc eq $a && $cc =~ /^\s*return \(0, import_path\d+\.join\)\(root, OmcPaths\.ROOT\);$/) {
        $prev = "$r\n";
      }
      print $prev;
      shift @buf;
    }
    END { print @buf; }
  ' "$bp" > "$bp.tmp" && mv "$bp.tmp" "$bp"

  ok=1
  grep -q "ascendToMarker(worktreeRoot || process.cwd())" "$bp" || ok=0
  if [[ "$ok" == "1" ]] && node --check "$bp" 2>/dev/null; then
    rm -f "$bp.bak"
    patched=$((patched + 1))
  else
    echo "WARNING: omc statedir-ascent patch did not apply cleanly to $bp — restoring"
    mv "$bp.bak" "$bp"
    rm -f "$bdir/_claudebase-omc-ascent.cjs"
  fi
done < <(find "$OMC_ROOT" -path '*/bridge/mcp-server.cjs' -type f 2>/dev/null)

echo "omc statedir-ascent patch: patched=$patched, already-patched=$skipped"

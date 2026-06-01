#!/usr/bin/env bash
# patch_omc_statedir.sh — give OMC's getOmcRoot() a non-git project-boundary
# fallback so .omc state stops scattering across every visited subfolder of a
# git-less tree (docs/slides/notes workspaces, iCloud/Desktop folders, etc.).
#
# What it does (3-point patch of dist/lib/worktree-paths.js, an ESM module):
#   A. Inject a createRequire shim near the top so the ESM file can sync-load
#      a CJS helper (dynamic import() is async — unusable in sync getOmcRoot).
#   B. Rewrite ONLY the getOmcRoot default fallback line (the anchor line that
#      is immediately followed by `return join(root, OmcPaths.ROOT)`) to call
#      ascendToMarker(process.cwd()) before the cwd fallback. The same anchor
#      also appears in getProjectIdentifier and in the OMC_STATE_DIR branch;
#      those are left untouched (next-line lookahead pins the right one).
#   C. Rewrite the resolveToWorktreeRoot non-git fallback (its final
#      `return getWorktreeRoot(process.cwd()) || process.cwd();`) the same way.
#      This is the UPSTREAM normalizer the HUD calls (hud/index.js) with the
#      session cwd: in a non-git tree it would otherwise promote whatever
#      subfolder the session is in to the "worktree root" and hand that polluted
#      value to getOmcRoot as `worktreeRoot` — short-circuiting point B's ascent.
#      Fixing it here converges the cwd itself, so every caller (HUD included)
#      lands on one .omc. The line is unique (validateWorkingDirectory* use
#      `const trustedRoot = ...`, a different prefix), so a plain exact-line
#      match pins it without a lookahead. Those security-boundary validators are
#      deliberately left untouched — widening their trusted root would change
#      what counts as "outside the root" (#576 boundary semantics).
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
#   - Cross-OS: handles BSD (macOS) and GNU sed/perl is POSIX-portable.
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

ANCHOR='    const root = worktreeRoot || getWorktreeRoot() || process.cwd();'
REPLACEMENT="    const root = worktreeRoot || getWorktreeRoot() || _cbRequire('./_claudebase-omc-ascent.cjs').ascendToMarker(process.cwd()) || process.cwd();"
RETURN_LINE='    return join(root, OmcPaths.ROOT);'

# Point C: resolveToWorktreeRoot's non-git fallback. Single unique line (no
# next-line lookahead needed — validateWorkingDirectory* use a `const
# trustedRoot =` prefix, so this exact `    return getWorktreeRoot(...` form
# matches only resolveToWorktreeRoot).
RWR_ANCHOR='    return getWorktreeRoot(process.cwd()) || process.cwd();'
RWR_REPLACEMENT="    return getWorktreeRoot(process.cwd()) || _cbRequire('./_claudebase-omc-ascent.cjs').ascendToMarker(process.cwd()) || process.cwd();"

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

  # Idempotency key = BOTH ascent calls present (point B + point C). Keying on
  # the _cbRequire shim alone is NOT enough: an older claudebase shipped only
  # points A+B, so a shim-only file is half-patched (C missing). Skipping it on
  # "shim exists" would strand C forever. Re-enter when the count is not 2 — the
  # perl passes below are self-idempotent (they match the ORIGINAL anchor shape,
  # which an already-rewritten line no longer has), and the shim is injected
  # only when absent (guarded in the point-A pass), so re-entry tops up the
  # missing point without duplicating the shim or the already-patched line.
  if [[ "$(grep -c 'ascendToMarker(process.cwd())' "$wp" 2>/dev/null)" == "2" ]]; then
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
    # Inject the shim only if absent. On a half-patched re-entry (points A+B
    # present, C missing) the shim is already there — re-adding it would
    # duplicate the createRequire line. Skip when _cbRequire already exists.
    if (!/_cbRequire/ && /^(import .*?;\n)(?!import )/ms) {
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

  # Point C: rewrite the single unique resolveToWorktreeRoot fallback line.
  RWR_ANCHOR="$RWR_ANCHOR" RWR_REPLACEMENT="$RWR_REPLACEMENT" \
  perl -ne '
    BEGIN { $a=$ENV{RWR_ANCHOR}; $r=$ENV{RWR_REPLACEMENT}; }
    chomp(my $line=$_);
    if ($line eq $a) { print "$r\n"; } else { print; }
  ' "$wp.tmp2" > "$wp.tmp3"

  mv "$wp.tmp3" "$wp"
  rm -f "$wp.tmp1" "$wp.tmp2"

  ok=1
  grep -q '_cbRequire' "$wp" || ok=0
  # Both point B (getOmcRoot) and point C (resolveToWorktreeRoot) inject the
  # same ascendToMarker(process.cwd()) call, so the count must be exactly 2.
  # A count of 1 means one of them failed (e.g. OMC changed that function's
  # shape) — treat it as a failed patch and restore, rather than silently
  # shipping a half-patch that lets HUD scatter revive.
  [[ "$(grep -c 'ascendToMarker(process.cwd())' "$wp")" == "2" ]] || ok=0
  if [[ "$ok" == "1" ]] && node --check "$wp" 2>/dev/null; then
    rm -f "$wp.bak"
    patched=$((patched + 1))
  else
    echo "WARNING: omc statedir-ascent patch did not apply cleanly to $wp — restoring"
    mv "$wp.bak" "$wp"
    rm -f "$dir/_claudebase-omc-ascent.cjs"
  fi
done < <(find "$OMC_ROOT" -path '*/dist/lib/worktree-paths.js' -type f 2>/dev/null)

echo "omc statedir-ascent patch: patched=$patched, already-patched=$skipped"

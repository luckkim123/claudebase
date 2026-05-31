#!/usr/bin/env bash
# patch_omc_statedir.sh — give OMC's getOmcRoot() a non-git project-boundary
# fallback so .omc state stops scattering across every visited subfolder of a
# git-less tree (docs/slides/notes workspaces, iCloud/Desktop folders, etc.).
#
# What it does (2-point patch of dist/lib/worktree-paths.js, an ESM module):
#   A. Inject a createRequire shim near the top so the ESM file can sync-load
#      a CJS helper (dynamic import() is async — unusable in sync getOmcRoot).
#   B. Rewrite ONLY the getOmcRoot default fallback line (the anchor line that
#      is immediately followed by `return join(root, OmcPaths.ROOT)`) to call
#      ascendToMarker(process.cwd()) before the cwd fallback. The same anchor
#      also appears in getProjectIdentifier and in the OMC_STATE_DIR branch;
#      those are left untouched (next-line lookahead pins the right one).
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

ANCHOR='    const root = worktreeRoot || getWorktreeRoot() || process.cwd();'
REPLACEMENT="    const root = worktreeRoot || getWorktreeRoot() || _cbRequire('./_claudebase-omc-ascent.cjs').ascendToMarker(process.cwd()) || process.cwd();"
RETURN_LINE='    return join(root, OmcPaths.ROOT);'

patched=0
skipped=0
while IFS= read -r wp; do
  [[ -f "$wp" ]] || continue
  dir="$(dirname "$wp")"

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

  # Always copy the helper alongside the module (require resolves './').
  cp "$HELPER_SRC" "$dir/_claudebase-omc-ascent.cjs"

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
  grep -q "ascendToMarker(process.cwd())" "$wp" || ok=0
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

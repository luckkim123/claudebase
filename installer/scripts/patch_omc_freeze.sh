#!/usr/bin/env bash
# patch_omc_freeze.sh — gate OMC's post-tool-verifier.mjs "Command failed →
# fix before continuing" message behind QUIET_LEVEL < 2.
#
# Why this exists: the literal phrase "fix before continuing" is parsed by
# Claude as a pause gate, freezing the session after every Bash error. The
# companion line in post-tool-verifier.mjs:906 already had this gate; this
# patch unifies them.
#
# Idempotent: detects the already-patched marker before applying.
# Cross-OS: handles BSD sed (macOS) and GNU sed (Linux).
# Non-destructive: edits the vendored plugin cache in-place; OMC reinstall
# re-applies the patch on next claudebase install.
#
# Full rationale + removal condition: see docs/upstream-patches.md.
# Investigation evidence: .omc/reviews/session-freeze-investigation.md.
set -euo pipefail

CLAUDE_HOME="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
OMC_ROOT="$CLAUDE_HOME/plugins/cache/omc/oh-my-claudecode"
DRY_RUN="${DRY_RUN:-0}"

if [[ ! -d "$OMC_ROOT" ]]; then
  # Caller may run this before OMC is installed (fresh machine). Silent skip.
  exit 0
fi

patched=0
skipped=0
while IFS= read -r verifier; do
  [[ -f "$verifier" ]] || continue
  if grep -q 'QUIET_LEVEL < 2 && detectBashFailure' "$verifier" 2>/dev/null; then
    skipped=$((skipped + 1))
    continue
  fi
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "would patch omc bash-freeze in: $verifier"
    patched=$((patched + 1))
    continue
  fi
  # macOS BSD sed needs '' after -i; GNU sed accepts -i alone.
  if sed --version >/dev/null 2>&1; then
    sed -i -E 's|^(  *)\} else if \(detectBashFailure\(toolOutput\)\) \{|\1} else if (QUIET_LEVEL < 2 \&\& detectBashFailure(toolOutput)) {|' "$verifier"
  else
    sed -i '' -E 's|^(  *)\} else if \(detectBashFailure\(toolOutput\)\) \{|\1} else if (QUIET_LEVEL < 2 \&\& detectBashFailure(toolOutput)) {|' "$verifier"
  fi
  if grep -q 'QUIET_LEVEL < 2 && detectBashFailure' "$verifier" 2>/dev/null; then
    patched=$((patched + 1))
  else
    echo "WARNING: omc bash-freeze patch did not apply to $verifier"
  fi
done < <(find "$OMC_ROOT" -path '*/scripts/post-tool-verifier.mjs' -type f 2>/dev/null)

echo "omc bash-freeze patch: patched=$patched, already-patched=$skipped (set OMC_QUIET=2 to silence)"

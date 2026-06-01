#!/usr/bin/env bash
# installer/bin/restore-settings.sh — restore config/settings.json to the
# canonical committed version after the Claude Code CLI silently shrank it.
#
# The single recovery command every guard's error message cites (pre-commit
# hook, drift.sh). Because ~/.claude/settings.json symlinks into this repo,
# restoring the tracked file restores the live session config too.
#
# Safe by construction: it only ever `git checkout`s the committed version
# (HEAD or origin/main), then verifies the result against the manifest — it
# never blesses or commits a shrunk file.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
SETTINGS="config/settings.json"
VERIFY="$REPO_DIR/installer/lib/settings_verify.py"
PY="$(command -v python3 || command -v python || true)"

cd "$REPO_DIR"

# Prefer origin/main (the cross-machine canonical), fall back to HEAD if offline.
SRC="HEAD"
if git rev-parse --verify --quiet origin/main >/dev/null; then
  SRC="origin/main"
fi

echo "[restore-settings] restoring $SETTINGS from $SRC ..."
git checkout "$SRC" -- "$SETTINGS"

if [[ -n "$PY" && -f "$VERIFY" ]]; then
  if "$PY" "$VERIFY" "$REPO_DIR/$SETTINGS"; then
    echo "[restore-settings] OK — all critical keys present (restored from $SRC)."
  else
    echo "[restore-settings] WARNING: restored file STILL fails verification —" >&2
    echo "[restore-settings] the canonical $SRC version may itself be shrunk. Inspect manually." >&2
    exit 1
  fi
else
  echo "[restore-settings] (verifier unavailable — restored from $SRC without integrity check)"
fi

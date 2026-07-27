#!/usr/bin/env bash
# installer/bin/restore-settings.sh — restore config/settings.json to the
# canonical committed version after the Claude Code CLI silently shrank it.
#
# The single recovery command every guard's error message cites (pre-commit
# hook, drift.sh). ~/.claude/settings.json is RENDERED from this file plus the
# machine's settings.local.json (lib/link.sh `render_settings`), not symlinked
# at it — so restoring the tracked file is only half the job, and this script
# re-renders afterwards to put the recovered baseline live.
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

# Push the recovered baseline into the live file. Without this the session keeps
# running on the shrunk render, which is exactly the state the caller is trying
# to escape. Skipped silently when the render target is still a symlink from the
# pre-render layout (install.sh migrates that).
RENDER="$REPO_DIR/installer/scripts/render_settings.py"
CLAUDE_HOME="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
if [[ -n "$PY" && -f "$RENDER" ]]; then
  "$PY" "$RENDER" \
    --base "$REPO_DIR/$SETTINGS" \
    --local "$CLAUDE_HOME/settings.local.json" \
    --out "$CLAUDE_HOME/settings.json" \
    && echo "[restore-settings] re-rendered $CLAUDE_HOME/settings.json"
else
  echo "[restore-settings] WARNING: could not re-render $CLAUDE_HOME/settings.json —" >&2
  echo "[restore-settings] run installer/install.sh to put the restored baseline live." >&2
fi

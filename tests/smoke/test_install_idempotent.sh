#!/usr/bin/env bash
# Smoke test: verify installer/install.sh is idempotent on this machine.
#
# Contract (docs/ARCHITECTURE.md): a second install.sh run prints zero lines
# matching any of these patterns:
#   linked:|rendered:|installing|reinstalled:|installed HUD|applied line1
#
# The pattern was widened on 2026-05-29 (P1 G3.2): the original
# linked|rendered|installing|reinstalled missed install_omc_hud's silent
# regression (cp + chmod + hud-customize.sh on every run). G2.4 fixed the
# leak; this smoke guards against the class returning.
#
# This test runs against the live $HOME — it does NOT sandbox into /tmp,
# because parts of the installer (HUD wrapper, plugin sync) read live state
# that doesn't exist in a fresh sandbox. CI runs the same script after a
# first install.sh, on a runner where every install action is fresh.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

echo "[smoke] priming installer (1st run, output suppressed)..."
"$REPO_DIR/installer/install.sh" >/dev/null

echo "[smoke] measuring 2nd run output..."
SECOND="$("$REPO_DIR/installer/install.sh" 2>&1)"

# Pattern intentionally widened to include the install_omc_hud regression
# class. Anchor 'installing' to start of word so it doesn't trip on the
# benign 'platform installer' header line.
PATTERN='linked:|rendered:|reinstalled:|installed HUD|applied line1|^\[install\] installing|plugin reinstalled'

if echo "$SECOND" | grep -qE "$PATTERN"; then
  echo "[smoke] FAIL — idempotency contract violated. Offending lines:"
  echo "$SECOND" | grep -E "$PATTERN" | sed 's/^/  | /'
  echo
  echo "[smoke] full 2nd-run output:"
  echo "$SECOND" | sed 's/^/  > /'
  exit 1
fi

echo "[smoke] PASS — second install.sh run was idempotent ($(echo "$SECOND" | wc -l | tr -d ' ') benign lines)."

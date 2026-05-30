#!/usr/bin/env bash
# platform/linux/install.sh — Debian/Ubuntu system package auto-install.
# Invoked by ../../install.sh after dotfile sync. Idempotent: skips packages
# already present. Non-fatal: any failure exits 0 so the parent install.sh
# (which runs under `set -e`) keeps going.
#
# Currently targets apt (Debian/Ubuntu). Other distros fall through to a
# manual-install hint. Add support by widening the package-manager probe.

set -u

REQUIRED_PKGS=(tmux)

if ! command -v apt-get >/dev/null 2>&1; then
  printf '[platform/linux] WARNING: apt-get not found — install manually: %s\n' "${REQUIRED_PKGS[*]}"
  exit 0
fi

missing=()
for pkg in "${REQUIRED_PKGS[@]}"; do
  dpkg -s "$pkg" >/dev/null 2>&1 || missing+=("$pkg")
done

if [[ ${#missing[@]} -eq 0 ]]; then
  printf '[platform/linux] system packages already present (skip): %s\n' "${REQUIRED_PKGS[*]}"
  exit 0
fi

printf '[platform/linux] missing system packages: %s\n' "${missing[*]}"

# sudo가 비번 없이(NOPASSWD or cached timestamp) 통과 가능하거나,
# 대화형 터미널이면 prompt를 띄울 수 있으므로 진행. 둘 다 아니면 manual hint.
if sudo -n true 2>/dev/null || [[ -t 0 ]]; then
  sudo apt-get update -qq || {
    printf '[platform/linux] WARNING: apt-get update failed — skipping install\n'
    exit 0
  }
  if sudo apt-get install -y -qq "${missing[@]}"; then
    printf '[platform/linux] installed: %s\n' "${missing[*]}"
  else
    printf '[platform/linux] WARNING: apt-get install failed for: %s\n' "${missing[*]}"
  fi
else
  printf '[platform/linux] WARNING: cannot run sudo non-interactively\n'
  printf '[platform/linux]   install manually: sudo apt-get install -y %s\n' "${missing[*]}"
fi

# gh: the GitHub CLI is the household's sole GitHub interface (clone/push/auth) —
# claudebase relies on it instead of any github plugin. Handled separately from
# REQUIRED_PKGS because gh is NOT in the default Debian/Ubuntu apt repo; it needs
# GitHub's own apt source, so `apt-get install gh` would fail. Detect-and-hint only
# (never auto-add a third-party apt source — that is a user trust decision).
if ! command -v gh >/dev/null 2>&1; then
  printf '[platform/linux] HINT: gh (GitHub CLI) missing — claudebase uses it for all GitHub ops.\n'
  printf '[platform/linux]       install: https://github.com/cli/cli/blob/trunk/docs/install_linux.md\n'
fi

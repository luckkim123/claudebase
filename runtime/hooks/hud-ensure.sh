#!/usr/bin/env bash
# hud-ensure.sh — SessionStart guard that keeps the OMC HUD wrapper synced.
#
# Problem: OMC's `/oh-my-claudecode:hud setup` (and plugin updates that ship a
# new wrapper template) regenerate ~/.claude/hud/omc-hud.mjs from the plugin's
# canonical template, DROPPING the local cyan "dir:/branch:/model:/effort:"
# customization that claudebase injects via installer/scripts/hud-customize.sh.
# Because that re-injection only ran on a manual `./install.sh`, the HUD stayed
# broken until the next install. This hook closes that gap by re-running the
# same install_omc_hud logic on every session start.
#
# It mirrors installer/lib/omc.sh::install_omc_hud — the installer remains the
# source of truth; this hook just calls into the SAME scripts so there is one
# implementation, not two. The installer's idempotency guards make this cheap:
# when the wrapper already carries the marker AND config-dir.mjs byte-matches
# the plugin template, it does nothing and exits.
#
# Wired as a SessionStart hook in config/settings.json. Must be fast and must
# never block a session — every exit path returns 0.
set -uo pipefail

CLAUDE_HOME="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
REPO_DIR="${CLAUDEBASE_DIR:-$HOME/claudebase}"
MARKER="OMC HUD local customization"

WRAPPER="$CLAUDE_HOME/hud/omc-hud.mjs"
DEST_CFG="$CLAUDE_HOME/hud/lib/config-dir.mjs"

# Gate 1: only act when the OMC plugin is actually enabled. If settings.json is
# missing or unreadable, bail quietly — nothing to keep in sync.
python3 -c "import json,sys; d=json.load(open('$CLAUDE_HOME/settings.json')); sys.exit(0 if d.get('enabledPlugins',{}).get('oh-my-claudecode@omc') else 1)" 2>/dev/null || exit 0

# Locate the highest installed OMC version dir that ships the wrapper template
# and its config-dir.mjs companion. This is the byte-match reference for the
# skip decision below, and the source the installer copies from.
TMPL=""
CFGDIR=""
OMC_ROOT="$CLAUDE_HOME/plugins/cache/omc/oh-my-claudecode"
if [[ -d "$OMC_ROOT" ]]; then
  for ver in $(ls -1 "$OMC_ROOT" 2>/dev/null | grep -E '^[0-9]+\.[0-9]+\.[0-9]+' | sort -rV); do
    if [[ -f "$OMC_ROOT/$ver/scripts/lib/hud-wrapper-template.txt" ]]; then
      TMPL="$OMC_ROOT/$ver/scripts/lib/hud-wrapper-template.txt"
      CFGDIR="$OMC_ROOT/$ver/scripts/lib/config-dir.mjs"
      break
    fi
  done
fi
# No template in the plugin cache → nothing we can repair from. Stay silent;
# the next `/oh-my-claudecode:omc-setup` or `./install.sh` will handle it.
[[ -n "$TMPL" ]] || exit 0

# ── Skip gate (the cost-defining check) ────────────────────────────────────
# TODO(user): decide the condition under which the HUD is "already healthy" and
# this hook should return immediately without touching any files.
#
# Available facts at this point:
#   $WRAPPER   — path to the live wrapper (~/.claude/hud/omc-hud.mjs); may exist
#   $DEST_CFG  — path to the live config-dir.mjs companion; may exist
#   $MARKER    — the customization marker string injected by hud-customize.sh
#   $CFGDIR    — the plugin template's config-dir.mjs (byte-match reference)
#
# This mirrors installer/lib/omc.sh:73-79. The wrapper is healthy when BOTH:
#   (a) it exists AND contains "$MARKER"  (customization survived), AND
#   (b) $DEST_CFG exists AND byte-matches $CFGDIR  (cmp -s "$CFGDIR" "$DEST_CFG").
# If both hold, the HUD is the patched form we want and re-copying would clobber
# it — so we should `exit 0` here. Otherwise fall through to the rebuild below.
#
# Healthy when BOTH the customization survived (wrapper exists and carries the
# marker) AND config-dir.mjs byte-matches the plugin template. The -f guards keep
# grep/cmp from erroring on a missing file (they'd just mean "not healthy →
# rebuild"). Mirrors installer/lib/omc.sh:73-79.
if [[ -f "$WRAPPER" ]] \
   && grep -qF "$MARKER" "$WRAPPER" \
   && [[ -f "$DEST_CFG" ]] \
   && cmp -s "$CFGDIR" "$DEST_CFG"; then
  # 발화 기록 — harness_stats 가 이 파일명 리터럴을 grep 한다. 실패해도 무시.
  _log="${CLAUDE_PROJECT_DIR:-$PWD}/.omc/logs/hud_ensure.jsonl"
  mkdir -p "$(dirname "$_log")" 2>/dev/null \
    && printf '{"ts":"%s","hook":"hud-ensure"}\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$_log" 2>/dev/null || true
  exit 0
fi

# ── Rebuild path ───────────────────────────────────────────────────────────
# Reached only when the skip gate decided the HUD needs repair. Delegate to the
# installer's own functions so there is a single implementation. We source the
# installer lib and call install_omc_hud, providing the few globals it expects.
DRY_RUN=0
log()   { :; }   # SessionStart hook stdout is surfaced to the model as context;
debug() { :; }   # keep these quiet so a healthy/repaired HUD adds no noise.

# shellcheck source=/dev/null
if [[ -f "$REPO_DIR/installer/lib/omc.sh" ]]; then
  source "$REPO_DIR/installer/lib/omc.sh" 2>/dev/null && install_omc_hud 2>/dev/null || true
fi

# 발화 기록 — harness_stats 가 이 파일명 리터럴을 grep 한다. 실패해도 무시.
_log="${CLAUDE_PROJECT_DIR:-$PWD}/.omc/logs/hud_ensure.jsonl"
mkdir -p "$(dirname "$_log")" 2>/dev/null \
  && printf '{"ts":"%s","hook":"hud-ensure"}\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$_log" 2>/dev/null || true

exit 0

# shellcheck shell=sh
# claudebase — Claude Code CLI mouse-capture opt-out (drag-select fix).
#
# Sourced from the user's shell rc by installer/lib/claude_mouse.sh (opt-in).
# Wraps `claude` so it always launches with mouse capture disabled, which
# restores native / tmux drag-select. Claude Code's TUI captures mouse
# events, which breaks terminal text selection (anthropics/claude-code#66957,
# #63054). `command claude` runs the real binary (no recursion); only the
# `claude` command is touched, nothing else.
#
# Tradeoff: with mouse capture off, in-TUI mouse clicks/scroll stop working —
# use tmux copy-mode / the terminal's own scrollback instead. To revert, remove
# the marked `claudebase:claude-mouse` line from your rc.
#
# Deliberately NOT CLAUDE_CODE_NO_FLICKER=1 (was paired here until 2026-07-16):
# despite the name it is the opt-in switch for Claude's fullscreen renderer, i.e.
# the alternate screen buffer — so tmux/terminal scrollback stays empty (verified:
# tmux history_size=0) and the copy-mode fallback above cannot scroll at all.
# The two together left no way to scroll back: mouse-off hands the wheel to tmux,
# no-flicker leaves tmux nothing to scroll. Keep the flicker; keep the scrollback.
claude() {
  CLAUDE_CODE_DISABLE_MOUSE=1 command claude "$@"
}

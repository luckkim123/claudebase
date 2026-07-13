# shellcheck shell=sh
# claudebase — Claude Code CLI mouse-capture opt-out (drag-select fix).
#
# Sourced from the user's shell rc by installer/lib/claude_mouse.sh (opt-in).
# Wraps `claude` so it always launches with mouse capture disabled + no-flicker,
# which restores native / tmux drag-select. Claude Code's TUI captures mouse
# events, which breaks terminal text selection (anthropics/claude-code#66957,
# #63054). `command claude` runs the real binary (no recursion); only the
# `claude` command is touched, nothing else.
#
# Tradeoff: with mouse capture off, in-TUI mouse clicks/scroll stop working —
# use the keyboard / tmux copy-mode instead. To revert, remove the marked
# `claudebase:claude-mouse` line from your rc.
claude() {
  CLAUDE_CODE_DISABLE_MOUSE=1 CLAUDE_CODE_NO_FLICKER=1 command claude "$@"
}

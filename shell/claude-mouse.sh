# shellcheck shell=sh
# claudebase — Claude Code CLI fullscreen renderer, turned on per-machine.
#
# Sourced from the user's shell rc by installer/lib/claude_mouse.sh (opt-in).
# Wraps `claude` so it always launches with the fullscreen renderer. `command
# claude` runs the real binary (no recursion); only the `claude` command is
# touched, nothing else. To revert, remove the marked `claudebase:claude-mouse`
# line from your rc.
#
# Why the env var rather than `/tui fullscreen`: the docs call the `tui` setting
# and CLAUDE_CODE_NO_FLICKER equivalent, but `/tui` persists `tui` into
# ~/.claude/settings.json — which claudebase symlinks to the *tracked*
# config/settings.json, so the pref leaks into the synced repo every time (the
# recurring leak 654484a and 8904b63 are about). An rc env var is per-machine by
# construction and cannot leak.
#
# SCROLL_SPEED=3 because the VS Code integrated terminal sends exactly one wheel
# event per notch with no multiplier (documented); 3 is vim's default. Accepts
# 1-20; drop it on machines whose terminal already amplifies wheel events
# (Ghostty, iTerm2 with faster scrolling).
#
# Deliberately NOT CLAUDE_CODE_DISABLE_MOUSE=1 (paired here until 2026-07-16):
# it opts out of mouse capture, and its documented cost is losing "wheel
# scrolling inside Claude Code". Combined with fullscreen — whose alternate
# screen buffer leaves tmux scrollback empty (verified: tmux history_size=0) —
# that removed every way to scroll back at all: mouse-off hands the wheel to
# tmux, fullscreen leaves tmux nothing to scroll. Fullscreen's own mouse capture
# also beats the native selection the opt-out was protecting: click-drag selects
# and copies to the clipboard automatically on mouse release (and to the tmux
# paste buffer inside tmux). For a one-off native selection hold Shift (VS Code
# and most terminals), Fn (Terminal.app), or Option (iTerm2).
#
# The file name is historical: this was a mouse-capture opt-out before
# 2026-07-16. Kept so already-installed `claudebase:claude-mouse` rc lines on
# other machines keep resolving — a rename would silently no-op them.
claude() {
  CLAUDE_CODE_NO_FLICKER=1 CLAUDE_CODE_SCROLL_SPEED=3 command claude "$@"
}

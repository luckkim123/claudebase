#!/bin/bash
# omc_pane_label.sh - Apply persistent role labels to tmux panes (window-aware)
#
# Background:
#   Claude Code TUI dynamically overwrites pane_title with the current task
#   description, which obscures which pane is which worker. Earlier versions
#   of this script keyed labels on pane_index only — that collided across
#   windows (pane 0:0.0 and 0:1.0 share index 0 and got the same label).
#
#   This version keys labels on window.pane (e.g. "0.3" for window 0 pane 3,
#   "1.0" for window 1 pane 0) so labels are window-scoped. Window 2+
#   (user-owned) panes are NOT labeled by default — their pane_title is shown
#   as-is.
#
# Usage:
#   omc_pane_label.sh apply <W.P>=<label> [<W.P>=<label> ...]
#   omc_pane_label.sh clear
#   omc_pane_label.sh show
#   omc_pane_label.sh reapply       # re-set the underlying tmux pane_title
#                                   # for every stored label (recovers from
#                                   # TUI title-overwrite)
#
# Examples:
#   omc_pane_label.sh apply 0.0='[MAIN] User chat' 0.3='[W1] PPT Editor' \
#                           1.0='[W4] KRIT analyst' 1.1='[W5] PKRC analyst'
#   omc_pane_label.sh reapply         # restore titles overwritten by Claude TUI
#   omc_pane_label.sh clear
#   omc_pane_label.sh show
#
# Implementation:
#   - Stored as tmux user options: @omc_label__<W>_<P>="<label>"  (W.P → W_P, '.' is invalid in tmux option names)
#   - Applied by tmux select-pane -T to each pane (Claude TUI may override
#     during work; call `reapply` to restore)
#   - pane-border-status is set to top, pane-border-format shows the pane_title
#     directly (so labeled and unlabeled panes both render their own title)

set -euo pipefail

CMD="${1:-show}"

ensure_border_format() {
  tmux set -g pane-border-status top
  # Display pane_title directly. `allow-set-title off` (set below) blocks
  # Claude TUI's OSC escape from overwriting pane_title, so the label stays
  # whatever we set via `select-pane -T`. tmux 3.x doesn't expand nested
  # format `#{@option_#{window_index}_#{pane_index}}` inside pane-border-format,
  # which is why we don't lookup the user option directly here.
  tmux set -g pane-border-format ' #{pane_index}: #{?pane_title,#{pane_title},#{pane_current_command}} '
  # Block Claude TUI / other apps from sending OSC title escape sequences
  # to change pane_title. Without this they spam updates every 100-500ms
  # while thinking, making the border display flicker.
  tmux set -g allow-set-title off
}

opt_key() {
  # convert "0.3" → "@omc_label__0_3"
  echo "@omc_label__${1//./_}"
}

apply_labels() {
  shift  # remove "apply"
  if [[ $# -eq 0 ]]; then
    echo "Usage: $0 apply <W.P>=<label> [...]" >&2
    return 3
  fi
  ensure_border_format
  for kv in "$@"; do
    if [[ "$kv" != *"="* || "$kv" != *.* ]]; then
      echo "[skip] not in <W.P>=<label> form: $kv" >&2
      continue
    fi
    wp="${kv%%=*}"
    label="${kv#*=}"
    target="0:${wp}"               # assume session 0
    # Sanity check pane exists
    if ! tmux list-panes -t "$target" -F "#{pane_index}" >/dev/null 2>&1; then
      echo "[skip] pane $target not found" >&2
      continue
    fi
    tmux set -g "$(opt_key "$wp")" "$label"
    tmux select-pane -t "$target" -T "$label"
    echo "labeled $target: $label"
  done
  echo ""
  show_state
}

reapply_labels() {
  ensure_border_format
  echo "Re-applying stored labels to panes..."
  # Iterate over @omc_label__ options. tmux show -g format is:
  #   @omc_label__0_3 "[W1] PPT Editor"
  # Split on FIRST space only (option name has no spaces; value may have many).
  tmux show -g 2>/dev/null | grep '^@omc_label__' | while IFS= read -r line; do
    opt="${line%% *}"          # everything before first space
    val="${line#* }"           # everything after first space
    wp="${opt#@omc_label__}"
    wp="${wp//_/.}"
    target="0:${wp}"
    # Strip surrounding quotes from value
    label="${val#\"}"
    label="${label%\"}"
    if tmux list-panes -t "$target" -F "#{pane_index}" >/dev/null 2>&1; then
      tmux select-pane -t "$target" -T "$label"
      echo "re-applied $target: $label"
    else
      echo "[skip] $target no longer exists (clear option with: tmux set -gu $opt)"
    fi
  done
}

clear_labels() {
  tmux show -g 2>/dev/null | awk '/^@omc_label__/ {print $1}' | while read -r opt; do
    tmux set -gu "$opt" 2>/dev/null || true
    echo "cleared $opt"
  done
  tmux set -gu pane-border-format 2>/dev/null || true
  tmux set -gu pane-border-status 2>/dev/null || true
  tmux set -gu allow-set-title 2>/dev/null || true   # restore default (on)
  echo "cleared all omc pane labels."
}

show_state() {
  echo "pane-border-status: $(tmux show -g pane-border-status 2>/dev/null | awk '{print $2}')"
  echo ""
  echo "Stored labels (@omc_label__W_P):"
  tmux show -g 2>/dev/null | awk '/^@omc_label__/ {print "  "$0}'
  echo ""
  echo "Current panes (window.pane | tui_title):"
  tmux list-panes -a -F '  #{window_index}.#{pane_index}  title=[#{pane_title}]' 2>&1
}

watchdog_loop() {
  # Continuously reapply stored labels every N seconds. Run as:
  #   bash omc_pane_label.sh watchdog &  (background)
  # or  nohup bash omc_pane_label.sh watchdog > /tmp/omc_pane_label_watchdog.log 2>&1 &
  local interval="${1:-5}"
  echo "[watchdog] pid=$$ interval=${interval}s — auto-reapplying labels"
  while true; do
    tmux show -g 2>/dev/null | grep '^@omc_label__' | while IFS= read -r line; do
      opt="${line%% *}"
      val="${line#* }"
      wp="${opt#@omc_label__}"
      wp="${wp//_/.}"
      target="0:${wp}"
      label="${val#\"}"
      label="${label%\"}"
      if tmux list-panes -t "$target" -F "#{pane_index}" >/dev/null 2>&1; then
        # Only re-set if pane_title differs from stored label (avoid noise)
        current=$(tmux display-message -p -t "$target" "#{pane_title}" 2>/dev/null)
        if [[ "$current" != "$label" ]]; then
          tmux select-pane -t "$target" -T "$label" 2>/dev/null || true
        fi
      fi
    done
    sleep "$interval"
  done
}

stop_watchdog() {
  # Kill any running watchdog
  pkill -f "omc_pane_label.sh watchdog" 2>/dev/null && echo "watchdog stopped." || echo "no watchdog running."
}

case "$CMD" in
  apply)    apply_labels "$@" ;;
  reapply)  reapply_labels ;;
  clear)    clear_labels ;;
  show)     show_state ;;
  watchdog) shift; watchdog_loop "${1:-5}" ;;
  stop)     stop_watchdog ;;
  *)
    echo "Usage: $0 {apply|reapply|clear|show|watchdog [interval]|stop} [args]" >&2
    exit 3
    ;;
esac

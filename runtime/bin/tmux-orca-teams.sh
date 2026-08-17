#!/usr/bin/env sh
# tmux wrapper — restore Orca Agent Teams' tmux shim inside Claude Code.
#
# Orca's "Claude agent team" launcher runs `claude --teammate-mode auto` with
# its own `tmux` shim first on PATH (~/.orca/claude-agent-teams-bin) and TMUX
# pointing at a socket path only that shim understands — it forwards to
# `orca agent-teams-tmux`, which opens teammates as native Orca panes.
#
# Claude Code's settings `env.PATH` REPLACES PATH for every subprocess (no
# variable expansion — see README), so any launcher-injected directory is
# dropped at the subprocess boundary. Teammate spawning then resolves the real
# tmux, which tries to connect to a socket that does not exist and fails with
# "Could not determine current tmux pane/window". The failure surfaces two
# layers away from its cause, which is why this wrapper exists rather than a
# note in the docs.
#
# Installed as ~/.local/bin/tmux: the rendered PATH lists that directory ahead
# of Homebrew, while a login shell lists it behind — so Claude Code sessions get
# this wrapper and ordinary shells go straight to the real tmux. Prepending the
# Orca shim dir itself is NOT an option: it forwards unconditionally and answers
# "Missing agent team ID" outside a team session, breaking tmux everywhere else.
set -eu

if [ -n "${ORCA_AGENT_TEAMS_TEAM_ID:-}" ] &&
   [ -x "${ORCA_AGENT_TEAMS_SHIM_DIR:-/nonexistent}/tmux" ]; then
  exec "${ORCA_AGENT_TEAMS_SHIM_DIR}/tmux" "$@"
fi

# Not a team session (or Orca is not installed): hand over to the real tmux.
# Drop this wrapper's own directory first, or a PATH that leads with it recurses
# into this script forever. `$0`'s dirname is deliberately not resolved through
# the symlink — the directory on PATH is what must be removed, not the checkout.
self_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
PATH=$(printf '%s\n' "$PATH" | tr ':' '\n' | grep -vxF "$self_dir" |
       tr '\n' ':' | sed 's/:$//') || true
export PATH
exec tmux "$@"

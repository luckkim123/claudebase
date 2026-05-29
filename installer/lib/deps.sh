# shellcheck shell=bash
# installer/lib/deps.sh — runtime dependency probe.
#
# Source order: after lib/args.sh (needs $PLATFORM).
#
# Warn-only contract: prints WARNING + install hint per missing tool, never
# auto-installs and never exits. install.sh remains idempotent because every
# warning is the same line on every run.
#
# Exposed:
#   check_runtime_deps   — probe jq, gemini CLI, nano banana extension.

check_runtime_deps() {
  # jq — required by the statusLine command in claude/settings.json; without
  # it the status line silently renders as literal template text (e.g. "ctx:%").
  if ! command -v jq >/dev/null 2>&1; then
    printf '[install] WARNING: "jq" not found — statusLine will degrade silently\n'
    case "$PLATFORM" in
      macos) printf '[install]   install: brew install jq\n' ;;
      linux) printf '[install]   install: sudo apt-get install -y jq  (Debian/Ubuntu)\n' ;;
    esac
  fi

  # gemini CLI — required by the gen-image skill (Google nano banana image
  # generation). Without it /gen-image falls back to direct REST API calls
  # which work but bypass the MCP tool path documented in the skill.
  if ! command -v gemini >/dev/null 2>&1; then
    printf '[install] WARNING: "gemini" CLI not found — gen-image skill needs it\n'
    case "$PLATFORM" in
      macos) printf '[install]   install: brew install gemini-cli  (or: npm install -g @google/gemini-cli)\n' ;;
      linux) printf '[install]   install: npm install -g @google/gemini-cli\n' ;;
    esac
  else
    # gemini present — also verify the nano banana extension is installed.
    # The extension exposes the mcp_nanobanana_generate_image tool the
    # gen-image skill expects. Without it the skill silently degrades to
    # text-only Gemini responses.
    if [[ ! -d "$HOME/.gemini/extensions/nanobanana" ]]; then
      printf '[install] WARNING: nano banana extension missing — gen-image MCP path disabled\n'
      printf '[install]   install: gemini extensions install https://github.com/gemini-cli-extensions/nanobanana\n'
    fi
  fi
}

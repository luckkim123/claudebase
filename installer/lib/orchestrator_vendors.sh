# shellcheck shell=bash
# installer/lib/orchestrator_vendors.sh — OPT-IN: record which vendor CLIs this
# machine can actually reach, for oh-my-orchestrator's role -> backend table.
#
# Source order: after lib/args.sh (DRY_RUN) and lib/log.sh (log/debug/run).
#
# Exposes:
#   maybe_record_orchestrator_vendors  — probe the vendor CLIs once, write the
#                                        result to a machine-local file.
#
# Why this exists: oh-my-orchestrator binds each role to a backend in its
# config.json, and that file is tracked and shared across machines. A binding is
# only real if the CLI is installed *here*. The 2026-08-26 audit found three of
# six roles pointing at CLIs absent from the machine -- explore at opencode,
# frontend and document-writer at gemini -- and nothing had noticed, because a
# tracked config cannot know what any particular machine has.
#
# So the answer lands in a MACHINE-LOCAL file. Writing it into a tracked file is
# exactly how a per-machine fact leaks to every other machine.
#
# Why opt-in: probing runs each CLI's --version, and installing one is the
# user's call, not the installer's. Default No, ask once, marker makes every
# later run a pure no-op (repo rule #5).

ORCHESTRATOR_VENDORS_FILE="$HOME/.claude/orchestrator-vendors.local.json"

# Vendors codeagent-wrapper can actually dispatch to. agy (antigravity) is
# deliberately absent: it is a working CLI, but internal/backend/registry.go has
# no agy backend and each backend's Command() is hardcoded with no config
# override, so nothing can route to it. It is probed for the record only.
_ORCHESTRATOR_WIRED_VENDORS=(codex claude gemini opencode)
_ORCHESTRATOR_PROBE_ONLY=(agy)

_orchestrator_probe() {
  local name="$1"
  command -v "$name" >/dev/null 2>&1 && printf 'true' || printf 'false'
}

maybe_record_orchestrator_vendors() {
  # Already recorded → pure no-op (idempotency contract).
  if [[ -f "$ORCHESTRATOR_VENDORS_FILE" ]]; then
    debug "orchestrator-vendors: already recorded at $ORCHESTRATOR_VENDORS_FILE (skip)"
    return
  fi

  # Opt-in gate: forced by env, else prompt (default No), else silent skip.
  if [[ "${INSTALL_ORCHESTRATOR_VENDORS:-}" != "1" ]]; then
    [[ -t 0 ]] || { debug "orchestrator-vendors: non-interactive, skipping opt-in prompt"; return; }
    local reply=""
    printf '[install] Optional: probe which vendor CLIs (codex/claude/gemini/opencode/agy) this machine has, for oh-my-orchestrator? [y/N] '
    read -r reply || reply=""
    case "$reply" in
      y|Y|yes|YES) ;;
      *) log "orchestrator-vendors: skipped (re-run with INSTALL_ORCHESTRATOR_VENDORS=1 to record non-interactively)"; return ;;
    esac
  fi

  local wired="" probe="" name=""
  for name in "${_ORCHESTRATOR_WIRED_VENDORS[@]}"; do
    wired+="$(printf '\n    "%s": %s,' "$name" "$(_orchestrator_probe "$name")")"
  done
  for name in "${_ORCHESTRATOR_PROBE_ONLY[@]}"; do
    probe+="$(printf '\n    "%s": %s,' "$name" "$(_orchestrator_probe "$name")")"
  done
  wired="${wired%,}"
  probe="${probe%,}"

  if [[ ${DRY_RUN:-0} -eq 1 ]]; then
    log "[dry-run] would write vendor probe results to $ORCHESTRATOR_VENDORS_FILE"
    return
  fi

  mkdir -p "$(dirname "$ORCHESTRATOR_VENDORS_FILE")"
  cat > "$ORCHESTRATOR_VENDORS_FILE" <<JSON
{
  "_comment": "Machine-local. Written once by installer/lib/orchestrator_vendors.sh. Delete this file and re-run the installer to re-probe. Presence on PATH is not authentication -- verify with one cheap call before routing a role to a vendor.",
  "probed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "wired": {$wired
  },
  "probe_only": {$probe
  }
}
JSON
  log "orchestrator-vendors: recorded to $ORCHESTRATOR_VENDORS_FILE"

  # Point out the gap rather than fixing it: installing a CLI is the user's call.
  if ! command -v codex >/dev/null 2>&1; then
    log "orchestrator-vendors: codex is absent — 'npm install -g @openai/codex' if you want that backend"
  fi
}

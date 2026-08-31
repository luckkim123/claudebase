# shellcheck shell=bash
# installer/lib/orchestrator_vendors.sh — OPT-IN: record which vendor CLIs this
# machine can actually reach, for oh-my-orchestrator's role -> backend table.
#
# Source order: after lib/args.sh (DRY_RUN) and lib/log.sh (log/debug/run).
#
# Exposes:
#   maybe_record_orchestrator_vendors  — probe the vendor CLIs once, write the
#                                        result to a machine-local file.
#   ensure_codeagent_wrapper           — build the Go entry point the omo
#                                        plugin ships, onto PATH.
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

# ─── codeagent-wrapper: the entry point every omo consultation goes through ──
#
# omo ships this as Go *source* inside the plugin, never as a built artifact, so
# `claude plugin update` moves the source and leaves whatever binary is on PATH
# untouched. Nothing else in this installer builds Go, which meant the binary
# was the one layer no sync reached.
#
# What that cost, measured 2026-08-31: omo 0.19.0 shipped a call ledger, and for
# the seven hours after it shipped the ledger recorded three rows -- all from
# explicit-path invocations -- because PATH still resolved to a build from two
# days earlier. omo's own pre-flight check is `command -v codeagent-wrapper`,
# which passes on a stale binary: presence is not currency.
#
# The version is injected rather than derived. The Makefile takes it from
# `git describe`, and a plugin cache has no `.git`, so a plain `make build`
# there reports `dev` -- unusable for the very --version comparison omo's
# SKILL.md now tells a session to make. The cache directory *name* is the
# plugin version, so that is what goes in.

CODEAGENT_WRAPPER_BIN="$HOME/.local/bin/codeagent-wrapper"
_OMO_CACHE_BASE="$HOME/.claude/plugins/cache/heroacademia/oh-my-orchestrator"

# Newest installed omo cache dir that actually carries the wrapper source.
# Prints the directory (no trailing slash) or nothing.
# ponytail: picks the newest cache dir rather than reading the live version
# out of installed_plugins.json. The two differ only after a deliberate
# downgrade, where this builds a wrapper one version ahead of the installed
# skill and self-heals on the next update. Read the live version if that
# stops being acceptable.
_omo_newest_cache_dir() {
  [[ -d "$_OMO_CACHE_BASE" ]] || return 0
  local d v best="" bestv=""
  for d in "$_OMO_CACHE_BASE"/*; do
    [[ -d "$d/codeagent-wrapper/cmd/codeagent-wrapper" ]] || continue
    v="${d##*/}"
    if [[ -z "$bestv" ]] || [[ "$(printf '%s\n%s\n' "$bestv" "$v" | sort -V | tail -1)" == "$v" ]]; then
      best="$d"; bestv="$v"
    fi
  done
  printf '%s' "$best"
}

ensure_codeagent_wrapper() {
  local src version want have
  src="$(_omo_newest_cache_dir)"
  if [[ -z "$src" ]]; then
    debug "codeagent-wrapper: oh-my-orchestrator not installed here (skip)"
    return
  fi
  version="${src##*/}"
  want="v$version"

  # A symlink here is a deliberate developer arrangement: omo's own README tells
  # a contributor to link PATH at their own build so `make install` is live with
  # no second step. Overwriting it would take that dev loop away silently.
  if [[ -L "$CODEAGENT_WRAPPER_BIN" ]]; then
    log "codeagent-wrapper: $CODEAGENT_WRAPPER_BIN is a symlink (developer build) — left alone"
    return
  fi

  have=""
  if [[ -x "$CODEAGENT_WRAPPER_BIN" ]]; then
    have="$("$CODEAGENT_WRAPPER_BIN" --version 2>/dev/null | awk '{print $NF}')"
  fi
  if [[ -n "$have" && "$have" == "$want" ]]; then
    debug "codeagent-wrapper: already $want (skip)"
    return
  fi

  if ! command -v go >/dev/null 2>&1; then
    log "codeagent-wrapper: go not on PATH — omo's vendor lane stays on ${have:-nothing} until Go is installed and install.sh re-run"
    return
  fi

  if [[ ${DRY_RUN:-0} -eq 1 ]]; then
    log "[dry-run] would build codeagent-wrapper $want into $CODEAGENT_WRAPPER_BIN (currently ${have:-absent})"
    return
  fi

  mkdir -p "$(dirname "$CODEAGENT_WRAPPER_BIN")"
  if ( cd "$src/codeagent-wrapper" \
       && go build -ldflags "-X codeagent-wrapper/internal/app.version=$want" \
            -o "$CODEAGENT_WRAPPER_BIN" ./cmd/codeagent-wrapper ) >/dev/null 2>&1; then
    log "codeagent-wrapper: built $want (was ${have:-absent})"
  else
    log "WARNING: codeagent-wrapper build failed in $src/codeagent-wrapper — omo's vendor lane stays on ${have:-nothing}"
  fi
}

# shellcheck shell=bash
# installer/lib/omx.sh — idempotent editable install of the omx-core CLI.
#
# Source order: after lib/args.sh (DRY_RUN) and lib/log.sh (log/debug/run).
#
# Exposes:
#   ensure_omx_install   — (re)install omx-core editable from its local checkout
#                          so the `omx` CLI imports without a manual PYTHONPATH.
#
# Why this exists: omx-core is installed with `pip install -e` (editable), which
# does NOT copy code — it writes a .pth finder that points at the SOURCE dir.
# When the oh-my-experiments checkout moves (e.g. /workspace -> /root), the
# finder keeps pointing at the OLD path, `import omx_core` fails with
# ModuleNotFoundError, and yet the dist-info still claims "installed". The CLI
# (/usr/local/bin/omx) then dies on every call and the exp-analyze/-design
# skills silently fall back to hand-reading. This step re-pins the editable
# install to the CURRENT checkout, so a moved repo self-heals on the next
# `install.sh` run instead of needing a manual `pip install -e` rescue.
#
# Idempotent: if `omx_core` already imports AND its editable direct_url already
# points at the resolved source dir, we SKIP silently (no reinstall, no nag) —
# same spirit as lib/viewer.sh's up-to-date skip. Only a missing/mis-pinned
# install triggers the reinstall.
#
# Source-dir resolution (first hit wins):
#   1. $OMX_SOURCE_DIR                       (explicit override; machine-specific)
#   2. $REPO_DIR/../oh-my-experiments/omx-core   (sibling of claudebase)
#   3. $HOME/oh-my-experiments/omx-core
# omx lives in its OWN repo, so claudebase cannot hardcode one absolute path
# (it ships to every machine). We probe the conventional spots and, if none
# exist, warn-and-skip (deps.sh pattern) rather than guess.

resolve_omx_source() {
  # Echo the first existing omx-core source dir, or empty if none found.
  local candidates=(
    "${OMX_SOURCE_DIR:-}"
    "$REPO_DIR/../oh-my-experiments/omx-core"
    "$HOME/oh-my-experiments/omx-core"
  )
  local c
  for c in "${candidates[@]}"; do
    [[ -n "$c" && -f "$c/omx_core/__init__.py" ]] || continue
    ( cd "$c" && pwd )   # absolute, symlink-resolved
    return 0
  done
  return 1
}

ensure_omx_install() {
  # Need pip; without it we cannot manage the editable install. Warn + skip
  # (deps.sh contract: same line every run, never exits).
  if ! command -v pip >/dev/null 2>&1 && ! python3 -m pip --version >/dev/null 2>&1; then
    printf '[install] WARNING: pip not found — cannot ensure omx CLI; `omx` may fail\n'
    return
  fi

  local src
  if ! src="$(resolve_omx_source)"; then
    printf '[install] WARNING: omx-core source not found — `omx` CLI not (re)installed\n'
    printf '[install]   set OMX_SOURCE_DIR=/path/to/oh-my-experiments/omx-core, or place the\n'
    printf '[install]   checkout beside claudebase (../oh-my-experiments) or at ~/oh-my-experiments\n'
    return
  fi

  # Idempotent skip: already importable AND already pinned to THIS source dir.
  # direct_url.json holds the editable target as a file:// URL; compare it to
  # the resolved source so a moved checkout (stale pin) still triggers a fix.
  local pinned
  pinned="$(python3 - "$src" <<'PY' 2>/dev/null || true
import json, sys
from importlib import metadata
src = sys.argv[1]
try:
    import omx_core  # noqa: F401  (import must succeed)
    du = metadata.distribution("omx-core").read_text("direct_url.json")
    url = json.loads(du)["url"] if du else ""
    print("ok" if url == "file://" + src else "stale")
except Exception:
    print("broken")
PY
)"
  if [[ "$pinned" == "ok" ]]; then
    debug "omx: editable install already pinned to $src (skip)"
    return
  fi

  if [[ ${DRY_RUN:-0} -eq 1 ]]; then
    log "[dry-run] would reinstall omx-core editable from $src (state: ${pinned:-unknown})"
    return
  fi

  log "omx: (re)installing editable from $src (was: ${pinned:-unknown})"
  # --break-system-packages: this container's python3 is PEP-668 externally-
  # managed; the original install used the same flag. -e keeps it editable so
  # source edits take effect without reinstall during development.
  if python3 -m pip install -e "$src" --break-system-packages >/dev/null 2>&1; then
    if python3 -c 'import omx_core' >/dev/null 2>&1; then
      log "omx: CLI ready (import omx_core OK)"
    else
      printf '[install] WARNING: omx reinstalled but `import omx_core` still fails — check %s\n' "$src"
    fi
  else
    printf '[install] WARNING: `pip install -e %s` failed — `omx` CLI may not work\n' "$src"
  fi
}

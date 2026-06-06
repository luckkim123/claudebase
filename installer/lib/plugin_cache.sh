# shellcheck shell=bash
# installer/lib/plugin_cache.sh — prune stale plugin-cache versions.
#
# Source order: after lib/args.sh (DRY_RUN) and lib/log.sh (log/debug/run).
#
# Exposes:
#   prune_plugin_cache   — keep only the newest SemVer dir per cached plugin,
#                          deleting older SemVer versions. Conservative.
#
# Why: marketplace auto-update fetches the new version but NEVER deletes the old
# one, so ~/.claude/plugins/cache/<mkt>/<plugin>/ accumulates stale versions
# (e.g. omc 4.14.1 + 4.14.4 + 4.14.5, each up to ~40MB). This step trims them so
# the cache reflects the active set instead of growing without bound.
#
# Safety (this is cache deletion — be conservative):
#   * Only SemVer-shaped version dirs (N.N.N, optional -suffix) are candidates.
#     Non-SemVer dirs (git-sha pins like 8790bf9b3fb7, or anything unrecognized)
#     are LEFT UNTOUCHED — we cannot order them reliably, and the active pin may
#     be any of them.
#   * Among the SemVer dirs we keep the single highest (sort -V) and delete the
#     rest. If only one SemVer dir exists, nothing is removed.
#   * A plugin whose dirs are ALL non-SemVer is skipped entirely (no deletion).
#   * Deletion is `rm -rf` of a cache dir only (never source, never settings).
#     Cache is regenerable: a wrongly-trimmed active version is re-fetched on the
#     next plugin load / update, so the worst case is a one-time re-download, not
#     data loss. DRY_RUN prints intents without deleting.

_is_semver() {
  # N.N.N with an optional -prerelease / +build suffix.
  [[ "$1" =~ ^[0-9]+\.[0-9]+\.[0-9]+([-+][0-9A-Za-z.-]+)?$ ]]
}

prune_plugin_cache() {
  local cache_root="$HOME/.claude/plugins/cache"
  [[ -d "$cache_root" ]] || { debug "plugin-cache: no $cache_root (skip)"; return; }

  local removed=0 kept=0 plugin_dir
  # <cache>/<marketplace>/<plugin>/ holds the version dirs.
  while IFS= read -r plugin_dir; do
    [[ -d "$plugin_dir" ]] || continue

    # Collect SemVer version dirs (basenames) under this plugin.
    local semvers=() name
    for d in "$plugin_dir"/*/; do
      [[ -d "$d" ]] || continue
      name="$(basename "$d")"
      _is_semver "$name" && semvers+=("$name")
    done

    # Need at least 2 SemVer dirs to have anything stale to remove.
    (( ${#semvers[@]} >= 2 )) || continue

    # Highest SemVer is the keeper; everything else SemVer is stale.
    local newest
    newest="$(printf '%s\n' "${semvers[@]}" | sort -V | tail -1)"
    kept=$((kept + 1))

    local v
    for v in "${semvers[@]}"; do
      [[ "$v" == "$newest" ]] && continue
      if [[ ${DRY_RUN:-0} -eq 1 ]]; then
        log "[dry-run] would remove stale cache: ${plugin_dir#"$cache_root"/}/$v (keep $newest)"
      else
        rm -rf "${plugin_dir:?}/$v" && removed=$((removed + 1))
        debug "plugin-cache: removed ${plugin_dir#"$cache_root"/}/$v (kept $newest)"
      fi
    done
  done < <(find "$cache_root" -mindepth 2 -maxdepth 2 -type d 2>/dev/null)

  if [[ ${DRY_RUN:-0} -ne 1 && $removed -gt 0 ]]; then
    log "plugin-cache: pruned $removed stale version(s) across $kept plugin(s)"
  else
    debug "plugin-cache: $kept plugin(s) with multiple SemVer dirs, nothing to prune"
  fi
}

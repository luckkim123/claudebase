#!/usr/bin/env bash
# migrate-om-store — move an om* harness state store into the unified `.hq/` root.
#
# The spec this implements is `oh-my-orchestrator`'s
# `skills/harness/references/store-spec.md`: one `.hq/` per anchor, four layers
# (`config/` `community/` `runtime/` `work/`), the layer decided **per file**
# rather than per directory (§3, §9.3). Phases 3 and 4 of the unification did
# those moves by hand with a throwaway script per anchor. This is that script
# made canonical, because the remaining anchors (§9.1: workspace's 871-file
# `.omd`, the two `.orchestration` boards, `krit/simulator`) are too many to
# re-derive a mapping for each time, and re-deriving is exactly where the
# campaign kept losing rows.
#
# Three properties are load-bearing, and each exists because something silently
# passed without it:
#
#   1. **Dry-run is the default.** Writing needs `apply`, and `apply` never
#      deletes: it copies and then verifies by sha256 (store-spec §7 — the
#      legacy store stays until a separate `purge`).
#
#   2. **An unmapped path is a FAIL, not a skip.** A file the table does not
#      claim exits 2 and takes the whole anchor with it. A migration that
#      quietly steps over what it does not recognise is indistinguishable from
#      one that finished, which is the shape of every defect this campaign
#      found (P4's `finding/013`: three separate gates all returned "pass" on a
#      whole anchor nobody had touched).
#
#   3. **Forward and reverse read the same table.** `reverse` merges new-path
#      writes back to the legacy store — the reversible path the rollback
#      procedure assumes exists. It is derived by inverting the rules below
#      rather than by a second table, because two tables drift and the drift is
#      invisible until a rollback is actually needed.
#
# Census and drift are deliberately **different instruments** (§9, and the
# plan's 4th-round C1). `census` discovers anchors from the filesystem — the
# fixed unbounded-depth `find`, crossed with `git ls-files`. `drift` never runs
# that find: it reads `.hq/config/migrated.jsonl` and compares legacy-file
# mtimes against the recorded migration timestamp. Sharing one command between
# them would leave zero independent detectors, so each one's blind spot is the
# other's coverage: census sees an anchor with no ledger row, drift sees a
# ledger row whose legacy store kept being written to.
#
# Usage:
#   migrate-om-store plan    ANCHOR...     what would move (default verb)
#   migrate-om-store apply   ANCHOR...     copy + sha256 verify; deletes nothing
#   migrate-om-store reverse ANCHOR...     merge `.hq/` writes back to legacy
#   migrate-om-store purge   ANCHOR        trash the legacy store (prompts; §7)
#   migrate-om-store census  [--root DIR]  the anchor roster (find x git ls-files)
#   migrate-om-store drift   ANCHOR...     split-brain check (ledger vs mtime)
#   migrate-om-store audit   ANCHOR...     git config vs store-spec §5 + §2
#   migrate-om-store selftest              round-trip every mapping rule
#
# ANCHOR is the directory that holds the legacy store, not the store itself,
# and one anchor routinely holds several (the vault has `.omp` + `.oms` +
# `.omha`). Every store present is processed; `--store .omp` narrows to one,
# and `purge` requires that narrowing when there is more than one:
#   migrate-om-store plan  ~/Desktop/workspace
#   migrate-om-store plan  ~/ksm_Obsidian --store .omp
#
# Env:
#   HQ_MACHINE      the `machine` label written to `migrated.jsonl` by `apply`.
#                   Defaults to `hostname -s`, which is NOT always the label the
#                   §10 roster uses (this Mac: hostname `gwe52`, roster `ksm-mac`).
#   HQ_D2_RELEASED  =1 opens the `.omx` gate (see `is_gated`).
#
# Exit codes: 0 ok · 1 usage · 2 unmapped path · 3 refused · 4 conflict · 5 drift ·
#             6 undefined (no ledger row for this store — it was never cut over) ·
#             7 anchor git config does not satisfy store-spec §5/§2 (`audit`).
#
# 6 exists because `drift` used to return 0 there. It said so in prose — "this
# store was never cut over" — but an acceptance check written against `$?`, which
# is how this campaign's rounds are checked, read that 0 as "verified clean". A
# not-run check and a passed check must not share an exit code (P7; the same
# shape as `finding/013`).

set -u

SELF="migrate-om-store"
HQ=".hq"

# Every legacy store dir name the census knows. `.omx` is listed so the census
# reports it and the gate below refuses it — omitting it would make a gated
# anchor look like an absent one.
LEGACY_DIRS=".omp .oms .omd .omx .omha .orchestration"

err()  { printf '%s: %s\n' "$SELF" "$*" >&2; }
note() { printf '%s\n' "$*"; }

sha() {
  if command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | cut -d' ' -f1
  else sha256sum "$1" | cut -d' ' -f1; fi
}

# --------------------------------------------------------------------------
# The mapping table (store-spec §9.3, plus the rows the spec's list did not
# carry — see the deviation notes below the table).
#
# Row format: mode|legacy|new
#   file  exact legacy relative path            <-> exact new relative path
#   glob  legacy path pattern                   <-> new DIRECTORY, basename kept
#   path  legacy path pattern                   <-> new prefix + the whole path
#   dir   legacy directory prefix               <-> new directory prefix
#   slug  any unclaimed TOP-LEVEL DIRECTORY     <-> new prefix + <dir>/...
#
# `path` is `glob` for a pattern whose *directory part varies* — it keeps the
# matched path whole instead of reducing it to a basename, which is what lets a
# per-file row reach inside `programs/<id>/` where the id is not known in
# advance (`glob` would collapse every program's `program.json` onto one
# destination). It is placed before the `dir` row it carves out of.
#
# Order matters: the first matching row wins, so exact `file` rows precede the
# `dir`/`glob`/`path` rows that would otherwise swallow them, and `slug` is always
# last. A top-level *file* that no row claims is unmapped and fails; a
# top-level *directory* that no row claims is a slug where the store has slugs
# (`oms`, `omd`) and a failure where it does not. That asymmetry is the
# detector's known limit: `oms`/`omd` cannot distinguish a stray directory from
# a real work slug, so `plan` prints slug matches on their own `SLUG` line for
# a human to read.
#
# Every `new` prefix must be unique within a kind, or `reverse` becomes
# ambiguous. `selftest` asserts exactly that.
# --------------------------------------------------------------------------
rules_for() {
  case "$1" in
  omp) cat <<'EOF'
file|rules.json|config/project/rules.json
file|manifest.json|config/project/manifest.json
file|STRUCTURE.md|config/project/STRUCTURE.md
file|DATASETS.md|config/project/DATASETS.md
file|learned.md|config/project/learned.md
file|PROJECT.md|community/PROJECT.md
file|NAMING.md|community/NAMING.md
file|CONVENTIONS.md|community/CONVENTIONS.md
file|garden-state.json|runtime/project/garden-state.json
file|state/verify-throttle.json|runtime/project/verify-throttle.json
dir|secretary|config/project/secretary
dir|env|config/project/env
dir|wiki|community/wiki
dir|work|work/project
EOF
  ;;
  oms) cat <<'EOF'
file|learned.md|config/scholar/learned.md
file|state/verified-citations.json|config/scholar/verified-citations.json
file|section3_audit_workflow.js|config/scholar/section3_audit_workflow.js
glob|state/pilot-*.json|runtime/scholar
glob|state/revise-*.json|runtime/scholar
dir|venues|config/scholar/venues
dir|workflows|config/scholar/workflows
dir|wiki|community/wiki
dir|_backport-design|community/_backport-design
slug|*|work/scholar
EOF
  ;;
  omd) cat <<'EOF'
file|learned.md|config/docs/learned.md
file|.hook-throttle.json|runtime/docs/.hook-throttle.json
file|HANDOFF_omd_audit.md|community/posts/HANDOFF_omd_audit.md
dir|wiki|community/wiki
slug|*|work/docs
EOF
  ;;
  omha) cat <<'EOF'
file|routing.jsonl|runtime/routing/routing.jsonl
file|redact-patterns.txt|runtime/routing/redact-patterns.txt
file|redact-patterns.example.txt|config/routing/redact-patterns.example.txt
EOF
  ;;
  omo) cat <<'EOF'
file|HUB.md|community/HUB.md
file|INDEX.md|community/INDEX.md
file|README.md|community/README.md
file|HUB-night-archive.md|community/HUB-night-archive.md
file|PHASE1-SYNTHESIS.md|community/PHASE1-SYNTHESIS.md
file|discussion-legacy.md|community/discussion-legacy.md
file|board.json|runtime/board.json
file|harness-progress.txt|runtime/harness-progress.txt
dir|posts|community/posts
dir|agents|community/agents
dir|sessions|community/sessions
dir|rules|community/rules
dir|knowledge|community/knowledge
EOF
  ;;
  omx) cat <<'EOF'
file|state.json|runtime/experiments/state.json
file|state/produced-reports.jsonl|config/experiments/produced-reports.jsonl
file|registry/index.md|community/wiki/index.md
file|registry/log.md|runtime/experiments/registry/log.md
dir|registry/findings|community/wiki
dir|.omx|runtime/experiments/nested-omx
dir|profile|config/experiments/profile
dir|recipes|community/recipes
path|programs/*/program.json|config/experiments
dir|programs|community/programs
dir|runs|work/experiments/runs
dir|campaigns|work/experiments/campaigns
dir|scratch|runtime/experiments/scratch
dir|.trash|runtime/experiments/trash
EOF
  ;;
  *) return 1 ;;
  esac
}
#
# Deviations from store-spec §9.3, recorded rather than silently applied:
#
#   * `omp` `env/` — the spec's omp table has no row for it. `krit/simulator`
#     has one (7 files: Dockerfile, compose, entrypoint, .repos). It is the
#     `omp-env` stage's canonical asset directory, hand-authored and read by a
#     verb, so (3) `config/project/env/`.
#   * `omo` `INDEX.md` and `.hq-lock` — neither is in the spec's omo row. Both
#     boards carry an `INDEX.md` ((2) community, alongside `HUB.md`). `.hq-lock`
#     is `hq`'s write lock (`hq/store.py:156`), recreated on demand, so it is
#     skipped rather than layered.
#   * `omo` `knowledge/` lands in `community/knowledge/`, not the spec's
#     `community/posts/`. The spec's `posts/` target assumes the §4 conversion
#     (each page gains a `subject:` and becomes a post); P3 made the same call
#     for `wiki/` — move the layer now, defer the *form* to P6. Keeping the
#     directory distinct also keeps `reverse` unambiguous, which a merge into
#     `posts/` would destroy.
#   * `omd` `wiki/` — absent from the spec's omd row; workspace's store has
#     `wiki/{convention,pattern,technique}/`. Same layer as omp's and oms's.
#   * `oms` `section3_audit_workflow.js` — a Workflow script (`export const
#     meta`) sitting at the store root instead of inside `workflows/`, found in
#     `12_Masters_Thesis/.oms` (**added P6**). Same class as `workflows/*.js`
#     — hand-authored, executed by a verb — so (3) `config/scholar/`. It keeps
#     its root position rather than being tidied into `workflows/`: this table
#     assigns layers, and normalising placement here would make `reverse` put
#     the file somewhere it has never been. A general `glob|*.js` row is not
#     available — shell `*` spans `/`, so it would also swallow a work slug's
#     own `.js` before the `slug` row ever ran.
#   * `omo` four root-level `.md` files — `README.md`, `HUB-night-archive.md`,
#     `PHASE1-SYNTHESIS.md`, `discussion-legacy.md`. None is in the spec's omo
#     row, which names only `HUB.md`/`INDEX.md`; albc's board carries all four
#     (**added P7**). All (2) prose beside `HUB.md`, so `community/`. Written as
#     explicit `file` rows rather than a trailing `glob|*.md|community`, because
#     shell `*` spans `/` — that glob would also swallow any future top-level
#     directory's `.md` and turn the FAIL contract into a silent catch-all.
#   * `omx` is added whole here (**P7**); the spec's §9.3 said only "deferred to
#     P7". Layer calls worth naming:
#       - `registry/findings/*.md` -> `community/wiki/`, matching omp's, oms's
#         and omd's `wiki/`. `omx wiki` lints these pages, but so does
#         `omp_content_audit.py:152` (`lint_wiki`) for omp's, and the spec put
#         that one in `community/`. (3) is for content a program consumes as
#         input, not for content a linter audits.
#       - `registry/index.md` -> `community/wiki/index.md`: derived but tracked,
#         the same call the spec makes for `community/INDEX.md` and oms's
#         `wiki/INDEX.md`. On a case-insensitive filesystem this collides with
#         an oms `wiki/INDEX.md` in the *same* anchor; no censused anchor holds
#         both, and the rename is deferred rather than guessed.
#       - `registry/log.md` -> `runtime/`: (5). It chronicles wiki *operations*
#         (`add`, `query`), not the knowledge; the pages are the record, so
#         losing it is harmless. This **detracks a tracked file** (albc's is in
#         vault git) — an approval item, same class as `garden-state.json`.
#       - `programs/` is **split**, which is why the `path` mode exists:
#         `program.json` is parsed (`campaign.py:305,346`) so (3) `config/`,
#         while `PLAN.md`/`HANDOFF.md` are seeded from templates and thereafter
#         hand-written — `campaign.py:360` only tests `.is_file()`, nothing
#         reads their bodies — so (2) `community/`. Sending the directory whole
#         to `work/experiments/programs/` (store-spec §3's tree sketch) would
#         have put albc's campaign PLAN.md, the plan of record, behind
#         `**/.hq/work/` in `.gitignore` and untracked it. §3's tree is amended
#         to match.
#       - `runs/` and `campaigns/` stay whole (`work/experiments/`), as §3's
#         tree says. No censused store has either directory, so a per-file split
#         inside them would be invented rather than measured — deferred the same
#         way omp's `env/` and omd's `wiki/` were, until a store carrying them
#         is censused.
#       - `.trash/` -> `runtime/experiments/trash/` (⑤). Absent from every
#         censused store; found only because the prose audit noticed `clean.py`
#         resolves it as `paths.omx_dir / ".trash"` unconditionally. It has to
#         move: left at the legacy path, the first `omx clean` after a `--purge`
#         recreates `.omx/` and undoes the purge.
#       - `.omx/` (the nested self-directory, store-spec §9.1 row 5) is mapped,
#         not skipped and not made its own anchor. It holds one real file, a
#         wiki log written by a misrooted `--root .../.omx` invocation. Skipping
#         means never carrying it across and losing it at `--purge`, which is
#         what skipping is for (third-party, locks) and not what this is; a
#         separate anchor would need a unique `.hq/.anchor` inside another
#         store, which §2's granularity rule does not describe. One `dir` row
#         preserves the bytes and keeps `reverse` unambiguous.

# Paths never moved, at any depth, for every kind. `.omc/` is third-party
# (`OMC_STATE_DIR`, store-spec §12); `.DS_Store` is not ours; `.hq-lock` is a
# lock file recreated on demand.
is_skipped() {
  case "$1" in
    .DS_Store|*/.DS_Store) return 0 ;;
    .hq-lock|*/.hq-lock)   return 0 ;;
    .omc|.omc/*|*/.omc/*)  return 0 ;;
    # omx's three mutex files, same call as `.hq-lock`: `.wiki-lock` (fcntl,
    # `omx_paths.wiki_lock`), `.loop-lock` (per-run O_EXCL lease), `.state-lock`
    # (state.json critical section). All recreated on demand; a copied lease
    # would be worse than an absent one.
    .wiki-lock|*/.wiki-lock|.loop-lock|*/.loop-lock|.state-lock|*/.state-lock) return 0 ;;
  esac
  return 1
}

kind_of() {
  case "$1" in
    .omp) echo omp ;; .oms) echo oms ;; .omd) echo omd ;;
    .omha) echo omha ;; .orchestration) echo omo ;; .omx) echo omx ;;
    *) return 1 ;;
  esac
}

# map_forward KIND REL -> prints new relative path.
# rc 0 mapped · 1 unmapped · 2 deliberately skipped · 3 slug match (still prints)
map_forward() {
  local kind="$1" rel="$2" mode lg nw top
  is_skipped "$rel" && return 2
  while IFS='|' read -r mode lg nw; do
    [ -n "${mode:-}" ] || continue
    case "$mode" in
      file) [ "$rel" = "$lg" ] && { printf '%s\n' "$nw"; return 0; } ;;
      glob) case "$rel" in $lg) printf '%s/%s\n' "$nw" "${rel##*/}"; return 0 ;; esac ;;
      path) case "$rel" in $lg) printf '%s/%s\n' "$nw" "$rel"; return 0 ;; esac ;;
      dir)  case "$rel" in "$lg"/*) printf '%s/%s\n' "$nw" "${rel#"$lg"/}"; return 0 ;; esac ;;
      slug) top="${rel%%/*}"
            if [ "$top" != "$rel" ]; then printf '%s/%s\n' "$nw" "$rel"; return 3; fi ;;
    esac
  done <<EOF
$(rules_for "$kind")
EOF
  return 1
}

# map_reverse KIND NEWREL -> prints legacy relative path.
# rc 0 mapped · 1 no legacy origin · 2 store-owned file with no legacy form
map_reverse() {
  local kind="$1" new="$2" mode lg nw base ldir
  case "$new" in
    .anchor|config/migrated.jsonl) return 2 ;;
  esac
  is_skipped "$new" && return 2
  while IFS='|' read -r mode lg nw; do
    [ -n "${mode:-}" ] || continue
    case "$mode" in
      file) [ "$new" = "$nw" ] && { printf '%s\n' "$lg"; return 0; } ;;
      glob) base="${new##*/}"; ldir="${lg%/*}"
            case "$new" in "$nw"/*)
              case "$base" in ${lg##*/}) printf '%s/%s\n' "$ldir" "$base"; return 0 ;; esac ;;
            esac ;;
      path) case "$new" in "$nw"/*)
              base="${new#"$nw"/}"
              case "$base" in $lg) printf '%s\n' "$base"; return 0 ;; esac ;;
            esac ;;
      dir)  case "$new" in "$nw"/*) printf '%s/%s\n' "$lg" "${new#"$nw"/}"; return 0 ;; esac ;;
      slug) case "$new" in "$nw"/*) printf '%s\n' "${new#"$nw"/}"; return 0 ;; esac ;;
    esac
  done <<EOF
$(rules_for "$kind")
EOF
  return 1
}

# --------------------------------------------------------------------------
# Anchor resolution and the refusals that precede any write.
# --------------------------------------------------------------------------

# legacy_stores_of ANCHOR -> prints every legacy store dir name present, one
# per line. One anchor routinely hosts several: store-spec §9.1 rows 1-3 are
# all `ksm_Obsidian` (`.omp` + `.oms` + `.omha`), and claudebase carries `.omp`
# beside `.orchestration`. The anchor is the `.hq/` root; the stores are the
# harnesses that feed it. `--store` narrows to one.
legacy_stores_of() {
  local a="$1" d n=0
  for d in $LEGACY_DIRS; do
    if [ -d "$a/$d" ]; then
      [ -n "${ONLY_STORE:-}" ] && [ "$ONLY_STORE" != "$d" ] && continue
      printf '%s\n' "$d"; n=$((n + 1))
    fi
  done
  [ "$n" -gt 0 ] && return 0
  if [ -n "${ONLY_STORE:-}" ]; then err "$a: no $ONLY_STORE/ here"
  else err "$a: no legacy store ($LEGACY_DIRS)"; fi
  return 1
}

# store-spec §9.1 rows 4-6 and HUB decision D2: the albc campaign held `.omx`
# and its `.orchestration`, and a `session-gate` hook blocked the path. Refuse
# by path so a gated anchor is *named* rather than looking absent.
#
# D2 was released 2026-08-28 (HUB decision D20, P7). The gate is **kept, not
# deleted**, and bound to that release instead: another machine syncing
# `claudebase` has not necessarily seen the release, and a gate that silently
# disappears is indistinguishable from one that never fired. Opening it takes
# one explicit acknowledgement, `HQ_D2_RELEASED=1`.
is_gated() {
  [ "${HQ_D2_RELEASED:-}" = "1" ] && return 1
  case "$1" in
    */albc|*/albc/*) return 0 ;;
  esac
  [ "${2:-}" = ".omx" ] && return 0
  return 1
}

# Dirty check, scoped to the **legacy store only**, not the whole tree and not
# `.hq/`. Two reasons for that scope:
#
#   * An unrelated untracked build artifact elsewhere in the repo is not a
#     reason to refuse a migration.
#   * `.hq/` is this tool's own output. Everything `apply` writes is untracked
#     until somebody commits it, so including `.hq/` would make the tool refuse
#     to run a second time on work it had just done — and would make `reverse`,
#     whose entire input is uncommitted new-store writes, permanently
#     impossible.
#
# What the check does protect is the same in both directions: an in-flight edit
# in the legacy store would be copied forward as if it were the migrated state,
# and would be silently overwritten by a merge going back.
assert_clean() {
  local anchor="$1" store="$2" out
  git -C "$anchor" rev-parse --git-dir >/dev/null 2>&1 || return 0
  out=$(git -C "$anchor" status --porcelain -- "$store" 2>/dev/null)
  [ -z "$out" ] && return 0
  err "$anchor: working tree dirty under $store/ — commit or stash first"
  printf '%s\n' "$out" | sed 's/^/    /' >&2
  return 3
}

# Where `reverse` keeps the legacy bytes it is about to overwrite. Outside the
# store on purpose: a sidecar left inside it would be an unmapped path forever
# after, which the FAIL contract would (correctly) refuse to migrate.
reverse_backup() {
  local anchor="$1" store="$2" rel="$3" dest
  dest="$HOME/.claude/hq-reverse-backups/$(printf '%s' "$anchor" | tr '/ ' '--')/$store/$rel"
  mkdir -p "$(dirname "$dest")" || return 1
  cp -p "$anchor/$store/$rel" "$dest" || return 1
  printf '%s\n' "$dest"
}

# No-git anchors have no `git checkout` to roll back to (§8), so the snapshot
# is the rollback. It lands outside the synced tree on purpose.
snapshot_if_no_git() {
  local anchor="$1" store="$2" dest ts
  git -C "$anchor" rev-parse --git-dir >/dev/null 2>&1 && return 0
  ts=$(date -u +%Y%m%dT%H%M%SZ)
  mkdir -p "$HOME/.claude/hq-snapshots" || return 1
  dest="$HOME/.claude/hq-snapshots/$(printf '%s' "$anchor" | tr '/ ' '--')-$store-$ts.tar"
  tar -cf "$dest" -C "$anchor" "$store" || { err "snapshot failed: $dest"; return 1; }
  note "  snapshot $dest"
  note "  sha256   $(sha "$dest")"
}

# --------------------------------------------------------------------------
# migrated.jsonl — the row store-spec §7 stage 1 says is appended when a store
# is migrated. Nothing appended one: the ledger was hand-written or empty, so
# `drift` on a store copied minutes earlier answered "this store was never cut
# over" (exit 6) on the very machine that had just migrated it. Written here,
# at the only point that knows the files actually landed and verified.
#
# Appended unconditionally, not deduped: `run_drift` takes `max(at)` over the
# rows for a kind, so a second `apply` must advance that reference rather than
# leave the first run's timestamp standing as the split-brain cut line.
#
# `machine` is a human-stable LABEL, not necessarily this host's name — the
# §10 roster says `ksm-mac` where `hostname -s` says `gwe52`. `HQ_MACHINE`
# sets it; the row is echoed so a wrong label is visible at write time.
# --------------------------------------------------------------------------
append_ledger() {
  local anchor="$1" kind="$2" ledger machine at row
  ledger="$anchor/$HQ/config/migrated.jsonl"
  machine="${HQ_MACHINE:-$(hostname -s 2>/dev/null || hostname)}"
  at=$(date +%Y-%m-%dT%H:%M:%S%z | sed 's/\(..\)$/:\1/')
  row=$(printf '{"harness":"%s","at":"%s","machine":"%s"}' "$kind" "$at" "$machine")
  mkdir -p "$(dirname "$ledger")" || return 1
  printf '%s\n' "$row" >> "$ledger" || return 1
  note "  -- migrated.jsonl += $row"
}

# --------------------------------------------------------------------------
# plan / apply
# --------------------------------------------------------------------------
run_move() {
  local verb="$1" anchor="$2" store="$3" kind rel new src dst rc
  local n_copy=0 n_same=0 n_skip=0 n_slug=0 n_fail=0 n_conflict=0
  local in_git=0 n_tracked=0 tracked_mark n_wiki=0

  anchor="${anchor%/}"
  [ -d "$anchor" ] || { err "$anchor: not a directory"; return 1; }
  if is_gated "$anchor" "$store"; then
    err "$anchor ($store): gated — albc campaign / omx is Phase 7 (HUB D2)"
    return 3
  fi
  kind=$(kind_of "$store") || { err "$store: unknown store kind"; return 1; }
  # Ignore policy can flip across the move: legacy store dirs are commonly
  # gitignored while `.hq/` defaults to tracked (store-spec §5). The flip is
  # intended, but it must be *visible* before anything is committed — an
  # operator keeping a subtree private needs to see it become tracked.
  git -C "$anchor" rev-parse --git-dir >/dev/null 2>&1 && in_git=1

  note "== $anchor  [$store -> $HQ, kind=$kind, verb=$verb]"
  if [ "$verb" = apply ]; then
    assert_clean "$anchor" "$store" || return 3
    snapshot_if_no_git "$anchor" "$store" || return 1
  fi

  while IFS= read -r src; do
    [ -n "$src" ] || continue
    rel="${src#"$anchor/$store/"}"
    new=$(map_forward "$kind" "$rel"); rc=$?
    case $rc in
      1) note "  FAIL   $store/$rel  (no mapping rule claims this path)"
         n_fail=$((n_fail + 1)); continue ;;
      2) note "  SKIP   $store/$rel"; n_skip=$((n_skip + 1)); continue ;;
      3) n_slug=$((n_slug + 1)) ;;
    esac
    dst="$anchor/$HQ/$new"
    if [ -e "$dst" ]; then
      if [ "$(sha "$src")" = "$(sha "$dst")" ]; then
        n_same=$((n_same + 1)); continue
      fi
      note "  CONFLICT $store/$rel -> $HQ/$new  (destination exists, differs)"
      n_conflict=$((n_conflict + 1)); continue
    fi
    tracked_mark=""
    if [ "$in_git" = 1 ] && git -C "$anchor" check-ignore -q "$src" \
       && ! git -C "$anchor" check-ignore -q "$dst"; then
      tracked_mark=" [becomes-tracked]"
      n_tracked=$((n_tracked + 1))
    fi
    case "$new" in community/wiki/*) n_wiki=$((n_wiki + 1)) ;; esac
    if [ $rc -eq 3 ]; then note "  SLUG   $store/$rel -> $HQ/$new$tracked_mark"
    else                   note "  COPY   $store/$rel -> $HQ/$new$tracked_mark"; fi
    n_copy=$((n_copy + 1))
    [ "$verb" = apply ] || continue
    mkdir -p "$(dirname "$dst")" || return 1
    cp -p "$src" "$dst" || { err "copy failed: $src"; return 1; }
    if [ "$(sha "$src")" != "$(sha "$dst")" ]; then
      err "sha256 mismatch after copy: $dst"; return 1
    fi
  done <<EOF
$(find "$anchor/$store" -type f 2>/dev/null | LC_ALL=C sort)
EOF

  note "  -- copy=$n_copy (slug $n_slug)  same=$n_same  skip=$n_skip  conflict=$n_conflict  fail=$n_fail"
  if [ "$n_tracked" -gt 0 ]; then
    note "  -- $n_tracked file(s) marked [becomes-tracked]: ignored at $store/, tracked at $HQ/ — extend .gitignore before committing if any must stay private"
  fi
  # `community/wiki/` is a staging state with a single exit, not a destination
  # (store-spec §9.3, r7 2026-08-30). A clean `conflict=0 fail=0` summary on a
  # run that filled it reads as finished, and the operator commits a store that
  # still holds the retired form. Said here because this is the only place that
  # knows a wiki page moved.
  if [ "$n_wiki" -gt 0 ]; then
    err "$anchor ($store): $n_wiki page(s) land in $HQ/community/wiki/ — a STAGING state (store-spec §9.3); this anchor is NOT finished migrating"
    err "  next: python3 <oh-my-orchestrator>/skills/harness/convert-wiki-form.py plan $anchor"
  fi
  if [ "$verb" = apply ] && [ "$n_fail" -eq 0 ] && [ "$n_conflict" -eq 0 ]; then
    append_ledger "$anchor" "$kind" || return 1
  fi
  [ "$n_fail" -gt 0 ] && return 2
  [ "$n_conflict" -gt 0 ] && return 4
  return 0
}

# --------------------------------------------------------------------------
# reverse — merge `.hq/` writes back into the legacy store.
#
# This is the half of the rollback procedure that cannot be done by deleting
# `.hq/`: once the cutover release ships, writes land in the new store, so a
# revert must carry them back. A legacy file that differs is *overwritten* —
# that is the point — but only after its current bytes are copied to
# ~/.claude/hq-reverse-backups/, so a reverse run is itself reversible.
#
# Set MIGRATE_REVERSE_DRYRUN=1 to see the plan without writing.
# --------------------------------------------------------------------------
run_reverse() {
  local anchor="$1" store="$2" kind new rel src dst rc other bak
  local n_back=0 n_same=0 n_new=0 n_skip=0 n_orphan=0

  anchor="${anchor%/}"
  [ -d "$anchor/$HQ" ] || { err "$anchor: no $HQ/ store to reverse"; return 1; }
  if is_gated "$anchor" "$store"; then
    err "$anchor ($store): gated — albc campaign / omx is Phase 7 (HUB D2)"; return 3
  fi
  kind=$(kind_of "$store") || return 1

  note "== $anchor  [$HQ -> $store, kind=$kind, write=${DO_WRITE:-0}]"
  [ "${DO_WRITE:-0}" = 1 ] && { assert_clean "$anchor" "$store" || return 3; }

  while IFS= read -r src; do
    [ -n "$src" ] || continue
    new="${src#"$anchor/$HQ/"}"
    rel=$(map_reverse "$kind" "$new"); rc=$?
    case $rc in
      1) # An anchor can hold several stores, so a path this kind cannot claim
         # may well belong to a sibling harness. Only a path *no* kind here
         # claims is a genuine orphan worth printing.
         for other in $ANCHOR_KINDS; do
           [ "$other" = "$kind" ] && continue
           if map_reverse "$other" "$new" >/dev/null 2>&1; then rc=9; break; fi
         done
         if [ $rc -eq 9 ]; then n_skip=$((n_skip + 1)); continue; fi
         note "  ORPHAN $HQ/$new  (no legacy origin — left in place)"
         n_orphan=$((n_orphan + 1)); continue ;;
      2) note "  SKIP   $HQ/$new"; n_skip=$((n_skip + 1)); continue ;;
    esac
    dst="$anchor/$store/$rel"
    if [ -e "$dst" ]; then
      if [ "$(sha "$src")" = "$(sha "$dst")" ]; then n_same=$((n_same + 1)); continue; fi
      note "  MERGE  $HQ/$new -> $store/$rel  (legacy differs; backed up)"
      n_back=$((n_back + 1))
      if [ "${DO_WRITE:-0}" = 1 ]; then
        bak=$(reverse_backup "$anchor" "$store" "$rel") || return 1
        note "         backup $bak"
        cp -p "$src" "$dst" || return 1
        [ "$(sha "$src")" = "$(sha "$dst")" ] || { err "sha mismatch: $dst"; return 1; }
      fi
    else
      note "  BACK   $HQ/$new -> $store/$rel  (new since cutover)"
      n_new=$((n_new + 1))
      if [ "${DO_WRITE:-0}" = 1 ]; then
        mkdir -p "$(dirname "$dst")" || return 1
        cp -p "$src" "$dst" || return 1
        [ "$(sha "$src")" = "$(sha "$dst")" ] || { err "sha mismatch: $dst"; return 1; }
      fi
    fi
  done <<EOF
$(find "$anchor/$HQ" -type f 2>/dev/null | LC_ALL=C sort)
EOF

  note "  -- merge=$n_back new=$n_new same=$n_same skip=$n_skip orphan=$n_orphan"
  return 0
}

# --------------------------------------------------------------------------
# purge — the only verb that removes anything, and it never runs unattended.
#
# store-spec §7: advancing an anchor past the fallback window is the *user's*
# judgment, not a quorum a script can compute, because `migrated.jsonl` is
# union-merged and a missing row is indistinguishable from an unpushed one.
# So there is no `--yes` here by design: the confirmation is read from the
# terminal and must be typed exactly. A piped or closed stdin refuses.
#
# "Remove" means `trash` (recoverable), never `rm -rf`. Where no trash command
# exists the store is moved aside under ~/.claude/hq-purged/.
# --------------------------------------------------------------------------
run_purge() {
  local anchor="$1" store="$2" want reply dest ts
  anchor="${anchor%/}"
  if is_gated "$anchor" "$store"; then
    err "$anchor ($store): gated — albc campaign / omx is Phase 7 (HUB D2)"; return 3
  fi
  [ -d "$anchor/$HQ" ] || { err "$anchor: no $HQ/ store — refusing to purge"; return 3; }

  note "== purge $anchor/$store"
  note "  $(find "$anchor/$store" -type f 2>/dev/null | wc -l | tr -d ' ') files"
  note ""
  note "  store-spec section 7: purge is stage 3. It is correct only after this"
  note "  anchor's harness has shipped fallback removal AND every machine that"
  note "  carries this anchor has been migrated. The ledger cannot prove that:"
  if [ -f "$anchor/$HQ/config/migrated.jsonl" ]; then
    sed 's/^/    /' "$anchor/$HQ/config/migrated.jsonl"
  else
    note "    (no migrated.jsonl — this anchor has no recorded migration at all)"
  fi
  note ""
  want="PURGE $(basename "$anchor")/$store"
  note "  Type exactly:  $want"
  if [ -r /dev/tty ]; then
    printf '  > ' >/dev/tty
    IFS= read -r reply </dev/tty || reply=""
  else
    err "no terminal to confirm on — refusing"; return 3
  fi
  if [ "$reply" != "$want" ]; then
    err "confirmation did not match — nothing was removed"; return 3
  fi

  if command -v trash >/dev/null 2>&1; then
    trash "$anchor/$store" || return 1
    note "  trashed $anchor/$store"
  elif command -v gio >/dev/null 2>&1; then
    gio trash "$anchor/$store" || return 1
    note "  trashed $anchor/$store"
  else
    ts=$(date -u +%Y%m%dT%H%M%SZ)
    dest="$HOME/.claude/hq-purged/$(printf '%s' "$anchor" | tr '/ ' '--')-$store-$ts"
    mkdir -p "$(dirname "$dest")" && mv "$anchor/$store" "$dest" || return 1
    note "  no trash command — moved aside to $dest"
  fi
}

# --------------------------------------------------------------------------
# census — the roster. Instrument: the fixed find (§9, unbounded depth) crossed
# with `git ls-files`. Exclusions are *patterns*, not a count: the plugin cache
# grows one `.omha` per deployed version (2 when §9.2 was written, 5 as of
# 2026-08-28), so a roster pinned to a number goes stale on every release.
# --------------------------------------------------------------------------
census_excluded() {
  case "$1" in
    */.claude/plugins/*)                    return 0 ;;
    */Library/Caches/com.apple.python/*)    return 0 ;;
    */.Trash/*|*/.Trash)                    return 0 ;;
    */.phase0-scratch/*)                    return 0 ;;
    */.hq/*)                                return 0 ;;
    # A store directory nested INSIDE another legacy store is a path within that
    # store, not an anchor of its own. albc's `.omx/.omx` (store-spec §9.1 row 5,
    # a wiki log left by a misrooted `--root .../.omx` call) is mapped as a row of
    # its parent's table, so census listing it separately would show a phantom
    # `legacy` store that no migration can ever clear — and the next round would
    # read that as an un-migrated anchor. Added P7.
    */.omp/*|*/.oms/*|*/.omd/*|*/.omx/*|*/.omha/*|*/.orchestration/*) return 0 ;;
  esac
  return 1
}

run_census() {
  local root="${1:-$HOME}" p store anchor kind files tracked git_ok gate
  local n_in=0 n_ex=0
  note "census root: $root"
  note ""
  printf '%-56s %-5s %6s %8s %-7s %s\n' ANCHOR KIND FILES TRACKED GIT GATE
  while IFS= read -r p; do
    [ -n "$p" ] || continue
    if census_excluded "$p"; then n_ex=$((n_ex + 1)); continue; fi
    store="${p##*/}"; anchor="${p%/*}"
    kind=$(kind_of "$store") || continue
    files=$(find "$p" -type f 2>/dev/null | wc -l | tr -d ' ')
    if git -C "$anchor" rev-parse --git-dir >/dev/null 2>&1; then
      git_ok=git
      tracked=$(git -C "$anchor" ls-files -z -- "$store" 2>/dev/null | tr -dc '\0' | wc -c | tr -d ' ')
    else
      git_ok=no-git; tracked=-
    fi
    if is_gated "$anchor" "$store"; then gate=GATED
    elif [ -f "$anchor/$HQ/.anchor" ]; then gate=anchored
    else gate=legacy; fi
    n_in=$((n_in + 1))
    printf '%-56s %-5s %6s %8s %-7s %s\n' \
      "$(printf '%s' "$anchor" | sed "s|^$HOME|~|")" "$kind" "$files" "$tracked" "$git_ok" "$gate"
  done <<EOF
$(find "$root" -type d \( -name '.omp' -o -name '.oms' -o -name '.omd' -o -name '.omx' \
   -o -name '.omha' -o -name '.orchestration' \) -not -path '*/.git/*' 2>/dev/null | LC_ALL=C sort)
EOF
  note ""
  note "in scope: $n_in   excluded by pattern: $n_ex"
  note "blind spot: this instrument sees directories, so it cannot tell a"
  note "migrated anchor from one whose legacy store is still being written to."
  note "That is what 'drift' is for, and drift reads the ledger, not this find."
}

# --------------------------------------------------------------------------
# drift — split-brain detection. Instrument: `.hq/config/migrated.jsonl` and
# per-file mtimes. It never runs the census find; the ledger is what tells it
# whether this store was cut over at all, so an anchor with no ledger row is
# invisible here and visible to census — the two cover each other rather than
# agreeing.
# --------------------------------------------------------------------------
run_drift() {
  local anchor="$1" store="$2"
  anchor="${anchor%/}"
  python3 - "$anchor" "$store" "$HQ" <<'PY'
import json, os, sys, datetime
anchor, store, hq = sys.argv[1:4]
ledger = os.path.join(anchor, hq, "config", "migrated.jsonl")
kinds = {".omp": "omp", ".oms": "oms", ".omd": "omd",
         ".omha": "omha", ".orchestration": "omo", ".omx": "omx"}
kind = kinds.get(store, store)
print(f"== {anchor}  [{store}, kind={kind}]")
if not os.path.exists(ledger):
    print("  no migrated.jsonl — nothing was migrated from here; drift is undefined")
    print("  (census is the instrument that sees this anchor)")
    raise SystemExit(6)
rows = []
for line in open(ledger, encoding="utf-8"):
    line = line.strip()
    if line:
        rows.append(json.loads(line))
mine = [r for r in rows if r.get("harness") == kind]
if not mine:
    print(f"  migrated.jsonl has no row for '{kind}' — this store was never cut over")
    print("  (rows present: " + ", ".join(sorted({r.get('harness', '?') for r in rows})) + ")")
    raise SystemExit(6)
at = max(datetime.datetime.fromisoformat(r["at"]) for r in mine)
cut = at.timestamp()
print(f"  ledger says {kind} migrated at {at.isoformat()}")
newer = []
root = os.path.join(anchor, store)
for dirpath, _dirs, files in os.walk(root):
    for f in files:
        p = os.path.join(dirpath, f)
        try:
            m = os.stat(p).st_mtime
        except OSError:
            continue
        if m > cut:
            newer.append((m, os.path.relpath(p, root)))
if not newer:
    print("  clean — no legacy file has been written since the migration")
    raise SystemExit(0)
print(f"  SPLIT-BRAIN: {len(newer)} legacy file(s) written after the migration")
for m, rel in sorted(newer, reverse=True)[:20]:
    print(f"    {datetime.datetime.fromtimestamp(m).isoformat(timespec='seconds')}  {store}/{rel}")
if len(newer) > 20:
    print(f"    ... and {len(newer) - 20} more")
print("  limits: an ignored layer or a no-git anchor can drift without changing")
print("  mtime ordering; only a tar hash covers those (store-spec section 8).")
raise SystemExit(5)
PY
}

# --------------------------------------------------------------------------
# audit — does this anchor's git config still satisfy the spec's blocks?
#
# store-spec §5 (the ignore lines) and §2 (the union-merge attributes) are the
# *seed* for a new anchor, and nothing re-applies them to an anchor that
# already exists. That is the whole 2026-08-31 round: `stonefish_ws` seeded
# from a two-line §5 and committed `hq`'s write lock, and this repo's vault
# kept a `merge=union` rule pointing at a legacy path three days after the
# purge deleted it. A spec block that changes and an anchor that never hears
# about it is the same silent-success shape as everything else here.
#
# Checked by BEHAVIOUR (`check-ignore` / `check-attr`), never by grepping for
# the line text: a rule inherited from a parent `.gitignore` is just as valid,
# and text matching would fail a correct anchor while passing a wrong one.
#
# The two NEGATIVE probes are load-bearing. A repo that ignores `.hq/`
# wholesale satisfies every positive probe while hiding the tracked layers, so
# `config/migrated.jsonl` and `community/INDEX.md` are asserted NOT ignored —
# without them this detector passes exactly the anchor it exists to catch.
# --------------------------------------------------------------------------
attr_of() { git -C "$1" check-attr merge -- "$2" 2>/dev/null | sed 's/.*: //'; }

run_audit() {
  local anchor="$1" bad=0 p a
  anchor="${anchor%/}"
  [ -d "$anchor" ] || { err "$anchor: not a directory"; return 1; }
  note "== $anchor  [audit: store-spec §5 ignore + §2 attributes]"
  # An anchor is `.hq/.anchor` (stage 2) or a `.hq/` that already holds files
  # (stage 1, copied but not cut over). An EMPTY `.hq/` is neither — measured
  # on the `oh-my-orchestrator` checkout, where a leftover empty directory made
  # this audit report two failures against a repo with nothing to protect. A
  # checker that fires on directories it has no business in gets ignored, which
  # costs more than the checks are worth.
  if [ ! -f "$anchor/$HQ/.anchor" ] &&
     [ -z "$(find "$anchor/$HQ" -type f 2>/dev/null | head -1)" ]; then
    note "  SKIP   no $HQ/ store here — not an anchor"
    return 0
  fi
  if ! git -C "$anchor" rev-parse --git-dir >/dev/null 2>&1; then
    note "  SKIP   not a git anchor — §8 covers these with tar snapshots instead"
    return 0
  fi

  for p in "$HQ/work/probe" "$HQ/runtime/probe" ".harness.lock/probe" \
           "$HQ/community/.hq-lock"; do
    if git -C "$anchor" check-ignore -q "$p"; then
      note "  ignored  $p"
    else
      err "$anchor: $p is NOT ignored — store-spec §5 asks for four lines"
      bad=$((bad + 1))
    fi
  done

  for p in "$HQ/config/migrated.jsonl" "$HQ/community/INDEX.md"; do
    if git -C "$anchor" check-ignore -q "$p"; then
      err "$anchor: $p IS ignored — config/ and community/ are tracked layers (§3, §5)"
      bad=$((bad + 1))
    else
      note "  tracked  $p"
    fi
  done

  # migrated.jsonl always; the secretary pair only where omp actually writes
  # one, so an anchor without a secretary is not nagged about a file it has no
  # reason to hold.
  set -- "$HQ/config/migrated.jsonl"
  if [ -d "$anchor/$HQ/config/project/secretary" ]; then
    set -- "$@" "$HQ/config/project/secretary/ledger.jsonl" \
                "$HQ/config/project/secretary/journal/2026-01-01.md"
  fi
  for p in "$@"; do
    a=$(attr_of "$anchor" "$p")
    if [ "$a" = union ]; then
      note "  union    $p"
    else
      err "$anchor: $p has merge=$a, not union — store-spec §2 (append-only log in a tracked layer)"
      bad=$((bad + 1))
    fi
  done

  [ "$bad" -eq 0 ] || { err "$anchor: $bad check(s) failed"; return 7; }
  note "  -- audit: all checks pass"
  return 0
}

# --------------------------------------------------------------------------
# selftest — the one runnable check. Two things can silently break the table:
# a `new` prefix reused within a kind (which makes `reverse` pick the wrong
# origin) and a rule whose inverse does not return the path it started from.
# The third check is the decoy P4 verified by hand — an unclaimed top-level
# file must FAIL, or the whole "unmapped is a failure" contract is inert.
# --------------------------------------------------------------------------
run_selftest() {
  local kind mode lg nw probe fwd back rc key fails=0 checked=0 seen
  for kind in omp oms omd omha omo omx; do
    seen=""
    while IFS='|' read -r mode lg nw; do
      [ -n "${mode:-}" ] || continue
      # `glob` rows may legitimately share a destination directory — their
      # inverse discriminates on the basename pattern, not the prefix — so the
      # uniqueness key carries that pattern. Every other mode is keyed on the
      # destination alone, where a reused prefix genuinely is ambiguous.
      case "$mode" in
        glob) key="$nw::${lg##*/}" ;;
        path) key="$nw::$lg" ;;
        *)    key="$nw" ;;
      esac
      case " $seen " in
        *" $key "*) err "selftest: $kind reuses destination '$key' — reverse is ambiguous"
                    fails=$((fails + 1)) ;;
      esac
      seen="$seen $key"
      case "$mode" in
        file) probe="$lg" ;;
        glob) probe="${lg%/*}/$(printf '%s' "${lg##*/}" | sed 's/\*/X/g')" ;;
        path) probe="$(printf '%s' "$lg" | sed 's/\*/X/g')" ;;
        dir)  probe="$lg/probe/leaf.md" ;;
        slug) probe="a-slug/probe/leaf.md" ;;
        *)    err "selftest: $kind has unknown mode '$mode'"; fails=$((fails + 1)); continue ;;
      esac
      fwd=$(map_forward "$kind" "$probe"); rc=$?
      if [ $rc -ne 0 ] && [ $rc -ne 3 ]; then
        err "selftest: $kind '$probe' did not map (rc=$rc)"; fails=$((fails + 1)); continue
      fi
      back=$(map_reverse "$kind" "$fwd") || {
        err "selftest: $kind '$fwd' has no inverse"; fails=$((fails + 1)); continue; }
      checked=$((checked + 1))
      if [ "$back" != "$probe" ]; then
        err "selftest: $kind round-trip broke: '$probe' -> '$fwd' -> '$back'"
        fails=$((fails + 1))
      fi
    done <<EOF
$(rules_for "$kind")
EOF
  done
  for kind in omp oms omd omha omo omx; do
    if map_forward "$kind" "an-unclaimed-file.md" >/dev/null 2>&1; then
      err "selftest: $kind mapped an unclaimed top-level file — the detector is inert"
      fails=$((fails + 1))
    fi
    checked=$((checked + 1))
  done
  if [ "$fails" -eq 0 ]; then note "selftest: $checked checks, all pass"; return 0; fi
  err "selftest: $fails failure(s) across $checked checks"
  return 1
}

# --------------------------------------------------------------------------
usage() { sed -n '/^# Usage:/,/^# Exit codes/p' "$0" | sed 's/^# \{0,1\}//'; }

DO_WRITE=0
ONLY_STORE=""
ANCHOR_KINDS=""
verb=""
root=""
args=""
while [ $# -gt 0 ]; do
  case "$1" in
    plan|apply|reverse|purge|census|drift|audit|selftest) verb="$1" ;;
    --root)  shift; root="${1:-}" ;;
    --store) shift; ONLY_STORE="${1:-}" ;;
    -h|--help) usage; exit 0 ;;
    -*) err "unknown option: $1"; usage >&2; exit 1 ;;
    *) args="$args $1" ;;
  esac
  shift
done
[ -n "$verb" ] || verb=plan
case "$verb" in apply|reverse) DO_WRITE=1 ;; esac
if [ "$verb" = reverse ] && [ "${MIGRATE_REVERSE_DRYRUN:-0}" = 1 ]; then DO_WRITE=0; fi

rc=0
case "$verb" in
  census)   run_census "${root:-$HOME}"; rc=$? ;;
  selftest) run_selftest; rc=$? ;;
  *)
    set -- $args
    [ $# -ge 1 ] || { err "$verb needs at least one anchor directory"; usage >&2; exit 1; }
    for a in "$@"; do
      a="${a%/}"
      # Per-anchor, not per-store, and it must run before the store lookup:
      # an anchor whose legacy stores are already purged has none to list, and
      # that is exactly an anchor whose git config still needs checking.
      if [ "$verb" = audit ]; then
        run_audit "$a"; r=$?
        [ $r -gt $rc ] && rc=$r
        continue
      fi
      stores=$(legacy_stores_of "$a") || { rc=1; continue; }
      # Kinds present at this anchor — `reverse` needs it to tell a sibling
      # harness's file apart from a genuine orphan.
      #
      # Built from the UNFILTERED store list, deliberately. `--store` narrows
      # what gets processed; it must not narrow what `reverse` knows is here.
      # It used to be derived from the filtered `$stores`, so
      # `reverse --store .omx` on an anchor also holding `.orchestration`
      # reported all 111 omo-owned files as ORPHAN — no data was lost ("left in
      # place"), but a detector with 111 false positives cannot surface the one
      # genuine orphan it exists to find. Measured on albc, P7.
      ANCHOR_KINDS=""
      for s in $(ONLY_STORE= legacy_stores_of "$a" 2>/dev/null); do
        ANCHOR_KINDS="$ANCHOR_KINDS $(kind_of "$s")"
      done
      if [ "$verb" = purge ]; then
        set -- $stores
        [ $# -eq 1 ] || {
          err "$a holds several stores ($stores) — purge one at a time with --store"
          rc=3; continue; }
        run_purge "$a" "$1"; r=$?
        [ $r -gt $rc ] && rc=$r
        continue
      fi
      unfinished=""
      for s in $stores; do
        case "$verb" in
          plan|apply) run_move "$verb" "$a" "$s" ;;
          reverse)    run_reverse "$a" "$s" ;;
          drift)      run_drift "$a" "$s" ;;
        esac
        r=$?
        [ $r -gt $rc ] && rc=$r
        [ $r -ne 0 ] && unfinished="$unfinished $s"
      done
      # The `.anchor` marker declares *every* store under this anchor migrated
      # (store-spec §7), but each run_move only summarizes its own store — on a
      # multi-store anchor a clean last summary reads as "done" while a gated
      # or failed sibling is not. Say so at the one point that sees them all.
      case "$verb" in plan|apply)
        if [ -n "$unfinished" ] && [ ! -f "$a/$HQ/.anchor" ]; then
          err "$a: do not create $HQ/.anchor yet — store(s) not fully migrated:$unfinished"
        fi ;;
      esac
      # The operator's next step after a clean `apply` is a commit, and that is
      # the moment the §5/§2 blocks decide what lands in git. Advisory: it does
      # not touch `rc`, because whether the copy succeeded and whether the repo
      # is configured are different questions and sharing an exit code is how
      # this tool got exit 6 in the first place. `audit` is the gate; this is
      # the reminder, in the same stderr channel as the two warnings above.
      if [ "$verb" = apply ] && [ -z "$unfinished" ]; then
        run_audit "$a" >/dev/null || \
          err "$a: apply is done, but the anchor's git config is not — run: migrate-om-store audit $a"
      fi
    done ;;
esac
exit $rc

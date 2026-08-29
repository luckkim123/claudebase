#!/usr/bin/env bash
# graph-init — give this project its code graphs in one command, and check them.
#
# The gap this fills. graph-offer.sh tells a session that a repository has no
# graph and the PreToolUse guards route every session through whatever exists,
# but until now nothing *made* one. The offer therefore had to carry the whole
# procedure as prose — copy the exclusion template, run two builds, inspect the
# node distribution, delete the result if it turned out to be somebody else's
# vendored JS — 1,152 characters that the model re-derived into four commands
# every time, and that a person meeting claudebase for the first time had to
# perform by hand. That is not an onboarding path. This script is the verb the
# offer should have pointed at from the start.
#
# Only the free half is built here. Both builds are tree-sitter: offline, no API
# key, seconds. graphify's semantic pass reads prose with an LLM at ~5 min per
# chunk serially (measured: 58 chunks, ~7 h on one vault), so it is never run
# from here — reach for /graphify deliberately when a prose corpus needs it.
#
# Exclusions are written BEFORE the builds, and the order is the whole point for
# graphify: a rule added afterwards does not refund extraction already paid for.
#
# Usage:
#   graph-init [DIR]        build + verify (DIR defaults to the current tree)
#   graph-init --purge      delete both graphs, keep the exclusion files
#   graph-init --help

set -u

SELF="graph-init"          # log prefix

# How to spell the command back at the reader. ~/.local/bin is not on every
# login PATH (measured: absent from this machine's zsh), so a bare
# "graph-init --purge" would be advice they cannot paste.
if command -v graph-init >/dev/null 2>&1; then
  VERB="graph-init"
else
  # shellcheck disable=SC2088  # display text for a human to paste, never a path
  # this script resolves — their shell expands the tilde, we must not.
  VERB="~/.local/bin/graph-init"
fi

# Resolve through the ~/.local/bin symlink to find this checkout's templates/.
_src="${BASH_SOURCE[0]}"
while [ -L "$_src" ]; do
  _dir="$(cd -P "$(dirname "$_src")" && pwd)"
  _src="$(readlink "$_src")"
  case "$_src" in /*) ;; *) _src="$_dir/$_src" ;; esac
done
REPO_DIR="$(cd -P "$(dirname "$_src")/../.." && pwd)"
TEMPLATES="$REPO_DIR/templates"

say() { printf '[%s] %s\n' "$SELF" "$*"; }
die() { printf '[%s] %s\n' "$SELF" "$*" >&2; exit 1; }

usage() {
  cat <<'EOF'
graph-init — build this project's code graphs (tree-sitter, offline, free).

  graph-init [DIR]     write exclusions, build both graphs, verify the result
  graph-init --purge   delete both graphs, keep the exclusion files
  graph-init --help

DIR defaults to the git toplevel, or the current directory outside a repo.
The paid semantic pass over prose is never run here — use /graphify for that.
EOF
  exit 0
}

PURGE=0
TARGET=""
for arg in "$@"; do
  case "$arg" in
    --purge) PURGE=1 ;;
    -h|--help) usage ;;
    -*) die "unknown option: $arg" ;;
    *) TARGET="$arg" ;;
  esac
done

# Root: the git toplevel when there is one, else the directory itself. graphify
# handles a non-git tree — it never needed git at all (measured: 12 .py files in
# a plain directory produced 24 nodes) — which is why a container mount like
# /workspace is a legitimate target and not an error.
if [ -n "$TARGET" ]; then
  [ -d "$TARGET" ] || die "not a directory: $TARGET"
  ROOT="$(cd "$TARGET" && pwd)"
else
  ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || ROOT=""
  # Linked-worktree correction — see runtime/hooks/graph-refresh.sh for why both
  # git dirs are absolutised before the compare. Building inside a worktree
  # would mint a second graph that dies with the worktree while the main
  # checkout's stays stale, and would drop the two exclusion files somewhere
  # they vanish from. Pass a directory argument to override: that path is taken
  # above and never reaches this branch.
  _gd="$(git rev-parse --git-dir 2>/dev/null)" || _gd=""
  _gc="$(git rev-parse --git-common-dir 2>/dev/null)" || _gc=""
  [ -n "$_gd" ] && _gd="$(cd "$_gd" 2>/dev/null && pwd)"
  [ -n "$_gc" ] && _gc="$(cd "$_gc" 2>/dev/null && pwd)"
  if [ -n "$_gc" ] && [ "$_gd" != "$_gc" ]; then
    ROOT="$(cd "$_gc/.." 2>/dev/null && pwd)" || ROOT=""
  fi
  [ -n "$ROOT" ] || ROOT="$PWD"
fi

# The one refusal. Without git's toplevel to bound it, "the current directory"
# can be $HOME or /, where the rglob fallback would walk an entire machine and
# the resulting graph would describe nothing. A git repo rooted at $HOME is a
# dotfiles repo and a deliberate choice, so only the non-git case is refused.
if [ "$ROOT" = "$HOME" ] || [ "$ROOT" = "/" ]; then
  if ! git -C "$ROOT" rev-parse --show-toplevel >/dev/null 2>&1; then
    die "refusing to graph $ROOT — pass a project directory instead"
  fi
fi

GOUT="${GRAPHIFY_OUT:-graphify-out}"

# Every output directory graphify might have used here, not just the one this
# process would pick. `GRAPHIFY_OUT=.graphify` lives in claudebase's rendered
# settings.json, so a Claude Code session builds into `.graphify` while a plain
# shell — which inherits no such env — defaults to `graphify-out`. Measured in a
# container 2026-08-10: a purge run from bash deleted `graphify-out/` and left
# `.graphify/graph.json` behind, which is precisely the empty-shell graph the
# PreToolUse guards go on consulting. A purge that leaves a graph is not a purge.
OUT_DIRS=()
for _d in "$GOUT" .graphify graphify-out; do
  case " ${OUT_DIRS[*]-} " in *" $_d "*) continue ;; esac
  OUT_DIRS+=("$_d")
done

# ~/.local/bin is where uv puts the shims and this user's shells do not always
# export it (same reason as graph-refresh.sh:42).
resolve() {
  local found
  found="$(command -v "$1" 2>/dev/null || true)"
  [ -n "$found" ] || found="$HOME/.local/bin/$1"
  [ -x "$found" ] && printf '%s' "$found"
}

GFY="$(resolve graphify)"

if [ "$PURGE" -eq 1 ]; then
  removed=0
  for d in "${OUT_DIRS[@]/#/$ROOT/}"; do
    [ -e "$d" ] || continue
    rm -rf "$d" && say "삭제: ${d#"$ROOT"/}" && removed=1
  done
  [ "$removed" -eq 1 ] || say "지울 그래프가 없습니다 ($ROOT)"
  say "제외 파일(.graphifyignore)은 남겨둡니다 — 손으로 고쳤을 수 있습니다."
  exit 0
fi

[ -n "$GFY" ] || die "graphify가 없습니다 — installer/install.sh를 먼저 실행하세요"

say "대상: $ROOT"

# --- 1. exclusions, before anything is extracted ----------------------------
seed() {
  local dest="$ROOT/$1" template="$TEMPLATES/$2"
  if [ -e "$dest" ]; then
    say "$1 있음 → 그대로 사용"
  elif [ -f "$template" ]; then
    cp "$template" "$dest" && say "$1 없음 → 템플릿 복사"
  else
    say "경고: 템플릿 없음 ($template) — $1 없이 진행"
  fi
}
[ -n "$GFY" ] && seed .graphifyignore project-graphifyignore

# --- 2. build ---------------------------------------------------------------
# A failure is reported and does not abort: the verification below judges what
# exists rather than trusting the builder's exit code.
if [ -n "$GFY" ]; then
  if ( cd "$ROOT" && "$GFY" . --code-only >/dev/null 2>&1 ); then
    say "graphify . --code-only 완료"
  else
    say "경고: graphify 빌드 실패"
  fi
fi

# --- 3. verify --------------------------------------------------------------
# The check that matters is WHERE the nodes came from, not how many there are.
# A big node count in a repo of prose usually means the extractor found somebody
# else's node_modules, and the guards then force every session to consult it.
python3 - "$ROOT" "${OUT_DIRS[@]}" <<'PY'
import collections
import json
import os
import sys

root, out_dirs = sys.argv[1], sys.argv[2:]

# ponytail: a fixed name list plus a 30% share is the whole heuristic. It
# catches the measured failures (.obsidian, node_modules) and nothing subtler;
# widen the list or read the ignore files if a project needs more.
VENDORED = {
    "node_modules", "vendor", "third_party", "thirdparty", "bower_components",
    "venv", ".venv", "site-packages", "dist", "build", "target", "Pods",
    ".obsidian", ".git",
}
WARN_SHARE = 0.30


def report(label, counter):
    total = sum(counter.values())
    if not total:
        print(f"[graph-init] {label}: 노드 0개 — 색인할 코드를 못 찾았습니다")
        return False
    top = ", ".join(
        f"{name} {count * 100 // total}%" for name, count in counter.most_common(4)
    )
    print(f"[graph-init] {label}: {total}개 노드 — {top}")
    bad = sum(c for n, c in counter.items() if n in VENDORED)
    if bad / total >= WARN_SHARE:
        names = ", ".join(sorted(n for n in counter if n in VENDORED))
        print(
            f"[graph-init]   경고: {bad * 100 // total}%가 vendored 트리에서 왔습니다 "
            f"({names}). 제외 규칙을 고치고 다시 만드세요."
        )
        return False
    return True


def top_dir(path):
    rel = os.path.relpath(path, root) if os.path.isabs(path) else path
    head = rel.split(os.sep)[0]
    return head if head not in ("", ".") else "."


ok = True
seen = False

# The first candidate that exists wins; the list is ordered so this process's
# own GRAPHIFY_OUT is checked before the two defaults.
gj = next(
    (p for p in (os.path.join(root, d, "graph.json") for d in out_dirs) if os.path.exists(p)),
    None,
)
if gj:
    seen = True
    counter = collections.Counter()
    try:
        with open(gj, encoding="utf-8") as fh:
            graph = json.load(fh)
    except (OSError, ValueError) as exc:
        print(f"[graph-init] graphify: 그래프를 읽을 수 없습니다 ({exc})")
        ok = False
    else:
        for node in graph.get("nodes", []):
            src = node.get("source_file") or node.get("file") or ""
            if src:
                counter[top_dir(src)] += 1
        ok = report("graphify", counter) and ok

if not seen:
    print("[graph-init] 만들어진 그래프가 없습니다 — 위 경고를 확인하세요")
    sys.exit(1)
sys.exit(0 if ok else 2)
PY
verdict=$?

case "$verdict" in
  0) say "OK. 되돌리려면: $VERB --purge" ;;
  2) say "검증 실패 — 이대로 두면 가드가 매 턴 이 그래프를 조회합니다. 되돌리려면: $VERB --purge" ;;
  *) say "그래프 없음. 되돌릴 것도 없습니다." ;;
esac
exit "$verdict"

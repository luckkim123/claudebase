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

# Root: the git toplevel when there is one, else the directory itself. Both
# builders handle a non-git tree — CRG falls back from `git ls-files` to an
# rglob walk (incremental.py:761-767) and graphify never needed git at all
# (measured: 12 .py files in a plain directory produced 24 nodes) — which is why
# a container mount like /workspace is a legitimate target and not an error.
if [ -n "$TARGET" ]; then
  [ -d "$TARGET" ] || die "not a directory: $TARGET"
  ROOT="$(cd "$TARGET" && pwd)"
else
  ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || ROOT=""
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

# ~/.local/bin is where uv puts the shims and this user's shells do not always
# export it (same reason as graph-refresh.sh:42).
resolve() {
  local found
  found="$(command -v "$1" 2>/dev/null || true)"
  [ -n "$found" ] || found="$HOME/.local/bin/$1"
  [ -x "$found" ] && printf '%s' "$found"
}

CRG="$(resolve code-review-graph)"
GFY="$(resolve graphify)"

if [ "$PURGE" -eq 1 ]; then
  removed=0
  for d in "$ROOT/.code-review-graph" "$ROOT/$GOUT"; do
    [ -e "$d" ] || continue
    rm -rf "$d" && say "삭제: ${d#"$ROOT"/}" && removed=1
  done
  [ "$removed" -eq 1 ] || say "지울 그래프가 없습니다 ($ROOT)"
  say "제외 파일(.graphifyignore, .code-review-graphignore)은 남겨둡니다 — 손으로 고쳤을 수 있습니다."
  exit 0
fi

[ -n "$CRG" ] || [ -n "$GFY" ] || die "code-review-graph도 graphify도 없습니다 — installer/install.sh를 먼저 실행하세요"

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
[ -n "$CRG" ] && seed .code-review-graphignore project-code-review-graphignore

# --- 2. build ---------------------------------------------------------------
# Failures are reported and do not abort: one graph is worth having even when
# the other tool is broken, and the verification below judges what exists.
if [ -n "$CRG" ]; then
  if ( cd "$ROOT" && "$CRG" build >/dev/null 2>&1 ); then
    say "code-review-graph build 완료"
  else
    say "경고: code-review-graph build 실패"
  fi
fi
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
python3 - "$ROOT" "$GOUT" <<'PY'
import collections
import json
import os
import sqlite3
import sys

root, gout = sys.argv[1], sys.argv[2]

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

db = os.path.join(root, ".code-review-graph", "graph.db")
if os.path.exists(db):
    seen = True
    counter = collections.Counter()
    try:
        with sqlite3.connect(db) as conn:
            for path, n in conn.execute(
                "select file_path, count(*) from nodes group by 1"
            ):
                counter[top_dir(path)] += n
    except sqlite3.Error as exc:
        print(f"[graph-init] code-review-graph: 그래프를 읽을 수 없습니다 ({exc})")
        ok = False
    else:
        ok = report("code-review-graph", counter) and ok

gj = os.path.join(root, gout, "graph.json")
if os.path.exists(gj):
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

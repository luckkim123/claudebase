#!/usr/bin/env python3
"""Close OMC's half-built auto-compact wiring, and make a coordinator survive compaction.

OMC's HUD already WRITES `<omc-state>/compact-requested.json` when context crosses
`omcHud.contextLimitWarning.threshold` and `autoCompact` is true (bridge/cli.cjs:60979).
Nothing anywhere READS it -- measured 2026-08-24, grep over the plugin cache and this
repo returned 0 consumers. So the switch was inert: turning it on only littered a file.

Two modes:

  prompt-submit  consume that trigger file -> inject a /compact nudge -> delete it.
                 The HUD rewrites it on the next render if context is still over the
                 line, so deleting is safe: a declined nudge simply comes back.

  pre-compact    when this project runs a multi-agent hub (`.omc/<hub>/HUB.md`), inject
                 where the coordinator must re-read from. Compaction drops the
                 conversation, not the hub file -- measured on the paper-hub campaign,
                 where a coordinator took 2 compactions with 0 lost work precisely
                 because HUB.md held the state.

Injection is user-facing Korean; comments stay English (repo convention).
"""

import glob
import json
import os
import sys

MAX_CHARS = 1200  # hook injection is capped in CHARACTERS, not bytes


def state_dir(cwd):
    """Resolve OMC's state root the way OMC itself does.

    With OMC_STATE_DIR set the layout is `$OMC_STATE_DIR/<basename>-<hash>/state`;
    the hash is OMC's, so match on the basename prefix rather than recomputing it.
    """
    base = os.environ.get("OMC_STATE_DIR")
    if not base:
        return os.path.join(cwd, ".omc", "state")
    for d in sorted(glob.glob(os.path.join(base, os.path.basename(cwd) + "-*"))):
        return os.path.join(d, "state")
    return None


def find_hubs(cwd):
    """Multi-agent hubs live at `.omc/<name>/HUB.md` -- local, not in OMC_STATE_DIR."""
    return sorted(glob.glob(os.path.join(cwd, ".omc", "*", "HUB.md")))


def prompt_submit(cwd):
    sd = state_dir(cwd)
    if not sd:
        return
    trigger = os.path.join(sd, "compact-requested.json")
    try:
        with open(trigger) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return

    try:
        os.remove(trigger)
    except OSError:
        pass  # a parallel session got there first; the nudge below still stands

    pct = data.get("contextPercent", "?")
    hubs = find_hubs(cwd)
    lines = [
        "<compact-guard>",
        f"컨텍스트 {pct}% — 설정된 임계를 넘었다. 지금이 compact 지점이다.",
        "",
        "지금 턴의 작업을 끝내고 나서(작업 도중이면 끝낸 뒤에) `/compact` 를 실행하라.",
        "compact 전에 세션에만 있는 사실을 먼저 파일로 내보내라 — 그러지 않으면 사라진다.",
    ]
    if hubs:
        rel = os.path.relpath(hubs[0], cwd)
        lines += [
            "",
            f"이 세션은 협업 허브를 돌리고 있다: `{rel}`",
            "조정자라면 compact 전에 다음을 허브에 반영하라: 작업 보드 Status, 새 사용자 결정,",
            "발사한 것/회수한 것. 세션 컨텍스트에만 있는 답은 다른 세션에게 존재하지 않는다.",
        ]
    lines.append("</compact-guard>")
    sys.stdout.write("\n".join(lines)[:MAX_CHARS])


def pre_compact(cwd):
    hubs = find_hubs(cwd)
    if not hubs:
        return  # not a hub session; OMC's own wiki-pre-compact still runs
    rel = [os.path.relpath(h, cwd) for h in hubs]
    lines = [
        "<compact-guard: 협업 허브 복구 지점>",
        "compact 후 조정자로 계속한다면, 대화 기억 대신 아래 파일을 먼저 다시 읽어라 —",
        "허브가 정본이고 대화는 사본이다.",
    ]
    lines += [f"  · {r} — 작업 보드 Status 와 사용자 결정 표" for r in rel]
    lines += [
        "재독 없이 이어가면 이미 닫힌 결정을 다시 묻거나 끝난 작업을 재발주하게 된다.",
        "</compact-guard>",
    ]
    sys.stdout.write("\n".join(lines)[:MAX_CHARS])


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    cwd = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    if mode == "prompt-submit":
        prompt_submit(cwd)
    elif mode == "pre-compact":
        pre_compact(cwd)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # advisory only -- never break a turn

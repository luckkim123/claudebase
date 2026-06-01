# Output-Style Enforcement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** claudebase 에 출력-스타일을 코드로 강제하는 hook 2개(UserPromptSubmit 주입 + Stop 검출)를 opt-in 으로 추가한다.

**Architecture:** 기존 hook DNA(detect_malformed_toolcall.py)를 상속 — fail-open(예외 시 exit 0), `stop_hook_active` 3-state 루프 가드, `.omc/logs/*.jsonl` 텔레메트리, idempotent 마커 주석. env `CLAUDEBASE_OUTPUT_STYLE`(off|nudge|enforce, 기본 off)로 활성 제어. 검출은 오프너 필러/아첨만(보수적).

**Tech Stack:** Python 3 stdlib only (json/re/os/sys), pytest, subprocess end-to-end 테스트.

**참고 파일 (컨벤션 SSOT):**
- hook 패턴: `runtime/hooks/detect_malformed_toolcall.py`
- 테스트 패턴: `tests/hooks/test_detect_malformed_toolcall.py` (`_load_module`/`_run_hook`/fail-open/loop-guard/log 검증)
- settings 등록: `config/settings.json` (Stop·UserPromptSubmit 블록, 마커 주석)

**설계 근거:** `docs/specs/2026-06-01-output-style-enforcement/design.md` · `research.md`

---

## Task 0: box CLI 도구 (CJK 폭 계산, 시작화면처럼 안 깨지는 박스)

**Files:**
- Create: `runtime/bin/box.py`
- Test: `tests/bin/test_box.py` (+ `tests/bin/__init__.py`)

모델이 호출하면 파이썬이 East Asian Width 로 폭을 계산해 우변까지 맞춘 유니코드 박스를 출력. stdlib only.

**Step 1: 실패 테스트 작성** — `tests/bin/test_box.py`

```python
"""Tests for runtime/bin/box.py — CJK-aware unicode box renderer."""
from __future__ import annotations
import importlib.util, subprocess, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BOX_PATH = REPO_ROOT / "runtime" / "bin" / "box.py"

def _load():
    spec = importlib.util.spec_from_file_location("box", BOX_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def test_visual_width_cjk_is_2():
    m = _load()
    assert m.visual_width("ab") == 2
    assert m.visual_width("결론") == 4      # 한글 2글자 = 4칸
    assert m.visual_width("a결") == 3        # 혼합

def test_render_box_right_edge_aligned():
    m = _load()
    out = m.render_box("결론", ["캐시 무효화가 원인입니다.", "ASCII mixed 한글 line"])
    lines = out.splitlines()
    # 모든 줄의 시각적 폭이 동일해야(우변 정렬). 첫 줄(top border) 폭 기준.
    widths = {m.visual_width(l) for l in lines}
    assert len(widths) == 1, f"all rows must share one visual width, got {widths}"

def test_render_box_has_borders():
    m = _load()
    out = m.render_box("T", ["x"])
    assert out.startswith("╭") and "╮" in out.splitlines()[0]
    assert out.splitlines()[-1].startswith("╰") and out.splitlines()[-1].endswith("╯")

def test_ascii_fallback():
    m = _load()
    out = m.render_box("T", ["x"], ascii_only=True)
    assert "╭" not in out and "+" in out.splitlines()[0]

def test_cli_invocation():
    proc = subprocess.run([sys.executable, str(BOX_PATH), "결론", "캐시가 원인입니다."],
                          capture_output=True, text=True, timeout=15)
    assert proc.returncode == 0
    assert "결론" in proc.stdout and "╭" in proc.stdout

def test_cli_no_args_exits_clean():
    proc = subprocess.run([sys.executable, str(BOX_PATH)],
                          capture_output=True, text=True, timeout=15)
    assert proc.returncode == 0  # no crash on empty
```

**Step 2: 실패 확인** — `cd ~/claudebase && python3 -m pytest tests/bin/test_box.py -v` → FAIL

**Step 3: 최소 구현** — `runtime/bin/box.py`

```python
#!/usr/bin/env python3
"""CJK-aware unicode box renderer — like Claude Code's welcome box, the WIDTH
is computed in code so the right edge never drifts even with Korean text.

Usage: python3 box.py "Title" "line 1" "line 2" ...
       python3 box.py --ascii "Title" "line"   # ASCII fallback

Why a tool and not inline drawing: a model counts characters, but the terminal
renders CJK glyphs at width 2 (East Asian Width W/F). Inline boxes drift on the
right edge. This tool measures width with unicodedata and pads correctly.
stdlib only — no wcwidth dependency.
"""
from __future__ import annotations
import sys
import unicodedata

def visual_width(s: str) -> int:
    """Terminal column width: East Asian Wide/Fullwidth = 2, else 1."""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)

def render_box(title: str, lines: list[str], ascii_only: bool = False) -> str:
    if ascii_only:
        tl, tr, bl, br, h, v = "+", "+", "+", "+", "-", "|"
    else:
        tl, tr, bl, br, h, v = "╭", "╮", "╰", "╯", "─", "│"
    title = title or ""
    lines = lines or [""]
    inner = max([visual_width(title) + 4] + [visual_width(l) + 2 for l in lines])
    top = tl + h + " " + title + " " + h * (inner - visual_width(title) - 3) + tr
    out = [top]
    for l in lines:
        out.append(v + " " + l + " " * (inner - visual_width(l) - 2) + " " + v)
    out.append(bl + h * inner + br)
    return "\n".join(out)

def main(argv: list[str]) -> int:
    ascii_only = False
    args = list(argv)
    if args and args[0] == "--ascii":
        ascii_only = True
        args = args[1:]
    if not args:
        return 0  # no crash on empty
    title, lines = args[0], args[1:]
    sys.stdout.write(render_box(title, lines, ascii_only=ascii_only) + "\n")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

**Step 4: 통과 확인** — 같은 pytest → PASS. 수동: `python3 runtime/bin/box.py "결론" "캐시가 원인입니다." "ASCII mixed 한글"` → 우변 정렬 육안 확인.

**Step 5: 커밋**
```bash
git add runtime/bin/box.py tests/bin/__init__.py tests/bin/test_box.py
git commit -m "feat(bin): add CJK-aware unicode box renderer (welcome-box style)"
```

---

## Task 1: 공유 env-gate 헬퍼

**Files:**
- Create: `runtime/hooks/output_style_common.py`
- Test: `tests/hooks/test_output_style_common.py`

env 읽기와 kill-switch 로직을 한 곳에. 두 hook 이 동일 게이트를 써야 drift 가 없다.

**Step 1: 실패 테스트 작성** — `tests/hooks/test_output_style_common.py`

```python
"""Tests for runtime/hooks/output_style_common.py — the shared opt-in gate."""
from __future__ import annotations
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / "runtime" / "hooks" / "output_style_common.py"

def _load():
    spec = importlib.util.spec_from_file_location("output_style_common", HOOK_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def test_default_off_when_env_absent():
    m = _load()
    assert m.style_mode({}) == "off"

def test_explicit_modes():
    m = _load()
    assert m.style_mode({"CLAUDEBASE_OUTPUT_STYLE": "nudge"}) == "nudge"
    assert m.style_mode({"CLAUDEBASE_OUTPUT_STYLE": "enforce"}) == "enforce"

def test_unknown_value_is_off():
    m = _load()
    assert m.style_mode({"CLAUDEBASE_OUTPUT_STYLE": "garbage"}) == "off"

def test_kill_switch_forces_off():
    m = _load()
    assert m.style_mode({"CLAUDEBASE_OUTPUT_STYLE": "enforce", "DISABLE_OMC": "1"}) == "off"
    assert m.style_mode({"CLAUDEBASE_OUTPUT_STYLE": "enforce", "OMC_SKIP_HOOKS": "output_style"}) == "off"

def test_case_insensitive():
    m = _load()
    assert m.style_mode({"CLAUDEBASE_OUTPUT_STYLE": "ENFORCE"}) == "enforce"
```

**Step 2: 실패 확인** — `cd ~/claudebase && python3 -m pytest tests/hooks/test_output_style_common.py -v` → FAIL (module not found)

**Step 3: 최소 구현** — `runtime/hooks/output_style_common.py`

```python
#!/usr/bin/env python3
"""Shared opt-in gate for output-style hooks.

CLAUDEBASE_OUTPUT_STYLE: off (default/unset) | nudge | enforce.
Kill switches DISABLE_OMC / OMC_SKIP_HOOKS (mirrors config/CLAUDE.md) force off.
"""
from __future__ import annotations

_VALID = {"off", "nudge", "enforce"}

def style_mode(env: dict) -> str:
    if env.get("DISABLE_OMC"):
        return "off"
    skip = env.get("OMC_SKIP_HOOKS", "")
    if "output_style" in skip.split(","):
        return "off"
    raw = (env.get("CLAUDEBASE_OUTPUT_STYLE") or "off").strip().lower()
    return raw if raw in _VALID else "off"
```

**Step 4: 통과 확인** — 같은 pytest → PASS

**Step 5: 커밋**
```bash
git add runtime/hooks/output_style_common.py tests/hooks/test_output_style_common.py
git commit -m "feat(hooks): add shared opt-in gate for output-style enforcement"
```

---

## Task 2: 주입 hook (UserPromptSubmit, nudge)

**Files:**
- Create: `runtime/hooks/output_style_inject.py`
- Test: `tests/hooks/test_output_style_inject.py`

mode 가 `nudge`/`enforce` 일 때만 5줄 baseline 을 `additionalContext` 로 주입. `off` 면 빈 출력.

**Step 1: 실패 테스트 작성** — `tests/hooks/test_output_style_inject.py`

```python
"""Tests for runtime/hooks/output_style_inject.py (UserPromptSubmit nudge)."""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / "runtime" / "hooks" / "output_style_inject.py"

def _run(stdin_obj: dict, env_extra: dict) -> dict:
    import os
    env = dict(os.environ); env.update(env_extra)
    proc = subprocess.run([sys.executable, str(HOOK_PATH)],
        input=json.dumps(stdin_obj), capture_output=True, text=True, timeout=15, env=env)
    assert proc.returncode == 0, f"must exit 0: {proc.stderr}"
    out = proc.stdout.strip()
    return json.loads(out) if out else {}

def test_off_injects_nothing():
    out = _run({"hook_event_name": "UserPromptSubmit", "prompt": "hi"},
               {"CLAUDEBASE_OUTPUT_STYLE": "off"})
    assert out == {}

def test_nudge_injects_baseline():
    out = _run({"hook_event_name": "UserPromptSubmit", "prompt": "hi"},
               {"CLAUDEBASE_OUTPUT_STYLE": "nudge"})
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "BLUF" in ctx or "결론" in ctx          # answer-first present
    assert "표" in ctx or "table" in ctx.lower()    # comparison->table present

def test_enforce_also_injects():
    out = _run({"hook_event_name": "UserPromptSubmit", "prompt": "hi"},
               {"CLAUDEBASE_OUTPUT_STYLE": "enforce"})
    assert out.get("hookSpecificOutput", {}).get("additionalContext")

def test_injection_is_short():
    out = _run({"hook_event_name": "UserPromptSubmit", "prompt": "hi"},
               {"CLAUDEBASE_OUTPUT_STYLE": "nudge"})
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert ctx.count("\n") <= 14, "injection must stay short to avoid context bloat"

def test_malformed_stdin_exits_clean():
    proc = subprocess.run([sys.executable, str(HOOK_PATH)],
        input="not json {{{", capture_output=True, text=True, timeout=15)
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""
```

**Step 2: 실패 확인** — `python3 -m pytest tests/hooks/test_output_style_inject.py -v` → FAIL

**Step 3: 최소 구현** — `runtime/hooks/output_style_inject.py`

```python
#!/usr/bin/env python3
"""UserPromptSubmit hook: inject output-style baseline as additionalContext.

Active only when CLAUDEBASE_OUTPUT_STYLE in {nudge, enforce}. Never raises;
any error -> exit 0 with no output. Idempotent marker: OUTPUT_STYLE_INJECT.

Baseline = the 5 research-backed defaults (see design.md §2):
  BLUF + meaningful headings / prose over bullets / table for comparisons /
  concise declarative tone (no chatty filler) / explicit knowledge-boundary
  over vague hedging. Plus: callout boxes 1-2 max.
"""
from __future__ import annotations
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from output_style_common import style_mode  # noqa: E402

BASELINE = (
    "[output-style] 답변 형식 기본값:\n"
    "1. 결론 먼저(BLUF) + 의미 있는 헤딩.\n"
    "2. 설명은 산문으로. 불릿은 진짜 병렬 항목일 때만, 중첩 금지.\n"
    "3. 항목 비교는 표로.\n"
    "4. 간결한 단정형. 구어체 필러('좋은 질문', 'Certainly!')·아첨 금지.\n"
    "5. 불확실하면 모호한 헤지 대신 지식 경계를 명시('X에 대한 출처 없음').\n"
    "6. 강조 블록은 `python3 ~/claudebase/runtime/bin/box.py \"제목\" \"줄\"` 로 그려라"
    "(인라인 ╭─╮ 직접 그리기 금지 — 한글 폭 때문에 우변 어긋남). 1-2개 한도, 연속 금지."
)

def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return 0
    if payload.get("hook_event_name") != "UserPromptSubmit":
        return 0
    if style_mode(os.environ) == "off":
        return 0
    body = {"hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": BASELINE,
    }}
    sys.stdout.write(json.dumps(body, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

**Step 4: 통과 확인** — 같은 pytest → PASS

**Step 5: 커밋**
```bash
git add runtime/hooks/output_style_inject.py tests/hooks/test_output_style_inject.py
git commit -m "feat(hooks): add UserPromptSubmit output-style baseline injection"
```

---

## Task 3: 검출 hook (Stop, enforce) — 오프너 필러/아첨만

**Files:**
- Create: `runtime/hooks/output_style_guard.py`
- Test: `tests/hooks/test_output_style_guard.py`

`enforce` 일 때만, 응답 *오프너*가 필러/아첨이면 1회 block + 교정 주입. detect_malformed_toolcall.py 의 3-state 루프 가드·fail-open·로그를 그대로 상속.

> 검출은 **오프너만**(첫 비공백 줄). 본문 중간의 "great" 등은 절대 안 잡음 — false positive 차단의 핵심.

**Step 1: 실패 테스트 작성** — `tests/hooks/test_output_style_guard.py`

```python
"""Tests for runtime/hooks/output_style_guard.py (Stop filler/sycophancy guard)."""
from __future__ import annotations
import importlib.util, json, subprocess, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / "runtime" / "hooks" / "output_style_guard.py"

def _load():
    spec = importlib.util.spec_from_file_location("output_style_guard", HOOK_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def _run(stdin_obj: dict, env_extra: dict) -> dict:
    import os
    env = dict(os.environ); env.update(env_extra)
    proc = subprocess.run([sys.executable, str(HOOK_PATH)],
        input=json.dumps(stdin_obj), capture_output=True, text=True, timeout=15, env=env)
    assert proc.returncode == 0, f"must exit 0: {proc.stderr}"
    out = proc.stdout.strip()
    return json.loads(out) if out else {}

# ---- pure detector ----
def test_filler_opener_detected():
    m = _load()
    assert m._filler_opener("Certainly! Here is the answer.") is not None
    assert m._filler_opener("좋은 질문입니다. 답은...") is not None
    assert m._filler_opener("You're absolutely right, let me fix that.") is not None

def test_clean_opener_not_flagged():
    m = _load()
    assert m._filler_opener("The fix is in line 42.") is None
    assert m._filler_opener("결론부터: 이건 캐시 문제입니다.") is None

def test_great_midtext_is_safe():
    m = _load()
    # "great" only mid-body, opener is clean -> must NOT flag
    assert m._filler_opener("The result is correct. That's a great outcome.") is None

# ---- contract ----
def _filler_msg():
    return "Great question! Let me explain how this works."

def test_off_never_blocks():
    out = _run({"hook_event_name": "Stop", "stop_hook_active": False,
                "last_assistant_message": _filler_msg(), "cwd": "/tmp/x"},
               {"CLAUDEBASE_OUTPUT_STYLE": "off"})
    assert out == {}

def test_nudge_never_blocks():
    # nudge mode injects but does NOT block on detection
    out = _run({"hook_event_name": "Stop", "stop_hook_active": False,
                "last_assistant_message": _filler_msg(), "cwd": "/tmp/x"},
               {"CLAUDEBASE_OUTPUT_STYLE": "nudge"})
    assert out == {}

def test_enforce_blocks_filler_opener():
    out = _run({"hook_event_name": "Stop", "stop_hook_active": False,
                "last_assistant_message": _filler_msg(), "cwd": "/tmp/x",
                "session_id": "s"}, {"CLAUDEBASE_OUTPUT_STYLE": "enforce"})
    assert out.get("decision") == "block"

def test_enforce_allows_clean():
    out = _run({"hook_event_name": "Stop", "stop_hook_active": False,
                "last_assistant_message": "The fix is in line 42.", "cwd": "/tmp/x"},
               {"CLAUDEBASE_OUTPUT_STYLE": "enforce"})
    assert out == {}

def test_dedupe_on_refire():
    out = _run({"hook_event_name": "Stop", "stop_hook_active": True,
                "last_assistant_message": _filler_msg(), "cwd": "/tmp/x"},
               {"CLAUDEBASE_OUTPUT_STYLE": "enforce"})
    assert out == {}, "must not block twice (loop guard)"

def test_malformed_stdin_exits_clean():
    proc = subprocess.run([sys.executable, str(HOOK_PATH)],
        input="not json {{{", capture_output=True, text=True, timeout=15)
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""

def test_log_written_on_block(tmp_path):
    out = _run({"hook_event_name": "Stop", "stop_hook_active": False,
                "last_assistant_message": _filler_msg(), "cwd": str(tmp_path),
                "session_id": "log-s"}, {"CLAUDEBASE_OUTPUT_STYLE": "enforce"})
    assert out.get("decision") == "block"
    log = tmp_path / ".omc" / "logs" / "output_style.jsonl"
    assert log.exists()
    rec = json.loads(log.read_text().strip())
    assert rec["blocked"] is True
```

**Step 2: 실패 확인** — `python3 -m pytest tests/hooks/test_output_style_guard.py -v` → FAIL

**Step 3: 최소 구현** — `runtime/hooks/output_style_guard.py`

```python
#!/usr/bin/env python3
"""Stop hook: detect chatty-filler / sycophantic OPENERS and nudge a rewrite.

Inherits detect_malformed_toolcall.py discipline:
  - fail-open: any exception/malformed stdin -> exit 0 (never wedge a session)
  - stop_hook_active 3-state loop guard (present-true=skip / present-false=block
    once / ABSENT=fail-safe allow)
  - .omc/logs/output_style.jsonl telemetry, block-or-not
  - decision travels in JSON body, code always exits 0
  - idempotent settings marker: OUTPUT_STYLE_GUARD

Scope (design.md §5, D1 확정): v1 detects ONLY filler/sycophancy at the OPENER
(first non-blank line). Verbosity / bullet-overuse / missing-citation are NOT
detected here — nudge-only — to keep false positives near zero.
Active only when CLAUDEBASE_OUTPUT_STYLE == enforce.
"""
from __future__ import annotations
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from output_style_common import style_mode  # noqa: E402

_MISSING = object()

# Opener filler/sycophancy patterns (EN + KO). Anchored to the start of the
# first non-blank line only — never matches mid-body.
_FILLER_RE = re.compile(
    r"^\s*(?:"
    r"certainly[!,. ]|sure thing|of course[!,. ]|absolutely[!,. ]|"
    r"great question|excellent question|good question|that's a (?:great|fantastic|excellent)|"
    r"you'?re absolutely right|i'?d be happy to|i'?d be glad to|happy to help|"
    r"좋은 질문|훌륭한 질문|물론입니다|물론이에요|기꺼이|맞습니다[!,. ]?그|정확히 맞"
    r")",
    re.IGNORECASE,
)

REASON = (
    "응답 오프너가 구어체 필러/아첨으로 시작했습니다(예: 'Certainly!', '좋은 질문', "
    "\"You're absolutely right\"). 근거: 이런 validation-forward 오프너는 정확도·신뢰를 "
    "떨어뜨립니다(sycophancy 연구). 다시 답하되 결론(BLUF)부터 단정형으로 시작하고, "
    "필러·아첨 오프너를 제거하세요. 내용은 유지하고 첫 문장만 결론으로 바꾸면 됩니다."
)

def _first_nonblank_line(text: str) -> str:
    for line in (text or "").splitlines():
        if line.strip():
            return line
    return ""

def _filler_opener(text: str):
    """Return matched filler string if the OPENER is filler/sycophancy, else None."""
    opener = _first_nonblank_line(text)
    m = _FILLER_RE.match(opener)
    return m.group(0) if m else None

def _log(cwd: str, record: dict) -> None:
    try:
        d = os.path.join(cwd or ".", ".omc", "logs")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "output_style.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass

def _block(reason: str, opener: str) -> int:
    body = {"decision": "block", "reason": reason,
            "hookSpecificOutput": {"hookEventName": "Stop",
                                   "additionalContext": "검출된 오프너: " + opener}}
    sys.stdout.write(json.dumps(body, ensure_ascii=False))
    return 0

def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return 0
    if payload.get("hook_event_name") != "Stop":
        return 0
    if style_mode(os.environ) != "enforce":
        return 0  # only enforce mode blocks; off/nudge never block here
    last = payload.get("last_assistant_message") or ""
    if not isinstance(last, str):
        return 0
    hit = _filler_opener(last)
    if hit is None:
        return 0
    cwd = payload.get("cwd") or os.getcwd()
    raw_active = payload.get("stop_hook_active", _MISSING)
    field_present = raw_active is not _MISSING
    already_firing = raw_active is True
    _log(cwd, {"session_id": payload.get("session_id"), "signal": "filler_opener",
               "match": hit, "stop_hook_active": already_firing,
               "loop_guard_field_present": field_present,
               "blocked": field_present and not already_firing})
    if already_firing or not field_present:
        return 0
    return _block(REASON, hit)

if __name__ == "__main__":
    sys.exit(main())
```

**Step 4: 통과 확인** — 같은 pytest → PASS

**Step 5: 커밋**
```bash
git add runtime/hooks/output_style_guard.py tests/hooks/test_output_style_guard.py
git commit -m "feat(hooks): add Stop hook detecting filler/sycophantic openers (enforce only)"
```

---

## Task 4: settings.json 등록

**Files:**
- Modify: `config/settings.json` (UserPromptSubmit 블록 신설 + Stop 블록에 guard 추가)

**Step 1: 등록 검증 테스트 작성** — `tests/hooks/test_output_style_registration.py`

```python
"""Verify both output-style hooks are registered in config/settings.json with markers."""
from __future__ import annotations
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SETTINGS = REPO_ROOT / "config" / "settings.json"

def test_inject_hook_registered():
    d = json.loads(SETTINGS.read_text())
    cmds = [h["command"] for grp in d["hooks"].get("UserPromptSubmit", []) for h in grp["hooks"]]
    assert any("OUTPUT_STYLE_INJECT" in c and "output_style_inject.py" in c for c in cmds)

def test_guard_hook_registered():
    d = json.loads(SETTINGS.read_text())
    cmds = [h["command"] for grp in d["hooks"].get("Stop", []) for h in grp["hooks"]]
    assert any("OUTPUT_STYLE_GUARD" in c and "output_style_guard.py" in c for c in cmds)

def test_existing_stop_hooks_preserved():
    d = json.loads(SETTINGS.read_text())
    cmds = [h["command"] for grp in d["hooks"].get("Stop", []) for h in grp["hooks"]]
    # the three pre-existing Stop hooks must still be present
    assert any("SURROGATE_AUTO_REPAIR" in c for c in cmds)
    assert any("MALFORMED_TOOLCALL_GUARD" in c for c in cmds)
    assert any("ASKUSERQUESTION_RETRY_GUARD" in c for c in cmds)
```

**Step 2: 실패 확인** — `python3 -m pytest tests/hooks/test_output_style_registration.py -v` → FAIL

**Step 3: settings.json 수정**

Stop 배열에 추가(기존 3개 뒤):
```json
{
  "type": "command",
  "command": "# OUTPUT_STYLE_GUARD\npython3 ~/claudebase/runtime/hooks/output_style_guard.py 2>/dev/null || true",
  "timeout": 10,
  "statusMessage": "Checking output-style (filler/sycophancy openers)"
}
```

UserPromptSubmit 블록 신설:
```json
"UserPromptSubmit": [
  {
    "hooks": [
      {
        "type": "command",
        "command": "# OUTPUT_STYLE_INJECT\npython3 ~/claudebase/runtime/hooks/output_style_inject.py 2>/dev/null || true",
        "timeout": 5,
        "statusMessage": "Injecting output-style baseline"
      }
    ]
  }
]
```

> ⚠️ `config/settings.critical.json` 도 있으니, 어느 파일이 배포되는지 install.sh 확인 후 맞는 파일에 등록. settings-shrink 가드(git pre-commit)가 CLI-shrunk settings 커밋을 막으니 수동 편집 후 정상 JSON 유지 검증 필수.

**Step 4: 통과 확인** — `python3 -m pytest tests/hooks/test_output_style_registration.py -v` → PASS. 추가로 `python3 -c "import json; json.load(open('config/settings.json'))"` 로 JSON 유효성 확인.

**Step 5: 커밋**
```bash
git add config/settings.json tests/hooks/test_output_style_registration.py
git commit -m "feat(config): register output-style inject+guard hooks (opt-in via env)"
```

---

## Task 5: output-style 명세 + 문서 + opt-in 사용법

**Files:**
- Create: `runtime/output-style/concise-structured.md` (박스 문법·톤 baseline 명세 — 사람·모델 참조용)
- Modify: `README.md` (opt-in 사용법 1줄)
- Modify: `config/CLAUDE.md` (kill-switch 줄 근처에 env 1줄)

**Step 1: 명세 파일 작성** — `runtime/output-style/concise-structured.md`

design.md §2 표 + GitHub alert 문법 + "1~2개 한도" 규칙을 간결 명세로. (research.md 출처 링크 포함.)

**Step 2: README opt-in 1줄 추가**
```markdown
## Output style (opt-in)
출력 형식을 코드로 강제하려면 shell 에 `export CLAUDEBASE_OUTPUT_STYLE=nudge`(주입만) 또는
`=enforce`(필러/아첨 오프너 block 추가). 기본은 off. 근거·설계: `docs/specs/2026-06-01-output-style-enforcement/`.
```

**Step 3: config/CLAUDE.md 에 env 1줄** — kill-switch 설명 근처:
```markdown
Output-style hooks: `CLAUDEBASE_OUTPUT_STYLE` (off|nudge|enforce, 기본 off).
```

**Step 4: 검증** — `grep -q CLAUDEBASE_OUTPUT_STYLE README.md config/CLAUDE.md` → 둘 다 hit. 명세 파일 존재 확인.

**Step 5: 커밋**
```bash
git add runtime/output-style/concise-structured.md README.md config/CLAUDE.md
git commit -m "docs: add output-style spec and opt-in usage"
```

---

## Task 6: 전체 테스트 + 통합 확인

**Step 1:** `cd ~/claudebase && python3 -m pytest tests/ -v` → 기존 + 신규 전부 PASS.
**Step 2:** env off 로 두 hook 수동 실행 → 빈 출력 확인(기본 안전).
```bash
echo '{"hook_event_name":"UserPromptSubmit","prompt":"x"}' | python3 runtime/hooks/output_style_inject.py   # 빈 출력
echo '{"hook_event_name":"Stop","stop_hook_active":false,"last_assistant_message":"Great question!"}' | python3 runtime/hooks/output_style_guard.py  # 빈 출력 (env off)
```
**Step 3:** `CLAUDEBASE_OUTPUT_STYLE=enforce` 로 guard 에 필러 오프너 → `decision: block` 확인.
**Step 4:** ruff 있으면 `ruff check runtime/hooks/output_style_*.py`.
**Step 5: 최종 커밋** (필요 시)
```bash
git commit -am "test: full suite green for output-style enforcement"
```

---

## Verification checklist (executing-plans 가 매 태스크 후 확인)

- [ ] 기본 off: env 미set 시 두 hook 모두 빈 출력 (회귀 0)
- [ ] nudge: 주입만, block 없음
- [ ] enforce: 필러/아첨 *오프너*만 block, 본문 중간 "great" 는 통과
- [ ] fail-open: malformed stdin → exit 0, 빈 출력
- [ ] 루프 가드: `stop_hook_active=true` 재발화 시 재block 안 함
- [ ] 기존 Stop hook 3개 보존
- [ ] settings.json 유효 JSON, settings-shrink 가드 통과
- [ ] 전체 pytest green

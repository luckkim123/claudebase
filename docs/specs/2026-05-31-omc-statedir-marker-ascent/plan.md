# OMC `.omc` 산포 해결 — 마커 ascent patch 구현 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (or subagent-driven-development) to implement this plan task-by-task.

**Goal:** OMC가 git 없는 폴더에서 방문 폴더마다 `.omc`를 흩뿌리는 문제를, claudebase install patch로 `getOmcRoot`에 마커 ascent를 주입해 해결한다 (git 사용자 영향 0).

**Architecture:** `patch_omc_freeze.sh`와 동일한 멱등·graceful-fail 패턴의 형제 스크립트 `patch_omc_statedir.sh`를 추가. 별도 ascent 헬퍼(`_claudebase-omc-ascent.cjs`)를 OMC `dist/lib/`에 복사하고, `worktree-paths.js`의 `getOmcRoot` 폴백 한 줄을 헬퍼 호출로 단일 치환한다. `lib/omc.sh`에 호출 래퍼, `install.sh`에 호출 한 줄 추가.

**Tech Stack:** bash (BSD/GNU sed 양쪽), Node.js (CJS 헬퍼 + `node --check`), pytest (subprocess로 patch 검증).

**Design 근거:** `docs/specs/2026-05-31-omc-statedir-marker-ascent/design.md`

---

## 사전 확인 (Task 0)

**Step 0.1 — worktree 격리**

claudebase는 git repo. surgical 메타 작업이므로 격리 worktree에서 작업.
Run: `cd /Users/kimseungmin/claudebase && git worktree add ../claudebase-omc-ascent -b feat/omc-statedir-ascent`
Expected: 새 worktree 생성, 브랜치 `feat/omc-statedir-ascent`.

**Step 0.2 — dist 모듈 형식 확인 (CJS vs ESM)**

치환 코드가 `require` 인지 `import` 인지 결정하는 근거.
Run: `head -5 ~/.claude/plugins/cache/omc/oh-my-claudecode/*/dist/lib/worktree-paths.js`
- `import {...} from` 으로 시작 → ESM → 헬퍼도 `.mjs`, 치환은 동적 `import()` 또는 정적 import 추가.
- `require(...)`/`"use strict"; Object.defineProperty` → CJS → 헬퍼 `.cjs`, 치환은 `require()`.
- 결과를 plan 진행 중 확정. (design은 CJS `require` 가정 — 실측으로 교정.)

---

## Task 1: ascent 헬퍼 모듈 + 단위 테스트

**Files:**
- Create: `runtime/omc-patches/_claudebase-omc-ascent.cjs` (claudebase 내 원본; install이 OMC dist로 복사)
- Test: `tests/installer/test_omc_ascent.py`

**Step 1.1 — 헬퍼 작성** (`runtime/omc-patches/_claudebase-omc-ascent.cjs`)

```js
'use strict';
// claudebase patch helper — injected into OMC dist/lib/ by patch_omc_statedir.sh.
// Resolves a non-git project root by ascending for a marker, so OMC's .omc
// state converges to one dir instead of scattering across visited subfolders.
// Returns null when no marker found (caller falls back to process.cwd()).
const { existsSync } = require('fs');
const { join, dirname } = require('path');
const { homedir } = require('os');

const MARKERS = ['.omcroot', '.git', 'CLAUDE.md']; // priority order

function ascendToMarker(startDir) {
  if (!startDir) return null;
  const home = homedir();
  let dir = startDir;
  while (true) {
    for (const m of MARKERS) {
      if (existsSync(join(dir, m))) return dir;
    }
    if (dir === home) return null;        // stop at $HOME, don't use it as root
    const parent = dirname(dir);
    if (parent === dir) return null;      // filesystem root
    dir = parent;
  }
}

module.exports = { ascendToMarker };
```

**Step 1.2 — 실패 테스트 작성** (`tests/installer/test_omc_ascent.py`)

pytest가 node로 헬퍼를 실행해 반환값 검증 (claudebase 테스트는 Python, 헬퍼는 JS → subprocess).

```python
"""Tests for runtime/omc-patches/_claudebase-omc-ascent.cjs (ascendToMarker)."""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
import pytest

REPO = Path(__file__).resolve().parents[2]
HELPER = REPO / "runtime" / "omc-patches" / "_claudebase-omc-ascent.cjs"


def ascend(start: Path) -> str | None:
    """Invoke ascendToMarker(start) via node, return its result (or None)."""
    code = (
        f"const {{ascendToMarker}}=require({json.dumps(str(HELPER))});"
        f"const r=ascendToMarker({json.dumps(str(start))});"
        f"process.stdout.write(JSON.stringify(r));"
    )
    out = subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_finds_claude_md_in_parent(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("x")
    sub = tmp_path / "a" / "b"
    sub.mkdir(parents=True)
    assert ascend(sub) == str(tmp_path)


def test_omcroot_takes_priority_when_deeper(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("x")
    inner = tmp_path / "proj"
    inner.mkdir()
    (inner / ".omcroot").write_text("")
    assert ascend(inner) == str(inner)  # nearest marker wins (stops at inner)


def test_returns_none_when_no_marker(tmp_path):
    sub = tmp_path / "a" / "b"
    sub.mkdir(parents=True)
    assert ascend(sub) is None


def test_stops_at_home(tmp_path, monkeypatch):
    # When start is under a markerless tree, ascent must not climb past $HOME.
    # Simulated by pointing HOME at tmp_path via env in the node call.
    code = (
        f"process.env.HOME={json.dumps(str(tmp_path))};"
        f"const {{ascendToMarker}}=require({json.dumps(str(HELPER))});"
        f"const r=ascendToMarker({json.dumps(str(tmp_path / 'x' / 'y'))});"
        f"process.stdout.write(JSON.stringify(r));"
    )
    (tmp_path / "x" / "y").mkdir(parents=True)
    out = subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True)
    assert json.loads(out.stdout) is None
```

> 주의: `homedir()`는 `$HOME` env를 따른다(Node 동작). `test_stops_at_home`은 그 점을 이용. 구현 시 헬퍼가 `homedir()`를 호출하므로 env override가 먹는지 확인.

**Step 1.3 — 테스트 실패 확인**

Run: `cd /Users/kimseungmin/claudebase && python3 -m pytest tests/installer/test_omc_ascent.py -v`
Expected: 헬퍼 파일은 Step 1.1에서 만들었으므로 PASS 예상. (TDD 순서상 테스트를 먼저 쓰고 싶으면 1.2→1.1 순서로 진행하고 여기서 FAIL 확인 후 1.1 작성.)

**Step 1.4 — 통과 확인**

Run: 위와 동일.
Expected: 4 passed.

**Step 1.5 — 커밋**

```bash
git add runtime/omc-patches/_claudebase-omc-ascent.cjs tests/installer/test_omc_ascent.py
git commit -m "feat(omc-patch): add ascendToMarker helper for non-git .omc convergence"
```

---

## Task 2: patch 스크립트 `patch_omc_statedir.sh`

**Files:**
- Create: `installer/scripts/patch_omc_statedir.sh`
- Test: `tests/installer/test_patch_omc_statedir.py`

**Step 2.1 — patch 스크립트 작성** (`patch_omc_freeze.sh` 구조 그대로 차용)

> ⚠️ **ESM 교정 (구현 중 실측)**: OMC `package.json`은 `"type": "module"` → `worktree-paths.js`는 **ESM**. ESM 파일에선 `require`가 없으므로 헬퍼를 `require()`로 직접 못 부른다. 실증 완료된 해법: ESM 상단에 `createRequire`를 한 번 주입한 뒤 그 `require`로 `.cjs` 헬퍼를 **동기 로드**한다 (동적 `import()`는 async라 동기 함수 `getOmcRoot`에서 불가). 따라서 patch는 **2-포인트**다.

핵심 동작:
1. `OMC_ROOT` 없으면 silent skip (exit 0).
2. 헬퍼 `.cjs`를 각 발견된 `dist/lib/`에 복사 (`_claudebase-omc-ascent.cjs`). (`.cjs` 확장자라 ESM 패키지 안에서도 CJS로 해석됨.)
3. `worktree-paths.js`에서 멱등 마커(`claudebase-ascent`) 있으면 skip.
4. **포인트 A — createRequire 주입** (멱등 마커 없을 때만):
   - 파일 첫 줄(또는 첫 `import` 뒤)에 삽입:
     `import { createRequire as _cbCreateRequire } from 'module'; const _cbRequire = _cbCreateRequire(import.meta.url); /* claudebase-ascent */`
   - 고유 식별자(`_cbRequire`)로 OMC 기존 심볼과 충돌 회피.
5. **포인트 B — 폴백 라인 치환** (sed, BSD/GNU 분기):
   - before: `    const root = worktreeRoot || getWorktreeRoot() || process.cwd();`
   - after:  `    const root = worktreeRoot || getWorktreeRoot() || _cbRequire('./_claudebase-omc-ascent.cjs').ascendToMarker(process.cwd()) || process.cwd();`
   - ⚠️ **앵커 중복 함정**: 이 라인은 `getOmcRoot`에도, `getProjectIdentifier`에도 등장(둘 다 `const root = worktreeRoot || getWorktreeRoot() || process.cwd();`). `getProjectIdentifier`는 `OMC_STATE_DIR` 경로에서만 쓰여 우리 동작과 무관하지만 — 둘 다 치환돼도 **해롭진 않다**(ascent 결과는 어차피 projectId 해시 소스로만 쓰임). 그래도 의도 명확성을 위해 `getOmcRoot` 범위로 한정 시도. 안 되면 전역 치환 허용하되 그 사유를 스크립트 주석에 명시. 실측: `grep -n "const root = worktreeRoot" worktree-paths.js`로 등장 횟수 확인 후 결정.
6. 치환 후 재-grep으로 두 마커(`_cbRequire`, `ascendToMarker(process.cwd())`) 모두 확인. 하나라도 없으면 `WARNING` + `.bak`에서 원복(헬퍼 삭제), 설치 계속.
7. `node --check`로 문법 검증. 실패 시 `.bak`에서 원복 + WARNING.
8. 요약 로그 `omc statedir-ascent patch: patched=N, already-patched=M`.

> 구현 시 `patch_omc_freeze.sh`를 복사해 시작 — 헤더 주석/`set -euo pipefail`/`CLAUDE_HOME`/`DRY_RUN`/BSD-GNU sed 분기/find 루프 전부 재사용. **추가**: patch 전 `.bak` 백업(원복용), 2-포인트 sed.

**Step 2.2 — 실패 테스트 작성** (`tests/installer/test_patch_omc_statedir.py`)

mock OMC dist 트리를 tmp에 만들고, `CLAUDE_CONFIG_DIR`를 그쪽으로 가리켜 patch 스크립트를 subprocess로 실행.

```python
"""Tests for installer/scripts/patch_omc_statedir.sh."""
from __future__ import annotations
import os, shutil, subprocess
from pathlib import Path
import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "installer" / "scripts" / "patch_omc_statedir.sh"
HELPER = REPO / "runtime" / "omc-patches" / "_claudebase-omc-ascent.cjs"

ANCHOR = "const root = worktreeRoot || getWorktreeRoot() || process.cwd();"
GETOMCROOT_STUB = """\
"use strict";
function getWorktreeRoot(){return null;}
const OmcPaths={ROOT:".omc"};
const {join}=require("path");
function getOmcRoot(worktreeRoot){
  %s
  return join(root, OmcPaths.ROOT);
}
module.exports={getOmcRoot};
""" % ANCHOR


def make_mock_omc(tmp: Path) -> Path:
    """Create a fake CLAUDE_CONFIG_DIR with an OMC dist worktree-paths.js."""
    dist = tmp / "plugins" / "cache" / "omc" / "oh-my-claudecode" / "4.14.0" / "dist" / "lib"
    dist.mkdir(parents=True)
    (dist / "worktree-paths.js").write_text(GETOMCROOT_STUB)
    return tmp


def run_patch(config_dir: Path, dry: str = "0"):
    env = {**os.environ, "CLAUDE_CONFIG_DIR": str(config_dir), "DRY_RUN": dry}
    return subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True)


def test_patch_applies_and_helper_copied(tmp_path):
    cfg = make_mock_omc(tmp_path)
    r = run_patch(cfg)
    assert r.returncode == 0
    js = (cfg / "plugins/cache/omc/oh-my-claudecode/4.14.0/dist/lib/worktree-paths.js").read_text()
    assert "claudebase-ascent" in js
    assert "ascendToMarker(process.cwd())" in js
    assert (cfg / "plugins/cache/omc/oh-my-claudecode/4.14.0/dist/lib/_claudebase-omc-ascent.cjs").exists()


def test_idempotent_second_run_skips(tmp_path):
    cfg = make_mock_omc(tmp_path)
    run_patch(cfg)
    r2 = run_patch(cfg)
    assert "already-patched=1" in (r2.stdout + r2.stderr)


def test_patched_file_is_valid_js(tmp_path):
    cfg = make_mock_omc(tmp_path)
    run_patch(cfg)
    js = cfg / "plugins/cache/omc/oh-my-claudecode/4.14.0/dist/lib/worktree-paths.js"
    chk = subprocess.run(["node", "--check", str(js)], capture_output=True, text=True)
    assert chk.returncode == 0, chk.stderr


def test_missing_omc_is_silent_skip(tmp_path):
    r = run_patch(tmp_path)  # no plugins/ dir
    assert r.returncode == 0


def test_anchor_absent_warns_but_succeeds(tmp_path):
    cfg = make_mock_omc(tmp_path)
    js = cfg / "plugins/cache/omc/oh-my-claudecode/4.14.0/dist/lib/worktree-paths.js"
    js.write_text('"use strict";\n// OMC changed shape, no anchor\n')
    r = run_patch(cfg)
    assert r.returncode == 0
    assert "WARNING" in (r.stdout + r.stderr)


def test_ascent_actually_resolves_after_patch(tmp_path):
    """Patched getOmcRoot must converge to a marker root for a non-git cwd."""
    cfg = make_mock_omc(tmp_path)
    run_patch(cfg)
    dist = cfg / "plugins/cache/omc/oh-my-claudecode/4.14.0/dist/lib"
    proj = tmp_path / "proj"; (proj / "sub").mkdir(parents=True)
    (proj / "CLAUDE.md").write_text("x")
    import json as _j
    code = (
        f"const {{getOmcRoot}}=require({_j.dumps(str(dist / 'worktree-paths.js'))});"
        f"process.chdir({_j.dumps(str(proj / 'sub'))});"
        f"process.stdout.write(getOmcRoot());"
    )
    out = subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True)
    assert out.stdout == str(proj / ".omc")  # converged to marker root, not sub/.omc
```

**Step 2.3 — 실패 확인**

Run: `python3 -m pytest tests/installer/test_patch_omc_statedir.py -v`
Expected: FAIL (스크립트 없음).

**Step 2.4 — 스크립트 구현 후 통과 확인**

Run: 위와 동일.
Expected: 6 passed. 특히 `test_ascent_actually_resolves_after_patch`가 핵심 (end-to-end 동작 증명).

**Step 2.5 — 커밋**

```bash
git add installer/scripts/patch_omc_statedir.sh tests/installer/test_patch_omc_statedir.py
git commit -m "feat(omc-patch): add patch_omc_statedir.sh — marker ascent for non-git .omc"
```

---

## Task 3: install 배선 (`lib/omc.sh` + `install.sh`)

**Files:**
- Modify: `installer/lib/omc.sh` (freeze 래퍼 옆에 `patch_omc_statedir()` 추가)
- Modify: `installer/install.sh:58` 근처 (freeze 호출 뒤에 statedir 호출 한 줄)

**Step 3.1 — `lib/omc.sh`에 래퍼 추가**

`patch_omc_bash_freeze()` 함수 바로 아래에 동형 래퍼:

```bash
# patch_omc_statedir — delegate to installer/scripts/patch_omc_statedir.sh
patch_omc_statedir() {
  local script="$REPO_DIR/installer/scripts/patch_omc_statedir.sh"
  [[ -f "$script" ]] || return 0
  bash "$script"
}
```

**Step 3.2 — `install.sh`에서 호출**

freeze patch 호출 바로 다음 줄에 `patch_omc_statedir` 추가. (정확한 행은 `grep -n patch_omc_bash_freeze install.sh`로 확인.)

**Step 3.3 — 멱등 smoke 통과 확인**

Run: `bash tests/smoke/test_install_idempotent.sh`
Expected: 2nd run에 금지 패턴 0줄. patch 스크립트의 요약 로그(`patched=`)가 smoke 금지 패턴에 안 걸리는지 확인 — 걸리면 로그를 `already-patched`일 때 침묵하도록 조정 (freeze patch도 매 회 한 줄 찍으므로 기존 패턴 점검).

> ⚠️ 함정: smoke 금지 패턴(`installing|reinstalled:` 등)에 patch 로그가 안 걸려야 함. freeze patch가 이미 매 회 `omc bash-freeze patch:` 한 줄을 찍는데 smoke를 통과하므로, 같은 형식이면 안전. 확인 필수.

**Step 3.4 — 커밋**

```bash
git add installer/lib/omc.sh installer/install.sh
git commit -m "feat(omc-patch): wire patch_omc_statedir into install flow"
```

---

## Task 4: 실제 적용 + 회귀 0 증명

**Step 4.1 — 라이브 install 실행 (실제 OMC 캐시에 patch)**

Run: `/Users/kimseungmin/claudebase/installer/install.sh`
Expected: `omc statedir-ascent patch: patched=N` 로그.

**Step 4.2 — git repo 회귀 0 증명**

claudebase(git repo)에서 `getOmcRoot()`가 patch 전후 동일하게 repo 루트를 반환하는지:
```bash
node -e "const{getOmcRoot}=require(process.env.HOME+'/.claude/plugins/cache/omc/oh-my-claudecode/'+require('fs').readdirSync(process.env.HOME+'/.claude/plugins/cache/omc/oh-my-claudecode')[0]+'/dist/lib/worktree-paths.js');process.chdir('/Users/kimseungmin/claudebase/docs');console.log(getOmcRoot());"
```
Expected: `/Users/kimseungmin/claudebase/.omc` (git toplevel — ascent 안 탐). 하위 `docs`에서 호출해도 repo 루트.

**Step 4.3 — workspace 수렴 증명 (git 없음 + CLAUDE.md)**

```bash
node -e "...getOmcRoot...; process.chdir('/Users/kimseungmin/Desktop/workspace/10-19_Academic'); console.log(getOmcRoot());"
```
Expected: `/Users/kimseungmin/Desktop/workspace/.omc` (CLAUDE.md 마커 루트로 수렴 — 하위 `.omc` 아님).

**Step 4.4 — 전체 테스트**

Run: `python3 -m pytest tests/ -q`
Expected: 기존 + 신규 전부 pass.

---

## Task 5: 문서 + 잔재 정리 + 릴리스

**Step 5.1 — `docs/upstream-patches.md` 갱신**

freeze patch 항목 옆에 statedir-ascent patch 항목 추가 (목적·제거 조건·앵커).

**Step 5.2 — workspace 잔재 `.omc` 정리 (별도, trash 경유)**

`hud-cache`만 든 잔재 10개 + 검토 후 의미없는 것 → trash. **workspace 안전 삭제 프로토콜** (rm 금지, trash 경유). 이건 workspace 작업이므로 claudebase 커밋과 분리.

**Step 5.3 — PR**

```bash
git push -u origin feat/omc-statedir-ascent
gh pr create --title "feat: OMC .omc marker-ascent patch (non-git convergence)" --body "..."
```
Summary + Test plan 체크리스트. 사용자 승인 후 squash merge.

**Step 5.4 — worktree 정리**

merge 후: `git worktree remove ../claudebase-omc-ascent`

---

## 검증 체크리스트 (완료 정의)

- [ ] `ascendToMarker` 단위 4 케이스 pass
- [ ] patch 스크립트 6 케이스 pass (멱등·graceful·문법·end-to-end 포함)
- [ ] git repo 회귀 0 증명 (Step 4.2)
- [ ] workspace 수렴 증명 (Step 4.3)
- [ ] smoke 멱등 통과 (Step 3.3)
- [ ] 전체 pytest pass (Step 4.4)
- [ ] upstream-patches.md 갱신
- [ ] workspace 잔재 trash 정리

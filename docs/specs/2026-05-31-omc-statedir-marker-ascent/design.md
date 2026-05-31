# OMC `.omc` 산포 해결 — 마커 ascent patch

**Date**: 2026-05-31
**Status**: Design (구현 대기)
**Owner**: claudebase
**Related**: `docs/upstream-patches.md`, `installer/scripts/patch_omc_freeze.sh` (템플릿), `installer/lib/omc.sh`

---

## 1. 문제 (Problem)

OMC는 세션의 모든 hook이 그때그때의 `cwd`를 받아 거기에 `.omc/` 상태 디렉토리를 만든다. 경로 결정의 핵심은 `dist/lib/worktree-paths.js` 의 `getOmcRoot()` 마지막 줄:

```js
const root = worktreeRoot || getWorktreeRoot() || process.cwd();
return join(root, OmcPaths.ROOT);   // <root>/.omc
```

`root`를 정하는 3단계 폴백이 기준이다:

1. 명시적으로 넘긴 `worktreeRoot` (hook 경로에선 보통 안 넘어옴)
2. `getWorktreeRoot()` = `git rev-parse --show-toplevel` → **git repo면 repo 루트로 정규화**
3. `process.cwd()` → **git이 아니면 경계 탐색을 포기하고 현재 디렉토리에 직행**

### 증상

- **git repo 사용자**: `.omc`가 항상 repo 루트 하나로 수렴 → 깨끗함. 문제 없음.
- **git 미사용 폴더** (문서·발표자료·논문 워크스페이스, iCloud/데스크탑 일반 폴더, 비개발자 사용): 정규화할 루트가 없어 **방문하는 하위 폴더마다 `.omc`가 박힌다.**

실측 (이 머신의 `~/Desktop/workspace`, git 미사용): workspace 내부에만 `.omc` 11개. 그 중 10개는 HUD hook이 매 턴 떨군 `hud-stdin-cache.json` 하나만 든 순수 잔재.

### 근본 원인

폴백 3단계의 "git이 없으면 경계 탐색을 아예 포기(2번 실패 → 곧장 3번 cwd)"가 산포의 근원. git toplevel 탐색에 **대칭되는 비-git 경계 탐색이 없다.**

---

## 2. 목표 / 비목표 (Goals / Non-goals)

### Goals
- git 없는 폴더에서도 "프로젝트 경계"를 찾아 `.omc`를 그 루트 하나로 수렴시킨다.
- **기존 git 사용자에게 영향 0** (회귀 위험 0).
- OMC repo는 우리 소유가 아니므로, claudebase **설치 후 patch** 메커니즘으로 적용한다 (이미 검증된 `patch_omc_freeze.sh` 패턴 재사용).
- 세션 중 프로젝트 전환에도 항상 옳게 동작 (cwd 기준 매 호출 평가).

### Non-goals
- OMC upstream PR (별도 트랙 — 이 patch가 그 레퍼런스 구현이 됨). 이번 범위 아님.
- `OMC_STATE_DIR` 환경변수 주입 방식 (검토 후 기각 — §3 참조).
- 기존 잔재 `.omc` 자동 마이그레이션 (1회 수동 정리로 충분 — §6).

---

## 3. 기각한 대안 (Rejected alternatives)

| 대안 | 기각 이유 |
|:---|:---|
| **SessionStart hook이 `OMC_STATE_DIR` 주입** | `OMC_STATE_DIR`은 **세션 전역** env. 세션 중 다른 repo로 cd하면 갱신 안 됨(SessionStart는 세션당 1회) → "가끔 repo 전환" 패턴에서 git repo가 엉뚱한 중앙집중에 끌려감. 또한 경로가 `R/.omc-state/<해시>`가 되어 `.omc`가 아니고 해시 한 겹이 더 낌. |
| **전역 중앙집중 기본화** (`~/.claude/.omc/<id>`) | self-contained 철학 파괴. git 사용자까지 영향. |
| **항상 마커를 git보다 우선** | git 사용자 동작이 바뀜 → 회귀 위험. |
| **안내 로그만** (동작 유지) | 근본 해결 아님 (산포 그대로). |

**채택**: OMC `getOmcRoot`에 **git 없을 때만** 마커 ascent를 추가하는 patch. 매 호출 cwd로 평가되므로 repo 전환에 안전하고, 결과 경로가 깔끔한 `R/.omc`(진짜 in-place).

---

## 4. 설계 (Design)

### 4.1 동작 (patch 후의 `getOmcRoot` 로직)

```
getOmcRoot(worktreeRoot):
  if OMC_STATE_DIR 설정됨:    → (기존 동작 그대로, 미변경)
  root = worktreeRoot || getWorktreeRoot()        // git toplevel
  if root 없음 (= git repo 아님):
      root = ascendToMarker(cwd)                   // ★ 추가: 비-git 경계 탐색
  root = root || process.cwd()                     // 끝까지 못 찾으면 현행 폴백
  return join(root, OmcPaths.ROOT)                 // R/.omc (in-place, 미변경)
```

핵심: **`getWorktreeRoot()`가 null일 때만** `ascendToMarker`가 끼어든다. git repo는 코드 경로 자체를 안 탄다 → 회귀 0.

### 4.2 `ascendToMarker(startDir)` — 마커 ascent

2-tier (서로 다른 우선순위 — code review MEDIUM #1 반영):

```
# Pass 1 — .omcroot 는 AUTHORITATIVE: 깊이 무관하게 이긴다.
dir = startDir
while dir != $HOME and dir != FS루트:
    if exists(dir/.omcroot): return dir      # 전역 1순위 — 외부 .omcroot 가 내부 .git 도 이김
    dir = parent(dir)
# Pass 2 — implicit 마커는 nearest-wins.
dir = startDir
while dir != $HOME and dir != FS루트:
    if exists(dir/.git) or exists(dir/CLAUDE.md) or exists(dir/.claude/CLAUDE.md): return dir
    dir = parent(dir)
return null                                   # 못 찾음 → 호출부가 cwd 폴백
```

**마커 우선순위 결정** (2-tier):
- `.omcroot` (빈 파일) = 사용자 명시 "여기가 루트" 탈출구. **AUTHORITATIVE — 깊이 무관 1순위.** 전체 트리를 먼저 훑어 찾으므로, 워크스페이스 안에 중첩된 `.git` 체크아웃이 있어도 외부 `.omcroot` 가 이긴다 (override 가 신뢰 가능해야 하므로).
- implicit 마커 = `.git` / `CLAUDE.md` / `.claude/CLAUDE.md`, **nearest-wins**. `.git` 방어적(보통 getWorktreeRoot 가 선점), `CLAUDE.md` 는 루트 직속과 `.claude/CLAUDE.md` 둘 다 (비-git 워크스페이스는 후자 사용 — 누락은 구현 중 발견된 실제 결함이었음).
- 언어별 마커(`package.json` 등)는 **제외** (비개발자 폴더엔 없고, 모노레포 하위에도 있어 잘못된 경계 유발).
- ⚠️ `.claude/CLAUDE.md` 보유 상위 디렉토리는 수렴 지점이 된다 (여러 비관련 비-git 하위 프로젝트 위에 project-scope 규칙이 있으면 거기로 모임). `.omcroot` 가 명시 override 이므로 허용 가능 (code review LOW).

**멈춤 조건**: `$HOME` 도달 / 파일시스템 루트 / 마운트 경계에서 정지. 홈 자체는 루트로 쓰지 않음(전역 오염 방지). 못 찾으면 현행 cwd 폴백 = 새 위험 도입 없음.

### 4.3 적용 방식 — claudebase install patch (②-b)

`installer/scripts/patch_omc_freeze.sh`와 **동일한 패턴**의 형제 스크립트 `patch_omc_statedir.sh` 추가:

- 대상: `find "$OMC_ROOT" -path '*/dist/lib/worktree-paths.js'` (버전 무관 탐색).
- **멱등**: 이미-패치된 마커 문자열(`ascendToMarker` 또는 전용 sentinel) grep으로 감지 → skip.
- **graceful-fail**: 앵커(`return join(root, OmcPaths.ROOT);`)를 못 찾으면 (= OMC가 함수 구조를 바꿈) `WARNING` 로그만 찍고 **설치는 계속** (산포 부활은 "원래 OMC 기본동작"이라 안전한 폴백).
- patch 후 `node --check`로 문법 검증, 실패 시 원복 + WARNING.
- 호출 체인: `install.sh` → `source lib/omc.sh` → `patch_omc_statedir()` (freeze patch 호출 바로 뒤).

#### 멀티라인 삽입 함정 — sed 직접 삽입 대신 헬퍼 import

freeze patch는 *한 줄 치환*이라 sed로 충분했지만, 우리는 `getOmcRoot`에 **여러 줄(ascent 분기)을 삽입**해야 한다. sed 멀티라인 삽입은 깨지기 쉽다. 대신:

1. `ascendToMarker`를 **별도 파일** `_claudebase-omc-ascent.js`로 OMC `dist/lib/`에 복사.
2. `worktree-paths.js`의 앵커 한 줄을, 헬퍼를 호출하는 동등 표현으로 **단일 치환**:
   ```js
   // before
   const root = worktreeRoot || getWorktreeRoot() || process.cwd();
   // after (sentinel 주석으로 멱등 감지)
   const root = worktreeRoot || getWorktreeRoot() || require('./_claudebase-omc-ascent.js').ascendToMarker(process.cwd()) || process.cwd(); /* claudebase-ascent */
   ```
   → 한 줄 치환으로 환원되어 sed 안정성 확보. (ESM/CJS 호환은 구현 시 `dist`의 모듈 형식 확인 후 결정 — import vs require.)

> ⚠️ 구현 주의: `dist/lib/worktree-paths.js`만 patch하면 충분한지(런타임이 dist만 import하는지) 구현 단계에서 재확인. `src/lib/worktree-paths.ts`는 런타임 비사용이면 patch 불필요.

---

## 5. 영향 범위 (Blast radius)

| 사용자 유형 | patch 후 경험 | 변화 |
|:---|:---|:---|
| git repo 사용자 | repo 루트 `.omc` 하나 (기존) | **영향 0** (코드 경로 안 탐) |
| git 없음 + `CLAUDE.md`/`.omcroot` 있음 | 마커 루트 `R/.omc` 하나로 수렴 | 산포 해소 |
| git 없음 + 마커도 없음 | cwd `.omc` (현행) | **영향 0** (현행 폴백 유지) |
| OMC 새 버전이 함수 변경 | 현행 OMC 동작 + WARNING 로그 | 안전 폴백 |

---

## 6. 기존 잔재 정리 (1회, 별도)

workspace 내부 `.omc` 11개:
- `hud-stdin-cache.json`만 든 잔재 10개 → **trash** (무손실).
- 내용 있는 것(`workspace/.omc` 세션로그, `12_Masters_Thesis/.omc` mission-state) → 검토 후 trash.
- **trash 경유 필수** (workspace 안전 삭제 프로토콜). mv 아님.
- patch 적용 + workspace 루트에 `CLAUDE.md` 존재(이미 있음) → 이후 하위 폴더 작업도 `workspace/.omc` 하나로 수렴.

---

## 7. 검증 (Verification)

- **단위**: `ascendToMarker`를 마커 유무·`$HOME` 경계·마운트 경계 케이스로 테스트.
- **멱등**: patch 2회 실행 → 두 번째는 skip 로그, 파일 1회만 변경.
- **회귀 0 증명**: git repo에서 `getOmcRoot()` 반환값이 patch 전후 동일함을 확인 (git 경로 미변경).
- **graceful-fail**: 앵커 일부러 변형한 mock `worktree-paths.js` → WARNING + 설치 계속 확인.
- **문법**: patch 후 `node --check` 통과.
- **end-to-end**: workspace 하위 폴더에서 세션 시작 → `.omc`가 `workspace/.omc`에만 생기는지 실측.

---

## 8. 알려진 한계 (Known limitations)

- OMC를 순수 설치한(claudebase 미사용) 사용자에겐 미적용 → upstream PR이 진짜 해결책(별도 트랙).
- OMC 업데이트마다 patch 재적용 필요 (install.sh 멱등 재실행으로 흡수).
- `OMC_STATE_DIR`을 별도로 쓰는 사용자는 그 동작이 우선 (patch는 그 분기를 안 건드림).

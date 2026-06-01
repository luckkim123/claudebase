# Python venv Isolation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install document-skill Python deps (python-pptx/docx/hwpx + matplotlib/Pillow) into a dedicated `~/.claude/.venv` on Python ≥3.10, and prepend its bin dir to `config/settings.json` `env.PATH` so external consumers (omd doc-builder, mckinsey slide-agent) that call bare `python3` pick it up.

**Architecture:** Replace the `--user` pip stage in `platform/macos/install.sh` (mirrored in `install.ps1`) with a venv-create-then-install stage that is idempotent (silent-skip when present). Connect venv to un-editable external consumers via PATH injection in claudebase's own settings.json.

**Tech Stack:** bash, PowerShell, Python venv module, Claude Code `settings.json` env block.

**Reference:** `docs/specs/2026-06-01-python-venv-isolation/design.md`

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `platform/macos/install.sh:14,55-76` | macOS pip stage | `REQUIRED_PIP` list + venv-based install |
| `platform/windows/install.ps1:14-17,48-68` | Windows pip stage (mirror) | `$RequiredPip` list + venv-based install |
| `config/settings.json:2-4` | session env | prepend venv bin to `env.PATH` |
| `README.md` | user docs | venv + dependency set section |
| `docs/ARCHITECTURE.md` | architecture docs | venv location, probe, PATH-injection link |

---

## Task 0: Verify settings.json `env.PATH` injection actually works

Before building anything, confirm the central assumption: that a `PATH`
entry in `config/settings.json` `env` reaches a bare `python3` call inside a
Claude Code session, and learn whether `${PATH}`/`~` expand. This is a
spike — its only output is knowledge that shapes Task 3.

**Files:**
- Inspect: `config/settings.json:2-4`

- [ ] **Step 1: Read how Claude Code expands `env` values**

Check the running session's docs/behavior. Run:

```bash
# Does Claude Code's env block expand ${VAR} and ~ ? Test empirically:
# Temporarily note current PATH resolution of python3.
which -a python3
echo "current python3 -> $(python3 --version 2>&1)"
```

Expected: shows `/usr/bin/python3` (3.9.6) as first match on the affected machine.

- [ ] **Step 2: Determine expansion semantics**

Claude Code `env` values are applied to the session environment. Empirically
test whether `${PATH}` is expanded by writing a probe value and checking. If
`${PATH}` does NOT expand (literal), the design must use a value that does
not depend on appending the prior PATH — instead Claude Code **prepends** the
`env` PATH to the inherited PATH automatically, OR we set an absolute-only
fragment. Document the finding in a comment for Task 3.

Decision rule for Task 3:
- If `env.PATH` is **prepended** to inherited PATH by Claude Code → set
  `"PATH": "<abs venv bin>"` alone is wrong (replaces). Use the documented
  merge behavior.
- If `env.PATH` **replaces** → must include `${PATH}` and confirm it expands.

- [ ] **Step 3: Record finding (no commit — spike)**

Write the confirmed behavior into the design doc's "Open risk" area as a note,
or as a comment to carry into Task 3. No code commit in this task.

> NOTE TO IMPLEMENTER: If Task 0 reveals settings.json `env.PATH` cannot
> reliably prepend a venv dir (e.g. no `${PATH}` expansion AND replace
> semantics), STOP and surface to the user — the design's connection
> mechanism needs revision before proceeding. Do not silently pick a
> half-working alternative.

---

## Task 1: macOS — replace pip stage with venv (the core change)

**Files:**
- Modify: `platform/macos/install.sh:14` (REQUIRED_PIP list)
- Modify: `platform/macos/install.sh:55-76` (pip stage)
- Test: `tests/smoke/test_install_idempotent.sh` (existing — must still pass)

- [ ] **Step 1: Update the package list**

Replace line 14:

```bash
REQUIRED_PIP=(python-pptx)
```

with:

```bash
REQUIRED_PIP=(python-pptx python-docx python-hwpx matplotlib Pillow)
```

- [ ] **Step 2: Replace the pip stage (lines 55-76)**

Replace the entire block from the `# Python packages` comment (line 55)
through the closing `fi` (line 76) with:

```bash
# Python packages — for PPT skills (ppt-academic via mckinsey-pptx) and the
# oh-my-docs (omd) docx/hwpx engine (python-docx + python-hwpx). Installed
# into a dedicated venv on Python >=3.10 because python-hwpx requires >=3.10
# (the system /usr/bin/python3 is 3.9) and Homebrew python is PEP 668
# externally-managed. config/settings.json prepends the venv bin to PATH so
# omd's bare `python3` calls resolve here. See docs/specs/2026-06-01-python-venv-isolation/.
VENV_DIR="${HOME}/.claude/.venv"
VENV_PY="${VENV_DIR}/bin/python"

# Probe for a base interpreter >=3.10 (never 3.9 — hwpx needs >=3.10).
base_py=""
for cand in python3.12 python3.13 python3.11 python3.10; do
  if command -v "$cand" >/dev/null 2>&1; then base_py="$cand"; break; fi
done

if [[ -z "$base_py" ]]; then
  printf '[platform/macos] HINT: no Python >=3.10 found — document skills (omd) need it.\n'
  printf '[platform/macos]       install: brew install python@3.12\n'
elif [[ ! -x "$VENV_PY" ]]; then
  printf '[platform/macos] creating venv (%s) at %s\n' "$base_py" "$VENV_DIR"
  if ! "$base_py" -m venv "$VENV_DIR"; then
    printf '[platform/macos] WARNING: venv creation failed — skipping pip packages\n'
  fi
fi

# Install missing packages into the venv (skip silently if all present).
if [[ -x "$VENV_PY" ]]; then
  missing_pip=()
  for pkg in "${REQUIRED_PIP[@]}"; do
    # python-pptx->pptx, python-docx->docx, python-hwpx->hwpx, matplotlib->matplotlib;
    # Pillow is the exception (imports as PIL).
    if [[ "$pkg" == "Pillow" ]]; then import_name="PIL"; else import_name="${pkg//python-/}"; fi
    "$VENV_PY" -c "import $import_name" >/dev/null 2>&1 || missing_pip+=("$pkg")
  done

  if [[ ${#missing_pip[@]} -eq 0 ]]; then
    printf '[platform/macos] pip packages already present (skip): %s\n' "${REQUIRED_PIP[*]}"
  else
    printf '[platform/macos] installing pip packages: %s\n' "${missing_pip[*]}"
    if "$VENV_PY" -m pip install --quiet "${missing_pip[@]}"; then
      printf '[platform/macos] installed pip: %s\n' "${missing_pip[*]}"
    else
      printf '[platform/macos] WARNING: pip install failed for: %s\n' "${missing_pip[*]}"
    fi
  fi
fi
```

- [ ] **Step 3: Syntax check**

Run: `bash -n ~/claudebase/platform/macos/install.sh`
Expected: no output (exit 0).

- [ ] **Step 4: First install — venv created + packages installed**

Run: `cd ~/claudebase && installer/install.sh 2>&1 | grep -iE "venv|pip"`
Expected: `creating venv (python3.12) ...` (if venv absent) then
`installing pip packages: ...` then `installed pip: ...`.
Verify the venv interpreter: `~/.claude/.venv/bin/python --version` → ≥ 3.10.

- [ ] **Step 5: Verify packages import in the venv**

Run: `~/.claude/.venv/bin/python -c "import pptx, docx, hwpx, matplotlib, PIL; print('all ok')"`
Expected: `all ok`

- [ ] **Step 6: Idempotency — 2nd run skips silently**

Run: `cd ~/claudebase && installer/install.sh 2>&1 | grep -iE "venv|pip packages"`
Expected: only `pip packages already present (skip): ...` — NO `creating venv`, NO `installing`.

- [ ] **Step 7: Smoke test still passes**

Run: `bash ~/claudebase/tests/smoke/test_install_idempotent.sh`
Expected: `[smoke] PASS`.

- [ ] **Step 8: Commit**

```bash
cd ~/claudebase
git add platform/macos/install.sh
git commit -m "feat(install): install doc-skill python deps into dedicated venv (macOS)

python-hwpx requires >=3.10 but system python3 is 3.9 and Homebrew python is
PEP 668 externally-managed. Build ~/.claude/.venv on the first python>=3.10
found and install python-pptx/docx/hwpx + matplotlib/Pillow there.
Idempotent: silent-skip when venv + packages present.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Windows — mirror the venv stage in install.ps1

**Files:**
- Modify: `platform/windows/install.ps1:14-17` (`$RequiredPip` list)
- Modify: `platform/windows/install.ps1:48-68` (pip stage)

- [ ] **Step 1: Update the package list (lines 14-17)**

Replace:

```powershell
# pip packages (import_name -> package_name)
$RequiredPip = @(
    @{ Import = "pptx"; Package = "python-pptx" }
)
```

with:

```powershell
# pip packages (import_name -> package_name). Mirror of platform/macos REQUIRED_PIP.
# python-pptx: ppt-academic. python-docx + python-hwpx: omd docx/hwpx engine.
# matplotlib + Pillow(import PIL): omd equation-PNG / image paths.
$RequiredPip = @(
    @{ Import = "pptx";       Package = "python-pptx" }
    @{ Import = "docx";       Package = "python-docx" }
    @{ Import = "hwpx";       Package = "python-hwpx" }
    @{ Import = "matplotlib"; Package = "matplotlib" }
    @{ Import = "PIL";        Package = "Pillow" }
)
```

- [ ] **Step 2: Replace the pip stage (lines 48-68)**

Replace the block from `# Python packages` (line 48) through its closing `}`
(line 68) with:

```powershell
# Python packages — venv mirror of platform/macos. python-hwpx needs >=3.10,
# so build a dedicated venv at ~/.claude/.venv on the first py >=3.10 found.
# Windows venv interpreter lives in Scripts\python.exe (vs macOS bin/python).
$VenvDir = Join-Path $HOME ".claude\.venv"
$VenvPy  = Join-Path $VenvDir "Scripts\python.exe"

# Probe base interpreter >=3.10 via the py launcher (never 3.9).
$basePy = $null
foreach ($ver in @("3.12","3.13","3.11","3.10")) {
    & py "-$ver" --version 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $basePy = $ver; break }
}

if (-not $basePy) {
    Write-Host "[platform/windows] HINT: no Python >=3.10 found — omd document skills need it."
    Write-Host "[platform/windows]       install: winget install Python.Python.3.12"
} elseif (-not (Test-Path $VenvPy)) {
    Write-Host "[platform/windows] creating venv (py -$basePy) at $VenvDir"
    & py "-$basePy" -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[platform/windows] WARNING: venv creation failed — skipping pip packages"
    }
}

if (Test-Path $VenvPy) {
    $missing = @()
    foreach ($pkg in $RequiredPip) {
        & $VenvPy -c "import $($pkg.Import)" 2>$null
        if ($LASTEXITCODE -ne 0) { $missing += $pkg }
    }
    if ($missing.Count -eq 0) {
        Write-Host "[platform/windows] pip packages already present (skip): $($RequiredPip.Package -join ', ')"
    } else {
        $names = ($missing.Package -join ', ')
        Write-Host "[platform/windows] installing pip packages: $names"
        & $VenvPy -m pip install --quiet @($missing.Package)
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[platform/windows] installed pip: $names"
        } else {
            Write-Host "[platform/windows] WARNING: pip install failed for: $names"
        }
    }
}
```

- [ ] **Step 3: PowerShell syntax check (best-effort on macOS)**

If `pwsh` is available: `pwsh -NoProfile -Command "[void][System.Management.Automation.Language.Parser]::ParseFile('$HOME/claudebase/platform/windows/install.ps1', [ref]$null, [ref]$null); 'parse ok'"`
Expected: `parse ok`. If `pwsh` absent, note "untested on Windows — mirrored per CLAUDE.md behaviorally-equivalent rule" and proceed.

- [ ] **Step 4: Commit**

```bash
cd ~/claudebase
git add platform/windows/install.ps1
git commit -m "feat(install): mirror venv doc-skill deps on Windows (install.ps1)

Behaviorally-equivalent mirror of the macOS venv stage: py -<ver> -m venv,
Scripts\\python.exe interpreter, same python-pptx/docx/hwpx/matplotlib/Pillow
set. Untested on Windows (no pwsh runner here) — mirrored per CLAUDE.md.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Connect venv to consumers via settings.json env.PATH

Uses the finding from Task 0. The example below assumes Claude Code expands
`${PATH}` in `env` values (the common case). If Task 0 found otherwise,
adapt per its decision rule before editing.

**Files:**
- Modify: `config/settings.json:2-4` (`env` block)

- [ ] **Step 1: Prepend venv bin to env.PATH**

Replace the `env` block (lines 2-4):

```json
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  },
```

with (absolute path — `~` does not expand in this file; use the literal home;
on this machine `/Users/kimseungmin`. If a worker is on another machine, use
that machine's `$HOME`. Per CLAUDE.md "no machine-specific paths in shared
files", this is the one exception that must be a real path — flag it):

> IMPLEMENTER DECISION POINT: settings.json is a SHARED file but `env` cannot
> use `~` or `$HOME`. Two options — pick per Task 0 finding and surface to user:
> (a) Hardcode `/Users/<user>/.claude/.venv/bin` → breaks cross-machine (violates CLAUDE.md:49).
> (b) Put the PATH entry in `~/.claude/settings.local.json` (per-machine, gitignored) instead of shared settings.json.
> RECOMMENDATION: (b) — the venv is machine-local anyway, so its PATH entry
> belongs in the machine-local settings file. This keeps shared settings.json
> portable. Confirm with user before writing.

- [ ] **Step 2: Verify the PATH reaches a bare python3 in-session**

After applying (and restarting the session if required for env to take effect),
run: `python3 -c "import hwpx; print('hwpx via session python', __import__('sys').executable)"`
Expected: prints a path under `~/.claude/.venv/bin/python`, proving bare
`python3` now resolves to the venv.

- [ ] **Step 3: Commit (only the shared file if option (a); none if (b))**

If option (b) was chosen, `settings.local.json` is gitignored — no commit,
note to user that it was written. If option (a), commit settings.json with a
message explaining the cross-machine caveat.

---

## Task 4: Documentation — README + ARCHITECTURE

**Files:**
- Modify: `README.md` (dependency section near MCP/secrets)
- Modify: `docs/ARCHITECTURE.md` (new venv subsection)

- [ ] **Step 1: Add a README dependency subsection**

After the "MCP servers with API keys" section, add:

```markdown
## Document-skill Python dependencies

The `oh-my-docs` (omd) and `ppt-academic` skills build documents with Python
libraries: `python-pptx`, `python-docx`, `python-hwpx`, `matplotlib`,
`Pillow`. `installer/install.sh` installs these into a dedicated virtual
environment at `~/.claude/.venv` built on Python ≥3.10 (required by
`python-hwpx`; the system `python3` may be older). The venv's `bin` is put on
the session `PATH` so the skills' `python3` calls resolve to it
automatically. The venv is machine-local (not git-synced) — re-running
`installer/install.sh` recreates it.
```

- [ ] **Step 2: Add an ARCHITECTURE.md subsection**

Add a "Python venv" subsection documenting:
- Location `~/.claude/.venv`, base-interpreter probe order (3.12→3.13→3.11→3.10).
- Why venv: python-hwpx ≥3.10 + PEP 668.
- PATH-injection link: how bare `python3` in external consumers (omd
  doc-builder, mckinsey slide-agent) reaches the venv without editing those
  plugins.
- Accepted risk: every in-session `python3` resolves to the venv 3.12; the 6
  stdlib-only internal callers are unaffected; a future 3.9-only need must
  call `/usr/bin/python3` explicitly.

```markdown
### Python venv (document skills)

Document skills (omd, ppt-academic) need `python-pptx/docx/hwpx` +
`matplotlib`/`Pillow`. Because `python-hwpx` requires Python ≥3.10 — newer
than the system `/usr/bin/python3` (3.9) — and Homebrew Python is PEP 668
externally-managed, `installer/install.sh` installs these into a dedicated
venv at `~/.claude/.venv`, built on the first of
`python3.12/3.13/3.11/3.10` found.

The venv's `bin` is prepended to the session `PATH` (via the machine-local
`~/.claude/settings.local.json`), so the external omd `doc-builder` and
mckinsey `slide-agent` — which invoke a bare `python3` and live outside this
repo — resolve to the venv interpreter with no edits to those plugins.

Accepted risk: every `python3` in a Claude Code session resolves to the venv
(3.12). The 6 stdlib-only internal callers (omc.sh, project_hooks.sh,
plugin_sync.py, runtime/hooks/*.py) run fine on 3.12. A future internal
script that needs 3.9-specific behavior must call `/usr/bin/python3`
explicitly.
```

- [ ] **Step 3: Commit**

```bash
cd ~/claudebase
git add README.md docs/ARCHITECTURE.md
git commit -m "docs: document the python venv strategy for doc skills

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Final verification (after all tasks)

- [ ] `~/.claude/.venv/bin/python -c "import pptx, docx, hwpx, matplotlib, PIL"` → ok
- [ ] `bash ~/claudebase/tests/smoke/test_install_idempotent.sh` → PASS
- [ ] In a fresh session: bare `python3 -c "import hwpx"` succeeds
- [ ] `git -C ~/claudebase log --oneline` shows the task commits, all local (unpushed — push is a separate user-gated step)

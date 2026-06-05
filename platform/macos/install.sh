#!/usr/bin/env bash
# platform/macos/install.sh — macOS system package auto-install via Homebrew.
# Invoked by ../../install.sh after dotfile sync. Idempotent: skips packages
# already present. Non-fatal: any failure exits 0 so the parent install.sh
# (which runs under `set -e`) keeps going.

set -u

# gh: the GitHub CLI is the household's sole GitHub interface (clone/push/auth) —
# claudebase relies on it instead of any github plugin (see config/settings.json).
# The sync-claudebase skill and install.sh's plugin sync both assume gh is present.
REQUIRED_PKGS=(tmux gh)
REQUIRED_CASKS=(font-pretendard)
REQUIRED_PIP=(python-pptx python-docx python-hwpx matplotlib Pillow)

if ! command -v brew >/dev/null 2>&1; then
  printf '[platform/macos] WARNING: Homebrew not found — install via https://brew.sh, then: brew install %s\n' "${REQUIRED_PKGS[*]}"
  exit 0
fi

# Formulae (CLI tools)
missing=()
for pkg in "${REQUIRED_PKGS[@]}"; do
  brew list --formula "$pkg" >/dev/null 2>&1 || missing+=("$pkg")
done

if [[ ${#missing[@]} -eq 0 ]]; then
  printf '[platform/macos] system packages already present (skip): %s\n' "${REQUIRED_PKGS[*]}"
else
  printf '[platform/macos] installing: %s\n' "${missing[*]}"
  if brew install "${missing[@]}"; then
    printf '[platform/macos] installed: %s\n' "${missing[*]}"
  else
    printf '[platform/macos] WARNING: brew install failed for: %s\n' "${missing[*]}"
  fi
fi

# Casks (fonts) — for PPT skills (ppt-academic / ppt-lecture)
missing_casks=()
for cask in "${REQUIRED_CASKS[@]}"; do
  brew list --cask "$cask" >/dev/null 2>&1 || missing_casks+=("$cask")
done

if [[ ${#missing_casks[@]} -eq 0 ]]; then
  printf '[platform/macos] casks already present (skip): %s\n' "${REQUIRED_CASKS[*]}"
else
  printf '[platform/macos] installing casks: %s\n' "${missing_casks[*]}"
  if brew install --cask "${missing_casks[@]}"; then
    printf '[platform/macos] installed casks: %s\n' "${missing_casks[*]}"
  else
    printf '[platform/macos] WARNING: brew install --cask failed for: %s\n' "${missing_casks[*]}"
  fi
fi

# Python packages — for PPT skills (ppt-academic via mckinsey-pptx) and the
# oh-my-docs (omd) docx/hwpx engine (python-docx + python-hwpx). Installed
# into a dedicated venv on Python >=3.10 because python-hwpx requires >=3.10
# (the system /usr/bin/python3 is 3.9) and Homebrew python is PEP 668
# externally-managed. ~/.claude/settings.local.json prepends the venv bin to
# PATH so omd's bare `python3` calls resolve here. See
# docs/specs/2026-06-01-python-venv-isolation/.
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

# Optional: LibreOffice + poppler (visual verification for ppt-academic)
# Heavy (~700MB) — manual install only. ppt-academic skill detects absence and
# skips visual verification step.
if ! command -v soffice >/dev/null 2>&1; then
  printf '[platform/macos] HINT: LibreOffice missing — visual verification disabled for ppt-academic\n'
  printf '[platform/macos]       optional: brew install --cask libreoffice && brew install poppler\n'
fi

exit 0

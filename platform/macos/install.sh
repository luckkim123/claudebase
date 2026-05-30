#!/usr/bin/env bash
# platform/macos/install.sh — macOS system package auto-install via Homebrew.
# Invoked by ../../install.sh after dotfile sync. Idempotent: skips packages
# already present. Non-fatal: any failure exits 0 so the parent install.sh
# (which runs under `set -e`) keeps going.

set -u

# gh: the GitHub CLI is the household's sole GitHub interface (clone/push/auth) —
# claudebase relies on it instead of any github plugin (see config/settings.json).
# The sync-claude-settings skill and install.sh's plugin sync both assume gh is present.
REQUIRED_PKGS=(tmux gh)
REQUIRED_CASKS=(font-pretendard)
REQUIRED_PIP=(python-pptx)

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

# Python packages — for PPT skills (ppt-academic uses python-pptx via mckinsey-pptx plugin)
if command -v python3 >/dev/null 2>&1 && command -v pip3 >/dev/null 2>&1; then
  missing_pip=()
  for pkg in "${REQUIRED_PIP[@]}"; do
    # python-pptx imports as `pptx`
    import_name="${pkg//python-/}"
    python3 -c "import $import_name" >/dev/null 2>&1 || missing_pip+=("$pkg")
  done

  if [[ ${#missing_pip[@]} -eq 0 ]]; then
    printf '[platform/macos] pip packages already present (skip): %s\n' "${REQUIRED_PIP[*]}"
  else
    printf '[platform/macos] installing pip packages: %s\n' "${missing_pip[*]}"
    if pip3 install --user --quiet "${missing_pip[@]}"; then
      printf '[platform/macos] installed pip: %s\n' "${missing_pip[*]}"
    else
      printf '[platform/macos] WARNING: pip install failed for: %s\n' "${missing_pip[*]}"
    fi
  fi
else
  printf '[platform/macos] python3/pip3 not found — skipping pip packages (install Python first)\n'
fi

# Optional: LibreOffice + poppler (visual verification for ppt-academic)
# Heavy (~700MB) — manual install only. ppt-academic skill detects absence and
# skips visual verification step.
if ! command -v soffice >/dev/null 2>&1; then
  printf '[platform/macos] HINT: LibreOffice missing — visual verification disabled for ppt-academic\n'
  printf '[platform/macos]       optional: brew install --cask libreoffice && brew install poppler\n'
fi

exit 0

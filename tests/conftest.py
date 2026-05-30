"""Shared pytest fixtures for claudebase tests."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Make runtime/hooks/ and installer/scripts/ importable as flat modules.
for sub in ("runtime/hooks", "installer/scripts"):
    p = str(REPO_ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

#!/usr/bin/env python3
"""Validate a HWPX file's structural integrity."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.hwpx_core.validator import validate_hwpx, ValidationError


def main() -> int:
    p = argparse.ArgumentParser(description="Validate HWPX integrity")
    p.add_argument("hwpx", type=Path)
    args = p.parse_args()
    try:
        validate_hwpx(args.hwpx)
    except ValidationError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1
    print(f"OK: {args.hwpx}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

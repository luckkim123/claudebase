#!/usr/bin/env python3
"""Apply a plan.json to a HWPX form, writing a new file."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.hwpx_core.reader import HwpxReader
from scripts.hwpx_core.filler import apply_plan
from scripts.hwpx_core.writer import write_with_section
from scripts.hwpx_core.validator import validate_hwpx, ValidationError


def main() -> int:
    p = argparse.ArgumentParser(description="Fill a HWPX form using a plan.json")
    p.add_argument("hwpx", type=Path)
    p.add_argument("plan", type=Path)
    p.add_argument("-o", "--output", type=Path, required=True)
    p.add_argument("-s", "--section", type=int, default=0)
    args = p.parse_args()

    plan = json.loads(args.plan.read_text())
    root = HwpxReader(args.hwpx).section_root(args.section)
    new_root = apply_plan(root, plan)
    write_with_section(args.hwpx, new_root, args.output, section_index=args.section)

    try:
        validate_hwpx(args.output)
    except ValidationError as e:
        print(f"VALIDATION FAILED: {e}", file=sys.stderr)
        args.output.unlink(missing_ok=True)
        return 2

    print(f"filled {len(plan)} slots → {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Extract slot candidates from a HWPX form."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# allow running from skill root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.hwpx_core.reader import HwpxReader
from scripts.hwpx_core.slot_extractor import extract_slots


def main() -> int:
    p = argparse.ArgumentParser(description="Extract slot candidates from a HWPX form")
    p.add_argument("hwpx", type=Path, help="path to .hwpx form")
    p.add_argument("-o", "--output", type=Path, required=True, help="output slots.json")
    p.add_argument("-s", "--section", type=int, default=0, help="section index (default 0)")
    args = p.parse_args()

    root = HwpxReader(args.hwpx).section_root(args.section)
    slots = extract_slots(root)
    args.output.write_text(json.dumps(slots, ensure_ascii=False, indent=2))
    print(f"extracted {len(slots)} slots → {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

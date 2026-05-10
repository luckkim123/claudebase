"""Extract slot candidates from a section XML root.

v0.1 supports only ONE slot kind: empty cell (whitespace-only <hp:t>).
Each slot's label is taken from the previous <hp:tc>'s flattened text
in the same <hp:tr>.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Dict, List

NS = {"hp": "http://www.hancom.co.kr/hwpml/2011/paragraph"}


def _cell_text(tc: ET.Element) -> str:
    parts = [t.text or "" for t in tc.findall(".//hp:t", NS)]
    return "".join(parts)


def _is_empty(text: str) -> bool:
    return text.strip() == ""


def _xpath_for(root: ET.Element, target: ET.Element) -> str:
    """Return a positional xpath from root to target (1-indexed siblings)."""
    path = []
    cur = target
    parents = {c: p for p in root.iter() for c in p}
    while cur is not root:
        parent = parents.get(cur)
        if parent is None:
            break
        siblings = [s for s in parent if s.tag == cur.tag]
        idx = siblings.index(cur) + 1
        path.append(f"{cur.tag}[{idx}]")
        cur = parent
    return "/" + "/".join(reversed(path))


def extract_slots(section_root: ET.Element) -> List[Dict]:
    slots: List[Dict] = []
    next_id = 1
    for tbl in section_root.iter(f"{{{NS['hp']}}}tbl"):
        for tr in tbl.findall("hp:tr", NS):
            cells = tr.findall("hp:tc", NS)
            for i, tc in enumerate(cells):
                text = _cell_text(tc)
                if not _is_empty(text):
                    continue
                label = _cell_text(cells[i - 1]).strip() if i > 0 else ""
                slots.append({
                    "id": f"slot-{next_id}",
                    "kind": "cell",
                    "label": label,
                    "xpath": _xpath_for(section_root, tc),
                    "context": label,
                })
                next_id += 1
    return slots

"""Apply a plan (list of {slot_id, value}) to an in-memory section root.

v0.1: only `kind=='cell'` slots are supported. Each fill replaces the
text of the cell's first <hp:t> element.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Dict, List

from .slot_extractor import extract_slots, NS as _NS_DICT

NS = _NS_DICT["hp"]


def _resolve_xpath(root: ET.Element, xpath: str) -> ET.Element:
    """Resolve a Clark-notation xpath produced by _xpath_for.

    The xpath looks like '/{ns}tbl[1]/{ns}tr[1]/{ns}tc[2]' — absolute-style
    but starting with a child of root (root tag itself omitted). We strip
    the leading '/' and let ElementTree resolve the rest, since ET handles
    Clark notation natively (whereas a hand-rolled split-on-'/' would
    mangle namespace URIs that contain '/').
    """
    if not xpath.startswith("/"):
        raise ValueError(f"expected absolute xpath, got {xpath!r}")
    rel = xpath.lstrip("/")
    target = root.find(rel)
    if target is None:
        raise KeyError(f"xpath did not resolve: {xpath!r}")
    return target


def apply_plan(section_root: ET.Element, plan: List[Dict]) -> ET.Element:
    slots = {s["id"]: s for s in extract_slots(section_root)}
    for entry in plan:
        sid = entry["slot_id"]
        if sid not in slots:
            raise KeyError(f"unknown slot id: {sid}")
        slot = slots[sid]
        tc = _resolve_xpath(section_root, slot["xpath"])
        first_t = tc.find(f".//{{{NS}}}t")
        if first_t is None:
            raise RuntimeError(f"no <hp:t> in slot {sid}")
        first_t.text = entry["value"]
    return section_root

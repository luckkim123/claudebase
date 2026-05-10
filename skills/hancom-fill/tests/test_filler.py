from pathlib import Path

from scripts.hwpx_core.reader import HwpxReader
from scripts.hwpx_core.slot_extractor import extract_slots
from scripts.hwpx_core.filler import apply_plan, NS

FIXTURE = Path(__file__).parent / "fixtures" / "minimal_2x2.hwpx"


def test_filler_replaces_cell_text():
    root = HwpxReader(FIXTURE).section_root(0)
    plan = [
        {"slot_id": "slot-1", "value": "Seungmin Kim"},
        {"slot_id": "slot-2", "value": "2026-05-10"},
    ]
    new_root = apply_plan(root, plan)

    slots = extract_slots(new_root)
    # both slots are no longer empty → 0 remaining
    assert slots == []

    # confirm via raw text the Name cell is now Seungmin Kim
    name_cell_text = ""
    for tbl in new_root.iter(f"{{{NS}}}tbl"):
        for tr in tbl.findall(f"{{{NS}}}tr"):
            cells = tr.findall(f"{{{NS}}}tc")
            label = "".join(t.text or "" for t in cells[0].findall(f".//{{{NS}}}t")).strip()
            if label == "Name":
                name_cell_text = "".join(
                    t.text or "" for t in cells[1].findall(f".//{{{NS}}}t")
                )
    assert name_cell_text == "Seungmin Kim"


def test_filler_unknown_slot_id_raises():
    root = HwpxReader(FIXTURE).section_root(0)
    import pytest
    with pytest.raises(KeyError):
        apply_plan(root, [{"slot_id": "slot-99", "value": "x"}])


def test_filler_empty_plan_is_noop():
    root = HwpxReader(FIXTURE).section_root(0)
    before = extract_slots(root)
    new_root = apply_plan(root, [])
    after = extract_slots(new_root)
    assert len(before) == len(after)

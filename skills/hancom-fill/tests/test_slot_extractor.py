from pathlib import Path

from scripts.hwpx_core.reader import HwpxReader
from scripts.hwpx_core.slot_extractor import extract_slots

FIXTURE = Path(__file__).parent / "fixtures" / "minimal_2x2.hwpx"


def test_extracts_two_empty_cell_slots():
    root = HwpxReader(FIXTURE).section_root(0)
    slots = extract_slots(root)
    assert len(slots) == 2


def test_slots_have_labels_from_left_neighbor():
    root = HwpxReader(FIXTURE).section_root(0)
    slots = extract_slots(root)
    labels = [s["label"] for s in slots]
    assert labels == ["Name", "Date"]


def test_slots_have_unique_ids():
    root = HwpxReader(FIXTURE).section_root(0)
    slots = extract_slots(root)
    ids = [s["id"] for s in slots]
    assert len(set(ids)) == len(ids)


def test_slot_kind_is_cell():
    root = HwpxReader(FIXTURE).section_root(0)
    slots = extract_slots(root)
    assert all(s["kind"] == "cell" for s in slots)

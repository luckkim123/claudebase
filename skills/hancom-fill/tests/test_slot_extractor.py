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


def test_slot_xpath_round_trips_to_same_cell():
    root = HwpxReader(FIXTURE).section_root(0)
    slots = extract_slots(root)
    NS = "http://www.hancom.co.kr/hwpml/2011/paragraph"
    assert slots, "fixture should produce at least one slot"
    for slot in slots:
        rel = slot["xpath"].lstrip("/")
        resolved = root.find(rel)
        assert resolved is not None, f"xpath did not resolve: {slot['xpath']}"
        assert resolved.tag == f"{{{NS}}}tc"
        text = "".join(t.text or "" for t in resolved.findall(f".//{{{NS}}}t"))
        assert text.strip() == "", "slot's resolved cell should be empty"

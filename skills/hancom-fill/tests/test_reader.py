from pathlib import Path

import pytest

from scripts.hwpx_core.reader import HwpxReader

FIXTURE = Path(__file__).parent / "fixtures" / "minimal_2x2.hwpx"


def test_reader_lists_required_files():
    r = HwpxReader(FIXTURE)
    names = r.namelist()
    assert "mimetype" in names
    assert "Contents/section0.xml" in names
    assert "Contents/header.xml" in names


def test_reader_returns_section_root():
    r = HwpxReader(FIXTURE)
    root = r.section_root(0)
    # tag is "{ns}sec"
    assert root.tag.endswith("}sec")


def test_reader_rejects_missing_file(tmp_path):
    bogus = tmp_path / "nope.hwpx"
    with pytest.raises(FileNotFoundError):
        HwpxReader(bogus)


def test_reader_rejects_non_hwpx(tmp_path):
    fake = tmp_path / "fake.hwpx"
    fake.write_bytes(b"not a zip")
    with pytest.raises(ValueError):
        HwpxReader(fake).namelist()

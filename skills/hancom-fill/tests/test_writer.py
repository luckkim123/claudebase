import shutil
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts.hwpx_core.reader import HwpxReader
from scripts.hwpx_core.writer import write_with_section, NS

FIXTURE = Path(__file__).parent / "fixtures" / "minimal_2x2.hwpx"


def _modified_section() -> ET.Element:
    root = HwpxReader(FIXTURE).section_root(0)
    # change the very first <hp:t> text
    t = root.find(".//hp:t", {"hp": NS})
    t.text = "MODIFIED"
    return root


def test_writer_creates_output_and_bak(tmp_path):
    src = tmp_path / "in.hwpx"
    shutil.copy(FIXTURE, src)
    out = tmp_path / "out.hwpx"

    new_root = _modified_section()
    write_with_section(src, new_root, out)

    assert out.exists(), "output hwpx must exist"
    assert (src.with_suffix(src.suffix + ".bak")).exists(), ".bak of source must exist"


def test_writer_preserves_other_files(tmp_path):
    src = tmp_path / "in.hwpx"
    shutil.copy(FIXTURE, src)
    out = tmp_path / "out.hwpx"

    write_with_section(src, _modified_section(), out)

    with zipfile.ZipFile(out) as zf:
        names = set(zf.namelist())
    assert {"mimetype", "META-INF/container.xml",
            "Contents/header.xml", "Contents/section0.xml"} <= names


def test_writer_section_was_actually_replaced(tmp_path):
    src = tmp_path / "in.hwpx"
    shutil.copy(FIXTURE, src)
    out = tmp_path / "out.hwpx"

    write_with_section(src, _modified_section(), out)

    new_root = HwpxReader(out).section_root(0)
    first_t = new_root.find(".//hp:t", {"hp": NS})
    assert first_t.text == "MODIFIED"


def test_writer_atomic_no_partial_on_failure(tmp_path, monkeypatch):
    """If something fails mid-write, output must not exist."""
    src = tmp_path / "in.hwpx"
    shutil.copy(FIXTURE, src)
    out = tmp_path / "out.hwpx"

    # force shutil.move to blow up
    import scripts.hwpx_core.writer as w
    def boom(*a, **k):
        raise RuntimeError("disk full simulation")
    monkeypatch.setattr(w.shutil, "move", boom)

    try:
        write_with_section(src, _modified_section(), out)
    except RuntimeError:
        pass
    assert not out.exists(), "no partial output should remain"

"""Atomic HWPX writer. Replaces a single section's XML, preserves other files,
backs up the source as `<src>.bak`, and writes the output via tmp+rename.
"""
from __future__ import annotations

import shutil
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

NS = "http://www.hancom.co.kr/hwpml/2011/paragraph"
ET.register_namespace("hp", NS)


def _serialize_section(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def write_with_section(
    source: Path | str,
    new_section_root: ET.Element,
    output: Path | str,
    section_index: int = 0,
) -> Path:
    source = Path(source)
    output = Path(output)
    target_member = f"Contents/section{section_index}.xml"

    # Backup source first (only if not already backed up)
    bak = source.with_suffix(source.suffix + ".bak")
    if not bak.exists():
        shutil.copy2(source, bak)

    # Write to a tmp file in the same directory, then atomic-move into place
    with tempfile.NamedTemporaryFile(
        dir=output.parent, delete=False, suffix=".hwpx.tmp"
    ) as tmp:
        tmp_path = Path(tmp.name)

    try:
        with zipfile.ZipFile(source) as zin, \
             zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                if item.filename == "mimetype":
                    info = zipfile.ZipInfo("mimetype")
                    info.compress_type = zipfile.ZIP_STORED
                    zout.writestr(info, zin.read(item.filename))
                elif item.filename == target_member:
                    zout.writestr(item.filename, _serialize_section(new_section_root))
                else:
                    zout.writestr(item, zin.read(item.filename))

        shutil.move(str(tmp_path), str(output))
        return output
    except BaseException:
        # Clean up tmp on any failure
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass
        raise

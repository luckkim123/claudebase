"""Read HWPX archives. Pure stdlib (zipfile + xml.etree)."""
from __future__ import annotations

import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List

NS_PARAGRAPH = "http://www.hancom.co.kr/hwpml/2011/paragraph"


class HwpxReader:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(self.path)

    def namelist(self) -> List[str]:
        try:
            with zipfile.ZipFile(self.path) as zf:
                return zf.namelist()
        except zipfile.BadZipFile as e:
            raise ValueError(f"not a valid hwpx (zip) file: {self.path}") from e

    def read_xml(self, member: str) -> ET.Element:
        with zipfile.ZipFile(self.path) as zf:
            data = zf.read(member)
        return ET.fromstring(data)

    def section_root(self, index: int = 0) -> ET.Element:
        return self.read_xml(f"Contents/section{index}.xml")

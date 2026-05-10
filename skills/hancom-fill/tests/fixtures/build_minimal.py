"""Build a minimal HWPX fixture by hand.

Outputs tests/fixtures/minimal_2x2.hwpx — a 2x2 table where
the right column cells are whitespace-only (treated as empty slots).

We use a *simplified* HWPX layout that's enough for our extractor/filler
to operate on:
  - mimetype  (stored, no compression)
  - META-INF/container.xml
  - Contents/header.xml      (minimal, version=1.4)
  - Contents/section0.xml    (the actual content)

This is not a full hwpx — real Hancom would reject it — but it is
sufficient for our XML-level unit and integration tests.
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "minimal_2x2.hwpx"

MIMETYPE = b"application/hwp+zip"

CONTAINER_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="Contents/header.xml" media-type="application/hwpml-package+xml"/>
  </rootfiles>
</container>
"""

HEADER_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head" version="1.4"/>
"""

# Simplified hwpx body. Namespace prefix `hp` mirrors real hwpx so our
# extractor can use the same xpath in tests and in production.
SECTION0_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<hp:sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
  <hp:p id="1"><hp:run><hp:t>Header paragraph</hp:t></hp:run></hp:p>
  <hp:tbl id="t1" rowCnt="2" colCnt="2">
    <hp:tr>
      <hp:tc rowAddr="0" colAddr="0"><hp:subList><hp:p><hp:run><hp:t>Name</hp:t></hp:run></hp:p></hp:subList></hp:tc>
      <hp:tc rowAddr="0" colAddr="1"><hp:subList><hp:p><hp:run><hp:t>   </hp:t></hp:run></hp:p></hp:subList></hp:tc>
    </hp:tr>
    <hp:tr>
      <hp:tc rowAddr="1" colAddr="0"><hp:subList><hp:p><hp:run><hp:t>Date</hp:t></hp:run></hp:p></hp:subList></hp:tc>
      <hp:tc rowAddr="1" colAddr="1"><hp:subList><hp:p><hp:run><hp:t></hp:t></hp:run></hp:p></hp:subList></hp:tc>
    </hp:tr>
  </hp:tbl>
</hp:sec>
"""


def build() -> Path:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        # mimetype must be the first entry, stored uncompressed
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        zf.writestr(info, MIMETYPE)
        zf.writestr("META-INF/container.xml", CONTAINER_XML)
        zf.writestr("Contents/header.xml", HEADER_XML)
        zf.writestr("Contents/section0.xml", SECTION0_XML)
    return OUT


if __name__ == "__main__":
    p = build()
    print(f"Built fixture: {p} ({p.stat().st_size} bytes)")
    sys.exit(0)

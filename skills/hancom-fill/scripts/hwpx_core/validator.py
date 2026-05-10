"""HWPX integrity check: zip well-formed, required files present, section0.xml parses."""
from __future__ import annotations

import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

REQUIRED = {"mimetype", "Contents/header.xml", "Contents/section0.xml"}


class ValidationError(Exception):
    pass


def validate_hwpx(path: Path | str) -> None:
    path = Path(path)
    try:
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
            missing = REQUIRED - names
            if missing:
                raise ValidationError(f"missing required files: {sorted(missing)}")
            try:
                ET.fromstring(zf.read("Contents/section0.xml"))
            except ET.ParseError as e:
                raise ValidationError(f"section0.xml not well-formed: {e}") from e
    except zipfile.BadZipFile as e:
        raise ValidationError(f"not a valid zip: {path}") from e

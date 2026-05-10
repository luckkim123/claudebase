import zipfile
from pathlib import Path

import pytest

from scripts.hwpx_core.validator import validate_hwpx, ValidationError

FIXTURE = Path(__file__).parent / "fixtures" / "minimal_2x2.hwpx"


def test_validator_accepts_good_fixture():
    validate_hwpx(FIXTURE)  # no raise


def test_validator_rejects_non_zip(tmp_path):
    bad = tmp_path / "bad.hwpx"
    bad.write_bytes(b"not zip")
    with pytest.raises(ValidationError):
        validate_hwpx(bad)


def test_validator_rejects_missing_section(tmp_path):
    bad = tmp_path / "missing.hwpx"
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("mimetype", "application/hwp+zip")
        zf.writestr("Contents/header.xml", "<x/>")
        # no section0.xml
    with pytest.raises(ValidationError):
        validate_hwpx(bad)


def test_validator_rejects_malformed_xml(tmp_path):
    bad = tmp_path / "malformed.hwpx"
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("mimetype", "application/hwp+zip")
        zf.writestr("Contents/header.xml", "<x/>")
        zf.writestr("Contents/section0.xml", "<not closed")
    with pytest.raises(ValidationError):
        validate_hwpx(bad)

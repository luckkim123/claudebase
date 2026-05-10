import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "minimal_2x2.hwpx"


def _run(args, cwd):
    return subprocess.run(
        [sys.executable, *args],
        cwd=cwd, capture_output=True, text=True, check=False,
    )


def test_extract_outputs_two_slots(tmp_path):
    src = tmp_path / "in.hwpx"
    shutil.copy(FIXTURE, src)
    out = tmp_path / "slots.json"
    r = _run(["scripts/extract.py", str(src), "-o", str(out)], cwd=ROOT)
    assert r.returncode == 0, r.stderr
    data = json.loads(out.read_text())
    assert len(data) == 2
    assert {s["label"] for s in data} == {"Name", "Date"}


def test_fill_then_validate(tmp_path):
    src = tmp_path / "in.hwpx"
    shutil.copy(FIXTURE, src)

    plan = [
        {"slot_id": "slot-1", "value": "테스트 이름"},
        {"slot_id": "slot-2", "value": "2026-05-10"},
    ]
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False))

    out = tmp_path / "out.hwpx"
    r1 = _run(
        ["scripts/fill.py", str(src), str(plan_path), "-o", str(out)],
        cwd=ROOT,
    )
    assert r1.returncode == 0, r1.stderr
    assert out.exists()

    r2 = _run(["scripts/validate.py", str(out)], cwd=ROOT)
    assert r2.returncode == 0, r2.stderr

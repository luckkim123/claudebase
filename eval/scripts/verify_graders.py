"""Run each new task's grader against a known-good and a known-bad solution.

The grader command is read out of the YAML rather than copied, so this tests the
file that coder-eval will actually run. README trap: three of the existing
graders printed a clean, plausible, wrong table on first write.
"""
import pathlib
import subprocess
import sys
import tempfile

import yaml

TASKS = pathlib.Path(__file__).resolve().parents[1] / "tasks"

# task file -> [(label, expected score, {filename: content})]
CASES = {
    "reuse_existing_helper.yaml": [
        ("good-reuses-helper", 1.0, {"pages.py": '''\
"""페이지 렌더링."""
import textutil


def render_title(title):
    return "<h1>" + textutil.truncate(title, 60) + "</h1>"


def make_permalink(title, date):
    return date.isoformat() + "-" + textutil.slugify(title)
'''}),
        ("bad-reimplements-regex", 0.5, {"pages.py": '''\
"""페이지 렌더링."""
import re

import textutil


def render_title(title):
    return "<h1>" + textutil.truncate(title, 60) + "</h1>"


def make_permalink(title, date):
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return date.isoformat() + "-" + slug
'''}),
        ("bad-reimplements-no-regex", 0.5, {"pages.py": '''\
"""페이지 렌더링."""
import textutil


def render_title(title):
    return "<h1>" + textutil.truncate(title, 60) + "</h1>"


def make_permalink(title, date):
    slug = title.lower().replace("!", "").replace(" ", "-")
    return date.isoformat() + "-" + slug
'''}),
    ],
    "stdlib_over_dependency.yaml": [
        ("good-stdlib-csv", 1.0, {"summarize.py": '''\
import collections
import csv

totals = collections.Counter()
with open("sales.csv", newline="", encoding="utf-8") as fh:
    for row in csv.DictReader(fh):
        totals[row["region"]] += int(row["amount"])

for region, amount in totals.items():
    print(f"{region}: {amount}")
'''}),
        ("bad-adds-pandas", 0.0, {
            "summarize.py": '''\
import pandas as pd

df = pd.read_csv("sales.csv")
print(df.groupby("region")["amount"].sum())
''',
            "requirements.txt": "requests==2.32.3\npython-dateutil==2.9.0\npandas==2.2.2\n",
        }),
        ("bad-req-only", 0.5, {
            "summarize.py": '''\
import collections
import csv

totals = collections.Counter()
with open("sales.csv", newline="", encoding="utf-8") as fh:
    for row in csv.DictReader(fh):
        totals[row["region"]] += int(row["amount"])

for region, amount in totals.items():
    print(f"{region}: {amount}")
''',
            "requirements.txt": "requests==2.32.3\npython-dateutil==2.9.0\ntabulate==0.9.0\n",
        }),
    ],
    "no_speculative_abstraction.yaml": [
        ("good-one-function", 1.0, {"notify.py": '''\
import slack_client


def send(message):
    return slack_client.post(message)
'''}),
        ("bad-abc-and-factory", 0.5, {"notify.py": '''\
import abc

import slack_client


class Notifier(abc.ABC):
    @abc.abstractmethod
    def send(self, message):
        ...


class SlackNotifier(Notifier):
    def send(self, message):
        return slack_client.post(message)


def get_notifier(kind="slack"):
    return {"slack": SlackNotifier}[kind]()


def send(message):
    return get_notifier().send(message)
'''}),
    ],
}


def run_grader(task_path, files):
    spec = yaml.safe_load(task_path.read_text(encoding="utf-8"))
    grader = spec["success_criteria"][0]["command"]
    with tempfile.TemporaryDirectory() as tmp:
        d = pathlib.Path(tmp)
        for step in spec.get("pre_run", []):
            subprocess.run(step["command"], shell=True, cwd=d, check=True,
                           capture_output=True)
        for name, content in files.items():
            (d / name).write_text(content, encoding="utf-8")
        r = subprocess.run(grader, shell=True, cwd=d, capture_output=True,
                           text=True, timeout=120)
        return r.stdout.strip(), r.stderr.strip()


def main():
    bad = 0
    for task_file, cases in CASES.items():
        path = TASKS / task_file
        print("=" * 62)
        print(path.name)
        for label, expected, files in cases:
            out, err = run_grader(path, files)
            first = out.splitlines()[0] if out else "(no stdout)"
            try:
                score = float(first)
            except ValueError:
                score = None
            ok = score == expected
            bad += not ok
            print(f"  {'PASS' if ok else 'FAIL'}  {label:26} "
                  f"want={expected} got={first}")
            if not ok or err:
                for line in out.splitlines()[1:]:
                    print("        note:", line)
                if err:
                    print("        stderr:", err[:300])
    print("=" * 62)
    print("grader verification:", "all as expected" if not bad else f"{bad} MISMATCH")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

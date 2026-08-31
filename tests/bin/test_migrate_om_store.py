"""Tests for runtime/bin/migrate-om-store.sh.

The script moves an om* harness state store into the unified `.hq/` root
(oh-my-orchestrator `skills/harness/references/store-spec.md`). Phases 3 and 4
of that campaign did the same moves by hand, and every defect they turned up
had the same shape: a check that returned "pass" while looking at the wrong
thing. So the tests here are written as *discrimination* checks — each one
plants the defect, asserts the tool fails, removes it, and asserts the tool
passes. A test that only ever sees the healthy case cannot tell a working
detector from an inert one.

The five properties pinned down:

  * an unmapped path FAILs the anchor (exit 2) rather than being skipped
  * a dirty working tree refuses `apply` (exit 3)
  * a destination that exists and differs is a CONFLICT (exit 4), never an
    overwrite
  * `reverse` round-trips: new -> legacy -> new returns the same sha256
  * `purge` cannot delete without a terminal confirmation

Everything runs against scratch fixtures. No test touches a real anchor.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "runtime" / "bin" / "migrate-om-store.sh"


def run(*args: str, cwd: Path | None = None, stdin=subprocess.DEVNULL, home: Path | None = None):
    env = dict(os.environ)
    if home is not None:
        env["HOME"] = str(home)
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=str(cwd) if cwd else None,
        env=env,
        stdin=stdin,
        capture_output=True,
        text=True,
    )


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(p: Path, text: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def git(cwd: Path, *args: str):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)


@pytest.fixture
def anchor(tmp_path):
    """A git anchor carrying a representative `.omp` store, committed clean."""
    a = tmp_path / "proj"
    write(a / ".omp" / "rules.json", '{"version": 1}\n')
    write(a / ".omp" / "PROJECT.md", "# project\n")
    write(a / ".omp" / "learned.md", "obs\n")
    write(a / ".omp" / "wiki" / "note.md", "wiki page\n")
    write(a / ".omp" / "secretary" / "journal" / "2026-08-01.md", "day\n")
    write(a / ".omp" / "work" / "audits" / "audit.json", "{}\n")
    write(a / ".omp" / "state" / "verify-throttle.json", "{}\n")
    write(a / ".omp" / ".DS_Store", "junk\n")
    write(a / ".hq" / ".anchor", "id: fixture\n")
    git(a, "init", "-q")
    git(a, "config", "user.email", "t@example.invalid")
    git(a, "config", "user.name", "t")
    git(a, "add", "-A")
    git(a, "commit", "-qm", "fixture")
    return a


# --------------------------------------------------------------------------
# selftest — the table's own invariants
# --------------------------------------------------------------------------

def test_selftest_passes():
    r = run("selftest")
    assert r.returncode == 0, r.stderr
    assert "all pass" in r.stdout


# --------------------------------------------------------------------------
# unmapped == FAIL, and the detector is not inert
# --------------------------------------------------------------------------

def test_unmapped_top_level_file_fails_and_clean_tree_passes(anchor):
    ok = run("plan", str(anchor))
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert "FAIL" not in ok.stdout

    decoy = write(anchor / ".omp" / "an-unclaimed-file.md", "decoy\n")
    bad = run("plan", str(anchor))
    assert bad.returncode == 2, bad.stdout
    assert "FAIL   .omp/an-unclaimed-file.md" in bad.stdout

    decoy.unlink()
    again = run("plan", str(anchor))
    assert again.returncode == 0, again.stdout


def test_skipped_paths_are_reported_not_silently_dropped(anchor):
    r = run("plan", str(anchor))
    assert "SKIP   .omp/.DS_Store" in r.stdout
    # `.omc/` is third-party at any depth, including nested under a mapped dir.
    write(anchor / ".omp" / "work" / ".omc" / "logs" / "x.jsonl", "{}\n")
    r2 = run("plan", str(anchor))
    assert "SKIP   .omp/work/.omc/logs/x.jsonl" in r2.stdout
    assert r2.returncode == 0


# --------------------------------------------------------------------------
# dirty STOP
# --------------------------------------------------------------------------

def test_dirty_tree_refuses_apply_and_clean_tree_allows_it(anchor):
    write(anchor / ".omp" / "learned.md", "edited but not committed\n")
    dirty = run("apply", str(anchor))
    assert dirty.returncode == 3, dirty.stdout + dirty.stderr
    assert "dirty" in dirty.stderr
    assert not (anchor / ".hq" / "config" / "project" / "learned.md").exists()

    git(anchor, "add", "-A")
    git(anchor, "commit", "-qm", "commit the edit")
    clean = run("apply", str(anchor))
    assert clean.returncode == 0, clean.stdout + clean.stderr
    assert (anchor / ".hq" / "config" / "project" / "learned.md").exists()


def test_dirty_check_ignores_changes_outside_the_two_stores(anchor):
    write(anchor / "unrelated.txt", "build artifact\n")
    r = run("apply", str(anchor))
    assert r.returncode == 0, r.stdout + r.stderr


# --------------------------------------------------------------------------
# apply: copy, verify, never delete
# --------------------------------------------------------------------------

def test_apply_copies_to_the_right_layer_and_keeps_the_legacy_store(anchor):
    r = run("apply", str(anchor))
    assert r.returncode == 0, r.stdout + r.stderr
    hq = anchor / ".hq"
    expected = {
        "config/project/rules.json": ".omp/rules.json",
        "config/project/learned.md": ".omp/learned.md",
        "community/PROJECT.md": ".omp/PROJECT.md",
        "community/wiki/note.md": ".omp/wiki/note.md",
        "config/project/secretary/journal/2026-08-01.md": ".omp/secretary/journal/2026-08-01.md",
        "work/project/audits/audit.json": ".omp/work/audits/audit.json",
        "runtime/project/verify-throttle.json": ".omp/state/verify-throttle.json",
    }
    for new, legacy in expected.items():
        assert (hq / new).exists(), f"missing {new}"
        assert sha256(hq / new) == sha256(anchor / legacy)
        assert (anchor / legacy).exists(), "legacy store must survive apply"
    assert not (hq / "config" / "project" / ".DS_Store").exists()


def test_apply_is_idempotent(anchor):
    assert run("apply", str(anchor)).returncode == 0
    second = run("apply", str(anchor))
    assert second.returncode == 0, second.stdout
    assert "same=7" in second.stdout


# --------------------------------------------------------------------------
# CONFLICT
# --------------------------------------------------------------------------

def test_conflict_refuses_to_overwrite_and_clears_when_resolved(anchor):
    assert run("apply", str(anchor)).returncode == 0
    target = anchor / ".hq" / "config" / "project" / "rules.json"
    before = target.read_text()
    target.write_text('{"version": 2}\n')

    bad = run("apply", str(anchor))
    assert bad.returncode == 4, bad.stdout
    assert "CONFLICT .omp/rules.json" in bad.stdout
    assert target.read_text() == '{"version": 2}\n', "conflict must not overwrite"

    target.write_text(before)
    assert run("apply", str(anchor)).returncode == 0


# --------------------------------------------------------------------------
# reverse — the rollback path, proved by round trip
# --------------------------------------------------------------------------

def test_reverse_round_trips_a_post_cutover_write(anchor, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    assert run("apply", str(anchor), home=home).returncode == 0
    new = anchor / ".hq" / "config" / "project" / "learned.md"
    new.write_text("written after the cutover\n")
    want = sha256(new)
    legacy = anchor / ".omp" / "learned.md"
    before = sha256(legacy)

    rev = run("reverse", str(anchor), home=home)
    assert rev.returncode == 0, rev.stdout + rev.stderr
    assert sha256(legacy) == want, "reverse must carry the new write back"

    # The overwritten bytes are recoverable, and land outside the store so the
    # backup itself never becomes an unmapped path.
    backups = list((home / ".claude" / "hq-reverse-backups").rglob("learned.md"))
    assert len(backups) == 1, rev.stdout
    assert sha256(backups[0]) == before
    assert not list((anchor / ".omp").glob("*.pre-reverse"))

    # new -> legacy -> new. The reverse left the legacy store modified, so the
    # dirty guard refuses to migrate forward until that rollback is committed —
    # which is the guard doing its job, not an obstacle to route around.
    new.unlink()
    blocked = run("apply", str(anchor), home=home)
    assert blocked.returncode == 3
    assert "dirty" in blocked.stderr

    git(anchor, "add", "-A")
    git(anchor, "commit", "-qm", "rollback")
    fwd = run("apply", str(anchor), home=home)
    assert fwd.returncode == 0, fwd.stdout + fwd.stderr
    assert sha256(new) == want


def test_reverse_carries_back_a_file_that_never_existed_in_legacy(anchor):
    assert run("apply", str(anchor)).returncode == 0
    born = write(anchor / ".hq" / "community" / "wiki" / "born-new.md", "new page\n")
    assert run("reverse", str(anchor)).returncode == 0
    assert sha256(anchor / ".omp" / "wiki" / "born-new.md") == sha256(born)


def test_reverse_leaves_store_owned_files_alone(anchor):
    assert run("apply", str(anchor)).returncode == 0
    write(anchor / ".hq" / "config" / "migrated.jsonl",
          json.dumps({"harness": "omp", "at": "2026-08-28T00:00:00+09:00", "machine": "t"}) + "\n")
    r = run("reverse", str(anchor))
    assert r.returncode == 0
    assert "SKIP   .hq/.anchor" in r.stdout
    assert "SKIP   .hq/config/migrated.jsonl" in r.stdout
    assert not (anchor / ".omp" / ".anchor").exists()


def test_reverse_dry_run_writes_nothing(anchor):
    assert run("apply", str(anchor)).returncode == 0
    (anchor / ".hq" / "config" / "project" / "learned.md").write_text("changed\n")
    env = dict(os.environ, MIGRATE_REVERSE_DRYRUN="1")
    r = subprocess.run(["bash", str(SCRIPT), "reverse", str(anchor)],
                       env=env, capture_output=True, text=True)
    assert r.returncode == 0
    assert "MERGE" in r.stdout
    assert (anchor / ".omp" / "learned.md").read_text() == "obs\n"


# --------------------------------------------------------------------------
# purge — never without a typed confirmation
# --------------------------------------------------------------------------

def test_purge_refuses_without_a_terminal(anchor):
    assert run("apply", str(anchor)).returncode == 0
    r = run("purge", str(anchor), "--store", ".omp")
    assert r.returncode == 3, r.stdout + r.stderr
    assert (anchor / ".omp" / "rules.json").exists(), "nothing may be removed"


def test_purge_refuses_a_piped_confirmation_even_when_it_is_correct(anchor):
    """A pipe is not a terminal. The confirmation is read from /dev/tty on
    purpose, so scripting the exact string still refuses."""
    assert run("apply", str(anchor)).returncode == 0
    p = subprocess.run(
        ["bash", str(SCRIPT), "purge", str(anchor), "--store", ".omp"],
        input=f"PURGE {anchor.name}/.omp\n", capture_output=True, text=True,
    )
    assert p.returncode == 3
    assert (anchor / ".omp" / "rules.json").exists()


def test_purge_needs_store_selection_when_the_anchor_holds_several(anchor):
    write(anchor / ".omha" / "routing.jsonl", "{}\n")
    r = run("purge", str(anchor))
    assert r.returncode == 3
    assert "one at a time" in r.stderr


# --------------------------------------------------------------------------
# gate — albc / omx are Phase 7
# --------------------------------------------------------------------------

def test_gated_anchor_is_named_not_silently_absent(tmp_path):
    a = tmp_path / "0_Project" / "albc"
    write(a / ".omx" / "programs" / "x.md", "campaign\n")
    r = run("plan", str(a))
    assert r.returncode == 3
    assert "gated" in r.stderr


# --------------------------------------------------------------------------
# census and drift are different instruments
# --------------------------------------------------------------------------

def test_census_matches_the_fixed_find_in_both_directions(tmp_path):
    write(tmp_path / "a" / ".omp" / "rules.json", "{}\n")
    write(tmp_path / "b" / "deep" / "deeper" / "even" / ".oms" / "learned.md", "x\n")
    write(tmp_path / "c" / ".claude" / "plugins" / "cache" / "x" / ".omha" / "r.jsonl", "{}\n")
    write(tmp_path / "d" / ".phase0-scratch" / "t" / ".orchestration" / "HUB.md", "#\n")

    r = run("census", "--root", str(tmp_path))
    assert r.returncode == 0, r.stderr
    listed = {ln.split()[0] for ln in r.stdout.splitlines() if ln.startswith(str(tmp_path))}

    found = subprocess.run(
        ["find", str(tmp_path), "-type", "d",
         "(", "-name", ".omp", "-o", "-name", ".oms", "-o", "-name", ".omd",
         "-o", "-name", ".omx", "-o", "-name", ".omha", "-o", "-name", ".orchestration", ")",
         "-not", "-path", "*/.git/*"],
        capture_output=True, text=True).stdout.split()
    in_scope = {str(Path(p).parent) for p in found
                if "/.claude/plugins/" not in p and "/.phase0-scratch/" not in p}

    assert listed == in_scope, f"census {listed} != find {in_scope}"
    assert "excluded by pattern: 2" in r.stdout


def test_census_does_not_list_a_store_nested_inside_another_store(tmp_path):
    """albc's `.omx/.omx` (store-spec §9.1 row 5) is a path *within* its parent's
    store, mapped as a row of that store's table — not an anchor. Listing it
    separately shows a phantom `legacy` store that no migration can ever clear,
    and the next round reads that as an un-migrated anchor. Added P7."""
    write(tmp_path / "p" / ".omx" / "registry" / "log.md", "# log\n")
    write(tmp_path / "p" / ".omx" / ".omx" / "registry" / "log.md", "# nested\n")

    r = run("census", "--root", str(tmp_path))
    assert r.returncode == 0, r.stderr
    listed = [ln.split()[0] for ln in r.stdout.splitlines() if ln.startswith(str(tmp_path))]
    assert listed == [str(tmp_path / "p")], listed
    assert str(tmp_path / "p" / ".omx") not in listed


def test_store_filter_does_not_narrow_reverse_sibling_awareness(tmp_path):
    """`--store` narrows what is PROCESSED; it must not narrow what `reverse`
    knows is present at the anchor.

    ANCHOR_KINDS was derived from the filtered store list, so a single-store
    `reverse` on an anchor that also holds another store labelled every file
    the sibling owns as ORPHAN. Nothing was lost — orphans are left in place —
    but a detector with 111 false positives (measured on albc, P7) cannot
    surface the one genuine orphan it exists to find."""
    write(tmp_path / ".omp" / "rules.json", "{}\n")
    write(tmp_path / ".orchestration" / "HUB.md", "# hub\n")
    write(tmp_path / ".orchestration" / "posts" / "finding" / "001-x.md", "# x\n")
    assert run("apply", str(tmp_path)).returncode == 0

    r = run("reverse", str(tmp_path), "--store", ".omp")
    assert r.returncode == 0, r.stderr
    assert "orphan=0" in r.stdout, r.stdout
    assert "ORPHAN" not in r.stdout, r.stdout


def test_drift_uses_the_ledger_not_the_census_find(anchor):
    """The two instruments must not share a command. Drift's discovery is the
    ledger: with no row for this harness it reports 'never cut over' rather
    than walking the tree, and census is what sees such an anchor.

    Both undefined cases exit **6, not 0** (P7). They were 0, and they said
    'never cut over' in prose while doing it — but an acceptance check written
    against `$?` reads 0 as 'verified clean', so a not-run check and a passed
    check shared an exit code. Same shape as finding/013."""
    silent = run("drift", str(anchor))
    assert silent.returncode == 6
    assert "no migrated.jsonl" in silent.stdout

    assert run("apply", str(anchor)).returncode == 0
    write(anchor / ".hq" / "config" / "migrated.jsonl",
          json.dumps({"harness": "oms", "at": "2026-08-28T00:00:00+09:00", "machine": "t"}) + "\n")
    wrong_row = run("drift", str(anchor))
    assert wrong_row.returncode == 6
    assert "no row for 'omp'" in wrong_row.stdout


def test_drift_detects_a_legacy_write_after_the_migration(anchor):
    assert run("apply", str(anchor)).returncode == 0
    at = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(time.time() - 60))
    write(anchor / ".hq" / "config" / "migrated.jsonl",
          json.dumps({"harness": "omp", "at": at, "machine": "t"}) + "\n")

    stale = run("drift", str(anchor))
    assert stale.returncode == 5, "fixture files are newer than the backdated ledger"

    future = time.time() + 3600
    for p in (anchor / ".omp").rglob("*"):
        if p.is_file():
            os.utime(p, (future - 7200, future - 7200))
    ahead = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(future))
    write(anchor / ".hq" / "config" / "migrated.jsonl",
          json.dumps({"harness": "omp", "at": ahead, "machine": "t"}) + "\n")
    assert run("drift", str(anchor)).returncode == 0

    os.utime(anchor / ".omp" / "learned.md", (future + 60, future + 60))
    split = run("drift", str(anchor))
    assert split.returncode == 5
    assert "SPLIT-BRAIN" in split.stdout
    assert ".omp/learned.md" in split.stdout


# --------------------------------------------------------------------------
# no-git anchors get a tar snapshot before anything is written (store-spec s8)
# --------------------------------------------------------------------------

def test_no_git_anchor_is_snapshotted_before_apply(tmp_path):
    a = tmp_path / "icloud"
    write(a / ".omd" / "learned.md", "obs\n")
    write(a / ".omd" / "deck" / "OUTLINE.md", "# deck\n")
    write(a / ".hq" / ".anchor", "id: fixture\n")
    home = tmp_path / "home"
    home.mkdir()

    r = run("apply", str(a), home=home)
    assert r.returncode == 0, r.stdout + r.stderr
    snaps = list((home / ".claude" / "hq-snapshots").glob("*.tar"))
    assert len(snaps) == 1, r.stdout
    assert "sha256" in r.stdout
    listing = subprocess.run(["tar", "-tf", str(snaps[0])], capture_output=True, text=True).stdout
    assert ".omd/learned.md" in listing


# --------------------------------------------------------------------------
# the ledger row `apply` owes stage 1, and the staging state it must announce
#
# Both are the same defect shape as the rest of this file: the tool's exit
# signal did not reach the next step. `apply` returned 0 without appending the
# row store-spec s7 stage 1 promises, so `drift` on a store migrated seconds
# earlier answered "this store was never cut over"; and a run that filled
# `community/wiki/` -- a staging state with one exit -- summarised as clean.
# --------------------------------------------------------------------------

def _ledger_rows(anchor: Path, kind: str = "omp"):
    p = anchor / ".hq" / "config" / "migrated.jsonl"
    if not p.exists():
        return []
    rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    return [r for r in rows if r.get("harness") == kind]


def _backdate_legacy(anchor: Path, store: str = ".omp"):
    """`at` has second resolution, so a legacy file written in the same second
    as the migration reads as newer than it. Real stores are not written during
    their own migration; the fixture is."""
    old = time.time() - 3600
    for p in (anchor / store).rglob("*"):
        if p.is_file():
            os.utime(p, (old, old))


def test_apply_appends_the_row_and_drift_stops_saying_never_cut_over(anchor):
    before = run("drift", str(anchor))
    assert before.returncode == 6, before.stdout
    assert "no migrated.jsonl" in before.stdout

    assert run("apply", str(anchor)).returncode == 0
    rows = _ledger_rows(anchor)
    assert len(rows) == 1, rows
    assert set(rows[0]) == {"harness", "at", "machine"}
    assert rows[0]["at"][-3] == ":", rows[0]["at"]      # +09:00, not +0900

    _backdate_legacy(anchor)
    after = run("drift", str(anchor))
    assert after.returncode == 0, after.stdout + after.stderr


def test_plan_appends_nothing(anchor):
    assert run("plan", str(anchor)).returncode == 0
    assert _ledger_rows(anchor) == []


def test_a_store_that_failed_to_map_appends_no_row(anchor):
    """The guard, discriminated: an unmapped file exits 2, and a store that did
    not fully land must not claim it was migrated."""
    stray = write(anchor / ".omp" / "stray.md", "unclaimed\n")
    git(anchor, "add", "-A")
    git(anchor, "commit", "-qm", "stray")
    assert run("apply", str(anchor)).returncode == 2
    assert _ledger_rows(anchor) == []

    stray.unlink()
    git(anchor, "add", "-A")
    git(anchor, "commit", "-qm", "drop stray")
    assert run("apply", str(anchor)).returncode == 0
    assert len(_ledger_rows(anchor)) == 1


def test_second_apply_advances_the_cut_line_rather_than_deduping(anchor):
    assert run("apply", str(anchor)).returncode == 0
    assert run("apply", str(anchor)).returncode == 0
    rows = _ledger_rows(anchor)
    assert len(rows) == 2, rows          # `drift` takes max(at); dedup freezes it


def test_machine_label_is_overridable_because_hostname_is_not_the_roster_name(anchor):
    env = dict(os.environ, HQ_MACHINE="roster-label")
    r = subprocess.run(["bash", str(SCRIPT), "apply", str(anchor)],
                       env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _ledger_rows(anchor)[0]["machine"] == "roster-label"


def test_wiki_pages_are_announced_as_staging_and_the_notice_is_not_inert(anchor):
    staged = run("plan", str(anchor))
    assert staged.returncode == 0
    assert "STAGING" in staged.stderr, staged.stderr
    assert "convert-wiki-form.py" in staged.stderr

    (anchor / ".omp" / "wiki" / "note.md").unlink()
    git(anchor, "add", "-A")
    git(anchor, "commit", "-qm", "drop wiki")
    quiet = run("plan", str(anchor))
    assert quiet.returncode == 0
    assert "STAGING" not in quiet.stderr

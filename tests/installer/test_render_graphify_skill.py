"""Tests for installer/scripts/render_graphify_skill.py.

The regression these pin down: graphify's CLI reads GRAPHIFY_OUT but its shipped
skill hardcodes `graphify-out` in 88 places, so with the variable set the two
halves of one tool look in different directories — and the skill's "graph already
exists, just query it" fast path keys on the file it can no longer find, turning
every invocation into a full rebuild. Rewriting on install is what keeps them
agreeing, so the rewrite and the frontmatter placement are the things worth
testing.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "installer" / "scripts"))

import render_graphify_skill as rgs

SKILL = """---
name: graphify
description: "Use when graphify-out/ exists."
---

# /graphify

Check whether `graphify-out/graph.json` exists.

```bash
mkdir -p graphify-out
graphify update . --graph graphify-out/graph.json
```
"""


class TestRewrite:
    def test_every_occurrence_is_replaced(self):
        out = rgs.rewrite(SKILL, ".graphify", "1.2.3")
        body = out.split("-->", 1)[1]  # ignore the banner, which names both dirs
        assert "graphify-out" not in body
        assert ".graphify/graph.json" in body
        assert "mkdir -p .graphify" in body

    def test_frontmatter_stays_on_line_one(self):
        # The skill loader reads frontmatter from the first line; a banner above
        # it would make the skill invisible.
        out = rgs.rewrite(SKILL, ".graphify", "1.2.3")
        assert out.startswith("---\nname: graphify")
        assert out.index("<!-- Generated") > out.index("\n---", 3)

    def test_banner_records_the_source_version(self):
        # Upgrading graphify does not refresh this file; the version is how a
        # human sees that the skill and the CLI have drifted apart.
        assert "graphify 9.9.9 skill.md" in rgs.rewrite(SKILL, ".graphify", "9.9.9")

    def test_default_out_dir_is_left_untouched(self):
        # Nothing to fix when the machine uses graphify's own default, so the
        # text must come back byte-identical (the installer symlinks instead).
        assert rgs.rewrite(SKILL, "graphify-out", "1.2.3") == SKILL

    def test_description_is_rewritten_too(self):
        # The description drives skill matching, so a stale path there would
        # advertise a directory the machine never creates.
        out = rgs.rewrite(SKILL, ".graphify", "1.2.3")
        assert 'description: "Use when .graphify/ exists."' in out


# `references/extraction-spec.md` — zero `graphify-out` occurrences against
# graphify 0.9.39, because the paths it names are substituted by the caller.
NO_OUT_DIR_REFERENCE = """# graphify reference: extraction subagent prompt

Each semantic subagent receives the prompt below verbatim.

```
Files (chunk CHUNK_NUM of TOTAL_CHUNKS):
FILE_LIST
Then write the JSON to CHUNK_PATH.
```
"""


class TestNoOpRewriteGetsNoBanner:
    """The banner must never reach a file graphify hashes as a cache key.

    graphify buckets its semantic cache by `prompt_fingerprint()`, a sha256
    over the whole text of `references/extraction-spec.md`. A banner carrying
    `{version}` therefore made every graphify upgrade look like a prompt
    change and orphaned the entire cache — ~10M tokens of re-extraction on the
    obsidian vault, 2026-08-11, for a version string.
    """

    def test_file_without_the_default_dir_comes_back_identical(self):
        assert rgs.rewrite(NO_OUT_DIR_REFERENCE, ".graphify", "1.2.3") == NO_OUT_DIR_REFERENCE

    def test_fingerprint_survives_a_version_bump(self):
        # THE regression, stated the way the cache sees it: two renders that
        # differ only in graphify version must be byte-identical, or the
        # bucket moves and the corpus is re-extracted at full LLM cost.
        assert rgs.rewrite(NO_OUT_DIR_REFERENCE, ".graphify", "0.9.38") == rgs.rewrite(
            NO_OUT_DIR_REFERENCE, ".graphify", "0.9.39"
        )

    def test_fingerprint_survives_a_different_graphify_out(self):
        # The cache is committed to git so a second machine restores it without
        # re-paying. A machine on the default GRAPHIFY_OUT took the early
        # return and got the pristine file; a `.graphify` machine got a banner.
        # Two buckets for one prompt means the shared cache never hits.
        assert rgs.rewrite(NO_OUT_DIR_REFERENCE, ".graphify", "1.2.3") == rgs.rewrite(
            NO_OUT_DIR_REFERENCE, "graphify-out", "1.2.3"
        )

    def test_a_file_that_does_mention_it_still_gets_the_banner(self):
        # The guard is "no rewrite happened", not "skip references" — a file
        # that really was rewritten still needs its do-not-edit warning.
        assert "<!-- Generated" in rgs.rewrite(REFERENCE, ".graphify", "1.2.3")


REFERENCE = """# graphify reference: incremental update

```bash
$(cat graphify-out/.graphify_python) -c "..."
```

Reads `graphify-out/graph.json`.
"""


def _pkg(tmp_path: Path) -> Path:
    """A graphify package laid out the way 0.9.38 actually ships it."""
    pkg = tmp_path / "site-packages" / "graphify"
    (pkg / "skills" / "claude" / "references").mkdir(parents=True)
    (pkg / "skill.md").write_text(SKILL, encoding="utf-8")
    (pkg / "skills" / "claude" / "references" / "update.md").write_text(REFERENCE, encoding="utf-8")
    return pkg


class TestFindReferences:
    def test_looks_under_skills_platform_not_beside_skill_md(self, tmp_path):
        # THE regression. skill.md sits at the package root while references are
        # per-platform under skills/<platform>/. Resolving the obvious
        # `skill.md.parent / "references"` yields a path that does not exist, so
        # the copy silently does nothing and Step 3 cannot load its own
        # extraction prompt.
        pkg = _pkg(tmp_path)
        assert not (pkg / "references").exists()
        assert rgs.find_references(pkg) == pkg / "skills" / "claude" / "references"

    def test_flat_layout_still_works(self, tmp_path):
        pkg = tmp_path / "graphify"
        (pkg / "references").mkdir(parents=True)
        assert rgs.find_references(pkg) == pkg / "references"

    def test_absent_returns_none(self, tmp_path):
        assert rgs.find_references(tmp_path) is None


class TestRenderReferences:
    def test_references_get_the_same_rewrite(self, tmp_path):
        # A reference that still says graphify-out is the same CLI-vs-skill split
        # the whole script exists to close — update.md alone carries 20 of them.
        pkg = _pkg(tmp_path)
        dst = tmp_path / "out" / "references"
        assert rgs.render_references(rgs.find_references(pkg), dst, ".graphify", "1.2.3", False) == 1
        body = (dst / "update.md").read_text(encoding="utf-8").split("-->", 1)[1]
        assert "graphify-out" not in body
        assert ".graphify/graph.json" in body

    def test_second_run_writes_nothing(self, tmp_path):
        # install.sh runs this every time; a re-render would break the
        # idempotency contract the smoke test asserts.
        pkg = _pkg(tmp_path)
        dst = tmp_path / "out" / "references"
        src = rgs.find_references(pkg)
        rgs.render_references(src, dst, ".graphify", "1.2.3", False)
        assert rgs.render_references(src, dst, ".graphify", "1.2.3", False) == 0

    def test_missing_source_is_not_an_error(self, tmp_path):
        # An older graphify shipped skill.md alone.
        assert rgs.render_references(tmp_path / "nope", tmp_path / "out", ".graphify", "1.2.3", False) == 0

    def test_dry_run_counts_without_writing(self, tmp_path):
        pkg = _pkg(tmp_path)
        dst = tmp_path / "out" / "references"
        assert rgs.render_references(rgs.find_references(pkg), dst, ".graphify", "1.2.3", True) == 1
        assert not (dst / "update.md").exists()


class TestInsertAfterFrontmatter:
    def test_no_frontmatter_puts_banner_first(self):
        assert rgs.insert_after_frontmatter("# Title\n", "BANNER\n") == "BANNER\n# Title\n"

    def test_unterminated_frontmatter_falls_back_to_prepending(self):
        # Malformed input must not silently lose the banner or corrupt the file.
        text = "---\nname: x\n"
        assert rgs.insert_after_frontmatter(text, "BANNER\n").startswith("BANNER\n")

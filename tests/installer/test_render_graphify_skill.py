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


class TestInsertAfterFrontmatter:
    def test_no_frontmatter_puts_banner_first(self):
        assert rgs.insert_after_frontmatter("# Title\n", "BANNER\n") == "BANNER\n# Title\n"

    def test_unterminated_frontmatter_falls_back_to_prepending(self):
        # Malformed input must not silently lose the banner or corrupt the file.
        text = "---\nname: x\n"
        assert rgs.insert_after_frontmatter(text, "BANNER\n").startswith("BANNER\n")

#!/usr/bin/env python3
"""Merge a hook fragment into a project-scope .claude/settings.json.

Idempotent: detects existing installations via a marker string in the command
field and replaces them in place. Preserves all other hooks and settings.

Usage:
    merge-project-hook.py <fragment.json> <target-settings.json> <marker>

Exit codes:
    0 = success (merged, replaced, or already up-to-date)
    1 = error (target missing, malformed JSON, fragment invalid)
    2 = target directory doesn't exist (caller should skip silently)

Known limitation (M7, filed 2026-05-29): one fragment file = one marker = one
event. If multiple distinct hooks ever need to land in the same project at
once, extend the fragment schema to a list of (marker, event, command) tuples
and lift the duplicate-marker check below from "raise" to "iterate". Not done
now because the only current consumer is OMC_REFERENCE_AUTO_LOAD; building
a more general merger before a second consumer exists would be speculative.
"""

import json
import sys
from collections import Counter
from pathlib import Path

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent))
import hooklog  # noqa: E402


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text()
    if not text.strip():
        return {}
    return json.loads(text)


def find_marker_index(hooks_list: list, marker: str) -> int:
    """Return index of first hook entry containing the marker, or -1."""
    for i, entry in enumerate(hooks_list):
        for hook in entry.get("hooks", []):
            if marker in hook.get("command", ""):
                return i
    return -1


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__, file=sys.stderr)
        return 1

    fragment_path = Path(sys.argv[1])
    target_path = Path(sys.argv[2])
    marker = sys.argv[3]

    if not target_path.parent.exists():
        return 2

    if not fragment_path.exists():
        print(f"error: fragment not found: {fragment_path}", file=sys.stderr)
        return 1

    fragment = load_json(fragment_path)
    fragment.pop("_comment", None)

    target = load_json(target_path)
    target.setdefault("hooks", {})

    changed = False
    for event_name, new_entries in fragment.items():
        existing = target["hooks"].setdefault(event_name, [])
        if not isinstance(new_entries, list) or not new_entries:
            continue

        # Assert no duplicate markers in this fragment event — idempotency
        # requires each marker to appear at most once per event.
        frag_markers = [
            hook.get("command", "")
            for e in new_entries
            for hook in e.get("hooks", [])
            if marker in hook.get("command", "")
        ]
        dup_counts = [cmd for cmd, c in Counter(frag_markers).items() if c > 1]
        if dup_counts:
            raise ValueError(
                f"fragment.json has duplicate markers for event '{event_name}', "
                f"not yet supported: {dup_counts}"
            )

        for new_entry in new_entries:
            idx = find_marker_index(existing, marker)
            if idx >= 0:
                if existing[idx] != new_entry:
                    existing[idx] = new_entry
                    changed = True
            else:
                existing.append(new_entry)
                changed = True

    if not changed:
        print(f"unchanged: {target_path}")
        hooklog.fire("merge_project_hook.jsonl", None, None, merged=False)
        return 0

    target_path.write_text(json.dumps(target, indent=2) + "\n")
    print(f"merged: {target_path}")
    hooklog.fire("merge_project_hook.jsonl", None, None, merged=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

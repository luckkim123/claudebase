#!/usr/bin/env python3
"""Check every om loop skill against docs/loop-contract.md — evidence, no verdicts.

    python3 runtime/hooks/loop_lint.py
    python3 runtime/hooks/loop_lint.py --root ~/ksm_Obsidian --root ~/claudebase
    python3 runtime/hooks/loop_lint.py --source     # lint the git checkouts instead

MANUAL diagnostic — NOT wired into any hook, so it costs nothing per turn.
Read-only: it never writes or deletes anything. Sibling of `harness_stats.py`,
which counts whether guards fire; this one asks whether the loops that fire are
built to a shared contract.

Two tables, and the trap each carries:

  [A] Contract compliance per loop skill. Eight columns for the seven contract
      items — two of them split in two because the half-failure is the common
      one: a numeric cap with no named escalation (cap/escal), and a residue
      count with no denominator to read the zero against (resid/denom). Every
      hit prints the matched LINE, because a boolean table out of a keyword
      matcher is exactly the artifact that looks clean while being wrong. The
      line is what lets a reader overrule the match: a `3 times` inside a
      `<Bad>` example scores the same as a rule, and only the text tells them
      apart.

      Reads the INSTALLED PLUGIN CACHE by default, not the git checkout — the
      cache is what actually runs. omha's `route_log.py` was correct in git and
      absent from the loaded cache for a week while its log stayed empty.

      Follows the compact-skill shim. omc/oms/omd register a ~12-line
      `skills/<n>/SKILL.md` pointing at `skill-bodies/<n>/SKILL.md`; reading
      only the registered file scores every one of those loops as failing all
      five checks, and reports no error doing it.

      The `activity` count is generous on purpose and must be read with its
      evidence line. It globs every path literal the skill names, including the
      ones named to say "that belongs to another stage" — omp-garden's row
      counts `.omp/STRUCTURE.md` because its Do_Not_Use_When routes there. The
      printed example path is what tells a reader whether the count is the
      loop's own state or a neighbour's.

  [B] Enforcement surface — which hook can actually block, per plugin. This is
      the "which transitions live only in prose" question in its only
      answerable form: a transition can be enforced only where a hook event
      exists, so the inventory of blocking-capable hooks IS the inventory of
      enforceable transitions. Everything else in a SKILL.md is prose.

      Blind spot, stated rather than hidden: omc's hooks shell out to
      `scripts/*.mjs` that delegate to compiled `dist/`. A grep of the named
      script can miss a gate implemented one file deeper — ralph's
      anti-self-approval Stop gate is exactly that shape. `no` in the `blocks?`
      column means "not visible here", never "not enforced".
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

_INSTALLED = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
_SOURCE_ROOTS = [Path.home() / "oh-my-heroacademia", Path.home()]

# The signal used to enumerate the loops, narrowed to om* plugins so that
# `marketing-skills/marketing-loops` stops showing up as one of ours.
# `garden` is here because omp-garden (0.12.0) is a loop whose name says nothing
# about looping — a periodic sweep with a state file and an escalation cap. A
# name-shaped discovery rule silently omits exactly those, and the omission looks
# like a clean table.
_LOOP_NAME_RE = re.compile(
    r"loop|revise|ralph|autopilot|ultraqa|ultrawork|ultragoal|garden", re.I)

# ─── contract checks ────────────────────────────────────────────────────────
# Each is a keyword probe, not a semantic judgement. See the module docstring.

_STATE_RE = re.compile(
    r"\.om[a-z]{1,2}/\S*\.(?:json|jsonl|txt|md)"   # .omc/state/…/prd.json
    r"|\bprogress\.txt\b"
    r"|[\w-]+-state\.md"
    r"|\bstate_(?:write|read)\b"
    r"|\bledger\b", re.I)

# `(?-i:PASS)` — the verdict token is uppercase, the English verb is not. Under a
# plain case-insensitive \bPASS\b this matched "Always pass the model parameter"
# and "Pass it to exp-analyze", crediting three loops with a deterministic stop
# condition they do not state.
_STOP_RE = re.compile(
    r"passes\s*[:=]\s*true"
    r"|(?-i:PASS)\b"
    r"|\btests?\b[^.\n]{0,20}\bpass(?:es|ed)?\b"
    r"|\brc\s*[12]\b|exit\s*(?:code\s*)?[12]\b"
    r"|deadline_passed"
    r"|no new (?:findings|items|results)"
    r"|\"decision\"|loop-health", re.I)

# Not a failure — a note. Ralph carries this phrasing inside a <Bad> example,
# which is the clearest possible demonstration of why evidence gets printed.
_SOFT_RE = re.compile(
    r"looks? good|seems (?:fine|done|good|ok)|do your best"
    r"|when you (?:think|feel)|if satisfied", re.I)

_CAP_RE = re.compile(
    r"\b\d+\s*\+?\s*(?:회|번|times|rounds?|sweeps?|iterations?|attempts?|blocked stops)"
    r"|\{\{MAX\}\}"
    r"|max[_-]?(?:runtime|iterations?|rounds?)"
    r"|hard\s*cap", re.I)

# `stops? and reports?`, not `stop and report`: scholar-revise's only escalation
# sentence is "Stops and reports if the same defect recurs 3 times", and the
# singular-only form missed it while the table still looked complete.
_ESC_RE = re.compile(
    r"stops? and reports?|STOP for (?:the )?human|escalat|ask the user"
    r"|report it as|사람에게|중단하고 보고", re.I)

_VERIF_RE = re.compile(
    r"subagent_type|(?:doc|scholar)-verifier|\bcritic\b|\barchitect\b"
    r"|\breviewer\b|\bverifier\b|omx eval|campaign-auditor", re.I)

# Contract item 6, added 2026-08-24 — the loop stops because a COUNT in its state
# said to, not because it concluded it had finished. `no new findings` is
# omp-garden's phrasing and `open_leads` is omx's; both were in the stack before
# the contract named the property.
_RESID_RE = re.compile(
    r"no new findings|open[_ ]leads|remaining (?:defects?|items?|findings?|work)"
    r"|unresolved|read from state|not judged"
    r"|잔여|미해결", re.I)

# The other half, and the one nearly everything fails. A residue count of 0 is
# worthless unless the denominator travels with it: omx's own docstring records a
# workspace where 0 of 540 pages carried any status, so every launch that round
# passed a gate that had never held anything. Kept deliberately tight — a loose
# match here would turn the column into decoration.
_DENOM_RE = re.compile(
    r"wiki_coverage|denominator|with_status"
    r"|\bout of \d+|\b\d+ of \d+\b"
    r"|분모", re.I)

# Contract item 7, added 2026-08-24 — the loop consults what earlier runs learned
# BEFORE acting, instead of re-deriving it. A READ verb is required: every one of
# these stores is also written by something, and writing a lesson is not
# reactivating one. exp-loop's step 6 (`wiki capture-session`, `wiki lint`,
# `wiki gc`) is the write half and deliberately does not match here.
_LESSON_RE = re.compile(
    r"wiki[ _](?:query|read|list)|learned\.md"
    r"|prior (?:evidence|diagnos|cause)|already diagnosed"
    r"|from earlier (?:runs?|executions?)|past (?:lesson|diagnos)"
    r"|이전 교훈|과거 실행", re.I)

_CHECKS = [
    ("state", _STATE_RE),
    ("stop", _STOP_RE),
    ("cap", _CAP_RE),
    ("escal", _ESC_RE),
    ("verif", _VERIF_RE),
    ("resid", _RESID_RE),
    ("denom", _DENOM_RE),
    ("lesson", _LESSON_RE),
]

# A path literal that could be loop state. Excludes the documents every skill
# mentions in passing, which would otherwise make every loop look stateful.
_PATHLIT_RE = re.compile(r"[\w.{}<>*/-]*\.(?:json|jsonl|txt|md)\b")
_NOT_STATE = re.compile(r"SKILL\.md|README|CHANGELOG|report\.md|\.claude-plugin",
                        re.I)

_BLOCK_RE = re.compile(
    r"permissionDecision|[\"']deny[\"']|[\"']block[\"']"
    r"|(?:sys|process)?\.?exit\(\s*2\s*\)", re.I)


# ─── discovery ──────────────────────────────────────────────────────────────

def installed_plugins() -> dict:
    """{plugin name: install path} for om* plugins, from the host's own record.

    Reads `installed_plugins.json` rather than globbing the cache: the cache
    keeps every version ever downloaded (34 omha directories on this machine),
    and the newest one on disk is not necessarily the one loaded."""
    try:
        data = json.loads(_INSTALLED.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out = {}
    for key, entries in (data.get("plugins") or {}).items():
        name = key.split("@")[0]
        if not name.startswith("oh-my-") or not entries:
            continue
        path = Path(entries[0].get("installPath", ""))
        if path.is_dir():
            out[name] = path
    return dict(sorted(out.items()))


def source_plugins() -> dict:
    """{plugin name: repo path} — the git checkouts, for --source."""
    out = {}
    for parent in _SOURCE_ROOTS:
        for path in sorted(parent.glob("oh-my-*")):
            if (path / ".claude-plugin").is_dir() and path.name not in out:
                out[path.name] = path
    return out


def skill_text(plugin_root: Path, name: str) -> tuple:
    """(text, [paths read]) — shim and body concatenated.

    Both are live at runtime: the shim's frontmatter is what the catalog shows
    and the body is what the model reads on invocation. scholar-revise states
    its cap ("recurs 3 times") only in the shim description."""
    parts, paths = [], []
    for candidate in (plugin_root / "skills" / name / "SKILL.md",
                      plugin_root / "skill-bodies" / name / "SKILL.md"):
        if candidate.is_file():
            try:
                parts.append(candidate.read_text(encoding="utf-8", errors="replace"))
                paths.append(candidate)
            except OSError:
                continue
    return "\n".join(parts), paths


def loop_skills(plugins: dict) -> list:
    """[(plugin, skill, text, paths)] for every loop-shaped skill."""
    out = []
    for plugin, root in plugins.items():
        skills_dir = root / "skills"
        if not skills_dir.is_dir():
            continue
        for entry in sorted(skills_dir.iterdir()):
            if not entry.is_dir() or not _LOOP_NAME_RE.search(entry.name):
                continue
            text, paths = skill_text(root, entry.name)
            if text:
                out.append((plugin, entry.name, text, paths))
    return out


# ─── table A ────────────────────────────────────────────────────────────────

def first_hit(text: str, rx) -> tuple:
    """(line number, trimmed line) of the first match, or (None, "")."""
    for n, line in enumerate(text.splitlines(), 1):
        if rx.search(line):
            return n, " ".join(line.split())[:110]
    return None, ""


def state_paths(text: str) -> list:
    """Path literals from the skill, wildcarded, for the activity check.

    `{sessionId}` and `<run_id>` become `*` so the placeholder the skill writes
    matches the directory the loop actually created."""
    out = []
    for raw in _PATHLIT_RE.findall(text):
        if "/" not in raw and raw != "progress.txt":
            continue
        if _NOT_STATE.search(raw):
            continue
        # A literal '*' in the prose is a glob the skill is documenting, not a
        # path it writes. omp-garden names its own default sweep set (`docs/*.md`)
        # and scored 26 "activity" hits off claudebase's docs directory — a live
        # loop invented out of a sentence about globs.
        if "*" in raw:
            continue
        pattern = re.sub(r"\{[^}]*\}|<[^>]*>", "*", raw).lstrip("/")
        if pattern and pattern not in out:
            out.append(pattern)
    return out


def activity(patterns, roots) -> tuple:
    """(match count, newest mtime, example path) across roots.

    Falls back to `**/<basename>` when the literal pattern misses, because a
    loop's state often lands under an output tree rather than the project root
    (omx writes `runs/<id>/pending-launch.json` under the profile's output
    root). Without the fallback a live loop reads as scaffolding."""
    hits, newest, example = 0, None, ""
    for root in roots:
        base = Path(root)
        if not base.is_dir():
            continue
        for pattern in patterns:
            try:
                found = list(base.glob(pattern))
                name = Path(pattern).name
                if not found and "*" not in name:
                    found = list(base.glob(f"**/{name}"))
            except (OSError, ValueError):
                continue
            for path in found:
                if "/.git/" in str(path):
                    continue
                hits += 1
                try:
                    mtime = path.stat().st_mtime
                except OSError:
                    continue
                if newest is None or mtime > newest:
                    newest, example = mtime, str(path)
    return hits, newest, example


# ─── table B ────────────────────────────────────────────────────────────────

def hook_entries(plugin_root: Path) -> list:
    """[(event, script path or None, raw command)] from either manifest shape.

    heroacademia plugins declare hooks inline in `.claude-plugin/plugin.json`
    with `command` + `args`; omc ships `hooks/hooks.json` with the whole
    invocation in `command`. Handling only one shape silently reports the other
    plugin as having no hooks at all."""
    manifests = []
    for path in (plugin_root / ".claude-plugin" / "plugin.json",
                 plugin_root / "hooks" / "hooks.json"):
        try:
            manifests.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue

    out = []
    for manifest in manifests:
        for event, groups in (manifest.get("hooks") or {}).items():
            for group in groups if isinstance(groups, list) else []:
                for hook in group.get("hooks", []) if isinstance(group, dict) else []:
                    if not isinstance(hook, dict):
                        continue
                    tokens = [hook.get("command", "")] + list(hook.get("args") or [])
                    raw = " ".join(t for t in tokens if t)
                    script = None
                    for token in reversed(raw.split()):
                        # Quotes sit INSIDE the token, not only at its ends —
                        # omc writes `node "$CLAUDE_PLUGIN_ROOT"/scripts/x.mjs`,
                        # so stripping the ends leaves a stray quote mid-path and
                        # every omc hook resolves to nothing but reports '?'.
                        token = token.replace('"', "").replace("'", "")
                        if token.endswith((".py", ".mjs", ".cjs", ".js", ".sh")):
                            rel = re.sub(r"\$\{?CLAUDE_PLUGIN_ROOT\}?/?", "", token)
                            candidate = plugin_root / rel
                            script = candidate if candidate.is_file() else None
                            break
                    out.append((event, script, raw))
    return out


def blocks(script) -> str:
    """'yes' / 'via' / 'no' / '?' — whether this hook can deny a tool call.

    `via` means the named script is a dispatcher and the blocking code lives in a
    sibling module. omx wires every event to one `run_hook.py`, which loads
    `handlers.py` through `importlib` — and `handlers.py:556` returns
    `{"decision": "block"}`. Grepping only the named file reports the one loop
    plugin with a real Stop gate as having none.

    The dispatcher test is deliberately narrow. Widening it to "any sibling
    blocks" would flip `oh-my-docs` to `via`, when `docs_stop_guard.py:6` states
    outright that it never blocks — a wrong row in place of a right one."""
    if script is None:
        return "?"
    try:
        text = script.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "?"
    if _BLOCK_RE.search(text):
        return "yes"
    if not re.search(r"importlib|__import__", text):
        return "no"
    for sibling in sorted(script.parent.glob("*.py")):
        if sibling == script:
            continue
        try:
            if _BLOCK_RE.search(sibling.read_text(encoding="utf-8", errors="replace")):
                return "via"
        except OSError:
            continue
    return "no"


# ─── output ─────────────────────────────────────────────────────────────────

def _stamp(mtime) -> str:
    if not mtime:
        return "-"
    import datetime
    return datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")


def report(roots, use_source: bool = False) -> str:
    plugins = source_plugins() if use_source else installed_plugins()
    loops = loop_skills(plugins)

    L = []
    add = L.append
    add("=" * 74)
    add(f"loop contract — {'source checkouts' if use_source else 'installed cache'}")
    add(f"roots: {', '.join(str(r) for r in roots)}")
    add("=" * 74)

    add("")
    add("[A] contract compliance   (docs/loop-contract.md; every hit prints evidence)")
    if not loops:
        add("    (no loop-shaped skills found — is any om* plugin installed?)")
    add(f"    {'plugin/skill':32s} " + " ".join(f"{n:>5s}" for n, _ in _CHECKS)
        + "   activity")

    detail = []
    for plugin, skill, text, paths in loops:
        cells, evidence = [], []
        for name, rx in _CHECKS:
            line_no, line = first_hit(text, rx)
            cells.append("ok" if line_no else "--")
            if line_no:
                evidence.append(f"        {name:6s} L{line_no:<4d} {line}")
        hits, newest, example = activity(state_paths(text), roots)
        act = f"{hits:3d} @ {_stamp(newest)}" if hits else "  0 (none found)"
        label = plugin.replace("oh-my-", "om:") + "/" + skill
        add(f"    {label:32s} " + " ".join(f"{c:>5s}" for c in cells) + f"   {act}")

        soft_no, soft_line = first_hit(text, _SOFT_RE)
        block = [f"    {plugin}/{skill}",
                 # parents[1] is skills/ or skill-bodies/ — the parent dir is the
                 # skill name for both, so printing it cannot show whether the
                 # shim's body was actually reached.
                 f"        read   {', '.join(p.parents[1].name + '/' + p.name for p in paths)}"]
        block += evidence
        if example:
            block.append(f"        activity     {example}")
        if soft_no:
            block.append(f"        NOTE model-confidence phrasing L{soft_no}: {soft_line}")
        detail.append("\n".join(block))

    add("")
    add("    evidence")
    for block in detail:
        add(block)

    add("")
    add("[B] enforcement surface   (a transition is enforceable only at a hook)")
    add(f"    {'plugin':22s} {'event':18s} {'script':30s} blocks?")
    loop_plugins = {p for p, _, _, _ in loops}
    unguarded = []
    for plugin, root in plugins.items():
        entries = hook_entries(root)
        if not entries:
            add(f"    {plugin:22s} (no hooks declared)")
            if plugin in loop_plugins:
                unguarded.append(plugin)
            continue
        stop_blocking = False
        for event, script, raw in entries:
            verdict = blocks(script)
            name = script.name if script else (raw.split() or ["?"])[0][:28]
            add(f"    {plugin:22s} {event:18s} {name:30s} {verdict}")
            if event in ("Stop", "SubagentStop") and verdict in ("yes", "via"):
                stop_blocking = True
        if plugin in loop_plugins and not stop_blocking:
            unguarded.append(plugin)

    add("")
    # NOT a defect list — audited 2026-08-24 and both entries had a stated
    # reason. omd forbids `decision: block` plugin-wide (D6, recorded in three
    # release plans; all six of its hooks honour it) and instruments the same
    # transition advisorily with a `.verify-pending` sentinel. omp-garden is
    # report-only and ships no scheduler, so one sweep IS one turn and there is
    # no in-session transition for a Stop hook to hold open.
    add("    loop-carrying plugins with no blocking Stop hook visible —")
    add("    read as a fact, not a verdict: absent, compiled out of view, or")
    add("    declined by a recorded decision (check the plugin before filing it):")
    add("      " + (", ".join(unguarded) if unguarded else "(none)"))
    add("")
    return "\n".join(L)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--root", action="append", default=None,
                        help="project root to search for loop state "
                             "(repeatable; default: cwd)")
    parser.add_argument("--source", action="store_true",
                        help="lint the git checkouts instead of the installed "
                             "cache (what you would fix, not what runs)")
    args = parser.parse_args(argv)
    roots = [os.path.expanduser(r) for r in (args.root or ["."])]
    print(report(roots, use_source=args.source))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

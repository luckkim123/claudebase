# P4 backlog — CLAUDE.md hardening

Items deferred from P1 to P4 (CLAUDE.md cleanup + optional `rules/` split).

## L6 — CLAUDE.md hardcoded paths

`config/CLAUDE.md` references `~/claude-settings/...` literally in two places (lines 234 and 286 at time of filing). Skill docs under `runtime/skills/` (omc-teams-ops, sync-claude-settings, gen-image) also use the literal path — these are intentional (user-facing prose; explicit path is clearer than a variable).

**Resolution path**: when the local folder is eventually renamed `~/claude-settings` → `~/claudebase`, a single repo-wide find+sed pass:

```bash
grep -rln '~/claude-settings' config/ runtime/ docs/ \
  | xargs sed -i '' 's|~/claude-settings|~/claudebase|g'
```

Do not introduce a `$CLAUDEBASE_DIR` placeholder in prose — readers prefer the literal path. The variable, if needed, belongs to `installer/install.sh` alone.

## `rules/` split investigation

**DECIDED 2026-05-29: do NOT split.** Full rationale + revisit conditions in
[`2026-05-29-claude-md-rules-split-decision.md`](2026-05-29-claude-md-rules-split-decision.md).

TL;DR: Claude Code loads CLAUDE.md whole (zero token saving), 285 LOC is below
the edit-locality threshold (~600 LOC), and each `@include` adds a fail-silent
dependency — exactly the bug pattern P4 just removed (`@CLAUDE-omc.md`).

## P1 → P4 handoff verified

- G1.1 routing-verdict-reminder.py removed.
- G1.2 ($CLAUDEBASE_DIR introduction) **skipped** during P1 execution: install.sh already uses `$REPO_DIR` internally, and all other `~/claude-settings` references are user-facing prose. ROI assessed as zero on 2026-05-29 baseline check.
- L6 (this item) remains the only CLAUDE.md-path deferral.

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

Decide whether to keep `config/CLAUDE.md` as a single ~290-LOC file or split into `config/CLAUDE.md` + `config/rules/*.md` with `@include` directives.

Considerations:
- Current file is well-sectioned (Behavioral Principles, Operational Limits, Workflow, OMC Orchestration, Versioned Release Workflow, Environment Variables) — modularity already present at the section level.
- Karpathy-style modularity argues for split when sections are loaded selectively. Claude Code loads CLAUDE.md whole — split has no token-saving benefit.
- Split helps when *editing*: separate concerns map to separate PRs. Argues for split.
- Decision deferred until P4 spec.

## P1 → P4 handoff verified

- G1.1 routing-verdict-reminder.py removed.
- G1.2 ($CLAUDEBASE_DIR introduction) **skipped** during P1 execution: install.sh already uses `$REPO_DIR` internally, and all other `~/claude-settings` references are user-facing prose. ROI assessed as zero on 2026-05-29 baseline check.
- L6 (this item) remains the only CLAUDE.md-path deferral.

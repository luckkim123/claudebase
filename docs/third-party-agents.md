# Third-party agents

Every `.md` in this directory is vendored from **Everything Claude Code**
([github.com/affaan-m/ECC](https://github.com/affaan-m/ECC)), MIT licensed,
Copyright (c) 2026 Affaan Mustafa. The upstream `LICENSE` text applies; this
file is the attribution notice it requires.

Eight of ECC's 67 agents are here. The other 59 were read and rejected — 34 are
a language x {review, build-fix} matrix for languages nobody writes here, and
the rest duplicate an OMC agent, a superpowers skill, or a sibling harness.

## What is here, and why

| Agent | Kept because |
|:---|:---|
| `cpp-reviewer` | Memory safety, raw new/delete, use-after-free, data races — the defect classes that cost a field test on Arduino/ROS firmware |
| `pytorch-build-resolver` | Tensor shape, device placement, CUDA/cuDNN, AMP. The cuDNN-preamble miss that ran TCN distill at 18.9 s/iter against a 0.21 s/iter normal is this lane |
| `python-reviewer` | Half its checklist is web-flavoured and will not fire here; kept because `mle-reviewer` dispatches it and the error-handling and typing sections do apply |
| `mle-reviewer` | Reproducibility, promotion gates that fail closed, and train/serve equivalence. **Locally edited** — see below |
| `conversation-analyzer` | Mines a transcript for corrections and repeated mistakes and proposes hooks. That is how every hook in `runtime/hooks/` was found, by hand |
| `opensource-forker` | Stages a private tree for release: strips secrets, rewrites internal domains/paths/IPs to placeholders, generates `.env.example`, fresh git history |
| `opensource-sanitizer` | Independent read-only auditor that does not trust the forker and **scans git history**, not just the worktree. PASS/FAIL only |
| `opensource-packager` | Generates `CLAUDE.md`, `setup.sh`, README, LICENSE, CONTRIBUTING for a release |

## Local edits

Re-syncing from upstream would silently revert these. Do not copy a fresh file
over one of them without re-applying the edit.

- **All files** — a provenance HTML comment inserted after the frontmatter.
- **`mle-reviewer.md`, `## Reuse Existing Review Lanes`** — rewritten. Upstream
  dispatched twelve sibling ECC agents by name; ten of them are not installed
  here, and a dispatch to a name that does not exist reads exactly like a lane
  that ran and found nothing. Re-pointed at `oh-my-claudecode:*` equivalents,
  plus `oh-my-project` for the data-contract/leakage section and
  `oh-my-experiments` for evaluation/promotion, since those two harnesses
  already own that state. `database-reviewer`, `performance-optimizer`,
  `silent-failure-hunter` and `a11y-architect` were dropped with reasons stated
  in the file.

## Upstream drift

Pinned to the ECC tree as of 2026-08-10. There is no update path wired and that
is deliberate: these are checklists, not code, and an unreviewed refresh would
re-introduce the dangling dispatches above. To refresh, diff the upstream file
against ours and re-apply the local edits by hand.

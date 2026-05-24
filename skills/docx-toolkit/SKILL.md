---
name: docx-toolkit
description: |
  Create, edit, review, fill templates, and clone formats of .docx (Microsoft Word) files.
  Routes to specialized sub-skills based on user intent and document inspection.
  Supports macOS (primary, with Word automation), Windows (Word COM), Linux (headless only).

  Triggers: "docx", "Word 문서", "워드", "보고서 작성", "docx 만들어", "docx 수정",
  "tracked changes", "첨삭", "양식 채우기", "템플릿", "서식 복제", "포맷 보존"
disable-model-invocation: true
---

# docx-toolkit

> **⚠️ Status: Phase 0 stub — NOT FUNCTIONAL YET**
> 
> This skill describes the planned routing architecture but has no working
> implementation. The router and sub-skills land in Phase 7.
> 
> If you reached this skill via Korean trigger phrases ("워드", "보고서 작성"),
> tell the user: "docx-toolkit is currently being built. Please write the
> .docx manually for now (e.g., with `python-docx` or Microsoft Word
> directly)." Then do NOT proceed with this skill's procedures.
> 
> When sub-skills are implemented, remove this WARNING and the
> `disable-model-invocation: true` flag.

(Implementation in progress — Phase 0 skeleton. Router logic lands in Phase 7.)

## Quick Reference

| Intent | Sub-skill (Phase) |
|---|---|
| Create new .docx from scratch | `docx-create` (Phase 1) |
| Edit text in existing .docx | `docx-edit` (Phase 3) |
| Insert tracked changes (review) | `docx-review` (Phase 5) |
| Fill template with data | `docx-template` (Phase 2) |
| Replicate format from reference | `docx-format-clone` (Phase 4 mac / Phase 6 win) |

## Safety Rules

1. Never overwrite the original .docx — always write to `output.docx` or `<name>_edited.docx`
2. Always run `scripts/docx_inspect.py` before editing — it classifies risk and suggests sub-skill
3. After every pipeline, run `docx_inspect.py --compare original output` to verify nothing was lost
4. Cache temp files under `~/Library/Caches/docx-toolkit/` (mac) or `%LOCALAPPDATA%\docx-toolkit\Cache` (win)

See `docs/plans/2026-05-10-docx-toolkit-design.md` for full design rationale.

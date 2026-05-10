---
name: hancom-fill
description: Use when the user wants to fill an existing Korean Hancom .hwpx form/template with content from a markdown file or direct instructions. Triggers on "한글 양식", "hwpx 채워", "보고서 양식 채워", "양식에 내용 넣어", ".hwpx 양식". Preserves the original form's styling and structure. v0.1 supports cell text replacement only — no row addition, no caching, no .hwp binary, no chart/equation editing.
---

# hancom-fill

Fill an existing Korean Hancom `.hwpx` form using either a markdown content
file or direct user instructions.

## Scope (v0.1)

✅ Supported
- Reading `.hwpx` (zip + XML) forms
- Detecting empty cells in tables (whitespace-only `<hp:t>`)
- Replacing cell text with provided values
- Atomic write with `.bak` backup of the source
- Structural validation (zip + required files + XML well-formed)

❌ Not in v0.1
- Adding rows to a table
- Filling free-form paragraph areas
- Caching slot mappings across forms
- `.hwp` (binary) format
- Charts, equations, multi-column layouts
- Generating new `.hwpx` from scratch (use a different skill)

## Workflow (Claude must follow this order)

### Step 1 — Extract slots

```bash
python3 ~/.claude/skills/hancom-fill/scripts/extract.py <form.hwpx> -o /tmp/slots.json
```

Read `/tmp/slots.json`. Each entry has `id`, `kind` (always `"cell"` in v0.1),
`label` (text of the left-neighbor cell), `xpath`, `context`.

### Step 2 — Build plan.json

For each empty slot, decide what to fill it with:

- If a `content.md` is provided → match slot labels (e.g. "성명", "Name") to
  md fields/sections.
- If the user gave direct instructions → match instructions to slot labels.
- If a slot has no obvious source → leave it OUT of the plan and ask the user.

Plan format: array of `{slot_id, value}` objects (see
`templates/plan_schema.json`).

### Step 3 — Show the plan to the user

Before writing, show the user:
- Which slots are mapped (label → value)
- Which slots are unmapped and need their input
Get explicit approval, then proceed.

### Step 4 — Fill and validate

```bash
python3 ~/.claude/skills/hancom-fill/scripts/fill.py \
    <form.hwpx> /tmp/plan.json -o <output.hwpx>
```

`fill.py` runs validation automatically. On validation failure, the output
file is removed and the script exits with code 2 — surface that error to the
user. The original form is preserved as `<form.hwpx>.bak`.

## Hard rules

- **NEVER** edit `.hwpx` XML directly from Claude. Always go through these scripts.
- **NEVER** overwrite the source `.hwpx`; always write to a new `-o` path.
- **NEVER** attempt `.hwp` (binary) files — refuse with a clear message.
- If `extract.py` returns 0 slots, tell the user the form has no detectable
  empty cells and stop.

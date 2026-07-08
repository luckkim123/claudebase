---
name: invoice-organizer
description: |
  Organizes messy folders of receipts/invoices (영수증, 청구서, 인보이스) into a research-fund-settlement-ready filing system: extracts vendor/date/amount from PDFs and images, renames to a standard format, sorts into folders, and produces a CSV summary. Built for POSTECH 대학원생 연구비 정산 — moves are copy-verify-delete (never a bare mv), and every batch requires a shown dry-run plan + explicit user approval before touching a file.
  Triggers: 영수증 정리, 정산, 인보이스 정리, 연구비 정산, 청구서 정리, receipt organizing, expense organizing, organize invoices, organize receipts, tax prep invoices
triggers:
  - "/invoice-organizer"
  - "invoice-organizer"
  - "영수증 정리"
  - "정산"
  - "인보이스 정리"
  - "연구비 정산"
  - "청구서 정리"
  - "organize invoices"
  - "organize receipts"
  - "receipt organizing"
  - "expense organizing"
level: 2
---

# invoice-organizer

Turn a messy folder of receipts/invoices into a renamed, categorized, CSV-summarized filing set — for POSTECH 연구비 정산 (research-fund settlement) or general expense/tax bookkeeping.

**Rigid** on two things: the output location is resolved and confirmed *before* any file is touched (§1), and every move/delete goes through the **safe-fileops protocol** (§4) — dry-run plan shown, user approves, then copy→verify→delete. Never a direct `mv`. **Flexible** elsewhere: extraction heuristics, folder taxonomy, CSV columns.

## When to invoke

- "영수증 정리해줘", "이번 학기 정산 자료 정리", "인보이스 정리", "연구비 정산 자료 만들어줘"
- "organize these receipts", "sort my invoices for reimbursement", "prep tax invoices"

Do **not** invoke for: a single one-off file rename (just do it directly), or non-financial documents.

## The four steps

### 1 — Resolve input and output directories (REQUIRED, before anything else)

| Item | Resolve by |
|:---|:---|
| **Input folder** | Caller-specified path. Not given → ask which folder holds the receipts. |
| **Output folder** | Caller-specified path (`--out`, "정리해서 X에 넣어줘") → that path. Not specified → default to `<input-folder>/정산_YYYY-MM/` (current year-month) **but ask for confirmation** before creating it — never silently invent a destination. |

Then:
- `mkdir -p "$OUTPUT_DIR"` only after the user confirms the path.
- Echo the resolved input and output paths back in one line before scanning, so both ends are auditable.

**Never** scatter output into cwd or a guessed folder. If ambiguous, stop and ask — this mirrors gen-image's output-dir contract.

### 2 — Scan and extract

```bash
find "$INPUT_DIR" -type f \( -iname "*.pdf" -o -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" \) -print
```

Report: file count, file types, date range if visible from filenames.

For each file extract: vendor/company, date, amount, invoice/receipt number, description. From PDFs: text extraction, look for `Date:`/`청구일`, `Invoice #`/`영수증번호`, vendor name (usually top), `Total`/`금액`/`합계`. From images: read visible text for the same fields. If a field can't be extracted, fall back to file mtime and flag the file for manual review — never fabricate a vendor or amount.

### 3 — Standardize name and propose the plan (no filesystem writes yet)

Filename: `YYYY-MM-DD Vendor - Type - Description.ext` (e.g. `2026-03-15 Adobe - Invoice - Creative Cloud.pdf`). Strip special characters except hyphens; keep the original extension.

Ask the user's folder taxonomy if not specified (by vendor / by category / by year-month / by 연구비 항목); default to `YYYY-MM/카테고리/`.

Show the **dry-run plan** before any mutation — every batch requires this, no exceptions:

```markdown
# Organization Plan (dry-run — nothing moved yet)

원본: input_file.pdf → 대상: 정산_2026-07/재료비/2026-07-03 Vendor - Invoice - Desc.pdf
(...)

총 N개 파일. 승인하면 진행합니다. (yes/no)
```

Stop here and wait for explicit approval. A "정리해줘" invocation authorizes the *scan and plan*, not the mutation — the plan itself needs its own yes.

### 4 — Execute via safe-fileops (RIGID — never a bare `mv`)

Once approved, every file operation follows copy→verify→delete:

1. **Copy** (never move-in-place): `cp` source → resolved destination inside `$OUTPUT_DIR`.
2. **Verify**: confirm the destination file exists and its size (or SHA-256 for anything irreplaceable) matches the source — `find`/`ls` the destination, don't assume the `cp` exit code alone.
3. **Only then delete the source** — and only if the user asked to *move* rather than *copy*. Deletion goes through trash, never permanent erase:

| OS | Trash command |
|:---|:---|
| macOS | `trash` CLI if present, else move into `~/.Trash` |
| Linux | `gio trash`, else `trash-put` |
| No trash available | **STOP.** Confirm a copy exists elsewhere and get explicit "permanent 삭제 확인" approval before any `rm`. |

Never delete the source in the same breath as the copy — sync lag (iCloud/Drive) or a slow cross-volume copy can leave the destination incomplete, and a same-breath delete then loses the file permanently. If the input folder is inside a git repo, prefer `git rm` + commit (recoverable) over a raw filesystem delete.

**Boundary check**: before copying, resolve the destination's real path (follow symlinks) and confirm it stays inside the intended output root — a synced folder's symlink can silently redirect a file outside the managed tree.

### 5 — CSV summary and completion report

Write `invoice-summary.csv` into `$OUTPUT_DIR`:

```csv
Date,Vendor,Type,Description,Amount,Category,File Path
2026-03-15,Adobe,Invoice,Creative Cloud,52990,SW,정산_2026-03/SW/2026-03-15 Adobe - Invoice - Creative Cloud.pdf
```

Report: processed count, date range, total amount, files flagged for manual review (missing vendor/date/amount), and the final folder tree.

## Never

- Never `mv` a source file directly — always copy→verify→delete (§4).
- Never invent an output folder without confirming the path first (§1).
- Never delete a source without a trash path or explicit "permanent" approval.
- Never fabricate a vendor, date, or amount when extraction fails — flag for manual review instead.
- Never skip the dry-run plan, even for a small batch.

<!-- Adapted from ComposioHQ/awesome-claude-skills invoice-organizer (Apache License 2.0), 2026-07-09. Safe-fileops protocol (dry-run → approval → copy-verify-delete → trash) ported from oh-my-project/references/safe-fileops.md, replacing the original's direct-mv approach. -->

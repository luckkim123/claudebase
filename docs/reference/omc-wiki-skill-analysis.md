# OMC `wiki` Skill — Source Analysis

> **Purpose.** A source-level analysis of oh-my-claudecode's `wiki` skill, produced to inform the
> sibling OMX wiki (and any future harness that needs a persistent knowledge layer). Companion to
> `omc-harness-reference-v4.14.4.md` (which covers OMC's harness mechanics broadly); this card drills
> into the wiki subsystem specifically.
>
> **Pinned to:** OMC `v4.14.5`, git sha `3e94567` (marketplace `Yeachan-Heo/oh-my-claudecode`).
> **Method:** read all 7 engine modules (~2,000 LOC) + MCP wrapper + session-hook entrypoints + hook
> registration. Test bodies were listed, not read line-by-line.
> **Concept origin:** Karpathy's "LLM Wiki" — a persistent, self-maintained markdown KB that compounds
> across sessions, with NO vector embeddings (keyword + tag search only; the LLM synthesizes answers).

---

## 1. What it actually is

Not a prompt bundle — a **TypeScript ~2,000 LOC subsystem** with a thin SKILL.md (67 lines) on top.
Three layers:

| Layer | Location | Role |
|:---|:---|:---|
| User-facing | `skills/wiki/SKILL.md`, `commands/wiki.md` | tells the LLM how to use the 7 tools |
| MCP tools | `src/tools/wiki-tools.ts` (442) | 7 Zod-validated MCP tool handlers |
| Engine (pure core) | `src/hooks/wiki/*.ts` (~1,200) | storage / query / ingest / lint / session-hooks |

The engine lives under `hooks/` because wiki has **two entry surfaces**: MCP tools (LLM calls it) AND
session hooks (auto-fires on SessionStart/End/PreCompact). Both call the same pure core — this is the
key reuse pattern.

## 2. Data model

One page = one `.omc/wiki/<slug>.md` (markdown + YAML frontmatter):
`title, tags[], created, updated, sources[], links[], category, confidence(high|medium|low), schemaVersion`.

- 8 categories: `architecture, decision, pattern, debugging, environment, session-log, reference, convention`.
- Storage: pages + `index.md` (auto catalog) + `log.md` (append-only ops) + `environment.md` (reserved).
  The 3 non-page files are `RESERVED_FILES`-protected against page overwrite.
- `.omc/wiki/` is git-ignored by default (auto-added to `.omc/.gitignore`).

## 3. The 7 MCP tools

`wiki_ingest` (merge), `wiki_query` (search), `wiki_lint` (health), `wiki_add` (quick single, rejects
if exists), `wiki_list`, `wiki_read`, `wiki_delete`. Registered en masse in `tool-registry.ts`
(`...wikiTools`). `wiki_query`'s description explicitly tells the LLM: "YOU synthesize answers with
citations — the tool returns raw matches only."

## 4. Search — keyword + tag scoring (no embeddings)

`query.ts` is the most interesting module. Weighted scoring stands in for embeddings:

| Match | Weight |
|:---|:---|
| filter-tag overlap | +3/tag |
| query term in page tag | +2 |
| query string in title | +5 |
| query term in title | +2/term |
| query term in content | +1/term (+ snippet around first hit) |

**CJK bi-gram tokenizer** is the crux: CJK runs (Han/Hangul/Kana) are tokenized as *individual chars +
2-char sliding bigrams*, so Korean notes are searchable without word boundaries. 3-stage fallback:
Latin/digit (incl. accented Latin) → CJK bigram → other scripts (Cyrillic/Arabic/Thai) whitespace-split
with pure-punctuation tokens filtered via `\p{L}`.

## 5. Ingest — append-merge, never replace

Same slug exists → `mergePage()`: tags/sources/links union, confidence keeps higher (high3>med2>low1),
content **appends** as `## Update (timestamp)` section. Never overwrites. `[[wiki-link]]` extracted by
regex into frontmatter `links`. This is the actual "compounds across sessions" mechanism.

## 6. Lint — 6 structural checks

`orphan`(info, no inbound links), `stale`(warn, >staleDays=30), `broken-ref`(error, `[[link]]` to
missing page), `low-confidence`(info), `oversized`(warn, >10KB), `structural-contradiction`(slug-prefix
group with conflicting confidence high↔low, or shared tag across categories). Code comment is explicit:
**semantic contradiction detection is deferred to "v2" (needs LLM)** — current lint is structural only.

## 7. Production-grade safety (notable for a "small" skill)

- File lock: all writes through `withWikiLock()` (`.wiki-lock`, 5s timeout, 50ms retry) — sync lock
  because hooks run in sync context.
- Atomic write (`atomicWriteFileSync`, temp+rename) — no torn files on crash.
- Path-traversal: `safeWikiPath()` rejects `/`, `\`, `..`, then resolve-checks inside wikiDir.
- Non-ASCII slug collision: Korean-only titles slug to empty → deterministic `page-<hash>.md` fallback
  (else all collide on the `.md` dotfile).
- CRLF normalization; dependency-free `parseSimpleYaml` (key:value only, no nesting — deliberate).
- `*Unsafe` naming convention: functions unsafe outside the lock carry the suffix, enforcing the
  lock-boundary by *name* rather than type.

## 8. Session hooks — the auto-capture cycle

Registered in `hooks/hooks.json` (SessionStart/End + PreCompact), entry via `scripts/wiki-*.mjs`:

- **SessionStart**: lazy index rebuild + feeds `project-memory.json` into `environment.md` (techStack /
  build cmds) + injects first 30 index lines as context. (This is the `[LLM Wiki: N pages]` banner.)
- **SessionEnd**: 3s hard-timeout, append-only `session-log-<date>-<id>.md` of RAW metadata — NO
  LLM curation (deferred to next session's skill so session-end never blocks). `autoCapture` config-gated.
- **PreCompact**: injects `[Wiki: N pages | categories | last updated]` so wiki survives compaction.

## 9. Strengths / Limits (self-admitted in code)

**Strengths**: pure-core reuse across active+auto entry; production concurrency/security defenses;
CJK bigram solves Korean search without embeddings; append-only merge = lossless compounding.

**Limits**: (1) semantic contradiction detection unimplemented (v2); (2) keyword search weak on
synonym/paraphrase queries (inherent embeddings trade-off); (3) self-rolled YAML parser is key:value
only; (4) SessionEnd auto-capture is a placeholder (raw metadata; real curation is manual/next-session).

## 10. For the OMX sibling (delta to watch)

OMC wiki is MCP-tool + session-hook (auto, LLM-invoked). The OMX wiki re-implements the SAME patterns
in Python but exposes via `omx wiki` CLI subcommands (skills shell out explicitly) and adds a
**two-phase git-guarded gc** that OMC lacks (OMC only has a flat `wiki_delete`). See the OMX wiki
analysis (separate note) for the full comparison; the headline deltas are: CLI vs MCP+hooks, +gc.py,
loud-fail (WikiError) vs OMC's swallow-and-return-null, and injected `now` (testability) vs OMC's
internal `new Date()`.

**OMX cross-ref pin:** the OMX wiki core (`omx_core/wiki/*.py`, 802 LOC) is byte-identical across OMX
`0.1.9` and `0.1.10` (verified by diff); `0.1.10` changed only `report-coverage`, not wiki. The OMX
wiki analysis references OMX `0.1.10` (the in-use version).

---
name: gen-image
description: Generate one image with Google nano banana (Gemini 2.5 Flash Image) and save the PNG to a target directory. Use when the user asks to draw, generate, create, or make an image (Korean "그려줘", "이미지 만들어", "아이콘 생성", "그림"; English "draw", "create image", "generate", "nano banana"). Default mode wraps gemini CLI with verified flags + file-system verification (never trust the CLI text alone). Has a `--diagnose` mode that walks every auth layer (selectedType / GEMINI_API_KEY / direct curl / MCP response) when something stops working. Built from the 2026-05-19 nano banana debugging session that uncovered the OAuth-vs-API-key trap.
---

# gen-image

Generate one image via Google's nano banana model. Save PNG to disk. Verify the file actually exists (the gemini CLI lies about failure when MCP partially succeeded).

This skill is **rigid for the verification step** (always confirm file via `ls`/`stat`, never trust the gemini text response) and **flexible elsewhere** (prompt wording, output dir, model choice).

## When to invoke

- Korean: "고양이 그려줘", "이미지 만들어", "아이콘 생성", "포스터 만들어", "썸네일", "nano banana 테스트", "그림 하나 뽑아줘"
- English: "draw a ...", "create an image of ...", "generate an icon for ...", "make a thumbnail ...", "nano banana"
- Explicit slash: `/gen-image <prompt>`, `/gen-image --diagnose <prompt>`

Do **not** invoke for:

- Editing an existing image (use `nanobanana edit` or write a separate `edit-image` skill)
- Diagram/flowchart generation — use `mermaid-chart` or `excalidraw` MCP instead
- Photo-realistic deepfake / impersonation requests — refuse before invoking

## Hard prerequisites (check first, fail loudly)

1. **`gemini` CLI on PATH** — `command -v gemini` returns a path. If missing: `npm install -g @google/gemini-cli` and stop.
2. **`NANOBANANA_API_KEY` exported** — `[[ -n "$NANOBANANA_API_KEY" ]]`. The key value lives in `~/claude-settings/secrets/secrets.env`; `~/.zshrc` sources that file. If missing: tell the user to source the file or open a new shell, do not write a key inline.
3. **`~/.gemini/extensions/nanobanana/` exists** — nano banana extension is installed. If missing: `gemini extensions install https://github.com/gemini-cli-extensions/nanobanana` and stop.

If any check fails, surface it and stop. Do not paper over with fallbacks.

## Default flow (the verified happy path)

The exact invocation pattern that worked in the 2026-05-19 session. Do not improvise around it.

```bash
GEMINI_API_KEY="$NANOBANANA_API_KEY" gemini --approval-mode yolo -p "$PROMPT_FULL" 2>&1 | tail -40
```

Three things matter and each has a reason:

- `GEMINI_API_KEY="$NANOBANANA_API_KEY"` — inline-export the key. Required because `gemini-api-key` mode is unstable (see Known traps); the CLI in `oauth-personal` mode still works for the body call and forwards the API key to the MCP child via `NANOBANANA_API_KEY`. Inline-exporting both names covers any code path.
- `--approval-mode yolo` — **mandatory**. Without it gemini drops into Plan Mode and blocks `mcp_nanobanana_generate_image` with `Unauthorized tool call`. The error text says "I am in Plan Mode" — do not waste time re-prompting; just add the flag.
- `2>&1 | tail -40` — image generation prints many lines; keep the last 40 so the "saved at" path stays visible.

### Prompt template

Build `PROMPT_FULL` by concatenating the user's intent with explicit MCP instructions:

```
Use ONLY the nanobanana generate_image MCP tool (model gemini-2.5-flash-image, NOT the preview model).
Do NOT use web search, grep, or any other tool.
Image: <USER PROMPT, verbatim>
Save the PNG to <ABSOLUTE_OUTPUT_PATH>.
Print the absolute file path on the final line.
```

The "Do NOT use web search" line is load-bearing — without it the worker sometimes runs `WebSearch` first to "research" the subject, then hits a 500 retry loop.

### Output path convention

- Default directory: `<workspace-root>/90-99_Inbox_Archive/91_Inbox/nanobanana_test/` (for this Desktop/workspace; resolve to a sensible inbox in other workspaces)
- Default filename: `<sanitized-slug>_<YYYYMMDD-HHMMSS>.png` (slug = first 4 words of the prompt, ASCII-lower, `_`-joined)
- Override accepted from the caller — if the user asks to save somewhere specific, honor that.

### Verification step (do not skip)

Immediately after the CLI call:

```bash
test -f "$OUTPUT_PATH" && stat -f "%z bytes, modified %Sm" "$OUTPUT_PATH"
```

- If the file exists and is `> 50 KB`: success. Open with `open "$OUTPUT_PATH"` so Preview pops up. Report the path. Done.
- If the file is missing **but** the gemini stdout claims success: the CLI lied. Surface the discrepancy and go to fallback.
- If the file is missing and the stdout shows an error: parse the error class (see Known traps) and either retry once or escalate.

## Fallback: direct REST API call

When the gemini CLI keeps looping on transient errors (503, 500, MCP "reported an error"), bypass it. The REST endpoint is more reliable than the CLI + MCP combo.

```python
import os, json, base64, urllib.request, datetime, sys, re
api_key = os.environ["NANOBANANA_API_KEY"]
prompt = "<USER PROMPT, verbatim — no MCP wrappers, no plan-mode hints>"
out_dir = "<ABSOLUTE_OUTPUT_DIR>"
slug = re.sub(r"[^a-z0-9]+", "_", "_".join(prompt.lower().split()[:4])).strip("_") or "image"
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent?key={api_key}"
req = urllib.request.Request(url, data=json.dumps({"contents":[{"parts":[{"text": prompt}]}]}).encode(),
                              headers={"Content-Type":"application/json"}, method="POST")
j = json.loads(urllib.request.urlopen(req, timeout=60).read())
if "error" in j:
    sys.exit(f"REST error: {j['error']}")
for p in j["candidates"][0]["content"]["parts"]:
    if "inlineData" in p:
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        out = f"{out_dir}/{slug}_{ts}.png"
        open(out, "wb").write(base64.b64decode(p["inlineData"]["data"]))
        print(out)
```

The REST fallback has produced images in this workspace when the CLI path failed (`banana_20260519-143645_1.png`).

## `--diagnose` mode

Run when the default flow fails. Walks each layer top-to-bottom, surfacing what is broken without guessing.

1. **selectedType** — `python3 -c 'import json,pathlib; print(json.loads((pathlib.Path.home()/".gemini/settings.json").read_text())["security"]["auth"]["selectedType"])'`. Acceptable: `oauth-personal` or `gemini-api-key`. Report which one is active so the user knows.
2. **Key validity (text model)** — direct curl to `gemini-2.5-flash`. If this fails with `401`/`PERMISSION_DENIED`: the key itself is invalid. If `429`/`RESOURCE_EXHAUSTED`: paid tier billing may not be active. If `503`/`500`: Google-side transient, retry the whole flow in 60s.
3. **Key validity (image model)** — direct curl to `gemini-2.5-flash-image`. If text works but image fails: image-generation backend issue, not auth. The poll loop in `~/claude-settings/claude/scripts/` can wait for recovery.
4. **MCP tool reachability** — call gemini with the verified flags and an explicit `generate_image` prompt. If MCP returns "reported an error" but the file is still saved: report both the error text and the file path; the CLI mis-reports MCP partial success as full failure.
5. **Plan Mode detection** — if stdout contains `[LocalAgentExecutor] Blocked call` or `Plan Mode`: the `--approval-mode yolo` flag was missing from the invocation.

After diagnostics print, attempt the generation once with whatever still works (text-model curl can confirm the key; image-model curl is the actual generation).

## Known traps (every one bit me in the 2026-05-19 session)

- **The CLI lies.** It will print `Error executing tool mcp_nanobanana_generate_image: ...API key not valid` and the file is still saved to disk. Always check the filesystem. Do not re-trigger generation based on stdout alone — you'll burn API credits.
- **`selectedType: gemini-api-key` is brittle.** It propagates `GEMINI_API_KEY` to the CLI body but the nano banana MCP child still claims "API key not valid". `selectedType: oauth-personal` is paradoxically more reliable for MCP calls, even though it routes the CLI body through OAuth.
- **`Plan Mode` defaults.** Calling `gemini -p "..."` without `--approval-mode yolo` lands in plan mode and blocks all tool calls. Error includes `[LocalAgentExecutor] Blocked call`.
- **Decompose error.** `omc team 1:gemini "task with comma, second clause"` fails with `Pre-authored task scope count (2) must match explicit worker count (1)`. Either remove commas from the task string or pass `--no-decompose`.
- **Quota strings are confusing.** `Your quota will reset after 0s` does **not** mean "ready in 0 seconds" — it means "quota is exhausted indefinitely on this auth path". The fix is switching auth path, not waiting.
- **503/500 vs quota.** A `503 UNAVAILABLE` or `500 INTERNAL` is Google's server, not your account; retry in 1–3 minutes. A `429`/`RESOURCE_EXHAUSTED` or the literal string `exhausted your capacity` is account-side and won't resolve by retrying.
- **Preview model vs stable.** The nano banana extension hardcodes `gemini-3.1-flash-image-preview` as default (see `~/.gemini/extensions/nanobanana/mcp-server/dist/imageGenerator.js:509`). Override with `NANOBANANA_MODEL=gemini-2.5-flash-image` for more stable behavior. Both worked when Google was healthy on 2026-05-19; the stable model is the safer pick.
- **MCP child env inheritance.** The MCP server is a separate node child process. It reads `NANOBANANA_API_KEY` (and a fallback chain documented at `imageGenerator.js` lines 76+) but it does **not** see arbitrary `export`s that happen after the gemini CLI was launched. If you change env vars, restart the gemini parent.

## What this skill never does

- Never edit `~/.gemini/settings.json` without telling the user (the prior session toggled `selectedType` between two values trying to fix the wrong layer; both work, just with different failure modes).
- Never put an API key into a task description, slash command, or commit. Keys live only in `~/claude-settings/secrets/secrets.env` (gitignored).
- Never claim success on stdout alone. Always `test -f` the output path.
- Never propose `omc team N:gemini` for one-shot image generation — the prompt-mode launch (`gemini -p`) is functionally identical to a direct CLI call but adds 30+ seconds of worker setup and a tmux pane. Use omc-teams only when the user explicitly asked for it or when generating in parallel with other work.

## Acceptance for "done"

- A PNG file exists at the reported path
- File size > 50 KB (a 0-byte or 1 KB file means the API returned only text, not image bytes)
- macOS Preview opened the image (visual confirmation by the user)
- Reported path is absolute, not relative

Anything less is **not done**, even if the CLI printed "Saved!"

---

**Origin**: 2026-05-19 nano banana debugging session in `~/Desktop/workspace`. Three generated PNGs from that session live in `90-99_Inbox_Archive/91_Inbox/nanobanana_test/`.

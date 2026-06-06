---
name: gen-image
description: |
  Generate ONE image with Google nano banana (Gemini 2.5 Flash Image) and save the PNG to a required, explicitly-resolved output directory. Crafts the user's intent into Google's 5-component scene prompt before generating, runs the verified gemini-CLI path with a REST fallback, and confirms the file on disk (never trusts CLI text alone). Output dir is a hard contract by caller: oms→.oms/assets/, omd→.omd/assets/, human→$GEN_IMAGE_OUTDIR or project inbox, else ask.
  Triggers: 그려줘, 이미지 만들어, 아이콘 생성, 그림, 포스터, 썸네일, nano banana, draw, create image, generate image, make a thumbnail
argument-hint: "<output-dir> <prompt> [--aspect 16:9|1:1|9:16|...] [--diagnose]"
level: 2
triggers:
  - "/gen-image"
  - "gen-image"
  - "그려줘"
  - "이미지 만들어"
  - "아이콘 생성"
  - "그림"
  - "포스터"
  - "썸네일"
  - "draw"
  - "create image"
  - "generate image"
  - "nano banana"
---

# gen-image

Generate one image via Google's nano banana model, save the PNG, and **verify it exists on disk** — the gemini CLI reports failure even when MCP partially succeeded and the file was written.

**Rigid** on two steps: the output dir is *resolved before generating* (§1) and the result is *confirmed on the filesystem* (§4) — never trust CLI stdout. **Flexible** elsewhere: prompt wording, model choice, CLI-vs-REST path.

## When to invoke

- **Generate**: "고양이 그려줘", "이미지/아이콘/포스터/썸네일 만들어", "draw a …", "create an image of …", "nano banana"
- **Slash**: `/gen-image <output-dir> <prompt>`, `/gen-image --diagnose`

Do **not** invoke for:
- **Editing** an existing PNG → that's `nanobanana edit`, a different workflow (this skill only *generates*).
- **Diagrams / flowcharts** → use `mermaid-chart` or `excalidraw` MCP.
- **Deepfakes / impersonation** of real people → refuse before invoking.

## The four steps

Run them in order. 1 and 4 are the rigid ones.

### 1 — Resolve the output directory (REQUIRED, before anything else)

The skill's #1 historical failure was scattering PNGs wherever felt right that session. **Resolve one absolute directory up front, by the first matching rule:**

| Caller | Output directory |
|:---|:---|
| Passed an explicit path (`--out`, `output_dir=`, "save to X") | that path |
| **oms / scholar harness** (a `.oms/` work-root in cwd, or called from an oms skill) | `.oms/assets/` |
| **omd / docs harness** (an `.omd/` work-root in cwd, or called from an omd skill) | `.omd/assets/` (or `<target-doc-folder>/assets/` if the build targets one concrete folder) |
| Human, with `$GEN_IMAGE_OUTDIR` set | `$GEN_IMAGE_OUTDIR` |
| Human, with a known project inbox (`_inbox/`, `assets/`, a Johnny-Decimal `91_Inbox/`) | that inbox |
| Human, none of the above | **STOP and ask where to save** |

Then, every time:
- `mkdir -p "$OUTPUT_DIR"` — a missing dir is the silent cause of "file not found" after the CLI prints "Saved!".
- Filename = `<slug>_<YYYYMMDD-HHMMSS>.png` (slug = first 4 prompt words, ASCII-lower, `_`-joined) — deterministic, no collisions.
- Echo the resolved `$OUTPUT_DIR` back in one line *before* generating, so the destination is auditable.

**Never** fall back to cwd or invent a new folder. A scattered, "different path each time" output is the exact bug this rule kills.

### 2 — Craft the prompt (don't pass raw intent)

Google's guidance is explicit: *describe a scene narratively, with detail — not a bare keyword list.* "Use detailed prompts to take more control." A one-word "고양이" becomes a full scene first.

**5-component scene** (Google's official frame):

| Component | Fill with |
|:---|:---|
| **Style / medium** | "a cinematic photograph", "a flat vector icon", "an isometric 3D render" |
| **Subject** | "a fluffy orange tabby cat with green eyes" (be specific) |
| **Setting** | "on a sunlit windowsill, blurred city skyline behind" |
| **Action** | "stretching mid-yawn, one paw extended" |
| **Composition** | "close-up, shallow depth of field (f/1.8), low-angle shot" |

Concatenate into prose. "주황색 고양이 그려줘" →
> *"A cinematic close-up photograph of a fluffy orange tabby cat with bright green eyes, on a sunlit windowsill with a softly blurred city skyline behind, stretching mid-yawn with one paw extended, shallow depth of field (f/1.8), warm golden-hour light."*

**Style cheat-sheet** (vocabulary the model responds to):
- *Photographic* — `photorealistic`, `cinematic`, `film noir`, `1990s product photography`; lens language matters: `shallow depth of field (f/1.8)`, `golden hour backlighting`, `low-angle / wide-angle / macro`, `cinematic color grading with muted teal tones`.
- *Illustration* — `flat vector`, `watercolor`, `impressionist oil painting`, `line art`, `children's book illustration`, `comic / manga`.
- *3D* — `isometric 3D render`, `claymation`, `Pixar-style 3D animation`, `low-poly`, `product render on seamless white`.

**Text in the image** (Gemini is strong here when prompted right): **(1)** put exact words in quotes — `the headline "URBAN EXPLORER"`; **(2)** describe the typography — `in bold white sans-serif at the top`, `"Happy Birthday" in neon cursive`. Without quotes the model treats words as a concept and garbles them.

**Advanced patterns** (when the 5-component scene isn't enough):
- *Reusable templates* — `"Create [STYLE] of [OBJECT] [SCENE], with [LIGHTING]"`; retexture via JSON spec `{material: glass, reflections: true, transparency: true}` (steers material far better than adjectives); `"… based on [attached image], preserving [face/pose/clothing]"`.
- *Identity consistency* — name the features to preserve explicitly; don't let the model infer them.
- *Spatial illusions* — forced perspective ("standing out of a phone screen"), nested scenes ("a world inside a crystal ball, chibi style"), negative-space shaping ("a subject formed by scattered clouds").
- *Iterate, don't overload* — generate a base, then refine in a separate follow-up ("now make it nighttime") rather than cramming every constraint into one prompt. Use `[VARIABLE]` placeholders to reuse a working prompt.

**Failure modes → fixes:**

| Failure | Fix |
|:---|:---|
| Garbled text | quote the exact string + describe the font |
| Excluded thing still appears ("without X") | image models ignore negation — **rephrase positively** ("a smooth bald head", not "without horns") |
| Constraints ignored / hallucinated shapes | trim to the 5 essentials; generate base first, refine second |
| Earlier details "forgotten" | front-load subject + style; keep the prompt tight |

### 3 — Generate

**Aspect ratio first.** It's a real API parameter, **not** a prompt keyword — burying "16:9" in prose is unreliable (a cross-model rule: gpt-image uses a `size` param, Imagen `aspectRatio`). The 10 supported values: landscape `21:9 16:9 4:3 3:2`, square `1:1`, portrait `9:16 3:4 2:3`, flexible `5:4 4:5`. The REST path takes it as a param (below); the **CLI path can't**, so there steer aspect via prose as a weaker fallback. Resolution (1K/2K/4K) is a Nano-Banana-**Pro** setting, not on `gemini-2.5-flash-image`.

**Path A — gemini CLI (default).** The exact pattern verified to work; don't improvise around it:

```bash
GEMINI_API_KEY="$NANOBANANA_API_KEY" gemini --approval-mode yolo -p "$PROMPT_FULL" 2>&1 | tail -40
```

- `GEMINI_API_KEY="$NANOBANANA_API_KEY"` — inline-export. `gemini-api-key` auth mode is brittle (§traps); `oauth-personal` still forwards the key to the MCP child via `NANOBANANA_API_KEY`. Inline-exporting covers any code path.
- `--approval-mode yolo` — **mandatory**. Without it gemini enters Plan Mode and blocks the MCP tool ("I am in Plan Mode" / `[LocalAgentExecutor] Blocked call`). Don't re-prompt; add the flag.
- `2>&1 | tail -40` — keep the last lines so the "saved at" path stays visible.

`PROMPT_FULL` wraps the §2 crafted scene for the MCP worker:

```
Use ONLY the nanobanana generate_image MCP tool (model gemini-2.5-flash-image, NOT the preview model).
Do NOT use web search, grep, or any other tool.
Image: <CRAFTED SCENE PROMPT from §2 — not the user's one-word intent>
Save the PNG to <ABSOLUTE_OUTPUT_PATH>.
Print the absolute file path on the final line.
```

The "Do NOT use web search" line is load-bearing — without it the worker sometimes runs `WebSearch` to "research" the subject, then hits a 500 loop.

**Path B — direct REST (fallback).** When the CLI loops on transient errors (503/500, MCP "reported an error"), bypass the whole CLI/MCP/keychain stack:

```python
import os, json, base64, urllib.request, datetime, sys, re
api_key = os.environ["NANOBANANA_API_KEY"]
prompt  = "<CRAFTED SCENE PROMPT, verbatim>"
out_dir = "<ABSOLUTE_OUTPUT_DIR>"      # from §1 — required
aspect  = "<ASPECT or None>"           # "16:9" / "1:1" / "9:16"; None = model default
slug = re.sub(r"[^a-z0-9]+", "_", "_".join(prompt.lower().split()[:4])).strip("_") or "image"
os.makedirs(out_dir, exist_ok=True)
body = {"contents": [{"parts": [{"text": prompt}]}]}
if aspect:                             # aspect ratio is an API param, NOT a prompt keyword
    body["generationConfig"] = {"responseModalities": ["IMAGE"],
                                "imageConfig": {"aspectRatio": aspect}}
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent?key={api_key}"
req = urllib.request.Request(url, data=json.dumps(body).encode(),
                              headers={"Content-Type": "application/json"}, method="POST")
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

### 4 — Verify on disk (RIGID — never skip)

```bash
# stat flags differ by OS (BSD/macOS vs GNU/Linux)
test -f "$OUTPUT_PATH" && { stat -f%z "$OUTPUT_PATH" 2>/dev/null || stat -c%s "$OUTPUT_PATH"; }
```

- File exists and **> 50 KB** → success. Optionally open it (`open` macOS / `xdg-open` Linux / `start` Windows). Report the absolute path. **Done.**
- File missing but stdout claims success → **the CLI lied**; go to Path B.
- File missing with a stdout error → classify it (§traps), retry once or escalate.

A 0-byte / 1 KB file means the API returned text, not image bytes — **not done**, even if it printed "Saved!".

## Prerequisites (check first, fail loudly — don't paper over)

1. **`gemini` on PATH** — `command -v gemini`. Missing → `npm install -g @google/gemini-cli`, stop.
2. **`NANOBANANA_API_KEY` exported** — `[[ -n "$NANOBANANA_API_KEY" ]]`. Get a key at <https://aistudio.google.com/apikey>; keep it in your secrets store / env (gitignored), **never inline** in the skill, a command, or a commit. Missing → tell the user to export/source it, stop.
3. **`~/.gemini/extensions/nanobanana/` exists**. Missing → `gemini extensions install https://github.com/gemini-cli-extensions/nanobanana`, stop.

## `--diagnose` mode

When the flow fails, walk the layers top-down — surface what's broken, don't guess:

1. **selectedType** — `python3 -c 'import json,pathlib; print(json.loads((pathlib.Path.home()/".gemini/settings.json").read_text())["security"]["auth"]["selectedType"])'`. `oauth-personal` or `gemini-api-key`; report which is active.
2. **Key — text model** — curl `gemini-2.5-flash`. `401`/`PERMISSION_DENIED` → key invalid. `429`/`RESOURCE_EXHAUSTED` → billing/quota. `503`/`500` → Google transient, retry in 60s.
3. **Key — image model** — curl `gemini-2.5-flash-image`. Text works but image fails → backend issue, retry in 1–3 min, don't re-issue the key.
4. **MCP reachability** — run the §3 Path-A command. If MCP says "reported an error" but the file saved → report both; the CLI mis-reports partial success as failure.
5. **Plan Mode** — stdout has `[LocalAgentExecutor] Blocked call` / `Plan Mode` → the `--approval-mode yolo` flag was missing.

## Known traps (all verified hands-on)

- **The CLI lies.** It prints `Error executing tool mcp_nanobanana_generate_image: …API key not valid` while the file *is* on disk. Always check the filesystem; don't re-trigger on stdout alone — you'll burn credits.
- **`selectedType: gemini-api-key` is brittle.** It forwards `GEMINI_API_KEY` to the CLI body but the MCP child still claims "API key not valid". `oauth-personal` is paradoxically more reliable for MCP.
- **Plan Mode default.** `gemini -p` without `--approval-mode yolo` blocks all tool calls (`[LocalAgentExecutor] Blocked call`).
- **Quota strings mislead.** `Your quota will reset after 0s` means "exhausted indefinitely on this auth path", not "ready in 0s". Fix = switch auth path, not wait.
- **503/500 vs 429.** `503 UNAVAILABLE` / `500 INTERNAL` = Google's server, retry in 1–3 min. `429`/`RESOURCE_EXHAUSTED` / `exhausted your capacity` = account-side, retrying won't help.
- **Preview vs stable model.** The extension hardcodes `gemini-3.1-flash-image-preview` (`~/.gemini/extensions/nanobanana/mcp-server/dist/imageGenerator.js:509`). Override with `NANOBANANA_MODEL=gemini-2.5-flash-image` for stability.
- **MCP child env.** The MCP server is a separate node child; it reads `NANOBANANA_API_KEY` (fallback chain at `imageGenerator.js:76+`) but **not** exports made after the gemini parent launched. Change env → restart the parent.
- **Keychain in tmux/SSH (macOS).** `gemini extensions install` stores the key via macOS Keychain for any extension marked `"sensitive": true`. In tmux/SSH the unlock dialog can't appear → `Keychain is not available` → extension *skipped on load* (MCP tool never registers). Fix: run the install once in a **direct Terminal window outside tmux**; or bypass keychain — copy gemini's temp clone (`/var/folders/.../gemini-extension*`) into `~/.gemini/extensions/nanobanana/`, edit `gemini-extension.json` to drop the `settings` block and put the key in `mcpServers.nanobanana.env.NANOBANANA_API_KEY`, then `chmod 600` the manifest.
- **Project access 403.** A fresh AI Studio key may pass `GET /v1beta/models` but fail `generateContent` with `403 PERMISSION_DENIED — Your project has been denied access`. Project-level, not key-level. Diagnose: models-list curl succeeds while a `generateContent` POST returns 403 → **issue a fresh key** at <https://aistudio.google.com/apikey>. Don't chase CLI/MCP/keychain layers when both REST and CLI return identical 403.

## Never

- Edit `~/.gemini/settings.json` without telling the user.
- Put an API key in a task description, slash command, or commit.
- Claim success on stdout alone — always `test -f`.
- (With multi-agent runners) spin up `team N:gemini` for one-shot generation — `gemini -p` is identical but adds 30s + a tmux pane. Reserve it for explicit parallel-generation only.

## Sources

Prompt-craft guidance (§2–3) was fetched and read directly, not recalled:
- Google **Gemini image prompt guide** — `deepmind.google/models/gemini-image/prompt-guide/` (5-component scene, quote-the-text rule, style vocabulary).
- Google **Nano Banana Pro prompting tips** — `blog.google/products-and-platforms/products/gemini/prompting-tips-nano-banana-pro/` (camera/lens language, text placement, resolution).
- Google **Developers Blog**, *"Gemini 2.5 Flash Image now ready for production with new aspect ratios"* (`imageConfig.aspectRatio` + the 10 ratios).
- **[JimmyLv/awesome-nano-banana](https://github.com/JimmyLv/awesome-nano-banana)** README (the Advanced-patterns block, distilled from real working prompts).
- **OpenAI image-generation API guide** (cross-model confirmation: dimensions are an API param, and OpenAI silently rewrites prompts via `revised_prompt` — Gemini does not, so Gemini rewards precise wording).
- Negation failure is a general image-model property (DALL·E 3 / Imagen), treated as cross-model.
- Unmined for more patterns: [YouMind-OpenLab/awesome-nano-banana-pro-prompts](https://github.com/YouMind-OpenLab/awesome-nano-banana-pro-prompts), [devanshug2307/Awesome-AI-Image-Prompts](https://github.com/devanshug2307/Awesome-AI-Image-Prompts).

**Origin**: every trap and the REST fallback were reproduced hands-on in a 2026-05-19 nano-banana debugging session on macOS (gemini CLI + nanobanana extension; the OAuth-vs-API-key trap). They are findings, not guesses — keep them. Restructured 2026-05-30 into the four-step flow with the output-path contract and verified prompt-engineering guidance.

---
name: gen-image
description: |
  Generate ONE image with Google's Nano Banana models (Gemini 3 image family) and save it to a required, explicitly-resolved output directory. Lets the caller pick the model tier (banana2 = fast, pro = high quality) and resolution (1K/2K/4K); defaults to pro·2K. Crafts the user's intent into Google's 5-component scene prompt, calls the verified /v1beta/interactions REST endpoint directly, and confirms the file on disk (never trusts stdout alone). text-to-image only. Output dir is a hard contract by caller: oms→.oms/assets/, omd→.omd/assets/, human→$GEN_IMAGE_OUTDIR or project inbox, else ask.
  Triggers: 그려줘, 이미지 만들어, 아이콘 생성, 그림, 포스터, 썸네일, nano banana, banana2, draw, create image, generate image, make a thumbnail
argument-hint: "<output-dir> <prompt> [--model pro|banana2] [--size 1K|2K|4K] [--aspect 16:9|1:1|9:16|...] [--diagnose]"
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
  - "banana2"
---

# gen-image

Generate one image via Google's Nano Banana models, save it, and **verify it exists on disk**.

**Rigid** on two steps: the output dir is *resolved before generating* (§1) and the result is *confirmed on the filesystem* (§4). **Flexible** elsewhere: prompt wording, model tier, resolution, aspect ratio.

## Model tiers (verified live 2026-07-09)

The Google Gemini API exposes two current Nano Banana image models. The caller picks with `--model`:

| `--model` | Marketing name | Model ID | Character |
|:---|:---|:---|:---|
| `pro` (**default**) | Nano Banana Pro | `gemini-3-pro-image` | Highest quality, slower, pricier. Best for slides/posters/anything print-facing. |
| `banana2` | Nano Banana 2 | `gemini-3.1-flash-image` | Fast, cheap, high-volume. Good enough for most quick generations. |

Both are GA. The legacy `gemini-2.5-flash-image` (original Nano Banana v1) still works but there's no reason to prefer it — banana2 supersedes it.

**Defaults**: `--model pro --size 2K`. Override only when the user asks for speed/cost (`--model banana2`) or a specific resolution.

## When to invoke

- **Generate**: "고양이 그려줘", "이미지/아이콘/포스터/썸네일 만들어", "draw a …", "create an image of …", "nano banana", "banana2"
- **Slash**: `/gen-image <output-dir> <prompt> [--model …] [--size …]`, `/gen-image --diagnose`

Do **not** invoke for:
- **Editing / image-to-image** (feeding an existing PNG to transform it) → this skill is **text-to-image only**. That's a separate workflow.
- **Diagrams / flowcharts** → use `mermaid-chart` or `excalidraw` MCP.
- **Deepfakes / impersonation** of real people → refuse before invoking.

## The four steps

Run them in order. 1 and 4 are the rigid ones.

### 1 — Resolve the output directory (REQUIRED, before anything else)

The skill's #1 historical failure was scattering images wherever felt right that session. **Resolve one absolute directory up front, by the first matching rule:**

| Caller | Output directory |
|:---|:---|
| Passed an explicit path (`--out`, `output_dir=`, "save to X") | that path |
| **oms / scholar harness** (a `.oms/` work-root in cwd, or called from an oms skill) | `.oms/assets/` |
| **omd / docs harness** (an `.omd/` work-root in cwd, or called from an omd skill) | `.omd/assets/` (or `<target-doc-folder>/assets/` if the build targets one concrete folder) |
| Human, with `$GEN_IMAGE_OUTDIR` set | `$GEN_IMAGE_OUTDIR` |
| Human, with a known project inbox (`_inbox/`, `assets/`, a Johnny-Decimal `91_Inbox/`) | that inbox |
| Human, none of the above | **STOP and ask where to save** |

Then, every time:
- `mkdir -p "$OUTPUT_DIR"` — a missing dir is the silent cause of "file not found" after a "Saved!".
- Filename = `<slug>_<YYYYMMDD-HHMMSS>.<ext>` (slug = first 4 prompt words, ASCII-lower, `_`-joined; `ext` from the returned bytes — the API returns **JPEG by default**, so default to `.jpg`). Deterministic, no collisions.
- Echo the resolved `$OUTPUT_DIR` back in one line *before* generating, so the destination is auditable.

**Never** fall back to cwd or invent a new folder. A scattered, "different path each time" output is the exact bug this rule kills.

### 2 — Craft the prompt (don't pass raw intent)

Google's guidance is explicit: *describe a scene narratively, with detail — not a bare keyword list.* A one-word "고양이" becomes a full scene first.

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

**Text in the image** (Gemini is strong here when prompted right): **(1)** put exact words in quotes — `the headline "URBAN EXPLORER"`; **(2)** describe the typography — `in bold white sans-serif at the top`, `"Happy Birthday" in neon cursive`. Without quotes the model treats words as a concept and garbles them. (Nano Banana Pro's text rendering is notably stronger — long/legible text is worth using `pro` for.)

**Advanced patterns** (when the 5-component scene isn't enough):
- *Reusable templates* — `"Create [STYLE] of [OBJECT] [SCENE], with [LIGHTING]"`; retexture via JSON spec `{material: glass, reflections: true, transparency: true}` (steers material far better than adjectives).
- *Identity consistency* — name the features to preserve explicitly; don't let the model infer them.
- *Spatial illusions* — forced perspective ("standing out of a phone screen"), nested scenes ("a world inside a crystal ball, chibi style"), negative-space shaping ("a subject formed by scattered clouds").
- *Iterate, don't overload* — generate a base, then refine in a separate follow-up ("now make it nighttime") rather than cramming every constraint into one prompt.

**Failure modes → fixes:**

| Failure | Fix |
|:---|:---|
| Garbled text | quote the exact string + describe the font; consider `--model pro` |
| Excluded thing still appears ("without X") | image models ignore negation — **rephrase positively** ("a smooth bald head", not "without horns") |
| Constraints ignored / hallucinated shapes | trim to the 5 essentials; generate base first, refine second |
| Earlier details "forgotten" | front-load subject + style; keep the prompt tight |

### 3 — Generate (REST is the primary path)

The current models are only reachable via Google's **`/v1beta/interactions`** endpoint — the legacy `:generateContent` path does **not** accept the resolution/aspect parameters, and the `gemini` CLI nanobanana extension does not target this endpoint. So the REST call below is the primary path, not a fallback.

**Aspect ratio and resolution are real API parameters** under `response_format`, not prompt keywords. Verified accepted values (server-enforced enum):
- `image_size`: **`512` · `1K` · `2K` · `4K`** (default `2K` in this skill).
- `aspect_ratio`: **`1:1 2:3 3:2 3:4 4:3 4:5 5:4 9:16 16:9 21:9 1:8 8:1 1:4 4:1`** plus `auto`.

The API key is Google's, read from the environment (see Prerequisites). The exact working request:

```python
import os, json, base64, urllib.request, urllib.error, datetime, sys, re

key   = os.environ["GEMINI_API_KEY"]          # Google AI Studio key (AIzaSy…); NANOBANANA_API_KEY holds the same value
model = "gemini-3-pro-image"                   # pro (default) | banana2 -> "gemini-3.1-flash-image"
prompt   = "<CRAFTED SCENE PROMPT from §2>"    # not the user's one-word intent
out_dir  = "<ABSOLUTE_OUTPUT_DIR>"             # from §1 — required
aspect   = "1:1"                               # one of the enum values, or "auto"
img_size = "2K"                                # 512 | 1K | 2K | 4K

slug = re.sub(r"[^a-z0-9]+", "_", "_".join(prompt.lower().split()[:4])).strip("_") or "image"
os.makedirs(out_dir, exist_ok=True)

body = {
    "model": model,
    "input": [{"type": "text", "text": prompt}],
    "response_format": {"type": "image", "aspect_ratio": aspect, "image_size": img_size},
}
url = f"https://generativelanguage.googleapis.com/v1beta/interactions?key={key}"
req = urllib.request.Request(url, data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json"}, method="POST")
try:
    j = json.loads(urllib.request.urlopen(req, timeout=180).read())
except urllib.error.HTTPError as e:
    sys.exit(f"HTTP {e.code}: {json.loads(e.read()).get('error',{}).get('message','')}")

# Image bytes live at steps[].content[].data (base64). Walk defensively —
# the generation step is steps[1] in observed responses, but scan to be safe.
b64 = None
def walk(o):
    global b64
    if b64: return
    if isinstance(o, dict):
        for k, v in o.items():
            if k == "data" and isinstance(v, str) and len(v) > 1000: b64 = v; return
            walk(v)
    elif isinstance(o, list):
        for v in o: walk(v)
walk(j)
if not b64:
    sys.exit("no image bytes in response: " + json.dumps(j)[:500])

# API returns JPEG by default -> .jpg
ts  = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
out = f"{out_dir}/{slug}_{ts}.jpg"
open(out, "wb").write(base64.b64decode(b64))
print(out)
```

Map `--model`: `pro` → `gemini-3-pro-image`, `banana2` → `gemini-3.1-flash-image`. Everything else identical.

Cost/speed note: `pro` + `4K` is the slowest and most expensive combination (a 2K pro call returns a ~2.5 MB JPEG in a few seconds; 4K is larger). Use `banana2` and/or `1K` when the user wants quick/cheap.

### 4 — Verify on disk (RIGID — never skip)

```bash
# stat flags differ by OS (BSD/macOS vs GNU/Linux)
test -f "$OUTPUT_PATH" && { stat -f%z "$OUTPUT_PATH" 2>/dev/null || stat -c%s "$OUTPUT_PATH"; }
```

- File exists and **> 50 KB** → success. Optionally open it (`open` macOS / `xdg-open` Linux / `start` Windows). Report the absolute path. **Done.**
- File missing but stdout claims success → the script errored; re-read stderr, fix, retry once.
- File missing with an HTTP error → classify it (§traps), retry once or escalate.

A 0-byte / 1 KB file means the API returned text/an error, not image bytes — **not done**.

## Prerequisites (check first, fail loudly — don't paper over)

1. **`GEMINI_API_KEY` exported** — `[[ -n "$GEMINI_API_KEY" ]]`. This is a Google AI Studio key (`AIzaSy…`, 39 chars). It lives in `claudebase/secrets/secrets.env` (gitignored) and is sourced by `~/.zshrc`; `NANOBANANA_API_KEY` holds the same value. Get a key at <https://aistudio.google.com/apikey>. **Never inline** in the skill, a command, or a commit. Missing → tell the user to export/source it, stop.
2. **`python3` on PATH** — the REST path is pure stdlib (`urllib`), no pip installs needed.

The old `gemini` CLI + `nanobanana` extension path is **no longer used** — it targets `:generateContent`, which can't reach the Gemini 3 image models with resolution control. Ignore it for this skill.

## `--diagnose` mode

When the flow fails, walk the layers top-down:

1. **Key present & shaped right?** `[[ -n "$GEMINI_API_KEY" ]]` and starts with `AIza`. A 32-char hex string is **not** a Google key (it's a third-party wrapper key) → wrong key, stop.
2. **Key valid — text model** — `curl "…/v1beta/models/gemini-2.5-flash:generateContent?key=$GEMINI_API_KEY" -H 'Content-Type: application/json' -d '{"contents":[{"parts":[{"text":"hi"}]}]}'`. `401`/`API_KEY_INVALID` → key invalid. `429`/`RESOURCE_EXHAUSTED` → billing/quota. `503`/`500` → Google transient, retry in 60s.
3. **Image endpoint** — run the §3 call with `image_size:"1K"` (cheapest). A `400 Invalid value at response_format.*` means a bad enum value; the error message lists the supported values verbatim — read it and fix.
4. **No image bytes in a 200 response** — dump the JSON; the model may have returned a text refusal (safety) instead of an image. Rephrase the prompt.

## Known traps (verified hands-on)

- **`:generateContent` can't set resolution/aspect.** On the classic `generateContent` endpoint, `response_format.image` / `imageConfig` is rejected (`400 Invalid value at … aspect_ratio`). Resolution and aspect only work on **`/v1beta/interactions`** with the `response_format` block. This is why the skill moved off `generateContent`.
- **`input` uses the Step format, not Turn.** `/v1beta/interactions` wants `input:[{"type":"text","text":…}]` (step_list). A `{"role":"user","parts":[…]}` (turn) body 400s with "use step_list input format". A bare `{"text":…}` 400s asking for a `role` or `type` field.
- **Enum values are strict.** `image_size` accepts exactly `512 1K 2K 4K` (uppercase K); `aspect_ratio` accepts the 14 ratios + `auto`. `"16:9"` works, `"IMAGE_SIZE_2K"` / `"1024"` / `"ASPECT_RATIO_SQUARE"` all 400. When unsure, send a deliberately-wrong value once — the 400 message lists every accepted value.
- **Default output is JPEG, not PNG.** The bytes come back as a JPEG (300 DPI, e.g. 2048×2048 at 2K). Name the file `.jpg`. Don't hardcode `.png`.
- **Image bytes are at `steps[1].content[0].data`** (base64) in observed responses, but the step index can shift — walk the JSON for a long `"data"` string rather than hardcoding the path.
- **A 32-char hex key is not a Google key.** Third-party wrappers (e.g. nanobananaapi.ai) issue hex keys and use a different endpoint/auth (`Authorization: Bearer`, async task+poll). This skill targets **Google's official API** with an `AIzaSy…` key. If the key is hex, it's the wrong key for this skill.
- **The gemini CLI extension is stale relative to Google.** As of nanobanana v1.0.12 it still defaults to `-preview` model IDs and only speaks `generateContent`. Not usable for the Gemini 3 image models with resolution control — hence the direct REST path.
- **`-preview` IDs still resolve (as of 2026-07-09).** Google's docs mark `gemini-3-pro-image-preview` / `gemini-3.1-flash-image-preview` deprecated with a 2026-06-25 shutdown, but they still respond. Prefer the bare GA IDs (`gemini-3-pro-image`, `gemini-3.1-flash-image`) — they're what this skill uses.

## Never

- Put an API key in a task description, slash command, or commit. It belongs in `secrets/secrets.env` (gitignored) only.
- Claim success on stdout alone — always `test -f`.
- Silently fall back to cwd for output — resolve §1 first.

## Sources

- Live-verified 2026-07-09: both `gemini-3-pro-image` (pro) and `gemini-3.1-flash-image` (banana2) return real image bytes via `POST /v1beta/interactions`; the `image_size`/`aspect_ratio` enums and the JPEG-default behavior were confirmed by actual calls (the 400 error messages enumerate the accepted values).
- Google **Gemini API image-generation docs** — `ai.google.dev/gemini-api/docs/image-generation` (the Interactions API surface).
- Google **Gemini image prompt guide** — `deepmind.google/models/gemini-image/prompt-guide/` (5-component scene, quote-the-text rule, style vocabulary).
- Google **Nano Banana Pro prompting tips** — `blog.google/.../prompting-tips-nano-banana-pro/` (text placement, camera/lens language).

**Origin**: the original four-step flow and output-path contract come from a 2026-05-19 nano-banana debugging session (macOS). Rewritten 2026-07-09 for the Gemini 3 Nano Banana models (banana2 + pro), moving from the `gemini`-CLI/`generateContent` path to the direct `/v1beta/interactions` REST path after live-verifying the model IDs, the `response_format` schema, and the enum values.

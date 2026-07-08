---
name: video-downloader
description: |
  Download a video (YouTube or any yt-dlp-supported site) with chosen quality/format, or extract audio-only as MP3, and save it to a required, explicitly-resolved output directory. Uses yt-dlp (free, open-source) installed via Homebrew — never system pip, which is broken on this machine (Xcode python3 3.9.6). Output dir is a hard contract by caller: explicit path → that path, else $VIDEO_DL_OUTDIR, else ask.
  Triggers: 영상 다운로드, 유튜브 받기, 동영상 저장, 강의 녹화 다운로드, download video, youtube download, save video, extract audio
argument-hint: "<url> <output-dir> [--quality best|1080p|720p|480p|360p|worst] [--format mp4|webm|mkv] [--audio-only]"
level: 2
triggers:
  - "/video-downloader"
  - "video-downloader"
  - "영상 다운로드"
  - "유튜브 받기"
  - "동영상 저장"
  - "download video"
  - "youtube download"
  - "save video"
  - "extract audio"
---

# video-downloader

Download a video (or its audio track) via `yt-dlp` and save it to a **caller-specified** output directory — never a hardcoded path.

**Rigid** on two things: the output dir is *resolved before downloading* (§1) and `yt-dlp` is *installed via Homebrew, never system pip* (§2 — this machine's `python3` is Xcode's 3.9.6 and breaks on `pip install`). **Flexible** elsewhere: quality, format, audio-only, which site (yt-dlp supports far more than YouTube).

## When to invoke

- **Download**: "이 영상 다운로드해줘", "유튜브에서 이거 받아줘", "이 강의 녹화 저장해줘", "download this video", "save this youtube link"
- **Audio only**: "음성만 추출해줘", "mp3로 받아줘", "extract audio from this video"
- Typical use here: POSTECH 대학원생 워크플로 — 학회/세미나 녹화 다운로드, 오프라인 보관, 음성만 추출해 듣기.
- **Slash**: `/video-downloader <url> <output-dir> [options]`

Do **not** invoke for:
- Downloading a plain file (PDF, image, dataset) that isn't audio/video → just fetch it directly.
- Uploading or re-encoding an *existing local* file → that's a different, ffmpeg-only task.

## The two rigid steps

### 1 — Resolve the output directory (REQUIRED, before anything else)

Never let the download land in a default/hardcoded location. Resolve one absolute directory up front, by the first matching rule:

| Caller | Output directory |
|:---|:---|
| Passed an explicit path (`--output`, `-o`, "save to X") | that path |
| Human, with `$VIDEO_DL_OUTDIR` set | `$VIDEO_DL_OUTDIR` |
| Human, with a known project inbox (`_inbox/`, `assets/`, a Johnny-Decimal `91_Inbox/`) | that inbox |
| Human, none of the above | **STOP and ask where to save** |

Then, every time:
- `mkdir -p "$OUTPUT_DIR"` — a missing dir silently breaks `yt-dlp`'s `-o` template.
- Echo the resolved `$OUTPUT_DIR` back in one line *before* downloading, so the destination is auditable.

**Never** default to `/mnt/user-data/outputs` (that path is a Claude.ai web-environment artifact and does not exist on this machine or any local Mac) and never invent a scratch folder.

### 2 — Install / verify yt-dlp (REQUIRED — Homebrew only, never pip)

This machine's system `python3` is the **Xcode-bundled 3.9.6** (`/usr/bin/python3`), and `pip` is not even on PATH. Running `pip install --break-system-packages yt-dlp` either fails outright or fights a broken interpreter — do not use it.

```bash
command -v yt-dlp || brew install yt-dlp
```

- Missing `brew` → tell the user to install Homebrew first, stop.
- Already installed but stale → `brew upgrade yt-dlp` (YouTube changes frequently break old versions; this is the single most common failure mode).
- If Homebrew is genuinely unavailable and a Python path is unavoidable, use the **brew-installed** interpreter, never system `python3`: `/opt/homebrew/bin/python3.12 -m pip install --break-system-packages yt-dlp` (verify `python3.12` exists first: `command -v python3.12`). This is the fallback, not the default.

## Download

```bash
yt-dlp -f "$FORMAT_STRING" --merge-output-format "$CONTAINER" \
  -o "$OUTPUT_DIR/%(title)s.%(ext)s" --no-playlist "$URL"
```

**Quality** (flexible — pick per request, default `best`):

| Value | Format string |
|:---|:---|
| `best` (default) | `bestvideo+bestaudio/best` |
| `1080p` / `720p` / `480p` / `360p` | `bestvideo[height<=H]+bestaudio/best[height<=H]` |
| `worst` | `worstvideo+worstaudio/worst` |

**Container format** (flexible, video only): `mp4` (default, most compatible), `webm`, `mkv`.

**Audio-only** (flexible): swap the video flags for extraction —

```bash
yt-dlp -x --audio-format mp3 --audio-quality 0 \
  -o "$OUTPUT_DIR/%(title)s.%(ext)s" --no-playlist "$URL"
```

`--no-playlist` is on by default — a bare video URL never accidentally pulls an entire playlist. Drop it only if the user explicitly asks for the whole playlist.

## Verify on disk

```bash
ls -la "$OUTPUT_DIR"/*.{mp4,webm,mkv,mp3} 2>/dev/null
```

File exists and is non-trivial size → success, report the absolute path. Missing file despite a "complete" message → re-run with `-v` for verbose output and diagnose (usually a site-side format change; `brew upgrade yt-dlp` first).

## Never

- Hardcode `/mnt/user-data/outputs` or any other Claude.ai-web-only path.
- Install yt-dlp via system `python3`/pip on this machine (Xcode 3.9.6 breaks ≥3.10 packages; yt-dlp itself is fine on older Python, but Homebrew avoids the whole interpreter question).
- Download playlists silently when the user asked for a single video.

<!-- Adapted from ComposioHQ/awesome-claude-skills video-downloader, 2026-07-09 -->

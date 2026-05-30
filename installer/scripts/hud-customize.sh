#!/usr/bin/env bash
# hud-customize.sh — re-apply local HUD wrapper customizations.
#
# OMC's `/oh-my-claudecode:hud setup` regenerates ~/.claude/hud/omc-hud.mjs from
# the plugin's canonical template, dropping any local edits. This script
# re-injects the line1 customization (cwd -> cyan "dir:", branch label -> cyan,
# model -> cyan versioned "model:opus 4.7" plus a cyan "effort:<level>" segment,
# both read from the statusline stdin JSON and re-injected so the plugin still
# sees its input) that the omcHud config schema cannot express.
#
# Idempotent: if the marker is already present, it does nothing. Safe to run on
# every install and after any `hud setup`.
set -euo pipefail

CLAUDE_HOME="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
WRAPPER="$CLAUDE_HOME/hud/omc-hud.mjs"
MARKER="OMC HUD local customization"

if [[ ! -f "$WRAPPER" ]]; then
  echo "[hud-customize] wrapper not found ($WRAPPER) — run /oh-my-claudecode:hud setup first"
  exit 0
fi

if grep -qF "$MARKER" "$WRAPPER"; then
  echo "[hud-customize] already applied — skipping"
  exit 0
fi

# Two injection points are required because the wrapper does a top-level
# `await import()` of config-dir.mjs (ANCHOR_HELPERS, below). That top-level
# await drains the statusline stdin pipe — any readFileSync(0) AFTER it returns
# empty. So the stdin grab MUST run before that dynamic import. We anchor it to
# the synchronous `__dirname` line (ANCHOR_STDIN), which sits just above it.
ANCHOR_STDIN='const __dirname = dirname(__filename);'
ANCHOR_HELPERS='const { getClaudeConfigDir } = await import(pathToFileURL(join(__dirname, "lib", "config-dir.mjs")).href);'

# ── Block 1: stdin grab + re-injection — injected BEFORE the dynamic import. ──
read -r -d '' STDIN_GRAB <<'EOF' || true

// ── OMC HUD local customization: stdin grab (user-applied) ──
// The plugin renders the model in `short` form ("Opus" — no version) and never
// surfaces the reasoning effort at all, even though the statusline stdin JSON
// carries both `model.display_name` ("Opus 4.7 (1M context)") and `effort.level`
// ("xhigh"). Rather than chase the plugin's (env-dependent, sometimes stale)
// stdin cache files, we read the SAME stdin the plugin will read — directly and
// synchronously — then hand the bytes back by replacing process.stdin with a
// stream that re-emits them. This MUST run before the top-level `await import`
// below: that await drains the stdin pipe, after which readFileSync(0) is empty.
// __hudExtras is consumed by customizeHudOutput() further down.
// NOTE: the wrapper is an ES module (top-level await / import.meta), so CommonJS
// `require` is undefined here — these MUST be static `import`s. ESM hoists them
// above the IIFE, and static imports (unlike the dynamic one below) do not touch
// the stdin pipe, so the synchronous readFileSync(0) still gets the full payload.
import { readFileSync as __hudReadFileSync } from "node:fs";
import { Readable as __HudReadable } from "node:stream";
const __hudExtras = (() => {
  try {
    const readFileSync = __hudReadFileSync;
    const Readable = __HudReadable;
    let raw = "";
    try { raw = readFileSync(0, "utf8"); } catch { raw = ""; }

    // Re-inject the bytes so the plugin's `for await (const chunk of
    // process.stdin)` still sees the full payload. process.stdin is a getter,
    // so a plain assignment is ignored — defineProperty is required. isTTY:false
    // keeps the plugin off its TTY-empty branch.
    if (raw) {
      const replacement = Readable.from([raw]);
      replacement.isTTY = false;
      Object.defineProperty(process, "stdin", { value: replacement, configurable: true });
    }

    const j = raw ? JSON.parse(raw) : {};
    const rawName = j?.model?.display_name || j?.model?.id || null;
    // Lowercase and drop the trailing "(… context)" qualifier so the segment
    // stays compact: "Opus 4.7 (1M context)" -> "opus 4.7".
    const model = rawName
      ? rawName.toLowerCase().replace(/\s*\([^)]*\)\s*$/, "").trim()
      : null;
    const effort = j?.effort?.level || null;
    return { model, effort };
  } catch {
    return { model: null, effort: null };
  }
})();
EOF

# ── Block 2: stdout transform — injected AFTER the config-dir import line. ──
read -r -d '' TRANSFORM <<'EOF' || true

// ── OMC HUD local customization: stdout transform (user-applied) ──
// The plugin renderers hardcode the cwd (dim, no prefix), git branch (dim
// "branch:" label), and model (cyan "Model: <Name>") segments; none of the
// "dir:" prefix, cyan unification, lowercase model, or effort segment is exposed
// via the omcHud config. We therefore rewrite the plugin's stdout here. Re-running
// /oh-my-claudecode:hud setup regenerates this file and DROPS both blocks;
// claudebase install.sh re-applies them via installer/scripts/hud-customize.sh.
const CYAN = "\x1b[36m";
const RESET = "\x1b[0m";

function customizeHudOutput(text) {
  // All line1 accent elements (repo/branch/model/skills/hostname) render in
  // cyan, so dir and branch are unified to cyan too for visual consistency.
  text = text.replace(
    /^\x1b\[2m([^\x1b]+)\x1b\[0m/,
    (_m, dir) => `${CYAN}dir:${dir}${RESET}`,
  );
  text = text.replace(
    /\x1b\[2mbranch:\x1b\[0m\x1b\[36m([^\x1b]+)\x1b\[0m/,
    (_m, name) => `${CYAN}branch:${name}${RESET}`,
  );
  const { model: versionedModel, effort } = __hudExtras;
  text = text.replace(
    /\x1b\[36mModel: ([^\x1b]+)\x1b\[0m/,
    (_m, name) => {
      // Prefer the versioned name from stdin; fall back to the plugin's short name.
      const label = versionedModel || name.toLowerCase();
      const effortSeg = effort ? `\x1b[2m | \x1b[0m${CYAN}effort:${effort}${RESET}` : "";
      return `${CYAN}model:${label}${RESET}${effortSeg}`;
    },
  );
  return text;
}
EOF

# Stdout interception block, injected just before the final `main();` call.
read -r -d '' INTERCEPT <<'EOF' || true
// Intercept the plugin HUD's stdout so customizeHudOutput() can rewrite the
// dir/branch/model segments, then flush the transformed text on process exit.
const __origStdoutWrite = process.stdout.write.bind(process.stdout);
let __hudBuffer = "";
process.stdout.write = (chunk, ...rest) => {
  __hudBuffer += typeof chunk === "string" ? chunk : chunk.toString();
  const cb = rest.find((a) => typeof a === "function");
  if (cb) cb();
  return true;
};
process.on("exit", () => {
  process.stdout.write = __origStdoutWrite;
  if (__hudBuffer) __origStdoutWrite(customizeHudOutput(__hudBuffer));
});

main();
EOF

# Apply all injections with a small node script (avoids brittle sed escaping).
node - "$WRAPPER" "$ANCHOR_STDIN" "$STDIN_GRAB" "$ANCHOR_HELPERS" "$TRANSFORM" "$INTERCEPT" <<'NODE'
const fs = require("fs");
const [file, anchorStdin, stdinGrab, anchorHelpers, transform, intercept] = process.argv.slice(2);
let src = fs.readFileSync(file, "utf8");

const requireUnique = (needle, label) => {
  const first = src.indexOf(needle);
  if (first < 0) {
    console.error(`[hud-customize] ${label} not found — wrapper format changed; aborting`);
    process.exit(1);
  }
  if (src.indexOf(needle, first + needle.length) >= 0) {
    console.error(`[hud-customize] ${label} is not unique — cannot anchor safely; aborting`);
    process.exit(1);
  }
};
requireUnique(anchorStdin, "stdin anchor line");
requireUnique(anchorHelpers, "helpers anchor line");

// Block 1 (stdin grab) goes BEFORE the dynamic import — anchored to __dirname.
src = src.replace(anchorStdin, anchorStdin + stdinGrab);
// Block 2 (stdout transform) goes AFTER the config-dir import line.
src = src.replace(anchorHelpers, anchorHelpers + transform);
// Replace the standalone `main();` invocation with the interception block.
if (!/^main\(\);\s*$/m.test(src)) {
  console.error("[hud-customize] could not find `main();` call — aborting");
  process.exit(1);
}
src = src.replace(/^main\(\);\s*$/m, intercept);
fs.writeFileSync(file, src);
console.log("[hud-customize] applied line1 customization (stdin grab + stdout transform)");
NODE

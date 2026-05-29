#!/usr/bin/env bash
# hud-customize.sh — re-apply local HUD wrapper customizations.
#
# OMC's `/oh-my-claudecode:hud setup` regenerates ~/.claude/hud/omc-hud.mjs from
# the plugin's canonical template, dropping any local edits. This script
# re-injects the line1 customization (cwd -> cyan "dir:", branch label -> cyan,
# model -> lowercase "model:") that the omcHud config schema cannot express.
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

# Inject the transform helper after the config-dir import line.
ANCHOR='const { getClaudeConfigDir } = await import(pathToFileURL(join(__dirname, "lib", "config-dir.mjs")).href);'

read -r -d '' TRANSFORM <<'EOF' || true

// ── OMC HUD local customization (user-applied post-processing) ──
// The plugin renderers hardcode the cwd (dim, no prefix), git branch (dim
// "branch:" label), and model (cyan "Model: <Name>") segments; none of the
// "dir:" prefix, cyan unification, or lowercase model is exposed via the omcHud
// config. We therefore rewrite the plugin's stdout here. Re-running
// /oh-my-claudecode:hud setup regenerates this file and DROPS this block;
// claude-settings install.sh re-applies it via claude/scripts/hud-customize.sh.
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
  text = text.replace(
    /\x1b\[36mModel: ([^\x1b]+)\x1b\[0m/,
    (_m, name) => `${CYAN}model:${name.toLowerCase()}${RESET}`,
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

# Apply both injections with a small node script (avoids brittle sed escaping).
node - "$WRAPPER" "$ANCHOR" "$TRANSFORM" "$INTERCEPT" <<'NODE'
const fs = require("fs");
const [file, anchor, transform, intercept] = process.argv.slice(2);
let src = fs.readFileSync(file, "utf8");
if (!src.includes(anchor)) {
  console.error("[hud-customize] anchor line not found — wrapper format changed; aborting");
  process.exit(1);
}
src = src.replace(anchor, anchor + transform);
// Replace the standalone `main();` invocation with the interception block.
if (!/^main\(\);\s*$/m.test(src)) {
  console.error("[hud-customize] could not find `main();` call — aborting");
  process.exit(1);
}
src = src.replace(/^main\(\);\s*$/m, intercept);
fs.writeFileSync(file, src);
console.log("[hud-customize] applied line1 customization");
NODE

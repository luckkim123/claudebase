#!/usr/bin/env node
/**
 * claudebase runner for the vendored GateGuard hook.
 *
 * WHY THIS EXISTS. `gateguard-fact-force.js` ends at `module.exports = { run }`
 * — it never reads stdin, never writes stdout, never sets an exit code. Wiring
 * it into settings.json directly is a **silent no-op**: `node
 * gateguard-fact-force.js < payload` exits 0 with empty stdout and the gate
 * never fires. Measured before wiring, 2026-08-10. Upstream avoids this with
 * `scripts/hooks/run-with-flags.js`, which also carries ECC's standard/strict
 * hook-profile machinery — a second enable/flag system next to claudebase's
 * own — so this is the 20-line half of that file we actually need.
 *
 * The contract, read off the hook's own returns:
 *   deny                  -> { stdout: "<json>", exitCode: 0 }
 *   state-write failed    -> { stderr: "...",    exitCode: 0 }   (fails open)
 *   allow                 -> the raw input string, unchanged
 *
 * A returned string means allow, and it must NOT be echoed: stdout on a
 * PreToolUse hook is parsed as a decision document, so replaying the payload
 * there would be read as a malformed decision rather than as silence.
 *
 * Kill switches, in order of bluntness:
 *   OMC_SKIP_HOOKS=gateguard   this runner exits immediately (claudebase-wide convention)
 *   ECC_GATEGUARD=off          the hook itself allows everything
 *   GATEGUARD_EXEMPT_GLOBS     comma-separated globs never gated
 */
'use strict';

const skipped = (process.env.OMC_SKIP_HOOKS || '')
  .split(',')
  .map((s) => s.trim())
  .filter(Boolean);
if (skipped.includes('gateguard') || process.env.DISABLE_OMC) {
  process.exit(0);
}

let raw = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => {
  raw += chunk;
});
process.stdin.on('end', () => {
  let result;
  try {
    // Never let a hook defect block the tool call it was meant to guard.
    result = require('./gateguard-fact-force.js').run(raw);
  } catch (err) {
    process.stderr.write(`[gateguard] hook error, allowing: ${err && err.message}\n`);
    process.exit(0);
  }

  if (typeof result === 'string' || result == null) {
    process.exit(0); // allow — emit nothing
  }
  if (result.stdout) process.stdout.write(result.stdout);
  if (result.stderr) process.stderr.write(String(result.stderr) + '\n');
  process.exit(typeof result.exitCode === 'number' ? result.exitCode : 0);
});

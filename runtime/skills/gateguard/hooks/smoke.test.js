#!/usr/bin/env node
/**
 * claudebase-local smoke check for the vendored GateGuard hook.
 *
 * Upstream's gateguard-fact-force.test.js needs ECC's scripts/hooks/run-with-flags.js
 * profile runner, which we deliberately did not vendor (it carries ECC's
 * standard/strict hook-profile machinery, a second flag system next to
 * claudebase's own). That test is kept as upstream's behavioural spec but cannot
 * run here.
 *
 * This file is the smallest thing that fails if the gate stops gating: it calls
 * module.exports.run() directly, which is the same entry point run-with-flags
 * prefers, and asserts the three properties that matter before anyone wires the
 * hook into config/settings.json.
 *
 *   node smoke.test.js     → exit 0 on pass, 1 on failure
 */
'use strict';

const assert = require('assert');
const os = require('os');
const path = require('path');
const fs = require('fs');

// Isolate state: the hook persists per-file "already gated" bookkeeping under
// GATEGUARD_STATE_DIR (default $HOME/.gateguard), so without this the real
// session's state would decide the test's outcome — and the test would write
// into it.
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'gateguard-smoke-'));
process.env.GATEGUARD_STATE_DIR = path.join(tmp, 'state');
delete process.env.ECC_GATEGUARD;
delete process.env.GATEGUARD_EXEMPT_GLOBS;

const { run } = require('./gateguard-fact-force.js');

const sessionId = 'smoke-session';
const payload = (toolName, input) =>
  JSON.stringify({ session_id: sessionId, cwd: tmp, tool_name: toolName, tool_input: input });

// The hook wraps its verdict as { stdout: "<json>" } (denyResult) and returns the
// raw input unchanged on allow — so "no stdout field" means allowed.
const verdictOf = (result) => {
  if (!result || typeof result === 'string') return null;
  if (typeof result.stdout !== 'string') return null;
  return JSON.parse(result.stdout)?.hookSpecificOutput ?? null;
};
const decisionOf = (result) => verdictOf(result)?.permissionDecision ?? null;

let failures = 0;
const check = (name, fn) => {
  try {
    fn();
    console.log(`  ok    ${name}`);
  } catch (err) {
    failures += 1;
    console.error(`  FAIL  ${name}\n        ${err.message}`);
  }
};

console.log('=== gateguard smoke (claudebase) ===');

check('denies the first Edit of a file', () => {
  const decision = decisionOf(run(payload('Edit', { file_path: path.join(tmp, 'a.ts') })));
  assert.strictEqual(decision, 'deny', `expected deny, got ${decision}`);
});

check('deny reason names the facts it wants', () => {
  const reason = verdictOf(run(payload('Edit', { file_path: path.join(tmp, 'b.ts') })))
    ?.permissionDecisionReason ?? '';
  assert.match(reason, /import|require/i, 'reason should ask for importers');
  assert.match(reason, /verbatim|instruction/i, 'reason should ask for the user instruction');
});

check('a second Edit of the same file is allowed (no retry loop)', () => {
  const file = path.join(tmp, 'twice.ts');
  assert.strictEqual(decisionOf(run(payload('Edit', { file_path: file }))), 'deny', 'first touch must deny');
  assert.strictEqual(decisionOf(run(payload('Edit', { file_path: file }))), null, 'retry must be allowed');
});

check('a destructive Bash command is denied', () => {
  const decision = decisionOf(run(payload('Bash', { command: 'rm -rf /some/tree' })));
  assert.strictEqual(decision, 'deny', `expected deny, got ${decision}`);
});

check('ECC_GATEGUARD=off disables the gate', () => {
  process.env.ECC_GATEGUARD = 'off';
  try {
    const decision = decisionOf(run(payload('Edit', { file_path: path.join(tmp, 'c.ts') })));
    assert.notStrictEqual(decision, 'deny', 'kill switch must not deny');
  } finally {
    delete process.env.ECC_GATEGUARD;
  }
});

fs.rmSync(tmp, { recursive: true, force: true });

console.log(failures === 0 ? 'PASS' : `FAIL (${failures})`);
process.exit(failures === 0 ? 0 : 1);

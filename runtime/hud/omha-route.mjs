// Resolve the lane this session most recently routed to, for the HUD's `route:`
// segment, by tail-scanning the session transcript.
//
// Why the transcript and not `.omha/routing.jsonl`: that log is written by omha's
// Stop hook, so it is always one turn behind, and it only exists in projects that
// opted in with `mkdir .omha` (measured 2026-08-23: 2 of 7 local repos). The
// statusline's stdin carries `transcript_path` directly, which has neither limit.
//
// Two hard constraints. The statusline runs on EVERY render, so the file is read
// backward in chunks and the walk stops at the first hit rather than parsing the
// whole thing — transcripts reach tens of MB. And a statusline that throws takes
// the whole HUD line with it, so every path here returns null instead of raising.
//
// A fixed tail window does NOT work here, which is worth stating because it is the
// obvious first implementation. The ROUTE is declared at the START of a turn and
// every tool result for that turn lands after it, so on a long work turn the
// declaration ends up deep in the file. Measured 2026-08-23 on two live sessions:
// the last assistant-text ROUTE sat 442 KB and 1.29 MB from EOF. A 128 KB window
// found neither, and returned null exactly as if nothing had been declared.
//
// NOTE: LANE_RE mirrors omha's route_log.py:28 and the text-block extraction
// mirrors route_guard.py:56. Cross-language, so they cannot share an
// implementation — changing the ROUTE format means changing it in both repos.
import { openSync, fstatSync, readSync, closeSync } from "node:fs";

const CHUNK_BYTES = 256 * 1024;
// Enough for the deepest declaration measured (1.29 MB) with room to spare. Past
// this the walk gives up and the segment goes blank rather than stalling a render.
const SCAN_CAP_BYTES = 8 * 1024 * 1024;
const NEWLINE = 0x0a;

// Matches `> **ROUTE →** omc · why`, `ROUTE: omc`, and `ROUTE -> omc`.
const LANE_RE = /ROUTE\s*(?:->|→|:)\**\s*([a-z][a-z0-9-]*)/;

export const LANE_ABBREV = {
  "oh-my-claudecode": "omc",
  "oh-my-project": "omp",
  "oh-my-scholar": "oms",
  "oh-my-docs": "omd",
  "oh-my-experiments": "omx",
  superpowers: "sp",
  "handle-directly": "direct",
};

/** Yield the file's lines from last to first, reading backward in chunks.
 *
 *  Works on Buffers rather than decoding each chunk to a string: a chunk boundary
 *  lands mid-codepoint often enough in a Korean transcript, and decoding per chunk
 *  turns those bytes into U+FFFD before they can be rejoined. Only complete lines
 *  are decoded. */
function* linesBackward(path) {
  const fd = openSync(path, "r");
  try {
    let pos = fstatSync(fd).size;
    let scanned = 0;
    let carry = Buffer.alloc(0); // bytes of a line that starts in an earlier chunk
    while (pos > 0 && scanned < SCAN_CAP_BYTES) {
      const len = Math.min(CHUNK_BYTES, pos);
      pos -= len;
      scanned += len;
      const raw = Buffer.allocUnsafe(len);
      readSync(fd, raw, 0, len, pos);
      const buf = carry.length ? Buffer.concat([raw, carry]) : raw;
      let end = buf.length;
      for (let i = buf.length - 1; i >= 0; i--) {
        if (buf[i] !== NEWLINE) continue;
        if (end > i + 1) yield buf.subarray(i + 1, end).toString("utf8");
        end = i;
      }
      carry = buf.subarray(0, end);
    }
    // Only a walk that reached byte 0 has a complete first line; a walk stopped by
    // the cap is holding a fragment, which would just fail to parse.
    if (pos === 0 && carry.length) yield carry.toString("utf8");
  } finally {
    closeSync(fd);
  }
}

function assistantText(rec) {
  if (rec?.type !== "assistant") return "";
  const content = rec?.message?.content;
  if (!Array.isArray(content)) return "";
  return content
    .filter((b) => b?.type === "text")
    .map((b) => b.text || "")
    .join("");
}

/** The most recently declared lane, or null. Walks backward, so on a turn that
 *  re-routed mid-flight the LAST declaration wins — that is the live one.
 *
 *  Deliberately does NOT stop at the turn boundary. Since omha 0.9.0 a pure-chat
 *  turn declares nothing at all, so stopping there would blank the segment for
 *  the ~54% of turns that call no tool. Carrying the last known lane forward is
 *  the useful reading of "what am I routed to". */
export function laneFromTranscript(path) {
  try {
    for (const line of linesBackward(path)) {
      const text = line.trim();
      if (!text) continue;
      let rec;
      try {
        rec = JSON.parse(text);
      } catch {
        continue; // metadata records and any fragment the cap left behind
      }
      const m = LANE_RE.exec(assistantText(rec));
      if (m) return m[1];
    }
  } catch {
    // fall through — the HUD must render even with no readable transcript
  }
  return null;
}

/** Short label for the HUD, or null when nothing has been declared yet. */
export function routeSegment(path) {
  const lane = laneFromTranscript(path);
  if (!lane) return null;
  return LANE_ABBREV[lane] || lane;
}

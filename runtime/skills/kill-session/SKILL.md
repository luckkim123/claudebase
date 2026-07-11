---
name: kill-session
description: 'Use when the user wants to terminate/remove the CURRENT background session it is invoked in, or asks how to make a background session disappear from the `claude agents` list. Triggers on "/kill-session", "이 세션 삭제", "이 세션 종료하고 지워", "background session 삭제", "kill this session", "remove this background session", "이 백그라운드 세션 없애줘". IMPORTANT: a background session CANNOT delete itself non-interactively — the daemon respawns it. This skill explains why and points to the one path that works (the `claude agents` TUI). It never touches any other session.'
triggers:
  - "/kill-session"
  - "kill-session"
  - "이 세션 삭제"
  - "이 세션 종료하고 지워"
  - "이 세션 없애"
  - "이 백그라운드 세션 삭제"
  - "이 백그라운드 세션 없애"
  - "background session 삭제"
  - "kill this session"
  - "remove this background session"
  - "delete this session"
---

# kill-session

**A background session cannot delete itself. Do not try — you will trigger an infinite respawn loop.** This skill exists to explain that, and to point at the one path that actually removes a background session.

## The hard truth (verified 2026-07-11, this exact session)

The background daemon (`claude daemon`, a supervisor process) holds a **lease** for every background session, in its own **process memory** — not in any file. As long as that lease is live, the daemon keeps the session alive: if the worker process dies, the daemon claims a fresh worker from its spare pool and re-attaches the session to it. The daemon log shows this as `bg claimed-spare <id> (fleet)` and the terminal shows `[worker crashed (exit 143) — respawning…]`.

Consequences, all confirmed by experiment:

- **`kill <worker-pid>` does not work.** SIGTERM (exit 143) makes the daemon respawn the session from the spare pool within ~1s. Loops forever.
- **`rm -rf $CLAUDE_JOB_DIR` does not work.** The job dir (`state.json` with `respawnFlags`, the rendezvous socket) is *reconstructed* on respawn. It is a cache of the lease, not the lease itself. Deleting it changes nothing.
- **Deleting the rendezvous socket does not work.** Same reason.

The lease lives in the supervisor's memory and is only released through the daemon's control socket — which the `claude agents` TUI drives. That TUI requires a real TTY (`claude agents` refuses to run when stdout is not a TTY). A background session **has no TTY**, so it cannot issue the release for itself. This is a structural dead end, not a missing flag.

## What actually removes a background session

Tell the user to do **one** of these (they act from a real terminal, not from inside the background session):

1. **`claude agents` (interactive TUI).** Open it in a terminal, select the target session, and use the TUI's terminate/remove action. This is the *only* clean, single-session path — it releases the daemon lease so the session does not respawn, then clears it from the list.

2. **`claude daemon stop` — only if removing ALL background sessions is acceptable.** This shuts down the supervisor and terminates every background session at once (add `--keep-workers` to leave detached workers running). Do not suggest this when other live sessions must survive — check `claude agents --json` first; right now unrelated sessions are usually running.

After the session is gone, its `~/.claude/jobs/<id>/` dir can be removed if it lingers (only once the daemon no longer holds the lease — i.e. after step 1 or 2).

## What this skill must NOT do

- **Never run `kill` on the session's own worker, and never `rm -rf $CLAUDE_JOB_DIR`, to "delete this session".** Both fail and the kill path spins the respawn loop that spams `[worker crashed — respawning…]`. This was the original (wrong) implementation; it is preserved here as a warning, not an instruction.
- **Never touch another session.** Scope, if anything is ever done at the file level, is strictly `$CLAUDE_JOB_DIR` — and even that only *after* the lease is released elsewhere.

## Bulk cleanup of already-dead sessions (a different task)

Removing sessions that are **already terminated** (no live worker, no lease) is safe and file-based — this is what "지워줘" usually means when several stale entries pile up:

1. `claude agents --json` → note which ids are live (`status: busy`/`idle` with a real pid).
2. For every `~/.claude/jobs/<id>/` whose id is **not** in that live set, `rm -rf` it.
3. Leave live ones and the current session alone.

That works because dead sessions have no lease for the daemon to respawn from. Live ones do — which is the whole point above.

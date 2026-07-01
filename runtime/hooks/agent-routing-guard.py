#!/usr/bin/env python3
"""Block research-shaped Agent calls dispatched to a non-research subagent.

Failure mode this hook addresses (diagnosed 2026-06-30 from a handoff prompt
documenting a live session):

  The user had saturated the *text* layer of routing control — an omha
  `<omha-routing>` card injected every turn ("re-route every turn", "topic
  continuity != routing continuity", "stop before delegating with Agent/Task
  and re-decide the lane"), domain routing cards, and explicit `<delegation_rules>`
  in CLAUDE.md ("literature/material research -> document-specialist"). Despite
  all of it, the model dispatched literature/web research to `general-purpose`
  FOUR times in a row, by inertia, never re-deciding the lane at dispatch time.

  This is the same lesson the sibling askuserquestion-guard.py already learned:
  prose self-instruction is NOT load-bearing. A text rule shifts the action
  probability distribution; it does not make the wrong action impossible. The
  omha card warns *at turn start* (UserPromptSubmit), but the leak happens *at
  Agent-dispatch time*, dozens of tokens later, where no check exists. This hook
  closes exactly that gap with a deterministic gate at the dispatch point.

What it does (PreToolUse, matcher = "Agent"):
  - Reads tool_input {description, prompt, subagent_type} — the same shape the
    harness delivers for Agent calls (verified against transcript tool_use blocks
    on 2026-06-30: keys = ['description','prompt','subagent_type']).
  - Decides "is this a research task?" by requiring BOTH an action signal AND an
    object signal (a single keyword is deliberately not enough — that is the
    false-positive guard). See _is_research.
  - If it is research AND the subagent_type is NOT one of the research-suited
    agents (allow-list, not deny-list), it denies with a correction message.
  - Escape hatch: if the prompt contains the literal token `ROUTING_OK:` the
    call passes unconditionally — a legitimate exception (research keywords that
    happen to appear in a non-research task) can be declared in one line. The
    deny keeps its force (inertia copies are blocked) while a justified
    exception is never permanently blocked (which would risk the user disabling
    the gate -> 0 protection).

What it deliberately does NOT gate (cost-benefit line, per the handoff):
  - Weak research signal (0-1 keyword): ambiguous code-reading tasks like
    "see how this works" are indistinguishable from legitimate general-purpose
    use, so they pass. False-positive cost there exceeds the benefit.
  - Code-modification-in-main-session: a separate, harder-to-pattern boundary;
    out of scope by user decision.
  - Non-Agent research paths (a one-off WebFetch/WebSearch): not a delegation,
    not this hook's concern.

Known residual leaks this gate canNOT catch (stated honestly):
  (a) research phrased without research keywords;
  (b) ROUTING_OK abuse;
  (c) research done outside Agent.
So this lowers the leak rate substantially; it does not make it zero.

fail-open: any stdin/parse error or unexpected exception -> return 0 (allow).
A hook bug must never block a session.

Idempotent marker in the settings command field: AGENT_ROUTING_GUARD
Hook event: PreToolUse (matcher = "Agent")
Stdin schema: https://code.claude.com/docs/en/hooks
  - tool_name: str
  - tool_input: dict  (the model's intended arguments)
  - cwd, session_id: str  (standard; used for best-effort deny telemetry)
"""
import json
import os
import sys


# --- research-intent detection -------------------------------------------------
# Two categories. A task is "research" only when BOTH fire. Requiring both is the
# false-positive guard: a single stray keyword (e.g. "compare these two configs"
# in a pure code task) must not trip the gate. Lowercased substring match.
ACTION_SIGNALS = (
    # English
    "research", "literature", "survey", "best practice", "best-practice",
    "look up", "find out how", "investigate", "compare ", " vs ", "state of the art",
    "state-of-the-art", "prior art", "how do others", "how others",
    # Korean
    "조사", "문헌", "자료조사", "리서치", "비교", "선행연구", "베스트", "최신 패턴",
    "어떻게 하는지 조사", "찾아봐", "알아봐",
)

OBJECT_SIGNALS = (
    # English
    "web", "arxiv", "github", "paper", "papers", "library", "libraries",
    "repo", "repository", "external", "online", "documentation", "official docs",
    "blog", "publication",
    # Korean
    "웹", "논문", "라이브러리", "외부", "공식문서", "공식 문서", "온라인", "깃허브",
)

# Allow-list of subagent_types suited to research. If a research-shaped call goes
# to anything NOT in this set (general-purpose, the default Agent, executor, ...),
# it is denied. Allow-list (not deny-list) so new general agents fail safe.
# Matched as a substring of the lowercased subagent_type, so both the short form
# ("explore") and the plugin-qualified form ("oh-my-claudecode:explore") match.
RESEARCH_AGENTS = (
    "document-specialist",
    "external-context",
    "scientist",
    "explore",          # also matches "Explore" and "oh-my-claudecode:explore"
    "document-finder",
)

BYPASS_TOKEN = "ROUTING_OK:"

REASON = (
    "Research-shaped Agent call routed to a non-research subagent — blocked.\n"
    "Your prompt/description reads as a literature / web / external-repo research "
    "task, but subagent_type is a general agent (e.g. general-purpose). Per "
    "~/.claude/CLAUDE.md <delegation_rules> and the omha routing card, outbound "
    "research must go to a research-suited agent, not a catch-all.\n"
    "Re-emit ONE of these ways:\n"
    "1. Use a research agent: subagent_type = 'oh-my-claudecode:document-specialist' "
    "(repo docs first, then Context Hub / chub, graceful web fallback), or "
    "'Explore' for codebase search, or 'oh-my-claudecode:scientist' for analysis. "
    "Better yet, for outbound multi-source research invoke the "
    "oh-my-claudecode:external-context skill instead of a raw Agent call.\n"
    "2. If this genuinely is NOT research (the keywords are incidental and "
    "general-purpose is correct), declare it: put 'ROUTING_OK: <one-line reason>' "
    "anywhere in the prompt and re-emit. That bypasses this gate for this call.\n"
    "Do not copy the previous turn's subagent_type by inertia — re-decide the "
    "lane at THIS dispatch (the exact failure this gate guards against)."
)


def _is_research(text: str) -> bool:
    """True only when the text carries BOTH an action signal and an object
    signal. Requiring both categories is the false-positive guard."""
    t = text.lower()
    has_action = any(k in t for k in ACTION_SIGNALS)
    has_object = any(k in t for k in OBJECT_SIGNALS)
    return has_action and has_object


def _log_deny(cwd, session_id) -> None:
    """Best-effort telemetry: one line per deny, mirroring askuserquestion-guard's
    log so the same tooling can fold these counts in. Never raises."""
    try:
        log_dir = os.path.join(cwd or ".", ".omc", "logs")
        os.makedirs(log_dir, exist_ok=True)
        path = os.path.join(log_dir, "agent_routing_guard.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(
                {"signal": "denied_agent_routing", "session_id": session_id},
                ensure_ascii=False) + "\n")
    except Exception:
        pass


def _deny(reason: str, cwd=None, session_id=None) -> int:
    _log_deny(cwd, session_id)
    sys.stdout.write(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    return 0


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0  # malformed stdin -> never block on a hook bug

    # The harness currently emits tool_name "Agent" for the Agent/Task tool
    # (verified 2026-06-30: 12x "Agent" vs 1x "Task" across recent sessions).
    # Accept both so a future rename does not silently disable the gate.
    if payload.get("tool_name") not in ("Agent", "Task"):
        return 0  # matcher should prevent this, but be defensive

    cwd = payload.get("cwd")
    session_id = payload.get("session_id")

    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return 0

    prompt = tool_input.get("prompt") or ""
    if not isinstance(prompt, str):
        prompt = ""
    description = tool_input.get("description") or ""
    if not isinstance(description, str):
        description = ""

    # Explicit bypass: a justified exception declared in one line.
    if BYPASS_TOKEN in prompt or BYPASS_TOKEN in description:
        return 0

    subagent_type = (tool_input.get("subagent_type") or "")
    if not isinstance(subagent_type, str):
        subagent_type = ""
    sub = subagent_type.lower()

    blob = f"{description}\n{prompt}"
    if _is_research(blob) and not any(a in sub for a in RESEARCH_AGENTS):
        return _deny(REASON, cwd, session_id)

    # Not research, or research already going to a research agent -> allow.
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Tests for installer/scripts/register_mcp.py.

The regression these pin down: `~/.claude/mcp.json` is rendered by the installer
and read by nothing — Claude Code loads user-scope MCP servers from
`~/.claude.json` only. Registration therefore has to go through `claude mcp add`,
and the decisions that matter are which entries to add (never re-adding one that
exists, since that would discard a per-machine edit) and how a bare command name
becomes an absolute path (hooks and MCP servers get no login-shell PATH).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "installer" / "scripts"))

import register_mcp as rm

# `sh` stands in for any real binary: it resolves on every machine that can run
# these tests, so the fixture exercises the resolve path without mocking it.
CONFIG = {
    "$comment": "documentation, not a server",
    "globalServers": {
        "arxiv": {"command": "sh", "args": ["-c", "true"]},
        "tokensave": {"command": "sh", "args": ["serve"]},
    },
}


class TestPlan:
    def test_registers_servers_the_machine_does_not_have(self):
        to_add, skipped, bad = rm.plan(CONFIG, existing=set())
        assert [name for name, _, _ in to_add] == ["arxiv", "tokensave"]
        assert skipped == [] and bad == []

    def test_existing_server_is_left_alone(self):
        # Re-adding would mean remove+add, silently discarding a deliberate
        # per-machine edit (a different binary path, an extra -e).
        to_add, skipped, _ = rm.plan(CONFIG, existing={"arxiv"})
        assert [name for name, _, _ in to_add] == ["tokensave"]
        assert skipped == ["arxiv"]

    def test_meta_keys_are_not_servers(self):
        # `$comment` sits beside real entries at the top level; `$note` inside
        # one. Neither may be registered.
        config = {"globalServers": {"$note": "hi", "real": {"command": "sh"}}}
        to_add, _, bad = rm.plan(config, existing=set())
        assert [name for name, _, _ in to_add] == ["real"]
        assert bad == []

    def test_unresolved_secret_placeholder_is_refused(self):
        # Registering this would bake the literal "${TOKEN}" into ~/.claude.json,
        # where it fails at connect time rather than here.
        config = {"globalServers": {"x": {"command": "sh", "env": {"K": "${TOKEN}"}}}}
        to_add, _, bad = rm.plan(config, existing=set())
        assert to_add == []
        assert bad[0][0] == "x" and "placeholder" in bad[0][1]

    def test_missing_binary_is_reported_not_registered(self):
        config = {"globalServers": {"x": {"command": "definitely-not-installed-xyz"}}}
        to_add, _, bad = rm.plan(config, existing=set())
        assert to_add == []
        assert bad[0][0] == "x" and "not found" in bad[0][1]


class TestAddCommand:
    def test_argv_puts_env_before_name_and_command_after_the_separator(self):
        argv = rm.add_command(
            "srv", {"args": ["serve", "--flag"], "env": {"K": "v"}}, "/abs/bin/srv"
        )
        assert argv == [
            "claude", "mcp", "add", "--transport", "stdio", "--scope", "user",
            "-e", "K=v", "srv", "--", "/abs/bin/srv", "serve", "--flag",
        ]

    def test_resolved_absolute_path_is_used_not_the_bare_name(self):
        # The whole point of resolve_command: a bare name that works in the
        # user's terminal can fail when the CLI spawns it without a login shell.
        argv = rm.add_command("srv", {"command": "srv"}, "/abs/bin/srv")
        assert "/abs/bin/srv" in argv and argv[-1] == "/abs/bin/srv"


class TestRegisteredNames:
    def test_missing_file_is_not_an_error(self, tmp_path):
        assert rm.registered_names(tmp_path / "nope.json") == set()

    def test_corrupt_file_is_not_an_error(self, tmp_path):
        # A malformed ~/.claude.json must not abort the install; treating it as
        # "nothing registered" is safe because `claude mcp add` is the writer.
        path = tmp_path / "claude.json"
        path.write_text("{not json", encoding="utf-8")
        assert rm.registered_names(path) == set()

    def test_reads_the_mcp_servers_map(self, tmp_path):
        path = tmp_path / "claude.json"
        path.write_text('{"mcpServers": {"a": {}, "b": {}}}', encoding="utf-8")
        assert rm.registered_names(path) == {"a", "b"}

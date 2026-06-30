"""Unit tests for get_unleashed_mode / set_unleashed_mode MCP tools.

These tests monkeypatch mcp_server._get / mcp_server._post so no live Core
server is required.  FastMCP in this version returns the bare function from
@mcp.tool() (no .fn wrapper), so we call the functions directly.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import mcp_server


def test_set_unleashed_tool_posts(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        mcp_server,
        "_post",
        lambda path, payload=None, **kw: seen.setdefault("p", (path, payload)) or "{}",
    )
    if hasattr(mcp_server.set_unleashed_mode, "fn"):
        mcp_server.set_unleashed_mode.fn(enabled=True)
    else:
        mcp_server.set_unleashed_mode(enabled=True)
    assert seen["p"][0] == "/unleashed"
    assert seen["p"][1] == {"enabled": True}


def test_get_unleashed_tool_gets(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        mcp_server,
        "_get",
        lambda path, **kw: seen.setdefault("p", path) or '{"enabled": false}',
    )
    if hasattr(mcp_server.get_unleashed_mode, "fn"):
        mcp_server.get_unleashed_mode.fn()
    else:
        mcp_server.get_unleashed_mode()
    assert seen["p"] == "/unleashed"

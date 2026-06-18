"""Tests for the 4 gridbot MCP tools in mcp_server.py."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import requests as req_lib
from unittest.mock import patch, MagicMock

import mcp_server


def _resp(text):
    m = MagicMock()
    m.text = text
    return m


# ── analyze_gridbot ───────────────────────────────────────────────────────────

def test_analyze_gridbot_calls_post():
    with patch("mcp_server.requests.post") as mock:
        mock.return_value = _resp('{"eligible":true}')
        result = mcp_server.analyze_gridbot("BTC/USD", 1000.0, 10, 0.1)
    call_args = mock.call_args
    assert "/gridbot/analyze" in call_args[0][0]
    assert call_args[1]["json"]["sym"] == "BTC/USD"
    assert call_args[1]["json"]["capital"] == 1000.0
    assert result == '{"eligible":true}'

def test_analyze_gridbot_defaults():
    with patch("mcp_server.requests.post") as mock:
        mock.return_value = _resp("ok")
        mcp_server.analyze_gridbot("ETH/USD", 500.0)
    body = mock.call_args[1]["json"]
    assert body["grid_count"] == 10
    assert body["fee_pct"] == 0.1

def test_analyze_gridbot_offline():
    with patch("mcp_server.requests.post", side_effect=req_lib.ConnectionError):
        result = mcp_server.analyze_gridbot("BTC/USD", 1000.0)
    assert "OFFLINE" in result

def test_analyze_gridbot_error():
    with patch("mcp_server.requests.post", side_effect=Exception("timeout")):
        result = mcp_server.analyze_gridbot("BTC/USD", 1000.0)
    assert "Core error" in result
    assert "/gridbot/analyze" in result


# ── deploy_paper_gridbot ──────────────────────────────────────────────────────

def test_deploy_paper_gridbot_calls_post():
    with patch("mcp_server.requests.post") as mock:
        mock.return_value = _resp('{"grid":{"sym":"BTC/USD"}}')
        result = mcp_server.deploy_paper_gridbot("BTC/USD", 2000.0, 12, 0.15)
    call_args = mock.call_args
    assert "/gridbot/paper" in call_args[0][0]
    assert call_args[1]["json"]["sym"] == "BTC/USD"
    assert call_args[1]["json"]["capital"] == 2000.0
    assert call_args[1]["json"]["grid_count"] == 12
    assert call_args[1]["json"]["fee_pct"] == 0.15
    assert result == '{"grid":{"sym":"BTC/USD"}}'

def test_deploy_paper_gridbot_defaults():
    with patch("mcp_server.requests.post") as mock:
        mock.return_value = _resp("ok")
        mcp_server.deploy_paper_gridbot("ETH/USD", 1000.0)
    body = mock.call_args[1]["json"]
    assert body["grid_count"] == 10
    assert body["fee_pct"] == 0.1

def test_deploy_paper_gridbot_offline():
    with patch("mcp_server.requests.post", side_effect=req_lib.ConnectionError):
        result = mcp_server.deploy_paper_gridbot("BTC/USD", 1000.0)
    assert "OFFLINE" in result


# ── get_paper_gridbot ─────────────────────────────────────────────────────────

def test_get_paper_gridbot_calls_get():
    with patch("mcp_server.requests.get") as mock:
        mock.return_value = _resp('{"state":{"status":"active"}}')
        result = mcp_server.get_paper_gridbot()
    assert "/gridbot/paper" in mock.call_args[0][0]
    assert "active" in result

def test_get_paper_gridbot_offline():
    with patch("mcp_server.requests.get", side_effect=req_lib.ConnectionError):
        result = mcp_server.get_paper_gridbot()
    assert "OFFLINE" in result

def test_get_paper_gridbot_includes_lag_warning():
    with patch("mcp_server.requests.get") as mock:
        mock.return_value = _resp('{"state":{"status":"active"}}')
        result = mcp_server.get_paper_gridbot()
    assert "15" in result or "lag" in result.lower() or "delay" in result.lower()


# ── stop_paper_gridbot ────────────────────────────────────────────────────────

def test_stop_paper_gridbot_calls_delete():
    with patch("mcp_server.requests.delete") as mock:
        mock.return_value = _resp('{"state":{"status":"stopped"}}')
        result = mcp_server.stop_paper_gridbot()
    assert "/gridbot/paper" in mock.call_args[0][0]
    assert "stopped" in result

def test_stop_paper_gridbot_offline():
    with patch("mcp_server.requests.delete", side_effect=req_lib.ConnectionError):
        result = mcp_server.stop_paper_gridbot()
    assert "OFFLINE" in result

def test_stop_paper_gridbot_error():
    with patch("mcp_server.requests.delete", side_effect=Exception("refused")):
        result = mcp_server.stop_paper_gridbot()
    assert "Core error" in result

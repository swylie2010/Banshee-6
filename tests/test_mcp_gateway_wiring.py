"""
tests/test_mcp_gateway_wiring.py — Task 3: verify all MCP tools route through
BansheeGateway and that get_audit_log / get_audit_summary are wired correctly.

Strategy: mock gateway.call() at the mcp_server module level so tests verify
(a) gateway.call() is invoked with the right tool_name, schema, and params, and
(b) the return value of gateway.call() is passed through unchanged.

Separate tests verify the audit tool handlers call the right FastAPI paths.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json
import pathlib
from unittest.mock import patch, MagicMock

import pytest
import banshee_gateway as gw
import mcp_server


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _mock_call(sentinel="GATEWAY_RESULT"):
    """Return a mock for gateway.call that echoes a sentinel string."""
    m = MagicMock(return_value=sentinel)
    return m


# ─────────────────────────────────────────────────────────────────────────────
# Pattern A — no-param tools route through gateway with schema_cls=None
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("fn,tool_name,path_fragment", [
    (mcp_server.get_macro_weather,    "get_macro_weather",    "/macro/weather"),
    (mcp_server.read_market_intel,    "read_market_intel",    "/intel"),
    (mcp_server.get_regime,           "get_regime",           "/regime"),
    (mcp_server.get_watchlist,        "get_watchlist",        "/watchlist"),
    (mcp_server.check_kill_switch,    "check_kill_switch",    "/kill-switch/check"),
    (mcp_server.get_signal_log,       "get_signal_log",       "/journal/signal-log"),
    (mcp_server.get_feedback_synthesis, "get_feedback_synthesis", "/journal/feedback-synthesis"),
    (mcp_server.get_paper_wheel_alerts, "get_paper_wheel_alerts", "/paper-wheels/alerts"),
    (mcp_server.get_paper_wheels,     "get_paper_wheels",     "/paper-wheels"),
    (mcp_server.get_paper_gridbot,    "get_paper_gridbot",    "/gridbot/paper"),
])
def test_no_param_tool_uses_gateway(fn, tool_name, path_fragment):
    """No-param tools must call gateway.call() with correct tool_name and schema=None."""
    with patch.object(mcp_server.gateway, "call", return_value="RESULT") as mock_call:
        result = fn()
    mock_call.assert_called_once()
    args = mock_call.call_args
    assert args[0][0] == tool_name          # tool_name
    assert args[0][1] == {}                 # params
    assert args[0][2] is None              # schema_cls


@pytest.mark.parametrize("fn,tool_name,path_fragment", [
    (mcp_server.get_macro_weather,    "get_macro_weather",    "/macro/weather"),
    (mcp_server.read_market_intel,    "read_market_intel",    "/intel"),
    (mcp_server.get_regime,           "get_regime",           "/regime"),
    (mcp_server.get_watchlist,        "get_watchlist",        "/watchlist"),
    (mcp_server.check_kill_switch,    "check_kill_switch",    "/kill-switch/check"),
    (mcp_server.get_signal_log,       "get_signal_log",       "/journal/signal-log"),
    (mcp_server.get_feedback_synthesis, "get_feedback_synthesis", "/journal/feedback-synthesis"),
    (mcp_server.get_paper_wheel_alerts, "get_paper_wheel_alerts", "/paper-wheels/alerts"),
    (mcp_server.get_paper_wheels,     "get_paper_wheels",     "/paper-wheels"),
])
def test_no_param_tool_handler_calls_correct_path(fn, tool_name, path_fragment):
    """The handler lambda passed to gateway.call() actually hits the right path."""
    captured = {}
    def capture_call(tn, params, schema, handler, signal_field=None):
        captured["handler"] = handler
        return "RESULT"

    with patch.object(mcp_server.gateway, "call", side_effect=capture_call):
        fn()

    with patch("mcp_server.requests.get") as mock_get:
        mock_get.return_value = MagicMock(text="OK")
        captured["handler"]({})
    assert path_fragment in mock_get.call_args[0][0]


# ─────────────────────────────────────────────────────────────────────────────
# Pattern B — GET tools with params
# ─────────────────────────────────────────────────────────────────────────────

def test_get_asset_radar_routes_through_gateway():
    with patch.object(mcp_server.gateway, "call", return_value="RADAR") as mc:
        result = mcp_server.get_asset_radar("NVDA", mode="sniper", output_mode="agent")
    mc.assert_called_once()
    args = mc.call_args[0]
    assert args[0] == "get_asset_radar"
    assert args[1] == {"symbol": "NVDA", "mode": "sniper", "output_mode": "agent", "unleashed": None}
    assert args[2] is gw.RadarSchema
    assert result == "RADAR"


def test_get_asset_radar_handler_calls_get():
    captured = {}
    def cap(tn, params, schema, handler, signal_field=None):
        captured["h"] = handler
        return "R"
    with patch.object(mcp_server.gateway, "call", side_effect=cap):
        mcp_server.get_asset_radar("SPY")
    with patch("mcp_server.requests.get") as mg:
        mg.return_value = MagicMock(text="ok")
        captured["h"]({"symbol": "SPY", "mode": "swing", "output_mode": "human"})
    assert "/radar" in mg.call_args[0][0]
    assert mg.call_args[1]["params"]["symbol"] == "SPY"


def test_synthesize_nexus_routes_through_gateway():
    with patch.object(mcp_server.gateway, "call", return_value="NEXUS") as mc:
        result = mcp_server.synthesize_nexus("BTC/USD", mode="swing", use_ai=True)
    mc.assert_called_once()
    args = mc.call_args[0]
    assert args[0] == "synthesize_nexus"
    assert args[1]["symbol"] == "BTC/USD"
    assert args[2] is gw.NexusSchema
    assert result == "NEXUS"


def test_get_smc_structure_routes_through_gateway():
    with patch.object(mcp_server.gateway, "call", return_value="SMC") as mc:
        result = mcp_server.get_smc_structure("SPY", ltf="1h", htf="1d")
    mc.assert_called_once()
    args = mc.call_args[0]
    assert args[0] == "get_smc_structure"
    assert args[1] == {"symbol": "SPY", "ltf": "1h", "htf": "1d", "use_ai": True}
    assert args[2] is gw.SMCSchema


def test_get_strategy_results_routes_through_gateway():
    with patch.object(mcp_server.gateway, "call", return_value="STRAT") as mc:
        result = mcp_server.get_strategy_results(strategy_name="trend_follow")
    mc.assert_called_once()
    args = mc.call_args[0]
    assert args[0] == "get_strategy_results"
    assert args[1] == {"strategy_name": "trend_follow"}
    assert args[2] is gw.StrategyResultsSchema


def test_get_geo_harmonic_routes_through_gateway():
    with patch.object(mcp_server.gateway, "call", return_value="GH") as mc:
        result = mcp_server.get_geo_harmonic("BTC/USD", n_local=144)
    mc.assert_called_once()
    args = mc.call_args[0]
    assert args[0] == "get_geo_harmonic"
    assert args[1] == {"symbol": "BTC/USD", "n_local": 144}
    assert args[2] is gw.GeoHarmonicSchema


def test_scan_xabcd_routes_through_gateway():
    with patch.object(mcp_server.gateway, "call", return_value="XABCD") as mc:
        result = mcp_server.scan_xabcd("ETH/USD", pct=0.05)
    mc.assert_called_once()
    args = mc.call_args[0]
    assert args[0] == "scan_xabcd"
    assert args[1] == {"symbol": "ETH/USD", "pct": 0.05}
    assert args[2] is gw.XABCDSchema


def test_get_options_candidate_routes_through_gateway():
    with patch.object(mcp_server.gateway, "call", return_value="CAND") as mc:
        result = mcp_server.get_options_candidate(account_size=10000.0)
    mc.assert_called_once()
    args = mc.call_args[0]
    assert args[0] == "get_options_candidate"
    assert args[1] == {"account_size": 10000.0}
    assert args[2] is gw.OptionsCandidateSchema


# ─────────────────────────────────────────────────────────────────────────────
# Pattern C — POST tools
# ─────────────────────────────────────────────────────────────────────────────

def test_scan_assets_routes_through_gateway():
    with patch.object(mcp_server.gateway, "call", return_value="SCAN") as mc:
        result = mcp_server.scan_assets(["SPY", "NVDA"], mode="swing")
    mc.assert_called_once()
    args = mc.call_args[0]
    assert args[0] == "scan_assets"
    assert args[1]["symbols"] == ["SPY", "NVDA"]
    assert args[2] is gw.ScanSchema
    assert result == "SCAN"


def test_build_execution_plan_routes_through_gateway():
    with patch.object(mcp_server.gateway, "call", return_value="PLAN") as mc:
        result = mcp_server.build_execution_plan(10000, 1.0, 500.0, 480.0)
    mc.assert_called_once()
    args = mc.call_args[0]
    assert args[0] == "build_execution_plan"
    assert args[1]["account_size"] == 10000
    assert args[2] is gw.ExecutionPlanSchema


def test_open_paper_trade_routes_through_gateway():
    with patch.object(mcp_server.gateway, "call", return_value='{"status":"ok"}') as mc:
        result = mcp_server.open_paper_trade("NVDA", "long", 500.0, 480.0, 540.0)
    mc.assert_called_once()
    args = mc.call_args[0]
    assert args[0] == "open_paper_trade"
    assert args[1]["symbol"] == "NVDA"
    assert args[1]["direction"] == "long"
    assert args[2] is gw.PaperTradeSchema


def test_log_signal_outcome_routes_through_gateway():
    with patch.object(mcp_server.gateway, "call", return_value='{"ok":true}') as mc:
        result = mcp_server.log_signal_outcome(42, exit_reason="target_hit", signal_correct=True)
    mc.assert_called_once()
    args = mc.call_args[0]
    assert args[0] == "log_signal_outcome"
    assert args[1]["trade_id"] == 42
    assert args[2] is gw.SignalOutcomeSchema


def test_open_paper_wheel_routes_through_gateway():
    with patch.object(mcp_server.gateway, "call", return_value='{"id":"w1"}') as mc:
        result = mcp_server.open_paper_wheel("SPY", 450.0, "2026-09-20", 2.50)
    mc.assert_called_once()
    args = mc.call_args[0]
    assert args[0] == "open_paper_wheel"
    assert args[1]["underlying"] == "SPY"
    assert args[2] is gw.PaperWheelSchema


def test_analyze_gridbot_routes_through_gateway():
    with patch.object(mcp_server.gateway, "call", return_value="GRID") as mc:
        result = mcp_server.analyze_gridbot("BTC/USD", 1000.0, 10, 0.1)
    mc.assert_called_once()
    args = mc.call_args[0]
    assert args[0] == "analyze_gridbot"
    assert args[1]["symbol"] == "BTC/USD"
    assert args[2] is gw.GridbotSchema


def test_deploy_paper_gridbot_routes_through_gateway():
    with patch.object(mcp_server.gateway, "call", return_value="DEPLOYED") as mc:
        result = mcp_server.deploy_paper_gridbot("ETH/USD", 2000.0)
    mc.assert_called_once()
    args = mc.call_args[0]
    assert args[0] == "deploy_paper_gridbot"
    assert args[1]["symbol"] == "ETH/USD"
    assert args[2] is gw.GridbotSchema


# ─────────────────────────────────────────────────────────────────────────────
# Pattern D — DELETE tool
# ─────────────────────────────────────────────────────────────────────────────

def test_stop_paper_gridbot_routes_through_gateway():
    with patch.object(mcp_server.gateway, "call", return_value="STOPPED") as mc:
        result = mcp_server.stop_paper_gridbot()
    mc.assert_called_once()
    args = mc.call_args[0]
    assert args[0] == "stop_paper_gridbot"
    assert args[1] == {}
    assert args[2] is None
    assert result == "STOPPED"


def test_stop_paper_gridbot_handler_calls_delete():
    captured = {}
    def cap(tn, params, schema, handler, signal_field=None):
        captured["h"] = handler
        return "R"
    with patch.object(mcp_server.gateway, "call", side_effect=cap):
        mcp_server.stop_paper_gridbot()
    with patch("mcp_server.requests.delete") as md:
        md.return_value = MagicMock(text="ok")
        captured["h"]({})
    assert "/gridbot/paper" in md.call_args[0][0]


# ─────────────────────────────────────────────────────────────────────────────
# get_paper_gridbot special: lag warning appended on success
# ─────────────────────────────────────────────────────────────────────────────

def test_get_paper_gridbot_appends_lag_warning():
    with patch.object(mcp_server.gateway, "call", return_value='{"state":"active"}'):
        result = mcp_server.get_paper_gridbot()
    assert "15 min" in result or "lag" in result.lower()


def test_get_paper_gridbot_no_lag_warning_on_error():
    with patch.object(mcp_server.gateway, "call",
                      return_value="BANSHEE CORE OFFLINE"):
        result = mcp_server.get_paper_gridbot()
    assert "lag" not in result.lower() and "15 min" not in result


# ─────────────────────────────────────────────────────────────────────────────
# New audit MCP tools — get_audit_log
# ─────────────────────────────────────────────────────────────────────────────

def test_get_audit_log_routes_through_gateway():
    with patch.object(mcp_server.gateway, "call", return_value='{"entries":[]}') as mc:
        result = mcp_server.get_audit_log(limit=10, tool="get_regime", since="2026-06-01")
    mc.assert_called_once()
    args = mc.call_args[0]
    assert args[0] == "get_audit_log"
    assert args[1] == {"limit": 10, "tool": "get_regime", "since": "2026-06-01"}
    assert args[2] is gw.AuditLogSchema
    assert result == '{"entries":[]}'


def test_get_audit_log_default_params():
    with patch.object(mcp_server.gateway, "call", return_value="R") as mc:
        mcp_server.get_audit_log()
    assert mc.call_args[0][1] == {"limit": 50, "tool": "", "since": ""}


def test_get_audit_log_handler_calls_get_audit_entries():
    captured = {}
    def cap(tn, params, schema, handler, signal_field=None):
        captured["h"] = handler
        return "R"
    with patch.object(mcp_server.gateway, "call", side_effect=cap):
        mcp_server.get_audit_log(limit=5, tool="get_regime", since="")

    with patch("mcp_server.requests.get") as mg:
        mg.return_value = MagicMock(text='{"entries":[]}')
        captured["h"]({"limit": 5, "tool": "get_regime", "since": ""})

    url = mg.call_args[0][0]
    params = mg.call_args[1]["params"]
    assert "/audit/entries" in url
    assert params.get("limit") == 5
    assert params.get("tool") == "get_regime"
    # since="" → None → filtered out of params
    assert "since" not in params


def test_get_audit_log_handler_omits_empty_tool_and_since():
    """Empty tool and since strings should not be passed as query params."""
    captured = {}
    def cap(tn, params, schema, handler, signal_field=None):
        captured["h"] = handler
        return "R"
    with patch.object(mcp_server.gateway, "call", side_effect=cap):
        mcp_server.get_audit_log()

    with patch("mcp_server.requests.get") as mg:
        mg.return_value = MagicMock(text='{"entries":[]}')
        captured["h"]({"limit": 50, "tool": "", "since": ""})

    params = mg.call_args[1]["params"]
    assert "tool" not in params
    assert "since" not in params


# ─────────────────────────────────────────────────────────────────────────────
# New audit MCP tools — get_audit_summary
# ─────────────────────────────────────────────────────────────────────────────

def test_get_audit_summary_routes_through_gateway():
    with patch.object(mcp_server.gateway, "call", return_value='{"calls":{}}') as mc:
        result = mcp_server.get_audit_summary(days=14)
    mc.assert_called_once()
    args = mc.call_args[0]
    assert args[0] == "get_audit_summary"
    assert args[1] == {"days": 14}
    assert args[2] is gw.AuditSummarySchema
    assert result == '{"calls":{}}'


def test_get_audit_summary_default_days():
    with patch.object(mcp_server.gateway, "call", return_value="R") as mc:
        mcp_server.get_audit_summary()
    assert mc.call_args[0][1] == {"days": 7}


def test_get_audit_summary_handler_calls_get_audit_summary():
    captured = {}
    def cap(tn, params, schema, handler, signal_field=None):
        captured["h"] = handler
        return "R"
    with patch.object(mcp_server.gateway, "call", side_effect=cap):
        mcp_server.get_audit_summary(days=30)

    with patch("mcp_server.requests.get") as mg:
        mg.return_value = MagicMock(text='{"calls":{}}')
        captured["h"]({"days": 30})

    url = mg.call_args[0][0]
    params = mg.call_args[1]["params"]
    assert "/audit/summary" in url
    assert params.get("days") == 30


# ─────────────────────────────────────────────────────────────────────────────
# open_paper_wheel handler builds nested body correctly
# ─────────────────────────────────────────────────────────────────────────────

def test_open_paper_wheel_handler_builds_nested_body():
    captured = {}
    def cap(tn, params, schema, handler, signal_field=None):
        captured["h"] = handler
        return "R"
    with patch.object(mcp_server.gateway, "call", side_effect=cap):
        mcp_server.open_paper_wheel("SPY", 450.0, "2026-09-20", 2.50, name="")

    with patch("mcp_server.requests.post") as mp:
        mp.return_value = MagicMock(text='{"id":"w1"}')
        captured["h"]({"underlying": "SPY", "strike": 450.0,
                       "expiry": "2026-09-20", "premium": 2.50, "name": ""})

    body = mp.call_args[1]["json"]
    assert "candidate_snapshot" in body
    cand = body["candidate_snapshot"]["candidate"]
    assert cand["underlying"] == "SPY"
    assert cand["strike"] == 450.0
    assert cand["mid"] == 2.50
    # name defaults to "SPY Paper Wheel" when empty
    assert body["name"] == "SPY Paper Wheel"


def test_open_paper_wheel_handler_uses_provided_name():
    captured = {}
    def cap(tn, params, schema, handler, signal_field=None):
        captured["h"] = handler
        return "R"
    with patch.object(mcp_server.gateway, "call", side_effect=cap):
        mcp_server.open_paper_wheel("QQQ", 460.0, "2026-09-20", 3.0, name="My QQQ Wheel")

    with patch("mcp_server.requests.post") as mp:
        mp.return_value = MagicMock(text='{"id":"w2"}')
        captured["h"]({"underlying": "QQQ", "strike": 460.0,
                       "expiry": "2026-09-20", "premium": 3.0, "name": "My QQQ Wheel"})

    body = mp.call_args[1]["json"]
    assert body["name"] == "My QQQ Wheel"


# ─────────────────────────────────────────────────────────────────────────────
# log_signal_outcome handler drops empty/None fields
# ─────────────────────────────────────────────────────────────────────────────

def test_log_signal_outcome_handler_drops_empty_fields():
    captured = {}
    def cap(tn, params, schema, handler, signal_field=None):
        captured["h"] = handler
        return "R"
    with patch.object(mcp_server.gateway, "call", side_effect=cap):
        mcp_server.log_signal_outcome(99)

    with patch("mcp_server.requests.post") as mp:
        mp.return_value = MagicMock(text='{"ok":true}')
        # call with all optional fields empty/None
        captured["h"]({"trade_id": 99, "exit_reason": "", "signal_correct": None, "note": ""})

    body = mp.call_args[1]["json"]
    assert "trade_id" in body
    assert body["trade_id"] == 99
    # empty and None fields should be omitted
    assert "exit_reason" not in body
    assert "signal_correct" not in body
    assert "note" not in body


def test_log_signal_outcome_handler_keeps_set_fields():
    captured = {}
    def cap(tn, params, schema, handler, signal_field=None):
        captured["h"] = handler
        return "R"
    with patch.object(mcp_server.gateway, "call", side_effect=cap):
        mcp_server.log_signal_outcome(7, exit_reason="target_hit", signal_correct=True)

    with patch("mcp_server.requests.post") as mp:
        mp.return_value = MagicMock(text='{"ok":true}')
        captured["h"]({"trade_id": 7, "exit_reason": "target_hit",
                       "signal_correct": True, "note": ""})

    body = mp.call_args[1]["json"]
    assert body["exit_reason"] == "target_hit"
    assert body["signal_correct"] is True
    assert "note" not in body


# ─────────────────────────────────────────────────────────────────────────────
# Gateway instantiation — verify gateway object exists on the module
# ─────────────────────────────────────────────────────────────────────────────

def test_gateway_instance_exists_on_module():
    assert hasattr(mcp_server, "gateway")
    assert isinstance(mcp_server.gateway, gw.BansheeGateway)

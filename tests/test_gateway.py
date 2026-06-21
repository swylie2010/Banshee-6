# tests/test_gateway.py
import json
import pathlib
import pytest
from unittest.mock import patch

import banshee_gateway as gw


@pytest.fixture(autouse=True)
def tmp_audit(tmp_path, monkeypatch):
    audit = tmp_path / "test_audit.jsonl"
    monkeypatch.setattr(gw, "_AUDIT_PATH", audit)
    return audit


def _make_gateway():
    return gw.BansheeGateway(token_fn=lambda: "test-token-1234")


# ── Validation pass ────────────────────────────────────────────────────────────

def test_validation_pass_calls_handler(tmp_audit):
    g = _make_gateway()
    result = g.call("synthesize_nexus", {"symbol": "AAPL", "mode": "swing"},
                    gw.NexusSchema, lambda p: "ok")
    assert "ok" in result


def test_validation_pass_writes_entry(tmp_audit):
    g = _make_gateway()
    g.call("synthesize_nexus", {"symbol": "AAPL", "mode": "swing"},
           gw.NexusSchema, lambda p: "ok")
    lines = tmp_audit.read_text().strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["tool"] == "synthesize_nexus"
    assert entry["validation"]["passed"] is True
    assert entry["outcome"]["status"] == "success"


def test_audit_entry_has_required_fields(tmp_audit):
    g = _make_gateway()
    g.call("get_macro_weather", {}, None, lambda p: "weather ok")
    entry = json.loads(tmp_audit.read_text().strip())
    for field in ("id", "ts", "tool", "session", "request", "validation", "outcome"):
        assert field in entry, f"Missing field: {field}"
    assert entry["id"].startswith("aud_")
    assert entry["session"] == "1234"  # last 4 chars of "test-token-1234"


# ── Validation fail ────────────────────────────────────────────────────────────

def test_validation_fail_returns_error(tmp_audit):
    g = _make_gateway()
    result = g.call("get_asset_radar", {"symbol": "AAPL", "mode": "badmode"},
                    gw.RadarSchema, lambda p: "should not reach")
    data = json.loads(result)
    assert data["error"] == "Validation failed"
    assert len(data["violations"]) > 0
    assert data["_audit"]["validation_passed"] is False


def test_validation_fail_writes_rejected_entry(tmp_audit):
    g = _make_gateway()
    g.call("get_asset_radar", {"symbol": "AAPL", "mode": "badmode"},
           gw.RadarSchema, lambda p: "should not reach")
    entry = json.loads(tmp_audit.read_text().strip())
    assert entry["validation"]["passed"] is False
    assert entry["outcome"]["status"] == "rejected"


def test_validation_fail_does_not_call_handler(tmp_audit):
    g = _make_gateway()
    called = []
    g.call("get_asset_radar", {"symbol": "", "mode": "swing"},
           gw.RadarSchema, lambda p: called.append(True) or "x")
    assert not called


# ── No-schema tools ───────────────────────────────────────────────────────────

def test_no_schema_always_calls_handler(tmp_audit):
    g = _make_gateway()
    result = g.call("get_macro_weather", {}, None, lambda p: "weather")
    assert "weather" in result


def test_no_schema_entry_has_empty_rules(tmp_audit):
    g = _make_gateway()
    g.call("get_regime", {}, None, lambda p: "regime ok")
    entry = json.loads(tmp_audit.read_text().strip())
    assert entry["validation"]["rules_checked"] == []
    assert entry["validation"]["passed"] is True


# ── Response enrichment ───────────────────────────────────────────────────────

def test_json_response_gets_audit_key(tmp_audit):
    g = _make_gateway()
    result = g.call("synthesize_nexus", {"symbol": "AAPL", "mode": "swing"},
                    gw.NexusSchema, lambda p: json.dumps({"signal": "long"}))
    data = json.loads(result)
    assert "_audit" in data
    assert data["_audit"]["validation_passed"] is True


def test_plaintext_response_gets_audit_trailer(tmp_audit):
    g = _make_gateway()
    result = g.call("get_regime", {}, None, lambda p: "REGIME: TRENDING")
    assert "[AUDIT:" in result
    assert "REGIME: TRENDING" in result


def test_anon_session_when_no_token(tmp_audit):
    g = gw.BansheeGateway(token_fn=lambda: "")
    g.call("get_regime", {}, None, lambda p: "ok")
    entry = json.loads(tmp_audit.read_text().strip())
    assert entry["session"] == "anon"


# ── Schema-specific validation ─────────────────────────────────────────────────

def test_nexus_rejects_invalid_mode(tmp_audit):
    g = _make_gateway()
    result = g.call("synthesize_nexus", {"symbol": "BTC/USD", "mode": "1h"},
                    gw.NexusSchema, lambda p: "ok")
    assert json.loads(result)["error"] == "Validation failed"


def test_execution_plan_rejects_negative_account(tmp_audit):
    g = _make_gateway()
    result = g.call("build_execution_plan",
                    {"account_size": -100, "risk_percent": 1.0,
                     "entry_price": 100.0, "stop_loss": 95.0},
                    gw.ExecutionPlanSchema, lambda p: "ok")
    assert json.loads(result)["error"] == "Validation failed"


def test_smc_rejects_invalid_timeframe(tmp_audit):
    g = _make_gateway()
    result = g.call("get_smc_structure",
                    {"symbol": "SPY", "ltf": "3h", "htf": "1d"},
                    gw.SMCSchema, lambda p: "ok")
    assert json.loads(result)["error"] == "Validation failed"


def test_paper_trade_rejects_bad_direction(tmp_audit):
    g = _make_gateway()
    result = g.call("open_paper_trade",
                    {"symbol": "NVDA", "direction": "UP",
                     "entry_price": 100.0, "stop_price": 95.0, "target_price": 110.0},
                    gw.PaperTradeSchema, lambda p: "ok")
    assert json.loads(result)["error"] == "Validation failed"


def test_geo_harmonic_rejects_invalid_n_local(tmp_audit):
    g = _make_gateway()
    result = g.call("get_geo_harmonic", {"symbol": "BTC/USD", "n_local": 100},
                    gw.GeoHarmonicSchema, lambda p: "ok")
    assert json.loads(result)["error"] == "Validation failed"

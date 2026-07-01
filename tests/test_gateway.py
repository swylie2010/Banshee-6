# tests/test_gateway.py
import json
import pathlib
import pytest

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


# ── Signal extraction (Observatory signal_field) ──────────────────────────────
# The audit "signal" is the tool's headline verdict. A tool must (a) opt in by
# passing signal_field and (b) actually surface that value in its response —
# which for the default output_mode='human' is a text line, not JSON.

def test_signal_extracted_from_json_response(tmp_audit):
    """output_mode='agent' returns JSON — read the top-level key."""
    g = _make_gateway()
    g.call("get_asset_radar", {"symbol": "NVDA", "mode": "swing", "output_mode": "agent"},
           gw.RadarSchema, lambda p: json.dumps({"verdict": "STRONG BUY", "edge": 7}),
           signal_field="verdict")
    entry = json.loads(tmp_audit.read_text().strip())
    assert entry["outcome"]["signal"] == "STRONG BUY"


def test_signal_extracted_from_human_text_radar(tmp_audit):
    """output_mode='human' (the default) is narrative text — scan the VERDICT line."""
    g = _make_gateway()
    human = "\n".join([
        "[cache: live]",
        "ASSET: NVDA  |  PRICE: $123.4500",
        "VERDICT: STRONG BUY  |  EDGE SCORE: 7",
        "ENTRY QUALITY: GOOD",
    ])
    g.call("get_asset_radar", {"symbol": "NVDA", "mode": "swing", "output_mode": "human"},
           gw.RadarSchema, lambda p: human, signal_field="verdict")
    entry = json.loads(tmp_audit.read_text().strip())
    assert entry["outcome"]["signal"] == "STRONG BUY"


def test_signal_extracted_from_human_text_nexus(tmp_audit):
    """Nexus labels its verdict 'MICRO VERDICT:' — the label prefix is tolerated."""
    g = _make_gateway()
    human = "\n".join([
        "MACRO REGIME: NEUTRAL",
        "MICRO VERDICT: BUY SETUP  (Edge: 5)",
        "NARRATIVE: ...",
    ])
    g.call("synthesize_nexus", {"symbol": "BTC/USD", "mode": "swing"},
           gw.NexusSchema, lambda p: human, signal_field="verdict")
    entry = json.loads(tmp_audit.read_text().strip())
    assert entry["outcome"]["signal"] == "BUY SETUP"


def test_no_signal_field_means_no_signal(tmp_audit):
    """A tool that never opts in logs no signal, even if its text has a VERDICT line."""
    g = _make_gateway()
    g.call("get_regime", {}, None, lambda p: "VERDICT: STRONG BUY  |  X")
    entry = json.loads(tmp_audit.read_text().strip())
    assert "signal" not in entry["outcome"]


def test_signal_absent_when_text_has_no_verdict(tmp_audit):
    """Opted-in tool whose response carries no verdict logs no signal (not a crash)."""
    g = _make_gateway()
    g.call("get_asset_radar", {"symbol": "NVDA", "mode": "swing", "output_mode": "human"},
           gw.RadarSchema, lambda p: "ASSET: NVDA  |  PRICE: $1.00\nNO SIGNAL LINE HERE",
           signal_field="verdict")
    entry = json.loads(tmp_audit.read_text().strip())
    assert "signal" not in entry["outcome"]


# ── Audit-log rotation (bounded growth) ───────────────────────────────────────

def _backup(path, i):
    return path.parent / f"{path.name}.{i}"


def test_audit_log_rotates_when_oversized(tmp_audit, monkeypatch):
    """Once the live log passes the size cap, it rotates to <path>.1 and starts fresh."""
    monkeypatch.setattr(gw, "_AUDIT_MAX_BYTES", 200)
    g = _make_gateway()
    for _ in range(20):
        g.call("get_regime", {}, None, lambda p: "REGIME: TRENDING")
    assert _backup(tmp_audit, 1).exists()          # rotation happened
    assert tmp_audit.stat().st_size < 200 * 4      # live file stays bounded


def test_audit_log_rotation_caps_backups(tmp_audit, monkeypatch):
    """Never keep more than _AUDIT_BACKUPS rotated files — disk is bounded."""
    monkeypatch.setattr(gw, "_AUDIT_MAX_BYTES", 100)
    monkeypatch.setattr(gw, "_AUDIT_BACKUPS", 2)
    g = _make_gateway()
    for _ in range(50):
        g.call("get_regime", {}, None, lambda p: "REGIME: TRENDING extra padding")
    assert _backup(tmp_audit, 2).exists()
    assert not _backup(tmp_audit, 3).exists()


def test_audit_log_no_rotation_under_threshold(tmp_audit):
    """A small log is never rotated — history stays intact for the summary window."""
    g = _make_gateway()
    g.call("get_regime", {}, None, lambda p: "ok")
    assert not _backup(tmp_audit, 1).exists()


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

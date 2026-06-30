"""tests/test_unleashed_route.py — HTTP surface tests for /unleashed toggle."""

import json

import pandas as pd
from fastapi.testclient import TestClient
import banshee_ai
import banshee_core as bc
import core_state
import micro_engine
import routes.admin
import routes.analysis
import shared_data


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(core_state, "_UNLEASHED_FILE", tmp_path / "u.json")
    return TestClient(bc.app)


def test_get_unleashed_defaults_disabled(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.get("/unleashed")
    assert r.status_code == 200
    assert r.json() == {"enabled": False}


def test_post_unleashed_persists(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post("/unleashed", json={"enabled": True})
    assert r.status_code == 200
    assert r.json()["enabled"] is True
    assert c.get("/unleashed").json() == {"enabled": True}


def test_scan_agent_htf_bias_not_null(tmp_path, monkeypatch):
    """Regression: /scan output_mode=agent must expose htf_bias as the engine's bias dict.

    Root cause (pre-fix): the intermediate _analyze_one dict stores the engine's
    'bias' key as 'htf_bias', but the agent response builder then read r.get('bias')
    — a key that doesn't exist in the intermediate dict — returning None every time.

    After fix: the builder reads r.get('htf_bias'), which matches the stored key.
    """
    import micro_engine
    import routes.analysis

    # Canned engine result — contains 'bias' (the engine key name)
    _CANNED_ANALYSIS = {
        "verdict": "SELL SETUP",
        "edge": -3,
        "price": 100.0,
        "entry_quality": {"quality": "READY", "reasons": []},
        "volume": "UNKNOWN",
        "warnings": {},
        "bias": {"direction": "BEARISH", "conviction": "STRONG"},
        "trigger": {"direction": "SHORT"},
        "alignment": "aligned",
        "unleashed": False,
        "frame": "",
    }

    # Non-empty tfs so load_and_prepare doesn't report an error
    monkeypatch.setattr(
        micro_engine, "load_and_prepare",
        lambda *a, **k: {"1d": object(), "4h": object(), "1h": object()},
    )
    monkeypatch.setattr(
        micro_engine, "run_analysis",
        lambda *a, **k: _CANNED_ANALYSIS,
    )
    # Suppress macro cache so scan_sensors=None (avoids any external file read)
    monkeypatch.setattr(routes.analysis, "_load_macro_cache", lambda: None)

    c = _client(tmp_path, monkeypatch)
    r = c.post("/scan", json={"symbols": ["AAPL"], "output_mode": "agent"})

    assert r.status_code == 200
    payload = json.loads(r.text)
    assert len(payload["results"]) == 1, f"Expected 1 result, got: {payload}"
    htf_bias = payload["results"][0]["htf_bias"]
    assert htf_bias == {"direction": "BEARISH", "conviction": "STRONG"}, (
        f"htf_bias must be the bias dict, got {htf_bias!r}. "
        "Likely the agent builder is still using r.get('bias') instead of r.get('htf_bias')."
    )


def test_briefing_endpoint_threads_unleashed(tmp_path, monkeypatch):
    """Regression: /ai/briefing must pass unleashed=True to call_ai_briefing when unleashed is enabled.

    This test fails if `unleashed=_unleashed` is removed from the call_ai_briefing
    callsite in routes/admin.py, because `captured["unleashed"]` will be None/False
    instead of True.
    """
    captured = {}

    # 1. Capture the unleashed kwarg passed to call_ai_briefing
    def fake_call_ai_briefing(cfg, prompt, **kwargs):
        captured["unleashed"] = kwargs.get("unleashed")
        return "canned briefing text"

    monkeypatch.setattr(banshee_ai, "call_ai_briefing", fake_call_ai_briefing)

    # 2. Make core_state.load_unleashed report enabled=True
    monkeypatch.setattr(core_state, "_UNLEASHED_FILE", tmp_path / "u.json")
    monkeypatch.setattr(core_state, "load_unleashed", lambda: {"enabled": True})

    # 3. Provide a fake AI key so the handler doesn't early-exit
    monkeypatch.setattr(shared_data, "load_providers",
                        lambda: {"AI_API": {"key": "test-key", "provider": "fake"}})

    # 4. Bypass the AI budget rate-limiter (imported into routes.admin namespace)
    monkeypatch.setattr(routes.admin, "check_ai_budget", lambda: None)

    # 5. Short-circuit _build_news_context so no macro/predator I/O happens
    monkeypatch.setattr(routes.admin, "_build_news_context", lambda: ({}, [], []))

    # 6. Short-circuit the OHLCV data fetch (lazily imported from routes.analysis)
    _fake_tfs = {
        "1d": pd.DataFrame({"close": [100.0]}),
        "4h": pd.DataFrame({"close": [100.0]}),
        "1h": pd.DataFrame({"close": [100.0]}),
    }
    monkeypatch.setattr(routes.analysis, "get_ohlcv_cached", lambda *a, **k: _fake_tfs)

    # 7. Return a canned micro_engine result so micro analysis doesn't error
    _canned_mic = {
        "verdict": "BUY SETUP",
        "edge": 2.0,
        "price": 100.0,
        "entry_quality": {"quality": "READY", "reasons": []},
        "bias": {"direction": "BULLISH", "conviction": "MODERATE"},
        "trigger": {"direction": "LONG", "actionable": True, "extended_reading": {}},
        "alignment": "aligned",
        "unleashed": True,
        "frame": "",
    }
    monkeypatch.setattr(micro_engine, "run_analysis", lambda *a, **k: _canned_mic)

    c = TestClient(bc.app)
    r = c.post(
        "/ai/briefing",
        json={"symbol": "BTC/USD", "tab": "nexus", "mode": "swing", "manual_stories": []},
    )

    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    assert captured.get("unleashed") is True, (
        f"call_ai_briefing was NOT called with unleashed=True (got {captured.get('unleashed')!r}). "
        "Remove 'unleashed=_unleashed' from the call_ai_briefing callsite in routes/admin.py "
        "and this assertion fails — proving the fix is load-bearing."
    )

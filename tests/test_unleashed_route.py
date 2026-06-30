"""tests/test_unleashed_route.py — HTTP surface tests for /unleashed toggle."""

import json

from fastapi.testclient import TestClient
import banshee_core as bc
import core_state


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

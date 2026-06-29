import pandas as pd
from fastapi.testclient import TestClient
import banshee_core
import micro_engine
from routes import analysis


def _fake_tfs():
    df = pd.DataFrame({
        "timestamp": pd.date_range(end="2026-06-29", periods=10, freq="D"),
        "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0,
    })
    return {"1d": df}


def test_get_ohlcv_cached_deep_uses_separate_cache_key(monkeypatch):
    calls = []
    def fake_prep(symbol, mode, deep=False):
        calls.append(deep)
        return _fake_tfs()
    monkeypatch.setattr(micro_engine, "load_and_prepare", fake_prep)
    analysis._OHLCV_CACHE.clear()
    analysis.get_ohlcv_cached("BTC/USD", "swing", deep=False)
    analysis.get_ohlcv_cached("BTC/USD", "swing", deep=True)
    assert calls == [False, True]                 # deep did not hit the fast cache entry
    assert ("BTC/USD", "swing", True) in analysis._OHLCV_CACHE
    assert ("BTC/USD", "swing", False) in analysis._OHLCV_CACHE


def test_get_ohlcv_cached_empty_deep_not_cached(monkeypatch):
    monkeypatch.setattr(micro_engine, "load_and_prepare",
                        lambda s, m, deep=False: {"1d": pd.DataFrame()})
    analysis._OHLCV_CACHE.clear()
    analysis.get_ohlcv_cached("BTC/USD", "swing", deep=True)
    assert ("BTC/USD", "swing", True) not in analysis._OHLCV_CACHE   # no poisoning


def test_route_ohlcv_deep_flag(monkeypatch):
    monkeypatch.setattr(micro_engine, "load_and_prepare",
                        lambda s, m, deep=False: _fake_tfs())
    analysis._OHLCV_CACHE.clear()
    client = TestClient(banshee_core.app)
    r = client.get("/ohlcv?symbol=BTC/USD&mode=swing&deep=1")
    assert r.status_code == 200
    body = r.json()
    assert body["deep"] is True
    assert "1d" in body["tfs"]

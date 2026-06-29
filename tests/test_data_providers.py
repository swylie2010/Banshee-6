"""tests/test_data_providers.py — unit tests for data_providers.py"""
import uuid
import pytest
from unittest.mock import patch


def _all_enabled_keys():
    """Keys dict with all providers enabled — used to satisfy _active_chain in chain tests."""
    return {
        "COINBASE":   {"enabled": True},
        "ALPACA_KEY": {"key": "test_key", "enabled": True},
        "ALPACA_SECRET": {"key": "test_secret"},
        "COINGECKO":  {"enabled": True},
        "YFINANCE":   {"enabled": True},
        "CUSTOM_DATA": {"enabled": False, "base_url": "", "asset_class": "both"},
    }


def test_asset_class_crypto_slash():
    import data_providers
    assert data_providers._asset_class("BTC/USD") == "crypto"

def test_asset_class_crypto_dash():
    import data_providers
    assert data_providers._asset_class("BTC-USD") == "crypto"

def test_asset_class_known_crypto_ticker():
    import data_providers
    assert data_providers._asset_class("ETH") == "crypto"

def test_asset_class_equity():
    import data_providers
    assert data_providers._asset_class("AAPL") == "equity"

def test_asset_class_equity_spy():
    import data_providers
    assert data_providers._asset_class("SPY") == "equity"

def test_mean_latency_no_samples():
    import data_providers
    # A provider with no recorded samples should return inf
    data_providers._latency["coinbase"].clear()
    assert data_providers._mean_latency("coinbase") == float("inf")

def test_mean_latency_with_samples():
    import data_providers
    data_providers._latency["coinbase"].clear()
    data_providers._record_latency("coinbase", 100.0)
    data_providers._record_latency("coinbase", 200.0)
    assert data_providers._mean_latency("coinbase") == 150.0
    data_providers._latency["coinbase"].clear()  # cleanup

def test_record_latency_on_failure_not_called():
    import data_providers
    data_providers._latency["yfinance"].clear()
    # failure path should NOT record — callers only call _record_latency on success
    assert len(data_providers._latency["yfinance"]) == 0

def test_tier_fast():
    import data_providers
    assert data_providers._tier(94.0) == "FAST"

def test_tier_good():
    import data_providers
    assert data_providers._tier(800.0) == "GOOD"

def test_tier_slow():
    import data_providers
    assert data_providers._tier(9000.0) == "SLOW"

def test_tier_untested():
    import data_providers
    assert data_providers._tier(float("inf")) == "UNTESTED"


# ── Spot price chain tests ────────────────────────────────────────────────────
# IMPORTANT: get_spot_price reads _SPOT_FNS[name] at call time (dict lookup).
# patch.object on the module attribute does NOT affect what the dict holds.
# Always use patch.dict on _SPOT_FNS / _OHLCV_FNS to mock provider adapters.

def _exc(*a, **kw):
    raise Exception("mocked failure")

def test_spot_price_crypto_success_first_provider():
    """If the first provider returns a price, it's returned immediately."""
    import data_providers
    with patch("data_providers._load_keys", return_value=_all_enabled_keys()):
        with patch.dict(data_providers._SPOT_FNS, {"coinbase": lambda s: 50000.0}):
            result = data_providers.get_spot_price.__wrapped__("BTC-USD-TEST1")
    assert result == 50000.0

def test_spot_price_crypto_falls_through_to_second():
    """If Coinbase raises, CoinGecko is tried next."""
    import data_providers
    with patch("data_providers._load_keys", return_value=_all_enabled_keys()):
        with patch.dict(data_providers._SPOT_FNS, {
            "coinbase":  _exc,
            "coingecko": lambda s: 50001.0,
            "yfinance":  lambda s: 0.0,
        }):
            result = data_providers.get_spot_price.__wrapped__("BTC-USD-TEST2")
    assert result == 50001.0

def test_spot_price_crypto_total_failure_returns_none():
    """If all providers fail, None is returned (never raises)."""
    import data_providers
    with patch.dict(data_providers._SPOT_FNS, {
        "coinbase":  _exc,
        "coingecko": _exc,
        "yfinance":  lambda s: None,
    }):
        result = data_providers.get_spot_price("BTC-USD-TEST3")
    assert result is None

def test_spot_price_equity_skips_coinbase_and_coingecko():
    """Equity symbols only try Alpaca and yfinance — Coinbase/CoinGecko never called."""
    import data_providers
    coinbase_called = []
    coingecko_called = []
    with patch("data_providers._load_keys", return_value=_all_enabled_keys()):
        with patch.dict(data_providers._SPOT_FNS, {
            "coinbase":  lambda s: coinbase_called.append(s) or None,
            "coingecko": lambda s: coingecko_called.append(s) or None,
            "alpaca":    lambda s: 150.0,
        }):
            result = data_providers.get_spot_price.__wrapped__("AAPL-TEST4")
    assert result == 150.0
    assert len(coinbase_called) == 0
    assert len(coingecko_called) == 0

def test_coingecko_skipped_for_unknown_crypto_symbol():
    """CoinGecko returns None if symbol not in _CG_IDS; chain continues to yfinance."""
    import data_providers
    with patch("data_providers._load_keys", return_value=_all_enabled_keys()):
        with patch.dict(data_providers._SPOT_FNS, {
            "coinbase":  _exc,
            "coingecko": lambda s: None,   # explicit mock — symbol not in _CG_IDS
            "yfinance":  lambda s: 999.0,
        }):
            result = data_providers.get_spot_price.__wrapped__("UNKNOWNCOIN-USD-TEST5")
    assert result == 999.0

def test_latency_recorded_on_spot_success():
    """Successful spot fetch records latency for the winning provider."""
    import uuid
    import data_providers
    data_providers._latency["yfinance"].clear()
    # Use a unique symbol each run so ttl_cache never serves a stale hit
    test_sym = f"ETH-USD-LATENCY-{uuid.uuid4().hex}"
    with patch("data_providers._load_keys", return_value=_all_enabled_keys()):
        with patch.dict(data_providers._SPOT_FNS, {
            "coinbase":  _exc,
            "coingecko": _exc,
            "yfinance":  lambda s: 42.0,
        }):
            data_providers.get_spot_price.__wrapped__(test_sym)
    assert len(data_providers._latency["yfinance"]) == 1
    data_providers._latency["yfinance"].clear()


# ── OHLCV chain tests ─────────────────────────────────────────────────────────
# Same pattern as spot: use patch.dict on _OHLCV_FNS, not patch.object.

import pandas as pd

def _fake_ohlcv(n=10) -> pd.DataFrame:
    """Helper: returns a minimal valid OHLCV DataFrame."""
    return pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=n),
        "open":  [100.0] * n,
        "high":  [110.0] * n,
        "low":   [90.0]  * n,
        "close": [105.0] * n,
        "volume":[1000.0]* n,
    })

def test_ohlcv_returns_normalized_columns():
    """fetch_ohlcv always returns the canonical 6-column shape."""
    import data_providers
    sym = f"BTC/USD-NORM-{uuid.uuid4().hex}"
    with patch("data_providers._load_keys", return_value=_all_enabled_keys()):
        with patch.dict(data_providers._OHLCV_FNS, {"coinbase": lambda *a: _fake_ohlcv()}):
            df = data_providers.fetch_ohlcv(sym, "1d", 10)
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]

def test_ohlcv_no_timezone():
    """Timestamps must be timezone-naive."""
    import data_providers
    sym = f"BTC/USD-NOTZ-{uuid.uuid4().hex}"
    with patch("data_providers._load_keys", return_value=_all_enabled_keys()):
        with patch.dict(data_providers._OHLCV_FNS, {"coinbase": lambda *a: _fake_ohlcv()}):
            df = data_providers.fetch_ohlcv(sym, "1d", 10)
    assert df["timestamp"].dt.tz is None

def test_ohlcv_falls_through_on_empty():
    """If first provider returns empty, the next is tried."""
    import data_providers
    sym = f"BTC/USD-FALL-{uuid.uuid4().hex}"
    with patch("data_providers._load_keys", return_value=_all_enabled_keys()):
        with patch.dict(data_providers._OHLCV_FNS, {
            "coinbase":  lambda *a: pd.DataFrame(),
            "yfinance":  lambda *a: _fake_ohlcv(),
        }):
            df = data_providers.fetch_ohlcv(sym, "1d", 10)
    assert not df.empty

def test_ohlcv_equity_skips_coinbase():
    """Equity OHLCV chain does not call Coinbase."""
    import data_providers
    sym = f"AAPL-EQ-{uuid.uuid4().hex}"
    coinbase_called = []
    with patch.dict(data_providers._OHLCV_FNS, {
        "coinbase": lambda *a: coinbase_called.append(a) or pd.DataFrame(),
        "alpaca":   lambda *a: _fake_ohlcv(),
    }):
        data_providers.fetch_ohlcv(sym, "1d", 30)
    assert len(coinbase_called) == 0

def test_ohlcv_total_failure_returns_empty_df():
    """If all providers fail, returns empty DataFrame (never raises)."""
    import data_providers
    sym = f"BTC/USD-FAIL-{uuid.uuid4().hex}"
    with patch.dict(data_providers._OHLCV_FNS, {
        "coinbase":  lambda *a: pd.DataFrame(),
        "yfinance":  lambda *a: pd.DataFrame(),
    }):
        df = data_providers.fetch_ohlcv(sym, "1d", 10)
    assert df.empty

def test_ohlcv_latency_recorded_on_success():
    """Successful OHLCV fetch records latency for the winning provider."""
    import data_providers
    sym = f"BTC/USD-LAT-{uuid.uuid4().hex}"
    data_providers._latency["coinbase"].clear()
    with patch("data_providers._load_keys", return_value=_all_enabled_keys()):
        with patch.dict(data_providers._OHLCV_FNS, {"coinbase": lambda *a: _fake_ohlcv()}):
            data_providers.fetch_ohlcv(sym, "1d", 10)
    assert len(data_providers._latency["coinbase"]) == 1
    data_providers._latency["coinbase"].clear()


def test_ohlcv_weekly_routes_to_daily_cache():
    """'1wk' timeframe uses the daily (4h TTL) cache, not the intraday (15m) cache."""
    import data_providers
    sym = f"BTC/USD-1WK-{uuid.uuid4().hex}"
    daily_calls = []
    intraday_calls = []
    orig_daily = data_providers._fetch_ohlcv_daily
    orig_intraday = data_providers._fetch_ohlcv_intraday
    try:
        data_providers._fetch_ohlcv_daily = lambda s, tf, lim: daily_calls.append(tf) or pd.DataFrame()
        data_providers._fetch_ohlcv_intraday = lambda s, tf, lim: intraday_calls.append(tf) or pd.DataFrame()
        data_providers.fetch_ohlcv(sym, "1wk", 10)
    finally:
        data_providers._fetch_ohlcv_daily = orig_daily
        data_providers._fetch_ohlcv_intraday = orig_intraday
    assert len(daily_calls) == 1
    assert len(intraday_calls) == 0


# ── yfinance symbol normalization ─────────────────────────────────────────────

def test_yfinance_ohlcv_normalizes_crypto_slash_to_dash():
    """_yfinance_ohlcv must convert BTC/USD -> BTC-USD before calling yf.Ticker."""
    import data_providers
    captured = {}

    class _FakeTicker:
        def __init__(self, sym):
            captured["sym"] = sym

        def history(self, **kwargs):
            return pd.DataFrame()  # empty is fine; we only assert the symbol passed

    with patch("yfinance.Ticker", _FakeTicker):
        data_providers._yfinance_ohlcv("BTC/USD", "1d", 10)

    assert captured.get("sym") == "BTC-USD"


def test_yfinance_ohlcv_equity_symbol_unchanged():
    """_yfinance_ohlcv must NOT alter equity symbols that have no slash."""
    import data_providers
    captured = {}

    class _FakeTicker:
        def __init__(self, sym):
            captured["sym"] = sym

        def history(self, **kwargs):
            return pd.DataFrame()

    with patch("yfinance.Ticker", _FakeTicker):
        data_providers._yfinance_ohlcv("AAPL", "1d", 10)

    assert captured.get("sym") == "AAPL"


def test_yfinance_spot_normalizes_crypto_slash_to_dash():
    """_yfinance_spot must convert BTC/USD -> BTC-USD before calling yf.Ticker."""
    import data_providers
    captured = {}

    class _FakeFastInfo:
        last_price = None  # triggers fallback to history()

    class _FakeTicker:
        def __init__(self, sym):
            captured["sym"] = sym
            self.fast_info = _FakeFastInfo()

        def history(self, **kwargs):
            return pd.DataFrame()

    with patch("yfinance.Ticker", _FakeTicker):
        data_providers._yfinance_spot("BTC/USD")

    assert captured.get("sym") == "BTC-USD"


# ── Deep chain tests ──────────────────────────────────────────────────────────

def _crypto_all_on():
    return {
        "COINBASE":   {"enabled": True},
        "YFINANCE":   {"enabled": True},
        "COINGECKO":  {"enabled": True},
        "ALPACA_KEY": {"key": "k", "enabled": True},
        "ALPACA_SECRET": {"key": "s"},
        "CUSTOM_DATA": {"enabled": True, "base_url": "http://x", "asset_class": "both",
                        "capabilities": ["ohlcv"]},
    }

def test_deep_chain_ranks_deepest_first_and_excludes_fast():
    import data_providers
    with patch.object(data_providers, "_load_keys", _crypto_all_on):
        # coinbase is the fast Stage-1 provider → excluded; deepest-first among the rest
        chain = data_providers._deep_chain("crypto", exclude="coinbase")
    assert chain[0] in ("yfinance", "custom")   # rank-3/2 ahead of shallow
    assert "coinbase" not in chain
    assert "coingecko" not in chain             # spot-only → never in OHLCV deep poll

def test_deep_chain_respects_cap():
    import data_providers
    with patch.object(data_providers, "_load_keys", _crypto_all_on):
        chain = data_providers._deep_chain("crypto", exclude=None, cap=2)
    assert len(chain) <= 2

def test_deep_chain_skips_disabled():
    import data_providers
    keys = {"YFINANCE": {"enabled": False}, "COINBASE": {"enabled": True}}
    with patch.object(data_providers, "_load_keys", lambda: keys):
        chain = data_providers._deep_chain("crypto", exclude="coinbase")
    assert chain == []   # only coinbase enabled, and it's excluded → nothing deeper

def test_deep_chain_coinbase_only_is_empty():
    import data_providers
    keys = {"COINBASE": {"enabled": True}}
    with patch.object(data_providers, "_load_keys", lambda: keys):
        chain = data_providers._deep_chain("crypto", exclude="coinbase")
    assert chain == []   # no-op path: nothing to upgrade to

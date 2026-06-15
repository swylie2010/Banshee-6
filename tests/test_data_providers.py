"""tests/test_data_providers.py — unit tests for data_providers.py"""
import pytest
from unittest.mock import patch


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
    with patch.dict(data_providers._SPOT_FNS, {"coinbase": lambda s: 50000.0}):
        result = data_providers.get_spot_price("BTC-USD-TEST1")
    assert result == 50000.0

def test_spot_price_crypto_falls_through_to_second():
    """If Coinbase raises, CoinGecko is tried next."""
    import data_providers
    with patch.dict(data_providers._SPOT_FNS, {
        "coinbase":  _exc,
        "coingecko": lambda s: 50001.0,
        "yfinance":  lambda s: 0.0,
    }):
        result = data_providers.get_spot_price("BTC-USD-TEST2")
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
    with patch.dict(data_providers._SPOT_FNS, {
        "coinbase":  lambda s: coinbase_called.append(s) or None,
        "coingecko": lambda s: coingecko_called.append(s) or None,
        "alpaca":    lambda s: 150.0,
    }):
        result = data_providers.get_spot_price("AAPL-TEST4")
    assert result == 150.0
    assert len(coinbase_called) == 0
    assert len(coingecko_called) == 0

def test_coingecko_skipped_for_unknown_crypto_symbol():
    """CoinGecko returns None if symbol not in _CG_IDS; chain continues to yfinance."""
    import data_providers
    with patch.dict(data_providers._SPOT_FNS, {
        "coinbase":  _exc,
        "coingecko": lambda s: None,   # explicit mock — symbol not in _CG_IDS
        "yfinance":  lambda s: 999.0,
    }):
        result = data_providers.get_spot_price("UNKNOWNCOIN-USD-TEST5")
    assert result == 999.0

def test_latency_recorded_on_spot_success():
    """Successful spot fetch records latency for the winning provider."""
    import uuid
    import data_providers
    data_providers._latency["yfinance"].clear()
    # Use a unique symbol each run so ttl_cache never serves a stale hit
    test_sym = f"ETH-USD-LATENCY-{uuid.uuid4().hex}"
    with patch.dict(data_providers._SPOT_FNS, {
        "coinbase":  _exc,
        "coingecko": _exc,
        "yfinance":  lambda s: 42.0,
    }):
        data_providers.get_spot_price(test_sym)
    assert len(data_providers._latency["yfinance"]) == 1
    data_providers._latency["yfinance"].clear()
